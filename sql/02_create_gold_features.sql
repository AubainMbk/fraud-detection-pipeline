-- Zone Gold : features prêtes pour le modèle de scoring fraude
CREATE SCHEMA IF NOT EXISTS gold;

DROP TABLE IF EXISTS gold.transaction_features;

CREATE TABLE gold.transaction_features AS
SELECT
    transaction_id,
    transaction_ts,
    transaction_type,
    amount,
    name_orig,
    name_dest,
    is_fraud,

    -- Cohérence comptable : écart entre solde attendu et solde réel
    -- Un écart significatif (souvent proche de 0 exactement chez les fraudeurs
    -- qui vident un compte) est un signal fort
    (oldbalance_org - amount - newbalance_orig) AS balance_error_orig,
    (oldbalance_dest + amount - newbalance_dest) AS balance_error_dest,

    -- Contexte
    CASE WHEN name_dest LIKE 'M%' THEN TRUE ELSE FALSE END AS is_merchant_dest,
    EXTRACT(HOUR FROM transaction_ts)::INT AS hour_of_day,
    CASE WHEN oldbalance_org = 0 THEN NULL ELSE amount / oldbalance_org END AS amount_to_oldbalance_ratio,

    -- Vélocité : fenêtres STRICTEMENT passées (pas de fuite de données)
    -- On exclut la transaction courante via la borne "1 microsecond preceding"
    COUNT(*) OVER w1h AS txn_count_1h_orig,
    COALESCE(SUM(amount) OVER w1h, 0) AS txn_sum_amount_1h_orig,
    COUNT(*) OVER w24h AS txn_count_24h_orig

FROM silver.transactions
WINDOW
    w1h AS (
        PARTITION BY name_orig
        ORDER BY transaction_ts
        RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND INTERVAL '1 microsecond' PRECEDING
    ),
    w24h AS (
        PARTITION BY name_orig
        ORDER BY transaction_ts
        RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND INTERVAL '1 microsecond' PRECEDING
    );

CREATE INDEX idx_gold_is_fraud ON gold.transaction_features(is_fraud);
CREATE INDEX idx_gold_transaction_ts ON gold.transaction_features(transaction_ts);