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
from pydantic import BaseModel

router = APIRouter(prefix="/receipts", tags=["Receipts"])

class ReceiptProcessRequest(BaseModel):
    image_url: str

class ReceiptProcessResponse(BaseModel):
    id: str
    amount: Optional[float] = None
    category_hint: Optional[str] = None
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

    # 3. Process with Gemini
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = """
        Extrae la siguiente información de este recibo o factura y devuélvela estrictamente en formato JSON válido:
        {
            "amount": (número total o monto final a pagar, usar punto para decimales, ej. 45000.0),
            "category_hint": (una palabra clave de la categoría probable, ej. "Mercado", "Restaurante", "Transporte"),
            "date": (fecha en formato YYYY-MM-DD o null si no se encuentra),
            "raw_text": (un breve resumen de los ítems o nombre del establecimiento comercial)
        }
        Solo responde con el JSON puro, sin tags de markdown.
        """
        
        image_part = {
            "mime_type": mime_type,
            "data": image_bytes
        }
        
        gemini_response = model.generate_content([image_part, prompt])
        text_response = gemini_response.text.strip()
        
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]
            
        extracted_data = json.loads(text_response.strip())
        
        response_data = ReceiptProcessResponse(
            id=str(new_receipt.id),
            amount=extracted_data.get("amount"),
            category_hint=extracted_data.get("category_hint"),
            date=extracted_data.get("date"),
            raw_text=extracted_data.get("raw_text")
        )
        
        return success_response(data=response_data.model_dump())

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse JSON from Gemini response")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing error: {str(e)}")
