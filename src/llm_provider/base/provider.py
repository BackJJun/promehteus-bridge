from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict

from langchain_core.messages import BaseMessage

from .types import ChatRequest


class LLMProvider(ABC):
    @abstractmethod
    async def stream(self, messages, data: ChatRequest):
        """Stream responses chunk by chunk"""
        ...

    async def complete(self, messages: List[Dict], data: Dict) -> Dict:
        """
        Get complete response at once (non-streaming).
        Default implementation collects stream chunks.
        Override for more efficient implementation.
        
        Args:
            messages: List of message dicts
            data: Request data
            
        Returns:
            Complete response dict (OpenAI format)
        """
        # Default: collect stream chunks
        content = ""
        last_obj = {}
        
        async for chunk in self.stream(messages, data):
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8")
            # Try to extract content from SSE format
            if chunk.startswith("data:"):
                import json
                payload = chunk.removeprefix("data:").strip()
                if payload and payload != "[DONE]":
                    try:
                        obj = json.loads(payload)
                        last_obj = obj # Keep last object structure
                        choices = obj.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            if delta.get("content"):
                                content += delta["content"]
                    except:
                        pass
        
        # Construct basic OpenAI-compatible response
        response = {
            "id": last_obj.get("id", "chatcmpl-default"),
            "object": "chat.completion",
            "created": last_obj.get("created", 0),
            "model": last_obj.get("model", data.get("model_id")),
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }]
        }
        return response

