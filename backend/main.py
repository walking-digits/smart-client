from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .auth.AuthHandler import router as auth_router
from .db import DBManager
from .ml import MLHandler
from .ml.MLHandler import router as ml_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await DBManager.connect()
    await MLHandler.start()
    try:
        yield
    finally:
        await MLHandler.stop()
        await DBManager.disconnect()


app = FastAPI(lifespan=lifespan)

app.include_router(auth_router)
app.include_router(ml_router)


@app.exception_handler(OSError)
@app.exception_handler(asyncpg.exceptions.ConnectionDoesNotExistError)
@app.exception_handler(asyncpg.exceptions.InterfaceError)
async def db_unavailable(request: Request, exc: Exception):
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable"})


@app.get("/health")
async def health():
    if await DBManager.is_alive():
        return {"status": "ok", "db": "ok"}
    return JSONResponse(status_code=503, content={"status": "error", "db": "unavailable"})
