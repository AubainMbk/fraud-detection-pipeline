-- Modèle staging : point d'entrée propre sur silver.transactions
-- Convention dbt : cette couche ne fait que sélectionner/renommer, pas de logique métier

select
    transaction_id,
    transaction_ts,
    transaction_type,
    amount,
    name_orig,
    oldbalance_org,
    newbalance_orig,
    name_dest,
    oldbalance_dest,
    newbalance_dest,
    is_fraud,
    is_flagged_fraud
from {{ source('bronze_silver', 'transactions') }}