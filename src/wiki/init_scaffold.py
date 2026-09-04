"""Helpers for `wiki init`: GitHub repo parsing, URL inference, and wiki.yml rendering."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .schemas import InitOptions, ScaffoldResult
from .schemas.wiki_config import DEFAULT_WIKI_BASE, normalize_base_iri

__all__ = [
    "InitOptions",
    "fetch_template",
    "load_packaged_official_layout",
    "render_wiki_yaml",
    "resolve_init_options",
    "_scaffold_wiki",
]

DEFAULT_BASE_URL = "/wiki"
DEFAULT_URL_STYLE = "dir"

_GITHUB_HTTPS_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
_GITHUB_SSH_RE = re.compile(
    r"git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    re.IGNORECASE,
)
_OWNER_REPO_RE = re.compile(r"^(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")


def normalize_base_url(value: str) -> str:
    """Ensure base_url starts with / and has no trailing slash (except root)."""
    text = str(value).strip()
    if not text.startswith("/"):
        text = "/" + text
    if text != "/" and text.endswith("/"):
        text = text.rstrip("/")
    return text


def parse_github_repo(value: str) -> tuple[str, str]:
    """Parse owner/repo from shorthand, HTTPS, or SSH GitHub URLs."""
    text = value.strip()
    for pattern in (_GITHUB_HTTPS_RE, _GITHUB_SSH_RE, _OWNER_REPO_RE):
        match = pattern.match(text)
        if match:
            owner = match.group("owner")
            repo = match.group("repo")
            if repo.endswith(".git"):
                repo = repo[:-4]
            return owner, repo
    raise ValueError(
        f"Invalid GitHub repo: {value!r} (expected owner/repo, "
        "https://github.com/owner/repo, or git@github.com:owner/repo.git)"
    )


def infer_github_pages_urls(owner: str, repo: str) -> tuple[str, str]:
    """Return (context.wiki IRI, base_url) for a GitHub Pages project site."""
    context_wiki = normalize_base_iri(f"https://{owner}.github.io/{repo}")
    base_url = normalize_base_url(f"/{repo}")
    return context_wiki, base_url


def detect_origin_repo(cwd: Path) -> str | None:
    """Return owner/repo parsed from git remote origin, or None."""
    if not (cwd / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    remote_url = result.stdout.strip()
    if not remote_url:
        return None
    try:
        owner, repo = parse_github_repo(remote_url)
    except ValueError:
        return None
    return f"{owner}/{repo}"


def resolve_init_options(
    *,
    repo: str | None,
    graph_context_wiki: str | None,
    site_base_url: str | None,
    site_url_style: str | None,
    site_layout: str | None = None,
    graph_content_predicate: str | None,
    link_style: str | None,
    cwd: Path,
    init_git: bool,
    prompt_context_wiki: Callable[[str], str],
    wiki_inputs: list[str] | None = None,
    graph_base_iri: str | None = None,
    graph_implicit_types: list[str] | None = None,
    graph_implicit_types_policy: str | None = None,
    graph_include_file_extension: bool | None = None,
) -> InitOptions:
    """Resolve init config from CLI flags, git remote, or interactive prompt."""
    inferred_context_wiki: str | None = None
    inferred_base_url: str | None = None

    repo_slug = repo
    if repo_slug is None and (init_git or (cwd / ".git").exists()):
        repo_slug = detect_origin_repo(cwd)

    if graph_context_wiki is None and repo_slug is not None:
        owner, repo_name = parse_github_repo(repo_slug)
        inferred_context_wiki, inferred_base_url = infer_github_pages_urls(owner, repo_name)

    resolved_context_wiki = graph_context_wiki or inferred_context_wiki
    if resolved_context_wiki is None:
        resolved_context_wiki = prompt_context_wiki(DEFAULT_WIKI_BASE)
    resolved_context_wiki = normalize_base_iri(resolved_context_wiki)

    resolved_base_url = site_base_url or inferred_base_url or DEFAULT_BASE_URL
    resolved_base_url = normalize_base_url(resolved_base_url)

    resolved_url_style = site_url_style or DEFAULT_URL_STYLE

    return InitOptions(
        graph_context_wiki=resolved_context_wiki,
        site_base_url=resolved_base_url,
        site_url_style=resolved_url_style,
        site_layout=site_layout,
        graph_content_predicate=graph_content_predicate,
        link_style=link_style,
        wiki_inputs=wiki_inputs,
        graph_base_iri=graph_base_iri,
        graph_implicit_types=graph_implicit_types,
        graph_implicit_types_policy=graph_implicit_types_policy,
        graph_include_file_extension=graph_include_file_extension,
    )


WIKI_TEMPLATES_REPO = "https://github.com/wazootech/wiki-templates.git"


def fetch_template(
    target_dir: Path,
    template_name: str,
) -> None:
    """Clone the wiki-templates monorepo and copy a template into *target_dir*.

    Args:
        target_dir: Destination directory (must be empty or new).
        template_name: Subdirectory name inside wiki-templates (e.g. "generic").

    Raises:
        RuntimeError: If the template is not found in the monorepo.
    """
    with tempfile.TemporaryDirectory(prefix="wiki-template-") as tmp_dir:
        clone_dir = Path(tmp_dir) / "wiki-templates"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", WIKI_TEMPLATES_REPO, str(clone_dir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to clone wiki-templates: {result.stderr.strip()}"
            )
        template_dir = clone_dir / template_name
        if not template_dir.is_dir():
            available = sorted(
                d.name
                for d in clone_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )
            raise RuntimeError(
                f"Template {template_name!r} not found in wiki-templates. "
                f"Available: {', '.join(available)}"
            )
        for item in template_dir.iterdir():
            if item.name.startswith(".") and item.name != ".gitignore":
                continue
            dest = target_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)


_INIT_TEMPLATE_NAME = "wiki.yml"
_OFFICIAL_LAYOUT_FILES = {
    "minimal": "index.html",
}
_PACKAGED_ASSETS_DIR = "assets"
_PACKAGED_ASSET_FILES = ()
_JINJA_COMMENT_PREFIX = "{# wiki init scaffold"


@lru_cache(maxsize=1)
def _init_template_env() -> Environment:
    return Environment(
        loader=PackageLoader("wiki", "templates"),
        autoescape=select_autoescape(default=False),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _strip_scaffold_comment(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if lines and lines[0].startswith(_JINJA_COMMENT_PREFIX):
        return "".join(lines[1:])
    return text


def render_wiki_yaml(opts: InitOptions) -> str:
    """Render the packaged wiki.yml scaffold into wiki.yml content."""
    rendered = _init_template_env().get_template(_INIT_TEMPLATE_NAME).render(**opts.model_dump())
    return _strip_scaffold_comment(rendered)


def load_packaged_official_layout(layout: str) -> str:
    """Return a packaged official init layout (wikipedia or minimal/index)."""
    filename = _OFFICIAL_LAYOUT_FILES.get(layout)
    if filename is None:
        raise ValueError(f"Unknown official layout: {layout!r}")
    return files("wiki").joinpath(filename).read_text(
        encoding="utf-8"
    )


_README_TEMPLATE = (
    "# My Wiki\n\n"
    "A semantic markdown knowledge base powered by the Wiki CLI.\n\n"
    "## Wiki layout\n\n"
    "- `wiki.yml` (or `wiki.toml`) — Wiki configuration, namespace prefixes, and `fmt` defaults.\n"
    "- `wiki/` — Empty directory for markdown pages with semantic frontmatter.\n\n"
    "## Commands\n\n"
    "- **Check** (integrity: SHACL, JSON Schema, route safety, layout frontmatter):\n"
    "  ```bash\n"
    "  wiki check\n"
    "  ```\n"
    "- **Lint** (conventions: broken links, filename pattern, heading style):\n"
    "  ```bash\n"
    "  wiki lint\n"
    "  ```\n"
    "- **Preview** (starts a local dev server with auto-reload):\n"
    "  ```bash\n"
    "  wiki serve --watch\n"
    "  ```\n"
    "- **Build** (compiles to static HTML site):\n"
    "  ```bash\n"
    "  wiki build\n"
    "  ```\n"
)

_GITIGNORE_TEMPLATE = (
    "# Source cache (fetched repos)\n"
    ".wiki/\n"
    "\n"
    "# Build output\n"
    "_site/\n"
)


def _scaffold_wiki(
    cwd: Path,
    init_options: InitOptions,
    *,
    init_git: bool = False,
) -> ScaffoldResult:
    """Write wiki.yml, starter pages, assets, and optional layout files."""
    import shutil

    written: list[Path] = []
    config_path = cwd / "wiki.yml"
    readme_path = cwd / "README.md"
    wiki_dir = cwd / "wiki"

    wiki_dir.mkdir(parents=True, exist_ok=True)
    gitignore_path = cwd / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(_GITIGNORE_TEMPLATE, encoding="utf-8")
        written.append(gitignore_path)
    readme_path.write_text(_README_TEMPLATE, encoding="utf-8")
    written.extend([readme_path, wiki_dir])

    config_content = render_wiki_yaml(init_options)
    config_path.write_text(config_content, encoding="utf-8")
    written.append(config_path)

    if init_git:
        if shutil.which("git") is None:
            return ScaffoldResult(
                ok=False,
                error_message="git was requested with --git, but no git executable was found on PATH.",
            )
        try:
            subprocess.run(["git", "init"], cwd=cwd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else "unknown git init error"
            return ScaffoldResult(ok=False, error_message=f"git init failed: {stderr}")

    message = (
        "Initialized wiki config, README.md, and an empty wiki/ directory."
    )
    if init_git:
        message += " Ran git init."

    return ScaffoldResult(
        ok=True,
        config_path=config_path,
        written_paths=written,
        message=message,
    )
