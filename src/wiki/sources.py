"""External source resolution and lockfile management.

The config file declares desired sources; wiki.lock records the exact resolved
state. ``wiki install`` fetches and locks; ``wiki remove`` deletes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
import tomllib
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from .config import CONFIG_FILENAMES, Config
from .schemas.sources import LOCKFILE_FILENAME, LockedSource, Lockfile, SourceConfig

logger = logging.getLogger(__name__)

_yaml = YAML()
_yaml.indent(mapping=2, sequence=4, offset=2)

_OWNER_REPO_SHORTHAND = re.compile(
    r"^(?P<owner>[a-zA-Z0-9._-]+)/(?P<repo>[a-zA-Z0-9._-]+?)(?:\.git)?$"
)


def _expand_source_url(url: str) -> str:
    """Expand ``owner/repo`` shorthand to ``https://github.com/owner/repo.git``.

    Full URLs (HTTPS, SSH) and non-GitHub URLs pass through unchanged.
    """
    match = _OWNER_REPO_SHORTHAND.match(url)
    if match:
        return f"https://github.com/{match.group('owner')}/{match.group('repo')}.git"
    return url


def _lockfile_path(config: Config) -> Path:
    return config.config_root / LOCKFILE_FILENAME


def _source_cache_dir(config: Config, source_name: str) -> Path:
    return config.config_root / ".wiki" / "sources" / source_name


def _config_path(config: Config) -> Path:
    for name in CONFIG_FILENAMES:
        candidate = config.config_root / name
        if candidate.exists():
            return candidate
    return config.config_root / "wiki.yml"


def _load_data_file(path: Path) -> dict[str, Any]:
    """Load a YAML, JSON, or TOML file and return the parsed dict."""
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(raw)
    elif suffix == ".toml":
        data = tomllib.loads(raw)
    else:
        data = _yaml.load(raw)
    if not isinstance(data, dict):
        raise RuntimeError(f"{path.name}: top-level content must be a mapping")
    return data


def _load_lockfile(config: Config) -> Lockfile:
    return Lockfile.load(_lockfile_path(config))


def _save_lockfile(config: Config, lockfile: Lockfile) -> None:
    lockfile.save(_lockfile_path(config))


def _is_full_sha(ref: str) -> bool:
    """Return True if *ref* looks like a full 40-character commit SHA."""
    return bool(re.fullmatch(r"[0-9a-f]{40}", ref))


def _git_resolve_ref(ref: str, repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", ref],
        capture_output=True,
        text=True,
        cwd=repo_dir,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to resolve git ref {ref!r}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_clone_or_fetch(source: SourceConfig, cache_dir: Path) -> Path:
    repo_dir = cache_dir / "repo"
    if repo_dir.exists():
        url_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if url_result.returncode == 0 and url_result.stdout.strip() != source.url:
            subprocess.run(
                ["git", "remote", "set-url", "origin", source.url],
                capture_output=True,
                text=True,
                cwd=repo_dir,
                check=True,
            )
            logger.info(
                "Updated remote URL for source from %s to %s",
                url_result.stdout.strip(),
                source.url,
            )

        # The cache repo may have a local branch checked out (the default
        # branch from the initial clone). Fetching into refs/heads/* is
        # refused by git when it would update the currently checked-out
        # branch, so detach HEAD first; _git_prepare_ref re-attaches and
        # re-checks-out the working tree afterward.
        detach = subprocess.run(
            ["git", "checkout", "--detach"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if detach.returncode != 0:
            raise RuntimeError(
                f"Failed to prepare {source.url}: {detach.stderr.strip()}"
            )

        result = subprocess.run(
            ["git", "fetch", "--tags", "--force", "origin", "+refs/heads/*:refs/heads/*"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to fetch {source.url}: {result.stderr.strip()}"
            )

        # Pinned commit SHAs may not be reachable in a shallow repo —
        # unshallow so the checkout in _git_prepare_ref can find them.
        if source.ref and _is_full_sha(source.ref):
            shallow_check = subprocess.run(
                ["git", "rev-parse", "--is-shallow-repository"],
                capture_output=True,
                text=True,
                cwd=repo_dir,
            )
            if shallow_check.stdout.strip() == "true":
                subprocess.run(
                    ["git", "fetch", "--unshallow", "origin"],
                    capture_output=True,
                    text=True,
                    cwd=repo_dir,
                    check=True,
                )
    else:
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Full clone for pinned commit SHAs; shallow is fine for branch/tag refs
        depth_args = [] if (source.ref and _is_full_sha(source.ref)) else ["--depth", "1"]
        result = subprocess.run(
            ["git", "clone", *depth_args, source.url, str(repo_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(cache_dir, ignore_errors=True)
            raise RuntimeError(
                f"Failed to clone {source.url}: {result.stderr.strip()}"
            )
    return repo_dir


def _git_prepare_ref(source: SourceConfig, repo_dir: Path) -> None:
    """After fetch, ensure the repo is checked out at the right ref.

    For pinned refs (branch, tag, or commit), checks out that ref.
    For unpinned sources (no ref), gets on a local branch if detached
    HEAD (handles switching from a pinned tag to an unpinned default).
    """
    ref = source.ref
    if ref is not None:
        subprocess.run(
            ["git", "checkout", ref, "--"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
            check=True,
        )
    else:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
        )
        if branch_result.stdout.strip() == "HEAD":
            sym_result = subprocess.run(
                ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                capture_output=True,
                text=True,
                cwd=repo_dir,
            )
            if sym_result.returncode == 0:
                default_branch = sym_result.stdout.strip().removeprefix("refs/remotes/origin/")
                subprocess.run(
                    ["git", "checkout", default_branch, "--"],
                    capture_output=True,
                    text=True,
                    cwd=repo_dir,
                    check=True,
                )
            else:
                branch_r_result = subprocess.run(
                    ["git", "branch", "-r"],
                    capture_output=True,
                    text=True,
                    cwd=repo_dir,
                )
                if branch_r_result.returncode == 0:
                    refs = [
                        b.strip().removeprefix("origin/")
                        for b in branch_r_result.stdout.strip().splitlines()
                        if b.strip().startswith("origin/")
                    ]
                    preferred = None
                    for candidate in ("main", "master"):
                        if candidate in refs:
                            preferred = candidate
                            break
                    default_branch = preferred or (refs[0] if refs else None)
                    if default_branch:
                        subprocess.run(
                            ["git", "checkout", default_branch, "--"],
                            capture_output=True,
                            text=True,
                            cwd=repo_dir,
                            check=True,
                        )


def _source_resolved_path(source: SourceConfig, repo_dir: Path) -> Path:
    base = repo_dir / source.path if source.path else repo_dir
    if not base.exists():
        raise RuntimeError(
            f"Source {source.name!r}: path {source.path!r} does not exist"
        )
    return base.resolve()


def _infer_name_from_url(url: str) -> str:
    stem = url.rstrip("/").rsplit("/", 1)[-1]
    stem = re.sub(r"(\.wiki|\.git)$", "", stem, flags=re.IGNORECASE)
    return stem or "source"


def _parse_url_ref(url: str) -> tuple[str, str | None]:
    if "#" in url:
        url, ref = url.rsplit("#", 1)
        return url, ref or None
    return url, None


def _yaml_dump(data: object) -> str:
    buf = StringIO()
    _yaml.dump(data, buf)
    return buf.getvalue().rstrip() + "\n"


def _add_to_wiki_yml(config: Config, source: SourceConfig) -> None:
    config_path = _config_path(config)
    if config_path.suffix.lower() == ".toml":
        raise RuntimeError(
            "Source management requires a YAML config file. "
            "Edit wiki.toml manually or use wiki.yml for source management."
        )
    if not config_path.exists():
        raise RuntimeError("No wiki config file found")

    raw = config_path.read_text(encoding="utf-8")
    data = _yaml.load(raw) or {}

    sources = data.get("sources")
    if sources is None:
        sources = []
        data["sources"] = sources

    if not isinstance(sources, list):
        raise RuntimeError("sources must be a list in the config file")

    for existing in sources:
        if isinstance(existing, dict) and existing.get("name") == source.name:
            raise RuntimeError(f"Source {source.name!r} already exists in the config file")

    entry: dict[str, Any] = {"name": source.name, "type": "git", "url": source.url}
    if source.ref:
        entry["ref"] = source.ref
    if source.path:
        entry["path"] = source.path
    sources.append(entry)

    config_path.write_text(_yaml_dump(data), encoding="utf-8")


def _remove_from_wiki_yml(config: Config, name: str) -> None:
    config_path = _config_path(config)
    if config_path.suffix.lower() == ".toml":
        raise RuntimeError(
            "Source management requires a YAML config file. "
            "Edit wiki.toml manually or use wiki.yml for source management."
        )
    if not config_path.exists():
        return

    raw = config_path.read_text(encoding="utf-8")
    data = _yaml.load(raw) or {}

    sources = data.get("sources")
    if not isinstance(sources, list):
        return

    new_sources = [s for s in sources if not (isinstance(s, dict) and s.get("name") == name)]
    if len(new_sources) == len(sources):
        raise RuntimeError(f"Source {name!r} not found in config file")

    if new_sources:
        data["sources"] = new_sources
    else:
        del data["sources"]

    config_path.write_text(_yaml_dump(data), encoding="utf-8")


def _discover_sources(repo_dir: Path) -> list[SourceConfig]:
    """Read the config file from a cloned source repo to discover its
    declared transitive dependencies.

    Only the ``sources:`` block is read — graph, check, and lint config
    from transitive deps are not merged.  Returns ``[]`` when no config
    file or no ``sources:`` block exists (leaf source).
    """
    for name in CONFIG_FILENAMES:
        config_file = repo_dir / name
        if config_file.exists():
            try:
                data = _load_data_file(config_file)
                if isinstance(data, dict) and isinstance(data.get("sources"), list):
                    result: list[SourceConfig] = []
                    for s in data["sources"]:
                        try:
                            result.append(SourceConfig(**s))
                        except Exception as exc:
                            logger.warning(
                                "Skipping invalid source entry in %s: %s",
                                config_file,
                                exc,
                            )
                    return result
            except Exception as exc:
                logger.warning(
                    "Failed to read sources from %s: %s", config_file, exc
                )
            break  # found a config file, even if malformed
    return []


def _install_tree(
    config: Config,
    sources: list[SourceConfig],
    lockfile: Lockfile,
    *,
    parent: str | None,
    visited: set[str],
    path: list[str],
) -> None:
    """Recursive dependency-tree walker.

    * ``parent`` — name of the source that declared these deps, or
      ``None`` for top-level entries.
    * ``visited`` — set of already-processed source names (shared
      across the whole install run).
    * ``path`` — ancestor chain for cycle detection.
    """
    for source in sources:
        # ---- cycle detection ---------------------------------------------------
        if source.name in path:
            cycle = " -> ".join(path + [source.name])
            raise RuntimeError(f"Circular dependency detected: {cycle}")

        # ---- deduplication / conflict check ------------------------------------
        if source.name in visited:
            existing = lockfile.sources[source.name]
            if existing.url != source.url or existing.ref != source.ref:
                raise RuntimeError(
                    f"Source {source.name!r} conflict: "
                    f"already locked as {existing.url}@{existing.ref or 'HEAD'}, "
                    f"but {parent or 'root'} declares "
                    f"{source.url}@{source.ref or 'HEAD'}"
                )
            if parent is not None and parent not in existing.required_by:
                existing.required_by.append(parent)
            continue

        visited.add(source.name)

        # ---- clone / fetch / checkout ------------------------------------------
        logger.info("Installing source %r from %s", source.name, source.url)
        cache_dir = _source_cache_dir(config, source.name)
        repo_dir = _git_clone_or_fetch(source, cache_dir)
        _git_prepare_ref(source, repo_dir)

        resolved_ref = _git_resolve_ref("HEAD", repo_dir)
        resolved_path = _source_resolved_path(source, repo_dir)

        lockfile.sources[source.name] = LockedSource(
            url=source.url,
            resolved_ref=resolved_ref,
            ref=source.ref,
            path=source.path,
            fetched_at=Lockfile.timestamp(),
            required_by=[parent] if parent is not None else [],
        )
        logger.info(
            "Locked source %r at %s -> %s",
            source.name,
            resolved_ref[:12],
            resolved_path,
        )

        # ---- recurse into transitive dependencies ------------------------------
        transitive = _discover_sources(repo_dir)
        if transitive:
            _install_tree(
                config,
                transitive,
                lockfile,
                parent=source.name,
                visited=visited,
                path=path + [source.name],
            )


def install(config: Config, url: str | None = None) -> Lockfile:
    """Fetch and lock sources.

    With no url, fetches all sources declared in the config and updates wiki.lock.
    With a url, adds a new source to the config file, fetches it, and updates
    wiki.lock.

    Transitive dependencies are resolved recursively: each source's own
    config file is checked for a ``sources:`` block, and those sources
    are fetched and locked too.  Circular dependency chains are detected
    and raise ``RuntimeError``.

    Returns the updated Lockfile.
    """
    if url:
        clean_url, ref = _parse_url_ref(url)
        clean_url = _expand_source_url(clean_url)
        name = _infer_name_from_url(clean_url)
        source = SourceConfig(name=name, type="git", url=clean_url, ref=ref)
        _add_to_wiki_yml(config, source)
        config.sources = list(config.sources) + [source]
    elif not config.sources:
        logger.info("No sources declared in config file.")
        return Lockfile()

    lockfile = _load_lockfile(config)
    visited: set[str] = set(lockfile.sources.keys())

    _install_tree(
        config,
        config.sources,
        lockfile,
        parent=None,
        visited=visited,
        path=[],
    )

    _save_lockfile(config, lockfile)
    return lockfile


@dataclass
class SourceUpdate:
    """Result of checking a single source for updates."""

    name: str
    url: str
    previous_ref: str
    current_ref: str
    updated: bool


@dataclass
class UpdateResult:
    """Aggregate result of ``update()``."""

    updates: list[SourceUpdate] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.updates)

    @property
    def changed(self) -> list[SourceUpdate]:
        return [u for u in self.updates if u.updated]


def _report_orphans(config: Config, lockfile: Lockfile) -> None:
    """Warn about transitive sources that are no longer declared by any
    parent but still exist in the lockfile.

    This is a read-only diagnostic — no lockfile or cache changes are
    made.  Users should run ``wiki remove <name>`` to clean up orphans.
    """
    remaining_top_level = {s.name for s in config.sources}

    for name, entry in lockfile.sources.items():
        if name not in remaining_top_level and entry.required_by:
            logger.warning(
                "Source %r (required_by=%r) may be orphaned. "
                "Run 'wiki remove %s' to clean up.",
                name,
                entry.required_by,
                name,
            )


def update(
    config: Config,
    name: str | None = None,
    *,
    dry_run: bool = False,
) -> UpdateResult:
    """Check locked sources for newer commits.

    Fetches each source's remote, resolves the current HEAD (or pinned ref),
    and compares against the locked SHA. With ``dry_run=True``, reports
    what would change without modifying wiki.lock.

    After updating commits, transitive dependencies are re-synced:
    newly-declared sources are installed; orphaned sources are reported
    (not auto-removed).

    Returns an ``UpdateResult`` with per-source ``SourceUpdate`` entries.
    """
    lockfile = _load_lockfile(config)
    result = UpdateResult()

    sources = [s for s in config.sources if name is None or s.name == name]
    if not sources:
        if name:
            logger.warning("Source %r not found in config file.", name)
        return result

    for source in sources:
        locked = lockfile.sources.get(source.name)
        if locked is None:
            logger.warning(
                "Source %r is not locked. Run 'wiki install' first.",
                source.name,
            )
            continue

        cache_dir = _source_cache_dir(config, source.name)
        repo_dir = _git_clone_or_fetch(source, cache_dir)
        _git_prepare_ref(source, repo_dir)

        current_ref = _git_resolve_ref("HEAD", repo_dir)
        previous_ref = locked.resolved_ref
        updated = current_ref != previous_ref

        if updated and not dry_run:
            lockfile.sources[source.name] = LockedSource(
                url=source.url,
                resolved_ref=current_ref,
                ref=source.ref,
                path=source.path,
                fetched_at=Lockfile.timestamp(),
                required_by=locked.required_by,
            )

        result.updates.append(SourceUpdate(
            name=source.name,
            url=source.url,
            previous_ref=previous_ref[:12] if previous_ref else "",
            current_ref=current_ref[:12],
            updated=updated,
        ))

    if not dry_run:
        if result.changed:
            _save_lockfile(config, lockfile)

        # ---- re-sync transitive dependency tree --------------------------------
        visited: set[str] = set(lockfile.sources.keys())
        for source in config.sources:
            repo_dir = _source_cache_dir(config, source.name) / "repo"
            if repo_dir.exists():
                transitive = _discover_sources(repo_dir)
                if transitive:
                    _install_tree(
                        config,
                        transitive,
                        lockfile,
                        parent=source.name,
                        visited=visited,
                        path=[],
                    )
        if visited != set(lockfile.sources.keys()):
            _save_lockfile(config, lockfile)

        _report_orphans(config, lockfile)

    return result


def _rmtree_force(path: Path) -> None:
    """Remove a directory tree, clearing the read-only attribute as needed.

    Git object files are created read-only, and ``shutil.rmtree`` cannot
    delete read-only files on Windows (PermissionError: [WinError 5]);
    POSIX unlinks them regardless. Clear the write bit and retry any
    failed entry so removals behave the same on both platforms.
    """

    def _clear_readonly(func: Any, entry: Path, exc_info: object) -> None:
        os.chmod(entry, stat.S_IWRITE)
        func(entry)

    shutil.rmtree(path, onerror=_clear_readonly)


def _remove_orphans(
    config: Config, lockfile: Lockfile, removed_name: str
) -> None:
    """Recursively remove transitive sources that are no longer needed.

    After ``removed_name`` is deleted, walk all remaining lockfile entries
    and remove ``removed_name`` from their ``required_by`` lists.  Any
    entry whose ``required_by`` becomes empty and is **not** a top-level
    source (declared in the root ``wiki.yml``) is an orphan — delete its
    cache, remove it from the lockfile, and recurse in case *its*
    dependants become orphans too.
    """
    remaining_top_level = {s.name for s in config.sources}

    for entry in lockfile.sources.values():
        if removed_name in entry.required_by:
            entry.required_by = [r for r in entry.required_by if r != removed_name]

    orphaned = [
        n
        for n, e in lockfile.sources.items()
        if not e.required_by and n not in remaining_top_level
    ]

    for orphan in orphaned:
        cache_dir = _source_cache_dir(config, orphan)
        if cache_dir.exists():
            _rmtree_force(cache_dir)
            logger.info("Removed cache for orphaned transitive source %r", orphan)
        del lockfile.sources[orphan]
        logger.info(
            "Removed orphaned transitive source %r from lockfile", orphan
        )
        _remove_orphans(config, lockfile, orphan)  # cascade


def remove(config: Config, name: str) -> None:
    """Remove a source from wiki.yml, its cache, and wiki.lock.

    Transitive dependencies that are no longer required by any remaining
    top-level source are automatically cleaned up (cache and lockfile
    entry removed).

    The cache deletion is the step most likely to fail (read-only files on
    Windows, antivirus locks), so it runs first: a failure then leaves
    wiki.yml and wiki.lock untouched and consistent, and the source can be
    re-installed cleanly.
    """
    cache_dir = _source_cache_dir(config, name)
    if cache_dir.exists():
        _rmtree_force(cache_dir)
        logger.info("Removed cache for source %r", name)

    _remove_from_wiki_yml(config, name)

    lockfile = _load_lockfile(config)
    if name in lockfile.sources:
        del lockfile.sources[name]
        _remove_orphans(config, lockfile, name)
        _save_lockfile(config, lockfile)
        logger.info("Removed lock entry for source %r", name)


def resolve(config: Config) -> list[Path]:
    """Return resolved local paths for all locked sources (including
    transitive dependencies).

    Reads ``wiki.lock`` and returns the local paths of all cached sources
    — both top-level (declared in the root ``wiki.yml``) and transitive
    (declared by those sources' own ``wiki.yml`` files).

    Does NOT fetch — use ``install()`` to ensure sources are up to date.
    """
    lockfile = _load_lockfile(config)
    if not lockfile.sources:
        return []

    resolved: list[Path] = []

    for name, locked in lockfile.sources.items():
        repo_dir = _source_cache_dir(config, name) / "repo"
        if not repo_dir.exists():
            logger.warning(
                "Source %r is not cached. Run 'wiki install' first.", name
            )
            continue

        source = SourceConfig(
            name=name,
            type="git",
            url=locked.url,
            ref=locked.ref,
            path=locked.path,
        )
        try:
            resolved.append(_source_resolved_path(source, repo_dir))
        except RuntimeError as exc:
            logger.warning("Source %r: %s", name, exc)
            continue

    return resolved
