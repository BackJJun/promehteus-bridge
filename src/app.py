from contextlib import asynccontextmanager

from fastapi import FastAPI
import httpx
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from src.config.logger import setup_app_logging
from src.config.router_config import regist_router
from src.db.connection.db_async_postgre import Connection


from fastapi.staticfiles import StaticFiles

@asynccontextmanager
async def lifespan(app: FastAPI):
    """런 서버 후 커넥션 풀 생성 및 스케줄러 시작"""

    # Keycloak 헬스체크
    logger.info("[시스템 초기화] (0/2) Keycloak 헬스체크 시작")
    from src.auth.auth import keycloak_health_check
    
    health_check_passed = await keycloak_health_check()
    if not health_check_passed:
        logger.error("=" * 80)
        logger.error("Keycloak 헬스체크 실패: 서버 연결 또는 클라이언트 자격증명을 확인하세요")
        logger.error("애플리케이션을 종료합니다")
        logger.error("=" * 80)
        raise RuntimeError("Keycloak 헬스체크 실패")
    
    logger.info("[시스템 초기화] (1/2) Keycloak 헬스체크 완료")

    logger.info("[시스템 초기화] (1/2) DB 커넥션 풀 생성 시작")
    await Connection.create_pool()
    logger.info("[시스템 초기화] (2/2) DB 커넥션 풀 생성 완료")
    yield
    await Connection.connection_pool.close()
    logger.info("커넥션풀을 정리 했음")


app = FastAPI(
    lifespan=lifespan
)

app.mount("/static", StaticFiles(directory="src/static"), name="static")

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 또는 특정 origin만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Username"]
)



setup_app_logging(app)  # 로그 설정
regist_router(app)  # 라우터 설정
