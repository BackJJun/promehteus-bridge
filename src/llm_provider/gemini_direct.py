import json
import time
import uuid
from typing import List, Dict, AsyncIterator

from google import genai
from google.genai import types
from loguru import logger

from src.llm_provider.base import LLMProvider
from src.llm_provider.util import converter


class GeminiDirectProvider(LLMProvider):
    """
    Gemini provider using the native google-genai SDK directly.
    More reliable tool calling via native tool_config (mode=ANY).
    """

    def _build_contents(self, messages: List[Dict]) -> list:
        """
        OpenAI 형식의 messages를 Gemini native SDK의 contents 형식으로 변환.
        """
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                # system 메시지는 system_instruction으로 분리
                system_instruction = content
                continue

            # Gemini는 'assistant' 대신 'model' 사용
            gemini_role = "model" if role == "assistant" else "user"

            contents.append(
                types.Content(
                    role=gemini_role,
                    parts=[types.Part(text=content if content else "")]
                )
            )

        return contents, system_instruction

    def _convert_tools(self, tools: List[Dict]) -> types.Tool:
        """
        OpenAI 형식의 tool 정의를 Gemini native SDK 형식으로 변환.
        """
        function_declarations = []

        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                function_declarations.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })

        return types.Tool(function_declarations=function_declarations)

    async def stream(self, messages, data: Dict) -> AsyncIterator[str]:
        """Stream using native Gemini SDK."""
        logger.info("Gemini Direct API stream 호출")

        contents, system_instruction = self._build_contents(data['messages'])

        client = genai.Client(api_key=data.get('api_key'))
        model_name = data.get('model_id', 'gemini-2.0-flash')

        config = types.GenerateContentConfig(
            max_output_tokens=data.get("max_tokens", 4096),
        )

        if system_instruction:
            config.system_instruction = system_instruction

        async for chunk in client.aio.models.generate_content_stream(
            model=model_name,
            contents=contents,
            config=config,
        ):
            if chunk.text:
                openai_chunk = {
                    "id": "chatcmpl-" + str(uuid.uuid4())[:8],
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": chunk.text
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
        Non-streaming complete using native Gemini SDK.
        Uses tool_config with mode=ANY for reliable tool calling.
        """
        logger.info("call gemini direct complete (non-streaming)")

        contents, system_instruction = self._build_contents(messages)

        client = genai.Client(api_key=data.get('api_key'))
        model_name = data.get('model_id', 'gemini-2.0-flash')

        # GenerateContentConfig 구성
        config = types.GenerateContentConfig(
            max_output_tokens=data.get("max_tokens", 4096),
        )

        if system_instruction:
            config.system_instruction = system_instruction

        # 도구 설정
        if data.get("tools"):
            gemini_tool = self._convert_tools(data["tools"])
            config.tools = [gemini_tool]

            # 도구 호출 강제: mode=ANY + allowed_function_names
            tool_names = [
                t["function"]["name"]
                for t in data["tools"]
                if t.get("type") == "function"
            ]
            config.tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=tool_names
                )
            )
            logger.info(f"Gemini Direct tool_config: mode=ANY, allowed_functions={tool_names}")

        # API 호출 (async)
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        logger.info(f"Gemini Direct response candidates: {len(response.candidates)}")

        # 응답 파싱
        content = ""
        tool_calls = []

        candidate = response.candidates[0]
        for part in candidate.content.parts:
            if part.text:
                content += part.text
            if part.function_call:
                fc = part.function_call
                tool_calls.append({
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {
                        "name": fc.name,
                        "arguments": json.dumps(dict(fc.args), ensure_ascii=False)
                    }
                })

        if tool_calls:
            logger.info(f"Gemini Direct tool_calls: {len(tool_calls)} calls")
            for tc in tool_calls:
                logger.info(f"  - {tc['function']['name']}: {tc['function']['arguments'][:200]}")

        # OpenAI 호환 응답 구성
        message_content = {
            "role": "assistant",
            "content": content
        }

        if tool_calls:
            message_content["tool_calls"] = tool_calls

        result = {
            "id": f"chatcmpl-{int(time.time())}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [{
                "index": 0,
                "message": message_content,
                "finish_reason": "tool_calls" if tool_calls else "stop"
            }]
        }

        return result
