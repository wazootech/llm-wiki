"""Path, route, URL, and output-manifest helpers for wiki pages."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

from .config import Config
from .parser import DOCUMENT_EXTENSIONS
from .schemas.domain import OutputEntry, PageRoute

UNSAFE_ROUTE_CHARS = set("?#%")


def iter_document_files(config: Config) -> list[Path]:
    doc_files: list[Path] = []
    for input_dir in config.wiki.input:
        if input_dir.exists():
            for file_path in sorted(input_dir.rglob("*")):
                if not file_path.is_file() or file_path.suffix.lower() not in DOCUMENT_EXTENSIONS:
                    continue
                if not config.is_excluded(file_path):
                    doc_files.append(file_path)
    return doc_files


def iter_markdown_files(config: Config) -> list[Path]:
    return [file_path for file_path in iter_document_files(config) if file_path.suffix.lower() == ".md"]


def _wiki_document_index(config: Config) -> dict[Path, Path]:
    return {file_path.resolve(): file_path for file_path in iter_document_files(config)}


def _resolve_wiki_paths(
    config: Config,
    paths: tuple[Path, ...],
    *,
    allowed_suffixes: set[str],
    label: str,
) -> list[Path]:
    if not paths:
        return []
    index = _wiki_document_index(config)
    selected: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        wiki_path = index.get(resolved)
        if wiki_path is None:
            raise ValueError(f"{path.name} is not a wiki document under inputs (or is excluded).")
        if wiki_path.suffix.lower() not in allowed_suffixes:
            raise ValueError(f"{label} only supports {', '.join(sorted(allowed_suffixes))} files, got {wiki_path.name}.")
        selected.append(wiki_path)
    return selected


def select_document_paths(config: Config, paths: tuple[Path, ...]) -> list[Path]:
    """Resolve explicit CLI paths to wiki documents (.md, .yaml, .json), preserving order."""
    return _resolve_wiki_paths(
        config,
        paths,
        allowed_suffixes=set(DOCUMENT_EXTENSIONS),
        label="export",
    )


def select_markdown_paths(config: Config, paths: tuple[Path, ...]) -> list[Path]:
    """Resolve explicit CLI paths to wiki markdown files, preserving order."""
    return _resolve_wiki_paths(config, paths, allowed_suffixes={".md"}, label="command")


def routes_from_markdown_files(config: Config, paths: tuple[Path, ...]) -> set[str]:
    """Build route filter set from explicit markdown paths."""
    return {route_for_document_file(config, path) for path in select_markdown_paths(config, paths)}


def route_for_document_file(config: Config, file_path: Path) -> str:
    rel = _relative_to_input_dir(config, file_path).with_suffix("").as_posix()
    parts = [part for part in rel.split("/") if part]
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    _validate_route_parts(parts, file_path)
    return "/".join(parts)


def page_routes(config: Config) -> list[PageRoute]:
    return [PageRoute(source=file_path, route=route_for_document_file(config, file_path)) for file_path in iter_document_files(config)]


def page_url(base_url: str, route: str, url_style: str) -> str:
    base = base_url.rstrip("/") if base_url else ""
    encoded = quote(route, safe="/()_-.$~")
    if url_style == "file":
        if encoded:
            return f"{base}/{encoded}.html" if base else f"/{encoded}.html"
        return f"{base}/index.html" if base else "/index.html"
    if encoded:
        return f"{base}/{encoded}/" if base else f"/{encoded}/"
    return f"{base}/" if base else "/"


def page_output_path(owned_output_dir: Path, route: str, url_style: str) -> Path:
    if url_style == "file":
        if not route:
            return owned_output_dir / "index.html"
        parts = route.split("/")
        return owned_output_dir.joinpath(*parts[:-1], f"{parts[-1]}.html")
    if not route:
        return owned_output_dir / "index.html"
    return owned_output_dir.joinpath(*route.split("/"), "index.html")


def build_page_manifest(config: Config, owned_output_dir: Path, base_url: str, url_style: str) -> list[OutputEntry]:
    return [
        OutputEntry(
            source=route.source,
            output_path=page_output_path(owned_output_dir, route.route, url_style),
            public_url=page_url(base_url, route.route, url_style),
            kind="page",
        )
        for route in page_routes(config)
    ]


def detect_output_collisions(entries: list[OutputEntry]) -> list[str]:
    issues: list[str] = []
    seen_paths: dict[str, OutputEntry] = {}
    seen_urls: dict[str, OutputEntry] = {}
    for entry in entries:
        path_key = str(entry.output_path).lower()
        url_key = entry.public_url.lower()
        previous_path = seen_paths.get(path_key)
        if previous_path is not None:
            issues.append(_collision_message("output path", previous_path, entry))
        else:
            seen_paths[path_key] = entry
        previous_url = seen_urls.get(url_key)
        if previous_url is not None:
            issues.append(_collision_message("public URL", previous_url, entry))
        else:
            seen_urls[url_key] = entry
    return issues


def validate_filename_pattern(config: Config, md_file: Path) -> str | None:
    if not config.wiki.filename_pattern:
        return None
    if md_file.suffix.lower() != ".md":
        return None
    try:
        pattern = re.compile(config.wiki.filename_pattern)
    except re.error as exc:
        return f"Invalid filename_pattern: {exc}"
    if pattern.fullmatch(md_file.name) is None:
        return f"Filename '{md_file.name}' does not match filename_pattern."
    return None


def validate_route_safety(config: Config) -> list[str]:
    issues: list[str] = []
    for file_path in iter_document_files(config):
        try:
            route_for_document_file(config, file_path)
        except ValueError as exc:
            issues.append(str(exc))
    return issues


def _relative_to_input_dir(config: Config, md_file: Path) -> Path:
    for root in config.wiki.input:
        try:
            return md_file.relative_to(root)
        except ValueError:
            continue
    return md_file


def _validate_route_parts(parts: list[str], source: Path) -> None:
    for part in parts:
        if part in {"", ".", ".."}:
            raise ValueError(f"Unsafe route for {source}: path segments cannot be empty, '.', or '..'.")
        if any(ch.isspace() for ch in part):
            raise ValueError(f"Unsafe route for {source}: spaces are not allowed in page paths.")
        if any(ord(ch) < 32 for ch in part):
            raise ValueError(f"Unsafe route for {source}: control characters are not allowed in page paths.")
        found = sorted(ch for ch in UNSAFE_ROUTE_CHARS if ch in part)
        if found:
            chars = "".join(found)
            raise ValueError(f"Unsafe route for {source}: characters '{chars}' are not allowed in page paths.")


def _collision_message(kind: str, first: OutputEntry, second: OutputEntry) -> str:
    return (
        f"Output collision on {kind} '{first.public_url}': "
        f"{_source_label(first)} conflicts with {_source_label(second)}."
    )


def _source_label(entry: OutputEntry) -> str:
    if entry.source is None:
        return entry.kind
    return f"{entry.kind} {entry.source}"
