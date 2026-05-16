"""Model listing for the ``GET /models`` API endpoint.

Provides the response schema (``ModelInfo``, ``ModelsResponse``) and the
``list_models()`` function that reads from ``PrimalCodexConfig`` and fills
defaults.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel, Field

from primal_codex.config import (
    PrimalCodexConfig,
    ReasoningEffortPreset,
    TruncationPolicyConfig,
)


class ModelInfo(BaseModel):
    """Metadata for a single model exposed by the API.

    Mirrors the codex-compat ``ModelInfo`` schema.
    """

    slug: str = Field(description="Unique model identifier.")
    display_name: str = Field(description="Human-readable model name.")
    supported_reasoning_levels: list[ReasoningEffortPreset] = Field(
        default_factory=list,
        description="Reasoning effort levels this model supports.",
    )
    visibility: str = Field(
        default="list",
        description=(
            "Visibility in model listings.  One of ``list``, ``hide``, ``none``."
        ),
    )
    supported_in_api: bool = Field(
        default=True,
        description="Whether the model is accessible through the API.",
    )
    priority: int = Field(
        default=1,
        description="Sort priority; higher values rank earlier.",
    )
    base_instructions: str = Field(
        default="",
        description="System prompt injected at the start of each conversation.",
    )
    supports_reasoning_summaries: bool = Field(
        default=True,
        description="Whether reasoning summaries are available.",
    )
    support_verbosity: bool = Field(
        default=False,
        description="Whether verbosity control (terse / verbose) is supported.",
    )
    truncation_policy: TruncationPolicyConfig = Field(
        default_factory=TruncationPolicyConfig,
        description="Token or byte truncation policy.",
    )
    supports_parallel_tool_calls: bool = Field(
        default=True,
        description="Whether the model supports parallel tool calls.",
    )
    experimental_supported_tools: list[Any] = Field(
        default_factory=list,
        description="Experimental tool names the model supports.",
    )


class ModelsResponse(BaseModel):
    """Top-level response for ``GET /models``."""

    models: list[ModelInfo] = Field(description="Available models.")


def list_models(config: PrimalCodexConfig) -> ModelsResponse:
    """Build the model list from ``[providers]`` configuration.

    Every ``[providers.<pid>.models.<mid>`` entry is exposed as a model
    with slug ``<pid>/<mid>``.  Metadata fields on the model config
    (``display_name``, ``priority``, etc.) are forwarded directly;
    missing optional fields fall back to their defaults.

    ``base_instructions`` is already resolved at config-load time.

    Returns:
        A :class:`ModelsResponse` containing all registered models sorted
        by ``priority``, highest first.

    """
    infos: list[ModelInfo] = []

    for pid, provider in config.providers.items():
        for mid, mc in provider.models.items():
            slug = f"{pid}/{mid}"
            info = ModelInfo(
                slug=slug,
                display_name=mc.display_name,
                supported_reasoning_levels=mc.supported_reasoning_levels,
                visibility=mc.visibility,
                supported_in_api=mc.supported_in_api,
                priority=mc.priority,
                base_instructions=cast("str", mc.base_instructions),
                supports_reasoning_summaries=mc.supports_reasoning_summaries,
                support_verbosity=mc.support_verbosity,
                truncation_policy=mc.truncation_policy,
                supports_parallel_tool_calls=mc.supports_parallel_tool_calls,
                experimental_supported_tools=mc.experimental_supported_tools,
            )
            infos.append(info)

    infos.sort(key=lambda m: m.priority)
    return ModelsResponse(models=infos)
