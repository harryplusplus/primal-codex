"""Shared fixtures and configuration for Primal Codex test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from primal_codex.paths import CODEX_HOME_ENV_KEY, PRIMAL_CODEX_HOME_ENV_KEY

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def cli_runner() -> CliRunner:
    """Return a ``typer.testing.CliRunner`` for invoking CLI commands."""
    return CliRunner()


@pytest.fixture
def tmp_primal_home(tmp_path: Path) -> Path:
    """Return a pristine temporary ``PRIMAL_CODEX_HOME`` directory."""
    home = tmp_path / "primal-home"
    home.mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def tmp_codex_home(tmp_path: Path) -> Path:
    """Return a pristine temporary ``CODEX_HOME`` directory."""
    home = tmp_path / "codex-home"
    home.mkdir(parents=True, exist_ok=True)
    return home


@pytest.fixture
def cli_env(tmp_primal_home: Path, tmp_codex_home: Path) -> dict[str, str]:
    """Return env vars for any ``primal-codex`` CLI command."""
    return {
        PRIMAL_CODEX_HOME_ENV_KEY: str(tmp_primal_home),
        CODEX_HOME_ENV_KEY: str(tmp_codex_home),
    }
