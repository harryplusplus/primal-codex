"""Primal Codex CLI."""

import typer

from primal_codex.run_codex import run_codex
from primal_codex.run_serve import run_serve

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")

# Path conventions shared across help texts.
_CONFIG_FILENAME = "config.toml"

_PRIMAL_CODEX_HOME_ENV_KEY = "PRIMAL_CODEX_HOME"
_PRIMAL_CODEX_HOME_DEFAULT = "~/.primal-codex"
_PRIMAL_CODEX_CONFIG = f"${{{_PRIMAL_CODEX_HOME_ENV_KEY}}}/{_CONFIG_FILENAME}"
_PRIMAL_CODEX_CONFIG_DEFAULT = f"{_PRIMAL_CODEX_HOME_DEFAULT}/{_CONFIG_FILENAME}"

_CODEX_HOME_ENV_KEY = "CODEX_HOME"
_CODEX_HOME_DEFAULT = "~/.codex"
_CODEX_CONFIG = f"${{{_CODEX_HOME_ENV_KEY}}}/{_CONFIG_FILENAME}"
_CODEX_CONFIG_DEFAULT = f"{_CODEX_HOME_DEFAULT}/{_CONFIG_FILENAME}"


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `{_PRIMAL_CODEX_CONFIG}` (default `{_PRIMAL_CODEX_CONFIG_DEFAULT}`)
and partially updates `{_CODEX_CONFIG}` (default `{_CODEX_CONFIG_DEFAULT}`).
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
- **`{_PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.
  Defaults to `{_PRIMAL_CODEX_HOME_DEFAULT}` if unset.
- **`{_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Codex home directory.
  Defaults to `{_CODEX_HOME_DEFAULT}` if unset."""  # noqa: E501
)
def codex() -> None:
    """Update the Codex model_provider configuration."""
    run_codex()


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `{_PRIMAL_CODEX_CONFIG}`
(default `{_PRIMAL_CODEX_CONFIG_DEFAULT}`) to configure the server.

### Environment Variables
- **`{_PRIMAL_CODEX_HOME_ENV_KEY}`** *(optional)* — Path to the Primal Codex home directory.
  Defaults to `{_PRIMAL_CODEX_HOME_DEFAULT}` if unset."""  # noqa: E501
)
def serve() -> None:
    """Start the Primal Codex API server."""
    run_serve()


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
