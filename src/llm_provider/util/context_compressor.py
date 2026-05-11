"""
Context Compressor Module for GPT-OSS

토큰 초과 시 가장 오래된 질문(user)/답변(assistant) 쌍을 순차적으로 삭제하여
컨텍스트 길이를 줄이는 방식으로 처리합니다.

- System 메시지: 항상 보존
- 마지막 user 메시지: 항상 보존
- 초과 시: 가장 오래된 user+assistant 쌍부터 삭제
"""
import json
import time
from dataclasses import dataclass
from typing import Any, List, Dict, Optional

import httpx
import tiktoken
from loguru import logger

import config
from src.db import dao_models

# Default encoding for GPT models
DEFAULT_ENCODING = "cl100k_base"
NO_TOOL_OUTPUT = "No tool output"
DEFAULT_RECENT_KEEP_COUNTS = (8, 6, 4, 2)
DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY = 100


@dataclass
class CompressionResult:
    ok: bool
    messages: List[Dict]
    before_tokens: int
    after_tokens: int
    method: str
    reason: str | None = None


def count_tokens(messages: List[Dict], model: str = "gpt-4") -> int:
    """
    Count total tokens in message list using tiktoken.

    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model name for encoding selection

    Returns:
        Total token count
    """
    try:
        encoding = tiktoken.get_encoding(DEFAULT_ENCODING)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")

    total_tokens = 0
    for message in messages:
        # Count role tokens (roughly 4 tokens per message for formatting)
        total_tokens += 4

        content = message.get("content", "")
        if isinstance(content, str):
            total_tokens += len(encoding.encode(content))
        elif isinstance(content, list):
            # Handle content blocks (e.g., multi-modal)
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total_tokens += len(encoding.encode(block["text"]))
                elif isinstance(block, str):
                    total_tokens += len(encoding.encode(block))

        # Count tool calls if present
        tool_calls = message.get("toolCalls") or message.get("tool_calls")
        if tool_calls:
            total_tokens += len(encoding.encode(json.dumps(tool_calls)))

    return total_tokens


def normalize_url(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"http://{url}"


def _message_text_for_summary(message: Dict[str, Any]) -> str:
    role = message.get("role", "unknown")
    content = message.get("content", "")

    if content == NO_TOOL_OUTPUT:
        return f"[{role}] <tool output missing>"

    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "text":
                    parts.append(str(block.get("text", "")))
                elif block_type in {"image_url", "imageUrl"}:
                    parts.append("<image omitted>")
                else:
                    parts.append(f"<{block_type or 'block'} omitted>")
            else:
                parts.append(str(block))
        text = "\n".join(parts)
    else:
        text = str(content)

    tool_calls = message.get("tool_calls") or message.get("toolCalls")
    if tool_calls:
        text += "\nTool calls:\n" + json.dumps(tool_calls, ensure_ascii=False)

    return f"[{role}]\n{text}".strip()


def _build_summary_prompt(messages: List[Dict]) -> list[dict[str, str]]:
    conversation = "\n\n---\n\n".join(_message_text_for_summary(message) for message in messages)
    return [
        {
            "role": "system",
            "content": (
                "You summarize long coding assistant conversations for continuation. "
                "Preserve concrete technical facts, file paths, user decisions, tool results, "
                "errors, and unresolved tasks. Do not invent details."
            ),
        },
        {
            "role": "user",
            "content": (
                "Summarize the following older conversation segment so a coding agent can "
                "continue from the newer messages that will remain verbatim. Include important "
                "tool calls and outputs, but mark missing tool outputs as missing instead of "
                "guessing.\n\n"
                f"{conversation}"
            ),
        },
    ]


def _build_fallback_summary(messages: List[Dict]) -> str:
    max_messages = 40
    max_chars = 12_000
    lines = [
        "Automatic conversation compaction fallback.",
        "The summary model was unavailable, so this extractive summary preserves older context.",
        "",
    ]

    for index, message in enumerate(messages[-max_messages:], start=1):
        text = " ".join(_message_text_for_summary(message).split())
        if not text:
            continue
        if len(text) > 500:
            text = f"{text[:500]}..."
        lines.append(f"{index}. {text}")
        if len("\n".join(lines)) >= max_chars:
            lines.append("Additional older messages were omitted to stay within the fallback summary limit.")
            break

    return "\n".join(lines)[:max_chars]


async def _call_summary_model(
    messages: List[Dict],
    request_id: str | None = None,
) -> str:
    summary_model = await dao_models.select_summary_model()
    summary_model_url = summary_model.get("api_base_url") if summary_model else None
    summary_model_id = summary_model.get("model_id") if summary_model else None
    summary_model_api_key = summary_model.get("api_key") if summary_model else None
    summary_model_source = "db"

    if not summary_model_url or not summary_model_id:
        summary_model_url = getattr(config, "SUMMARY_MODEL_URL", None)
        summary_model_id = getattr(config, "SUMMARY_MODEL_ID", None)
        summary_model_api_key = getattr(config, "SUMMARY_MODEL_API_KEY", None)
        summary_model_source = "config"

    if not summary_model_url or not summary_model_id:
        raise RuntimeError("missing_summary_config")

    url = normalize_url(str(summary_model_url))
    payload = {
        "model": summary_model_id,
        "messages": _build_summary_prompt(messages),
        "temperature": 0.1,
        "stream": False,
    }

    start = time.perf_counter()
    logger.info(
        "[compress_messages] summary_model start request_id={} source={} model={} url={}",
        request_id,
        summary_model_source,
        summary_model_id,
        url,
    )
    headers = {}
    if summary_model_api_key:
        headers["Authorization"] = f"Bearer {summary_model_api_key}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    elapsed_ms = int((time.perf_counter() - start) * 1000)
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError("summary_model_empty_response") from exc

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("summary_model_empty_response")

    logger.info(
        "[compress_messages] summary_model success request_id={} summary_chars={} elapsed_ms={}",
        request_id,
        len(content),
        elapsed_ms,
    )
    return content.strip()


def _build_summary_compressed_messages(
    messages: List[Dict],
    summary: str,
    recent_keep_count: int,
) -> List[Dict]:
    system_messages = [msg for msg in messages if msg.get("role") == "system"]
    other_messages = [msg for msg in messages if msg.get("role") != "system"]

    if len(other_messages) <= 1:
        return messages

    effective_keep_count = min(recent_keep_count, max(1, len(other_messages) - 1))
    recent_messages = other_messages[-effective_keep_count:] if effective_keep_count > 0 else []
    if not recent_messages:
        recent_messages = [other_messages[-1]]

    summary_message = {
        "role": "system",
        "content": f"Previous conversation summary:\n\n{summary}",
    }
    return system_messages + [summary_message] + recent_messages


async def compress_messages_with_summary(
    messages: List[Dict],
    max_tokens: int,
    request_id: str | None = None,
) -> CompressionResult:
    before_tokens = count_tokens(messages)
    message_count = len(messages)
    over_token_limit = before_tokens > max_tokens
    over_message_limit = message_count >= DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY
    logger.info(
        "[compress_messages] before_tokens={} limit={} message_count={} message_limit={} request_id={}",
        before_tokens,
        max_tokens,
        message_count,
        DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY,
        request_id,
    )

    if not over_token_limit and not over_message_limit:
        return CompressionResult(
            ok=True,
            messages=messages,
            before_tokens=before_tokens,
            after_tokens=before_tokens,
            method="none",
        )

    system_count = sum(1 for msg in messages if msg.get("role") == "system")
    other_messages = [msg for msg in messages if msg.get("role") != "system"]

    if over_message_limit and not over_token_limit:
        summary_target = other_messages[:-DEFAULT_RECENT_KEEP_COUNTS[0]]
        if not summary_target:
            summary_target = other_messages[:-1]

        try:
            summary = await _call_summary_model(summary_target, request_id=request_id)
            method = "summary_model_message_count"
        except Exception as exc:
            logger.warning(
                "[compress_messages] message_count summary_model failed request_id={} reason={} error={}; using fallback",
                request_id,
                str(exc) or exc.__class__.__name__,
                exc,
            )
            summary = _build_fallback_summary(summary_target)
            method = "summary_fallback_message_count"

        candidate = _build_summary_compressed_messages(
            messages,
            summary,
            DEFAULT_RECENT_KEEP_COUNTS[0],
        )
        candidate_tokens = count_tokens(candidate)
        logger.info(
            "[compress_messages] message_count compacted request_id={} method={} tokens {} -> {} messages {} -> {} system_count={}",
            request_id,
            method,
            before_tokens,
            candidate_tokens,
            message_count,
            len(candidate),
            system_count,
        )
        return CompressionResult(
            ok=True,
            messages=candidate,
            before_tokens=before_tokens,
            after_tokens=candidate_tokens,
            method=method,
        )

    delete_compressed = compress_messages(messages, max_tokens)
    delete_tokens = count_tokens(delete_compressed)
    logger.info(
        "[compress_messages] delete_pairs after_tokens={} request_id={}",
        delete_tokens,
        request_id,
    )
    if delete_tokens <= max_tokens:
        return CompressionResult(
            ok=True,
            messages=delete_compressed,
            before_tokens=before_tokens,
            after_tokens=delete_tokens,
            method="delete_pairs",
        )

    if len(other_messages) <= 1:
        return CompressionResult(
            ok=False,
            messages=delete_compressed,
            before_tokens=before_tokens,
            after_tokens=delete_tokens,
            method="delete_pairs",
            reason="no_summary_target",
        )

    summary_target = other_messages[:-DEFAULT_RECENT_KEEP_COUNTS[0]]
    if not summary_target:
        summary_target = other_messages[:-1]

    try:
        summary = await _call_summary_model(summary_target, request_id=request_id)
    except httpx.HTTPError as exc:
        logger.error(
            "[compress_messages] summary_model failed request_id={} reason=summary_model_http_error error={}",
            request_id,
            exc,
        )
        return CompressionResult(
            ok=False,
            messages=delete_compressed,
            before_tokens=before_tokens,
            after_tokens=delete_tokens,
            method="summary_model",
            reason="summary_model_http_error",
        )
    except Exception as exc:
        reason = str(exc) or exc.__class__.__name__
        logger.error(
            "[compress_messages] summary_model failed request_id={} reason={} error={}",
            request_id,
            reason,
            exc,
        )
        return CompressionResult(
            ok=False,
            messages=delete_compressed,
            before_tokens=before_tokens,
            after_tokens=delete_tokens,
            method="summary_model",
            reason=reason,
        )

    best_messages = delete_compressed
    best_tokens = delete_tokens
    for recent_keep_count in DEFAULT_RECENT_KEEP_COUNTS:
        candidate = _build_summary_compressed_messages(messages, summary, recent_keep_count)
        candidate_tokens = count_tokens(candidate)
        logger.info(
            "[compress_messages] summary_model candidate request_id={} recent_keep_count={} after_tokens={} system_count={}",
            request_id,
            recent_keep_count,
            candidate_tokens,
            system_count,
        )
        if candidate_tokens < best_tokens:
            best_messages = candidate
            best_tokens = candidate_tokens
        if candidate_tokens <= max_tokens:
            return CompressionResult(
                ok=True,
                messages=candidate,
                before_tokens=before_tokens,
                after_tokens=candidate_tokens,
                method="summary_model",
            )

    logger.error(
        "[compress_messages] failed request_id={} reason=still_over_limit before_tokens={} after_tokens={} limit={}",
        request_id,
        before_tokens,
        best_tokens,
        max_tokens,
    )
    return CompressionResult(
        ok=False,
        messages=best_messages,
        before_tokens=before_tokens,
        after_tokens=best_tokens,
        method="summary_model",
        reason="still_over_limit",
    )


def _find_oldest_qa_pair_index(other_messages: List[Dict], last_user_idx: int) -> int | None:
    """
    other_messages에서 가장 오래된 user 메시지의 인덱스를 찾습니다.
    마지막 user 메시지(last_user_idx)는 제외합니다.

    Args:
        other_messages: system 메시지를 제외한 메시지 리스트
        last_user_idx: 마지막 user 메시지의 인덱스 (삭제 금지)

    Returns:
        삭제할 user 메시지의 인덱스, 없으면 None
    """
    for i, msg in enumerate(other_messages):
        if msg.get("role") == "user" and i != last_user_idx:
            return i
    return None


def _remove_qa_pair(other_messages: List[Dict], user_idx: int) -> List[Dict]:
    """
    user 메시지와 그 뒤에 이어지는 assistant/tool 응답들을 함께 삭제합니다.

    Args:
        other_messages: system 메시지를 제외한 메시지 리스트
        user_idx: 삭제할 user 메시지의 인덱스

    Returns:
        삭제 후의 메시지 리스트
    """
    # user 메시지 이후, 다음 user 메시지 전까지가 응답 범위
    end_idx = user_idx + 1
    while end_idx < len(other_messages):
        if other_messages[end_idx].get("role") == "user":
            break
        end_idx += 1

    removed_count = end_idx - user_idx
    removed_roles = [other_messages[i].get("role") for i in range(user_idx, end_idx)]
    logger.info(f"Q&A 쌍 삭제: index={user_idx}, count={removed_count}, roles={removed_roles}")

    return other_messages[:user_idx] + other_messages[end_idx:]


def compress_messages(
    messages: List[Dict],
    max_tokens: int
) -> List[Dict]:
    """
    토큰 초과 시 가장 오래된 질문/답변 쌍을 순차적으로 삭제하여 압축합니다.

    전략:
    1. System 메시지: 항상 보존
    2. 마지막 user 메시지: 항상 보존
    3. 토큰 초과 시: 가장 오래된 user + 이어지는 assistant/tool 응답을 삭제
    4. 삭제 후에도 초과하면 반복

    Args:
        messages: Original message list
        max_tokens: Maximum allowed tokens

    Returns:
        Compressed message list
    """
    if not messages:
        return messages

    current_tokens = count_tokens(messages)

    if current_tokens <= max_tokens:
        logger.info(f"토큰 수 {current_tokens} <= {max_tokens}, 압축 불필요")
        return messages

    logger.info(f"토큰 수 {current_tokens} > {max_tokens}, Q&A 쌍 삭제 압축 시작")

    # system 메시지와 나머지 분리
    system_messages = []
    other_messages = []

    for msg in messages:
        if msg.get("role") == "system":
            system_messages.append(msg)
        else:
            other_messages.append(msg)

    if not other_messages:
        return messages

    # 반복적으로 가장 오래된 Q&A 쌍 삭제
    while True:
        result = system_messages + other_messages
        current_tokens = count_tokens(result)

        if current_tokens <= max_tokens:
            logger.info(f"압축 완료: 토큰 수 {current_tokens} <= {max_tokens}")
            break

        # 마지막 user 메시지 인덱스 찾기
        last_user_idx = -1
        for i in range(len(other_messages) - 1, -1, -1):
            if other_messages[i].get("role") == "user":
                last_user_idx = i
                break

        # 삭제할 가장 오래된 user 메시지 찾기
        oldest_idx = _find_oldest_qa_pair_index(other_messages, last_user_idx)

        if oldest_idx is None:
            # 더 이상 삭제할 Q&A 쌍이 없음
            logger.warning(f"더 이상 삭제할 Q&A 쌍 없음, 현재 토큰 수: {current_tokens}")
            break

        other_messages = _remove_qa_pair(other_messages, oldest_idx)

    result = system_messages + other_messages
    final_tokens = count_tokens(result)
    logger.info(f"Q&A 쌍 삭제 압축 결과: {count_tokens(messages)} -> {final_tokens} 토큰, "
                f"{len(messages)} -> {len(result)} 메시지")
    return result



