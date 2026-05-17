"""Response handling for the ``/responses`` endpoint."""

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import openai
from openai import AsyncOpenAI, AsyncStream
from openai.types.chat.chat_completion_assistant_message_param import (
    ChatCompletionAssistantMessageParam,
)
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat.chat_completion_content_part_image_param import (
    ChatCompletionContentPartImageParam,
    ImageURL,
)
from openai.types.chat.chat_completion_content_part_param import (
    ChatCompletionContentPartParam,
)
from openai.types.chat.chat_completion_content_part_param import (
    File as ChatCompletionFile,
)
from openai.types.chat.chat_completion_content_part_param import (
    FileFile as ChatCompletionFileFile,
)
from openai.types.chat.chat_completion_content_part_text_param import (
    ChatCompletionContentPartTextParam,
)
from openai.types.chat.chat_completion_developer_message_param import (
    ChatCompletionDeveloperMessageParam,
)
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
)
from openai.types.chat.chat_completion_system_message_param import (
    ChatCompletionSystemMessageParam,
)
from openai.types.chat.chat_completion_user_message_param import (
    ChatCompletionUserMessageParam,
)
from openai.types.responses.easy_input_message import EasyInputMessage
from openai.types.responses.response_format_text_json_schema_config import (
    ResponseFormatTextJSONSchemaConfig,
)
from openai.types.responses.response_input_content import ResponseInputContent
from openai.types.responses.response_text_config import ResponseTextConfig
from openai.types.shared.reasoning import Reasoning
from pydantic import BaseModel


class ResponsesApiRequest(BaseModel):
    """Wire-format mirror of the Codex client's ``ResponsesApiRequest``.

    This is **not** the standard OpenAI Responses API.

    The Codex client
    (``<repo_root>/external/codex/codex-rs/codex-api/src/common.rs``)
    serializes its own ``ResponsesApiRequest`` struct as JSON and sends
    it to the Primal Codex ``POST /responses`` endpoint.  This Pydantic
    model deserializes that same JSON.

    The OpenAI SDK's ``ResponseCreateParamsBase``
    (``<repo_root>/.venv/lib/python3.11/site-packages/openai/types/
    responses/response_create_params.py``) is the *spec* for OpenAI's
    standard Responses API, but the Codex client does **not** send that
    wire format.  Instead it sends a subset of those fields (12 of 28)
    plus two Codex-specific ones:

    * ``client_metadata`` — traceparent/tracestate for W3C distributed
      tracing; not part of the OpenAI spec.
    * ``stream`` — a plain ``bool``, whereas OpenAI splits this into
      two type-level variants (``ResponseCreateParamsNonStreaming`` vs
      ``ResponseCreateParamsStreaming``).

    The following OpenAI-standard fields are **omitted** because the
    Codex client handles them differently or doesn't need them:
    ``temperature``, ``top_p``, ``top_logprobs``, ``max_output_tokens``,
    ``max_tool_calls``, ``previous_response_id``, ``conversation``,
    ``metadata``, ``user``, ``safety_identifier``, ``background``,
    ``context_management``, ``truncation``, ``prompt``,
    ``prompt_cache_retention``, ``stream_options``.

    Every remaining field matches the Rust struct one-to-one:

    * ``Option<T>`` → ``type | None``, defaults to ``None``.
    * ``T`` (non-optional) → ``T``, with the same default as the
      Rust side (``""`` for ``String``, ``[]`` for ``Vec``, ``false``
      for ``bool``, etc.).  Note that ``skip_serializing_if`` on the
      Rust side is a serialization-only optimisation — it does not
      make the field optional at the wire level.

    **Internal types are reused from the OpenAI SDK** wherever the
    wire format overlaps: ``EasyInputMessage``, ``ResponseInputContent``,
    ``ResponseTextConfig``, and ``Reasoning`` all come from
    ``openai.types.responses.*``.
    """

    model: str
    input: list[EasyInputMessage]
    instructions: str = ""
    tools: list[Any] = []
    tool_choice: str = "auto"
    parallel_tool_calls: bool = True
    reasoning: Reasoning | None = None
    store: bool = False
    stream: bool = True
    include: list[str] = []
    service_tier: str | None = None
    prompt_cache_key: str | None = None
    text: ResponseTextConfig | None = None
    client_metadata: dict[str, str] | None = None


def _map_content_part(
    part: ResponseInputContent,
) -> ChatCompletionContentPartParam | None:
    """Map a single Responses API content part to Chat Completions format.

    Returns ``None`` for unrecognised part types.
    """
    if part.type == "input_text":
        return ChatCompletionContentPartTextParam(text=part.text, type="text")
    if part.type == "input_image":
        url = part.image_url or part.file_id
        if url is None:
            return None
        image = ImageURL(url=url)
        if part.detail in ("auto", "low", "high"):
            image["detail"] = part.detail  # type: ignore[typed-dict-key]
        return ChatCompletionContentPartImageParam(type="image_url", image_url=image)
    if part.type == "input_file":
        url = part.file_url or part.file_data
        if url is None:
            return None
        return ChatCompletionFile(
            type="file",
            file=ChatCompletionFileFile(file_id=url, filename=part.filename or ""),
        )
    return None


def _map_item_content(
    content: str | list[ResponseInputContent],
) -> str | list[ChatCompletionContentPartParam]:
    """Map an input item's ``content`` to Chat Completions format."""
    if isinstance(content, str):
        return content
    return [
        mapped for part in content if (mapped := _map_content_part(part)) is not None
    ]


def _map_messages(body: ResponsesApiRequest) -> list[ChatCompletionMessageParam]:
    """Map input items to Chat Completions messages."""
    messages: list[ChatCompletionMessageParam] = []
    if body.instructions:
        messages.append(
            ChatCompletionSystemMessageParam(role="system", content=body.instructions)
        )
    for item in body.input:
        mapped = _map_item_content(item.content)
        if not mapped:
            continue
        if item.role == "user":
            messages.append(ChatCompletionUserMessageParam(role="user", content=mapped))
        elif item.role == "system":
            messages.append(
                ChatCompletionSystemMessageParam(role="system", content=mapped)  # type: ignore[arg-type]
            )
        elif item.role == "developer":
            messages.append(
                ChatCompletionDeveloperMessageParam(role="developer", content=mapped)  # type: ignore[arg-type]
            )
        elif item.role == "assistant":
            messages.append(
                ChatCompletionAssistantMessageParam(role="assistant", content=mapped)  # type: ignore[arg-type]
            )
    return messages


def _map_text_controls(body: ResponsesApiRequest) -> dict[str, Any]:
    """Map ``text`` controls to Chat Completions parameters."""
    params: dict[str, Any] = {}
    if body.text is None:
        return params
    if body.text.verbosity is not None:
        params["verbosity"] = body.text.verbosity
    fmt = body.text.format
    if isinstance(fmt, ResponseFormatTextJSONSchemaConfig):
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": fmt.name,
                "schema": fmt.schema_,
                "strict": fmt.strict,
            },
        }
    return params


def _map_tools(body: ResponsesApiRequest) -> dict[str, Any]:
    """Map tool-related parameters to Chat Completions format."""
    params: dict[str, Any] = {}
    if body.tools:
        params["tools"] = body.tools
    if body.tool_choice != "auto":
        params["tool_choice"] = body.tool_choice
    if not body.parallel_tool_calls:
        params["parallel_tool_calls"] = body.parallel_tool_calls
    if body.reasoning and body.reasoning.effort:
        params["reasoning_effort"] = body.reasoning.effort
    if body.service_tier is not None:
        params["service_tier"] = body.service_tier
    if body.prompt_cache_key is not None:
        params["prompt_cache_key"] = body.prompt_cache_key
    params.update(_map_text_controls(body))
    return params


def responses_to_chat_completions(
    body: ResponsesApiRequest, model_id: str
) -> dict[str, Any]:
    """Map a ``ResponsesApiRequest`` to a Chat Completions request body.

    The following Responses API fields have no Chat Completions equivalent
    and are intentionally omitted:

    * ``store`` — Responses API concept for persisting responses server-side.
    * ``include`` — Responses API concept for requesting extra data in the
      response envelope (e.g. token usage, model metadata). Use
      ``stream_options.include_usage`` instead if needed.
    * ``reasoning.summary`` — Requests the model to produce reasoning
      summaries alongside its output. Chat Completions only supports
      ``reasoning_effort``.
    * ``client_metadata`` — Codex-internal tracing metadata (traceparent,
      tracestate). Not passed to the upstream; could be forwarded as custom
      HTTP headers if the upstream supports distributed tracing.
    """
    result: dict[str, Any] = {
        "model": model_id,
        "messages": _map_messages(body),
        "stream": body.stream,
        **_map_tools(body),
    }
    return result


def generate_response_id() -> str:
    """Generate a unique response ID.

    Sample: resp_0309c0d6cb4ff519016a032143c2288191b3759a2e031f11b2
    """
    return f"resp_{os.urandom(25).hex()}"


def _generate_reasoning_item_id() -> str:
    """Generate a unique reasoning item ID.

    Sample: rs_0309c0d6cb4ff519016a03214c9eb08191b938b46b170f9d90
    """
    return f"rs_{os.urandom(25).hex()}"


def _generate_message_item_id() -> str:
    """Generate a unique message item ID.

    Sample: msg_0309c0d6cb4ff519016a03214e4e7c8191bf036ec8113050a7
    """
    return f"msg_{os.urandom(25).hex()}"


def _generate_function_call_item_id() -> str:
    """Generate a unique function call item ID.

    Sample: fc_0309c0d6cb4ff519016a032152eb1c819182b3994c61de195b
    """
    return f"fc_{os.urandom(25).hex()}"


# 24-char [a-zA-Z0-9] using rejection sampling for unbiased distribution.
_BASE62 = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
_CALL_ID_CHARS = 24
_CALL_ID_REJECT_THRESHOLD = 248


def _generate_call_id() -> str:
    """Generate a unique call ID (``call_`` + 24 base62 chars, rejection-sampled).

    Sample: call_ueWI5DaDk7YLNXdK8uBWyUTg

    Uses rejection sampling (byte < 248 → byte % 62) for unbiased output.
    """
    result: list[str] = []
    while len(result) < _CALL_ID_CHARS:
        for b in os.urandom(32):
            if b < _CALL_ID_REJECT_THRESHOLD:
                result.append(_BASE62[b % 62])
                if len(result) == _CALL_ID_CHARS:
                    break
    return f"call_{''.join(result)}"


def _format_sse(event_name: str, data: dict[str, Any]) -> str:
    """Format a dict as an SSE ``event:`` / ``data:`` pair."""
    encoded = json.dumps(data, separators=(",", ":"))
    return f"event: {event_name}\ndata: {encoded}\n\n"


def _stream_extra_kwargs(upstream_body: dict[str, Any]) -> dict[str, Any]:
    """Extract optional parameters from the upstream body."""
    kwargs: dict[str, Any] = {}
    for key in (
        "tools",
        "tool_choice",
        "parallel_tool_calls",
        "reasoning_effort",
        "service_tier",
        "prompt_cache_key",
        "verbosity",
        "response_format",
    ):
        if key in upstream_body:
            kwargs[key] = upstream_body[key]
    return kwargs


def _usage_from_chunk(
    chunk: ChatCompletionChunk,
) -> dict[str, object] | None:
    """Extract usage info from a chunk if present."""
    if not chunk.usage:
        return None
    u = chunk.usage
    usage: dict[str, object] = {
        "input_tokens": u.prompt_tokens,
        "output_tokens": u.completion_tokens,
        "total_tokens": u.total_tokens,
    }
    if u.completion_tokens_details and u.completion_tokens_details.reasoning_tokens:
        usage["reasoning_output_tokens"] = u.completion_tokens_details.reasoning_tokens
    return usage


async def _emit_content_events(
    stream: AsyncStream[ChatCompletionChunk],
    item_id: str,
    usage_out: list[dict[str, object] | None],
) -> AsyncIterator[str]:
    """Emit item/delta/done SSE events from upstream chunks."""
    final_text = ""
    item_started = False

    async for chunk in stream:  # type: ignore[type-var]
        if chunk.usage:
            usage_out[0] = _usage_from_chunk(chunk)

        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        content = choice.delta.content
        if content:
            if not item_started:
                item_started = True
                yield _format_sse(
                    "response.output_item.added",
                    {
                        "type": "response.output_item.added",
                        "item": {
                            "id": item_id,
                            "type": "message",
                            "role": "assistant",
                            "content": [],
                        },
                    },
                )
            final_text += content
            yield _format_sse(
                "response.output_text.delta",
                {"type": "response.output_text.delta", "delta": content},
            )
        elif choice.finish_reason:
            if not item_started:
                item_started = True
                yield _format_sse(
                    "response.output_item.added",
                    {
                        "type": "response.output_item.added",
                        "item": {
                            "id": item_id,
                            "type": "message",
                            "role": "assistant",
                            "content": [],
                        },
                    },
                )
            yield _format_sse(
                "response.output_text.done",
                {"type": "response.output_text.done", "text": final_text},
            )
            yield _format_sse(
                "response.output_item.done",
                {
                    "type": "response.output_item.done",
                    "item": {
                        "id": item_id,
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": final_text}],
                    },
                },
            )

    # Stream ended without any content chunks.
    # Emit empty item events so codex can produce item.completed even when
    # the upstream returned no content (e.g. oversized instructions/tools).
    if not item_started:
        yield _format_sse(
            "response.output_item.added",
            {
                "type": "response.output_item.added",
                "item": {
                    "id": item_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                },
            },
        )
        yield _format_sse(
            "response.output_text.done",
            {"type": "response.output_text.done", "text": ""},
        )
        yield _format_sse(
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "item": {
                    "id": item_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": ""}],
                },
            },
        )


async def relay_stream(
    body: ResponsesApiRequest,
    model_id: str,
    base_url: str,
    api_key: str | None,
    response_id: str,
) -> AsyncIterator[str]:
    """Forward the mapped Chat Completions request using the OpenAI SDK."""
    upstream_body = responses_to_chat_completions(body, model_id)
    item_id = _generate_message_item_id()

    yield _format_sse(
        "response.created",
        {"type": "response.created", "response": {"id": response_id}},
    )

    async with AsyncOpenAI(api_key=api_key, base_url=base_url) as client:
        extra_kwargs = _stream_extra_kwargs(upstream_body)
        try:
            stream = await client.chat.completions.create(
                model=upstream_body["model"],
                messages=upstream_body["messages"],
                stream=True,
                stream_options={"include_usage": True},
                **extra_kwargs,
            )
        except openai.APIError as e:
            yield _format_sse(
                "response.failed",
                {
                    "type": "response.failed",
                    "response": {
                        "id": response_id,
                        "status": "failed",
                        "error": {"code": "upstream_error", "message": str(e)},
                    },
                },
            )
            return

        usage_out: list[dict[str, object] | None] = [None]
        # pyrefly cannot infer stream type through **extra_kwargs
        events = _emit_content_events(stream, item_id, usage_out)  # type: ignore[type-var]
        async for event in events:  # type: ignore[type-var]
            yield event
        final_usage = usage_out[0]

    # 6. response.completed
    resp: dict[str, object] = {"id": response_id, "status": "completed"}
    if final_usage:
        resp["usage"] = final_usage
    yield _format_sse(
        "response.completed",
        {"type": "response.completed", "response": resp},
    )
