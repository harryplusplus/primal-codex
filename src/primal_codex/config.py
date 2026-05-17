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
from primal_codex.paths import resolve_primal_codex_config_path

DEFAULT_CONFIG = """\
# Primal Codex configuration.
#
# This file is entirely optional — every field has a built-in default
# (shown below).  Uncomment a line and modify the value to override it.

[server]
# Address the server binds to.
# (default: "127.0.0.1")
# host = "127.0.0.1"

# Port the server listens on.
# (default: 8010)
# port = 8010

# --- Providers ---
#
# Provider keys are dynamic.  Add any name you like under ``[providers]``.
#
#   [providers.<provider_id>]
#   base_url = "..."          # required
#   env_key = "API_KEY_VAR"   # optional; env var name holding the API key
#
# Each provider can expose one or more models under
# ``[providers.<provider_id>.models."<model_id>"]``.
# All fields below are optional — the value the Codex client actually
# receives is shown in parentheses.
#
# --- Identity ---
# display_name = "..."                        # (default: <model_id>)
# description = "..."                          # (default: null)
#
# --- Capabilities ---
# supported_reasoning_levels = []              # (default: [])
# input_modalities = ["text", "image"]        # (default: ["text", "image"])
# supports_search_tool = false                 # (default: false)
# supports_parallel_tool_calls = false          # (default: false)
# supports_image_detail_original = false        # (default: false)
#
# --- Ranking & visibility ---
# priority = 0                                  # (default: 0)
# visibility = "list"                           # (default: "list")
# supported_in_api = true                        # (default: true)
#
# --- Shell & tools ---
# shell_type = "shell_command"                  # (default: "shell_command")
# apply_patch_tool_type                          # (default: null)
# web_search_tool_type = "text"                  # (default: "text")
#
# --- Context & truncation ---
# truncation_policy = { mode = "bytes", limit = 10000 }  # (default)
# context_window                                  # (default: omitted)
# max_context_window                              # (default: omitted)
# auto_compact_token_limit                        # (default: omitted)
# effective_context_window_percent = 95           # (default: 95)
#
# --- Instructions ---
# base_instructions = ""                          # (default: <built-in>)
# supports_reasoning_summaries = false            # (default: false)
# default_reasoning_summary = "auto"              # (default: "auto")
# support_verbosity = false                       # (default: false)
# default_verbosity                               # (default: null)
#
# --- Reasoning ---
# default_reasoning_level                         # (default: omitted)
#
# --- Advanced ---
# additional_speed_tiers = []                     # (default: [])
# service_tiers = []                              # (default: [])
# availability_nux                                # (default: null)
# upgrade                                         # (default: null)
# model_messages                                  # (default: omitted)
# experimental_supported_tools = []               # (default: [])
#
# --- Example ---
#
# Uncomment the block below to register Crof with two models.
#
# [providers.crof]
# base_url = "https://crof.ai/v1"
# env_key = "CROF_API_KEY"
#
# [providers.crof.models."glm-5.1-precision"]
# display_name = "Crof GLM-5.1 Precision"
# supported_reasoning_levels = [{ effort = "medium" }, { effort = "high" }]
# input_modalities = ["text"]
#
# [providers.crof.models."kimi-k2.6-precision"]
# display_name = "Crof Kimi K2.6 Precision"
# supported_reasoning_levels = [{ effort = "medium" }, { effort = "high" }]
"""


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
    infos: list[ModelInfo] = []
    for pid, provider in config.providers.items():
        for key, cfg in provider.models.items():
            infos.append(enrich_model(key, pid, cfg))
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
