"""ML-сервис, модель 2: POST /approval и POST /alternative (API.md, 4.2–4.3).

Запуск из этой папки:
    uvicorn app:app --port 8001
"""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from contract import is_number, validate_company, validate_offer
from model import approval_probability, find_alternative, load

HERE = Path(__file__).resolve().parent
MODEL = load()  # один раз при старте

app = FastAPI(title="ML-сервис: модель 2 (/approval, /alternative)")


class BadRequest(Exception):
    pass


def example(name):
    """Пример запроса для страницы /docs."""
    body = json.loads((HERE / name).read_text(encoding="utf-8"))
    return {"requestBody": {"required": True, "content": {"application/json": {
        "schema": {"type": "object"}, "example": body}}}}


@app.exception_handler(BadRequest)
async def bad_request(request, exc):
    return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": str(exc)}})


@app.exception_handler(Exception)
async def internal_error(request, exc):
    return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "внутренняя ошибка"}})


async def read_request(request: Request, *keys):
    """Тело запроса → (company, offer) после проверки по контракту."""
    try:
        body = await request.json()
    except ValueError:
        raise BadRequest("тело запроса не JSON")
    if not isinstance(body, dict):
        raise BadRequest("тело запроса должно быть объектом")
    missing = [k for k in ("company", "offer", *keys) if k not in body]
    if missing:
        raise BadRequest(f"нет поля: {', '.join(missing)}")
    errors = validate_company(body["company"])
    if not errors:
        errors = validate_offer(body["offer"], body["company"]["msp_category"])
    if errors:
        raise BadRequest("; ".join(errors))
    return body


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/approval", openapi_extra=example("example_approval.json"))
async def approval(request: Request):
    body = await read_request(request)
    p = await run_in_threadpool(approval_probability, MODEL, body["company"], body["offer"])
    return {"approval_probability": p}


@app.post("/alternative", openapi_extra=example("example_alternative.json"))
async def alternative(request: Request):
    body = await read_request(request, "gamma")
    gamma = body["gamma"]
    if not (is_number(gamma) and 0 <= gamma <= 1):
        raise BadRequest(f"gamma={gamma!r}: нужно число 0…1")
    return await run_in_threadpool(find_alternative, MODEL, body["company"], body["offer"], gamma)
