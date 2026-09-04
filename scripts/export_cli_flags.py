"""Emit the real Click option strings for every top-level command.

Stage 4 of the npm drift test (``npm/test-cli-drift.js``): the wrapper's flag
emissions in ``npm/src/wiki.ts`` are literal strings duplicated from Click's
``@click.option`` declarations, and until now nothing verified the two agree —
a renamed or misspelled flag passed every earlier stage (models only carry
field names/aliases, never flag strings) and failed at runtime with Click's
"no such option". This script closes that hole by introspecting the real Click
tree (same walk as ``scripts/check_cli_models.py``) and printing, per top-level
leaf command, the exact option strings Click accepts:

- ``param.opts`` carries every spelling of an option (long and short, e.g.
  ``--verbose`` and ``-v``); ``param.secondary_opts`` carries the negative
  half of ``"/"`` boolean pairs (e.g. ``--no-graph-include-file-extension``).
  Only ``-``-prefixed strings are collected, so positional arguments
  (whose ``opts`` is just the bare name) never pollute the set.
- The root group's own params (``--config``, ``--wiki-inputs``) are emitted
  under the ``"__root__"`` key — they live in no ``COMMAND_MODELS`` entry, so
  no earlier stage guards them.
- Nested leaves (e.g. ``graph list``) are zero-param by construction
  (``check_cli_models.py`` enforces it), so they carry no options to emit.

The drift test extracts every ``--flag`` string literal from each wrapper
method and asserts each one is in its command's set here.

Usage:
    uv run python scripts/export_cli_flags.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

_src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src))

# Aliased so this script's own main() below doesn't shadow the CLI group.
from wiki.cli import main as cli_main  # noqa: E402 — path inserted above

ROOT_KEY = "__root__"


def _opts(params: list[click.Parameter]) -> list[str]:
    """Sorted unique option strings for ``params``.

    Excludes the auto ``--help`` param and positional arguments (whose
    ``opts`` is just the bare name — never a ``-``-prefixed string).
    """
    strings: set[str] = set()
    for param in params:
        if param.name == "help":
            continue
        for opt in (*param.opts, *getattr(param, "secondary_opts", ())):
            if opt.startswith("-"):
                strings.add(opt)
    return sorted(strings)


def main() -> int:
    result: dict[str, list[str]] = {ROOT_KEY: _opts(cli_main.params)}

    def walk(group: click.Group, prefix: tuple[str, ...] = ()) -> None:
        for name, command in group.commands.items():
            path = (*prefix, name)
            if getattr(command, "hidden", False):
                continue
            if isinstance(command, click.Group):
                walk(command, path)
                continue
            if len(path) == 1:
                result[name] = _opts(command.params)

    walk(cli_main)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())