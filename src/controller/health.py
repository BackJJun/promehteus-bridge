"""헬스 체크 API"""
from fastapi import APIRouter
from loguru import logger

from src.db import dao_etc

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("")
@health_router.get("/")
async def health_check():
    return {"status": "ok"}


@health_router.get("/db")
async def health_check_db():
    now = await dao_etc.select_now()
    logger.info(f"now={now}")
    return {"now": now}
