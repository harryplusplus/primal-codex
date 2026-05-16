"""Primal Codex CLI."""

import os

import typer

from primal_codex.run_codex import run_codex

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")


@app.command(
    help="""Update the `model_provider` configuration in the Codex config file.

The file is located at `$CODEX_HOME/config.toml` (fallback `~/.codex/config.toml`).  
A backup of any existing file is saved as `<path>.bak`.

### Environment Variables
- **`CODEX_HOME`** *(optional)* — Path to the Codex home directory.
  Defaults to `~/.codex` if unset."""  # noqa: W291
)
def codex() -> None:
    """Update the Codex model_provider configuration."""
    run_codex(os.environ.get("CODEX_HOME", ""))


@app.command()
def serve() -> None:
    """Start the Primal Codex API server."""


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
