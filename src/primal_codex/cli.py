"""Primal Codex CLI."""

import typer

from primal_codex.paths import (
    CODEX_HOME_DISPLAY,
    CODEX_HOME_ENV_KEY,
    CONFIG_FILENAME,
    PRIMAL_CODEX_HOME_DISPLAY,
    PRIMAL_CODEX_HOME_ENV_KEY,
)
from primal_codex.run_codex import run_codex
from primal_codex.run_serve import run_serve

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `${{{PRIMAL_CODEX_HOME_ENV_KEY}}}/{CONFIG_FILENAME}`
(default `{PRIMAL_CODEX_HOME_DISPLAY}/{CONFIG_FILENAME}`)
and partially updates `${{{CODEX_HOME_ENV_KEY}}}/{CONFIG_FILENAME}`
(default `{CODEX_HOME_DISPLAY}/{CONFIG_FILENAME}`).
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
- **`{PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.
  Defaults to `{PRIMAL_CODEX_HOME_DISPLAY}` if unset.
- **`{CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Codex home directory.
  Defaults to `{CODEX_HOME_DISPLAY}` if unset."""  # noqa: E501
)
def codex() -> None:
    """Update Codex configuration based on Primal Codex settings."""
    run_codex()


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `${{{PRIMAL_CODEX_HOME_ENV_KEY}}}/{CONFIG_FILENAME}`
(default `{PRIMAL_CODEX_HOME_DISPLAY}/{CONFIG_FILENAME}`) to configure the server.

### Environment Variables
- **`{PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.
  Defaults to `{PRIMAL_CODEX_HOME_DISPLAY}` if unset."""  # noqa: E501
)
def serve() -> None:
    """Start the Primal Codex API server."""
    run_serve()


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
