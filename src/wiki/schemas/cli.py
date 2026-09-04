"""Pydantic models for CLI command options — single source of truth.

These models define the shape of every CLI subcommand's options.
Export via ``model_json_schema(by_alias=True)`` for JSON Schema files
that drive TypeScript type generation.

The ``alias`` on each field controls the JSON Schema
property name (camelCase for TS consumers).  Click decorators in
``cli.py`` remain hand-written.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MainOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    wiki_inputs: tuple[str, ...] | None = Field(
        default=None, alias="wikiInputs"
    )
    config_path: str = Field(default=".", alias="config")


# ── Mixin for commands that accept zero-or-more FILE positional args ──


class FileOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    files: tuple[Path, ...] = Field(default=(), alias="files")


# ── check / lint ──


class CheckOptions(FileOptions):
    verbose: bool = Field(default=False, alias="verbose")
    strict: bool = Field(default=False, alias="strict")


class LintOptions(FileOptions):
    verbose: bool = Field(default=False, alias="verbose")
    strict: bool = Field(default=False, alias="strict")


# ── link ──


class LinkOptions(FileOptions):
    apply: bool = Field(default=False, alias="apply")
    fix_broken: bool = Field(default=False, alias="fixBroken")
    dry_run: bool = Field(default=False, alias="dryRun")
    check: bool = Field(default=False, alias="check")
    verbose: bool = Field(default=False, alias="verbose")


# ── query ──


QUERY_FORMATS = ["table", "json", "csv", "tsv", "turtle", "n3", "markdown"]


class QueryOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query_args: tuple[str, ...] = Field(default=(), alias="query")
    output_format: str = Field(
        default="table",
        alias="format",
        json_schema_extra={"enum": QUERY_FORMATS},
    )
    output: Path | None = Field(default=None, alias="output")
    no_inference: bool = Field(default=False, alias="noInference")
    reload: bool = Field(default=False, alias="reload")
    disk_cache: bool = Field(default=False, alias="cache")
    jq: str | None = Field(default=None, alias="jq")
    pretty: bool = Field(default=False, alias="pretty")
    verbose: bool = Field(default=False, alias="verbose")


# ── render ──


class RenderOptions(FileOptions):
    no_inference: bool = Field(default=False, alias="noInference")
    reload: bool = Field(default=False, alias="reload")
    disk_cache: bool = Field(default=False, alias="cache")
    check: bool = Field(default=False, alias="check")
    verbose: bool = Field(default=False, alias="verbose")


# ── build ──


class BuildOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    output_dir: str = Field(default="_site", alias="outputDir")
    site_base_url: str | None = Field(default=None, alias="baseUrl")
    site_url_style: Literal["dir", "file"] | None = Field(
        default=None, alias="urlStyle"
    )
    render: bool = Field(default=False, alias="render")
    reload: bool = Field(default=False, alias="reload")
    disk_cache: bool = Field(default=False, alias="cache")
    no_check: bool = Field(default=False, alias="noCheck")
    verbose: bool = Field(default=False, alias="verbose")


# ── export ──


EXPORT_FORMATS = ["dict", "json-ld", "turtle", "xml", "n3", "nt", "trig", "nquads"]


class ExportOptions(FileOptions):
    output: Path | None = Field(default=None, alias="output")
    rdf_format: str = Field(
        default="dict",
        alias="format",
        json_schema_extra={"enum": EXPORT_FORMATS},
    )
    mode: Literal["expanded", "compacted"] = Field(
        default="expanded", alias="mode"
    )


# ── serve ──


class ServeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    host: str = Field(default="127.0.0.1", alias="host")
    port: int = Field(default=8080, alias="port")
    site_base_url: str | None = Field(default=None, alias="baseUrl")
    site_url_style: Literal["dir", "file"] | None = Field(
        default=None, alias="urlStyle"
    )
    watch: bool = Field(default=False, alias="watch")


# ── init ──


class InitOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    init_git: bool = Field(default=False, alias="git")
    repo: str | None = Field(default=None, alias="repo")
    graph_context_wiki: str | None = Field(
        default=None, alias="graphContextWiki"
    )
    site_base_url: str | None = Field(default=None, alias="baseUrl")
    site_url_style: Literal["dir", "file"] | None = Field(
        default=None, alias="urlStyle"
    )
    site_layout: str | None = Field(default=None, alias="siteLayout")
    graph_content_predicate: str | None = Field(
        default=None, alias="graphContentPredicate"
    )
    link_style: Literal["standard", "wikilink"] | None = Field(
        default=None, alias="linkStyle"
    )
    wiki_inputs: tuple[str, ...] | None = Field(
        default=None, alias="wikiInputs"
    )
    graph_base_iri: str | None = Field(
        default=None, alias="graphBaseIri"
    )
    graph_implicit_types: tuple[str, ...] | None = Field(
        default=None, alias="graphImplicitTypes"
    )
    graph_implicit_types_policy: Literal["fallback", "append"] | None = Field(
        default=None, alias="graphImplicitTypesPolicy"
    )
    graph_include_file_extension: bool | None = Field(
        default=None, alias="graphIncludeFileExtension"
    )
    init_template: str | None = Field(default=None, alias="template")


# ── mcp ──


class McpOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: Literal["stdio"] = Field(default="stdio", alias="mode")
    disk_cache: bool = Field(default=False, alias="cache")


# ── sources: install / update / remove ──


class InstallOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: str | None = Field(default=None, alias="url")


class UpdateOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = Field(default=None, alias="name")
    dry_run: bool = Field(default=False, alias="dryRun")


class RemoveOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(alias="name")


# ── fmt ──


class FmtOptions(FileOptions):
    check: bool = Field(default=False, alias="check")
    verbose: bool = Field(default=False, alias="verbose")


# ── upgrade ──


class UpgradeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    check_only: bool = Field(default=False, alias="check")
    auto_yes: bool = Field(default=False, alias="yes")
    verbose: bool = Field(default=False, alias="verbose")


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
