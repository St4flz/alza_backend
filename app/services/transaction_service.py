from sqlalchemy.orm import Session
from typing import Optional
from app.models.transaction_model import Transaction
from app.models.wallet_model import Wallet
from app.models.category_model import Category
from app.models.tag_model import Tag
from app.serializers.transaction_serializer import TransactionCreateSerializer, TransactionUpdateSerializer
from app.permissions.ownership import check_ownership
from app.utils.exceptions import not_found_exception, bad_request_exception

def get_all_transactions(
    db: Session,
    user_id: str,
    wallet_id: Optional[str] = None,
    category_id: Optional[str] = None,
    type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    if wallet_id:
        query = query.filter(Transaction.wallet_id == wallet_id)
    if category_id:
        query = query.filter(Transaction.category_id == category_id)
    if type:
        query = query.filter(Transaction.type == type)
    if start_date:
        query = query.filter(Transaction.created_at >= start_date)
    if end_date:
        query = query.filter(Transaction.created_at <= end_date)
    offset = (page - 1) * limit
    return query.offset(offset).limit(limit).all()

def get_transaction_by_id(db: Session, transaction_id: str, user_id: str):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        not_found_exception("Transacción")
    check_ownership(transaction.user_id, user_id)
    return transaction

def update_wallet_balance(db: Session, wallet: Wallet, amount: float, type: str, reverse: bool = False):
    if reverse:
        if type == "income":
            wallet.balance -= amount
        else:
            wallet.balance += amount
    else:
        if type == "income":
            wallet.balance += amount
        else:
            wallet.balance -= amount

def create_transaction(db: Session, data: TransactionCreateSerializer, user_id: str):
    wallet = db.query(Wallet).filter(Wallet.id == data.wallet_id).first()
    if not wallet:
        not_found_exception("Wallet")
    check_ownership(wallet.user_id, user_id)

    if data.type == "expense" and wallet.balance - data.amount < 0:
        bad_request_exception("Saldo insuficiente en la billetera para realizar este gasto.")

    category = db.query(Category).filter(Category.id == data.category_id).first()
    if not category:
        not_found_exception("Categoría")

    tags = []
    if data.tag_ids:
        for tag_id in data.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tag_id).first()
            if not tag:
                not_found_exception("Tag")
            tags.append(tag)

    transaction = Transaction(
        user_id=user_id,
        title=data.title,
        description=data.description,
        amount=data.amount,
        type=data.type,
        wallet_id=data.wallet_id,
        category_id=data.category_id,
        tags=tags
    )
    db.add(transaction)
    update_wallet_balance(db, wallet, data.amount, data.type)
    db.commit()
    db.refresh(transaction)
    return transaction

def update_transaction(db: Session, transaction_id: str, data: TransactionUpdateSerializer, user_id: str):
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    old_wallet = db.query(Wallet).filter(Wallet.id == transaction.wallet_id).first()

    orig_amount = transaction.amount
    orig_type = transaction.type
    orig_wallet_id = transaction.wallet_id

    # 1. Reverse the original transaction from the old wallet.
    update_wallet_balance(db, old_wallet, orig_amount, orig_type, reverse=True)

    # 2. Determine target wallet
    new_wallet = old_wallet
    if data.wallet_id is not None and data.wallet_id != orig_wallet_id:
        new_wallet = db.query(Wallet).filter(Wallet.id == data.wallet_id).first()
        if not new_wallet:
            # Revert old wallet to previous state
            update_wallet_balance(db, old_wallet, orig_amount, orig_type, reverse=False)
            not_found_exception("Wallet")
        # Ensure user owns the new wallet
        check_ownership(new_wallet.user_id, user_id)

    # 3. Determine new values
    new_amount = data.amount if data.amount is not None else orig_amount
    new_type = data.type if data.type is not None else orig_type

    # 4. Check balance: if the new type is expense, check if new wallet balance is negative after transaction
    if new_type == "expense" and new_wallet.balance - new_amount < 0:
        # Revert old wallet to previous state
        update_wallet_balance(db, old_wallet, orig_amount, orig_type, reverse=False)
        bad_request_exception("Saldo insuficiente en la billetera para realizar este gasto.")

    # 5. Apply changes to transaction
    if data.title is not None:
        transaction.title = data.title
    if data.description is not None:
        transaction.description = data.description

    transaction.amount = new_amount
    transaction.type = new_type

    if data.wallet_id is not None:
        transaction.wallet_id = data.wallet_id
    if data.category_id is not None:
        transaction.category_id = data.category_id

    if data.tag_ids is not None:
        tags = []
        for tag_id in data.tag_ids:
            tag = db.query(Tag).filter(Tag.id == tag_id).first()
            if not tag:
                # Revert old wallet to previous state
                update_wallet_balance(db, old_wallet, orig_amount, orig_type, reverse=False)
                not_found_exception("Tag")
            tags.append(tag)
        transaction.tags = tags

    # 6. Apply transaction to new wallet
    update_wallet_balance(db, new_wallet, transaction.amount, transaction.type)
    db.commit()
    db.refresh(transaction)
    return transaction

def delete_transaction(db: Session, transaction_id: str, user_id: str):
    transaction = get_transaction_by_id(db, transaction_id, user_id)
    wallet = db.query(Wallet).filter(Wallet.id == transaction.wallet_id).first()
    update_wallet_balance(db, wallet, transaction.amount, transaction.type, reverse=True)
    db.delete(transaction)
    db.commit()
    return True