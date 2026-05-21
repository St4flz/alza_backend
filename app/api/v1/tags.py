from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.services.tag_service import get_all_tags, get_tag_by_id, create_tag, update_tag, delete_tag
from app.serializers.tag_serializer import TagCreateSerializer, TagUpdateSerializer
from app.utils.responses import success_response, created_response

router = APIRouter(prefix="/tags", tags=["Tags"])

@router.get("")
def list_tags(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    tags = get_all_tags(db, user_id)
    data = [{k: v for k, v in t.__dict__.items() if k != "_sa_instance_state"} for t in tags]
    return success_response(data=data)

@router.get("/{tag_id}")
def get_tag(tag_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    tag = get_tag_by_id(db, tag_id, user_id)
    data = {k: v for k, v in tag.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=data)

@router.post("")
def create(payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = TagCreateSerializer(**payload)
    tag = create_tag(db, data, user_id)
    result = {k: v for k, v in tag.__dict__.items() if k != "_sa_instance_state"}
    return created_response(data=result)

@router.patch("/{tag_id}")
def update(tag_id: str, payload: dict, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    data = TagUpdateSerializer(**payload)
    tag = update_tag(db, tag_id, data, user_id)
    result = {k: v for k, v in tag.__dict__.items() if k != "_sa_instance_state"}
    return success_response(data=result)

@router.delete("/{tag_id}")
def delete(tag_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    delete_tag(db, tag_id, user_id)
    return success_response(message="Tag eliminado exitosamente")