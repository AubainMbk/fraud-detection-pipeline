"""Configuration centralisée de l'API de scoring."""
import os

from dotenv import load_dotenv

load_dotenv()

MODEL_PATH = os.getenv("MODEL_PATH", "models/fraud_baseline_xgb.joblib")
DECISION_THRESHOLD = float(os.getenv("DECISION_THRESHOLD", "0.30"))
MODEL_VERSION = os.getenv("MODEL_VERSION", "baseline_xgb_v1")
