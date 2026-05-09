from typing import Optional

from fastapi import APIRouter, Request, Depends
from loguru import logger

from src.auth.auth import User, get_current_user
from src.db import dao_models

models_router = APIRouter(tags=["chat_model"])


@models_router.get("/api/models")
async def list_sessions(
        http_request: Request,
        current_user: User = Depends(get_current_user)
):
    """
    모든 모델 리턴
    """

    # user_id = current_user.user_id

    # 모델 목록 불러옴
    models = await dao_models.select_models()

    models
    logger.info(f"models={models}")

    # 기본 모델 id 추출
    default_model_id: Optional[str] = next(
        (model['model_id'] for model in models if model.get("default_model") == "y"),
        None
    )

    logger.info(f"모델 수: {len(models)}, 기본 모델: {default_model_id}")

    return {
        "models": models,
        "default_model_id": default_model_id
    }
