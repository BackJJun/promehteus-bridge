import traceback

from fastapi import APIRouter
from loguru import logger
from starlette import status
from starlette.responses import JSONResponse

from src.db import dao_code_referece

code_reference_router = APIRouter(tags=["code_reference"])


@code_reference_router.get("/code_reference_list")
async def code_reference_select():
    try:
        code_reference_list = await dao_code_referece.select_code_reference_by_id()
        return JSONResponse(content={"code_reference_list": code_reference_list})
    except Exception as e:
        logger.error(f"Error occurred while fetching code references: {e}")
        traceback.print_exc()
        return JSONResponse(
            content={"error": "Failed to fetch code references"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@code_reference_router.get("/code_reference/{doc_id}")
async def code_reference_detail(doc_id: str):
    try:
        doc = await dao_code_referece.select_code_reference_detail_by_doc_id(doc_id)
        if not doc:
            return JSONResponse(
                content={"error": "Code reference not found"},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return JSONResponse(
            content={
                "doc_id": doc["doc_id"],
                "doc_name": doc["doc_name"],
                "content": doc["content"],
            }
        )
    except Exception as e:
        logger.error(f"Error occurred while fetching code reference detail: {e}")
        traceback.print_exc()
        return JSONResponse(
            content={"error": "Failed to fetch code reference detail"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
