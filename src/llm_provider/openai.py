import json
import time
from typing import AsyncIterator, Dict, List

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from .base.provider import LLMProvider
from .util import converter


class OpenAIProvider(LLMProvider):
    async def stream(self, messages, data: Dict) -> AsyncIterator[str]:

        # 랭체인 메시지로 변환
        messages = converter.convert_to_langchain(data['messages'])

        # ChatOpenAI 기반으로 클라이언트 생성
        client = ChatOpenAI(
            model=data.get("model_id", 'gpt'),
            api_key=data.get("api_key"),
            streaming=True
        )

        async for chunk in client.astream(messages):

            delta = {}

            if chunk.content:
                delta["content"] = chunk.content

            # tool_call_chunks 처리 추가
            if hasattr(chunk, 'tool_call_chunks') and chunk.tool_call_chunks:
                delta["tool_calls"] = [
                    {
                        "index": tc.get("index", 0),
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": tc.get("name"),
                            "arguments": tc.get("args", "")
                        }
                    }
                    for tc in chunk.tool_call_chunks
                ]

            if delta:  # content 또는 tool_calls가 있으면 전송
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

    async def complete(self, messages: List[Dict], data: Dict) -> Dict:
        """
        Get complete response at once (non-streaming) using LangChain ainvoke.
        
        Args:
            messages: List of message dicts
            data: Request data
            
        Returns:
            Complete response dict (OpenAI format)
        """
        logger.info("call openai complete (non-streaming)")
        
        # 랭체인 메시지로 변환
        lc_messages = converter.convert_to_langchain(messages)
        
        # ChatOpenAI 클라이언트 생성 (streaming=False)
        client = ChatOpenAI(
            model=data.get("model_id", 'gpt'),
            api_key=data.get("api_key"),
            streaming=False
        )

        if data.get("tools"):
            client = client.bind_tools(data["tools"])
        
        # ainvoke로 한 번에 응답 받기
        result = await client.ainvoke(lc_messages)
        content = result.content if hasattr(result, 'content') else str(result)
        logger.info(f"openai complete response length: {len(content)}")
        
        tool_calls = []
        if hasattr(result, 'tool_calls') and result.tool_calls:
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

