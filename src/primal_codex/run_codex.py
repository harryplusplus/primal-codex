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
from tomlkit import TOMLDocument

from primal_codex.config import load_config
from primal_codex.paths import resolve_codex_config_path

PRIMAL_CODEX_PROVIDER_ID = "primal-codex"


class _DeleteMarker:
    """Marker for a TOML key to be removed, optionally with a reason.

    When a non-empty ``reason`` is provided it is included in the removal
    message shown to the user.
    """

    def __init__(self, reason: str = "") -> None:
        self.reason = reason


def _get_toml_value(doc: TOMLDocument, key: str) -> object:
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


def _set_toml_value(doc: TOMLDocument, key: str, value: object) -> None:
    """Set a dotted key path in a dict-like document.

    Intermediate containers are created via ``setdefault`` when they do not
    exist.
    """
    parts = key.split(".")
    current = doc
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _delete_toml_key(doc: TOMLDocument, key: str) -> None:
    """Remove a dotted key path from a dict-like document.

    Silently returns when the key or any of its parent containers does not
    exist.
    """
    parts = key.split(".")
    current = doc
    for part in parts[:-1]:
        current = current.get(part)
        if not isinstance(current, dict):
            return
    current.pop(parts[-1], None)


def _detect_changes(doc: TOMLDocument, desired: dict[str, object]) -> bool:
    """Return ``True`` when any desired value differs from the current document."""
    for key, value in desired.items():
        current = _get_toml_value(doc, key)
        if isinstance(value, _DeleteMarker):
            if current is not None:
                return True
        elif current != value:
            return True
    return False


def run_codex() -> None:
    """Update Codex configuration based on Primal Codex settings.

    Compares the current Codex config against the desired values derived
    from the Primal Codex config and writes changes only when necessary.
    """
    # 1. Load the Primal Codex server config.
    primal_config = load_config()
    server_url = f"http://{primal_config.server.host}:{primal_config.server.port}"

    # 2. Read the existing Codex config, or start fresh if absent.
    codex_path = resolve_codex_config_path()
    raw = codex_path.read_text(encoding="utf-8") if codex_path.exists() else ""
    doc = tomlkit.parse(raw)

    # 3. Define the desired state — the single source of truth for all changes.
    desired: dict[str, object] = {
        "model_provider": PRIMAL_CODEX_PROVIDER_ID,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.name": PRIMAL_CODEX_PROVIDER_ID,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.base_url": server_url,
        f"model_providers.{PRIMAL_CODEX_PROVIDER_ID}.supports_websockets": False,
        "model_catalog_json": _DeleteMarker("Primal Codex manages models dynamically"),
    }

    # 4. Detect whether any change is needed.
    changed = _detect_changes(doc, desired)
    if not changed:
        typer.echo(f"Codex config is already up to date at {codex_path}")
        return

    # 5. Backup the existing file (only when it already exists).
    if codex_path.exists():
        bak_path = str(codex_path) + ".bak"
        shutil.copy2(codex_path, bak_path)
        typer.echo(f"Backed up existing config to {bak_path}")

    # 6. Apply all desired changes using tomlkit (preserves formatting of
    #    untouched sections).
    for key, value in desired.items():
        if isinstance(value, _DeleteMarker):
            _delete_toml_key(doc, key)
        else:
            _set_toml_value(doc, key, value)

    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

    # 7. Report results.
    typer.echo(f"Updated Codex config at {codex_path}")
    for key, value in desired.items():
        if isinstance(value, _DeleteMarker):
            msg = f"  Removed {key}"
            if value.reason:
                msg += f" ({value.reason})"
            typer.echo(msg)
        else:
            typer.echo(f"  Set {key} = {value!r}")
