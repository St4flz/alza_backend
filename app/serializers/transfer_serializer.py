from pydantic import BaseModel, field_validator
from uuid import UUID

class TransferCreateSerializer(BaseModel):
    origin_wallet_id: UUID
    dest_wallet_id: UUID
    amount: float

    @field_validator('amount')
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('El monto de la transferencia debe ser mayor a 0.')
        return v
