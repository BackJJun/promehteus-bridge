from fastapi import FastAPI
from loguru import logger

from src.controller.auth import auth_router
from src.controller.chat import chat_router
from src.controller.chat_models import models_router
from src.controller.chat_sessions import session_router
from src.controller.health import health_router
from src.controller.scan import scan_router
from src.controller.scan_fix import scan_fix_router
from src.controller.code_reference import code_reference_router


def regist_router(app: FastAPI):
    app.include_router(chat_router)  # 채팅
    app.include_router(session_router)  # 채팅 세션
    app.include_router(models_router)  # 채팅에서 사용할 모델
    app.include_router(auth_router)  # 권한
    app.include_router(health_router)  # 헬스체크
    app.include_router(scan_router)  # 소스코드보안검사
    app.include_router(scan_fix_router)  # 보안검사 수정 (LLM)
    app.include_router(code_reference_router)  # 코드 레퍼런스 조회
    logger.info("라우터 등록 완료")
