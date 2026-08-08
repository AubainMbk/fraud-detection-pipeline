-- Modèle Gold : features prêtes pour le scoring fraude
-- Reprend exactement la logique de sql/02_create_gold_features.sql,
-- avec transaction_type encodé en one-hot pour rester cohérent
-- avec ce qu'attend le modèle entraîné.

with base as (
    select * from {{ ref('stg_transactions') }}
)

select
    transaction_id,
    transaction_ts,
    transaction_type,
    amount,
    name_orig,
    name_dest,
    is_fraud,

    (oldbalance_org - amount - newbalance_orig) as balance_error_orig,
    (oldbalance_dest + amount - newbalance_dest) as balance_error_dest,

    case when name_dest like 'M%' then true else false end as is_merchant_dest,
    extract(hour from transaction_ts)::int as hour_of_day,
    case when oldbalance_org = 0 then null else amount / oldbalance_org end as amount_to_oldbalance_ratio,

    case when transaction_type = 'CASH_IN' then 1 else 0 end as type_cash_in,
    case when transaction_type = 'CASH_OUT' then 1 else 0 end as type_cash_out,
    case when transaction_type = 'DEBIT' then 1 else 0 end as type_debit,
    case when transaction_type = 'PAYMENT' then 1 else 0 end as type_payment,
    case when transaction_type = 'TRANSFER' then 1 else 0 end as type_transfer,

    count(*) over w1h as txn_count_1h_orig,
    coalesce(sum(amount) over w1h, 0) as txn_sum_amount_1h_orig,
    count(*) over w24h as txn_count_24h_orig

from base
window
    w1h as (
        partition by name_orig
        order by transaction_ts
        range between interval '1 hour' preceding and interval '1 microsecond' preceding
    ),
    w24h as (
        partition by name_orig
        order by transaction_ts
        range between interval '24 hours' preceding and interval '1 microsecond' preceding
    )