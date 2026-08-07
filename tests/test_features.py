"""
Tests unitaires sur le calcul de features de l'API.
Aucune dépendance externe (pas de DB, pas de réseau) -> rapide et fiable en CI.
"""
from datetime import datetime

import pytest

from api.features import TRANSACTION_TYPES, compute_features
from api.schemas import TransactionRequest


def make_transaction(**overrides) -> TransactionRequest:
    """Construit une transaction de test avec des valeurs par défaut sensées,
    surchargeables au cas par cas."""
    defaults = dict(
        transaction_type="TRANSFER",
        amount=1000.0,
        name_orig="C1231006815",
        oldbalance_org=5000.0,
        newbalance_orig=4000.0,
        name_dest="C1979787155",
        oldbalance_dest=0.0,
        newbalance_dest=1000.0,
        transaction_ts=datetime(2026, 8, 3, 14, 0, 0),
    )
    defaults.update(overrides)
    return TransactionRequest(**defaults)


def test_balance_error_orig_is_zero_for_perfectly_consistent_transaction():
    """Si le solde après = solde avant - montant exactement, l'écart doit être nul."""
    txn = make_transaction(oldbalance_org=5000.0, amount=1000.0, newbalance_orig=4000.0)
    features = compute_features(txn)
    assert features["balance_error_orig"] == 0.0


def test_balance_error_orig_detects_inconsistency():
    """Un écart de solde doit être correctement mesuré, pas juste détecté comme non-nul."""
    txn = make_transaction(oldbalance_org=5000.0, amount=1000.0, newbalance_orig=4500.0)
    features = compute_features(txn)
    assert features["balance_error_orig"] == pytest.approx(-500.0)


def test_merchant_destination_detected_by_prefix():
    """Le préfixe 'M' doit déclencher is_merchant_dest -- comportement identifié
    comme déterminant dans l'analyse du modèle (voir historique du projet)."""
    txn_merchant = make_transaction(name_dest="M1979787155")
    txn_client = make_transaction(name_dest="C1979787155")

    assert compute_features(txn_merchant)["is_merchant_dest"] == 1
    assert compute_features(txn_client)["is_merchant_dest"] == 0


def test_amount_to_oldbalance_ratio_handles_zero_balance():
    """Cas limite : un compte à solde nul ne doit jamais provoquer une division par zéro."""
    txn = make_transaction(oldbalance_org=0.0, amount=500.0)
    features = compute_features(txn)
    assert features["amount_to_oldbalance_ratio"] == 0


def test_exactly_one_transaction_type_column_is_active():
    """Vérifie que l'encodage one-hot est correct : une seule colonne type_* à 1,
    toutes les autres à 0 -- une erreur ici casserait silencieusement le modèle."""
    txn = make_transaction(transaction_type="CASH_OUT")
    features = compute_features(txn)

    active_types = [t for t in TRANSACTION_TYPES if features[f"type_{t}"] == 1]
    assert active_types == ["CASH_OUT"]


def test_all_expected_feature_keys_are_present():
    """Garde-fou anti-régression : si une feature est renommée/supprimée par erreur,
    ce test échoue avant même d'atteindre le modèle."""
    txn = make_transaction()
    features = compute_features(txn)

    expected_keys = {
        "amount", "balance_error_orig", "balance_error_dest", "is_merchant_dest",
        "hour_of_day", "amount_to_oldbalance_ratio",
        "txn_count_1h_orig", "txn_sum_amount_1h_orig", "txn_count_24h_orig",
    } | {f"type_{t}" for t in TRANSACTION_TYPES}

    assert expected_keys.issubset(features.keys())
