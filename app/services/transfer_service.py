from sqlalchemy.orm import Session
from app.models.transfer_model import Transfer
from app.models.wallet_model import Wallet
from app.serializers.transfer_serializer import TransferCreateSerializer
from app.permissions.ownership import check_ownership
from app.utils.exceptions import not_found_exception, bad_request_exception
import logging

logger = logging.getLogger(__name__)

def get_user_transfers(db: Session, user_id: str):
    logger.info(f"Obteniendo transferencias para el usuario: {user_id}")
    return db.query(Transfer).filter(Transfer.user_id == user_id).order_by(Transfer.created_at.desc()).all()

def create_transfer(db: Session, data: TransferCreateSerializer, user_id: str):
    logger.info(f"Iniciando transferencia para usuario {user_id}: {data.amount} de {data.origin_wallet_id} a {data.dest_wallet_id}")
    
    if data.origin_wallet_id == data.dest_wallet_id:
        logger.warning(f"Error de transferencia para usuario {user_id}: Origen y destino son iguales.")
        bad_request_exception("La billetera de origen y destino no pueden ser la misma.")

    # Retrieve origin wallet
    origin_wallet = db.query(Wallet).filter(Wallet.id == data.origin_wallet_id).first()
    if not origin_wallet:
        logger.warning(f"Billetera de origen {data.origin_wallet_id} no encontrada para transferencia.")
        not_found_exception("Billetera de origen")
    check_ownership(origin_wallet.user_id, user_id)

    # Retrieve destination wallet
    dest_wallet = db.query(Wallet).filter(Wallet.id == data.dest_wallet_id).first()
    if not dest_wallet:
        logger.warning(f"Billetera de destino {data.dest_wallet_id} no encontrada para transferencia.")
        not_found_exception("Billetera de destino")
    check_ownership(dest_wallet.user_id, user_id)

    # Check balance
    if origin_wallet.balance < data.amount:
        logger.warning(f"Saldo insuficiente en la billetera de origen: {origin_wallet.balance} < {data.amount}")
        bad_request_exception("Saldo insuficiente en la billetera de origen.")

    try:
        # Perform transactional updates
        origin_wallet.balance -= data.amount
        dest_wallet.balance += data.amount

        transfer = Transfer(
            user_id=user_id,
            origin_wallet_id=data.origin_wallet_id,
            dest_wallet_id=data.dest_wallet_id,
            amount=data.amount
        )
        db.add(transfer)
        db.commit()
        db.refresh(transfer)
        logger.info(f"Transferencia creada exitosamente con ID {transfer.id}")
        return transfer
    except Exception as e:
        db.rollback()
        logger.exception("Error al procesar la transferencia en la base de datos.")
        bad_request_exception(f"Error al procesar la transferencia: {str(e)}")
