-- sql/03_create_streaming_scores.sql
CREATE SCHEMA IF NOT EXISTS streaming;

CREATE TABLE IF NOT EXISTS streaming.scored_transactions (
    id                      BIGSERIAL PRIMARY KEY,
    transaction_ts           TIMESTAMPTZ NOT NULL,
    scored_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    transaction_type          VARCHAR(20) NOT NULL,
    amount                    NUMERIC(18, 2) NOT NULL,
    name_orig                 VARCHAR(50) NOT NULL,
    name_dest                 VARCHAR(50) NOT NULL,
    fraud_probability          NUMERIC(6, 4) NOT NULL,
    is_fraud_predicted         BOOLEAN NOT NULL,
    decision_threshold         NUMERIC(4, 2) NOT NULL,
    model_version              VARCHAR(50) NOT NULL,
    scoring_latency_ms          NUMERIC(10, 2) NOT NULL,
    -- Colonne réservée à la VALIDATION LOCALE du pipeline uniquement.
    -- En production, ce label n'existerait jamais au moment du scoring
    -- (c'est justement ce que le modèle essaie de prédire).
    is_synthetic_fraud_injection BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_streaming_scored_at ON streaming.scored_transactions(scored_at);
CREATE INDEX IF NOT EXISTS idx_streaming_is_fraud_predicted ON streaming.scored_transactions(is_fraud_predicted);