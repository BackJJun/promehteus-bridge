from .openai import OpenAIProvider
from .vllm import VLLMProvider
# from .vllm_openai import VLLMProvider
from .claude import ClaudeProvider
from .gemini import  GeminiProvider
# from .gemini_direct import GeminiDirectProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "vllm": VLLMProvider,
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "gemini": GeminiProvider,
}

def get_provider(name: str):
    _provider = PROVIDERS.get(name.lower())
    if not _provider:
        raise ValueError(f"Unknown provider: {name}")
    return _provider()




