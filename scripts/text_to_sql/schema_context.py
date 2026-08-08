"""Description du schéma exposé au LLM pour la génération de SQL.
Volontairement limité aux deux tables autorisées (voir sql_guardrails.py)."""

SCHEMA_DESCRIPTION = """
Table: dbt_gold.fct_transaction_features
Une ligne par transaction historique, avec son label de fraude et ses features.
Colonnes :
- transaction_id (bigint)
- transaction_ts (timestamp)
- transaction_type (text : CASH_IN, CASH_OUT, DEBIT, PAYMENT, TRANSFER)
- amount (numeric) -- montant de la transaction
- name_orig (text) -- compte émetteur
- name_dest (text) -- compte destinataire
- is_fraud (boolean) -- vérité terrain (fraude confirmée ou non)
- balance_error_orig (numeric) -- écart de solde côté émetteur
- is_merchant_dest (boolean) -- destinataire marchand ou particulier
- hour_of_day (int)

Table: streaming.scored_transactions
Une ligne par transaction scorée en temps réel par l'API.
Colonnes :
- id (bigint)
- transaction_ts (timestamptz)
- scored_at (timestamptz) -- moment où le scoring a eu lieu
- transaction_type (text)
- amount (numeric)
- name_orig (text)
- name_dest (text)
- fraud_probability (numeric) -- probabilité prédite par le modèle (0 à 1)
- is_fraud_predicted (boolean) -- décision finale après application du seuil
- decision_threshold (numeric)
- model_version (text)
- scoring_latency_ms (numeric)
"""
