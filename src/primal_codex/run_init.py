"""Primal Codex config initialisation."""

import typer

from primal_codex.config import get_default_config
from primal_codex.paths import resolve_primal_codex_config_path


def run_init() -> None:
    """Create the default Primal Codex config file if it does not exist.

    The file is written to ``$PRIMAL_CODEX_HOME/config.toml``, or
    ``~/.primal-codex/config.toml`` when the environment variable is unset.
    An existing file is never overwritten.
    """
    path = resolve_primal_codex_config_path()

    if path.exists():
        typer.echo(f"Config already exists at {path}")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(get_default_config(), encoding="utf-8")
    typer.echo(f"Created default config at {path}")
