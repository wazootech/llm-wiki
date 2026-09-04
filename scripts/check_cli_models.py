"""Verify Pydantic CLI option models cover the real Click command tree.

The npm drift test (``npm/test-cli-drift.js``) compares the TypeScript
binding against ``COMMAND_MODELS`` in ``src/wiki/schemas/cli.py``. That
only catches drift once a command/flag has a model — a subcommand or
``@click.option`` added without a model entry is invisible to it.

This script closes the loop by introspecting the actual Click CLI
(``wiki.cli.main``) and failing when a non-hidden command or option has
no Pydantic model with a matching field (by python name or alias):

- every non-hidden top-level leaf command must be registered in
  ``COMMAND_MODELS`` with a model whose fields cover every Click param
  (option and positional argument);
- nested group leaves (e.g. ``wiki graph list``) must have zero Click
  params unless they gain a model — the TS binding flattens them into a
  dedicated method such as ``Wiki.graphList()`` with no options;
- every model field must correspond to a real Click param (catches stale
  aliases after a flag is removed);
- **choice values must agree** — where a Click param uses ``click.Choice``
  (or the ``FormatChoice`` subclass), the set of canonical choices must
  equal the allowed values of the matching model field (its ``Literal[...]``
  annotation and/or ``json_schema_extra={"enum": [...]}`` list). A new
  choice accepted by the CLI but missing from the model — and therefore
  from the generated TypeScript — fails here before it can ship, and so
  does a model value the CLI rejects. For ``case_sensitive=False`` choices
  the comparison is case-insensitive (Click accepts ``JSON`` while the
  model documents the canonical ``json``). ``FormatChoice`` MIME/extension
  aliases are intentionally not compared: they resolve to canonical choices
  the model already lists.

Mirroring rule from AGENTS.md: when changing ``src/wiki/cli.py``
subcommands, flags, choices, or positional arguments, update
``npm/src/wiki.ts``, ``npm/src/types.ts``, and ``npm/test-wiki-api.js``
in the same PR. This check enforces the first half of that contract
(CLI -> schemas); the npm drift test enforces the second half
(schemas -> TypeScript).

Usage:
    uv run python scripts/check_cli_models.py
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Literal, Union, get_args, get_origin, get_type_hints

import click

_src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src))

from wiki.schemas import COMMAND_MODELS  # noqa: E402 — path inserted above


def _matching_field(model: type, param_name: str) -> tuple[str, object] | None:
    """The (field name, field info) in ``model`` matching a Click param name.

    Click param names are the python snake_case names (e.g.
    ``site_url_style``, ``disk_cache``); model fields use the same python
    names with camelCase ``alias`` for TS consumers, so either spelling
    satisfies the match.
    """
    for field_name, field_info in model.model_fields.items():
        if field_name == param_name or field_info.alias == param_name:
            return field_name, field_info
    return None


def _literal_values(annotation: object) -> set[str]:
    """String values allowed by a ``Literal[...]`` annotation (union-aware)."""
    origin = get_origin(annotation)
    if origin is Literal:
        return {v for v in get_args(annotation) if isinstance(v, str)}
    if origin in (Union, types.UnionType):
        values: set[str] = set()
        for arg in get_args(annotation):
            values |= _literal_values(arg)
        return values
    return set()


def _model_choice_values(
    model: type,
    field_name: str,
    field_info: object,
    hints: dict[str, object],
) -> set[str]:
    """Allowed values the model declares for ``field_name``.

    Combines any ``Literal[...]`` annotation with a
    ``json_schema_extra={"enum": [...]}`` list — the two ways choice unions
    are expressed in ``src/wiki/schemas/cli.py``.
    """
    values = _literal_values(hints.get(field_name))
    extra = getattr(field_info, "json_schema_extra", None)
    if isinstance(extra, dict):
        enum = extra.get("enum")
        if isinstance(enum, list):
            values.update(v for v in enum if isinstance(v, str))
    return values


def _click_choice_values(
    param: click.Parameter,
) -> tuple[set[str], bool] | None:
    """Canonical choices of a Click Choice param, or None for non-Choice params.

    Returns ``(choices, case_sensitive)``. ``FormatChoice`` (a ``click.Choice``
    subclass) is handled transparently: ``.choices`` holds the canonical short
    names, while its MIME/extension aliases are CLI-only conveniences that
    resolve to those canonical names and are not part of the mirror contract.
    """
    if not isinstance(param.type, click.Choice):
        return None
    case_sensitive = bool(getattr(param.type, "case_sensitive", True))
    return set(param.type.choices), case_sensitive


def _walk(group: click.Group, errors: list[str], prefix: tuple[str, ...] = ()) -> None:
    """Collect conformance errors for every leaf command under ``group``."""
    for name, command in group.commands.items():
        path = (*prefix, name)
        if getattr(command, "hidden", False):
            continue

        if isinstance(command, click.Group):
            _walk(command, errors, path)
            continue

        if len(path) > 1:
            # Nested group leaf (e.g. ``graph list``). The TS binding
            # flattens it into a dedicated zero-option method
            # (``Wiki.graphList()``); if it ever gains params, give it a
            # model and a TS wrapper.
            if command.params:
                errors.append(
                    f"Nested CLI leaf '{' '.join(path)}' has params but no "
                    f"COMMAND_MODELS entry; add a Pydantic model + TS wrapper."
                )
            continue

        leaf = path[0]
        model = COMMAND_MODELS.get(leaf)
        if model is None:
            errors.append(
                f"CLI command '{leaf}' has no Pydantic model in COMMAND_MODELS "
                f"(src/wiki/schemas/cli.py); add one and mirror it into the TS "
                f"binding (npm/src/wiki.ts, npm/src/types.ts)."
            )
            continue

        click_params = {param.name for param in command.params}
        hints = get_type_hints(model)
        for param in command.params:
            match = _matching_field(model, param.name)
            flags = " ".join(param.opts or []) or param.name
            if match is None:
                errors.append(
                    f"CLI command '{leaf}' {flags} has no field in "
                    f"{model.__name__}; add a field with the matching camelCase "
                    f"alias."
                )
                continue
            field_name, field_info = match
            click_choice = _click_choice_values(param)
            model_choices = _model_choice_values(model, field_name, field_info, hints)
            if click_choice is None and not model_choices:
                continue
            if click_choice is None:
                errors.append(
                    f"CLI command '{leaf}' {flags} accepts any value but "
                    f"{model.__name__}.{field_name} restricts to "
                    f"{sorted(model_choices)}; add a click.Choice so the CLI and "
                    f"TypeScript agree on accepted values."
                )
                continue
            choices, case_sensitive = click_choice
            if not model_choices:
                errors.append(
                    f"CLI command '{leaf}' {flags} restricts to {sorted(choices)} "
                    f"but {model.__name__}.{field_name} declares no Literal/enum; "
                    f"mirror the Choice into the model (and the TS union)."
                )
                continue
            norm = (lambda v: v) if case_sensitive else (lambda v: v.casefold())
            cli_set = {norm(v) for v in choices}
            model_set = {norm(v) for v in model_choices}
            if cli_set != model_set:
                parts = []
                cli_only = sorted(cli_set - model_set)
                model_only = sorted(model_set - cli_set)
                if cli_only:
                    parts.append(f"CLI-only: {cli_only}")
                if model_only:
                    parts.append(f"model-only: {model_only}")
                errors.append(
                    f"CLI command '{leaf}' {flags} choices {sorted(choices)} "
                    f"differ from {model.__name__}.{field_name} "
                    f"{sorted(model_choices)} ({'; '.join(parts)}); comparison is "
                    f"case-{'insensitive' if not case_sensitive else 'sensitive'}."
                )
        for field_name, field_info in model.model_fields.items():
            alias = field_info.alias or field_name
            if field_name not in click_params and alias not in click_params:
                errors.append(
                    f"{model.__name__} field '{field_name}' has no matching "
                    f"Click param on '{leaf}'; remove or realign the field."
                )


def main() -> int:
    from wiki.cli import main  # noqa: PLC0415 — deferred heavy import

    errors: list[str] = []
    _walk(main, errors)

    if errors:
        print(f"CLI/model conformance FAILED ({len(errors)} issue(s)):", file=sys.stderr)
        for error in errors:
            print(f"  *  {error}", file=sys.stderr)
        print(
            "Fix: update src/wiki/schemas/cli.py so COMMAND_MODELS mirrors the "
            "Click CLI, then mirror new wrappers into npm/src/wiki.ts, "
            "npm/src/types.ts, and npm/test-wiki-api.js.",
            file=sys.stderr,
        )
        return 1

    command_count = sum(
        1
        for cmd in main.commands.values()
        if not getattr(cmd, "hidden", False) and not isinstance(cmd, click.Group)
    )
    print(
        f"CLI/model conformance passed: {command_count} commands mirror "
        f"COMMAND_MODELS."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())