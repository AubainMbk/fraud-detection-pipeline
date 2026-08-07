"""Affiche l'importance de chaque feature dans le modèle entraîné."""
import joblib
import pandas as pd

bundle = joblib.load("models/fraud_baseline_xgb.joblib")
model, features = bundle["model"], bundle["features"]

importances = pd.DataFrame({
    "feature": features,
    "importance": model.feature_importances_,
}).sort_values("importance", ascending=False)

print(importances.to_string(index=False))
