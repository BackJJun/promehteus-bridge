import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette import status
from starlette.requests import Request

from src.auth.auth import User, get_current_user
from src.llm_provider.util.context_compressor import _call_summary_model
from src.util.chat_stream import stream_chat_response
from src.util.imges import (
    build_processed_image_parts,
    get_required_messages,
    merge_images_into_last_user_message,
    parse_payload_json,
)


chat_router = APIRouter(tags=["chat"])


def _extract_uploaded_files(form: Any, field_name: str) -> list[UploadFile]:
    files: list[UploadFile] = []
    for item in form.getlist(field_name):
        if hasattr(item, "read") and hasattr(item, "content_type"):
            files.append(item)
    return files


@chat_router.post("/chat")
@chat_router.post("/v1/chat/completions")
@chat_router.post("/chat/chat/completions")
async def chat_completions(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    content_type = request.headers.get("content-type", "").lower()

    if "multipart/form-data" in content_type:
        form = await request.form()
        payload = form.get("payload")

        if payload is None or not isinstance(payload, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="multipart request requires a payload field.",
            )

        data = parse_payload_json(payload)
        messages = get_required_messages(data)
        images = _extract_uploaded_files(form, "images")
        image_parts = await build_processed_image_parts(images)
        data["messages"] = merge_images_into_last_user_message(messages, image_parts)
        return await stream_chat_response(data)

    try:
        data = await request.json()
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported request body for /chat. content-type={content_type}, error={str(e)}",
        )

    return await stream_chat_response(dict(data))


@chat_router.post("/api/summary/compact")
async def compact_conversation_summary(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    try:
        data = await request.json()
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported request body for /api/summary/compact. error={str(e)}",
        )

    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="messages must be a non-empty array.",
        )

    request_id = data.get("requestId") or data.get("request_id")
    try:
        summary = await _call_summary_model(messages, request_id=request_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"summary model failed: {str(e)}",
        )

    return {"summary": summary}


@chat_router.post("/api/v1/multimodal/request")
async def multimodal_chat_completions(
    payload: str = Form(...),
    images: list[UploadFile] | None = File(default=None),
    current_user: User = Depends(get_current_user),
):
    data = parse_payload_json(payload)
    messages = get_required_messages(data)
    image_parts = await build_processed_image_parts(images or [])
    data["messages"] = merge_images_into_last_user_message(messages, image_parts)
    return await stream_chat_response(data)
