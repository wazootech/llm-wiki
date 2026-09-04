"""Build in-memory WikiSite from wiki documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import Config
from ..links import is_external_link
from ..parser import split_document_body
from ..paths import iter_document_files, route_for_document_file
from ..schemas.site import VirtualPage, WikiSite
from ..wiki_links import LinkIndex
from .markdown import (
    extract_outline,
    extract_title,
    render_wiki_markdown,
    strip_leading_title_heading,
)


def build_site(
    input_dirs: Config | list[Path] | Path,
    base_url: str | None = None,
    url_style: str | None = None,
) -> WikiSite:
    """Build in-memory representation of the wiki site."""
    if isinstance(input_dirs, Config):
        config = input_dirs
    else:
        dirs_arg = [input_dirs] if isinstance(input_dirs, Path) else input_dirs
        config = Config.for_root(Path.cwd(), wiki={"input": [str(p) for p in dirs_arg]})
    resolved_base_url = config.site.base_url if base_url is None else base_url
    resolved_url_style = config.site.url_style if url_style is None else url_style
    pages: list[VirtualPage] = []

    doc_files = sorted(iter_document_files(config))

    def file_slug(file_path: Path) -> str:
        return route_for_document_file(config, file_path)

    link_index = LinkIndex.from_config(config)

    for file_path in doc_files:
        fm_data, body = split_document_body(file_path)
        frontmatter = fm_data if fm_data is not None else {}

        doc_slug = file_slug(file_path)
        h1_title = (
            frontmatter.get("headline")
            or frontmatter.get("name")
            or extract_title(body, doc_slug)
        )
        h1_toc = extract_outline(body)
        wiki_ids = _page_wiki_ids(config, doc_slug, frontmatter)
        layout_path, layout_stem = parse_page_layout(frontmatter, config.config_root)

        display_body = strip_leading_title_heading(body, h1_title)
        h1_html = render_wiki_markdown(
            display_body,
            base_url=resolved_base_url,
            url_style=resolved_url_style,
            current_route=doc_slug,
        )
        pages.append(VirtualPage(
            file_slug=doc_slug,
            title=h1_title,
            markdown=body,
            html=h1_html,
            frontmatter=frontmatter,
            layout_path=layout_path,
            layout_stem=layout_stem,
            wiki_ids=wiki_ids,
            outline=h1_toc,
            backlink_slugs=link_index.backlinks_to(doc_slug),
            source_path=file_path,
        ))

    pages_by_route = {page.file_slug: page for page in pages}
    routes_by_wiki_id: dict[str, str] = {}
    for page in pages:
        for wiki_id in page.wiki_ids:
            routes_by_wiki_id[wiki_id] = page.file_slug

    return WikiSite(pages=pages, config=config, pages_by_route=pages_by_route, routes_by_wiki_id=routes_by_wiki_id)


def parse_page_layout(frontmatter: dict[str, Any], config_root: Path) -> tuple[Path | None, str]:
    from ..layout import parse_layout_from_frontmatter

    return parse_layout_from_frontmatter(frontmatter, config_root)


def _page_wiki_ids(config: Config, route: str, frontmatter: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("@id", "id"):
        raw = frontmatter.get(key)
        if isinstance(raw, str) and raw.strip():
            raw_value = raw.strip()
            values.append(raw_value)
            expanded = expand_known_curie(raw_value, config)
            if expanded != raw_value:
                values.append(expanded)
    suffix = ".md" if config.graph.include_file_extension else ""
    values.append(f"{config.base_iri}{route}{suffix}")
    return list(dict.fromkeys(values))


def expand_known_curie(value: str, config: Config) -> str:
    if ":" not in value or is_external_link(value) or value.lower().startswith("urn:"):
        return value
    prefix, local = value.split(":", 1)
    namespace = config.context.namespaces.get(prefix)
    if namespace is None:
        return value
    return f"{namespace}{local}"

