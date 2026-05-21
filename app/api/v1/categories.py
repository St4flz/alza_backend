from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services.category_service import get_all_categories, get_category_by_id, create_category, update_category, delete_category
from app.serializers.category_serializer import CategoryCreateSerializer, CategoryUpdateSerializer
from app.utils.responses import success_response, created_response

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.get("")
def list_categories(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    categories = get_all_categories(db, user_id)
    data = [{k: v for k, v in c.__dict__.items() if k != "_sa_instance_state"} for c in categories]
    return success_response(data=data)

@router.get("/{category_id}")
def get_category(category_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    category = get_category_by_id(db, category_id, user_id)
    data = {k: v for k, v in category.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=data)

@router.post("")
def create(payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = CategoryCreateSerializer(**payload)
    category = create_category(db, data, user_id)
    result = {k: v for k, v in category.__dict__.items() if k != "_sa_instance_state"}
    return created_response(data=result)

@router.patch("/{category_id}")
def update(category_id: str, payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = CategoryUpdateSerializer(**payload)
    category = update_category(db, category_id, data, user_id)
    result = {k: v for k, v in category.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=result)

@router.delete("/{category_id}")
def delete(category_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    delete_category(db, category_id, user_id)
    return success_response(message="Categoría eliminada exitosamente")