"""
Consumer temps réel : lit le flux de transactions depuis Redpanda,
calcule les features, appelle l'API de scoring, journalise la décision.

Réutilise api.features.compute_features() pour éviter une troisième
duplication de la logique de feature engineering (voir note dans api/features.py).
"""
import json
import logging
import os
import sys
import time

import psycopg2
import requests
from dotenv import load_dotenv
from kafka import KafkaConsumer

# Permet d'importer le module api/ depuis la racine du projet
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "transactions.raw"
CONSUMER_GROUP = "fraud-scoring-consumer"
SCORING_API_URL = "http://localhost:8000/score"


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def score_transaction(txn: dict) -> dict:
    """Appelle l'API de scoring. On retire explicitement le champ de validation
    interne avant l'envoi -- l'API ne doit jamais voir cette information,
    exactement comme en production."""
    payload = {k: v for k, v in txn.items() if k != "is_synthetic_fraud_injection"}
    start = time.perf_counter()
    response = requests.post(SCORING_API_URL, json=payload, timeout=5)
    latency_ms = (time.perf_counter() - start) * 1000
    response.raise_for_status()
    return response.json(), latency_ms


def persist_score(conn, txn: dict, result: dict, latency_ms: float):
    query = """
        INSERT INTO streaming.scored_transactions (
            transaction_ts, transaction_type, amount, name_orig, name_dest,
            fraud_probability, is_fraud_predicted, decision_threshold,
            model_version, scoring_latency_ms, is_synthetic_fraud_injection
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(query, (
            txn["transaction_ts"], txn["transaction_type"], txn["amount"],
            txn["name_orig"], txn["name_dest"],
            result["fraud_probability"], result["is_fraud_predicted"],
            result["decision_threshold"], result["model_version"],
            round(latency_ms, 2), txn.get("is_synthetic_fraud_injection"),
        ))
    conn.commit()


def main():
    consumer = KafkaConsumer(
        TOPIC_NAME,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    conn = get_pg_connection()

    logger.info(f"Consumer démarré -> écoute '{TOPIC_NAME}' (groupe: {CONSUMER_GROUP})")

    true_positives = false_negatives = 0

    try:
        for message in consumer:
            txn = message.value
            try:
                result, latency_ms = score_transaction(txn)
            except requests.exceptions.RequestException as e:
                logger.error(f"Échec appel API scoring: {e}")
                continue

            persist_score(conn, txn, result, latency_ms)

            was_injected_fraud = txn.get("is_synthetic_fraud_injection", False)
            detected = result["is_fraud_predicted"]

            if was_injected_fraud:
                if detected:
                    true_positives += 1
                    status = "DETECTEE"
                else:
                    false_negatives += 1
                    status = "MANQUEE"
                logger.warning(
                    f"[FRAUDE INJECTEE - {status}] {txn['name_orig']} -> {txn['name_dest']} "
                    f"| proba={result['fraud_probability']} | latence={latency_ms:.1f}ms"
                )
            elif detected:
                logger.info(
                    f"[ALERTE] {txn['name_orig']} -> {txn['name_dest']} "
                    f"| proba={result['fraud_probability']} | latence={latency_ms:.1f}ms"
                )

    except KeyboardInterrupt:
        logger.info("Arrêt demandé (Ctrl+C).")
        total = true_positives + false_negatives
        if total > 0:
            logger.info(
                f"Bilan session: {true_positives}/{total} fraudes injectées détectées "
                f"({true_positives / total:.1%})"
            )
    finally:
        conn.close()
        consumer.close()


if __name__ == "__main__":
    main()
