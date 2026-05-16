"""Primal Codex CLI."""

import os

import typer

from primal_codex.run_codex import run_codex

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")


# Environment variable names and default paths shared across commands.
_PRIMAL_CODEX_HOME = "PRIMAL_CODEX_HOME"
_PRIMAL_CODEX_HOME_DEFAULT = "~/.primal-codex"


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `${{{_PRIMAL_CODEX_HOME}}}/config.toml`  
(default `{_PRIMAL_CODEX_HOME_DEFAULT}/config.toml`) and partially updates  
`$CODEX_HOME/config.toml` (default `~/.codex/config.toml`).  
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
- **`{_PRIMAL_CODEX_HOME}`** *(optional)* — Path to the Primal Codex home directory. Defaults to `{_PRIMAL_CODEX_HOME_DEFAULT}` if unset.
- **`CODEX_HOME`** *(optional)* — Path to the Codex home directory. Defaults to `~/.codex` if unset."""  # noqa: E501, W291
)
def codex() -> None:
    """Update the Codex model_provider configuration."""
    run_codex(os.environ.get("CODEX_HOME", ""))


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `${{{_PRIMAL_CODEX_HOME}}}/config.toml`  
(default `{_PRIMAL_CODEX_HOME_DEFAULT}/config.toml`) to configure the server.

### Environment Variables
- **`{_PRIMAL_CODEX_HOME}`** *(optional)* — Path to the Primal Codex home directory. Defaults to `{_PRIMAL_CODEX_HOME_DEFAULT}` if unset."""  # noqa: E501, W291
)
def serve() -> None:
    """Start the Primal Codex API server."""


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
