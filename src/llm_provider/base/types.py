from typing import TypedDict, Literal, List

class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str

class ChatRequest(TypedDict, total=False):
    model: str
    messages: List[Message]
    stream: bool
    max_tokens: int
    temperature: float


