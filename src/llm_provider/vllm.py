import json
from typing import AsyncIterator, Dict, List

import httpx
from loguru import logger

import config
from .openai import OpenAIProvider


def _preview(value, max_len: int = 500):
    if value is None:
        return None

    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if len(text) > max_len:
        return f"{text[:max_len]}...<truncated len={len(text)}>"
    return text


def _summarize_delta(delta: Dict) -> Dict:
    return {
        "keys": sorted(delta.keys()),
        "content": _preview(delta.get("content")),
        "reasoning_content": _preview(delta.get("reasoning_content")),
        "reasoning": _preview(delta.get("reasoning")),
        "tool_calls": _preview(delta.get("tool_calls")),
    }


class VLLMProvider(OpenAIProvider):
    @staticmethod
    def _request_headers(data: Dict) -> Dict[str, str]:
        api_key = data.get("api_key")
        if not api_key:
            return {}

        return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def _request_json(data: Dict) -> Dict:
        request_data = dict(data)
        request_data.pop("api_key", None)
        return request_data

    async def stream(self, messages, data: Dict) -> AsyncIterator[bytes]:
        url = data['api_base_url']
        headers = self._request_headers(data)
        request_data = self._request_json(data)
        logger.info(f"call vllm, API_URL={url}")
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                json=request_data,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    body_text = body.decode("utf-8", errors="replace")
                    logger.error(
                        "vllm stream returned HTTP {} body={}",
                        response.status_code,
                        body_text[:4000],
                    )
                    raise httpx.HTTPStatusError(
                        f"vLLM stream returned HTTP {response.status_code}: {body_text[:1000]}",
                        request=response.request,
                        response=response,
                    )

                buffer = ""
                raw_event_count = 0
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue

                    buffer += chunk.decode("utf-8", errors="ignore")

                    while "\n\n" in buffer:
                        raw_event, buffer = buffer.split("\n\n", 1)
                        event = raw_event.strip()
                        if not event:
                            continue

                        if not event.startswith("data:"):
                            # Forward unknown chunks as-is.
                            yield (raw_event + "\n\n").encode("utf-8")
                            continue

                        payload = event.removeprefix("data:").strip()
                        if payload == "[DONE]":
                            logger.info(
                                "vllm stream upstream done after raw_events={}",
                                raw_event_count,
                            )
                            # NOTE:
                            # think 태그 기반 표현은 현재 비활성화.
                            # if in_reasoning:
                            #     close_obj = {
                            #         "id": last_obj.get("id", "chatcmpl-reasoning-close") if last_obj else "chatcmpl-reasoning-close",
                            #         "object": "chat.completion.chunk",
                            #         "created": last_obj.get("created", 0) if last_obj else 0,
                            #         "model": last_obj.get("model", data.get("model_id", "gpt")) if last_obj else data.get("model_id", "gpt"),
                            #         "choices": [{
                            #             "index": 0,
                            #             "delta": {"content": "</think>"},
                            #             "finish_reason": None
                            #         }]
                            #     }
                            #     yield f"data: {json.dumps(close_obj, ensure_ascii=False)}\n\n".encode("utf-8")
                            #     in_reasoning = False
                            yield b"data: [DONE]\n\n"
                            continue

                        try:
                            raw_event_count += 1
                            if raw_event_count <= 3:
                                logger.debug(
                                    "vllm raw stream event sample[{}]={}",
                                    raw_event_count,
                                    payload[:2000],
                                )

                            obj = json.loads(payload)
                            choices = obj.get("choices", [])
                            for choice_index, choice in enumerate(choices):
                                finish_reason = choice.get("finish_reason")
                                if finish_reason is not None:
                                    logger.info(
                                        "vllm stream chunk finish_reason={}",
                                        finish_reason,
                                    )

                                delta = choice.get("delta")
                                if isinstance(delta, dict):
                                    logger.info(
                                        "vllm raw chunk #{} choice={} finish_reason={} delta={}",
                                        raw_event_count,
                                        choice_index,
                                        choice.get("finish_reason"),
                                        _summarize_delta(delta),
                                    )

                                    if delta.get("tool_calls"):
                                        logger.info(
                                            "vllm stream chunk contains tool_calls: {}",
                                            delta.get("tool_calls"),
                                        )
                                    if delta.get("content"):
                                        logger.debug(
                                            "vllm stream chunk content_len={}",
                                            len(str(delta.get("content"))),
                                        )
                                    if delta.get("reasoning_content"):
                                        logger.debug(
                                            "vllm stream chunk reasoning_content_len={}",
                                            len(str(delta.get("reasoning_content"))),
                                        )

                                    reasoning_content = delta.pop("reasoning_content", None)

                                    if reasoning_content:
                                        # reasoning이 있을 때만 별도 필드로 전달
                                        delta["reasoning"] = reasoning_content

                                        # NOTE:
                                        # think 태그 기반 content 합성은 현재 비활성화.
                                        # prefix = ""
                                        # if not in_reasoning:
                                        #     prefix = "<think>"
                                        #     in_reasoning = True
                                        # delta_content = delta.get("content", "")
                                        # delta["content"] = f"{prefix}{reasoning_content}{delta_content}"
                                        # delta.pop("reasoning", None)
                                    else:
                                        # NOTE:
                                        # think 태그 기반 closing 처리 비활성화.
                                        # if in_reasoning and delta.get("content"):
                                        #     delta["content"] = f"</think>{delta['content']}"
                                        #     in_reasoning = False
                                        pass

                            normalized = f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
                            logger.info(
                                "vllm normalized chunk #{} choices={}",
                                raw_event_count,
                                [
                                    {
                                        "finish_reason": choice.get("finish_reason"),
                                        "delta": _summarize_delta(choice.get("delta", {}))
                                        if isinstance(choice.get("delta"), dict)
                                        else choice.get("delta"),
                                    }
                                    for choice in choices
                                ],
                            )
                            yield normalized.encode("utf-8")
                        except Exception as e:
                            logger.warning(
                                "vllm stream chunk parse failed: error={} raw_event_preview={}",
                                str(e),
                                _preview(raw_event, 1000),
                            )
                            # If parsing fails, pass through original event unchanged.
                            yield (raw_event + "\n\n").encode("utf-8")

    async def complete(self, messages: List[Dict], data: Dict) -> Dict:
        """
        Get complete response at once (non-streaming) using httpx.
        
        Args:
            messages: List of message dicts
            data: Request data
            
        Returns:
            Complete response dict (OpenAI format)
        """

        url = data['api_base_url']

        logger.info(f"call vllm complete (non-streaming), API_URL={url}")
        
        # Ensure stream is disabled for non-streaming request
        request_data = {**self._request_json(data), "stream": False}
        headers = self._request_headers(data)
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.post(url, json=request_data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            # logger.info(f"vllm complete raw result: {result}")
            
            if result is None:
                logger.error("vllm complete: API returned None response")
                return {}
            
            return result


