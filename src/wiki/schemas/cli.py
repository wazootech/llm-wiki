"""Pydantic models for CLI command options — single source of truth.

These models define the shape of every CLI subcommand's options.
Export via ``model_json_schema(by_alias=True)`` for JSON Schema files
that drive TypeScript type generation.

The ``alias`` on each field controls the JSON Schema
property name (camelCase for TS consumers).  Click decorators in
``cli.py`` remain hand-written.

Class docstrings and ``Field(description=...)`` mirror the TypeScript API
docs (``npm/src/types.ts``): they flow through ``model_json_schema`` into
the generated ``npm/src/types.generated.ts`` as JSDoc, which the typedoc
``notDocumented`` gate requires.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MainOptions(BaseModel):
    """Options for the root ``wiki`` command (config resolution)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    wiki_inputs: tuple[str, ...] | None = Field(
        default=None,
        alias="wikiInputs",
        description="Override ``wiki.inputs`` from the config file.",
    )
    config_path: str = Field(
        default=".",
        alias="config",
        description="Path to ``wiki.yml`` (or directory containing it).",
    )


# ── Mixin for commands that accept zero-or-more FILE positional args ──


class FileOptions(BaseModel):
    """Mixin for commands that accept a ``files`` filter."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    files: tuple[Path, ...] = Field(
        default=(),
        alias="files",
        description="Subset of wiki files to operate on. Omit for whole-wiki mode.",
    )


# ── check / lint ──


class CheckOptions(FileOptions):
    """Options for ``Wiki.check()``."""

    verbose: bool = Field(
        default=False, alias="verbose", description="Print detailed audit output."
    )
    strict: bool = Field(
        default=False,
        alias="strict",
        description="Elevate all warnings to errors.",
    )


class LintOptions(FileOptions):
    """Options for ``Wiki.lint()``."""

    verbose: bool = Field(
        default=False, alias="verbose", description="Print detailed audit output."
    )
    strict: bool = Field(
        default=False,
        alias="strict",
        description="Elevate all warnings to errors.",
    )


# ── link ──


class LinkOptions(FileOptions):
    """Options for ``Wiki.link()``."""

    apply: bool = Field(
        default=False,
        alias="apply",
        description="Insert suggested internal links.",
    )
    fix_broken: bool = Field(
        default=False,
        alias="fixBroken",
        description="Repair unambiguous broken internal links.",
    )
    dry_run: bool = Field(
        default=False,
        alias="dryRun",
        description="Preview changes without writing files.",
    )
    check: bool = Field(
        default=False,
        alias="check",
        description="Exit with code 1 if opportunities or broken links remain.",
    )
    verbose: bool = Field(
        default=False,
        alias="verbose",
        description="Show target titles; list changed files.",
    )


# ── query ──


QUERY_FORMATS = ["table", "json", "csv", "tsv", "turtle", "n3", "markdown"]


class QueryOptions(BaseModel):
    """Options for ``Wiki.query()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query_args: tuple[str, ...] = Field(
        default=(),
        alias="query",
        description="The SPARQL query string (required).",
    )
    output_format: str = Field(
        default="table",
        alias="format",
        description="Output format.",
        json_schema_extra={"enum": QUERY_FORMATS},
    )
    output: Path | None = Field(
        default=None,
        alias="output",
        description="Write output to a file.",
    )
    no_inference: bool = Field(
        default=False,
        alias="noInference",
        description="Skip OWL-RL inference.",
    )
    reload: bool = Field(
        default=False,
        alias="reload",
        description="Rebuild the graph before querying.",
    )
    disk_cache: bool = Field(
        default=False,
        alias="cache",
        description="Persist the graph to disk.",
    )
    jq: str | None = Field(
        default=None,
        alias="jq",
        description='Key-path filter for JSON output (implies ``format="json"``).',
    )
    pretty: bool = Field(
        default=False,
        alias="pretty",
        description="Render a rich table (stdout only).",
    )
    verbose: bool = Field(
        default=False,
        alias="verbose",
        description="Print graph statistics before results.",
    )


# ── render ──


class RenderOptions(FileOptions):
    """Options for ``Wiki.render()``."""

    no_inference: bool = Field(
        default=False,
        alias="noInference",
        description="Skip OWL-RL inference.",
    )
    reload: bool = Field(
        default=False,
        alias="reload",
        description="Rebuild the graph before rendering.",
    )
    disk_cache: bool = Field(
        default=False,
        alias="cache",
        description="Persist the graph to disk.",
    )
    check: bool = Field(
        default=False,
        alias="check",
        description="Detect stale blocks without modifying files.",
    )
    verbose: bool = Field(
        default=False,
        alias="verbose",
        description="Print summary of updated files.",
    )


# ── build ──


class BuildOptions(BaseModel):
    """Options for ``Wiki.build()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    output_dir: str = Field(
        default="_site",
        alias="outputDir",
        description='Target directory (default ``"_site"``).',
    )
    site_base_url: str | None = Field(
        default=None,
        alias="baseUrl",
        description="Override ``site.base_url``.",
    )
    site_url_style: Literal["dir", "file"] | None = Field(
        default=None,
        alias="urlStyle",
        description='Override ``site.url_style`` (``"file"`` or ``"dir"``).',
    )
    render: bool = Field(
        default=False,
        alias="render",
        description="Render inline SPARQL blocks before building.",
    )
    reload: bool = Field(
        default=False,
        alias="reload",
        description="Rebuild the graph before rendering.",
    )
    disk_cache: bool = Field(
        default=False,
        alias="cache",
        description="Persist the graph to disk.",
    )
    no_check: bool = Field(
        default=False,
        alias="noCheck",
        description="Skip lint + check preflight.",
    )
    verbose: bool = Field(
        default=False,
        alias="verbose",
        description="Print generated file paths.",
    )


# ── export ──


EXPORT_FORMATS = ["dict", "json-ld", "turtle", "xml", "n3", "nt", "trig", "nquads"]


class ExportOptions(FileOptions):
    """Options for ``Wiki.export()``."""

    output: Path | None = Field(
        default=None,
        alias="output",
        description="Output file path.",
    )
    rdf_format: str = Field(
        default="dict",
        alias="format",
        description="RDF serialization format.",
        json_schema_extra={"enum": EXPORT_FORMATS},
    )
    mode: Literal["expanded", "compacted"] = Field(
        default="expanded",
        alias="mode",
        description='JSON-LD mode (``"expanded"`` or ``"compacted"``).',
    )


# ── serve ──


class ServeOptions(BaseModel):
    """Options for ``Wiki.serve()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    host: str = Field(
        default="127.0.0.1",
        alias="host",
        description="Host to bind the server to.",
    )
    port: int = Field(default=8080, alias="port", description="Port to serve on.")
    site_base_url: str | None = Field(
        default=None,
        alias="baseUrl",
        description="Override ``site.base_url``.",
    )
    site_url_style: Literal["dir", "file"] | None = Field(
        default=None,
        alias="urlStyle",
        description='Override ``site.url_style`` (``"file"`` or ``"dir"``).',
    )
    watch: bool = Field(
        default=False,
        alias="watch",
        description="Watch for file changes and auto-rebuild.",
    )


# ── init ──


class InitOptions(BaseModel):
    """Options for ``Wiki.init()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    init_git: bool = Field(
        default=False,
        alias="git",
        description="Run ``git init`` after scaffolding.",
    )
    repo: str | None = Field(
        default=None,
        alias="repo",
        description="GitHub ``owner/repo`` string for inferring defaults.",
    )
    graph_context_wiki: str | None = Field(
        default=None,
        alias="graphContextWiki",
        description="Override ``graph.context.wiki`` IRI.",
    )
    site_base_url: str | None = Field(
        default=None,
        alias="baseUrl",
        description='Override ``site.base_url`` (default ``/wiki`` or inferred from ``--repo``).',
    )
    site_url_style: Literal["dir", "file"] | None = Field(
        default=None,
        alias="urlStyle",
        description='Override ``site.url_style`` (``"file"`` or ``"dir"``).',
    )
    site_layout: str | None = Field(
        default=None,
        alias="siteLayout",
        description="Override ``site.layout``.",
    )
    graph_content_predicate: str | None = Field(
        default=None,
        alias="graphContentPredicate",
        description="Override ``graph.content_predicate``.",
    )
    link_style: Literal["standard", "wikilink"] | None = Field(
        default=None,
        alias="linkStyle",
        description='Override ``link.style`` (``"standard"`` or ``"wikilink"``).',
    )
    wiki_inputs: tuple[str, ...] | None = Field(
        default=None,
        alias="wikiInputs",
        description="Override ``wiki.inputs`` (repeatable).",
    )
    graph_base_iri: str | None = Field(
        default=None,
        alias="graphBaseIri",
        description="Override ``graph.base_iri``.",
    )
    graph_implicit_types: tuple[str, ...] | None = Field(
        default=None,
        alias="graphImplicitTypes",
        description="Default types for untyped documents.",
    )
    graph_implicit_types_policy: Literal["fallback", "append"] | None = Field(
        default=None,
        alias="graphImplicitTypesPolicy",
        description="Strategy when applying ``graph.implicit_types``.",
    )
    graph_include_file_extension: bool | None = Field(
        default=None,
        alias="graphIncludeFileExtension",
        description="Override ``graph.include_file_extension``.",
    )
    init_template: str | None = Field(
        default=None,
        alias="template",
        description="Scaffold from a starter template in wazootech/wiki-templates.",
    )


# ── mcp ──


class McpOptions(BaseModel):
    """Options for ``Wiki.mcp()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: Literal["stdio"] = Field(
        default="stdio",
        alias="mode",
        description='MCP transport mode (default ``"stdio"``).',
    )
    disk_cache: bool = Field(
        default=False,
        alias="cache",
        description="Persist graph under ``.wiki/cache`` across MCP launches.",
    )


# ── sources: install / update / remove ──


class InstallOptions(BaseModel):
    """Options for ``Wiki.install()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: str | None = Field(
        default=None,
        alias="url",
        description=(
            "Git URL of an external source to add, fetch, and lock. "
            "Omit to install all declared sources."
        ),
    )


class UpdateOptions(BaseModel):
    """Options for ``Wiki.update()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = Field(
        default=None,
        alias="name",
        description="Source name to check; omit to check all locked sources.",
    )
    dry_run: bool = Field(
        default=False,
        alias="dryRun",
        description="Report what would update without modifying wiki.lock.",
    )


class RemoveOptions(BaseModel):
    """Options for ``Wiki.remove()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(alias="name", description="Name of the source to remove.")


# ── fmt ──


class FmtOptions(FileOptions):
    """Options for ``Wiki.fmt()``."""

    check: bool = Field(
        default=False,
        alias="check",
        description="Report formatting issues without modifying files.",
    )
    verbose: bool = Field(
        default=False,
        alias="verbose",
        description="Print per-file formatting status.",
    )


# ── upgrade ──


class UpgradeOptions(BaseModel):
    """Options for ``Wiki.upgrade()``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    check_only: bool = Field(
        default=False,
        alias="check",
        description="Check for updates without upgrading. Exits 1 if outdated.",
    )
    auto_yes: bool = Field(
        default=False,
        alias="yes",
        description="Skip confirmation prompt.",
    )
    verbose: bool = Field(
        default=False,
        alias="verbose",
        description="Show pip install output.",
    )


# ── registry: command → model mapping ──

COMMAND_MODELS: dict[str, type[BaseModel]] = {
    "check": CheckOptions,
    "lint": LintOptions,
    "link": LinkOptions,
    "query": QueryOptions,
    "render": RenderOptions,
    "build": BuildOptions,
    "export": ExportOptions,
    "serve": ServeOptions,
    "init": InitOptions,
    "mcp": McpOptions,
    "fmt": FmtOptions,
    "upgrade": UpgradeOptions,
    "install": InstallOptions,
    "update": UpdateOptions,
    "remove": RemoveOptions,
}

__all__ = [
    "COMMAND_MODELS",
    "EXPORT_FORMATS",
    "QUERY_FORMATS",
]
