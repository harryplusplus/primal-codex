"""Primal Codex CLI."""

import typer

from primal_codex.paths import (
    CODEX_HOME_DISPLAY_DIR,
    CODEX_HOME_DISPLAY_PATH,
    CODEX_HOME_ENV_KEY,
    CODEX_HOME_ENV_VAR_PATH,
    CONFIG_FILENAME,
    PRIMAL_CODEX_HOME_DISPLAY_DIR,
    PRIMAL_CODEX_HOME_DISPLAY_PATH,
    PRIMAL_CODEX_HOME_ENV_KEY,
    PRIMAL_CODEX_HOME_ENV_VAR_PATH,
)
from primal_codex.run_codex import run_codex
from primal_codex.run_init import run_init
from primal_codex.run_serve import run_serve

app = typer.Typer(
    no_args_is_help=True, rich_markup_mode="markdown", add_completion=False
)


@app.command(
    help=f"""Create the default Primal Codex config file if it does not exist.

Writes a fresh ``{CONFIG_FILENAME}`` to ``{PRIMAL_CODEX_HOME_ENV_VAR_PATH}`` (default ``{PRIMAL_CODEX_HOME_DISPLAY_PATH}``).  
An existing file is never overwritten.

### Environment Variables
- **`{PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.  
  Defaults to ``{PRIMAL_CODEX_HOME_DISPLAY_DIR}`` if unset."""  # noqa: E501, W291
)
def init() -> None:
    """Create the default Primal Codex config file if it does not exist."""
    run_init()


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `{PRIMAL_CODEX_HOME_ENV_VAR_PATH}` (default `{PRIMAL_CODEX_HOME_DISPLAY_PATH}`) and partially updates `{CODEX_HOME_ENV_VAR_PATH}` (default `{CODEX_HOME_DISPLAY_PATH}`).  
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
- **`{PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.  
  Defaults to `{PRIMAL_CODEX_HOME_DISPLAY_DIR}` if unset.
- **`{CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Codex home directory.  
  Defaults to `{CODEX_HOME_DISPLAY_DIR}` if unset."""  # noqa: E501, W291
)
def codex() -> None:
    """Update Codex configuration based on Primal Codex settings."""
    run_codex()


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `{PRIMAL_CODEX_HOME_ENV_VAR_PATH}` (default `{PRIMAL_CODEX_HOME_DISPLAY_PATH}`) to configure the server.

### Environment Variables
- **`{PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.  
  Defaults to `{PRIMAL_CODEX_HOME_DISPLAY_DIR}` if unset."""  # noqa: E501, W291
)
def serve() -> None:
    """Start the Primal Codex API server."""
    run_serve()


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
