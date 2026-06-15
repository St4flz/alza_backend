from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services.transaction_service import get_all_transactions, get_transaction_by_id, create_transaction, update_transaction, delete_transaction
from app.serializers.transaction_serializer import TransactionCreateSerializer, TransactionUpdateSerializer
from app.utils.responses import success_response, created_response
from app.models.transaction_model import Transaction
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions"])

def serialize_transaction(t: Transaction) -> dict:
    t_dict = {k: v for k, v in t.__dict__.items() if k != "_sa_instance_state"}
    t_dict["wallet_name"] = t.wallet.name if t.wallet else ""
    t_dict["category_name"] = t.category.name if t.category else ""
    t_dict["tags"] = [{"id": str(tag.id), "name": tag.name} for tag in t.tags]
    return t_dict

@router.get("/count")
def get_transaction_count(
    wallet_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    logger.info(f"API: GET /transactions/count invocado por usuario {user_id} para billetera: {wallet_id}")
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    if wallet_id:
        query = query.filter(Transaction.wallet_id == wallet_id)
    count = query.count()
    return success_response(data={"count": count})

@router.get("")
def list_transactions(
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    wallet_id: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    page: int = Query(1),
    limit: int = Query(20)
):
    logger.info(f"API: GET /transactions invocado por usuario {user_id}")
    transactions = get_all_transactions(db, user_id, wallet_id, category_id, type, start_date, end_date, page, limit)
    data = [serialize_transaction(t) for t in transactions]
    return success_response(data=data)

@router.get("/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"API: GET /transactions/{transaction_id} invocado por usuario {user_id}")
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    return success_response(data=serialize_transaction(transaction))

@router.post("")
def create(payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"API: POST /transactions invocado por usuario {user_id} con payload: {payload}")
    data = TransactionCreateSerializer(**payload)
    transaction = create_transaction(db, data, user_id)
    return created_response(data=serialize_transaction(transaction), message="Movimiento creado exitosamente")

@router.patch("/{transaction_id}")
def update(transaction_id: str, payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"API: PATCH /transactions/{transaction_id} invocado por usuario {user_id} con payload: {payload}")
    data = TransactionUpdateSerializer(**payload)
    transaction = update_transaction(db, transaction_id, data, user_id)
    return success_response(data=serialize_transaction(transaction), message="Movimiento actualizado exitosamente")

@router.delete("/{transaction_id}")
def delete(transaction_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"API: DELETE /transactions/{transaction_id} invocado por usuario {user_id}")
    delete_transaction(db, transaction_id, user_id)
    return success_response(message="Transacción eliminada exitosamente")