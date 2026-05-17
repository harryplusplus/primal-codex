"""Primal Codex model layer.

Two roles live in this module, separated by convention:

1. **Wire format mirror** (``ModelInfo`` + supporting types)
   Every type, field, enum variant, optionality rule, default value, and
   serialization name is derived from codex-rs:

       codex-rs/protocol/src/openai_models.rs
       codex-rs/protocol/src/config_types.rs

   Do NOT add, remove, or rename anything in ``ModelInfo`` without also
   updating the upstream source.

2. **User input schema** (``ModelConfig``)
   All-optional model configuration that users write in their TOML file.
   The server enriches it into a complete ``ModelInfo`` at load time.
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

    slug: str
    display_name: str
    description: str | None
    default_reasoning_level: ReasoningEffort | None = None
    supported_reasoning_levels: list[ReasoningEffortPreset]
    shell_type: ConfigShellToolType
    visibility: ModelVisibility
    supported_in_api: bool
    priority: int
    additional_speed_tiers: list[str] = Field(default_factory=list)
    service_tiers: list[ModelServiceTier] = Field(default_factory=list)
    availability_nux: ModelAvailabilityNux | None
    upgrade: ModelInfoUpgrade | None
    base_instructions: str
    model_messages: ModelMessages | None = None
    supports_reasoning_summaries: bool
    default_reasoning_summary: ReasoningSummary = ReasoningSummary.auto
    support_verbosity: bool
    default_verbosity: Verbosity | None
    apply_patch_tool_type: ApplyPatchToolType | None
    web_search_tool_type: WebSearchToolType = WebSearchToolType.text
    truncation_policy: TruncationPolicyConfig
    supports_parallel_tool_calls: bool
    supports_image_detail_original: bool = False
    context_window: int | None = None
    max_context_window: int | None = None
    auto_compact_token_limit: int | None = None
    effective_context_window_percent: int = 95
    experimental_supported_tools: list[str]
    input_modalities: list[InputModality] = Field(
        default_factory=lambda: [InputModality.text, InputModality.image]
    )
    used_fallback_model_metadata: bool = False
    supports_search_tool: bool = False


class ModelsResponse(BaseModel):
    """codex ModelsResponse — response wrapper for ``GET /models``."""

    models: list[ModelInfo]


class ModelConfig(BaseModel):
    """User-supplied model configuration from TOML.

    All fields are optional — the server provides sensible defaults when a
    field is omitted (set to ``None``).
    """

    display_name: str | None = None
    description: str | None = None
    default_reasoning_level: ReasoningEffort | None = None
    supported_reasoning_levels: list[ReasoningEffortPreset] | None = None
    shell_type: ConfigShellToolType | None = None
    visibility: ModelVisibility | None = None
    supported_in_api: bool | None = None
    priority: int | None = None
    additional_speed_tiers: list[str] | None = None
    service_tiers: list[ModelServiceTier] | None = None
    availability_nux: ModelAvailabilityNux | None = None
    upgrade: ModelInfoUpgrade | None = None
    base_instructions: str | None = None
    model_messages: ModelMessages | None = None
    supports_reasoning_summaries: bool | None = None
    default_reasoning_summary: ReasoningSummary | None = None
    support_verbosity: bool | None = None
    default_verbosity: Verbosity | None = None
    apply_patch_tool_type: ApplyPatchToolType | None = None
    web_search_tool_type: WebSearchToolType | None = None
    truncation_policy: TruncationPolicyConfig | None = None
    supports_parallel_tool_calls: bool | None = None
    supports_image_detail_original: bool | None = None
    context_window: int | None = None
    max_context_window: int | None = None
    auto_compact_token_limit: int | None = None
    effective_context_window_percent: int | None = None
    experimental_supported_tools: list[str] | None = None
    input_modalities: list[InputModality] | None = None
    supports_search_tool: bool | None = None


def enrich_model(
    model_id: str,
    provider_id: str,
    cfg: ModelConfig,
    default_base_instructions: str = "",
) -> ModelInfo:
    """Build a complete ``ModelInfo`` from a user-supplied ``ModelConfig``.

    Args:
        model_id: Model key under ``[providers.<provider_id>.models]`` in TOML.
        provider_id: Provider key under ``[providers]`` in TOML.
        cfg: User-supplied model configuration (all fields optional).
        default_base_instructions: Built-in prompt used when
            ``cfg.base_instructions`` is None.

    Returns:
        A fully-populated ``ModelInfo`` ready for wire serialisation.

    """
    slug = f"{provider_id}/{model_id}"

    return ModelInfo(
        slug=slug,
        display_name=cfg.display_name or model_id,
        description=cfg.description,
        default_reasoning_level=cfg.default_reasoning_level,
        supported_reasoning_levels=cfg.supported_reasoning_levels or [],
        shell_type=cfg.shell_type or ConfigShellToolType.shell_command,
        visibility=cfg.visibility or ModelVisibility.list,
        supported_in_api=cfg.supported_in_api
        if cfg.supported_in_api is not None
        else True,
        priority=cfg.priority if cfg.priority is not None else 0,
        additional_speed_tiers=cfg.additional_speed_tiers or [],
        service_tiers=cfg.service_tiers or [],
        availability_nux=cfg.availability_nux,
        upgrade=cfg.upgrade,
        base_instructions=cfg.base_instructions
        if cfg.base_instructions is not None
        else default_base_instructions,
        model_messages=cfg.model_messages,
        supports_reasoning_summaries=cfg.supports_reasoning_summaries
        if cfg.supports_reasoning_summaries is not None
        else False,
        default_reasoning_summary=cfg.default_reasoning_summary
        or ReasoningSummary.auto,
        support_verbosity=cfg.support_verbosity
        if cfg.support_verbosity is not None
        else False,
        default_verbosity=cfg.default_verbosity,
        apply_patch_tool_type=cfg.apply_patch_tool_type,
        web_search_tool_type=cfg.web_search_tool_type or WebSearchToolType.text,
        truncation_policy=cfg.truncation_policy
        or TruncationPolicyConfig(mode=TruncationMode.bytes, limit=10_000),
        supports_parallel_tool_calls=cfg.supports_parallel_tool_calls
        if cfg.supports_parallel_tool_calls is not None
        else False,
        supports_image_detail_original=cfg.supports_image_detail_original
        if cfg.supports_image_detail_original is not None
        else False,
        context_window=cfg.context_window,
        max_context_window=cfg.max_context_window,
        auto_compact_token_limit=cfg.auto_compact_token_limit,
        effective_context_window_percent=cfg.effective_context_window_percent
        if cfg.effective_context_window_percent is not None
        else 95,
        experimental_supported_tools=cfg.experimental_supported_tools or [],
        input_modalities=cfg.input_modalities
        or [InputModality.text, InputModality.image],
        supports_search_tool=cfg.supports_search_tool
        if cfg.supports_search_tool is not None
        else False,
    )
