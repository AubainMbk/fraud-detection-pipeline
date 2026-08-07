"""
Générateur de transactions bancaires en streaming, publié sur Redpanda (API Kafka).

Principe : on interroge Postgres au démarrage pour récupérer les distributions
statistiques réelles (proportions par type, ordres de grandeur des montants),
puis on génère des transactions synthétiques qui respectent ces distributions
plutôt que du pur aléatoire uniforme -- pour un flux réaliste.

Simplification assumée : les montants sont modélisés par une loi log-normale
approximée à partir de la moyenne/écart-type observés. Un vrai projet ferait un
fit de distribution plus rigoureux, mais c'est suffisant pour démontrer le pipeline.
"""
import json
import logging
import os
import random
import time
from datetime import datetime, timezone

import numpy as np
import psycopg2
from dotenv import load_dotenv
from kafka import KafkaProducer

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC_NAME = "transactions.raw"
FRAUD_INJECTION_RATE = 0.02  # 2% des transactions simulent un pattern de fraude connu
EMIT_INTERVAL_SECONDS = 1.0
NUM_SYNTHETIC_ACCOUNTS = 500


def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def load_real_distributions():
    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT transaction_type, COUNT(*), AVG(amount), STDDEV(amount)
        FROM silver.transactions
        GROUP BY transaction_type
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    total = sum(r[1] for r in rows)
    distributions = {}
    for txn_type, count, avg_amount, std_amount in rows:
        distributions[txn_type] = {
            "weight": count / total,
            "avg_amount": float(avg_amount),
            "std_amount": float(std_amount) if std_amount else float(avg_amount) * 0.5,
        }
    logger.info(f"Distributions chargées: {list(distributions.keys())}")
    return distributions


def sample_amount(txn_type: str, distributions: dict) -> float:
    stats = distributions[txn_type]
    mean, std = stats["avg_amount"], stats["std_amount"]
    sigma = np.sqrt(np.log(1 + (std ** 2) / (mean ** 2)))
    mu = np.log(mean) - (sigma ** 2) / 2
    amount = np.random.lognormal(mean=mu, sigma=sigma)
    return round(max(amount, 1.0), 2)


def sample_transaction_type(distributions: dict) -> str:
    types = list(distributions.keys())
    weights = [distributions[t]["weight"] for t in types]
    return random.choices(types, weights=weights, k=1)[0]


class AccountPool:
    """État en mémoire de comptes synthétiques (id + solde), pour générer
    des transactions cohérentes (soldes avant/après réalistes)."""

    def __init__(self, n_accounts: int):
        self.accounts = {
            f"C{random.randint(10**9, 10**10 - 1)}": round(random.uniform(500, 50_000), 2)
            for _ in range(n_accounts)
        }

    def random_account(self, exclude: str = None) -> str:
        choices = [a for a in self.accounts if a != exclude]
        return random.choice(choices)

    def get_balance(self, account_id: str) -> float:
        return self.accounts.get(account_id, 0.0)

    def apply_transfer(self, orig: str, dest: str, amount: float):
        self.accounts[orig] = max(self.accounts.get(orig, 0.0) - amount, 0.0)
        self.accounts[dest] = self.accounts.get(dest, 0.0) + amount


def build_legitimate_transaction(pool: AccountPool, distributions: dict) -> dict:
    txn_type = sample_transaction_type(distributions)
    amount = sample_amount(txn_type, distributions)

    orig = pool.random_account()
    dest = pool.random_account(exclude=orig)

    oldbalance_org = pool.get_balance(orig)
    amount = min(amount, oldbalance_org * 0.9) if oldbalance_org > 0 else amount
    newbalance_orig = round(max(oldbalance_org - amount, 0.0), 2)

    oldbalance_dest = pool.get_balance(dest)
    newbalance_dest = round(oldbalance_dest + amount, 2)

    pool.apply_transfer(orig, dest, amount)

    return {
        "transaction_type": txn_type,
        "amount": amount,
        "name_orig": orig,
        "oldbalance_org": oldbalance_org,
        "newbalance_orig": newbalance_orig,
        "name_dest": dest,
        "oldbalance_dest": oldbalance_dest,
        "newbalance_dest": newbalance_dest,
        "transaction_ts": datetime.now(timezone.utc).isoformat(),
        "is_synthetic_fraud_injection": False,
    }


def build_fraud_transaction(pool: AccountPool) -> dict:
    """Reproduit le pattern de fraude identifié : compte vidé intégralement."""
    txn_type = random.choice(["TRANSFER", "CASH_OUT"])
    orig = pool.random_account()
    dest = pool.random_account(exclude=orig)

    oldbalance_org = pool.get_balance(orig)
    amount = oldbalance_org
    newbalance_orig = 0.0

    oldbalance_dest = pool.get_balance(dest)
    newbalance_dest = round(oldbalance_dest + amount, 2)

    pool.apply_transfer(orig, dest, amount)

    return {
        "transaction_type": txn_type,
        "amount": round(amount, 2),
        "name_orig": orig,
        "oldbalance_org": oldbalance_org,
        "newbalance_orig": newbalance_orig,
        "name_dest": dest,
        "oldbalance_dest": oldbalance_dest,
        "newbalance_dest": newbalance_dest,
        "transaction_ts": datetime.now(timezone.utc).isoformat(),
        "is_synthetic_fraud_injection": True,  # usage interne uniquement, jamais envoyé au scoring réel
    }


def main():
    distributions = load_real_distributions()
    pool = AccountPool(NUM_SYNTHETIC_ACCOUNTS)

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )

    logger.info(f"Démarrage du générateur -> topic '{TOPIC_NAME}' sur {KAFKA_BOOTSTRAP}")
    sent = 0
    try:
        while True:
            if random.random() < FRAUD_INJECTION_RATE:
                txn = build_fraud_transaction(pool)
                logger.info(f"[FRAUD INJECTÉE] {txn['name_orig']} -> {txn['name_dest']} | {txn['amount']}")
            else:
                txn = build_legitimate_transaction(pool, distributions)

            producer.send(TOPIC_NAME, key=txn["name_orig"], value=txn)
            sent += 1
            if sent % 20 == 0:
                logger.info(f"{sent} transactions émises.")

            time.sleep(EMIT_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé (Ctrl+C).")
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()
