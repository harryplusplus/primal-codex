"""Application-wide context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from primal_codex.config import PrimalCodexConfig
    from primal_codex.models import ModelInfo


@dataclass
class AppContext:
    """Type-safe holder for application-wide state."""

    primal_config: PrimalCodexConfig
    model_map: dict[str, dict[str, ModelInfo]]
