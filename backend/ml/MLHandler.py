import httpx
from fastapi import APIRouter, HTTPException

from .ApprovalRequest import ApprovalRequest
from .OffersRequest import OffersRequest
from ..db import DBManager

router = APIRouter(prefix="/data")

clients: dict[int, httpx.AsyncClient | None] = {1: None, 2: None}


async def start():
    global clients

    clients[1] = httpx.AsyncClient(base_url="http://192.168.1.78:25575", timeout=30, trust_env=False)
    clients[2] = httpx.AsyncClient(base_url="http://192.168.1.78:25585", timeout=30, trust_env=False)


async def stop():
    global clients

    for client in clients:
        if clients[client] is not None:
            await clients[client].aclose()


async def call_ml(path: str, payload: dict, ml: int):
    global clients

    try:
        client = clients[ml]
        r = await client.post(path, json=payload)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"ML service returned {e.response.status_code}: {e.response.text}")
    except httpx.RequestError as e:
        raise HTTPException(503, f"ML service unavailable: {e!r}")
    return r.json()


@router.post("/offers")
async def get_offers(data: OffersRequest):
    company = await DBManager.get_client_info(data.inn)
    return await call_ml("/offers", {"company": company}, 1)

@router.post("/approval")
async def get_approval(data: ApprovalRequest):
    company = await DBManager.get_client_info(data.inn)
    return await call_ml("/approval", {"company": company, "offer": data.offer.model_dump()}, 2)
