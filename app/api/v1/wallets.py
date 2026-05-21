from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services.wallet_service import get_all_wallets, get_wallet_by_id, create_wallet, update_wallet, delete_wallet
from app.serializers.wallet_serializer import WalletCreateSerializer, WalletUpdateSerializer
from app.utils.responses import success_response, created_response

router = APIRouter(prefix="/wallets", tags=["Wallets"])

@router.get("")
def list_wallets(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    wallets = get_all_wallets(db, user_id)
    data = [w.__dict__ for w in wallets]
    for d in data:
        d.pop("_sa_instance_state", None)
    return success_response(data=data)

@router.get("/{wallet_id}")
def get_wallet(wallet_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    wallet = get_wallet_by_id(db, wallet_id, user_id)
    data = {k: v for k, v in wallet.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=data)

@router.post("")
def create(payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = WalletCreateSerializer(**payload)
    wallet = create_wallet(db, data, user_id)
    result = {k: v for k, v in wallet.__dict__.items() if k != "_sa_instance_state"}
    return created_response(data=result)

@router.patch("/{wallet_id}")
def update(wallet_id: str, payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = WalletUpdateSerializer(**payload)
    wallet = update_wallet(db, wallet_id, data, user_id)
    result = {k: v for k, v in wallet.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=result)

@router.delete("/{wallet_id}")
def delete(wallet_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    delete_wallet(db, wallet_id, user_id)
    return success_response(message="Wallet eliminada exitosamente")