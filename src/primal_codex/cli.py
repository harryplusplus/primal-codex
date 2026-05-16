"""Primal Codex CLI."""

import os

import typer

from primal_codex.run_codex import run_codex

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")


PRIMAL_CODEX_HOME_HELP = (
    "- **`PRIMAL_CODEX_HOME`** *(optional)* — Path to the Primal Codex home "
    "directory. Defaults to `~/.primal-codex` if unset."
)


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `$PRIMAL_CODEX_HOME/config.toml` (default `~/.primal-codex/config.toml`)  
and partially updates `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`).  
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
{PRIMAL_CODEX_HOME_HELP}
- **`CODEX_HOME`** *(optional)* — Path to the Codex home directory. Defaults to `~/.codex` if unset."""  # noqa: E501, W291
)
def codex() -> None:
    """Update the Codex model_provider configuration."""
    run_codex(os.environ.get("CODEX_HOME", ""))


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `$PRIMAL_CODEX_HOME/config.toml`  
(default `~/.primal-codex/config.toml`) to configure the server.

### Environment Variables
{PRIMAL_CODEX_HOME_HELP}"""  # noqa: W291
)
def serve() -> None:
    """Start the Primal Codex API server."""


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
