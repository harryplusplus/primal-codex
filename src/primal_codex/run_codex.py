from pathlib import Path


def run_codex(codex_home: str):
    config_path = _codex_config_path(codex_home)


def _codex_home(codex_home: str) -> Path:
    if codex_home:
        return Path(codex_home)
    return Path.home() / ".codex"


def _codex_config_path(codex_home: str) -> Path:
    return _codex_home(codex_home) / "config.toml"
