from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services.transaction_service import get_all_transactions, get_transaction_by_id, create_transaction, update_transaction, delete_transaction
from app.serializers.transaction_serializer import TransactionCreateSerializer, TransactionUpdateSerializer
from app.utils.responses import success_response, created_response

router = APIRouter(prefix="/transactions", tags=["Transactions"])

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
    transactions = get_all_transactions(db, user_id, wallet_id, category_id, type, start_date, end_date, page, limit)
    data = [{k: v for k, v in t.__dict__.items() if k != "_sa_instance_state"} for t in transactions]
    return success_response(data=data)

@router.get("/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    data = {k: v for k, v in transaction.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=data)

@router.post("")
def create(payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = TransactionCreateSerializer(**payload)
    transaction = create_transaction(db, data, user_id)
    result = {k: v for k, v in transaction.__dict__.items() if k != "_sa_instance_state"}
    return created_response(data=result)

@router.patch("/{transaction_id}")
def update(transaction_id: str, payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = TransactionUpdateSerializer(**payload)
    transaction = update_transaction(db, transaction_id, data, user_id)
    result = {k: v for k, v in transaction.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=result)

@router.delete("/{transaction_id}")
def delete(transaction_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    delete_transaction(db, transaction_id, user_id)
    return success_response(message="Transacción eliminada exitosamente")