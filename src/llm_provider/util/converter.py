from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from loguru import logger

# from langchain_community.adapters.openai import convert_openai_messages

def normalize_content_blocks(content):
    if not isinstance(content, list):
        return content

    normalized = []
    for block in content:
        if not isinstance(block, dict):
            normalized.append(block)
            continue

        block_type = block.get("type")
        if block_type == "imageUrl":
            url = (block.get("imageUrl") or {}).get("url")
            normalized.append({
                "type": "image_url",
                "image_url": {
                    "url": url
                }
            })
        elif block_type == "image_url":
            normalized.append(block)
        elif block_type == "text":
            normalized.append({
                "type": "text",
                "text": block.get("text", "")
            })
        else:
            normalized.append(block)

    return normalized


def normalize_messages(messages):
    normalized_messages = []

    for message in messages:
        normalized_message = dict(message)
        normalized_message["content"] = normalize_content_blocks(
            normalized_message.get("content", "")
        )
        normalized_messages.append(normalized_message)

    return normalized_messages


def convert_to_langchain(messages):
    langchain_messages = []

    for message in normalize_messages(messages):
        role = message.get("role", "")
        content = message.get("content", "")

        if role == "system":
            langchain_messages.append(SystemMessage(content=content))
        elif role == "user":
            langchain_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            # Tool calls 처리
            tool_calls = message.get("toolCalls") or message.get("tool_calls") or []
            if tool_calls:
                logger.info("툴 콜이 있어~!")
                # LangChain의 AIMessage with tool_calls
                langchain_messages.append(AIMessage(
                    content=content,
                    additional_kwargs={
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["function"]["name"],
                                    "arguments": tc["function"]["arguments"]
                                }
                            }
                            for tc in tool_calls
                        ]
                    }
                ))
            else:
                langchain_messages.append(AIMessage(content=content))
        elif role == "tool":
            # Tool 응답 메시지
            langchain_messages.append(ToolMessage(
                content=content,
                tool_call_id=message.get("toolCallId") or message.get("tool_call_id") or ""
            ))
        else:
            langchain_messages.append(HumanMessage(content=content))

    return langchain_messages
