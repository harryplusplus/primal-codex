"""Tests for the ``_map_messages()`` and tool mapping helpers.

Verifies that a ``ResponsesApiRequest`` body is correctly mapped to
Chat Completions API parameters, and that tool definitions are
correctly transformed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.logging import LogCaptureFixture

from openai.types.responses import CustomTool, FunctionTool
from openai.types.shared.custom_tool_input_format import Grammar, Text

from primal_codex.responses import (
    CustomFormatGrammar,
    CustomFormatText,
    ResponsesApiRequest,
    _map_custom_format,
    _map_custom_tool,
    _map_function_tool,
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


class TestMapFunctionTool:
    """Mapping ``type: "function"`` tools."""

    def test_basic_function_tool(self) -> None:
        """Map a basic function tool."""
        raw = {
            "type": "function",
            "name": "get_weather",
            "description": "Get the weather",
            "strict": False,
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        }
        parsed = FunctionTool.model_validate(raw)
        result = _map_function_tool(parsed)
        assert result == {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
                "strict": False,
            },
        }

    def test_function_tool_minimal(self) -> None:
        """Map with only required fields (no description, no parameters)."""
        raw = {"type": "function", "name": "ping", "strict": False}
        parsed = FunctionTool.model_validate(raw)
        result = _map_function_tool(parsed)
        assert result == {
            "type": "function",
            "function": {
                "name": "ping",
                "description": "",
                "parameters": {},
                "strict": False,
            },
        }

    def test_function_tool_defer_loading_dropped(self) -> None:
        """``defer_loading`` is absent in Chat Completions."""
        raw = {
            "type": "function",
            "name": "lazy_load",
            "description": "Lazy loaded",
            "strict": True,
            "defer_loading": True,
            "parameters": {},
        }
        parsed = FunctionTool.model_validate(raw)
        result = _map_function_tool(parsed)
        # ``defer_loading`` must not appear in the output
        assert "defer_loading" not in result["function"]


class TestMapCustomFormat:
    """Mapping custom format subtypes."""

    def test_text_format_direct(self) -> None:
        """``type: "text"`` passes through unchanged."""
        raw = {"type": "text", "syntax": "", "definition": ""}
        parsed = Text.model_validate(raw)
        result = _map_custom_format(parsed)
        assert result == CustomFormatText(type="text")

    def test_grammar_format_nested(self) -> None:
        """``type: "grammar"`` nests fields under ``"grammar"``."""
        raw = {
            "type": "grammar",
            "syntax": "lark",
            "definition": 'start: "hello"',
        }
        parsed = Grammar.model_validate(raw)
        result = _map_custom_format(parsed)
        assert result == CustomFormatGrammar(
            type="grammar",
            grammar={
                "definition": 'start: "hello"',
                "syntax": "lark",
            },
        )


class TestMapCustomTool:
    """Mapping ``type: "custom"`` tools."""

    def test_basic_custom_tool(self) -> None:
        """Map a custom tool without format."""
        raw = {"type": "custom", "name": "exec", "description": "Execute"}
        parsed = CustomTool.model_validate(raw)
        result = _map_custom_tool(parsed)
        assert result == {
            "type": "custom",
            "custom": {
                "name": "exec",
                "description": "Execute",
            },
        }

    def test_custom_tool_with_text_format(self) -> None:
        """Map a custom tool with ``format.type: "text"``."""
        raw = {
            "type": "custom",
            "name": "exec",
            "description": "Execute",
            "format": {"type": "text", "syntax": "", "definition": ""},
        }
        parsed = CustomTool.model_validate(raw)
        result = _map_custom_tool(parsed)
        assert result == {
            "type": "custom",
            "custom": {
                "name": "exec",
                "description": "Execute",
                "format": {"type": "text"},
            },
        }

    def test_custom_tool_with_grammar_format(self) -> None:
        """Map a custom tool with ``format.type: "grammar"``."""
        raw = {
            "type": "custom",
            "name": "exec",
            "description": "Execute",
            "format": {
                "type": "grammar",
                "syntax": "lark",
                "definition": 'start: "a"',
            },
        }
        parsed = CustomTool.model_validate(raw)
        result = _map_custom_tool(parsed)
        assert result == {
            "type": "custom",
            "custom": {
                "name": "exec",
                "description": "Execute",
                "format": {
                    "type": "grammar",
                    "grammar": {
                        "definition": 'start: "a"',
                        "syntax": "lark",
                    },
                },
            },
        }


class TestMapTools:
    """Top-level tool mapping dispatcher."""

    def test_function_and_custom(self) -> None:
        """Map both ``function`` and ``custom`` tools."""
        raw_tools = [
            {"type": "function", "name": "f1", "strict": False, "parameters": {}},
            {"type": "custom", "name": "c1"},
        ]
        result = _map_tools(raw_tools)
        assert len(result) == 2
        assert result[0]["type"] == "function"
        assert result[1]["type"] == "custom"

    def test_unsupported_types_skipped(self, caplog: LogCaptureFixture) -> None:
        """Non-mappable types are skipped with a warning."""
        caplog.set_level(logging.WARNING)
        raw_tools = [
            {"type": "function", "name": "f1", "strict": False, "parameters": {}},
            {"type": "namespace", "name": "ns", "description": "", "tools": []},
            {"type": "custom", "name": "c1"},
            {"type": "local_shell"},
            {"type": "web_search"},
        ]
        result = _map_tools(raw_tools)
        assert len(result) == 2
        assert len(caplog.records) == 3
        for record in caplog.records:
            assert record.levelname == "WARNING"
            assert "Unsupported tool type" in record.message

    def test_non_dict_skipped(self, caplog: LogCaptureFixture) -> None:
        """Non-dict entries are skipped with a warning."""
        caplog.set_level(logging.WARNING)
        raw_tools: list = [
            "not_a_dict",
            {"type": "function", "name": "f1", "strict": False, "parameters": {}},
        ]
        result = _map_tools(raw_tools)
        assert len(result) == 1
        assert len(caplog.records) == 1
        assert "Non-dict tool entry" in caplog.records[0].message

    def test_malformed_function_skipped(self, caplog: LogCaptureFixture) -> None:
        """A function tool that fails validation is skipped."""
        caplog.set_level(logging.WARNING)
        raw_tools: list = [
            {"type": "function", "name": 123},  # name must be str
            {"type": "function", "name": "ok", "strict": False, "parameters": {}},
        ]
        result = _map_tools(raw_tools)
        assert len(result) == 1
        assert len(caplog.records) == 1
        assert "Failed to parse function tool" in caplog.records[0].message

    def test_empty_tools(self) -> None:
        """Empty input returns empty list."""
        assert _map_tools([]) == []
