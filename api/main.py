"""API de scoring fraude temps réel."""
import logging

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException

from api.config import DECISION_THRESHOLD, MODEL_PATH, MODEL_VERSION
from api.features import compute_features
from api.schemas import ScoringResponse, TransactionRequest

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Fraud Scoring API",
    description="Scoring temps réel des transactions bancaires",
    version=MODEL_VERSION,
)

_bundle = None


@app.on_event("startup")
def load_model():
    global _bundle
    logger.info(f"Chargement du modèle depuis {MODEL_PATH}")
    _bundle = joblib.load(MODEL_PATH)
    logger.info(f"Modèle chargé. Seuil de décision actif: {DECISION_THRESHOLD}")


@app.get("/health")
def health_check():
    return {"status": "ok", "model_version": MODEL_VERSION, "model_loaded": _bundle is not None}


@app.post("/score", response_model=ScoringResponse)
def score_transaction(txn: TransactionRequest):
    if _bundle is None:
        raise HTTPException(status_code=503, detail="Modèle non chargé")

    features_dict = compute_features(txn)
    features_df = pd.DataFrame([features_dict])[_bundle["features"]]

    proba = _bundle["model"].predict_proba(features_df)[0, 1]
    is_fraud = bool(proba >= DECISION_THRESHOLD)

    logger.info(
        f"Transaction scorée | orig={txn.name_orig} | proba={proba:.4f} | decision={is_fraud}"
    )

    return ScoringResponse(
        is_fraud_predicted=is_fraud,
        fraud_probability=round(float(proba), 4),
        decision_threshold=DECISION_THRESHOLD,
        model_version=MODEL_VERSION,
    )
