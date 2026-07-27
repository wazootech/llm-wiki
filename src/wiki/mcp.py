"""Model Context Protocol server for query-first wiki graph access."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from rdflib import RDF, Graph, URIRef

from . import __version__
from .format import detect_query_form, is_sparql_update
from .format_choice import FormatChoice
from .graph import graph_stats
from .wiki import Wiki

QUERY_FORMATS = {"table", "json", "csv", "tsv", "turtle", "n3", "markdown"}
ALLOWED_QUERY_FORMS = {"SELECT", "ASK", "CONSTRUCT", "DESCRIBE"}


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _display_path(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    return _relative_path(path, root)


def _normalize_query_format(output_format: str | None) -> str:
    raw = str(output_format or "json").strip()
    if not raw:
        return "json"
    canonical = FormatChoice.FORMAT_ALIASES.get(raw.casefold(), raw.casefold())
    if canonical not in QUERY_FORMATS:
        raise ValueError(f"Unsupported query result format: {output_format}")
    return canonical


def _namespace_map(graph: Graph) -> dict[str, str]:
    return {prefix: str(namespace) for prefix, namespace in graph.namespaces()}


def _curie(graph: Graph, iri: URIRef) -> str | None:
    normalized = graph.namespace_manager.normalizeUri(iri)
    if normalized.startswith("<") and normalized.endswith(">"):
        return None
    return normalized


def _vocabulary_entry(graph: Graph, iri: URIRef, count: int) -> dict[str, Any]:
    entry: dict[str, Any] = {"iri": str(iri), "count": count}
    compact = _curie(graph, iri)
    if compact is not None:
        entry["curie"] = compact
    return entry


def vocabulary_summary(graph: Graph, *, class_limit: int = 25, predicate_limit: int = 50) -> dict[str, list[dict[str, Any]]]:
    """Return observed classes and predicates to help agents write grounded SPARQL."""
    classes: Counter[URIRef] = Counter()
    predicates: Counter[URIRef] = Counter()

    for _, object_ in graph.subject_objects(RDF.type):
        if isinstance(object_, URIRef):
            classes[object_] += 1
    for predicate in graph.predicates():
        if isinstance(predicate, URIRef):
            predicates[predicate] += 1

    return {
        "classes": [_vocabulary_entry(graph, iri, count) for iri, count in classes.most_common(class_limit)],
        "predicates": [_vocabulary_entry(graph, iri, count) for iri, count in predicates.most_common(predicate_limit)],
    }


def describe_wiki(wiki: Wiki, *, disk_cache: bool = False) -> dict[str, Any]:
    """Return factual graph context for agents writing SPARQL queries."""
    graph = wiki.graph(infer=True, reload=False, disk_cache=disk_cache)
    config = wiki.config
    root = config.config_root
    return {
        "version": __version__,
        "config": _display_path(wiki.config_path, root),
        "inputs": [_relative_path(path, root) for path in config.wiki.inputs],
        "namespaces": _namespace_map(graph),
        "graph": {
            **graph_stats(graph),
            "inference": True,
        },
        "vocabulary": vocabulary_summary(graph),
    }


def query_sparql(
    wiki: Wiki,
    query: str,
    *,
    format: str = "json",
    inference: bool = True,
    reload: bool = False,
    cache: bool = False,
) -> dict[str, str]:
    """Execute an allowlisted SPARQL query against the configured wiki graph."""
    if is_sparql_update(query):
        raise ValueError("SPARQL Update is not supported by wiki mcp.")
    query_form = detect_query_form(query)
    if query_form not in ALLOWED_QUERY_FORMS:
        raise ValueError(f"Unsupported SPARQL query form: {query_form}")
    output_format = _normalize_query_format(format)
    result = wiki.query(
        query,
        format=output_format,
        no_inference=not inference,
        reload=reload,
        cache=cache,
    )
    return {
        "format": output_format,
        "query_form": query_form,
        "result": result,
    }


def info_resource(wiki: Wiki, *, disk_cache: bool = False) -> str:
    """Return wiki info as an application/json resource body."""
    return json.dumps(describe_wiki(wiki, disk_cache=disk_cache), indent=2, sort_keys=True)


def namespaces_resource(wiki: Wiki, *, disk_cache: bool = False) -> str:
    """Return graph namespace bindings as an application/json resource body."""
    graph = wiki.graph(infer=True, reload=False, disk_cache=disk_cache)
    return json.dumps(_namespace_map(graph), indent=2, sort_keys=True)


def graph_ttl_resource(wiki: Wiki, *, disk_cache: bool = False) -> str:
    """Return the inferred graph serialized as Turtle."""
    graph = wiki.graph(infer=True, reload=False, disk_cache=disk_cache)
    return graph.serialize(format="turtle")


def create_mcp_server(wiki: Wiki, *, disk_cache: bool = False):
    """Create the FastMCP server. Imported lazily so tests can avoid protocol startup."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("wiki")

    @server.tool(name="query_sparql", structured_output=True)
    def query_sparql_tool(
        query: str,
        format: str = "json",
        inference: bool = True,
        reload: bool = False,
    ) -> dict[str, str]:
        """Execute SPARQL SELECT, ASK, CONSTRUCT, or DESCRIBE against the wiki graph."""
        return query_sparql(wiki, query, format=format, inference=inference, reload=reload, cache=disk_cache)

    @server.tool(name="describe_wiki", structured_output=True)
    def describe_wiki_tool() -> dict[str, Any]:
        """Return config, namespaces, graph stats, and observed vocabulary."""
        return describe_wiki(wiki, disk_cache=disk_cache)

    @server.resource("wiki://info", mime_type="application/json")
    def wiki_info_resource() -> str:
        """Version, config path, inputs, graph settings, stats, and vocabulary."""
        return info_resource(wiki, disk_cache=disk_cache)

    @server.resource("wiki://namespaces", mime_type="application/json")
    def wiki_namespaces_resource() -> str:
        """Prefix map for SPARQL authoring."""
        return namespaces_resource(wiki, disk_cache=disk_cache)

    @server.resource("wiki://graph.ttl", mime_type="text/turtle")
    def wiki_graph_resource() -> str:
        """Current inferred wiki graph serialized as Turtle."""
        return graph_ttl_resource(wiki, disk_cache=disk_cache)

    return server


def run_mcp_server(wiki: Wiki, *, mode: str = "stdio", disk_cache: bool = False) -> None:
    """Run the MCP server over the requested transport."""
    if mode != "stdio":
        raise ValueError(f"Unsupported MCP mode: {mode}")
    create_mcp_server(wiki, disk_cache=disk_cache).run(transport="stdio")
