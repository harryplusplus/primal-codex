import os
from pathlib import Path

CONFIG_FILENAME = "config.toml"

PRIMAL_CODEX_HOME_ENV_KEY = "PRIMAL_CODEX_HOME"
PRIMAL_CODEX_HOME_DEFAULT = Path.home() / ".primal-codex"


def resolve_primal_codex_config_path() -> Path:
    env = os.environ.get(PRIMAL_CODEX_HOME_ENV_KEY, "")
    p = (Path(env) if env else PRIMAL_CODEX_HOME_DEFAULT) / CONFIG_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


CODEX_HOME_ENV_KEY = "CODEX_HOME"
CODEX_HOME_DEFAULT = Path.home() / ".codex"


def resolve_codex_config_path() -> Path:
    env = os.environ.get(CODEX_HOME_ENV_KEY, "")
    p = (Path(env) if env else CODEX_HOME_DEFAULT) / CONFIG_FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
