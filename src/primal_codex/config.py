"""Primal Codex configuration loader.

Provides :class:`PrimalCodexConfig` (server host, port, etc.) by reading
``~/.primal-codex/config.toml`` (or ``$PRIMAL_CODEX_HOME/config.toml``).
Missing settings fall back to their field defaults, so the config file is
entirely optional.
"""

from __future__ import annotations

import os

import tomlkit
from pydantic import BaseModel

from primal_codex.paths import resolve_primal_codex_config_path

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
# temperature = 0.7
# max_tokens = 4096
"""


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
    """

    server: ServerConfig = ServerConfig()
    providers: dict[str, ProviderConfig] = {}


class ModelConfig(BaseModel):
    """Configuration for a single model within a provider.

    Attributes:
        temperature: Sampling temperature. ``None`` means the provider default.
        max_tokens: Maximum tokens per response. ``None`` means the provider
            default.

    """

    temperature: float | None = None
    max_tokens: int | None = None


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
