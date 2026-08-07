"""Schémas Pydantic : contrat strict d'entrée/sortie de l'API."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TransactionRequest(BaseModel):
    transaction_type: str = Field(..., description="CASH_OUT, TRANSFER, PAYMENT, CASH_IN, DEBIT")
    amount: float = Field(..., gt=0)
    name_orig: str
    oldbalance_org: float = Field(..., ge=0)
    newbalance_orig: float = Field(..., ge=0)
    name_dest: str
    oldbalance_dest: float = Field(..., ge=0)
    newbalance_dest: float = Field(..., ge=0)
    transaction_ts: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "transaction_type": "TRANSFER",
                "amount": 250000.0,
                "name_orig": "C1231006815",
                "oldbalance_org": 250000.0,
                "newbalance_orig": 0.0,
                "name_dest": "M1979787155",
                "oldbalance_dest": 0.0,
                "newbalance_dest": 250000.0,
                "transaction_ts": "2026-08-03T14:00:00",
            }
        }
    )

class ScoringResponse(BaseModel):
    is_fraud_predicted: bool
    fraud_probability: float
    decision_threshold: float
    model_version: str
