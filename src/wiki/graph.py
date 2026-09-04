"""RDF Lib graph loading, frontmatter-to-triple conversion, and blank node resolution."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from linked_markdown import LinkedMarkdownError, extract
from rdflib import RDF, BNode, Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD

from .config import Config, Context
from .parser import document_data_from_path
from .paths import iter_document_files, route_for_document_file
from .schemas.sources import GraphDescriptor, Lockfile, SourceConfig
from .sources import _source_cache_dir, _source_resolved_path

logger = logging.getLogger(__name__)


def uses_named_graphs(sparql_query: str) -> bool:
    """Return true when a SPARQL query uses an explicit GRAPH clause."""
    return re.search(r"(?<![?$A-Za-z0-9_:-])GRAPH\s+", sparql_query, flags=re.IGNORECASE) is not None


def load_query_graph(
    config: Config,
    sparql_query: str,
    *,
    infer: bool = True,
    reload: bool = False,
    disk_cache: bool = False,
) -> Graph | Dataset:
    """Load the right RDF query target for plain or named-graph SPARQL."""
    if uses_named_graphs(sparql_query):
        return load_dataset(config, infer=infer, reload=reload, disk_cache=disk_cache)
    return load_graph(config, infer=infer, reload=reload, disk_cache=disk_cache)


def _graph_base(config: Config) -> str:
    return str(config.context.namespaces.get("wiki") or config.base_iri).rstrip("/")


def root_graph_uri(config: Config) -> str:
    """Stable named graph URI for the root wiki corpus."""
    return f"{_graph_base(config)}/graphs/root"


def source_graph_uri(config: Config, source_name: str) -> str:
    """Stable named graph URI for an installed source."""
    from urllib.parse import quote

    return f"{_graph_base(config)}/graphs/source/{quote(source_name, safe='')}"


def graph_descriptors(config: Config) -> list[GraphDescriptor]:
    """Describe root and installed source graphs without mutating source state."""
    lockfile = Lockfile.load(config.config_root / "wiki.lock")
    cache_root = config.config_root / ".wiki" / "sources"
    if not lockfile.sources and cache_root.exists() and any(cache_root.iterdir()):
        logger.warning(
            "Source cache exists under %s but wiki.lock has no sources; source graph provenance is unavailable.",
            cache_root,
        )
    source_paths: dict[Path, GraphDescriptor] = {}

    direct_source_names = {source.name for source in config.sources}
    for name, locked in lockfile.sources.items():
        required_by = list(locked.required_by)
        if not required_by and name in direct_source_names:
            required_by = ["root"]
        repo_dir = _source_cache_dir(config, name) / "repo"
        if not repo_dir.exists():
            continue
        source = SourceConfig(
            name=name,
            type="git",
            url=locked.url,
            ref=locked.ref,
            path=locked.path,
        )
        try:
            local_path = _source_resolved_path(source, repo_dir)
        except RuntimeError:
            continue
        source_paths[local_path.resolve()] = GraphDescriptor(
            name=name,
            uri=source_graph_uri(config, name),
            kind="source",
            source_name=name,
            source_type="git",
            url=locked.url,
            ref=locked.ref,
            resolved_ref=locked.resolved_ref,
            path=locked.path,
            local_path=local_path,
            required_by=required_by,
        )

    root_inputs = []
    source_descriptors = []
    for input_dir in config.wiki.input:
        resolved = input_dir.resolve()
        descriptor = source_paths.get(resolved)
        if descriptor is None:
            root_inputs.append(input_dir)
        elif descriptor not in source_descriptors:
            source_descriptors.append(descriptor)

    root = GraphDescriptor(
        name="root",
        uri=root_graph_uri(config),
        kind="root",
        local_path=config.config_root,
        path=", ".join(config.relative_to_root(path) for path in root_inputs) or None,
        required_by=[],
    )
    return [root, *source_descriptors]


def kebab_case(s: str) -> str:
    """Convert a string to kebab-case for URI segments."""
    s = str(s).lower().strip()
    s = re.sub(r"[\s\-]+", "-", s)
    s = re.sub(r"[^a-z0-9\-]", "", s)
    return s


def _slugify_path(p: Path) -> str:
    """Compute a stable nested slug (posix, no extension) for wiki files."""
    return p.with_suffix("").as_posix().strip("/")


def _file_slug(file_path: Path, input_dirs: list[Path]) -> str:
    for root in input_dirs:
        try:
            rel = file_path.relative_to(root)
            return _slugify_path(rel)
        except ValueError:
            continue
    return _slugify_path(file_path)


def resolve_predicate(key: str, context: Context) -> URIRef | None:
    """Map a frontmatter key to an RDF predicate URI using managed namespaces.

    Resolution order: CURIE (prefix:localName) → wiki.* dotted keys → vocab: default.
    """
    if ":" in key:
        prefix, name = key.split(":", 1)
        if prefix in context.namespaces:
            return context.namespaces[prefix][name]
    if key.startswith("wiki."):
        return context.namespaces["wiki"][key[5:]]
    if context.vocab:
        return URIRef(f"{str(context.vocab)}{key}")
    return None


def resolve_type(t: Any, context: Context) -> URIRef | None:
    """Map a frontmatter type to an RDF type URI using managed namespaces."""
    if isinstance(t, str):
        if ":" in t:
            prefix, name = t.split(":", 1)
            if prefix in context.namespaces:
                return context.namespaces[prefix][name]
        if context.vocab:
            return URIRef(f"{str(context.vocab)}{t}")
        return None
    return URIRef(str(t))


def resolve_object(key: str, value: Any, graph: Graph, subject: URIRef, context: Context) -> None:
    """Add a predicate-object pair to the graph, recursively handling nested structures."""
    pred = resolve_predicate(key, context)
    if pred is None:
        return

    if isinstance(value, dict):
        if "@id" in value:
            uri = value["@id"]
            if ":" in uri:
                prefix, name = uri.split(":", 1)
                if prefix in context.namespaces:
                    uri = str(context.namespaces[prefix][name])
            graph.add((subject, pred, URIRef(uri)))
        elif "@type" in value:
            blank = BNode()
            graph.add((subject, pred, blank))
            resolved_type = resolve_type(value["@type"], context)
            if resolved_type:
                graph.add((blank, RDF.type, resolved_type))
            for k, v in value.items():
                if not k.startswith("@"):
                    resolve_object(k, v, graph, blank, context)
        else:
            blank = BNode()
            graph.add((subject, pred, blank))
            for k, v in value.items():
                if not k.startswith("@"):
                    resolve_object(k, v, graph, blank, context)
    elif isinstance(value, str):
        if value.startswith("http"):
            graph.add((subject, pred, URIRef(value)))
        elif ":" in value and " " not in value and "\n" not in value:
            prefix, name = value.split(":", 1)
            if prefix in context.namespaces:
                graph.add((subject, pred, URIRef(context.namespaces[prefix][name])))
            else:
                graph.add((subject, pred, Literal(value)))
        else:
            graph.add((subject, pred, Literal(value)))
    elif isinstance(value, bool):
        graph.add((subject, pred, Literal(value, datatype=XSD.boolean)))
    elif isinstance(value, (int, float)):
        graph.add((subject, pred, Literal(value)))
    elif hasattr(value, "hour"):
        graph.add((subject, pred, Literal(value, datatype=XSD.dateTime)))
    elif hasattr(value, "isoformat") and hasattr(value, "year"):
        graph.add((subject, pred, Literal(value, datatype=XSD.date)))
    elif value is not None:
        graph.add((subject, pred, Literal(str(value))))


def _rdf_binding(ctx: Context | Config) -> tuple[Context, str | None]:
    if isinstance(ctx, Config):
        return ctx.context, ctx.graph.content_predicate
    return ctx, getattr(ctx, "content_predicate", None)


def _normalize_type_list(raw: Any) -> list[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    return [raw]


def _is_shacl_shape_document(fm_types: list[Any]) -> bool:
    for item in fm_types:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized in {"sh:NodeShape", "sh:PropertyShape", "NodeShape", "PropertyShape"}:
            return True
        if ":" in normalized:
            prefix, local = normalized.split(":", 1)
            if prefix == "sh" and local in {"NodeShape", "PropertyShape"}:
                return True
    return False


def _effective_types(data: dict[str, Any], context: Context | Config) -> list[Any]:
    """Merge frontmatter type with graph.implicit_types per implicit_types_policy."""
    fm_types = _normalize_type_list(data.get("@type") or data.get("type"))

    implicit_types: list[str] = []
    policy = "fallback"
    if isinstance(context, Config):
        implicit_types = list(context.graph.implicit_types)
        policy = context.graph.implicit_types_policy

    if not implicit_types:
        return fm_types
    if not fm_types:
        return list(implicit_types)
    if policy == "fallback":
        return fm_types
    if _is_shacl_shape_document(fm_types):
        return fm_types

    rdf_ctx = context if isinstance(context, Context) else context.context
    seen: set[str] = set()
    merged: list[Any] = []
    for item in fm_types + implicit_types:
        res = resolve_type(item, rdf_ctx)
        if res is None:
            continue
        resolved = str(res)
        if resolved in seen:
            continue
        seen.add(resolved)
        merged.append(item)
    return merged


def frontmatter_to_graph(
    data: dict[str, Any],
    context: Context | Config,
    file_id: str | None = None,
    body: str | None = None,
    include_file_extension: bool = False,
    file_ext: str = ".md",
    content_predicate: str | None = None,
) -> Graph:
    """Convert parsed frontmatter dictionary to an RDF graph."""
    rdf_ctx, default_predicate = _rdf_binding(context)
    if content_predicate is None:
        content_predicate = default_predicate
    graph = Graph()
    rdf_ctx.bind_namespaces(graph)
    graph._vocab = rdf_ctx.vocab

    effective_types = _effective_types(data, context)
    if not data or not effective_types:
        return graph

    doc_id = data.get("@id") or data.get("id")
    if not doc_id:
        if not file_id:
            return Graph()
        suffix = file_ext if include_file_extension else ""
        doc_id = f"{rdf_ctx.base_iri}{file_id}{suffix}"

    if doc_id and ":" in doc_id:
        prefix, name = doc_id.split(":", 1)
        if prefix in rdf_ctx.namespaces:
            doc_id = str(rdf_ctx.namespaces[prefix][name])

    subject = URIRef(doc_id)

    for t in effective_types:
        resolved_t = resolve_type(t, rdf_ctx)
        if resolved_t:
            graph.add((subject, RDF.type, resolved_t))

    skip_keys = {"id", "type", "@type"}
    for key, value in data.items():
        if key.startswith("@") or key in skip_keys:
            continue
        if isinstance(value, list):
            for item in value:
                resolve_object(key, item, graph, subject, rdf_ctx)
        elif value:
            resolve_object(key, value, graph, subject, rdf_ctx)

    if body and content_predicate:
        resolve_object(content_predicate, body, graph, subject, rdf_ctx)

    return graph


def _process_document_file(graph: Graph, file_path: Path, context: Config) -> None:
    """Parse a supported wiki document into the graph."""
    data = document_data_from_path(file_path)
    if data:
        body = None
        if file_path.suffix.lower() == ".md" and context.graph.content_predicate:
            content = file_path.read_text(encoding="utf-8")
            try:
                body = extract(content).body.strip()
            except LinkedMarkdownError:
                pass
        file_id = route_for_document_file(context, file_path)
        graph += frontmatter_to_graph(
            data,
            context,
            file_id=file_id,
            body=body,
            include_file_extension=context.graph.include_file_extension,
            file_ext=file_path.suffix.lower(),
        )

    if file_path.suffix.lower() != ".md":
        return

    content = file_path.read_text(encoding="utf-8")

    turtle_blocks = re.findall(r"```turtle\s*([\s\S]*?)```", content)
    for block in turtle_blocks:
        try:
            graph.parse(data=block.strip(), format="turtle")
        except Exception as e:
            logger.warning("Failed to parse turtle block in %s: %s", file_path.name, e)


# Map file extensions to rdflib format names
_EXT_FORMAT_MAP = {
    ".ttl": "turtle",
    ".trig": "trig",
    ".nt": "nt",
    ".nq": "nquads",
    ".rdf": "xml",
    ".xml": "xml",
    ".jsonld": "json-ld",
}


def _process_input_dir(graph: Graph, context: Config, input_dir: Path, document_files: set[Path]) -> None:
    if not input_dir.exists():
        return
    for file_path in sorted(input_dir.rglob("*")):
        if not file_path.is_file() or context.is_excluded(file_path):
            continue
        try:
            if file_path in document_files:
                _process_document_file(graph, file_path, context)
            else:
                fmt = _EXT_FORMAT_MAP.get(file_path.suffix.lower())
                if fmt:
                    graph.parse(file_path, format=fmt)
        except Exception as e:
            logger.warning("Failed to process %s: %s", file_path.name, e)


def _build_graph_from_wiki(context: Config) -> Graph:
    """Load asserted triples from all wiki sources without OWL-RL inference."""
    graph = Graph()
    context.bind_namespaces(graph)
    graph._vocab = context.context.vocab

    document_files = set(iter_document_files(context))

    for input_dir in context.wiki.input:
        _process_input_dir(graph, context, input_dir, document_files)

    return graph


def load_dataset(
    context: Config,
    infer: bool = True,
    *,
    use_cache: bool = True,
    reload: bool = False,
    disk_cache: bool = False,
) -> Dataset:
    """Load wiki sources into a read-only Dataset with stable named graphs.

    The dataset uses ``default_union=True`` so unscoped SPARQL queries preserve
    the existing umbrella/union behavior while ``GRAPH`` clauses can inspect
    source boundaries.
    """
    from .graph_cache import (
        clear_disk_dataset,
        clear_process_dataset,
        get_disk_dataset,
        get_process_dataset,
        set_disk_dataset,
        set_process_dataset,
    )

    if reload:
        clear_process_dataset(context, infer)
        if disk_cache:
            clear_disk_dataset(context, infer)
    elif use_cache:
        cached = get_process_dataset(context, infer)
        if cached is not None:
            return cached
        if disk_cache:
            cached_disk = get_disk_dataset(context, infer)
            if cached_disk is not None:
                set_process_dataset(context, infer, cached_disk)
                return cached_disk

    dataset = Dataset(default_union=True)
    context.bind_namespaces(dataset)
    dataset._vocab = context.context.vocab
    document_files = set(iter_document_files(context))
    descriptors = graph_descriptors(context)
    source_by_path = {
        descriptor.local_path.resolve(): descriptor
        for descriptor in descriptors
        if descriptor.kind == "source" and descriptor.local_path is not None
    }
    root_descriptor = descriptors[0]

    for input_dir in context.wiki.input:
        resolved = input_dir.resolve()
        descriptor = source_by_path.get(resolved, root_descriptor)
        graph = dataset.graph(URIRef(descriptor.uri))
        context.bind_namespaces(graph)
        graph._vocab = context.context.vocab
        _process_input_dir(graph, context, input_dir, document_files)

    if infer:
        from .infer import apply_inference
        for graph in dataset.graphs():
            apply_inference(graph, context)

    if use_cache:
        set_process_dataset(context, infer, dataset)
    if disk_cache:
        set_disk_dataset(context, infer, dataset)

    return dataset


def load_graph(
    context: Config,
    infer: bool = True,
    *,
    use_cache: bool = True,
    reload: bool = False,
    disk_cache: bool = False,
) -> Graph:
    """Load wiki sources into a Graph, reusing the in-process cache when possible.

    Multiple calls in the same process (many SPARQL blocks, query + render, SHACL
    checks, serve requests) share one graph build unless ``reload`` is set.
    """
    from .graph_cache import (
        clear_disk_graph,
        clear_process_graph,
        get_disk_graph,
        get_process_graph,
        set_disk_graph,
        set_process_graph,
    )

    if reload:
        clear_process_graph(context, infer)
        if disk_cache:
            clear_disk_graph(context, infer)
    elif use_cache:
        cached = get_process_graph(context, infer)
        if cached is not None:
            return cached
        if disk_cache:
            cached_disk = get_disk_graph(context, infer)
            if cached_disk is not None:
                set_process_graph(context, infer, cached_disk)
                return cached_disk

    graph = _build_graph_from_wiki(context)
    if infer:
        from .infer import apply_inference
        apply_inference(graph, context)

    if use_cache:
        set_process_graph(context, infer, graph)
    if disk_cache:
        set_disk_graph(context, infer, graph)

    return graph


def graph_stats(graph: Graph | Dataset) -> dict[str, int]:
    """Return basic statistics about the loaded graph."""
    return {
        "triples": len(graph),
        "subjects": len(set(graph.subjects())),
        "predicates": len(set(graph.predicates())),
        "objects": len(set(graph.objects())),
    }
