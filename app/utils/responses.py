from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

def success_response(data=None, message="OK", status_code=200):
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({
            "success": True,
            "message": message,
            "data": data
        })
    )

def created_response(data=None, message="Creado exitosamente"):
    return success_response(data=data, message=message, status_code=201)    