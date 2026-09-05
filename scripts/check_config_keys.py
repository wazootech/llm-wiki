"""Verify every documented ``wiki.yml`` config key resolves against the schema.

Stage 5 of the CLI drift contract.  Stages 1-4 anchor the Click command tree,
the ``COMMAND_MODELS``, the generated TypeScript, and the wrapper's flag
strings — but the ``wiki.yml`` config surface is outside all of them: renaming
a config-schema field (e.g. ``wiki.inputs`` -> ``wiki.input``) sails through
every earlier stage and only breaks at runtime, when a stale template key
fails to load or a doc reference points at a dead key.

This script resolves every config-key reference in the surfaces that
duplicate the schema — the init scaffold template
(``src/wiki/templates/wiki.yml``) and the markdown documentation
(``docs/wiki``, ``skills/wiki``, ``README.md``) — against the Pydantic
``Config`` model, and fails on any reference that does not resolve.

Reference surfaces and extraction:

- **Template**: a light state machine over the Jinja template (the ``{% %}``
  blocks make it unparseable as YAML).  Top-level sections sit at column 0,
  sub-keys are indented; commented keys (``# exclude:``) are checked too, so
  a schema rename cannot silently stale the documentation examples.  No
  allowlist applies here: the scaffold must only ever emit schema-valid keys.
- **Markdown**: dotted ``section.key`` tokens whose first segment is a
  top-level config section.  The docs legitimately mix four namespaces —
  config keys, layout slot tokens (``%wiki.base_url%``), Python module paths
  (``wiki.site.layout_tokens...``), and filenames (``wiki.yml``) — so
  non-config tokens are allowlisted below with a reason each.  The allowlist
  covers no schema field, so a config-key rename is never masked.

Resolution walks the ``Config`` model: the first segment must be a top-level
field, then each further segment a field of the nested model.  ``dict``-typed
fields (``graph.context``, ``link.renames``), list-of-model fields
(``sources``), and unions containing a ``dict`` member (``fmt``) accept
arbitrary keys below them.

Usage:
    uv run python scripts/check_config_keys.py
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from typing import Annotated, Union, get_args, get_origin

from pydantic import BaseModel

_src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src))

from wiki.schemas.wiki_config import Config  # noqa: E402 — path inserted above

# Doc-only tokens that match the ``section.key`` pattern but are not config
# keys.  Each entry carries its reason; nothing here is a schema field, so a
# field rename can never be hidden by the allowlist.
ALLOWED: dict[str, str] = {
    # Layout slot tokens — template variables, not config keys.
    "wiki.base_url": "layout slot token ``%wiki.base_url%`` (template variable)",
    "wiki.head": "layout slot token ``%wiki.head%``",
    "wiki.body": "layout slot token ``%wiki.body%``",
    # Python module paths in the programmatic-API docs, not config keys.
    "wiki.site.layout_tokens.build_layout_token_map": "Python module path in the programmatic API docs",
    "wiki.__all__": "Python module attribute reference",
    # Filenames / URLs whose dotted form matches the section-key pattern.
    "wiki.yml": "filename reference (wiki.yml)",
    "wiki.yaml": "filename reference (wiki.yaml)",
    "wiki.md": "filename reference (wiki.md)",
    "wiki.lock": "filename reference (wiki.lock lockfile)",
    "wiki.json": "filename reference (wiki.json)",
    "wiki.exe": "binary name reference (wiki.exe)",
    "wiki.git": "filename/repo reference",
    "wiki.example.org": "example URL host",
    "wiki.wazoo.dev": "URL host (wiki.wazoo.dev)",
    "check.yml": "filename reference (check.yml)",
    # CLI subcommands written with a dot in prose.
    "wiki.check": "CLI subcommand written with a dot",
    "wiki.query": "CLI subcommand written with a dot",
    # Documented anti-patterns — the doc explicitly says these fail at load
    # and points at the lint.* equivalents.
    "check.filename_pattern": "documented anti-pattern (use ``lint.filename_pattern``)",
    "check.headings": "documented anti-pattern (use ``lint.headings``)",
    # Linked Markdown vocabulary keys (frontmatter, ``wiki.``-prefixed) — the
    # document explains these map to the local ``wiki:`` namespace; they are
    # not wiki.yml config keys.
    "wiki.status": "Linked Markdown ``wiki.``-vocabulary key, not a config key",
    # Deprecated keys the lint rule still warns on — documented as no longer
    # part of the schema, so they must not resolve.
    "site.manifest": "documented deprecated key (lint warns on its presence)",
    "site.title": "documented deprecated key (lint warns on its presence)",
    "site.theme_color": "documented deprecated key (lint warns on its presence)",
    # Python module / attribute references in the programmatic-API docs.
    "wiki.site": "Python module reference (``wiki.site``)",
    "wiki.graph": "Python module reference (``wiki.graph``)",
    "wiki.py": "Python module reference (``src/wiki/wiki.py`` line-range citation)",
    "graph.py": "Python module reference (``src/wiki/graph.py`` line-range citation)",
    "wiki.schemas.init": "Python module reference (``wiki.schemas.init``)",
    "wiki.schemas.layout": "Python module reference (``wiki.schemas.layout``)",
    "graph.name": "Python attribute access in a code snippet",
    "graph.kind": "Python attribute access in a code snippet",
    "graph.uri": "Python attribute access in a code snippet",
    "graph.resolved_ref": "Python attribute access in a code snippet",
    "site.base_url.strip": "Python method call in a code snippet",
    # Filenames / URIs.
    "site.css": "filename reference (assets/site.css)",
    "graph.ttl": "filename reference (wiki://graph.ttl)",
    "wiki.ts": "filename reference (npm/src/wiki.ts)",
    "wiki.svg": "filename reference (README badge)",
}

def _kind(annotation: object) -> str | tuple[str, type[BaseModel]]:
    """Classify an annotation for key resolution.

    Returns ``"any"`` (arbitrary sub-keys accepted), ``("model", cls)``
    (descend into the model's fields), or ``"leaf"`` (scalar — path ends).
    """
    origin = get_origin(annotation)
    if origin is Annotated:
        return _kind(get_args(annotation)[0])
    if origin is Union or origin is types.UnionType:
        members = [_kind(a) for a in get_args(annotation)]
        if any(kind == "any" for kind in members):
            return "any"
        for kind in members:
            if isinstance(kind, tuple):
                return kind  # ("model", cls)
        return "leaf"
    if origin is dict:
        return "any"
    if origin in (list, tuple, set, frozenset):
        args = get_args(annotation)
        if args and args[0] is not Ellipsis:
            return _kind(args[0])
        return "leaf"
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return ("model", annotation)
    return "leaf"


SECTIONS: dict[str, str | tuple[str, type[BaseModel]]] = {
    name: _kind(field.annotation)
    for name, field in Config.model_fields.items()
    if name
    != "config_root"  # internal bookkeeping field, not a documented section
}

# First segment must be a Config top-level section. Derived from the schema
# so a new top-level config section is verified automatically - a hardcoded
# list here would itself drift from the schema it guards.
SECTION_RE = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in SECTIONS) + r")\.[a-z_]+(?:\.[a-z_]+)*"
)


def resolve(section: str, rest: tuple[str, ...]) -> str | None:
    """Resolve a ``section.rest`` path; return an error message or ``None``."""
    kind = SECTIONS.get(section)
    if kind is None:
        return (
            f"unknown config section '{section}' "
            f"(top-level sections: {', '.join(sorted(SECTIONS))})"
        )
    for seg in rest:
        if kind == "any":
            return None
        if kind == "leaf":
            return f"no nested fields under scalar '{section}'"
        model = kind[1]
        fields = model.model_fields
        if seg not in fields:
            valid = ", ".join(sorted(fields))
            return f"unknown field '{seg}' under '{section}' (valid: {valid})"
        kind = _kind(fields[seg].annotation)
    return None


def template_keys(template: Path) -> list[tuple[str, int]]:
    """``(section.key, lineno)`` pairs from the Jinja scaffold template.

    A stack keyed by indent tracks nesting, so the CURIE prefix map under
    ``graph.context`` yields ``graph.context.schema`` (which the resolver
    accepts — ``context`` is a dict) rather than the bogus ``graph.schema``.
    """
    keys: list[tuple[str, int]] = []
    stack: list[tuple[int, str]] = []
    for lineno, raw in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
        if " #" in raw:
            raw = raw.split(" #", 1)[0]
        indent = len(raw) - len(raw.lstrip())
        content = raw.strip()
        if content.startswith("#"):
            content = content.lstrip("#").strip()
        if not content or content.startswith(("{%", "{{")):
            continue
        match = re.match(r"^(?:-\s+)?([a-z_]+):", content)
        if not match:
            continue
        key = match.group(1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            # Top-level section at column 0 — start a new path.
            stack.append((indent, key))
            continue
        path = f"{stack[-1][1]}.{key}"
        keys.append((path, lineno))
        stack.append((indent, path))
    return keys


def markdown_tokens(path: Path) -> list[tuple[str, int]]:
    """``(token, lineno)`` pairs matching the section-key pattern."""
    tokens: list[tuple[str, int]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in SECTION_RE.finditer(line):
            tokens.append((match.group(0), lineno))
    return tokens


def main() -> int:
    template = Path("src/wiki/templates/wiki.yml")
    md_files = sorted(Path("docs/wiki").rglob("*.md")) + sorted(
        Path("skills/wiki").rglob("*.md")
    )
    readme = Path("README.md")

    errors: list[str] = []
    template_count = 0
    doc_count = 0
    allowed_count = 0

    def check(path: Path, key: str, lineno: int, allowlistable: bool) -> None:
        nonlocal template_count, doc_count, allowed_count
        head, *rest = key.split(".")
        message = resolve(head, tuple(rest))
        if message is None:
            if allowlistable:
                doc_count += 1
            else:
                template_count += 1
            return
        if allowlistable and key in ALLOWED:
            allowed_count += 1
            return
        if allowlistable:
            doc_count += 1
            hint = f" (allowlist candidate: {ALLOWED.get(key, 'not yet classified')})"
            errors.append(f"{path}:{lineno}: {key} — {message}{hint}")
        else:
            errors.append(f"{path}:{lineno}: {key} — {message} (template keys must resolve)")

    for key, lineno in template_keys(template):
        check(template, key, lineno, allowlistable=False)

    for path in md_files + [readme]:
        for key, lineno in markdown_tokens(path):
            check(path, key, lineno, allowlistable=True)

    if errors:
        print(f"Config-key conformance FAILED ({len(errors)} issue(s)):\n")
        for error in errors:
            print(f"  *  {error}")
        return 1

    print(
        f"Config-key conformance passed: {template_count + doc_count} references "
        f"verified across {len(md_files) + 2} files "
        f"({template_count} template keys, {doc_count} doc keys, "
        f"{allowed_count} allowlisted)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())