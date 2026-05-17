"""Tests for Chat Completions → Responses API SSE transformation."""

from __future__ import annotations

from openai.types.chat import ChatCompletionChunk

from primal_codex.responses import (
    _build_text_delta_event,
    _build_text_done_event,
    _format_sse,
)


def _chunk(
    content: str | None = None, finish: str | None = None
) -> ChatCompletionChunk:
    """Build a ``ChatCompletionChunk`` with one choice."""
    return ChatCompletionChunk(
        id="x",
        object="chat.completion.chunk",
        created=1,
        model="gpt-4",
        choices=[{"delta": {"content": content}, "index": 0, "finish_reason": finish}],
    )


class TestBuildTextDeltaEvent:
    """Build ``response.output_text.delta`` events via SDK types."""

    def test_content_delta(self) -> None:
        """Create a delta event with content."""
        event = _build_text_delta_event("Hello", "item_abc", 1)
        assert event.type == "response.output_text.delta"
        assert event.delta == "Hello"
        assert event.item_id == "item_abc"
        assert event.sequence_number == 1
        assert event.content_index == 0
        assert event.output_index == 0
        assert event.logprobs == []

    def test_sse_format(self) -> None:
        """Format the event as SSE."""
        event = _build_text_delta_event("A", "item_1", 2)
        sse = _format_sse("response.output_text.delta", event.model_dump(mode="json"))
        assert sse.startswith("event: response.output_text.delta\n")
        assert '"delta":"A"' in sse
        assert '"type":"response.output_text.delta"' in sse


class TestBuildTextDoneEvent:
    """Build ``response.output_text.done`` events via SDK types."""

    def test_done_event(self) -> None:
        """Create a done event with final text."""
        event = _build_text_done_event("Hello world", "item_abc", 3)
        assert event.type == "response.output_text.done"
        assert event.text == "Hello world"
        assert event.item_id == "item_abc"
        assert event.sequence_number == 3

    def test_sse_format(self) -> None:
        """Format the done event as SSE."""
        event = _build_text_done_event("Done", "item_1", 4)
        sse = _format_sse("response.output_text.done", event.model_dump(mode="json"))
        assert sse.startswith("event: response.output_text.done\n")
        assert '"text":"Done"' in sse
        assert '"type":"response.output_text.done"' in sse


class TestTransformOpenaiChunk:
    """Inline stream processing logic (reused by ``_relay_stream``)."""

    def test_role_only_chunk_skipped(self) -> None:
        """Skip chunks that only set ``role: assistant`` (content is ``None``)."""
        chunk = _chunk(content=None)
        assert not (chunk.choices and chunk.choices[0].delta.content)

    def test_content_takes_precedence_over_finish(self) -> None:
        """Content triggers delta even when finish_reason is present."""
        chunk = _chunk(content="Bye", finish="stop")
        assert chunk.choices[0].delta.content is not None

    def test_empty_choices_returns_none(self) -> None:
        """No processing when there are no choices."""
        chunk = ChatCompletionChunk(
            id="x",
            object="chat.completion.chunk",
            created=1,
            model="gpt-4",
            choices=[],
        )
        assert not chunk.choices
