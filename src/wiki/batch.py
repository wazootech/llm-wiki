"""Document selection and batch operations engine for Wiki operations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from .config import Config
from .fmt_util import format_markdown
from .paths import (
    iter_markdown_files,
    routes_from_markdown_files,
    select_document_paths,
    select_markdown_paths,
)
from .schemas import FmtReport


class DocumentBatch:
    """Helper for managing document collections and executing batch transformations."""

    def __init__(self, config: Config, files: Sequence[Path] | None = None) -> None:
        self.config = config
        self.raw_files = tuple(files) if files else None

    @property
    def is_filtered(self) -> bool:
        return self.raw_files is not None

    def route_filter(self) -> set[str] | None:
        if not self.raw_files:
            return None
        return routes_from_markdown_files(self.config, self.raw_files)

    def document_paths(self) -> list[Path] | None:
        if not self.raw_files:
            return None
        return select_document_paths(self.config, self.raw_files)

    def markdown_paths(self) -> list[Path]:
        if self.raw_files:
            return select_markdown_paths(self.config, self.raw_files)
        return list(iter_markdown_files(self.config))

    def format(self, *, check: bool = False, verbose: bool = False) -> FmtReport:
        """Format batch markdown files and build FmtReport."""
        report = FmtReport()
        for file_path in self.markdown_paths():
            try:
                original = file_path.read_text(encoding="utf-8")
                formatted = format_markdown(original, file_path, self.config)
                if original != formatted:
                    report.stale_files.append(file_path)
                    if not check:
                        file_path.write_text(formatted, encoding="utf-8")
                        report.formatted_count += 1
                        if verbose:
                            report.verbose_lines.append(f"Formatted {file_path.name}")
                elif verbose:
                    report.verbose_lines.append(f"Already formatted {file_path.name}")
            except Exception as exc:
                report.ok = False
                report.error_message = f"Error formatting {file_path.name}: {exc}"
                return report

        report.ok = not report.stale_files if check else True
        return report
