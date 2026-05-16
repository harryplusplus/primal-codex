"""Primal Codex CLI."""

import os

import typer

from primal_codex.run_codex import run_codex

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")

# ---------------------------------------------------------------------------
# Path conventions shared across help texts.
#
# These constants capture the env-var names, default directories, and full
# config-file paths so that every command help uses exactly the same spelling
# for the same contract.
# ---------------------------------------------------------------------------

# Primal Codex home
_PRIMAL_CODEX_HOME = "PRIMAL_CODEX_HOME"
_PRIMAL_CODEX_HOME_DEFAULT = "~/.primal-codex"
_PRIMAL_CODEX_CONFIG = "${PRIMAL_CODEX_HOME}/config.toml"
_PRIMAL_CODEX_CONFIG_DEFAULT = "~/.primal-codex/config.toml"

# Codex home (upstream)
_CODEX_HOME = "CODEX_HOME"
_CODEX_HOME_DEFAULT = "~/.codex"
_CODEX_CONFIG = "${CODEX_HOME}/config.toml"
_CODEX_CONFIG_DEFAULT = "~/.codex/config.toml"


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `{_PRIMAL_CODEX_CONFIG}` (default `{_PRIMAL_CODEX_CONFIG_DEFAULT}`)  
and partially updates `{_CODEX_CONFIG}` (default `{_CODEX_CONFIG_DEFAULT}`).  
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
- **`{_PRIMAL_CODEX_HOME}`** *(optional)* — Path to the Primal Codex home directory. Defaults to `{_PRIMAL_CODEX_HOME_DEFAULT}` if unset.
- **`{_CODEX_HOME}`** *(optional)* — Path to the Codex home directory. Defaults to `{_CODEX_HOME_DEFAULT}` if unset."""  # noqa: E501, W291
)
def codex() -> None:
    """Update the Codex model_provider configuration."""
    run_codex(os.environ.get("CODEX_HOME", ""))


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `{_PRIMAL_CODEX_CONFIG}` (default `{_PRIMAL_CODEX_CONFIG_DEFAULT}`)  
to configure the server.

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
