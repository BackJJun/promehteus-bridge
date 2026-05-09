import json
import time
from typing import List, Dict, AsyncIterator
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage
from loguru import logger

from src.llm_provider.base import LLMProvider
from src.llm_provider.util import converter


class GeminiProvider(LLMProvider):
    async def stream(self, messages: List[BaseMessage], data: Dict) -> AsyncIterator[str]:

        logger.info("제미나이 API stream 호출")

        # 랭체인 메시지로 변환
        messages = converter.convert_to_langchain(data['messages'])

        # 1. Gemini 클라이언트 생성
        # model_id 예: "gemini-1.5-pro" 또는 "gemini-1.5-flash"
        client = ChatGoogleGenerativeAI(
            model=data['model_id'],
            google_api_key=data.get('api_key'),
            max_output_tokens=data.get("max_tokens", 4096),
            streaming=True
        )

        model_name = data.get('model_id', 'gemini-1.5-pro')

        # 2. 스트리밍 - OpenAI 형식으로 변환하여 yield
        async for chunk in client.astream(messages):
            if chunk.content:
                openai_chunk = {
                    "id": "chatcmpl-" + str(id(chunk)),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": chunk.content
                        },
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(openai_chunk)}\n\n"

        # 3. 스트림 종료 신호 (OpenAI 규격 준수)
        final_chunk = {
            "id": "chatcmpl-end",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model_name,
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
        logger.info("call gemini complete (non-streaming)")
        
        # 랭체인 메시지로 변환
        lc_messages = converter.convert_to_langchain(messages)
        
        # Gemini 클라이언트 생성 (streaming=False)
        client = ChatGoogleGenerativeAI(
            model=data['model_id'],
            google_api_key=data.get('api_key'),
            max_output_tokens=data.get("max_tokens", 4096),
            streaming=False
        )

        if data.get("tools"):
            tool_choice = data.get("tool_choice", "any")
            client = client.bind_tools(data["tools"], tool_choice=tool_choice)
            logger.info(f"Tools bound to Gemini client: {len(data['tools'])} tools, tool_choice={tool_choice}")
        
        # ainvoke로 한 번에 응답 받기
        result = await client.ainvoke(lc_messages)
        content = result.content if hasattr(result, 'content') else str(result)
        logger.info(f"gemini complete response length: {len(content)}")

        tool_calls = []
        if hasattr(result, 'tool_calls') and result.tool_calls:
            logger.info(f"gemini tool calls: {result.tool_calls}")
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

