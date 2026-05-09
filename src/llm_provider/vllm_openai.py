import json
import time
from typing import AsyncIterator, Dict, List

import httpx
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from loguru import logger

import config
from .base import LLMProvider
from .util import converter


class VLLMProvider(LLMProvider):

    async def stream(self, messages: List[BaseMessage], data: Dict) -> AsyncIterator[str]:


        url = None
        if data.get("api_base_url"):
            url = data.get("api_base_url")

        # 랭체인 메시지로 변환
        messages = converter.convert_to_langchain(data['messages'])

        # ChatOpenAI 기반으로 클라이언트 생성
        logger.info(f"call vllm with langchain openai, base_url={url}")
        client = ChatOpenAI(
            base_url=url,
            model=data.get("model_id", 'gpt'),
            api_key=data.get("api_key", "?"),
            streaming=True,
        )

        async for chunk in client.astream(messages):

            logger.info(f"chunk={chunk}")

            if chunk.additional_kwargs.get("reasoning_content"):
                openai_chunk = {
                    "id": "chatcmpl-" + str(id(chunk)),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": data.get('model_id', 'gpt'),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": chunk.additional_kwargs.get("reasoning_content")
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"

            elif chunk.content:
                openai_chunk = {
                    "id": "chatcmpl-" + str(id(chunk)),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": data.get('model_id', 'gpt'),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": chunk.content
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"

        # 마지막 종료 신호
        final_chunk = {
            "id": "chatcmpl-end",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": data.get('model_id', 'gpt'),
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"
