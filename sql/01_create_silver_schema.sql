-- Schéma Silver : données nettoyées et typées, prêtes pour l'analytique
CREATE SCHEMA IF NOT EXISTS silver;

CREATE TABLE IF NOT EXISTS silver.transactions (
    transaction_id      BIGSERIAL PRIMARY KEY,
    step                INTEGER NOT NULL,
    transaction_ts       TIMESTAMP NOT NULL,
    transaction_type     VARCHAR(20) NOT NULL,
    amount               NUMERIC(18, 2) NOT NULL,
    name_orig            VARCHAR(50) NOT NULL,
    oldbalance_org        NUMERIC(18, 2) NOT NULL,
    newbalance_orig       NUMERIC(18, 2) NOT NULL,
    name_dest            VARCHAR(50) NOT NULL,
    oldbalance_dest       NUMERIC(18, 2) NOT NULL,
    newbalance_dest       NUMERIC(18, 2) NOT NULL,
    is_fraud             BOOLEAN NOT NULL,
    is_flagged_fraud       BOOLEAN NOT NULL,
    ingestion_date        DATE NOT NULL,
    source_file           VARCHAR(255) NOT NULL,
    loaded_at             TIMESTAMP NOT NULL DEFAULT now()
);

-- Index pour les futures requêtes analytiques (feature engineering)
CREATE INDEX IF NOT EXISTS idx_transactions_name_orig ON silver.transactions(name_orig);
CREATE INDEX IF NOT EXISTS idx_transactions_name_dest ON silver.transactions(name_dest);
CREATE INDEX IF NOT EXISTS idx_transactions_ts ON silver.transactions(transaction_ts);
CREATE INDEX IF NOT EXISTS idx_transactions_is_fraud ON silver.transactions(is_fraud);

-- Contrainte d'unicité pour garantir l'idempotence du chargement
CREATE UNIQUE INDEX IF NOT EXISTS uniq_transaction_natural_key
    ON silver.transactions(step, name_orig, name_dest, amount, transaction_type);