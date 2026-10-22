from fastapi import HTTPException, APIRouter

from . import SMSHandler

from .PhoneRequest import PhoneRequest
from .PhoneVerify import PhoneVerify


router = APIRouter(prefix="/auth")


@router.post("/phone/request")
async def auth_by_phone(data: PhoneRequest):
    try:
        SMSHandler.set_code(data.phone)
    except Exception as e:
        raise HTTPException(400, e.args)


@router.post("/phone/verify")
async def auth_by_phone_code(data: PhoneVerify):
    try:
        return {"result": SMSHandler.verify_code(data.phone, data.code)}
    except Exception as e:
        raise HTTPException(400, e.args)
