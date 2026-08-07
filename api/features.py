"""
Calcul des features synchrones (celles ne nécessitant aucun historique).
ATTENTION - dette technique assumée : cette logique duplique celle du SQL/entraînement.
Voir note dans le README projet sur le risque de training-serving skew.
"""
from api.schemas import TransactionRequest

TRANSACTION_TYPES = ["CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER"]


def compute_features(txn: TransactionRequest) -> dict:
    balance_error_orig = txn.oldbalance_org - txn.amount - txn.newbalance_orig
    balance_error_dest = txn.oldbalance_dest + txn.amount - txn.newbalance_dest
    is_merchant_dest = 1 if txn.name_dest.startswith("M") else 0
    hour_of_day = txn.transaction_ts.hour
    amount_to_oldbalance_ratio = (
        txn.amount / txn.oldbalance_org if txn.oldbalance_org > 0 else 0
    )

    features = {
        "amount": txn.amount,
        "balance_error_orig": balance_error_orig,
        "balance_error_dest": balance_error_dest,
        "is_merchant_dest": is_merchant_dest,
        "hour_of_day": hour_of_day,
        "amount_to_oldbalance_ratio": amount_to_oldbalance_ratio,
        "txn_count_1h_orig": 0,
        "txn_sum_amount_1h_orig": 0,
        "txn_count_24h_orig": 0,
    }

    for t in TRANSACTION_TYPES:
        features[f"type_{t}"] = 1 if txn.transaction_type == t else 0

    return features
