"""Tests for the ``primal-codex init`` CLI command.

Behavior under test:
1.  ``init`` with no existing config creates ``config.toml`` with default content.
2.  ``init`` with an existing config does **not** overwrite it.
3.  The created config content matches the built-in default template.
4.  The parent directory is created automatically when missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from primal_codex.cli import app
from primal_codex.config import get_default_config
from primal_codex.paths import (
    PRIMAL_CODEX_HOME_ENV_KEY,
    resolve_primal_codex_config_path,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from typer.testing import CliRunner


class TestInit:
    """Test suite for ``primal-codex init``."""

    def test_init_creates_config_in_empty_dir(
        self,
        cli_runner: CliRunner,
        tmp_primal_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """``init`` creates a ``config.toml`` when none exists."""
        result = cli_runner.invoke(app, ["init"], env=cli_env)

        assert result.exit_code == 0, f"CLI exited with error: {result.stdout}"
        config_path = tmp_primal_home / "config.toml"
        assert config_path.exists(), "config.toml should have been created"

    def test_init_prints_created_message(
        self,
        cli_runner: CliRunner,
        tmp_primal_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """``init`` prints a success message when creating the config."""
        result = cli_runner.invoke(app, ["init"], env=cli_env)

        config_path = tmp_primal_home / "config.toml"
        assert f"Created default config at {config_path}" in result.stdout

    def test_init_creates_parent_directory(
        self,
        cli_runner: CliRunner,
        tmp_path: Path,
        cli_env: dict[str, str],
    ) -> None:
        """``init`` creates the parent directory when it does not exist."""
        deep_home = tmp_path / "a" / "b" / "c" / "primal"
        deep_env = {**cli_env}
        deep_env[PRIMAL_CODEX_HOME_ENV_KEY] = str(deep_home)

        result = cli_runner.invoke(app, ["init"], env=deep_env)

        assert result.exit_code == 0
        assert deep_home.exists(), "Parent directory should have been created"
        assert (deep_home / "config.toml").exists()

    def test_init_config_content_matches_default(
        self,
        cli_runner: CliRunner,
        tmp_primal_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """The created config content should be identical to the built-in default."""
        expected = get_default_config()

        cli_runner.invoke(app, ["init"], env=cli_env)

        config_path = tmp_primal_home / "config.toml"
        actual = config_path.read_text(encoding="utf-8")
        assert actual == expected, "Config content differs from default template"

    def test_init_does_not_overwrite_existing(
        self,
        cli_runner: CliRunner,
        tmp_primal_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """``init`` does not overwrite an existing config file."""
        config_path = tmp_primal_home / "config.toml"
        original_text = "# custom config\n[server]\nhost = '0.0.0.0'\n"
        config_path.write_text(original_text, encoding="utf-8")

        result = cli_runner.invoke(app, ["init"], env=cli_env)

        assert result.exit_code == 0
        assert config_path.read_text(encoding="utf-8") == original_text

    def test_init_prints_already_exists_message(
        self,
        cli_runner: CliRunner,
        tmp_primal_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Print an "already exists" message for existing config."""
        config_path = tmp_primal_home / "config.toml"
        config_path.write_text("", encoding="utf-8")

        result = cli_runner.invoke(app, ["init"], env=cli_env)

        assert f"Config already exists at {config_path}" in result.stdout

    def test_init_respects_primal_codex_home_env(
        self, cli_runner: CliRunner, tmp_path: Path
    ) -> None:
        """``init`` uses ``PRIMAL_CODEX_HOME`` to determine the config path."""
        custom_home = tmp_path / "custom-location"
        env = {PRIMAL_CODEX_HOME_ENV_KEY: str(custom_home)}

        cli_runner.invoke(app, ["init"], env=env)

        assert (custom_home / "config.toml").exists()

    def test_init_resolves_path_correctly(
        self,
        cli_runner: CliRunner,
        tmp_primal_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``resolve_primal_codex_config_path`` returns the expected path."""
        monkeypatch.setenv(PRIMAL_CODEX_HOME_ENV_KEY, str(tmp_primal_home))
        expected = tmp_primal_home / "config.toml"

        cli_runner.invoke(
            app, ["init"], env={PRIMAL_CODEX_HOME_ENV_KEY: str(tmp_primal_home)}
        )

        actual = resolve_primal_codex_config_path()
        assert actual == expected
