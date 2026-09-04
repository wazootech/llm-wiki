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
  aliases after a flag is removed).

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
from pathlib import Path

import click

_src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src))

from wiki.schemas import COMMAND_MODELS  # noqa: E402 — path inserted above


def _covered(model: type, param_name: str) -> bool:
    """Whether ``model`` has a field matching a Click param name.

    Click param names are the python snake_case names (e.g.
    ``site_url_style``, ``disk_cache``); model fields use the same python
    names with camelCase ``alias`` for TS consumers, so either spelling
    satisfies the match.
    """
    for field_name, field_info in model.model_fields.items():
        if field_name == param_name or field_info.alias == param_name:
            return True
    return False


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
        for param in command.params:
            if not _covered(model, param.name):
                flags = " ".join(param.opts or [])
                errors.append(
                    f"CLI command '{leaf}' {flags or param.name} has no field in "
                    f"{model.__name__}; add a field with the matching camelCase "
                    f"alias."
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
