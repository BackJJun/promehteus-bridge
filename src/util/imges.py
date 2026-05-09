import json
from typing import Any

from fastapi import HTTPException, UploadFile
from loguru import logger
from starlette import status

from src.util.image_processing import (
    build_image_message_parts,
    process_upload_files,
)


def normalize_message_content_to_list(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, list):
        return list(content)
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if content is None:
        return []
    return [{"type": "text", "text": str(content)}]


def parse_payload_json(payload: str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"payload JSON parse failed: {str(e)}",
        )

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload must be a JSON object.",
        )

    return data


def get_required_messages(data: dict[str, Any]) -> list[dict[str, Any]]:
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload.messages must be a non-empty array.",
        )
    return messages


async def build_processed_image_parts(images: list[UploadFile]) -> list[dict[str, Any]]:
    processed_parts = await process_upload_files(images)

    logger.info(
        "processed images: input_count={}, output_count={}, outputs={}",
        len(images),
        len(processed_parts),
        [
            {
                "filename": part.meta.filename,
                "original_mime": part.meta.original_mime,
                "detected_format": part.meta.detected_format,
                "original_size": [
                    part.meta.original_width,
                    part.meta.original_height,
                ],
                "output_size": [
                    part.meta.output_width,
                    part.meta.output_height,
                ],
                "resized": part.meta.resized,
                "split_applied": part.meta.split_applied,
                "split_index": part.meta.split_index,
                "split_total": part.meta.split_total,
            }
            for part in processed_parts
        ],
    )

    return build_image_message_parts(processed_parts)


def merge_images_into_last_user_message(
    messages: list[dict[str, Any]],
    image_parts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not image_parts:
        return messages

    merged_messages = [dict(message) for message in messages]

    for index in range(len(merged_messages) - 1, -1, -1):
        if merged_messages[index].get("role") != "user":
            continue

        content = normalize_message_content_to_list(
            merged_messages[index].get("content")
        )
        content.extend(image_parts)
        merged_messages[index]["content"] = content
        return merged_messages

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="이미지를 첨부할 사용자 메시지를 찾을 수 없습니다.",
    )
