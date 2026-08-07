"""
Entraîne un modèle baseline de scoring fraude à partir des features Gold (dbt).
Split temporel + métriques adaptées au déséquilibre de classes.
Chaque run est tracé dans MLflow : hyperparamètres, métriques, et modèle versionné.
"""
import logging
import os

import joblib
import mlflow
import mlflow.sklearn
import mlflow.xgboost
import pandas as pd
from dotenv import load_dotenv
from mlflow import MlflowClient
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
)
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine
from xgboost import XGBClassifier

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("fraud_detection_baseline")

TRANSACTION_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]

FEATURE_COLUMNS = [
    "amount", "balance_error_orig", "balance_error_dest", "is_merchant_dest",
    "hour_of_day", "amount_to_oldbalance_ratio",
    "txn_count_1h_orig", "txn_sum_amount_1h_orig", "txn_count_24h_orig",
] + [f"type_{t}" for t in TRANSACTION_TYPES]
TARGET_COLUMN = "is_fraud"
MODEL_OUTPUT_PATH = "models/fraud_baseline_xgb.joblib"
REGISTERED_MODEL_NAME = "fraud_xgboost"


def get_engine():
    url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
        f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    return create_engine(url)


def load_features(engine) -> pd.DataFrame:
    logger.info("Chargement des features depuis dbt_gold.fct_transaction_features...")
    base_cols = [c for c in FEATURE_COLUMNS if not c.startswith("type_")]
    query = f"""
        SELECT transaction_ts, transaction_type, {", ".join(base_cols)}, {TARGET_COLUMN}
        FROM dbt_gold.fct_transaction_features
        ORDER BY transaction_ts
    """
    df = pd.read_sql(query, engine)
    df["amount_to_oldbalance_ratio"] = df["amount_to_oldbalance_ratio"].fillna(0)
    df["is_merchant_dest"] = df["is_merchant_dest"].astype(int)
    for t in TRANSACTION_TYPES:
        df[f"type_{t}"] = (df["transaction_type"] == t).astype(int)
    return df


def temporal_split(df: pd.DataFrame, test_size: float = 0.2):
    split_index = int(len(df) * (1 - test_size))
    train_df = df.iloc[:split_index]
    test_df = df.iloc[split_index:]
    logger.info(f"Train: {len(train_df)} lignes | Test: {len(test_df)} lignes")
    return train_df, test_df


def compute_metrics(y_test, y_proba, threshold: float = 0.5) -> dict:
    y_pred = (y_proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    return {
        "pr_auc": average_precision_score(y_test, y_proba),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "precision": tp / (tp + fp) if (tp + fp) > 0 else 0,
        "recall": tp / (tp + fn) if (tp + fn) > 0 else 0,
    }


def main():
    engine = get_engine()
    df = load_features(engine)
    train_df, test_df = temporal_split(df)

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN]
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[TARGET_COLUMN]

    fraud_ratio = y_train.mean()
    scale_pos_weight = (1 - fraud_ratio) / fraud_ratio

    # ---- Run 1 : baseline interprétable (régression logistique) ----
    with mlflow.start_run(run_name="logistic_regression"):
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        params = {"class_weight": "balanced", "max_iter": 1000}
        mlflow.log_params(params)
        mlflow.log_param("model_type", "LogisticRegression")
        mlflow.log_param("n_features", len(FEATURE_COLUMNS))

        logreg = LogisticRegression(**params)
        logreg.fit(X_train_scaled, y_train)

        y_proba = logreg.predict_proba(X_test_scaled)[:, 1]
        metrics = compute_metrics(y_test, y_proba)
        mlflow.log_metrics(metrics)

        mlflow.sklearn.log_model(logreg, "model")
        logger.info(f"[LogisticRegression] PR-AUC: {metrics['pr_auc']:.4f}")

    # ---- Run 2 : XGBoost, enregistré dans le Model Registry ----
    with mlflow.start_run(run_name="xgboost") as run:
        params = {
            "n_estimators": 200,
            "max_depth": 5,
            "learning_rate": 0.1,
            "scale_pos_weight": scale_pos_weight,
        }
        mlflow.log_params(params)
        mlflow.log_param("model_type", "XGBClassifier")
        mlflow.log_param("n_features", len(FEATURE_COLUMNS))
        mlflow.log_param("decision_threshold", 0.65)

        xgb_model = XGBClassifier(**params, eval_metric="aucpr", random_state=42)
        xgb_model.fit(X_train, y_train)

        y_proba = xgb_model.predict_proba(X_test)[:, 1]
        metrics_default = compute_metrics(y_test, y_proba, threshold=0.5)
        metrics_chosen = compute_metrics(y_test, y_proba, threshold=0.65)
        mlflow.log_metrics({f"{k}_at_0.5": v for k, v in metrics_default.items()})
        mlflow.log_metrics({f"{k}_at_0.65": v for k, v in metrics_chosen.items()})
        mlflow.log_metric("pr_auc", metrics_default["pr_auc"])

        mlflow.xgboost.log_model(
            xgb_model, "model", registered_model_name=REGISTERED_MODEL_NAME
        )
        logger.info(f"[XGBoost] PR-AUC: {metrics_default['pr_auc']:.4f}")
        logger.info(f"[XGBoost @ seuil 0.65] {metrics_chosen}")

        run_id = run.info.run_id

    # ---- Sauvegarde locale (compatibilité avec l'API actuelle) ----
    os.makedirs("models", exist_ok=True)
    joblib.dump({"model": xgb_model, "features": FEATURE_COLUMNS}, MODEL_OUTPUT_PATH)
    logger.info(f"Modèle sauvegardé localement -> {MODEL_OUTPUT_PATH}")

    # ---- Attribution de l'alias "champion" à cette version dans le Registry ----
    client = MlflowClient()
    model_version = client.search_model_versions(f"run_id='{run_id}'")[0].version
    client.set_registered_model_alias(REGISTERED_MODEL_NAME, "champion", model_version)
    logger.info(f"Alias 'champion' attribué à la version {model_version} de '{REGISTERED_MODEL_NAME}'")


if __name__ == "__main__":
    main()
