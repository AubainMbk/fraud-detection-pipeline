"""
Transformation Bronze -> Silver.
Lit le fichier brut depuis MinIO, applique le nettoyage/typage,
et charge le résultat dans Postgres par lots (chunks), de manière idempotente.
"""
import io
import logging
import os
from datetime import date, timedelta

import boto3
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

BUCKET = os.getenv("MINIO_BUCKET_RAW")
SOURCE_NAME = "paysim"
CHUNK_SIZE = 100_000  # nombre de lignes traitées par lot

# PaySim n'a pas de vraies dates, seulement des "steps" (1 step = 1 heure simulée).
# On choisit une date de référence arbitraire pour transformer step -> timestamp réel.
SIMULATION_START = date(2024, 1, 1)

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)


def get_latest_raw_key(bucket: str, source: str) -> str:
    """Trouve le fichier le plus récemment ingéré dans la raw zone pour cette source."""
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=f"{source}/")
    objects = response.get("Contents", [])
    if not objects:
        raise FileNotFoundError(f"Aucun fichier trouvé pour la source '{source}'")
    latest = max(objects, key=lambda obj: obj["LastModified"])
    return latest["Key"]


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def transform_chunk(chunk: pd.DataFrame, source_file: str, ingestion_date: str) -> pd.DataFrame:
    """Nettoie et type un chunk brut PaySim vers le schéma Silver."""
    chunk = chunk.copy()

    # Renommage vers nos conventions (snake_case, cohérent avec le schéma SQL)
    chunk = chunk.rename(columns={
        "type": "transaction_type",
        "nameOrig": "name_orig",
        "oldbalanceOrg": "oldbalance_org",
        "newbalanceOrig": "newbalance_orig",
        "nameDest": "name_dest",
        "oldbalanceDest": "oldbalance_dest",
        "newbalanceDest": "newbalance_dest",
        "isFraud": "is_fraud",
        "isFlaggedFraud": "is_flagged_fraud",
    })

    # step (heures écoulées) -> vrai timestamp
    chunk["transaction_ts"] = chunk["step"].apply(
        lambda h: pd.Timestamp(SIMULATION_START) + timedelta(hours=int(h))
    )

    # Typage explicite : NUMERIC en base, donc float propre côté Python (jamais de string)
    numeric_cols = ["amount", "oldbalance_org", "newbalance_orig", "oldbalance_dest", "newbalance_dest"]
    for col in numeric_cols:
        chunk[col] = pd.to_numeric(chunk[col], errors="coerce")

    chunk["is_fraud"] = chunk["is_fraud"].astype(bool)
    chunk["is_flagged_fraud"] = chunk["is_flagged_fraud"].astype(bool)
    chunk["ingestion_date"] = ingestion_date
    chunk["source_file"] = source_file

    return chunk


def run_quality_checks(chunk: pd.DataFrame) -> dict:
    """Contrôles qualité de base. En pratique, on tracerait ces métriques dans un outil
    dédié (ex: Great Expectations), mais le principe est le même : on mesure avant de charger."""
    return {
        "rows": len(chunk),
        "null_amounts": int(chunk["amount"].isna().sum()),
        "negative_amounts": int((chunk["amount"] < 0).sum()),
        "fraud_count": int(chunk["is_fraud"].sum()),
    }


def load_chunk_to_postgres(conn, chunk: pd.DataFrame):
    """Charge un chunk dans silver.transactions avec ON CONFLICT DO NOTHING (idempotence)."""
    columns = [
        "step", "transaction_ts", "transaction_type", "amount",
        "name_orig", "oldbalance_org", "newbalance_orig",
        "name_dest", "oldbalance_dest", "newbalance_dest",
        "is_fraud", "is_flagged_fraud", "ingestion_date", "source_file",
    ]
    records = chunk[columns].values.tolist()

    query = f"""
        INSERT INTO silver.transactions ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (step, name_orig, name_dest, amount, transaction_type)
        DO NOTHING
    """
    with conn.cursor() as cur:
        execute_values(cur, query, records, page_size=1000)
    conn.commit()


def main():
    raw_key = get_latest_raw_key(BUCKET, SOURCE_NAME)
    logger.info(f"Fichier source sélectionné : {raw_key}")

    obj = s3_client.get_object(Bucket=BUCKET, Key=raw_key)
    raw_bytes = obj["Body"].read()

    ingestion_date = date.today().isoformat()
    conn = get_pg_connection()

    total_rows = 0
    total_fraud = 0

    try:
        reader = pd.read_csv(io.BytesIO(raw_bytes), chunksize=CHUNK_SIZE)
        for i, chunk in enumerate(reader):
            clean_chunk = transform_chunk(chunk, raw_key, ingestion_date)
            metrics = run_quality_checks(clean_chunk)

            if metrics["null_amounts"] > 0 or metrics["negative_amounts"] > 0:
                logger.warning(f"Chunk {i}: anomalies détectées -> {metrics}")
            else:
                logger.info(f"Chunk {i}: OK -> {metrics}")

            load_chunk_to_postgres(conn, clean_chunk)
            total_rows += metrics["rows"]
            total_fraud += metrics["fraud_count"]

        logger.info(f"Chargement terminé : {total_rows} lignes traitées, {total_fraud} fraudes.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
