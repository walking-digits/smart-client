import asyncio
import logging
import os

import asyncpg
from fastapi import HTTPException

log = logging.getLogger("uvicorn.error")

FATAL_ERRORS = (asyncpg.InvalidPasswordError, asyncpg.InvalidCatalogNameError)

pool: asyncpg.Pool | None = None


async def _init_connection(conn: asyncpg.Connection):
    await conn.set_type_codec(
        "numeric", encoder=str, decoder=float, schema="pg_catalog", format="text"
    )


async def connect(retries: int = 5, delay: float = 2.0):
    global pool

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(
                database_url,
                min_size=1,
                max_size=10,
                timeout=5,
                init=_init_connection,
                server_settings={"search_path": "info,public"},
            )
            await pool.fetchval("SELECT 1")
            log.info("Database is available.")
            return
        except FATAL_ERRORS as e:
            raise RuntimeError(f"Database connection error: {e}") from e
        except (OSError, TimeoutError, asyncpg.PostgresError) as e:
            log.warning("Database unavailable (attempt %d/%d): %s", attempt, retries, e)
            if attempt == retries:
                raise RuntimeError("Could not connect to the database, shutting down...") from e
            await asyncio.sleep(delay)


async def disconnect():
    global pool

    if pool is not None:
        await pool.close()

        pool = None


async def is_alive() -> bool:
    try:
        await pool.fetchval("SELECT 1")

        return True
    except Exception:
        return False


async def get_client_info(inn: str) -> dict:
    row = await pool.fetchrow("SELECT * FROM client WHERE inn = $1", inn)

    if row is None:
        raise HTTPException(404, "Client not found")

    return dict(row)
