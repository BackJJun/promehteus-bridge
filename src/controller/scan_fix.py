import json
import traceback

from fastapi import APIRouter, HTTPException
from loguru import logger
from starlette.requests import Request

from src.db import dao_models
from src.llm_provider import get_provider

scan_fix_router = APIRouter(prefix="/scan", tags=["scan"])


# edit_existing_file 도구 정의
EDIT_EXISTING_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "edit_existing_file",
        "description": "Use this tool to edit an existing file. Output the COMPLETE modified file content.",
        "parameters": {
            "type": "object",
            "required": ["filepath", "changes"],
            "properties": {
                "filepath": {
                    "type": "string",
                    "description": "The path of the file to edit."
                },
                "changes": {
                    "type": "string",
                    "description": "The COMPLETE modified file content. You MUST output the ENTIRE file content, NOT just the changed parts."
                }
            }
        }
    }
}


@scan_fix_router.post("/fix")
async def fix(
        request: Request,
):
    """보안 스캔 결과를 기반으로 LLM에 edit_existing_file 도구 호출 요청"""
    data = await request.json()
    data = dict(data)

    logger.info(f"[scan/fix] request data keys: {data.keys()}")

    # 모델 정보 불러오기 (기본값 설정)
    #model_id = "gpt-4o-2024-11-20"
    #if data.get("model"):
    #    model_id = data.get("model")
    
    model_info = await dao_models.select_default_model()
    if not model_info:
        logger.error(f"기본 모델 설정 필요")
        raise HTTPException(
            status_code=500,
            detail=f"default model does not exist."
        )

    # 프로바이더 선택 (vllm)
    provider_name = model_info.get('model_provider')
    provider = get_provider(provider_name)
    if not provider:
        raise HTTPException(
            status_code=500,
            detail=f"Provider not found: {provider_name}"
        )

    # 요청 데이터 구성
    request_data = {
        "model_id": model_info['model_id'],
        "api_base_url": model_info['api_base_url'],
        "api_key": model_info.get("api_key"),
        "messages": data.get("messages", []),
        "tools": [EDIT_EXISTING_FILE_TOOL],
        "tool_choice": "auto",  # or required, depending on needs
        "stream": False,
        # 필요한 다른 파라미터 추가
    }

    logger.info(f"[scan/fix] provider model id: {model_info['model_id']}")
    logger.info(f"[scan/fix] Calling provider {provider_name} complete method")

    try:
        # Provider의 complete 메서드 호출
        result = await provider.complete(request_data['messages'], request_data)

        logger.info(f"[scan/fix] LLM response: {json.dumps(result, ensure_ascii=False)[:500]}")

        # LLM 응답 JSON 그대로 반환 (tool_calls 포함)
        return result

    except Exception as e:
        logger.error(f"[scan/fix] LLM call failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
