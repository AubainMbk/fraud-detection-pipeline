"""
Sélection du seuil de décision optimal selon un arbitrage coût métier.
Coût d'une fraude manquée = montant moyen de fraude non détectée.
Coût d'une fausse alerte = coût forfaitaire d'investigation par un analyste.
"""
import os

import joblib
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import precision_recall_curve
from sqlalchemy import create_engine

load_dotenv()

INVESTIGATION_COST = 15
FRAUD_AVG_AMOUNT = 1_467_967

TRANSACTION_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

BASE_COLUMNS = [
    "amount",
    "balance_error_orig",
    "balance_error_dest",
    "is_merchant_dest",
    "hour_of_day",
    "amount_to_oldbalance_ratio",
    "txn_count_1h_orig",
    "txn_sum_amount_1h_orig",
    "txn_count_24h_orig",
]


def get_engine():
    url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(url)


bundle = joblib.load("models/fraud_baseline_xgb.joblib")
model, features = bundle["model"], bundle["features"]

engine = get_engine()
df = pd.read_sql(
    f"SELECT transaction_ts, transaction_type, {', '.join(BASE_COLUMNS)}, is_fraud "
    f"FROM gold.transaction_features ORDER BY transaction_ts",
    engine,
)
df["amount_to_oldbalance_ratio"] = df["amount_to_oldbalance_ratio"].fillna(0)
df["is_merchant_dest"] = df["is_merchant_dest"].astype(int)

# Même encodage one-hot que dans train_baseline_model.py -- doit toujours rester identique
for t in TRANSACTION_TYPES:
    df[f"type_{t}"] = (df["transaction_type"] == t).astype(int)

split_index = int(len(df) * 0.8)
test_df = df.iloc[split_index:]
X_test, y_test = test_df[features], test_df["is_fraud"]

y_proba = model.predict_proba(X_test)[:, 1]
precision, recall, thresholds = precision_recall_curve(y_test, y_proba)

print(f"{'seuil':>8} | {'precision':>10} | {'recall':>8} | {'cout_estime_eur':>16}")
print("-" * 55)
for t in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
    y_pred = (y_proba >= t).astype(int)
    tp = ((y_pred == 1) & (y_test == 1)).sum()
    fp = ((y_pred == 1) & (y_test == 0)).sum()
    fn = ((y_pred == 0) & (y_test == 1)).sum()

    cost = fn * FRAUD_AVG_AMOUNT + fp * INVESTIGATION_COST
    p = tp / (tp + fp) if (tp + fp) > 0 else 0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0
    print(f"{t:8.2f} | {p:10.3f} | {r:8.3f} | {cost:16,.0f}")
