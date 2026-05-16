"""Codex SOT types for the ``/models`` endpoint.

Every type, field, enum variant, optionality rule, default value, and
serialization name in this module is derived from codex-rs:

    codex-rs/protocol/src/openai_models.rs
    codex-rs/protocol/src/config_types.rs

Do NOT add, remove, or rename anything here without also updating the
upstream source.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReasoningEffort(StrEnum):
    """codex ReasoningEffort — serialised lowercase."""

    none = "none"
    minimal = "minimal"
    low = "low"
    medium = "medium"
    high = "high"
    xhigh = "xhigh"


class InputModality(StrEnum):
    """codex InputModality — serialised lowercase."""

    text = "text"
    image = "image"


class ModelVisibility(StrEnum):
    """codex ModelVisibility — serialised lowercase."""

    list = "list"
    hide = "hide"
    none = "none"


class ConfigShellToolType(StrEnum):
    """codex ConfigShellToolType — serialised snake_case."""

    default = "default"
    local = "local"
    unified_exec = "unified_exec"
    disabled = "disabled"
    shell_command = "shell_command"


class ApplyPatchToolType(StrEnum):
    """codex ApplyPatchToolType — serialised snake_case."""

    freeform = "freeform"
    function = "function"


class WebSearchToolType(StrEnum):
    """codex WebSearchToolType — serialised snake_case."""

    text = "text"
    text_and_image = "text_and_image"


class TruncationMode(StrEnum):
    """codex TruncationMode — serialised snake_case."""

    bytes = "bytes"
    tokens = "tokens"


class ReasoningSummary(StrEnum):
    """codex ReasoningSummary — serialised lowercase."""

    auto = "auto"
    concise = "concise"
    detailed = "detailed"
    none = "none"


class Verbosity(StrEnum):
    """codex Verbosity — serialised lowercase."""

    low = "low"
    medium = "medium"
    high = "high"


# ── Structs ────────────────────────────────────────────────────────────────


class ReasoningEffortPreset(BaseModel):
    """codex ReasoningEffortPreset."""

    effort: ReasoningEffort
    description: str = ""


class ModelUpgrade(BaseModel):
    """codex ModelUpgrade."""

    id: str
    reasoning_effort_mapping: dict[ReasoningEffort, ReasoningEffort] | None = None
    migration_config_key: str
    model_link: str | None = None
    upgrade_copy: str | None = None
    migration_markdown: str | None = None


class ModelAvailabilityNux(BaseModel):
    """codex ModelAvailabilityNux."""

    message: str


class ModelServiceTier(BaseModel):
    """codex ModelServiceTier."""

    id: str
    name: str
    description: str


class TruncationPolicyConfig(BaseModel):
    """codex TruncationPolicyConfig."""

    mode: TruncationMode
    limit: int


class ModelInstructionsVariables(BaseModel):
    """codex ModelInstructionsVariables."""

    personality_default: str | None = None
    personality_friendly: str | None = None
    personality_pragmatic: str | None = None


class ModelMessages(BaseModel):
    """codex ModelMessages."""

    instructions_template: str | None = None
    instructions_variables: ModelInstructionsVariables | None = None


class ModelInfoUpgrade(BaseModel):
    """codex ModelInfoUpgrade."""

    model: str
    migration_markdown: str


class ModelInfo(BaseModel):
    """codex ModelInfo — every field mirrors the Rust struct one-to-one.

    Wire format (JSON) uses snake_case for field names and lowercase for
    enum variant names, exactly matching codex-rs serialisation.
    """

    slug: str = ""
    display_name: str
    description: str | None = None
    default_reasoning_level: ReasoningEffort | None = None
    supported_reasoning_levels: list[ReasoningEffortPreset] = Field(
        default_factory=list
    )
    shell_type: ConfigShellToolType = ConfigShellToolType.shell_command
    visibility: ModelVisibility = ModelVisibility.list
    supported_in_api: bool = True
    priority: int = 0
    additional_speed_tiers: list[str] = Field(default_factory=list)
    service_tiers: list[ModelServiceTier] = Field(default_factory=list)
    availability_nux: ModelAvailabilityNux | None = None
    upgrade: ModelInfoUpgrade | None = None
    base_instructions: str | None = None
    model_messages: ModelMessages | None = None
    supports_reasoning_summaries: bool = False
    default_reasoning_summary: ReasoningSummary = ReasoningSummary.auto
    support_verbosity: bool = False
    default_verbosity: Verbosity | None = None
    apply_patch_tool_type: ApplyPatchToolType | None = None
    web_search_tool_type: WebSearchToolType = WebSearchToolType.text
    truncation_policy: TruncationPolicyConfig = Field(
        default_factory=lambda: TruncationPolicyConfig(
            mode=TruncationMode.bytes, limit=10_000
        )
    )
    supports_parallel_tool_calls: bool = False
    supports_image_detail_original: bool = False
    context_window: int | None = None
    max_context_window: int | None = None
    auto_compact_token_limit: int | None = None
    effective_context_window_percent: int = 95
    experimental_supported_tools: list[str] = Field(default_factory=list)
    input_modalities: list[InputModality] = Field(
        default_factory=lambda: [InputModality.text, InputModality.image]
    )
    supports_search_tool: bool = False


class ModelsResponse(BaseModel):
    """codex ModelsResponse — response wrapper for ``GET /models``."""

    models: list[ModelInfo]
