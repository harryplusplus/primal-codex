"""Tests for the ``primal-codex codex`` CLI command.

Behavior under test:
1.  ``codex`` creates a Codex config with correct provider settings when none exists.
2.  ``codex`` is a no-op when config is already correct.
3.  ``codex`` fixes an incorrect ``model_provider`` and backs up the old config.
4.  ``codex`` removes ``model_catalog_json`` if present.
5.  ``codex`` respects custom ``server.host`` / ``server.port``.
"""

from __future__ import annotations

from tomllib import load as toml_load
from typing import TYPE_CHECKING

from primal_codex.cli import app
from primal_codex.run_codex import PRIMAL_CODEX_PROVIDER_ID

if TYPE_CHECKING:
    from pathlib import Path

    from typer.testing import CliRunner


class TestCodex:
    """Test suite for ``primal-codex codex``."""

    def test_codex_creates_config_when_missing(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Create a Codex config when none exists."""
        result = cli_runner.invoke(app, ["codex"], env=cli_env)

        assert result.exit_code == 0, f"CLI exited with error: {result.stdout}"
        config_path = tmp_codex_home / "config.toml"
        assert config_path.exists(), "Codex config should have been created"

    def test_codex_sets_correct_provider_settings(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Set the correct provider name and base URL."""
        cli_runner.invoke(app, ["codex"], env=cli_env)
        config_path = tmp_codex_home / "config.toml"

        with config_path.open("rb") as f:
            cfg = toml_load(f)

        assert cfg["model_provider"] == PRIMAL_CODEX_PROVIDER_ID
        provider = cfg["model_providers"][PRIMAL_CODEX_PROVIDER_ID]
        assert provider["name"] == PRIMAL_CODEX_PROVIDER_ID
        assert provider["base_url"] == "http://127.0.0.1:8010"

    def test_codex_prints_updated_message(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Print an update message with the config path."""
        result = cli_runner.invoke(app, ["codex"], env=cli_env)
        config_path = tmp_codex_home / "config.toml"
        assert f"Updated Codex config at {config_path}" in result.stdout

    def test_codex_prints_custom_messages(
        self,
        cli_runner: CliRunner,
        cli_env: dict[str, str],
    ) -> None:
        """Print custom messages for each desired value."""
        result = cli_runner.invoke(app, ["codex"], env=cli_env)

        assert (
            f"Use '{PRIMAL_CODEX_PROVIDER_ID}' as the model provider" in result.stdout
        )
        assert f"Register model provider '{PRIMAL_CODEX_PROVIDER_ID}'" in result.stdout
        assert (
            f"Point '{PRIMAL_CODEX_PROVIDER_ID}' at http://127.0.0.1:8010"
            in result.stdout
        )
        assert (
            f"'{PRIMAL_CODEX_PROVIDER_ID}' uses HTTP SSE streaming, not WebSocket"
            in result.stdout
        )
        removed_msg = (
            "Removed model_catalog_json"
            " (Primal Codex provides model discovery via /models)"
        )
        assert removed_msg in result.stdout

    def test_codex_already_up_to_date(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Skip changes when config is already correct."""
        cli_runner.invoke(app, ["codex"], env=cli_env)
        config_path = tmp_codex_home / "config.toml"
        contents_before = config_path.read_text(encoding="utf-8")

        result = cli_runner.invoke(app, ["codex"], env=cli_env)
        assert f"Codex config is already up to date at {config_path}" in result.stdout
        assert config_path.read_text(encoding="utf-8") == contents_before

    def test_codex_no_backup_when_up_to_date(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Skip creating a ``.bak`` file when no changes are needed."""
        cli_runner.invoke(app, ["codex"], env=cli_env)
        cli_runner.invoke(app, ["codex"], env=cli_env)
        assert not (tmp_codex_home / "config.toml.bak").exists()

    def test_codex_updates_wrong_provider(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Fix an incorrect ``model_provider`` value."""
        config_path = tmp_codex_home / "config.toml"
        config_path.write_text(
            "model_provider = 'some-other-provider'\n", encoding="utf-8"
        )

        cli_runner.invoke(app, ["codex"], env=cli_env)
        with config_path.open("rb") as f:
            cfg = toml_load(f)
        assert cfg["model_provider"] == PRIMAL_CODEX_PROVIDER_ID

    def test_codex_updates_wrong_base_url(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Fix an incorrect ``base_url`` value."""
        config_path = tmp_codex_home / "config.toml"
        config_path.write_text(
            "[model_providers.primal-codex]\nname = 'primal-codex'\nbase_url = 'http://wrong:9999'\n",
            encoding="utf-8",
        )

        cli_runner.invoke(app, ["codex"], env=cli_env)
        with config_path.open("rb") as f:
            cfg = toml_load(f)
        assert (
            cfg["model_providers"]["primal-codex"]["base_url"]
            == "http://127.0.0.1:8010"
        )

    def test_codex_removes_model_catalog_json(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Remove ``model_catalog_json`` and report the removal reason."""
        config_path = tmp_codex_home / "config.toml"
        config_path.write_text(
            'model_catalog_json = "/some/path"\nmodel_provider = "wrong"\n',
            encoding="utf-8",
        )

        result = cli_runner.invoke(app, ["codex"], env=cli_env)
        removed_msg = (
            "Removed model_catalog_json"
            " (Primal Codex provides model discovery via /models)"
        )
        assert removed_msg in result.stdout

        with config_path.open("rb") as f:
            cfg = toml_load(f)
        assert "model_catalog_json" not in cfg

    def test_codex_creates_backup(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Create a ``.bak`` file when changes are made."""
        config_path = tmp_codex_home / "config.toml"
        original = "model_provider = 'old-provider'\n"
        config_path.write_text(original, encoding="utf-8")

        cli_runner.invoke(app, ["codex"], env=cli_env)

        bak_path = tmp_codex_home / "config.toml.bak"
        assert bak_path.exists()
        assert bak_path.read_text(encoding="utf-8") == original

    def test_codex_prints_backup_message(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Print a backup message when backing up an existing config."""
        config_path = tmp_codex_home / "config.toml"
        config_path.write_text("model_provider = 'old'\n", encoding="utf-8")

        result = cli_runner.invoke(app, ["codex"], env=cli_env)
        assert f"Backed up existing config to {config_path}.bak" in result.stdout

    def test_codex_handles_multiple_issues(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
    ) -> None:
        """Fix wrong provider AND remove model_catalog_json in one run."""
        config_path = tmp_codex_home / "config.toml"
        config_path.write_text(
            'model_catalog_json = "/some/path"\n'
            'model_provider = "some-other-provider"\n',
            encoding="utf-8",
        )

        result = cli_runner.invoke(app, ["codex"], env=cli_env)

        # Both changes reported with their custom messages.
        removed_msg = (
            "Removed model_catalog_json"
            " (Primal Codex provides model discovery via /models)"
        )
        assert removed_msg in result.stdout
        assert (
            f"Use '{PRIMAL_CODEX_PROVIDER_ID}' as the model provider" in result.stdout
        )

        # Both applied to the file.
        with config_path.open("rb") as f:
            cfg = toml_load(f)
        assert "model_catalog_json" not in cfg
        assert cfg["model_provider"] == PRIMAL_CODEX_PROVIDER_ID

    def test_codex_uses_custom_host_port(
        self,
        cli_runner: CliRunner,
        tmp_codex_home: Path,
        cli_env: dict[str, str],
        tmp_primal_home: Path,
    ) -> None:
        """Use custom ``server.host`` and ``server.port`` for base_url."""
        config_path = tmp_primal_home / "config.toml"
        config_path.write_text(
            "[server]\nhost = '0.0.0.0'\nport = 9999\n", encoding="utf-8"
        )

        cli_runner.invoke(app, ["codex"], env=cli_env)

        codex_config = tmp_codex_home / "config.toml"
        with codex_config.open("rb") as f:
            cfg = toml_load(f)
        assert (
            cfg["model_providers"]["primal-codex"]["base_url"] == "http://0.0.0.0:9999"
        )
