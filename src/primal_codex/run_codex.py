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


def _get_toml_value(doc: dict, key: str) -> object:
    """Walk a dotted key path (e.g. ``"a.b.c"``) into a tomlkit document."""
    parts = key.split(".")
    current: object = doc
    try:
        for part in parts:
            if isinstance(current, dict):
                current = current[part]
            else:
                return None
    except (KeyError, TypeError):
        return None
    else:
        return current


def run_codex() -> None:
    """Update Codex configuration based on Primal Codex settings.

    Compares the current Codex config against the desired values derived
    from the Primal Codex config and writes changes only when necessary.
    """
    # 1. Load the Primal Codex server config.
    primal = load_config()
    server_url = f"http://{primal.server.host}:{primal.server.port}"

    # 2. Read the existing Codex config, or start fresh if absent.
    codex_path = resolve_codex_config_path()
    raw = codex_path.read_text(encoding="utf-8") if codex_path.exists() else ""
    doc = tomlkit.parse(raw)

    # 3. Detect required changes.
    changed = False

    # Remove model_catalog_json if present — Primal Codex manages models
    # dynamically via its own endpoints; a static catalog would interfere.
    if doc.get("model_catalog_json") is not None:
        del doc["model_catalog_json"]
        changed = True
        typer.echo(
            "  Removed model_catalog_json (Primal Codex manages models dynamically)"
        )

    # Detect provider value changes.
    desired = {
        "model_provider": PRIMAL_CODEX_PROVIDER_ID,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.name": PRIMAL_CODEX_PROVIDER_ID,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.base_url": server_url,
    }
    for key, value in desired.items():
        if _get_toml_value(doc, key) != value:
            changed = True
            break

    if not changed:
        typer.echo(f"Codex config is already up to date at {codex_path}")
        return

    # 5. Backup the existing file (only when it already exists).
    if codex_path.exists():
        bak_path = str(codex_path) + ".bak"
        shutil.copy2(codex_path, bak_path)
        typer.echo(f"Backed up existing config to {bak_path}")

    # 6. Apply changes with tomlkit (preserves formatting of untouched sections).
    doc["model_provider"] = PRIMAL_CODEX_PROVIDER_ID
    providers = doc.setdefault("model_providers", {})
    entry = providers.setdefault(PRIMAL_CODEX_PROVIDER_ID, {})
    entry["name"] = PRIMAL_CODEX_PROVIDER_ID
    entry["base_url"] = server_url
    entry["supports_websockets"] = False

    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    # 7. Report results.
    typer.echo(f"Updated Codex config at {codex_path}")
    for key, value in desired.items():
        typer.echo(f"  Set {key} = {value!r}")
