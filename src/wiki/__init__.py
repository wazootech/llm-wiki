"""Clean, pure, idiomatic Python CLI for managing a semantic LLM wiki."""

from __future__ import annotations

from .config import Config
from .errors import BuildError, UpgradeError, WikiError
from .schemas import (
    AuditReport,
    BuildOptions,
    BuildResult,
    ExportResult,
    FmtReport,
    GraphDescriptor,
    InitOptions,
    Issue,
    LinkReport,
    RenderReport,
    ScaffoldResult,
)
from .wiki import Wiki

__version__ = "0.1.22"

__all__ = [
    "__version__",
    "AuditReport",
    "BuildError",
    "BuildOptions",
    "BuildResult",
    "Config",
    "ExportResult",
    "FmtReport",
    "GraphDescriptor",
    "InitOptions",
    "Issue",
    "LinkReport",
    "RenderReport",
    "ScaffoldResult",
    "UpgradeError",
    "WikiError",
    "Wiki",
]
