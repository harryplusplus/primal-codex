"""Tests for the ``_map_messages()`` and ``_map_tools()`` helpers.

Verifies that a ``ResponsesApiRequest`` body is correctly mapped to
Chat Completions API parameters.
"""

from __future__ import annotations

from primal_codex.responses import (
    ResponsesApiRequest,
    _map_messages,
    _map_tools,
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


class TestMapMessages:
    """Mapping Responses API input items to Chat Completions messages."""

    def test_basic_text_input(self) -> None:
        """Map a single user text message to a chat message."""
        messages = _map_messages(_body())
        assert messages == [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
        ]

    def test_instructions_as_system_message(self) -> None:
        """Prepend system message from ``instructions``."""
        messages = _map_messages(
            _body(
                instructions="Be concise.",
                input=[
                    {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}
                ],
            )
        )
        assert messages[0] == {"role": "system", "content": "Be concise."}
        assert len(messages) == 2

    def test_empty_instructions_omitted(self) -> None:
        """Skip system message when ``instructions`` is empty string."""
        messages = _map_messages(
            _body(
                input=[
                    {"role": "user", "content": [{"type": "input_text", "text": "Hi"}]}
                ]
            )
        )
        assert messages[0]["role"] == "user"

    def test_multiple_input_items(self) -> None:
        """Map multiple input items to multiple messages."""
        messages = _map_messages(
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
            )
        )
        assert len(messages) == 2
        assert messages[0]["content"] == [{"type": "text", "text": "First"}]
        assert messages[1]["content"] == [{"type": "text", "text": "Second"}]

    def test_function_tool_input(self) -> None:
        """Map input items with function call output."""
        messages = _map_messages(
            _body(
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "What is the weather?"}
                        ],
                    },
                ]
            )
        )
        assert len(messages) == 1


class TestMapTools:
    """Mapping Responses API parameters to Chat Completions tool/extra params."""

    def test_no_extra_params_by_default(self) -> None:
        """Return empty dict when all optionals are default."""
        params = _map_tools(_body())
        assert params == {}

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
        params = _map_tools(_body(tools=tools))
        assert params["tools"] == tools

    def test_tool_choice_non_auto(self) -> None:
        """Pass ``tool_choice`` when not ``auto``."""
        params = _map_tools(_body(tool_choice="none"))
        assert params["tool_choice"] == "none"

    def test_tool_choice_auto_omitted(self) -> None:
        """Omit ``tool_choice`` when ``auto`` (default)."""
        params = _map_tools(_body())
        assert "tool_choice" not in params

    def test_parallel_tool_calls_false(self) -> None:
        """Pass ``parallel_tool_calls`` only when ``False``."""
        params = _map_tools(_body(parallel_tool_calls=False))
        assert params["parallel_tool_calls"] is False

    def test_parallel_tool_calls_true_omitted(self) -> None:
        """Omit ``parallel_tool_calls`` when ``True`` (default)."""
        params = _map_tools(_body())
        assert "parallel_tool_calls" not in params

    def test_reasoning_effort_mapping(self) -> None:
        """Map ``reasoning.effort`` to ``reasoning_effort`` string."""
        params = _map_tools(_body(reasoning={"effort": "high", "summary": None}))
        assert params["reasoning_effort"] == "high"

    def test_reasoning_none_omitted(self) -> None:
        """Omit ``reasoning_effort`` when ``reasoning`` is ``None``."""
        params = _map_tools(_body())
        assert "reasoning_effort" not in params

    def test_service_tier_passthrough(self) -> None:
        """Pass ``service_tier`` through when set."""
        params = _map_tools(_body(service_tier="flex"))
        assert params["service_tier"] == "flex"

    def test_service_tier_none_omitted(self) -> None:
        """Omit ``service_tier`` when ``None``."""
        params = _map_tools(_body())
        assert "service_tier" not in params

    def test_prompt_cache_key_passthrough(self) -> None:
        """Pass ``prompt_cache_key`` through when set."""
        params = _map_tools(_body(prompt_cache_key="abc123"))
        assert params["prompt_cache_key"] == "abc123"

    def test_verbosity_mapping(self) -> None:
        """Map ``text.verbosity`` to ``verbosity`` string."""
        params = _map_tools(
            _body(
                text={
                    "verbosity": "low",
                    "format": None,
                }
            )
        )
        assert params["verbosity"] == "low"

    def test_verbosity_medium(self) -> None:
        """Map ``text.verbosity`` medium."""
        params = _map_tools(
            _body(
                text={
                    "verbosity": "medium",
                    "format": None,
                }
            )
        )
        assert params["verbosity"] == "medium"

    def test_verbosity_none_omitted(self) -> None:
        """Omit ``verbosity`` when ``text`` is ``None``."""
        params = _map_tools(_body())
        assert "verbosity" not in params

    def test_text_format_to_response_format(self) -> None:
        """Map ``text.format`` to ``response_format`` JSON Schema."""
        params = _map_tools(
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
            )
        )
        assert params["response_format"] == {
            "type": "json_schema",
            "json_schema": {
                "name": "my_schema",
                "strict": True,
                "schema": {"type": "object", "properties": {}},
            },
        }
