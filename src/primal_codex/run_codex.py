"""Codex configuration update logic.

Reads the Primal Codex server config (host, port) and applies or corrects
the corresponding ``model_provider`` / ``model_providers`` entries in the
Codex config file (``~/.codex/config.toml``).  Existing files are backed up
to ``<path>.bak`` before overwriting, and the original TOML formatting is
preserved via :mod:`tomlkit`.
"""

from __future__ import annotations

import shutil

import tomlkit
import typer

from primal_codex.config import load_config
from primal_codex.paths import resolve_codex_config_path

PRIMAL_CODEX_PROVIDER_ID = "primal-codex"


def run_codex() -> None:
    """Update Codex configuration based on Primal Codex settings.

    Compares the current Codex config against the desired values derived
    from the Primal Codex config and writes changes only when necessary.
    """
    # 1. Load the Primal Codex server config.
    primal = load_config()
    server_url = f"http://{primal.server.host}:{primal.server.port}"

    # 2. Read the existing Codex config (if any).
    codex_path = resolve_codex_config_path()
    if codex_path.exists():
        raw = codex_path.read_text(encoding="utf-8")
        doc = tomlkit.parse(raw)
    else:
        doc = tomlkit.parse("")

    # 3. Compare desired vs. current values.
    desired = {
        "model_provider": PRIMAL_CODEX_PROVIDER_ID,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.name": PRIMAL_CODEX_PROVIDER_ID,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.base_url": server_url,
    }

    changes: dict[str, str] = {}
    for key, value in desired.items():
        # Walk the dotted path to read the current value.
        parts = key.split(".")
        current: object = doc
        try:
            for part in parts:
                if isinstance(current, dict):
                    current = current[part]
                else:
                    current = None
                    break
        except (KeyError, TypeError):
            current = None

        if current != value:
            changes[key] = value

    if not changes:
        typer.echo(f"Codex config is already up to date at {codex_path}")
        return

    # 4. Backup the existing file (only when it already exists).
    bak_path: str | None = None
    if codex_path.exists():
        bak_path = str(codex_path) + ".bak"
        shutil.copy2(codex_path, bak_path)
        typer.echo(f"Backed up existing config to {bak_path}")

    # 5. Apply changes with tomlkit (preserves formatting of untouched sections).
    doc["model_provider"] = PRIMAL_CODEX_PROVIDER_ID
    providers = doc.setdefault("model_providers", {})
    entry = providers.setdefault(PRIMAL_CODEX_PROVIDER_ID, {})
    entry["name"] = PRIMAL_CODEX_PROVIDER_ID
    entry["base_url"] = server_url

    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    # 6. Report results.
    typer.echo(f"Updated Codex config at {codex_path}")
    for key, value in changes.items():
        typer.echo(f"  Set {key} = {value!r}")
