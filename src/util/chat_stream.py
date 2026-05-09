import json
import traceback
from typing import Any

import httpx
from fastapi import HTTPException
from loguru import logger
from starlette import status
from starlette.responses import JSONResponse, StreamingResponse

from src.db import dao_models
from src.llm_provider import get_provider
from src.llm_provider.util import converter
from src.llm_provider.util.context_compressor import compress_messages_with_summary

DEFAULT_CONTEXT_LENGTH = 258_000


def _preview(value: Any, max_len: int = 500) -> str | None:
    if value is None:
        return None

    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if len(text) > max_len:
        return f"{text[:max_len]}...<truncated len={len(text)}>"
    return text


def _summarize_stream_chunk(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, (bytes, bytearray)):
        text = chunk.decode("utf-8", errors="replace").strip()
    else:
        text = str(chunk).strip()

    summary: dict[str, Any] = {
        "raw_length": len(text),
        "raw_preview": _preview(text, 300),
    }

    if text.startswith("data:"):
        payload = text.removeprefix("data:").strip()
    else:
        payload = text

    if not payload or payload == "[DONE]":
        summary["event"] = payload or "empty"
        return summary

    try:
        obj = json.loads(payload)
    except Exception as e:
        summary["parse_error"] = str(e)
        return summary

    choices = obj.get("choices", [])
    summary["choice_count"] = len(choices)
    summarized_choices: list[dict[str, Any]] = []
    for choice in choices:
        delta = choice.get("delta", {})
        if isinstance(delta, dict):
            summarized_choices.append(
                {
                    "finish_reason": choice.get("finish_reason"),
                    "delta_keys": sorted(delta.keys()),
                    "content": _preview(delta.get("content")),
                    "reasoning": _preview(delta.get("reasoning")),
                    "reasoning_content": _preview(delta.get("reasoning_content")),
                    "tool_calls": _preview(delta.get("tool_calls")),
                }
            )
        else:
            summarized_choices.append(
                {
                    "finish_reason": choice.get("finish_reason"),
                    "delta": _preview(delta),
                }
            )
    summary["choices"] = summarized_choices
    return summary


def extract_response_text(chunks: list[Any]) -> str:
    content_text = ""
    for chunk in chunks:
        try:
            if isinstance(chunk, (bytes, bytearray)):
                text = chunk.decode("utf-8").strip()
            else:
                text = str(chunk).strip()

            if text.startswith("data:"):
                text = text.removeprefix("data:").strip()
            if not text or text == "[DONE]":
                continue

            obj = json.loads(text)
            choices = obj.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            if "content" in delta and delta["content"] is not None:
                content_text += str(delta["content"])
        except Exception:
            continue

    return content_text

def extract_reasoning_text(chunks: list[Any]) -> str:
    reasoning_text = ""
    for chunk in chunks:
        try:
            if isinstance(chunk, (bytes, bytearray)):
                text = chunk.decode("utf-8").strip()
            else:
                text = str(chunk).strip()

            if text.startswith("data:"):
                text = text.removeprefix("data:").strip()
            if not text or text == "[DONE]":
                continue

            obj = json.loads(text)
            choices = obj.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            for key in ("reasoning", "reasoning_content"):
                if key in delta and delta[key] is not None:
                    reasoning_text += str(delta[key])
        except Exception:
            continue

    return reasoning_text


def count_tool_call_chunks(chunks: list[Any]) -> int:
    count = 0
    for chunk in chunks:
        try:
            if isinstance(chunk, (bytes, bytearray)):
                text = chunk.decode("utf-8").strip()
            else:
                text = str(chunk).strip()

            if text.startswith("data:"):
                text = text.removeprefix("data:").strip()
            if not text or text == "[DONE]":
                continue

            obj = json.loads(text)
            choices = obj.get("choices", [])
            if not choices:
                continue

            delta = choices[0].get("delta", {})
            if delta.get("tool_calls"):
                count += 1
        except Exception:
            continue

    return count


def summarize_stream_chunks(chunks: list[Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "raw_chunks": len(chunks),
        "sse_events": 0,
        "content_chars": 0,
        "reasoning_chars": 0,
        "tool_call_chunks": 0,
        "finish_reasons": [],
        "done_seen": False,
        "parse_errors": 0,
        "empty_delta_chunks": 0,
    }

    finish_reasons: list[Any] = []

    for chunk in chunks:
        try:
            if isinstance(chunk, (bytes, bytearray)):
                text = chunk.decode("utf-8", errors="replace")
            else:
                text = str(chunk)

            for raw_event in text.split("\n\n"):
                event = raw_event.strip()
                if not event:
                    continue
                if event.startswith("data:"):
                    event = event.removeprefix("data:").strip()
                else:
                    continue

                summary["sse_events"] += 1
                if event == "[DONE]":
                    summary["done_seen"] = True
                    continue

                obj = json.loads(event)
                choices = obj.get("choices", [])
                if not choices:
                    continue

                for choice in choices:
                    finish_reason = choice.get("finish_reason")
                    if finish_reason is not None:
                        finish_reasons.append(finish_reason)

                    delta = choice.get("delta") or {}
                    if not isinstance(delta, dict):
                        continue

                    if delta.get("content") is not None:
                        summary["content_chars"] += len(str(delta.get("content")))
                    if delta.get("reasoning") is not None:
                        summary["reasoning_chars"] += len(str(delta.get("reasoning")))
                    if delta.get("reasoning_content") is not None:
                        summary["reasoning_chars"] += len(str(delta.get("reasoning_content")))
                    if delta.get("tool_calls"):
                        summary["tool_call_chunks"] += 1

                    if (
                        not delta.get("content")
                        and not delta.get("reasoning")
                        and not delta.get("reasoning_content")
                        and not delta.get("tool_calls")
                    ):
                        summary["empty_delta_chunks"] += 1
        except Exception:
            summary["parse_errors"] += 1

    summary["finish_reasons"] = finish_reasons
    return summary


def _summarize_message(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("content")
    summary: dict[str, Any] = {
        "role": message.get("role"),
        "keys": sorted(message.keys()),
        "content_type": type(content).__name__,
    }

    if isinstance(content, str):
        preview = content[:120]
        if len(content) > 120:
            preview += "..."
        summary["content_preview"] = preview
        summary["content_length"] = len(content)
        return summary

    if isinstance(content, list):
        blocks: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                blocks.append({"type": type(block).__name__})
                continue

            block_type = block.get("type")
            block_summary: dict[str, Any] = {"type": block_type}

            if block_type == "text":
                text = str(block.get("text", ""))
                preview = text[:80]
                if len(text) > 80:
                    preview += "..."
                block_summary["text_preview"] = preview
                block_summary["text_length"] = len(text)
            elif block_type in {"image_url", "imageUrl"}:
                image_obj = block.get("image_url") or block.get("imageUrl") or {}
                url = str(image_obj.get("url", ""))
                if url.startswith("data:"):
                    comma_idx = url.find(",")
                    mime_part = url[5:comma_idx] if comma_idx != -1 else url[5:40]
                    block_summary["image_url"] = f"data:{mime_part},<omitted>"
                    block_summary["image_url_length"] = len(url)
                else:
                    preview = url[:120]
                    if len(url) > 120:
                        preview += "..."
                    block_summary["image_url"] = preview
                    block_summary["image_url_length"] = len(url)
            else:
                block_summary["block_keys"] = sorted(block.keys())

            blocks.append(block_summary)

        summary["content_blocks"] = blocks
        summary["content_block_count"] = len(blocks)
        return summary

    summary["content_value"] = content
    return summary


def _filter_unsupported_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    allowed_roles = {"system", "user", "assistant", "tool"}
    filtered_messages: list[dict[str, Any]] = []
    dropped_messages: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        role = message.get("role")
        if role in allowed_roles:
            filtered_messages.append(message)
            continue

        dropped_messages.append(
            {
                "index": index,
                **_summarize_message(message),
            }
        )

    if dropped_messages:
        logger.warning("dropped_unsupported_messages={}", dropped_messages)

    return filtered_messages


async def stream_chat_response(data: dict[str, Any]) -> StreamingResponse | JSONResponse:
    data = dict(data)
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="messages must be a non-empty array.",
        )

    data["messages"] = converter.normalize_messages(messages)
    messages = data["messages"]

    logger.info(f"messages type={type(messages)}, length={len(messages)}")
    logger.info(f"last_message={messages[-1]}")
    logger.info(f"message_roles={[message.get('role') for message in messages]}")
    logger.info(
        "message_summaries={}",
        [
            {
                "index": index,
                **_summarize_message(message),
            }
            for index, message in enumerate(messages)
        ],
    )

    messages = _filter_unsupported_messages(messages)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No supported messages remain after filtering.",
        )
    data["messages"] = messages
    logger.info(f"filtered_message_roles={[message.get('role') for message in messages]}")

    if messages[-1].get("content") == "err":
        logger.info("chat request intentionally returned 401")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    model_id = data["model"]
    model_info = await dao_models.select_model_by_model_id(model_id)
    logger.info(f"model_info={model_info}")
    if not model_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="",
        )

    requested_max_tokens = data.get("max_tokens")
    logger.info(f"request max_tokens={requested_max_tokens}")
    configured_max_tokens = model_info.get("max_tokens")
    if configured_max_tokens:
        data["max_tokens"] = int(configured_max_tokens)
    elif requested_max_tokens:
        data["max_tokens"] = int(requested_max_tokens)
    else:
        data["max_tokens"] = 4096
    logger.info(f'applied max_tokens={data.get("max_tokens")}')
    logger.info(
        "request tools count={}, tool_choice={}, parallel_tool_calls={}",
        len(data.get("tools") or []),
        data.get("tool_choice"),
        data.get("parallel_tool_calls"),
    )

    provider = get_provider(model_info["model_provider"])
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="",
        )

    data["model_id"] = model_info["model_id"]
    data["api_base_url"] = model_info["api_base_url"]

    if model_info.get("api_key", None):
        data["api_key"] = model_info["api_key"]

    max_input_tokens = DEFAULT_CONTEXT_LENGTH
    if max_input_tokens is not None:
        request_id = data.get("requestId") or data.get("request_id")
        compression_result = await compress_messages_with_summary(
            messages,
            max_input_tokens,
            request_id=request_id,
        )
        if not compression_result.ok:
            logger.error(
                "context compression failed; blocking provider call: "
                "request_id={} method={} reason={} before_tokens={} after_tokens={} limit={}",
                request_id,
                compression_result.method,
                compression_result.reason,
                compression_result.before_tokens,
                compression_result.after_tokens,
                max_input_tokens,
            )
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "Context too large after compression",
                    "reason": compression_result.reason,
                    "before_tokens": compression_result.before_tokens,
                    "after_tokens": compression_result.after_tokens,
                    "limit": max_input_tokens,
                },
            )

        messages = compression_result.messages
        if compression_result.method != "none":
            logger.info(
                "context compression applied: request_id={} method={} "
                "tokens {} -> {}, messages {} -> {}",
                request_id,
                compression_result.method,
                compression_result.before_tokens,
                compression_result.after_tokens,
                len(data["messages"]),
                len(messages),
            )

    data["messages"] = messages
    chunk_list: list[Any] = []

    async def stream_generator(first_chunk, stream_iter):
        emitted_count = 1
        logger.info(
            "bridge emit chunk #{} summary={}",
            emitted_count,
            _summarize_stream_chunk(first_chunk),
        )
        yield first_chunk
        chunk_list.append(first_chunk)

        try:
            async for chunk in stream_iter:
                emitted_count += 1
                chunk_list.append(chunk)
                logger.info(
                    "bridge emit chunk #{} summary={}",
                    emitted_count,
                    _summarize_stream_chunk(chunk),
                )
                yield chunk
        except Exception as e:
            traceback.print_exc()
            err_data = {
                "choices": [
                    {
                        "delta": {"content": f"\n[stream error]: {str(e)}"},
                        "finish_reason": "error",
                    }
                ]
            }
            yield f"data: {json.dumps(err_data, ensure_ascii=False)}"

        stream_summary = summarize_stream_chunks(chunk_list)
        logger.info(
            "stream_finish: request_id={} raw_chunks={} sse_events={} "
            "content_chars={} reasoning_chars={} tool_call_chunks={} "
            "finish_reasons={} done_seen={} empty_delta_chunks={} parse_errors={}",
            request_id,
            stream_summary["raw_chunks"],
            stream_summary["sse_events"],
            stream_summary["content_chars"],
            stream_summary["reasoning_chars"],
            stream_summary["tool_call_chunks"],
            stream_summary["finish_reasons"],
            stream_summary["done_seen"],
            stream_summary["empty_delta_chunks"],
            stream_summary["parse_errors"],
        )

        if (
            stream_summary["content_chars"] == 0
            and stream_summary["reasoning_chars"] == 0
            and stream_summary["tool_call_chunks"] == 0
        ):
            logger.warning(
                "empty_stream_payload: request_id={} raw_chunks={} "
                "sse_events={} finish_reasons={} done_seen={} parse_errors={}",
                request_id,
                stream_summary["raw_chunks"],
                stream_summary["sse_events"],
                stream_summary["finish_reasons"],
                stream_summary["done_seen"],
                stream_summary["parse_errors"],
            )

        content_text = extract_response_text(chunk_list)
        reasoning_text = extract_reasoning_text(chunk_list)
        tool_call_chunk_count = count_tool_call_chunks(chunk_list)
        logger.info(
            "llm_response(summary): chunks={}, content_len={}, reasoning_len={}, tool_call_chunks={}",
            len(chunk_list),
            len(content_text),
            len(reasoning_text),
            tool_call_chunk_count,
        )
        if reasoning_text and not content_text and tool_call_chunk_count == 0:
            logger.warning(
                "llm_response appears reasoning-only: reasoning_preview={}",
                _preview(reasoning_text, 1000),
            )
        if content_text:
            max_log_len = 4000
            if len(content_text) > max_log_len:
                logger.info(
                    f"llm_response(content, truncated)={content_text[:max_log_len]}"
                )
            else:
                logger.info(f"llm_response(content)={content_text}")

    try:
        stream_iter = provider.stream(data["messages"], data)
        first_chunk = await stream_iter.__anext__()
    except StopAsyncIteration:
        logger.warning("provider returned an empty stream response")
        return JSONResponse(
            status_code=502,
            content={
                "error": "Empty stream response from provider",
                "detail": "The upstream model provider returned no chunks.",
            },
        )
    except httpx.HTTPStatusError as e:
        response_text = e.response.text if e.response is not None else str(e)
        logger.error(
            "provider stream HTTP error: status={} body={}",
            e.response.status_code if e.response is not None else None,
            response_text[:4000],
        )
        return JSONResponse(
            status_code=502,
            content={
                "error": "Provider HTTP error",
                "provider_status": e.response.status_code
                if e.response is not None
                else None,
                "detail": response_text[:4000],
            },
        )
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"error": f"{str(e)}", "detail": f"{str(e)}"},
        )

    return StreamingResponse(
        stream_generator(first_chunk, stream_iter),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
