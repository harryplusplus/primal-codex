"""Response handling for the ``/responses`` endpoint."""

import json
import os
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any

import openai
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
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
from pydantic import BaseModel, ValidationError


class ResponsesApiRequest(BaseModel):
    """Pydantic model matching the Codex ``ResponsesApiRequest``.

    All ``Optional`` Rust fields (``Option<T>``) default to ``None``.
    Required fields (``model``, ``input``) have no default.
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


def responses_to_chat_completions(body: ResponsesApiRequest) -> dict[str, Any]:
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
    _, model_id = body.model.split("/", 1)
    result: dict[str, Any] = {
        "model": model_id,
        "messages": _map_messages(body),
        "stream": body.stream,
        **_map_tools(body),
    }
    return result


async def handle_responses(request: Request) -> JSONResponse | StreamingResponse:
    """Handle a ``POST /responses`` request.

    Parses and validates the request body with Pydantic, then streams
    the relayed response as server-sent events.

    Args:
        request: The incoming FastAPI request.

    Returns:
        A ``StreamingResponse`` for valid streaming requests, or a
        ``JSONResponse`` error otherwise.

    """
    try:
        raw = await request.json()
    except json.JSONDecodeError as e:
        return JSONResponse(
            {"error": f"Invalid JSON in request body: {e}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    try:
        body = ResponsesApiRequest.model_validate(raw)
    except ValidationError as e:
        return JSONResponse(
            {"error": f"Invalid request body: {e}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    if not body.stream:
        return JSONResponse(
            {"error": "Only streaming responses are supported."},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    ctx = request.app.state.ctx
    if body.model not in ctx.model_map:
        return JSONResponse(
            {"error": f"Model not found: {body.model}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    provider_id, _ = body.model.split("/", 1)
    provider = ctx.primal_config.providers.get(provider_id)
    if provider is None or provider.base_url is None:
        return JSONResponse(
            {"error": f"Provider not found for model: {body.model}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )

    api_key = provider.resolve_api_key()

    response_id = f"resp_{_random_hex(25)}"

    return StreamingResponse(
        _relay_stream(body, provider.base_url, api_key, response_id),
        media_type="text/event-stream",
        headers={
            "cache-control": "no-cache",
            "x-accel-buffering": "no",
        },
    )


def _random_hex(bytes_count: int) -> str:
    """Generate a hex string from ``bytes_count`` random bytes."""
    return os.urandom(bytes_count).hex()


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


async def _relay_stream(
    body: ResponsesApiRequest,
    base_url: str,
    api_key: str | None,
    response_id: str,
) -> AsyncIterator[str]:
    """Forward the mapped Chat Completions request using the OpenAI SDK."""
    upstream_body = responses_to_chat_completions(body)
    item_id = f"msg_{_random_hex(25)}"

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
