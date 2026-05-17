"""Canonical path definitions and resolvers for Primal Codex.

All path-related constants (directory names, env var keys, default paths, and
user-facing display strings) are defined here as a single source of truth.
"""

import os
from pathlib import Path

CONFIG_FILENAME = "config.toml"

PRIMAL_CODEX_HOME_DIR = ".primal-codex"
PRIMAL_CODEX_HOME_ENV_KEY = "PRIMAL_CODEX_HOME"
PRIMAL_CODEX_HOME_DEFAULT = Path.home() / PRIMAL_CODEX_HOME_DIR
PRIMAL_CODEX_HOME_DISPLAY = f"~/{PRIMAL_CODEX_HOME_DIR}"


def resolve_primal_codex_config_path() -> Path:
    """Resolve the config path for Primal Codex.

    Respects the ``PRIMAL_CODEX_HOME`` environment variable. Falls back to
    ``~/.primal-codex/config.toml`` when the variable is unset.

    Returns:
        Absolute ``Path`` to the Primal Codex config file.

    """
    env = os.environ.get(PRIMAL_CODEX_HOME_ENV_KEY, "")
    return (Path(env) if env else PRIMAL_CODEX_HOME_DEFAULT) / CONFIG_FILENAME


CODEX_HOME_DIR = ".codex"
CODEX_HOME_ENV_KEY = "CODEX_HOME"
CODEX_HOME_DEFAULT = Path.home() / CODEX_HOME_DIR
CODEX_HOME_DISPLAY = f"~/{CODEX_HOME_DIR}"


def resolve_codex_config_path() -> Path:
    """Resolve the config path for Codex.

    Respects the ``CODEX_HOME`` environment variable. Falls back to
    ``~/.codex/config.toml`` when the variable is unset.

    Returns:
        Absolute ``Path`` to the Codex config file.

    """
    env = os.environ.get(CODEX_HOME_ENV_KEY, "")
    return (Path(env) if env else CODEX_HOME_DEFAULT) / CONFIG_FILENAME


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = _PROJECT_ROOT / "assets" / "prompt.md"
DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "assets" / "default-config.toml"
