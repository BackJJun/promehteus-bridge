"""
Unit tests for context_compressor module
"""
import pytest
from src.llm_provider.util.context_compressor import (
    count_tokens,
    compress_messages,
)


class TestCountTokens:
    def test_basic_messages(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"}
        ]
        token_count = count_tokens(messages)
        # Expect roughly 20-30 tokens
        assert token_count > 10
        assert token_count < 50

    def test_empty_messages(self):
        assert count_tokens([]) == 0


class TestCompressMessages:
    def test_preserves_system_and_last_user(self):
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "User 1"},
            {"role": "assistant", "content": "Assistant 1"},
            {"role": "user", "content": "Last User Message (MUST KEEP)"},
        ]

        compressed = compress_messages(messages, max_tokens=20)

        last_user = [m for m in compressed if m["role"] == "user"]
        assert any(m["content"] == "Last User Message (MUST KEEP)" for m in last_user)
        assert compressed[0]["role"] == "system"

    def test_no_compression_when_under_limit(self):
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        result = compress_messages(messages, max_tokens=10000)
        assert result == messages

    def test_oldest_qa_pair_removed_first(self):
        """가장 오래된 Q&A 쌍이 먼저 삭제되는지 확인"""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
            {"role": "assistant", "content": "Second answer"},
            {"role": "user", "content": "Third question"},
        ]

        compressed = compress_messages(messages, max_tokens=25)

        contents = [m["content"] for m in compressed]
        assert "First question" not in contents
        assert "First answer" not in contents
        assert "Third question" in contents

    def test_multiple_pairs_removed(self):
        """토큰이 많이 초과하면 여러 쌍이 삭제되는지 확인"""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Q1 " * 50},
            {"role": "assistant", "content": "A1 " * 50},
            {"role": "user", "content": "Q2 " * 50},
            {"role": "assistant", "content": "A2 " * 50},
            {"role": "user", "content": "Q3 " * 50},
            {"role": "assistant", "content": "A3 " * 50},
            {"role": "user", "content": "Last Q"},
        ]

        compressed = compress_messages(messages, max_tokens=20)

        last_user_msgs = [m for m in compressed if m["role"] == "user"]
        assert any("Last Q" in m["content"] for m in last_user_msgs)

    def test_tool_messages_removed_with_qa(self):
        """user 뒤에 tool 메시지가 있는 경우 함께 삭제되는지 확인"""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Old question"},
            {"role": "assistant", "content": "Calling tool..."},
            {"role": "tool", "content": "Tool result"},
            {"role": "user", "content": "Recent question"},
        ]

        compressed = compress_messages(messages, max_tokens=20)

        contents = [m["content"] for m in compressed]
        assert "Old question" not in contents
        assert "Calling tool..." not in contents
        assert "Tool result" not in contents
        assert "Recent question" in contents
