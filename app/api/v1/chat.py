import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import google.generativeai as genai

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.utils.responses import success_response
from app.services import transaction_service, category_service, wallet_service, transfer_service
from app.serializers.wallet_serializer import WalletCreateSerializer
from app.serializers.transfer_serializer import TransferCreateSerializer

import logging
logger = logging.getLogger("chat_agent")

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatMessage(BaseModel):
    role: str # "user" or "model"
    text: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

def _get_chat_model(db: Session, user_id: str):
    def get_wallet_balances() -> list:
        """Obtiene el saldo de todas las billeteras o cuentas del usuario. Útil para responder cuánto dinero tiene el usuario en total o en cada cuenta."""
        wallets = wallet_service.get_all_wallets(db, user_id)
        return [{"name": w.name, "balance": w.balance} for w in wallets]

    def get_transactions(limit: int = 20, type: str = None) -> list:
        """Obtiene las últimas transacciones del usuario. type puede ser 'expense' (gasto) o 'income' (ingreso). Útil para saber en qué gastó o cuánto ingresó."""
        txs = transaction_service.get_all_transactions(db, user_id, limit=limit, type=type)
        return [{"title": t.title, "amount": t.amount, "type": t.type, "date": t.created_at.isoformat() if t.created_at else None} for t in txs]
    
    def get_categories() -> list:
        """Obtiene la lista de categorías financieras del usuario."""
        cats = category_service.get_all_categories(db, user_id)
        return [{"name": c.name} for c in cats]

    def create_wallet(name: str, initial_balance: float) -> str:
        """Crea una nueva cuenta o billetera. Útil cuando el usuario te pide registrar una nueva cuenta."""
        wallet_data = WalletCreateSerializer(name=name, balance=initial_balance)
        wallet = wallet_service.create_wallet(db, wallet_data, user_id)
        return f"Billetera '{wallet.name}' creada exitosamente."

    def transfer_money(origin_wallet_name: str, dest_wallet_name: str, amount: float) -> str:
        """Transfiere dinero entre dos cuentas. Debes pedirle al usuario el nombre exacto de la cuenta origen y destino."""
        wallets = wallet_service.get_all_wallets(db, user_id)
        origin_wallet = next((w for w in wallets if w.name.lower() == origin_wallet_name.lower()), None)
        dest_wallet = next((w for w in wallets if w.name.lower() == dest_wallet_name.lower()), None)
        
        if not origin_wallet:
            return f"Error: No encontré la cuenta origen '{origin_wallet_name}'."
        if not dest_wallet:
            return f"Error: No encontré la cuenta destino '{dest_wallet_name}'."
            
        transfer_data = TransferCreateSerializer(
            origin_wallet_id=str(origin_wallet.id),
            dest_wallet_id=str(dest_wallet.id),
            amount=amount
        )
        transfer = transfer_service.create_transfer(db, transfer_data, user_id)
        return f"Transferencia de {amount} exitosa."

    return genai.GenerativeModel(
        model_name='gemini-2.5-flash',
        tools=[get_wallet_balances, get_transactions, get_categories, create_wallet, transfer_money],
        system_instruction=(
            "Eres el asistente financiero inteligente de la app Alza+. "
            "Tu objetivo es dar consejos financieros concisos, amigables y al punto. "
            "Siempre que necesites datos reales del usuario (para saber saldos, ingresos, o gastos), "
            "USA TUS HERRAMIENTAS. No asumas números ni te los inventes. "
            "IMPORTANTE: ANTES de llamar a las herramientas 'create_wallet' o 'transfer_money', DEBES "
            "preguntarle al usuario de forma clara y explícita si está seguro de querer realizar la acción "
            "(ej. 'Voy a transferir 50 de X a Y. ¿Estás de acuerdo?'). SOLO si el usuario responde "
            "afirmativamente en el siguiente mensaje, puedes ejecutar la herramienta correspondiente. "
            "Responde con emojis para hacerlo amigable."
        )
    )

@router.post("/message")
async def send_chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        model = _get_chat_model(db, user_id)

        # Reconstruir el historial del chat
        history = []
        # El historial de genai requiere el formato {'role': 'user'/'model', 'parts': ['texto']}
        for msg in request.messages[:-1]:  # Todo menos el último mensaje
            history.append({
                "role": "model" if msg.role == "model" else "user",
                "parts": [msg.text]
            })

        user_current_message = request.messages[-1].text

        # Iniciar sesión de chat
        chat_session = model.start_chat(
            history=history,
            enable_automatic_function_calling=True
        )

        logger.info(f"Procesando mensaje de usuario: {user_current_message}")
        response = chat_session.send_message(user_current_message)

        return success_response(data={"reply": response.text})

    except Exception as e:
        logger.error(f"Error en Chatbot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/audio")
async def send_chat_audio(
    file: UploadFile = File(...),
    history: str = Form("[]"),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        model = _get_chat_model(db, user_id)
        
        # Parse history
        history_data = json.loads(history)
        chat_history = []
        for msg in history_data:
            chat_history.append({
                "role": "model" if msg.get("role") == "model" else "user",
                "parts": [msg.get("text", "")]
            })
            
        chat_session = model.start_chat(
            history=chat_history,
            enable_automatic_function_calling=True
        )
        
        audio_bytes = await file.read()
        audio_part = {
            "mime_type": file.content_type or "audio/mp3",
            "data": audio_bytes
        }
        
        logger.info("Procesando mensaje de audio")
        response = chat_session.send_message([audio_part])
        
        return success_response(data={"reply": response.text})
        
    except Exception as e:
        logger.error(f"Error en Chatbot Audio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
