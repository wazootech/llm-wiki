"""Wiki fingerprinting and graph caches.

Build the wiki graph once per process and reuse it for every SPARQL query and
render in that process, so OWL-RL expansion and wiki parsing are not repeated
for each block or CLI subcommand. Optional disk warm-start can persist a graph
between one-shot CLI invocations.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from rdflib import Dataset, Graph

from . import __version__
from .config import Config

# In-process graph cache: (wiki_fingerprint, infer) -> graph object
_process_graph_cache: dict[tuple[str, bool, str], Graph | Dataset] = {}


def cache_dir(config: Config) -> Path:
    """Directory for optional on-disk graph cache artifacts."""
    return config.config_root / ".wiki" / "cache"


def _config_fingerprint(config: Config) -> dict[str, Any]:
    namespaces = {
        prefix: str(ns)
        for prefix, ns in sorted(config.context.namespaces.items(), key=lambda item: item[0])
    }
    return {
        "base_iri": config.base_iri,
        "graph_base_iri": config.graph.base_iri,
        "context_wiki": (config.graph.context or {}).get("wiki"),
        "include_file_extension": config.graph.include_file_extension,
        "content_predicate": config.graph.content_predicate,
        "implicit_types": config.graph.implicit_types,
        "implicit_types_policy": config.graph.implicit_types_policy,
        "exclude": sorted(config.wiki.exclude),
        "namespaces": namespaces,
    }


def iter_wiki_files(config: Config) -> list[Path]:
    """All non-excluded files under inputs that contribute to the graph."""
    files: list[Path] = []
    cache_root = cache_dir(config).resolve()
    for input_dir in config.wiki.input:
        if not input_dir.exists():
            continue
        for file_path in sorted(input_dir.rglob("*")):
            if not file_path.is_file() or config.is_excluded(file_path):
                continue
            try:
                if file_path.resolve().is_relative_to(cache_root):
                    continue
            except ValueError:
                continue
            files.append(file_path)
    return files


def wiki_manifest(config: Config) -> dict[str, Any]:
    """Build a stable manifest describing wiki inputs (without infer flag)."""
    entries = []
    for file_path in iter_wiki_files(config):
        stat = file_path.stat()
        entries.append(
            {
                "path": config.relative_to_root(file_path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            }
        )
    return {
        "version": __version__,
        "config": _config_fingerprint(config),
        "files": entries,
    }


def wiki_fingerprint(config: Config) -> str:
    """SHA-256 hex digest of the wiki manifest."""
    payload = json.dumps(wiki_manifest(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_key(config: Config, infer: bool, kind: str = "graph") -> tuple[str, bool, str]:
    return (wiki_fingerprint(config), infer, kind)


def _disk_cache_prefix(infer: bool, kind: str = "graph") -> str:
    prefix = "dataset" if kind == "dataset" else "graph"
    return f"{prefix}-infer" if infer else f"{prefix}-asserted"


def disk_cache_path(config: Config, infer: bool) -> Path:
    """Path to the persisted graph for the current wiki fingerprint."""
    fp = wiki_fingerprint(config)
    return cache_dir(config) / f"{_disk_cache_prefix(infer)}-{fp}.nt"


def dataset_cache_path(config: Config, infer: bool) -> Path:
    """Path to the persisted named-graph dataset for the current wiki fingerprint."""
    fp = wiki_fingerprint(config)
    return cache_dir(config) / f"{_disk_cache_prefix(infer, 'dataset')}-{fp}.nq"


def get_process_graph(config: Config, infer: bool) -> Graph | None:
    """Return the in-memory graph for this wiki fingerprint and infer mode, if loaded."""
    graph = _process_graph_cache.get(_cache_key(config, infer))
    return graph if isinstance(graph, Graph) and not isinstance(graph, Dataset) else None


def get_process_dataset(config: Config, infer: bool) -> Dataset | None:
    """Return the in-memory dataset for this wiki fingerprint and infer mode, if loaded."""
    graph = _process_graph_cache.get(_cache_key(config, infer, "dataset"))
    return graph if isinstance(graph, Dataset) else None


def get_disk_graph(config: Config, infer: bool) -> Graph | None:
    """Return a persisted graph for this wiki fingerprint and infer mode, if present."""
    cache_path = disk_cache_path(config, infer)
    if not cache_path.exists():
        return None
    try:
        graph = Graph()
        graph.parse(cache_path, format="nt")
        return graph
    except Exception:
        try:
            cache_path.unlink()
        except OSError:
            pass
        return None


def get_disk_dataset(config: Config, infer: bool) -> Dataset | None:
    """Return a persisted named-graph dataset for this wiki fingerprint, if present."""
    cache_path = dataset_cache_path(config, infer)
    if not cache_path.exists():
        return None
    try:
        dataset = Dataset(default_union=True)
        dataset.parse(cache_path, format="nquads")
        return dataset
    except Exception:
        try:
            cache_path.unlink()
        except OSError:
            pass
        return None


def set_process_graph(config: Config, infer: bool, graph: Graph) -> None:
    """Store a graph in the in-process cache, dropping stale entries for the same infer mode."""
    fp = wiki_fingerprint(config)
    stale_keys = [key for key in _process_graph_cache if key[1] == infer and key[2] == "graph" and key[0] != fp]
    for key in stale_keys:
        del _process_graph_cache[key]
    _process_graph_cache[(fp, infer, "graph")] = graph


def set_process_dataset(config: Config, infer: bool, dataset: Dataset) -> None:
    """Store a dataset in the in-process cache, dropping stale dataset entries."""
    fp = wiki_fingerprint(config)
    stale_keys = [key for key in _process_graph_cache if key[1] == infer and key[2] == "dataset" and key[0] != fp]
    for key in stale_keys:
        del _process_graph_cache[key]
    _process_graph_cache[(fp, infer, "dataset")] = dataset


def set_disk_graph(config: Config, infer: bool, graph: Graph) -> None:
    """Persist a graph for reuse across one-shot CLI invocations."""
    root = cache_dir(config)
    root.mkdir(parents=True, exist_ok=True)
    cache_path = disk_cache_path(config, infer)
    for stale in root.glob(f"{_disk_cache_prefix(infer)}-*.nt"):
        if stale != cache_path:
            try:
                stale.unlink()
            except OSError:
                pass
    cache_path.write_text(graph.serialize(format="nt"), encoding="utf-8")


def set_disk_dataset(config: Config, infer: bool, dataset: Dataset) -> None:
    """Persist a named-graph dataset for reuse across one-shot CLI invocations."""
    root = cache_dir(config)
    root.mkdir(parents=True, exist_ok=True)
    cache_path = dataset_cache_path(config, infer)
    for stale in root.glob(f"{_disk_cache_prefix(infer, 'dataset')}-*.nq"):
        if stale != cache_path:
            try:
                stale.unlink()
            except OSError:
                pass
    cache_path.write_text(dataset.serialize(format="nquads"), encoding="utf-8")


def clear_process_graph(config: Config, infer: bool) -> None:
    """Drop the in-process graph entry for the current wiki fingerprint."""
    _process_graph_cache.pop(_cache_key(config, infer), None)


def clear_process_dataset(config: Config, infer: bool) -> None:
    """Drop the in-process dataset entry for the current wiki fingerprint."""
    _process_graph_cache.pop(_cache_key(config, infer, "dataset"), None)


def clear_disk_graph(config: Config, infer: bool) -> None:
    """Drop the persisted graph entry for the current wiki fingerprint."""
    try:
        disk_cache_path(config, infer).unlink()
    except OSError:
        pass


def clear_disk_dataset(config: Config, infer: bool) -> None:
    """Drop the persisted dataset entry for the current wiki fingerprint."""
    try:
        dataset_cache_path(config, infer).unlink()
    except OSError:
        pass


def clear_all_process_graphs() -> None:
    """Clear the entire in-process graph cache (tests and watch reload)."""
    _process_graph_cache.clear()
