from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.config.settings import settings
from app.utils.responses import success_response
import httpx
import logging

# Configure basic logging if not configured yet
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])

@router.delete("/me")
def delete_me(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    logger.info(f"[USER DELETION] Iniciando proceso de eliminación para user_id: {user_id}")
    
    # 1. Clean local database records that are linked to this user
    try:
        # Delete from transaction_tags (which maps tags to transactions)
        # We find transaction_ids of transactions belonging to user_id
        logger.info(f"[USER DELETION] Borrando registros de transaction_tags para user_id: {user_id}")
        db.execute(text("""
            DELETE FROM transaction_tags 
            WHERE transaction_id IN (
                SELECT id FROM transactions WHERE user_id = :user_id
            )
        """), {"user_id": user_id})
        
        # Delete from transactions
        logger.info(f"[USER DELETION] Borrando registros de transactions para user_id: {user_id}")
        db.execute(text("DELETE FROM transactions WHERE user_id = :user_id"), {"user_id": user_id})
        
        # Delete from wallets
        logger.info(f"[USER DELETION] Borrando registros de wallets para user_id: {user_id}")
        db.execute(text("DELETE FROM wallets WHERE user_id = :user_id"), {"user_id": user_id})
        
        # Delete from categories
        logger.info(f"[USER DELETION] Borrando registros de categories para user_id: {user_id}")
        db.execute(text("DELETE FROM categories WHERE user_id = :user_id"), {"user_id": user_id})
        
        # Delete from tags
        logger.info(f"[USER DELETION] Borrando registros de tags para user_id: {user_id}")
        db.execute(text("DELETE FROM tags WHERE user_id = :user_id"), {"user_id": user_id})
        
        # Delete from profiles (if it exists locally or in the profiles table)
        logger.info(f"[USER DELETION] Borrando registros de profiles para user_id: {user_id}")
        db.execute(text("DELETE FROM profiles WHERE id = :user_id"), {"user_id": user_id})
        
        # Commit DB operations
        db.commit()
        logger.info(f"[USER DELETION] Eliminación de base de datos local completada con éxito para user_id: {user_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"[USER DELETION] ERROR eliminando registros de base de datos local para user_id {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al limpiar la base de datos local: {str(e)}"
        )
        
    # 2. Delete the user from Supabase Auth via HTTP Admin API
    try:
        if not settings.SUPABASE_SECRET_KEY:
            logger.error("[USER DELETION] ERROR: SUPABASE_SECRET_KEY no configurado en variables de entorno.")
            raise ValueError("SUPABASE_SECRET_KEY no está configurado.")
            
        headers = {
            "apikey": settings.SUPABASE_SECRET_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SECRET_KEY}"
        }
        # Build Supabase Auth Admin delete user endpoint URL
        supabase_url = settings.SUPABASE_URL.rstrip('/')
        url = f"{supabase_url}/auth/v1/admin/users/{user_id}"
        
        logger.info(f"[USER DELETION] Enviando DELETE a Supabase Auth Admin API: {url}")
        
        with httpx.Client() as client:
            response = client.delete(url, headers=headers)
            logger.info(f"[USER DELETION] Respuesta de Supabase Auth Admin: status_code={response.status_code}")
            
            if response.status_code not in (200, 204):
                logger.error(f"[USER DELETION] ERROR de Supabase Auth Admin. Status: {response.status_code}, Body: {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Error eliminando de Supabase Auth: {response.text}"
                )
        
        logger.info(f"[USER DELETION] Usuario {user_id} eliminado exitosamente de Supabase Auth")
    except Exception as e:
        logger.error(f"[USER DELETION] Excepción durante eliminación de Supabase Auth para user_id {user_id}: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error conectando con el servicio de autenticación de Supabase: {str(e)}"
        )
        
    return success_response(message="Tu perfil y todos los datos asociados han sido eliminados de forma permanente.")
