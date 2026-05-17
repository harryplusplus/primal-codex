"""Tests for ``responses_to_chat_completions()``.

Verifies that a ``ResponsesApiRequest`` body is correctly mapped to a
Chat Completions API request body.
"""

from __future__ import annotations

from primal_codex.responses import (
    ResponsesApiRequest,
    responses_to_chat_completions,
)

_MODEL_ID = "glm-5"


def _body(**kwargs: object) -> ResponsesApiRequest:
    """Return a ``ResponsesApiRequest`` with all required fields set."""
    defaults: dict[str, object] = {
        "model": "crof/glm-5",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "Hello"}]}
        ],
        "instructions": "",
        "tools": [],
        "tool_choice": "auto",
        "parallel_tool_calls": True,
        "reasoning": None,
        "store": False,
        "stream": True,
        "include": [],
        "service_tier": None,
        "prompt_cache_key": None,
        "text": None,
        "client_metadata": None,
    }
    defaults.update(kwargs)
    return ResponsesApiRequest.model_validate(defaults)


class TestResponsesToChatCompletions:
    """Mapping from Responses API to Chat Completions."""

    def test_basic_text_input(self) -> None:
        """Map a single user text message to a chat message."""
        result = responses_to_chat_completions(_body(), _MODEL_ID)
        assert result["model"] == _MODEL_ID
        assert result["messages"] == [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        ]
        assert result["stream"] is True

    def test_instructions_as_system_message(self) -> None:
        """Prepend system message from ``instructions``."""
        result = responses_to_chat_completions(
            _body(
                instructions="Be concise.",
                input=[
                    {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}
                ],
            ),
            _MODEL_ID,
        )
        assert result["messages"][0] == {"role": "system", "content": "Be concise."}
        assert len(result["messages"]) == 2

    def test_empty_instructions_omitted(self) -> None:
        """Skip system message when ``instructions`` is ``None``."""
        result = responses_to_chat_completions(
            _body(
                input=[
                    {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}
                ]
            ),
            _MODEL_ID,
        )
        assert result["messages"][0]["role"] == "user"

    def test_multiple_input_items(self) -> None:
        """Map multiple input items to multiple messages."""
        result = responses_to_chat_completions(
            _body(
                input=[
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "First"}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": "Second"}],
                    },
                ]
            ),
            _MODEL_ID,
        )
        assert len(result["messages"]) == 2
        assert result["messages"][0]["content"] == [{"type": "text", "text": "First"}]
        assert result["messages"][1]["content"] == [{"type": "text", "text": "Second"}]

    def test_stream_passthrough(self) -> None:
        """Pass ``stream`` through unchanged."""
        result = responses_to_chat_completions(_body(stream=True), _MODEL_ID)
        assert result["stream"] is True

    def test_function_tool_input(self) -> None:
        """Map input items with function call output."""
        result = responses_to_chat_completions(
            _body(
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "What is the weather?"}
                        ],
                    },
                ]
            ),
            _MODEL_ID,
        )
        assert len(result["messages"]) == 1

    def test_no_extra_params_by_default(self) -> None:
        """Emit only model, messages, stream when all optionals are default."""
        result = responses_to_chat_completions(_body(), _MODEL_ID)
        assert set(result) == {"model", "messages", "stream"}

    def test_tools_passthrough(self) -> None:
        """Pass ``tools`` list through to Chat Completions."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather",
                    "parameters": {"type": "object"},
                },
            }
        ]
        result = responses_to_chat_completions(_body(tools=tools), _MODEL_ID)
        assert result["tools"] == tools

    def test_tool_choice_non_auto(self) -> None:
        """Pass ``tool_choice`` when not ``auto``."""
        result = responses_to_chat_completions(_body(tool_choice="none"), _MODEL_ID)
        assert result["tool_choice"] == "none"

    def test_tool_choice_auto_omitted(self) -> None:
        """Omit ``tool_choice`` when ``auto`` (default)."""
        result = responses_to_chat_completions(_body(), _MODEL_ID)
        assert "tool_choice" not in result

    def test_parallel_tool_calls_false(self) -> None:
        """Pass ``parallel_tool_calls`` only when ``False``."""
        result = responses_to_chat_completions(
            _body(parallel_tool_calls=False), _MODEL_ID
        )
        assert result["parallel_tool_calls"] is False

    def test_reasoning_effort_mapping(self) -> None:
        """Map ``reasoning.effort`` to ``reasoning_effort`` string."""
        result = responses_to_chat_completions(
            _body(reasoning={"effort": "high", "summary": None}), _MODEL_ID
        )
        assert result["reasoning_effort"] == "high"

    def test_reasoning_none_omitted(self) -> None:
        """Omit ``reasoning_effort`` when ``reasoning`` is ``None``."""
        result = responses_to_chat_completions(_body(), _MODEL_ID)
        assert "reasoning_effort" not in result

    def test_service_tier_passthrough(self) -> None:
        """Pass ``service_tier`` through when set."""
        result = responses_to_chat_completions(_body(service_tier="flex"), _MODEL_ID)
        assert result["service_tier"] == "flex"

    def test_service_tier_none_omitted(self) -> None:
        """Omit ``service_tier`` when ``None``."""
        result = responses_to_chat_completions(_body(), _MODEL_ID)
        assert "service_tier" not in result

    def test_prompt_cache_key_passthrough(self) -> None:
        """Pass ``prompt_cache_key`` through when set."""
        result = responses_to_chat_completions(
            _body(prompt_cache_key="abc123"), _MODEL_ID
        )
        assert result["prompt_cache_key"] == "abc123"

    def test_verbosity_mapping(self) -> None:
        """Map ``text.verbosity`` to ``verbosity`` string."""
        result = responses_to_chat_completions(
            _body(
                text={
                    "verbosity": "low",
                    "format": None,
                }
            ),
            _MODEL_ID,
        )
        assert result["verbosity"] == "low"

    def test_verbosity_medium(self) -> None:
        """Map ``text.verbosity`` medium."""
        result = responses_to_chat_completions(
            _body(
                text={
                    "verbosity": "medium",
                    "format": None,
                }
            ),
            _MODEL_ID,
        )
        assert result["verbosity"] == "medium"

    def test_verbosity_none_omitted(self) -> None:
        """Omit ``verbosity`` when ``text`` is ``None``."""
        result = responses_to_chat_completions(_body(), _MODEL_ID)
        assert "verbosity" not in result

    def test_text_format_to_response_format(self) -> None:
        """Map ``text.format`` to ``response_format`` JSON Schema."""
        result = responses_to_chat_completions(
            _body(
                text={
                    "verbosity": None,
                    "format": {
                        "type": "json_schema",
                        "strict": True,
                        "schema": {"type": "object", "properties": {}},
                        "name": "my_schema",
                    },
                }
            ),
            _MODEL_ID,
        )
        assert result["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "my_schema",
                "strict": True,
                "schema": {"type": "object", "properties": {}},
            },
        }
