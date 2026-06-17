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

@router.post("/process")
async def process_receipt(
    request: ReceiptProcessRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    # 1. Save to DB
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

    # 3. Agente 1 (Extractor): Process with Gemini Vision
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt1 = """
        Extrae la siguiente información de este recibo o factura y devuélvela estrictamente en formato JSON válido:
        {
            "amount": (número total o monto final a pagar, usar punto para decimales, ej. 45000.0),
            "category_hint": (una palabra clave de la categoría probable, ej. "Mercado", "Restaurante", "Transporte"),
            "date": (fecha en formato YYYY-MM-DD o null si no se encuentra),
            "raw_text": (un breve resumen de los ítems o nombre del establecimiento comercial. MÁXIMO 50 CARACTERES)
        }
        Solo responde con el JSON puro, sin tags de markdown.
        """
        
        image_parts = [{"mime_type": mime_type, "data": base64.b64encode(image_bytes).decode('utf-8')}]
        response = model.generate_content([image_parts[0], prompt1])
        
        text_response = response.text
        if text_response.startswith("```json"):
            text_response = text_response[7:-3]
            
        extracted_data = json.loads(text_response.strip())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI extraction error: {str(e)}")

    # 4. Agente 2 (Historial) y Agente 3 (Consolidador): Contexto del usuario y segunda llamada
    try:
        categories = category_service.get_all_categories(db, user_id)
        transactions = transaction_service.get_all_transactions(db, user_id, limit=30)
        
        categories_data = [{"id": str(c.id), "name": c.name} for c in categories]
        transactions_data = [{"title": t.title, "amount": t.amount, "category_id": str(t.category_id)} for t in transactions]

        prompt2 = f"""
        Eres un agente consolidador de finanzas. Tienes los datos crudos extraídos de un recibo:
        {json.dumps(extracted_data)}

        Las categorías reales del usuario son:
        {json.dumps(categories_data)}

        El historial reciente de transacciones del usuario es:
        {json.dumps(transactions_data)}

        Tu tarea es:
        1. Analizar el 'category_hint' y el 'raw_text' extraídos del recibo.
        2. Determinar a cuál de las "categorías reales" del usuario pertenece este recibo (apóyate en el historial si es necesario).
        3. Devolver un JSON estricto con:
        {{
            "category_id": (El ID exacto de la categoría seleccionada de la lista dada, o null si no estás seguro de ninguna),
            "confidence": (Un número entre 0.0 y 1.0 indicando qué tan seguro estás de la categoría y los datos extraídos en general)
        }}
        Solo responde con el JSON puro, sin tags de markdown.
        """
        
        # Como es texto puro, usamos el mismo modelo flash o pro para mayor velocidad
        consolidator_model = genai.GenerativeModel('gemini-2.5-flash')
        consolidation_response = consolidator_model.generate_content(prompt2)
        
        cons_text = consolidation_response.text
        if cons_text.startswith("```json"):
            cons_text = cons_text[7:-3]
            
        consolidated_data = json.loads(cons_text.strip())
        
        response_data = ReceiptProcessResponse(
            id=str(new_receipt.id),
            amount=extracted_data.get("amount"),
            category_id=consolidated_data.get("category_id"),
            confidence=consolidated_data.get("confidence", 0.0),
            date=extracted_data.get("date"),
            raw_text=extracted_data.get("raw_text")
        )
        
        return success_response(data=response_data.model_dump())

    except Exception as e:
        # Fallback al resultado del Agente 1 si el Consolidador falla
        response_data = ReceiptProcessResponse(
            id=str(new_receipt.id),
            amount=extracted_data.get("amount", 0.0),
            category_id=None,
            confidence=0.5,
            date=extracted_data.get("date"),
            raw_text=extracted_data.get("raw_text")
        )
        return success_response(data=response_data.model_dump())
