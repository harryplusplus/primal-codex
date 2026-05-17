"""Response handling for the ``/responses`` endpoint."""

import json
import os
import time
from collections.abc import AsyncIterator
from http import HTTPStatus
from typing import Any

import openai
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_assistant_message_param import (
    ChatCompletionAssistantMessageParam,
)
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
from openai.types.responses.response import Response as OpenAIResponse
from openai.types.responses.response_completed_event import ResponseCompletedEvent
from openai.types.responses.response_error_event import ResponseErrorEvent
from openai.types.responses.response_format_text_json_schema_config import (
    ResponseFormatTextJSONSchemaConfig,
)
from openai.types.responses.response_input_content import ResponseInputContent
from openai.types.responses.response_text_config import ResponseTextConfig
from openai.types.responses.response_text_delta_event import ResponseTextDeltaEvent
from openai.types.responses.response_text_done_event import ResponseTextDoneEvent
from openai.types.shared.reasoning import Reasoning
from pydantic import BaseModel, ValidationError


class ResponsesApiRequest(BaseModel):
    """Pydantic model matching the Codex ``ResponsesApiRequest``."""

    model: str
    instructions: str
    input: list[EasyInputMessage]
    tools: list[Any]
    tool_choice: str
    parallel_tool_calls: bool
    reasoning: Reasoning | None
    store: bool
    stream: bool
    include: list[str]
    service_tier: str | None
    prompt_cache_key: str | None
    text: ResponseTextConfig | None
    client_metadata: dict[str, str] | None


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
        headers={"content-type": "text/event-stream"},
    )


def _random_hex(bytes_count: int) -> str:
    """Generate a hex string from ``bytes_count`` random bytes."""
    return os.urandom(bytes_count).hex()


def _format_sse(event_name: str, data: dict[str, Any]) -> str:
    """Format a dict as an SSE ``event:`` / ``data:`` pair."""
    return f"event: {event_name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _build_text_delta_event(
    content: str, item_id: str, seq: int
) -> ResponseTextDeltaEvent:
    """Build a ``response.output_text.delta`` event."""
    return ResponseTextDeltaEvent(
        type="response.output_text.delta",
        delta=content,
        content_index=0,
        item_id=item_id,
        logprobs=[],
        output_index=0,
        sequence_number=seq,
    )


def _build_text_done_event(text: str, item_id: str, seq: int) -> ResponseTextDoneEvent:
    """Build a ``response.output_text.done`` event."""
    return ResponseTextDoneEvent(
        type="response.output_text.done",
        content_index=0,
        item_id=item_id,
        logprobs=[],
        output_index=0,
        sequence_number=seq,
        text=text,
    )


def _build_completed_event(
    body: ResponsesApiRequest, model: str, response_id: str, seq: int
) -> ResponseCompletedEvent:
    """Build a ``response.completed`` event with a minimal response."""
    minimal_response = OpenAIResponse(
        id=response_id,
        created_at=time.time(),
        model=model,
        object="response",
        output=[],
        parallel_tool_calls=body.parallel_tool_calls,
        tool_choice=body.tool_choice,
        tools=[],
    )
    return ResponseCompletedEvent(
        type="response.completed",
        response=minimal_response,
        sequence_number=seq,
    )


async def _relay_stream(
    body: ResponsesApiRequest,
    base_url: str,
    api_key: str | None,
    response_id: str,
) -> AsyncIterator[str]:
    """Forward the mapped Chat Completions request using the OpenAI SDK."""
    upstream_body = responses_to_chat_completions(body)
    seq = 0
    item_id = f"msg_{_random_hex(25)}"
    final_text: str | None = None

    async with AsyncOpenAI(api_key=api_key, base_url=base_url) as client:
        extra_kwargs: dict[str, Any] = {}
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
                extra_kwargs[key] = upstream_body[key]
        try:
            stream = await client.chat.completions.create(
                model=upstream_body["model"],
                messages=upstream_body["messages"],
                stream=True,
                **extra_kwargs,
            )
        except openai.APIError as e:
            error_event = ResponseErrorEvent(
                type="error",
                message=f"Upstream connection failed: {e}",
                sequence_number=seq,
            )
            yield _format_sse("error", error_event.model_dump(mode="json"))
            return

        # pyrefly cannot infer stream type through **extra_kwargs
        async for chunk in stream:  # type: ignore[type-var]
            seq += 1
            if chunk.choices:
                choice = chunk.choices[0]
                content = choice.delta.content
                if content:
                    final_text = (final_text or "") + content
                    delta_event = _build_text_delta_event(content, item_id, seq)
                    yield _format_sse(
                        "response.output_text.delta",
                        delta_event.model_dump(mode="json"),
                    )
                elif choice.finish_reason:
                    done_text = final_text or ""
                    done_event = _build_text_done_event(done_text, item_id, seq)
                    yield _format_sse(
                        "response.output_text.done",
                        done_event.model_dump(mode="json"),
                    )

    seq += 1
    completed_event = _build_completed_event(
        body, upstream_body["model"], response_id, seq
    )
    yield _format_sse(
        "response.completed",
        completed_event.model_dump(mode="json"),
    )
