"""
Ingestion d'un fichier source vers la raw zone (MinIO).
Convention de nommage: raw/<source>/ingestion_date=<YYYY-MM-DD>/<filename>
Cette convention permet de tracer QUAND chaque lot de données est arrivé,
et de rejouer facilement le pipeline pour une date donnée.
"""
import hashlib
import os
from datetime import date

import boto3
from dotenv import load_dotenv

load_dotenv()

s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
)

BUCKET = os.getenv("MINIO_BUCKET_RAW")
SOURCE_NAME = "paysim"
LOCAL_FILE = "data/raw/paysim.csv"


def compute_sha256(filepath: str) -> str:
    """Calcule le hash SHA256 du fichier pour vérifier son intégrité après upload."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def ingest_file(local_path: str, source_name: str):
    ingestion_date = date.today().isoformat()
    filename = os.path.basename(local_path)
    s3_key = f"{source_name}/ingestion_date={ingestion_date}/{filename}"

    print(f"Calcul du hash de contrôle pour {local_path}...")
    file_hash = compute_sha256(local_path)

    print(f"Upload vers s3://{BUCKET}/{s3_key} ...")
    s3_client.upload_file(local_path, BUCKET, s3_key)

    # On stocke le hash en métadonnée de l'objet, consultable a posteriori
    s3_client.put_object_tagging(
        Bucket=BUCKET,
        Key=s3_key,
        Tagging={"TagSet": [{"Key": "sha256", "Value": file_hash}]},
    )

    print(f"Ingestion terminée. Hash: {file_hash}")
    return s3_key


if __name__ == "__main__":
    ingest_file(LOCAL_FILE, SOURCE_NAME)
