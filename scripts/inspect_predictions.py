"""
Diagnostic : compare la distribution des probabilités prédites sur les vraies
fraudes du test set à notre transaction synthétique, pour comprendre l'écart observé.
"""
import os

import joblib
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

TRANSACTION_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]
BASE_COLUMNS = [
    "amount", "balance_error_orig", "balance_error_dest", "is_merchant_dest",
    "hour_of_day", "amount_to_oldbalance_ratio",
    "txn_count_1h_orig", "txn_sum_amount_1h_orig", "txn_count_24h_orig",
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
for t in TRANSACTION_TYPES:
    df[f"type_{t}"] = (df["transaction_type"] == t).astype(int)

split_index = int(len(df) * 0.8)
test_df = df.iloc[split_index:].copy()

X_test = test_df[features]
test_df["proba"] = model.predict_proba(X_test)[:, 1]

fraud_test = test_df[test_df["is_fraud"] == 1]

print("=== Distribution des probabilités sur les VRAIES fraudes du test set ===")
print(fraud_test["proba"].describe())
print(f"\nNombre de vraies fraudes scorées < 0.65 : {(fraud_test['proba'] < 0.65).sum()} / {len(fraud_test)}")

print("\n=== Profil moyen d'une vraie fraude TRANSFER ===")
transfer_fraud = fraud_test[fraud_test["transaction_type"] == "TRANSFER"]
print(transfer_fraud[BASE_COLUMNS].describe().loc[["mean", "50%"]])

print("\n=== Notre transaction synthétique (rappel) ===")
synthetic = {
    "amount": 250000.0, "balance_error_orig": 0.0, "balance_error_dest": 0.0,
    "is_merchant_dest": 0, "hour_of_day": 14, "amount_to_oldbalance_ratio": 1.0,
}
print(pd.Series(synthetic))
