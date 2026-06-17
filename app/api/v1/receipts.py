import os
import httpx
import base64
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import google.generativeai as genai

from app.database.connection import get_db
from app.models.receipt_model import ReceiptImage
from app.middleware.auth_middleware import get_current_user_id
from app.utils.responses import success_response
from app.services import category_service, transaction_service
from pydantic import BaseModel

router = APIRouter(prefix="/receipts", tags=["Receipts"])

class ReceiptProcessRequest(BaseModel):
    image_url: str

class ReceiptProcessResponse(BaseModel):
    id: str
    amount: Optional[float] = None
    category_id: Optional[str] = None
    confidence: float = 0.0
    date: Optional[str] = None
    raw_text: Optional[str] = None

# Configure Gemini
api_key = os.environ.get("GEMINI_API_KEY", "")
if api_key:
    genai.configure(api_key=api_key)

import logging

logger = logging.getLogger("receipts_agents")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

@router.post("/process")
async def process_receipt(
    request: ReceiptProcessRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    # 1. Save initial record
    new_receipt = ReceiptImage(
        user_id=user_id,
        image_url=request.image_url
    )
    db.add(new_receipt)
    db.commit()
    db.refresh(new_receipt)

    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured")

    # 2. Download image
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(request.image_url)
            response.raise_for_status()
            image_bytes = response.content
            mime_type = response.headers.get("content-type", "image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")

    logger.info("==========================================")
    logger.info(f"Iniciando procesamiento Multiagente para imagen: {request.image_url}")

    # --- AGENTE 1: Extractor Visual ---
    try:
        model_vision = genai.GenerativeModel('gemini-2.5-flash')
        prompt1 = """
        Extrae la siguiente información de este recibo o factura y devuélvela estrictamente en formato JSON válido:
        {
            "amount": (número total a pagar, usar punto para decimales),
            "category_hint": (palabra clave de la categoría probable, ej. "Mercado"),
            "date": (fecha en formato YYYY-MM-DD o null si no se encuentra),
            "raw_text": (un breve resumen de los ítems o nombre del establecimiento. MÁXIMO 50 CARACTERES)
        }
        Solo responde con el JSON puro.
        """
        image_parts = [{"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode('utf-8')}]
        response1 = model_vision.generate_content([image_parts[0], prompt1])
        text_response1 = response1.text
        if text_response1.startswith("```json"): text_response1 = text_response1[7:-3]
        extracted_data = json.loads(text_response1.strip())
        
        logger.info(f"AGENTE 1 (Extractor) JSON: {json.dumps(extracted_data, indent=2)}")

    except Exception as e:
        logger.error(f"Error en Agente 1: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI extraction error: {str(e)}")

    # --- Fetch Data for Next Agents ---
    categories = category_service.get_all_categories(db, user_id)
    transactions = transaction_service.get_all_transactions(db, user_id, limit=30)
    
    categories_data = [{"id": str(c.id), "name": c.name} for c in categories]
    transactions_data = [{"title": t.title, "amount": t.amount, "category_id": str(t.category_id)} for t in transactions]

    if not categories_data:
        # Fallback si el usuario no tiene ninguna categoría
        response_data = ReceiptProcessResponse(
            id=str(new_receipt.id),
            amount=extracted_data.get("amount", 0.0),
            category_id=None,
            confidence=0.0,
            date=extracted_data.get("date"),
            raw_text=extracted_data.get("raw_text")
        )
        return success_response(data=response_data.model_dump())

    # --- AGENTE 2: Analista de Historial y Contexto ---
    try:
        model_analyst = genai.GenerativeModel('gemini-2.5-flash')
        prompt2 = f"""
        Eres un analista de datos transaccionales.
        Datos extraídos de un recibo actual:
        {json.dumps(extracted_data)}

        Categorías del usuario:
        {json.dumps(categories_data)}

        Últimas transacciones del usuario:
        {json.dumps(transactions_data)}

        Tarea:
        1. Compara los datos actuales con el historial.
        2. Determina cómo suele categorizar el usuario gastos similares.
        3. Genera un razonamiento detallado y sugiere las categorías más probables.
        
        Devuelve estrictamente un JSON válido con este formato:
        {{
            "reasoning": "Texto explicando tu lógica de forma detallada.",
            "suggested_categories_ids": ["id1", "id2"]
        }}
        Solo responde con el JSON puro.
        """
        response2 = model_analyst.generate_content(prompt2)
        text_response2 = response2.text
        if text_response2.startswith("```json"): text_response2 = text_response2[7:-3]
        analyst_data = json.loads(text_response2.strip())
        
        logger.info(f"AGENTE 2 (Analista) Razonamiento: {analyst_data.get('reasoning')}")
        logger.info(f"AGENTE 2 (Analista) Sugerencias: {analyst_data.get('suggested_categories_ids')}")

    except Exception as e:
        logger.error(f"Error en Agente 2: {str(e)}")
        analyst_data = {"reasoning": "Fallo en análisis", "suggested_categories_ids": []}


    # --- AGENTE 3: Consolidador Estricto ---
    try:
        model_consolidator = genai.GenerativeModel('gemini-2.5-flash')
        prompt3 = f"""
        Eres el Agente Consolidador Final de una arquitectura Multiagente.
        
        Información inicial (Agente 1): {json.dumps(extracted_data)}
        Análisis de contexto (Agente 2): {json.dumps(analyst_data)}
        Lista ESTRICTA de categorías válidas: {json.dumps(categories_data)}

        REGLA CRÍTICA Y OBLIGATORIA:
        DEBES seleccionar exactamente UNO de los "id" de la Lista ESTRICTA de categorías válidas.
        No puedes devolver null en "category_id". Si ninguna coincide perfectamente, elige la categoría lógica más cercana (ej. "Otros", "Varios", "Alimentación"). ¡ESTÁ PROHIBIDO DEJAR LA CATEGORÍA VACÍA!

        Devuelve ESTRICTAMENTE un JSON válido con este formato:
        {{
            "category_id": "EL_ID_ELEGIDO",
            "confidence": (número entre 0.0 y 1.0)
        }}
        Solo responde con el JSON puro.
        """
        response3 = model_consolidator.generate_content(prompt3)
        text_response3 = response3.text
        if text_response3.startswith("```json"): text_response3 = text_response3[7:-3]
        final_decision = json.loads(text_response3.strip())

        final_category_id = final_decision.get("category_id")
        # Seguridad extrema: si la IA se vuelve loca y envía un ID falso o null, forzamos el primero.
        if final_category_id not in [c["id"] for c in categories_data]:
            logger.warning(f"Agente 3 devolvió un category_id inválido o null ({final_category_id}). Forzando la primera categoría.")
            final_category_id = categories_data[0]["id"]
            final_decision["confidence"] = 0.0

        logger.info(f"AGENTE 3 (Consolidador) Decisión Final: Categoría ID {final_category_id} con confianza {final_decision.get('confidence')}")
        logger.info("==========================================")

        response_data = ReceiptProcessResponse(
            id=str(new_receipt.id),
            amount=extracted_data.get("amount", 0.0),
            category_id=final_category_id,
            confidence=final_decision.get("confidence", 0.0),
            date=extracted_data.get("date"),
            raw_text=extracted_data.get("raw_text")
        )
        return success_response(data=response_data.model_dump())

    except Exception as e:
        logger.error(f"Error en Agente 3: {str(e)}")
        # Fallback extremo
        response_data = ReceiptProcessResponse(
            id=str(new_receipt.id),
            amount=extracted_data.get("amount", 0.0),
            category_id=categories_data[0]["id"] if categories_data else None,
            confidence=0.0,
            date=extracted_data.get("date"),
            raw_text=extracted_data.get("raw_text")
        )
        return success_response(data=response_data.model_dump())
