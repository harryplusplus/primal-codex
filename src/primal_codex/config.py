"""Primal Codex configuration loader.

Provides :class:`PrimalCodexConfig` (server host, port, etc.) by reading
``~/.primal-codex/config.toml`` (or ``$PRIMAL_CODEX_HOME/config.toml``).
Missing settings fall back to their field defaults, so the config file is
entirely optional.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import tomlkit
from pydantic import BaseModel

from primal_codex.paths import resolve_primal_codex_config_path


def _base_instructions() -> str:
    """Read and cache the contents of ``assets/prompt.md``."""
    path = Path(__file__).resolve().parents[2] / "assets" / "prompt.md"
    return path.read_text(encoding="utf-8")


DEFAULT_CONFIG = """\
# Primal Codex configuration.
#
# This file is entirely optional — any missing setting falls back to its
# built-in default value.

[server]
# Address the server binds to.
# (default: 127.0.0.1)
# host = "127.0.0.1"

# Port the server listens on.
# (default: 8010)
# port = 8010

# --- Providers & model configuration ---
#
# Provider keys are dynamic. Below is an example structure.
# Uncomment and adjust for your providers.

# [providers.crof]
# base_url = "https://crof.ai/v1"
# env_key = "CROF_API_KEY"

# [providers.crof.models."glm-5.1-precision"]
# display_name = "GLM 5.1 Precision"
# priority = 100
# truncation_policy = { mode = "tokens", limit = 10000 }
"""


class TruncationPolicyConfig(BaseModel):
    """Token truncation policy.

    Attributes:
        mode: Truncation unit, either ``bytes`` or ``tokens``.
        limit: Maximum number of the chosen unit before truncation kicks in.

    """

    mode: str = "tokens"
    limit: int = 10_000


class ReasoningEffortPreset(BaseModel):
    """A single reasoning-effort level with a human-readable description.

    Attributes:
        effort: Effort level identifier (e.g. ``low``, ``medium``, ``high``).
        description: Free-text description of what this effort level means.

    """

    effort: str
    description: str = ""


class ServerConfig(BaseModel):
    """Server binding configuration.

    Attributes:
        host: Bind address. Defaults to ``127.0.0.1``.
        port: Bind port. Defaults to ``8010``.

    """

    host: str = "127.0.0.1"
    port: int = 8010


class PrimalCodexConfig(BaseModel):
    """Top-level Primal Codex configuration, loaded from TOML.

    Use :func:`load_config` to read the TOML file and construct an instance.

    Attributes:
        server: Server binding configuration.
        providers: Provider-specific runtime settings keyed by provider name.
            Models discovered under each provider are merged into a unified
            list exposed via ``GET /models``.

    """

    server: ServerConfig = ServerConfig()
    providers: dict[str, ProviderConfig] = {}

    def model_post_init(self, __context: object, /) -> None:
        """Post-initialisation: fill per-model defaults.

        For each model under every provider, fills ``display_name`` with
        the model ID (the TOML key) and ``base_instructions`` with the
        contents of ``assets/prompt.md`` when not explicitly set.
        """
        prompt: str | None = None
        for provider in self.providers.values():
            for mid, mc in provider.models.items():
                if not mc.display_name:
                    mc.display_name = mid
                if mc.base_instructions is None:
                    if prompt is None:
                        prompt = _base_instructions()
                    mc.base_instructions = prompt


class ModelConfig(BaseModel):
    """Configuration and metadata for a single model within a provider.

    ``temperature`` and ``max_tokens`` are runtime settings forwarded to
    the upstream.  All other fields are metadata exposed via the
    ``GET /models`` endpoint (mirrors the codex-compat ``ModelInfo``
    schema).

    Attributes:
        display_name: Human-readable name. Defaults to the model ID (the
            TOML key under ``[providers.<pid>.models]``).
        supported_reasoning_levels: Reasoning effort levels this model
            supports.
        visibility: Visibility in model listings. One of ``list``,
            ``hide``, ``none``.
        supported_in_api: Whether the model is accessible through the API.
        priority: Sort priority; higher values rank earlier.
        base_instructions: System prompt for this model. ``None`` means
            fall back to ``assets/prompt.md``; an empty string explicitly
            disables the prompt.
        supports_reasoning_summaries: Whether reasoning summaries are
            available.
        support_verbosity: Whether verbosity control is supported.
        truncation_policy: Token or byte truncation policy.
        supports_parallel_tool_calls: Whether parallel tool calling is
            supported.
        experimental_supported_tools: Experimental tool identifiers.

    """

    display_name: str = ""
    supported_reasoning_levels: list[ReasoningEffortPreset] = []
    visibility: str = "list"
    supported_in_api: bool = True
    priority: int = 1
    base_instructions: str | None = None
    supports_reasoning_summaries: bool = True
    support_verbosity: bool = False
    truncation_policy: TruncationPolicyConfig = TruncationPolicyConfig()
    supports_parallel_tool_calls: bool = True
    experimental_supported_tools: list[Any] = []


class ProviderConfig(BaseModel):
    """Configuration for a single provider.

    Provider keys are dynamic (e.g. ``crof``, ``opencode-go``).

    Attributes:
        base_url: API base URL. ``None`` falls back to the provider's default
            endpoint.
        env_key: Environment variable name that holds the API key
            (e.g. ``"CROF_API_KEY"``). Resolved via
            :meth:`resolve_api_key`.
        models: Per-provider model overrides keyed by model ID.

    """

    base_url: str | None = None
    env_key: str | None = None
    models: dict[str, ModelConfig] = {}

    def resolve_api_key(self) -> str | None:
        """Return the API key from the environment variable, if configured.

        Returns:
            The value of the environment variable named by :attr:`env_key`,
            or ``None`` when ``env_key`` is unset or the variable is not
            defined.

        """
        if self.env_key is None:
            return None
        return os.environ.get(self.env_key)


def load_config() -> PrimalCodexConfig:
    """Load configuration from the Primal Codex TOML file.

    Reads the file at
    :func:`~primal_codex.paths.resolve_primal_codex_config_path`.
    If the file is missing, returns a config with all defaults.

    Returns:
        A :class:`PrimalCodexConfig` instance.

    """
    path = resolve_primal_codex_config_path()
    if not path.exists():
        return PrimalCodexConfig()
    data = tomlkit.parse(path.read_text(encoding="utf-8"))
    return PrimalCodexConfig(
        **{k: v for k, v in data.items() if k in PrimalCodexConfig.model_fields}
    )
