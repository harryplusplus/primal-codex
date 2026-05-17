"""Primal Codex configuration loader.

Config structure:

  [providers.<provider_id>]
  base_url = "..."
  env_key = "API_KEY_VAR"

  [providers.<provider_id>.models."<model_id>"]
  # ``ModelConfig`` keys (see model_config.py for every field).
  display_name = "My Model"
  priority = 100
"""

import os

import tomlkit
from pydantic import BaseModel

from primal_codex.models import ModelConfig, ModelInfo, enrich_model
from primal_codex.paths import (
    DEFAULT_CONFIG_PATH,
    PROMPT_PATH,
    resolve_primal_codex_config_path,
)


def get_default_config() -> str:
    """Return the default Primal Codex configuration template."""
    return DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")


class ServerConfig(BaseModel):
    """Server binding configuration."""

    host: str = "127.0.0.1"
    port: int = 8010


class ProviderConfig(BaseModel):
    """Configuration for a single provider."""

    base_url: str | None = None
    env_key: str | None = None
    models: dict[str, ModelConfig] = {}

    def resolve_api_key(self) -> str | None:
        """Return the API key from the environment variable, if configured."""
        if self.env_key is None:
            return None
        return os.environ.get(self.env_key)


class PrimalCodexConfig(BaseModel):
    """Top-level Primal Codex configuration, loaded from TOML."""

    server: ServerConfig = ServerConfig()
    providers: dict[str, ProviderConfig] = {}


def compute_model_infos(config: PrimalCodexConfig) -> list[ModelInfo]:
    """Enrich every raw ``ModelConfig`` into a complete ``ModelInfo``."""
    default_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    infos: list[ModelInfo] = []
    for pid, provider in config.providers.items():
        for key, cfg in provider.models.items():
            infos.append(enrich_model(key, pid, cfg, default_prompt))
    infos.sort(key=lambda m: m.priority)
    return infos


def load_config() -> PrimalCodexConfig:
    """Load configuration from the Primal Codex TOML file."""
    path = resolve_primal_codex_config_path()
    if not path.exists():
        return PrimalCodexConfig()
    data = tomlkit.parse(path.read_text(encoding="utf-8"))
    return PrimalCodexConfig(
        **{k: v for k, v in data.items() if k in PrimalCodexConfig.model_fields}
    )
