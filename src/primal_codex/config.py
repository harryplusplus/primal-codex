"""Primal Codex configuration loader.

Config structure — the only schema we own:

  [providers.<name>]
  base_url = "..."
  env_key = "API_KEY_VAR"

  [providers.<name>.models."<slug>"]
  # Every field here is codex ``ModelInfo`` (src/primal_codex/models.py).
  # Any field omitted falls back to the codex SOT default.
  display_name = "My Model"
  priority = 100

Everything else (types, field names, defaults, optionality rules) is
codex SOT — see ``models.py``.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import tomlkit
from pydantic import BaseModel

from primal_codex.paths import resolve_primal_codex_config_path

if TYPE_CHECKING:
    from primal_codex.models import ModelInfo


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

# --- Providers ---
#
# Provider keys are dynamic. Each entry under ``[providers.<name>.models]``
# maps to codex ``ModelInfo``; any field omitted uses the codex SOT default.

# [providers.crof]
# base_url = "https://crof.ai/v1"
# env_key = "CROF_API_KEY"
#
# [providers.crof.models."glm-5.1-precision"]
# display_name = "GLM 5.1 Precision"
# priority = 100
# truncation_policy = { mode = "tokens", limit = 10000 }
"""


class ServerConfig(BaseModel):
    """Server binding configuration."""

    host: str = "127.0.0.1"
    port: int = 8010


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""

    base_url: str | None = None
    env_key: str | None = None
    models: dict[str, ModelInfo] = {}

    def resolve_api_key(self) -> str | None:
        """Return the API key from the environment variable, if configured."""
        if self.env_key is None:
            return None
        return os.environ.get(self.env_key)


class PrimalCodexConfig(BaseModel):
    """Top-level Primal Codex configuration, loaded from TOML."""

    server: ServerConfig = ServerConfig()
    providers: dict[str, ProviderConfig] = {}

    def model_post_init(self, __context: object, /) -> None:
        """Set slug for every model entry at config-load time."""
        for pid, provider in self.providers.items():
            for key, mi in provider.models.items():
                mi.slug = f"{pid}/{key}"


def load_config() -> PrimalCodexConfig:
    """Load configuration from the Primal Codex TOML file."""
    path = resolve_primal_codex_config_path()
    if not path.exists():
        return PrimalCodexConfig()
    data = tomlkit.parse(path.read_text(encoding="utf-8"))
    return PrimalCodexConfig(
        **{k: v for k, v in data.items() if k in PrimalCodexConfig.model_fields}
    )
