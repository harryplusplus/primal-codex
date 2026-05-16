"""Primal Codex CLI."""

import dataclasses
import os

import typer

from primal_codex.run_codex import run_codex

app = typer.Typer(no_args_is_help=True, rich_markup_mode="markdown")


@dataclasses.dataclass(frozen=True)
class _Home:
    """Convention for a home-directory-based config path.

    Attributes:
        env_var: Environment variable name (e.g. ``PRIMAL_CODEX_HOME``).
        default_dir: Default directory path (e.g. ``~/.primal-codex``).

    """

    env_var: str
    default_dir: str

    @property
    def config(self) -> str:
        """Display form of the config path using the env var."""
        return f"${{{self.env_var}}}/config.toml"

    @property
    def config_default(self) -> str:
        """Default filesystem path to the config file."""
        return f"{self.default_dir}/config.toml"


# Path conventions shared across help texts.
PRIMAL_CODEX = _Home("PRIMAL_CODEX_HOME", "~/.primal-codex")
CODEX = _Home("CODEX_HOME", "~/.codex")


@app.command(
    help=f"""Update Codex configuration based on Primal Codex settings.

Reads settings from `{PRIMAL_CODEX.config}` (default `{PRIMAL_CODEX.config_default}`)  
and partially updates `{CODEX.config}` (default `{CODEX.config_default}`).  
A backup of any existing target file is saved as `<path>.bak`.

### Environment Variables
- **`{PRIMAL_CODEX.env_var}`** *(optional)* — Path to the Primal Codex home directory. Defaults to `{PRIMAL_CODEX.default_dir}` if unset.
- **`{CODEX.env_var}`** *(optional)* — Path to the Codex home directory. Defaults to `{CODEX.default_dir}` if unset."""  # noqa: E501, W291
)
def codex() -> None:
    """Update the Codex model_provider configuration."""
    run_codex(os.environ.get("CODEX_HOME", ""))


@app.command(
    help=f"""Start the Primal Codex API server.

Reads settings from `{PRIMAL_CODEX.config}` (default `{PRIMAL_CODEX.config_default}`)  
to configure the server.

### Environment Variables
- **`{PRIMAL_CODEX.env_var}`** *(optional)* — Path to the Primal Codex home directory. Defaults to `{PRIMAL_CODEX.default_dir}` if unset."""  # noqa: E501, W291
)
def serve() -> None:
    """Start the Primal Codex API server."""


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
