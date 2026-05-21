from fastapi import HTTPException, status
from jose import JWTError, jwt
import httpx
from app.config.settings import settings

# Caché en memoria para el JSON Web Key Set (JWKS) de Supabase (para algoritmos asimétricos como ES256)
_jwks_cache = None

def get_jwks(force_reload: bool = False) -> dict:
    global _jwks_cache
    if _jwks_cache is None or force_reload:
        try:
            # Obtener las llaves públicas desde el endpoint de configuración de Supabase Auth
            jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
            with httpx.Client() as client:
                response = client.get(jwks_url, timeout=5.0)
                response.raise_for_status()
                _jwks_cache = response.json()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No se pudieron cargar las llaves públicas de autenticación de Supabase: {e}"
            )
    return _jwks_cache

def verify_jwt_token(token: str) -> dict:
    try:
        # 1. Leer el header sin verificar firma para saber qué algoritmo se usó (ES256 o HS256)
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")

        if algorithm == "ES256":
            # Autenticación moderna de Supabase (Asimétrica - ES256)
            jwks = get_jwks()
            kid = header.get("kid")
            
            # Buscar la llave pública que corresponde al 'kid' del token
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            
            if not key:
                # Si no se encuentra, intentamos recargar por si hubo rotación de llaves en Supabase
                jwks = get_jwks(force_reload=True)
                key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
                
            if not key:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Firma de token inválida (kid no encontrado en JWKS)"
                )
            
            payload = jwt.decode(
                token,
                key,
                algorithms=["ES256"],
                options={"verify_aud": False}
            )
        else:
            # Autenticación legacy de Supabase (Simétrica - HS256)
            if not settings.SUPABASE_JWT_SECRET:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error del servidor: Se requiere SUPABASE_JWT_SECRET para validar firmas HS256."
                )
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )

        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido (sub missing)"
            )
        return payload

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido o expirado: {e}"
        )