"""Tests for the SSE event transformation in the responses proxy."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from openai.types.chat import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice, ChoiceDelta

from primal_codex.responses import _usage_from_chunk


def _make_chunk(
    content: str | None = None,
    finish_reason: str | None = None,
    usage: dict[str, Any] | None = None,
) -> ChatCompletionChunk:
    """Build a minimal ``ChatCompletionChunk`` for testing."""
    delta = ChoiceDelta(content=content, role="assistant", tool_calls=None)
    choices = [Choice(index=0, delta=delta, finish_reason=finish_reason, logprobs=None)]
    usage_obj: object | None = None
    if usage:
        usage_mock = MagicMock()
        usage_mock.prompt_tokens = usage.get("prompt_tokens", 0)
        usage_mock.completion_tokens = usage.get("completion_tokens", 0)
        usage_mock.total_tokens = usage.get("total_tokens", 0)
        completion_details = MagicMock()
        completion_details.reasoning_tokens = usage.get("completion_reasoning_tokens")
        usage_mock.completion_tokens_details = completion_details
        usage_obj = usage_mock
    return MagicMock(
        id="chunk_abc",
        object="chat.completion.chunk",
        created=1234567890,
        model="test-model",
        choices=choices,
        usage=usage_obj,
        spec=ChatCompletionChunk,
    )


class TestUsageFromChunk:
    """Extract usage info from a chunk."""

    def test_no_usage_returns_none(self) -> None:
        """A chunk without usage returns ``None``."""
        chunk = _make_chunk(content="hello", usage=None)
        assert _usage_from_chunk(chunk) is None

    def test_basic_usage_extracted(self) -> None:
        """Basic prompt/completion/total tokens are extracted."""
        chunk = _make_chunk(
            content="hello",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        )
        result = _usage_from_chunk(chunk)
        assert result == {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }

    def test_reasoning_tokens_included(self) -> None:
        """Reasoning tokens are included when present."""
        chunk = _make_chunk(
            content="hello",
            usage={
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
                "completion_reasoning_tokens": 5,
            },
        )
        result = _usage_from_chunk(chunk)
        assert result == {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
            "reasoning_output_tokens": 5,
        }
