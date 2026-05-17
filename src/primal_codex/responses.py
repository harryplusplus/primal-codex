"""Response handling for the ``/responses`` endpoint.

SSE event payload types
    The TypedDict classes in this module (``ResponseCreatedEvent``,
    ``ResponseCompletedEvent``, etc.) share type names with the OpenAI
    SDK's corresponding Pydantic models so that developers can
    cross-reference during review.

    Every class docstring lists two reference types:
        * OpenAI SDK path — the client-side Pydantic model.
        * Codex Rust path — the struct the Codex CLI uses to
          deserialise the event.
"""

import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, Literal, NotRequired, TypeAlias, TypedDict

import openai
from openai import AsyncOpenAI, AsyncStream, Omit
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
from openai.types.chat.chat_completion_custom_tool_param import (
    ChatCompletionCustomToolParam,
    Custom,
    CustomFormatGrammar,
    CustomFormatText,
)
from openai.types.chat.chat_completion_developer_message_param import (
    ChatCompletionDeveloperMessageParam,
)
from openai.types.chat.chat_completion_function_tool_param import (
    ChatCompletionFunctionToolParam,
    FunctionDefinition,
)
from openai.types.chat.chat_completion_message_param import (
    ChatCompletionMessageParam,
)
from openai.types.chat.chat_completion_stream_options_param import (
    ChatCompletionStreamOptionsParam,
)
from openai.types.chat.chat_completion_system_message_param import (
    ChatCompletionSystemMessageParam,
)
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)
from openai.types.chat.chat_completion_user_message_param import (
    ChatCompletionUserMessageParam,
)
from openai.types.responses.custom_tool import CustomTool
from openai.types.responses.easy_input_message import EasyInputMessage
from openai.types.responses.function_tool import FunctionTool
from openai.types.responses.response_format_text_json_schema_config import (
    ResponseFormatTextJSONSchemaConfig,
)
from openai.types.responses.response_input_content import ResponseInputContent
from openai.types.responses.response_text_config import ResponseTextConfig
from openai.types.shared.custom_tool_input_format import (
    Grammar,
    Text,
)
from openai.types.shared.reasoning import Reasoning
from openai.types.shared_params.response_format_json_schema import (
    ResponseFormatJSONSchema,
)
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ResponseError(TypedDict):
    """Error payload embedded inside a failed ``response`` object.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_error.ResponseError``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses.rs``
        local ``Error`` struct (``{ code, message, … }`` inside
        ``response.error``)

    The ``code`` field drives the Codex client's error classification:
    ``rate_limit_exceeded``, ``context_length_exceeded``,
    ``insufficient_quota``, ``invalid_prompt``, ``cyber_policy``,
    ``server_is_overloaded``, ``usage_not_included``.

    Attributes:
        code: Machine-readable error code (e.g. ``upstream_error``).
              The OpenAI SDK uses a closed ``Literal`` union; Primal
              Codex keeps it as ``str`` because upstream proxies may
              return codes outside that set.
        message: Human-readable description of the error.

    """

    code: str
    message: str


class ResponseUsage(TypedDict):
    """Token usage embedded inside a completed ``response`` object.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_usage.ResponseUsage``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``ResponseCompletedUsage``
        (``{ input_tokens, output_tokens, total_tokens }``)

    The OpenAI SDK and Codex Rust client expect nested detail blocks
    (``input_tokens_details`` / ``output_tokens_details``).  Primal
    Codex **currently** omits those and may add a flat
    ``reasoning_output_tokens`` key that Rust serde silently ignores.
    This is a known gap to be fixed in a follow-up.

    Attributes:
        input_tokens: Number of input (prompt) tokens.
        output_tokens: Number of output (completion) tokens.
        total_tokens: Total tokens used (input + output).
        input_tokens_details: Breakdown of input tokens (cached vs.
            non-cached).  **Not yet emitted** — reserved for future
            alignment with the OpenAI SDK / Codex client expectations.
        output_tokens_details: Breakdown of output tokens (reasoning
            vs. non-reasoning).  **Not yet emitted** — reserved for
            future alignment.

    """

    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_tokens_details: NotRequired["ResponseUsageInputTokensDetails"]
    output_tokens_details: NotRequired["ResponseUsageOutputTokensDetails"]


class ResponseUsageInputTokensDetails(TypedDict):
    """Nested detail for cached input tokens.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_usage.InputTokensDetails``

    Attributes:
        cached_tokens: Number of tokens retrieved from cache.

    """

    cached_tokens: int


class ResponseUsageOutputTokensDetails(TypedDict):
    """Nested detail for reasoning output tokens.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_usage.OutputTokensDetails``

    Attributes:
        reasoning_tokens: Number of reasoning tokens.

    """

    reasoning_tokens: int


class Response(TypedDict):
    """A model response object embedded inside SSE events.

    Reference — OpenAI SDK:
        ``openai.types.responses.response.Response``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``ResponseCompleted``
        (``{ id, usage?, end_turn? }``)

    The OpenAI SDK's ``Response`` model has ~35 fields.  Primal Codex
    only ever serialises a **minimal subset** — just enough for the
    Codex client to function.  Field presence varies by event:

    * ``response.created``   → ``{ id }``
    * ``response.completed`` → ``{ id, status, usage? }``
    * ``response.failed``    → ``{ id, status, error }``

    Attributes:
        id: Unique identifier for this response (e.g. ``resp_…``).
            Required for every event that carries a ``response`` key.
        status: Status of the response generation.
            One of ``completed``, ``failed``, ``in_progress``,
            ``cancelled``, ``queued``, or ``incomplete``.
            Only present in completion/failure events.
        error: Error object, present only when ``status == "failed"``.
        usage: Token usage, present only in ``response.completed``.
            The Codex Rust client accepts ``None`` / absent usage.
        end_turn: Whether the model affirmatively ended its turn.
            Primal Codex does **not** currently emit this field.
            The Codex Rust client gracefully handles ``None``.

    """

    id: str
    status: NotRequired[str]
    error: NotRequired[ResponseError]
    usage: NotRequired[ResponseUsage]
    end_turn: NotRequired[bool]


class ResponseOutputRefusal(TypedDict):
    """A refusal content part inside a message item.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_output_refusal.ResponseOutputRefusal``

    Attributes:
        type: Discriminator.  Always ``"output_refusal"``.
        refusal: The refusal message.

    """

    type: Literal["output_refusal"]
    refusal: str


class ResponseOutputText(TypedDict):
    """A text content part inside a message item.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_output_text.ResponseOutputText``

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ContentItem::OutputText``

    Attributes:
        type: Discriminator.  Always ``"output_text"``.
        text: The text content.
        annotations: Annotations (file/URL citations).  Not yet
            emitted by Primal Codex.

    """

    type: Literal["output_text"]
    text: str
    annotations: NotRequired[list[Any]]


ResponseOutputMessageContent: TypeAlias = ResponseOutputText | ResponseOutputRefusal
"""Content part inside a message output item.

Reference — OpenAI SDK:
    ``openai.types.responses.response_output_message.Content``
    (``ResponseOutputText | ResponseOutputRefusal``)

.. note::
   Primal Codex currently only emits ``ResponseOutputText``.
   ``ResponseOutputRefusal`` is defined here for spec completeness.
"""


class ResponseOutputMessage(TypedDict):
    """An ``assistant`` message inside a ``response.output_item.*`` event.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_output_message.ResponseOutputMessage``

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::Message``
        (``{ role, content, phase? }`` — the local ``id`` is
        ``#[serde(skip_serializing)]`` so it is **not** sent on the wire)

    Attributes:
        id: Item identifier (e.g. ``msg_…``).  The Codex Rust struct
            annotates ``id`` with ``#[serde(skip_serializing)]``,
            meaning it is **read** from the ``item.id`` field in the
            JSON but **not re-serialised** by Rust.  Primal Codex
            includes it unconditionally so the client can consume it.
        type: Discriminator.  Always ``"message"``.
        role: Message role.  Always ``"assistant"`` for output items.
        content: List of content parts (text, potentially
            images/refusals).
        status: Status of the message.  Not yet emitted by
            Primal Codex.  The OpenAI SDK requires this; the Codex
            Rust client treats it as optional.
        phase: Labels an assistant message as commentary or final
            answer.  Not yet emitted by Primal Codex.  The Codex
            Rust client accepts ``None``.

    """

    id: str
    type: Literal["message"]
    role: Literal["assistant"]
    content: list[ResponseOutputMessageContent]
    status: NotRequired[Literal["in_progress", "completed", "incomplete"]]
    phase: NotRequired[Literal["commentary", "final_answer"]]


class ResponseReasoningItemSummary(TypedDict):
    """A single summary text part inside a reasoning item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ReasoningItemReasoningSummary::SummaryText``

    Attributes:
        type: Discriminator.  Always ``"summary_text"``.
        text: The summary text.

    """

    type: Literal["summary_text"]
    text: str


class ResponseReasoningItemContent(TypedDict):
    """A single content part inside a reasoning item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ReasoningItemContent``

    Attributes:
        type: Discriminator.  One of ``"reasoning_text"`` or
            ``"text"``.
        text: The content text.

    """

    type: Literal["reasoning_text", "text"]
    text: str


class ResponseReasoningItem(TypedDict):
    """A reasoning item produced by the model.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_reasoning_item.ResponseReasoningItem``

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::Reasoning``
        (``{ summary, content?, encrypted_content? }`` — the
        local ``id`` is ``#[serde(skip_serializing)]``)

    Attributes:
        id: Item identifier (e.g. ``rs_…``).
        type: Discriminator.  Always ``"reasoning"``.
        summary: List of reasoning summary text parts.
        content: Full reasoning content parts.  Not yet emitted
            by Primal Codex.
        encrypted_content: Encrypted content.  Not yet emitted
            by Primal Codex.

    """

    id: str
    type: Literal["reasoning"]
    summary: list[ResponseReasoningItemSummary]
    content: NotRequired[list[ResponseReasoningItemContent]]
    encrypted_content: NotRequired[str]


class WebSearchAction(TypedDict):
    """Action payload inside a ``WebSearchCall`` item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``WebSearchAction``

    Attributes:
        type: Discriminator.
            ``"search"`` / ``"open_page"`` / ``"find_in_page"``.
        query: Search query (when type is ``"search"``).
        url: URL to open or search in (when type is
            ``"open_page"`` or ``"find_in_page"``).
        pattern: Pattern to find (when type is
            ``"find_in_page"``).

    """

    type: str
    query: NotRequired[str]
    url: NotRequired[str]
    pattern: NotRequired[str]


class ResponseWebSearchCall(TypedDict):
    """A web search call item emitted by the Responses API.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::WebSearchCall``

    Attributes:
        id: Item identifier (e.g. ``ws_…``).
        type: Discriminator.  Always ``"web_search_call"``.
        status: Status of the web search call.
        action: The search action (query, open page, etc.).

    """

    id: str
    type: Literal["web_search_call"]
    status: str
    action: NotRequired[WebSearchAction]


class ResponseFunctionToolCall(TypedDict):
    """A function tool call item.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_function_tool_call.ResponseFunctionToolCall``

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::FunctionCall``
        (``{ name, namespace?, arguments, call_id }``)

    Attributes:
        id: Item identifier (e.g. ``fc_…``).
        type: Discriminator.  Always ``"function_call"``.
        name: Name of the function to call.
        call_id: Identifier for this specific call instance.
        arguments: JSON string of arguments.
        namespace: Optional namespace for the function.

    """

    id: str
    type: Literal["function_call"]
    name: str
    call_id: str
    arguments: str
    namespace: NotRequired[str]


class FunctionCallOutputContentItem(TypedDict):
    """A structured content item inside a function call output.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``FunctionCallOutputContentItem``

    Attributes:
        type: Discriminator.  ``"input_text"`` or ``"input_image"``.
        text: Text content (when type is ``"input_text"``).
        image_url: Image URL (when type is ``"input_image"``).
        detail: Image detail level (when type is
            ``"input_image"``).

    """

    type: Literal["input_text", "input_image"]
    text: NotRequired[str]
    image_url: NotRequired[str]
    detail: NotRequired[Literal["auto", "low", "high", "original"]]


class ResponseFunctionToolCallOutputItem(TypedDict):
    """Output of a function tool call.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_function_tool_call_output_item.ResponseFunctionToolCallOutputItem``

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::FunctionCallOutput``
        (``{ call_id, output }``)

    Attributes:
        type: Discriminator.  Always ``"function_call_output"``.
        call_id: Matches the ``call_id`` of the corresponding
            ``ResponseFunctionToolCall``.
        output: Output content — either a plain string or a list
            of structured content items.

    """

    type: Literal["function_call_output"]
    call_id: str
    output: str | list[FunctionCallOutputContentItem]


class ResponseCustomToolCall(TypedDict):
    """A custom tool call item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::CustomToolCall``
        (``{ call_id, name, input }``)

    Attributes:
        id: Item identifier.
        type: Discriminator.  Always ``"custom_tool_call"``.
        call_id: Identifier for this specific call instance.
        name: Name of the custom tool.
        input: Raw input string.
        status: Status of the tool call.

    """

    id: str
    type: Literal["custom_tool_call"]
    call_id: str
    name: str
    input: str
    status: NotRequired[str]


class ResponseCustomToolCallOutputItem(TypedDict):
    """Output of a custom tool call.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::CustomToolCallOutput``
        (``{ call_id, name?, output }``)

    Attributes:
        type: Discriminator.  Always ``"custom_tool_call_output"``.
        call_id: Matches the ``call_id`` of the corresponding
            ``ResponseCustomToolCall``.
        output: Output content.
        name: Optional tool name.

    """

    type: Literal["custom_tool_call_output"]
    call_id: str
    output: str | list[FunctionCallOutputContentItem]
    name: NotRequired[str]


class ResponseToolSearchCall(TypedDict):
    """A tool search call item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::ToolSearchCall``
        (``{ call_id?, status?, execution, arguments }``)

    Attributes:
        id: Item identifier.
        type: Discriminator.  Always ``"tool_search_call"``.
        call_id: Identifier for this specific call instance.
        execution: Execution mode (``"client"`` or ``"server"``).
        arguments: Search arguments as a JSON object.
        status: Status of the search call.

    """

    id: str
    type: Literal["tool_search_call"]
    call_id: str
    execution: str
    arguments: Any
    status: NotRequired[str]


class ResponseToolSearchOutputItem(TypedDict):
    """Output of a tool search call.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::ToolSearchOutput``
        (``{ call_id?, status, execution, tools }``)

    Attributes:
        type: Discriminator.  Always ``"tool_search_output"``.
        call_id: Matches the ``call_id`` of the corresponding
            ``ResponseToolSearchCall``.
        status: Status of the search output.
        execution: Execution mode.
        tools: List of tools found.

    """

    type: Literal["tool_search_output"]
    call_id: str
    status: str
    execution: str
    tools: list[Any]


class ResponseImageGenerationCall(TypedDict):
    """An image generation call item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::ImageGenerationCall``
        (``{ id, status, result, revised_prompt? }``)

    Attributes:
        id: Item identifier (e.g. ``ig_…``).
        type: Discriminator.  Always ``"image_generation_call"``.
        status: Status (e.g. ``"completed"``).
        result: The generated image encoded in base64.
        revised_prompt: The revised/upsampled prompt used.

    """

    id: str
    type: Literal["image_generation_call"]
    status: str
    result: str
    revised_prompt: NotRequired[str]


class LocalShellAction(TypedDict):
    """Action payload inside a ``LocalShellCall`` item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``LocalShellAction``

    Attributes:
        type: Discriminator.  Always ``"exec"``.
        command: The command to run as a list of arguments.
        timeout_ms: Optional timeout in milliseconds.
        working_directory: Optional working directory.
        env: Optional environment variables.
        user: Optional user to run as.

    """

    type: Literal["exec"]
    command: list[str]
    timeout_ms: NotRequired[int]
    working_directory: NotRequired[str]
    env: NotRequired[dict[str, str]]
    user: NotRequired[str]


class ResponseLocalShellCall(TypedDict):
    """A local shell tool call item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::LocalShellCall``
        (``{ call_id?, status, action }``)

    Attributes:
        id: Item identifier.
        type: Discriminator.  Always ``"local_shell_call"``.
        call_id: Identifier for this specific call instance.
        status: Status (``"in_progress"``, ``"completed"``,
            ``"incomplete"``).
        action: The shell action (command to execute).

    """

    id: str
    type: Literal["local_shell_call"]
    call_id: str
    status: Literal["in_progress", "completed", "incomplete"]
    action: LocalShellAction


class ResponseCompactionItem(TypedDict):
    """A compaction (summarised) item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::Compaction``
        (``{ encrypted_content }``)

    Attributes:
        type: Discriminator.  Always ``"compaction"``.
        encrypted_content: Encrypted summary content.

    """

    type: Literal["compaction"]
    encrypted_content: str


class ResponseContextCompactionItem(TypedDict):
    """A context compaction item.

    Reference — Codex Rust:
        ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem::ContextCompaction``
        (``{ encrypted_content? }``)

    Attributes:
        type: Discriminator.  Always ``"context_compaction"``.
        encrypted_content: Encrypted content.

    """

    type: Literal["context_compaction"]
    encrypted_content: NotRequired[str]


ResponseOutputItem: TypeAlias = (
    ResponseOutputMessage
    | ResponseReasoningItem
    | ResponseFunctionToolCall
    | ResponseFunctionToolCallOutputItem
    | ResponseWebSearchCall
    | ResponseImageGenerationCall
    | ResponseLocalShellCall
    | ResponseToolSearchCall
    | ResponseToolSearchOutputItem
    | ResponseCustomToolCall
    | ResponseCustomToolCallOutputItem
    | ResponseCompactionItem
    | ResponseContextCompactionItem
)
"""An output item in a ``response.output_item.*`` event.

Reference — OpenAI SDK:
    ``openai.types.responses.response_output_item.ResponseOutputItem``
    (25-variant union)

Reference — Codex Rust:
    ``external/codex/codex-rs/protocol/src/models`.rs``
        ``ResponseItem``
    (tagged enum with 14+ variants)

.. note::
   Primal Codex currently only emits ``ResponseOutputMessage``.
   All other variants are defined here for spec completeness and
   will be emitted as functionality expands.
"""


class ResponseCreatedEvent(TypedDict):
    """Emitted when a response is created.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_created_event.ResponseCreatedEvent``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``process_responses_event``:
        ``"response.created"`` → ``ResponseEvent::Created``
        (the client only checks that ``response`` is ``Some``)

    Attributes:
        type: The event type discriminator.  Always
            ``"response.created"``.
        response: The response that was created.  The Codex Rust
            client requires this field to exist, but only extracts
            ``response.id`` indirectly via ``response.completed``.
            A minimal ``{"id": …}`` suffices.

    """

    type: Literal["response.created"]
    response: Response


class ResponseOutputItemAddedEvent(TypedDict):
    """Emitted when a new output item is added.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_output_item_added_event.ResponseOutputItemAddedEvent``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``process_responses_event``:
        ``"response.output_item.added"`` →
        ``ResponseEvent::OutputItemAdded(ResponseItem)``
        (deserialises ``item`` as ``ResponseItem``)

    Attributes:
        type: The event type discriminator.  Always
            ``"response.output_item.added"``.
        item: The output item that was added.

    """

    type: Literal["response.output_item.added"]
    item: ResponseOutputItem


class ResponseTextDeltaEvent(TypedDict):
    """Emitted when there is an additional text delta.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_text_delta_event.ResponseTextDeltaEvent``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``process_responses_event``:
        ``"response.output_text.delta"`` → ``ResponseEvent::OutputTextDelta(String)``
        (only the ``delta`` string is consumed)

    Attributes:
        type: The event type discriminator.  Always
            ``"response.output_text.delta"``.
        delta: The text delta that was added.

    """

    type: Literal["response.output_text.delta"]
    delta: str


class ResponseTextDoneEvent(TypedDict):
    """Emitted when text content is finalized.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_text_done_event.ResponseTextDoneEvent``

    The Codex Rust client does **not** handle ``response.output_text.done``
    explicitly — it relies on ``response.output_item.done`` carrying the
    final ``content`` array.  This event is emitted for OpenAI SDK
    compatibility but may be a no-op on the consumer side.

    Attributes:
        type: The event type discriminator.  Always
            ``"response.output_text.done"``.
        text: The final text content.

    """

    type: Literal["response.output_text.done"]
    text: str


class ResponseOutputItemDoneEvent(TypedDict):
    """Emitted when an output item is marked done.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_output_item_done_event.ResponseOutputItemDoneEvent``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``process_responses_event``:
        ``"response.output_item.done"`` →
        ``ResponseEvent::OutputItemDone(ResponseItem)``
        (deserialises ``item`` as ``ResponseItem``)

    Attributes:
        type: The event type discriminator.  Always
            ``"response.output_item.done"``.
        item: The output item that was marked done.

    """

    type: Literal["response.output_item.done"]
    item: ResponseOutputItem


class ResponseCompletedEvent(TypedDict):
    """Emitted when the model response is complete.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_completed_event.ResponseCompletedEvent``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``process_responses_event``:
        ``"response.completed"`` → ``ResponseEvent::Completed``
        (deserialises ``response`` as ``ResponseCompleted { id, usage?, end_turn? }``)

    Attributes:
        type: The event type discriminator.  Always
            ``"response.completed"``.
        response: The completed response, minimally
            ``{"id": …, "status": "completed"}``.
            ``usage`` is included when upstream usage data is available.

    """

    type: Literal["response.completed"]
    response: Response


class ResponseFailedEvent(TypedDict):
    """Emitted when a response fails.

    Reference — OpenAI SDK:
        ``openai.types.responses.response_failed_event.ResponseFailedEvent``

    Reference — Codex Rust:
        ``external/codex/codex-rs/codex-api/src/sse/responses`.rs``
        ``process_responses_event``:
        ``"response.failed"`` → extracts ``response.error.{code, message}``
        and returns an ``ApiError`` variant.

    Attributes:
        type: The event type discriminator.  Always
            ``"response.failed"``.
        response: The failed response, must include
            ``{"id": …, "status": "failed", "error": …}``.

    """

    type: Literal["response.failed"]
    response: Response


ResponseStreamEvent: TypeAlias = (
    ResponseCreatedEvent
    | ResponseOutputItemAddedEvent
    | ResponseTextDeltaEvent
    | ResponseTextDoneEvent
    | ResponseOutputItemDoneEvent
    | ResponseCompletedEvent
    | ResponseFailedEvent
)
"""Union of all SSE event payloads that Primal Codex can emit.

Reference — OpenAI SDK:
    ``openai.types.responses.response_stream_event.ResponseStreamEvent``

Reference — Codex Rust:
    ``external/codex/codex-rs/codex-api/src/common`.rs``
        ``ResponseEvent``
"""


class ResponsesApiRequest(BaseModel):
    """Wire-format mirror of the Codex client's ``ResponsesApiRequest``.

    This is **not** the standard OpenAI Responses API.

    The Codex client
    (``external/codex/codex-rs/codex-api/src/common.rs``)
    serializes its own ``ResponsesApiRequest`` struct as JSON and sends
    it to the Primal Codex ``POST /responses`` endpoint.  This Pydantic
    model deserializes that same JSON.

    The OpenAI SDK's ``ResponseCreateParamsBase``
    (``openai.types.responses.response_create_params.ResponseCreateParamsBase``)
    is the *spec* for OpenAI's
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
    tool_choice: Literal["auto", "none", "required"] = "auto"
    parallel_tool_calls: bool = True
    reasoning: Reasoning | None = None
    store: bool = False
    stream: bool = True
    include: list[str] = []
    service_tier: Literal["auto", "default", "flex", "scale", "priority"] | None = None
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


def _map_function_tool(parsed: FunctionTool) -> ChatCompletionFunctionToolParam:
    """Responses API ``FunctionTool`` → Chat Completions nested ``function:{...}``."""
    return ChatCompletionFunctionToolParam(
        type="function",
        function=FunctionDefinition(
            name=parsed.name,
            description=parsed.description or "",
            parameters=parsed.parameters or {},
            strict=parsed.strict,
        ),
    )


def _map_custom_format(
    fmt: Text | Grammar,
) -> CustomFormatText | CustomFormatGrammar:
    """Map a Responses API ``format`` to Chat Completions custom format.

    ``type: "text"`` passes through directly.
    ``type: "grammar"`` nests ``definition`` and ``syntax`` under ``"grammar"``:

    - Input:  ``{"type": "grammar", "definition": …, "syntax": …}``
    - Output: ``{"type": "grammar", "grammar": {"definition": …, "syntax": …}}``
    """
    if fmt.type == "text":
        return CustomFormatText(type="text")
    return CustomFormatGrammar(
        type="grammar",
        grammar={
            "definition": fmt.definition,
            "syntax": fmt.syntax,
        },
    )


def _map_custom_tool(parsed: CustomTool) -> ChatCompletionCustomToolParam:
    """Responses API ``CustomTool`` → Chat Completions nested ``custom:{...}``."""
    tool_custom: Custom = {
        "name": parsed.name,
    }
    if parsed.description is not None:
        tool_custom["description"] = parsed.description
    if parsed.format is not None:
        tool_custom["format"] = _map_custom_format(parsed.format)
    return ChatCompletionCustomToolParam(
        type="custom",
        custom=tool_custom,
    )


def _map_tools(raw_tools: list[Any]) -> list[ChatCompletionToolUnionParam]:
    """Map Responses API tools to Chat Completions format.

    References:
    - Responses API format: external/codex/codex-rs/tools/src/tool_spec.rs
    - Chat Completions format: openai.types.chat.chat_completion_tool_union_param

    """
    result: list[ChatCompletionToolUnionParam] = []
    for raw in raw_tools:
        if not isinstance(raw, dict):
            logger.warning(
                "Non-dict tool entry in responses API request: %s — dropping.",
                raw,
            )
            continue
        tool_type = raw.get("type")
        if tool_type == "function":
            try:
                parsed = FunctionTool.model_validate(raw)
            except ValidationError as exc:
                logger.warning(
                    "Failed to parse function tool: %s — raw data: %s",
                    exc,
                    raw,
                )
                continue
            result.append(_map_function_tool(parsed))
        elif tool_type == "custom":
            try:
                parsed = CustomTool.model_validate(raw)
            except ValidationError as exc:
                logger.warning(
                    "Failed to parse custom tool: %s — raw data: %s",
                    exc,
                    raw,
                )
                continue
            result.append(_map_custom_tool(parsed))
        else:
            logger.warning(
                "Unsupported tool type '%s' in responses API request — "
                "dropping. Supported types: function, custom.",
                tool_type,
            )
            continue
    return result


def _generate_response_id() -> str:
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


def _format_sse(data: ResponseStreamEvent) -> str:
    """Format a TypedDict as an SSE ``event:`` / ``data:`` pair.

    The event name is read from the ``type`` field of the TypedDict,
    and the entire dict is serialised as the ``data`` line.
    """
    encoded = json.dumps(data, separators=(",", ":"))
    return f"event: {data['type']}\ndata: {encoded}\n\n"


def _usage_from_chunk(
    chunk: ChatCompletionChunk,
) -> ResponseUsage | None:
    """Extract usage info from a chunk if present.

    Maps the Chat Completions usage fields to the Responses API format
    that the Codex Rust client expects (
    ``external/codex/codex-rs/codex-api/src/sse/responses.rs``,
    ``ResponseCompletedUsage``).

    Nested details:
    * ``prompt_tokens_details.cached_tokens`` →
      ``input_tokens_details.cached_tokens``
    * ``completion_tokens_details.reasoning_tokens`` →
      ``output_tokens_details.reasoning_tokens``
    """
    if not chunk.usage:
        return None
    u = chunk.usage
    usage: ResponseUsage = {
        "input_tokens": u.prompt_tokens,
        "output_tokens": u.completion_tokens,
        "total_tokens": u.total_tokens,
    }
    if u.prompt_tokens_details and u.prompt_tokens_details.cached_tokens:
        usage["input_tokens_details"] = ResponseUsageInputTokensDetails(
            cached_tokens=u.prompt_tokens_details.cached_tokens
        )
    if u.completion_tokens_details and u.completion_tokens_details.reasoning_tokens:
        usage["output_tokens_details"] = ResponseUsageOutputTokensDetails(
            reasoning_tokens=u.completion_tokens_details.reasoning_tokens
        )
    return usage


def _build_output_message(
    item_id: str,
    text: str,
) -> ResponseOutputMessage:
    """Build a ``ResponseOutputMessage`` with a single text content part."""
    return ResponseOutputMessage(
        id=item_id,
        type="message",
        role="assistant",
        content=[ResponseOutputText(type="output_text", text=text)],
    )


def _build_empty_output_message(item_id: str) -> ResponseOutputMessage:
    """Build a ``ResponseOutputMessage`` with an empty content list."""
    return ResponseOutputMessage(
        id=item_id,
        type="message",
        role="assistant",
        content=[],
    )


async def _emit_content_events(
    stream: AsyncStream[ChatCompletionChunk],
    item_id: str,
    usage_out: list[ResponseUsage | None],
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
                    ResponseOutputItemAddedEvent(
                        type="response.output_item.added",
                        item=_build_empty_output_message(item_id),
                    )
                )
            final_text += content
            yield _format_sse(
                ResponseTextDeltaEvent(
                    type="response.output_text.delta",
                    delta=content,
                )
            )
        elif choice.finish_reason:
            if not item_started:
                item_started = True
                yield _format_sse(
                    ResponseOutputItemAddedEvent(
                        type="response.output_item.added",
                        item=_build_empty_output_message(item_id),
                    )
                )
            yield _format_sse(
                ResponseTextDoneEvent(
                    type="response.output_text.done",
                    text=final_text,
                )
            )
            yield _format_sse(
                ResponseOutputItemDoneEvent(
                    type="response.output_item.done",
                    item=_build_output_message(item_id, final_text),
                )
            )

    # Stream ended without any content chunks.
    # Emit empty item events so codex can produce item.completed even when
    # the upstream returned no content (e.g. oversized instructions/tools).
    if not item_started:
        yield _format_sse(
            ResponseOutputItemAddedEvent(
                type="response.output_item.added",
                item=_build_empty_output_message(item_id),
            )
        )
        yield _format_sse(
            ResponseTextDoneEvent(
                type="response.output_text.done",
                text="",
            )
        )
        yield _format_sse(
            ResponseOutputItemDoneEvent(
                type="response.output_item.done",
                item=_build_output_message(item_id, ""),
            )
        )


async def relay_stream(
    body: ResponsesApiRequest,
    model_id: str,
    base_url: str,
    api_key: str | None,
) -> AsyncIterator[str]:
    """Forward the mapped Chat Completions request using the OpenAI SDK."""
    response_id = _generate_response_id()
    item_id = _generate_message_item_id()
    messages = _map_messages(body)
    stream_options: ChatCompletionStreamOptionsParam = ChatCompletionStreamOptionsParam(
        include_usage=True
    )
    reasoning_effort: (
        Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None | Omit
    ) = Omit()
    if body.reasoning:
        reasoning_effort = body.reasoning.effort
    verbosity: Literal["low", "medium", "high"] | None | Omit = Omit()
    if body.text:
        verbosity = body.text.verbosity
    tools: list[ChatCompletionToolUnionParam] | Omit = _map_tools(body.tools) or Omit()
    response_format: ResponseFormatJSONSchema | Omit = Omit()
    if body.text and isinstance(body.text.format, ResponseFormatTextJSONSchemaConfig):
        fmt = body.text.format
        response_format = ResponseFormatJSONSchema(
            type="json_schema",
            json_schema={
                "name": fmt.name,
                "schema": fmt.schema_,
                "strict": fmt.strict,
            },
        )

    yield _format_sse(
        ResponseCreatedEvent(
            type="response.created",
            response=Response(id=response_id),
        )
    )

    async with AsyncOpenAI(api_key=api_key, base_url=base_url) as client:
        try:
            stream = await client.chat.completions.create(
                model=model_id,
                messages=messages,
                stream=True,
                stream_options=stream_options,
                tools=tools,
                tool_choice=body.tool_choice,
                parallel_tool_calls=body.parallel_tool_calls,
                reasoning_effort=reasoning_effort,
                service_tier=body.service_tier,
                verbosity=verbosity,
                response_format=response_format,
                prompt_cache_key=body.prompt_cache_key
                if body.prompt_cache_key is not None
                else Omit(),
            )
        except openai.APIError as e:
            yield _format_sse(
                ResponseFailedEvent(
                    type="response.failed",
                    response=Response(
                        id=response_id,
                        status="failed",
                        error=ResponseError(code="upstream_error", message=str(e)),
                    ),
                )
            )
            return

        usage_out: list[ResponseUsage | None] = [None]
        events = _emit_content_events(stream, item_id, usage_out)
        async for event in events:
            yield event
        final_usage = usage_out[0]

    response: Response = Response(id=response_id, status="completed")
    if final_usage:
        response["usage"] = final_usage
    yield _format_sse(
        ResponseCompletedEvent(
            type="response.completed",
            response=response,
        )
    )
