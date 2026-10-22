"""ML-сервис, модель 1: POST /offers (API.md, 4.1).

Запуск из этой папки:
    uvicorn app:app --port 8000
"""
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from contract import validate_company
from model import load, predict

MODELS = load()  # один раз при старте
EXAMPLE = json.loads((Path(__file__).resolve().parent / "example.json").read_text(encoding="utf-8"))

app = FastAPI(title="ML-сервис: модель 1 (/offers)")


def error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(Exception)
async def internal_error(request, exc):
    return error(500, "INTERNAL_ERROR", "внутренняя ошибка")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/offers", openapi_extra={"requestBody": {"required": True, "content": {
    "application/json": {"schema": {"type": "object"}, "example": EXAMPLE}}}})
async def offers(request: Request):
    try:
        body = await request.json()
    except ValueError:
        return error(422, "VALIDATION_ERROR", "тело запроса не JSON")
    if not isinstance(body, dict) or "company" not in body:
        return error(422, "VALIDATION_ERROR", "нет поля: company")
    errors = validate_company(body["company"])
    if errors:
        return error(422, "VALIDATION_ERROR", "; ".join(errors))
    # расчёт в отдельном потоке, чтобы не держать другие запросы
    return {"offers": await run_in_threadpool(predict, MODELS, body["company"])}
