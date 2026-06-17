import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import google.generativeai as genai

from app.database.connection import get_db
from app.middleware.auth_middleware import get_current_user_id
from app.utils.responses import success_response
from app.services import transaction_service, category_service, wallet_service

import logging
logger = logging.getLogger("chat_agent")

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatMessage(BaseModel):
    role: str # "user" or "model"
    text: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

@router.post("/message")
async def send_chat_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    try:
        # Define las herramientas disponibles como closures para inyectar db y user_id
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

        # Configurar modelo con herramientas
        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=[get_wallet_balances, get_transactions, get_categories],
            system_instruction=(
                "Eres el asistente financiero inteligente de la app Alza+. "
                "Tu objetivo es dar consejos financieros concisos, amigables y al punto. "
                "Siempre que necesites datos reales del usuario (para saber saldos, ingresos, o gastos), "
                "USA TUS HERRAMIENTAS. No asumas números ni te los inventes. "
                "Responde con emojis para hacerlo amigable."
            )
        )

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
