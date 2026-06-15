from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services.transfer_service import get_user_transfers, create_transfer
from app.serializers.transfer_serializer import TransferCreateSerializer
from app.utils.responses import success_response, created_response
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transfers", tags=["Transfers"])

@router.get("")
def list_transfers(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"API: GET /transfers invocado por usuario {user_id}")
    transfers = get_user_transfers(db, user_id)
    data = [t.__dict__ for t in transfers]
    for d in data:
        d.pop("_sa_instance_state", None)
    return success_response(data=data)

@router.post("")
def create(payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"API: POST /transfers invocado por usuario {user_id} con payload: {payload}")
    data = TransferCreateSerializer(**payload)
    transfer = create_transfer(db, data, user_id)
    result = {k: v for k, v in transfer.__dict__.items() if k != "_sa_instance_state"}
    return created_response(data=result, message="Transferencia realizada con éxito")
