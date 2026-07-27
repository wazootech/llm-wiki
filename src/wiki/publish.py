"""Static site build orchestration."""

from __future__ import annotations

import shutil
from pathlib import Path

from .assets import build_asset_manifest, write_packaged_asset
from .errors import BuildError
from .graph import load_query_graph
from .paths import build_page_manifest, detect_output_collisions, page_output_path
from .render import render_markdown_files
from .schemas import BuildOptions, BuildResult
from .wiki import Wiki
from .site import build_index_html, build_page_html, build_site


def _path_is_same_or_ancestor(ancestor: Path, descendant: Path) -> bool:
    ancestor = ancestor.resolve()
    descendant = descendant.resolve()
    if ancestor == descendant:
        return True
    try:
        descendant.relative_to(ancestor)
        return True
    except ValueError:
        return False


def _validate_build_output_dir(page_output_dir: Path, config) -> None:
    page_output_dir = page_output_dir.resolve()
    protected: list[tuple[str, Path]] = [
        ("config root", config.config_root.resolve()),
    ]
    for input_dir in config.wiki.inputs:
        protected.append(("wiki input", input_dir.resolve()))
    for asset_dir in config.wiki.assets:
        protected.append(("wiki asset", asset_dir.resolve()))
    layout = config.page_layout
    if layout is not None and layout.is_file():
        protected.append(("page layout", layout.parent.resolve()))

    for label, path in protected:
        if _path_is_same_or_ancestor(page_output_dir, path):
            raise BuildError(
                f"refusing to clean build output path {page_output_dir} because it "
                f"overlaps {label} at {path}. Choose a separate output directory such as _site."
            )


def _build_static_site(wiki: Wiki, options: BuildOptions) -> BuildResult:
    config = wiki.config
    written_paths: list[Path] = []

    if options.render_first:
        reload_next = options.reload_graph

        def query_graph(sparql_query: str):
            nonlocal reload_next
            graph = load_query_graph(config, sparql_query, infer=True, reload=reload_next, disk_cache=options.disk_cache)
            reload_next = False
            return graph

        success, _errors, _stale, _render_errors = render_markdown_files(config, query_graph=query_graph)
        if options.disk_cache and success > 0:
            wiki.graph(infer=True, reload=True, disk_cache=True)
            wiki.dataset(infer=True, reload=True, disk_cache=True)

    if not any(path.exists() for path in config.wiki.inputs):
        dirs_str = ", ".join(str(path) for path in config.wiki.inputs)
        return BuildResult(ok=False, error_message=f"none of the input directories exist ({dirs_str})")

    if not options.skip_preflight:
        preflight = wiki.preflight()
        if preflight.errors or not preflight.ok:
            return BuildResult(ok=False, preflight=preflight)

    base_url = config.site.base_url or ""
    url_style = config.site.url_style or "dir"
    site = build_site(config, base_url=base_url, url_style=url_style)
    output_dir = options.output_dir.resolve()

    config_root = config.config_root
    default_layout: Path | None = None
    if config.page_layout is not None and config.page_layout.is_file():
        default_layout = config.page_layout

    page_output_dir = output_dir / base_url.strip("/") if base_url else output_dir
    manifest = (
        build_page_manifest(config, page_output_dir, base_url, url_style)
        + build_asset_manifest(config, page_output_dir, base_url)
    )
    collision_issues = detect_output_collisions(manifest)
    if collision_issues:
        from .schemas import AuditReport, Issue

        preflight = AuditReport(
            ok=False,
            errors=[
                Issue(code="output_collision", message=message, severity="error")
                for message in collision_issues
            ],
        )
        return BuildResult(ok=False, preflight=preflight)

    page_output_dir = page_output_dir.resolve()
    _validate_build_output_dir(page_output_dir, config)

    if page_output_dir.exists():
        shutil.rmtree(page_output_dir)
    page_output_dir.mkdir(parents=True, exist_ok=True)

    has_root_index = any(page.full_slug == "" for page in site.pages)
    if not has_root_index:
        index_path = page_output_dir / "index.html"
        index_path.write_text(
            build_index_html(
                site,
                config_root,
                base_url=base_url,
                url_style=url_style,
                default_layout=default_layout,
            ),
            encoding="utf-8",
        )
        written_paths.append(index_path.relative_to(output_dir))

    for page in site.pages:
        file_path = page_output_path(page_output_dir, page.full_slug, url_style)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            build_page_html(
                page,
                config_root,
                base_url=base_url,
                url_style=url_style,
                default_layout=default_layout,
            ),
            encoding="utf-8",
        )
        written_paths.append(file_path.relative_to(output_dir))

    asset_entries = build_asset_manifest(config, page_output_dir, base_url)
    for entry in asset_entries:
        entry.output_path.parent.mkdir(parents=True, exist_ok=True)
        if entry.source is not None:
            shutil.copy2(entry.source, entry.output_path)
        elif entry.output_path.name.endswith(".css"):
            write_packaged_asset(entry.output_path.name, entry.output_path)
        written_paths.append(entry.output_path.relative_to(output_dir))

    return BuildResult(
        ok=True,
        page_count=len(site.pages),
        asset_count=len(asset_entries),
        written_paths=written_paths,
    )
