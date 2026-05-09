import json
import time
from typing import AsyncIterator, Dict, List

import httpx

from langchain_anthropic import ChatAnthropic
from loguru import logger

from .base.provider import LLMProvider
from .base.types import ChatRequest
from .util import converter
from .util.converter import convert_to_langchain


class ClaudeProvider(LLMProvider):
    async def stream(self, messages, data: Dict) -> AsyncIterator[str]:

        # 랭체인 메시지로 변환
        messages = converter.convert_to_langchain(data['messages'])

        # 2. Claude 클라이언트 생성
        client = ChatAnthropic(
            model=data['model_id'],
            api_key=data['api_key'],
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 1.0)
        )

        logger.info("밑에서 랭체인 CLAUDE 메세지스 확인")
        logger.info(f"messages={messages}")

        # 3. 스트리밍 - OpenAI 형식으로 변환
        async for chunk in client.astream(messages):
            # AIMessageChunk를 OpenAI 형식의 SSE로 변환
            if chunk.content:
                openai_chunk = {
                    "id": "chatcmpl-" + str(id(chunk)),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "claude-sonnet-4-5",
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": chunk.content
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"

        # 스트림 종료 신호
        final_chunk = {
            "id": "chatcmpl-end",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "claude-sonnet-4-5",
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    async def complete(self, messages: List[Dict], data: Dict) -> Dict:
        """
        Get complete response at once (non-streaming) using LangChain ainvoke.
        
        Args:
            messages: List of message dicts
            data: Request data
            
        Returns:
            Complete response dict (OpenAI format)
        """
        logger.info("call claude complete (non-streaming)")
        
        # 랭체인 메시지로 변환
        lc_messages = converter.convert_to_langchain(messages)
        
        # Claude 클라이언트 생성
        client = ChatAnthropic(
            model=data['model_id'],
            api_key=data['api_key'],
            max_tokens=data.get("max_tokens", 4096),
            temperature=data.get("temperature", 1.0)
        )

        if data.get("tools"):
            client = client.bind_tools(data["tools"])
            logger.info(f"Tools bound to Claude client: {len(data['tools'])} tools")
        
        # ainvoke로 한 번에 응답 받기
        result = await client.ainvoke(lc_messages)
        content = result.content if hasattr(result, 'content') else str(result)
        logger.info(f"claude complete response length: {len(content)}")

        tool_calls = []
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.info(f"claude tool calls: {result.tool_calls}")
            for tc in result.tool_calls:
                tool_calls.append({
                    "id": tc.get('id'),
                    "type": "function",
                    "function": {
                        "name": tc.get('name'),
                        "arguments": json.dumps(tc.get('args', {}), ensure_ascii=False)
                    }
                })
        
        # Construct OpenAI-compatible response
        message_content = {
            "role": "assistant",
            "content": content
        }
        
        if tool_calls:
            message_content["tool_calls"] = tool_calls

        response = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": data.get("model_id"),
            "choices": [{
                "index": 0,
                "message": message_content,
                "finish_reason": "tool_calls" if tool_calls else "stop"
            }]
        }
        
        return response

