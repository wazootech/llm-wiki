"""Export CLI option models as JSON Schema documents.

First half of the Python -> TypeScript generation pipeline (issue #286): dump
each distinct ``COMMAND_MODELS`` model as a standalone JSON Schema document
whose property names are the camelCase ``alias`` values TypeScript consumers
use — the ``by_alias=True`` export this module's package docstring has
anticipated since #283.  The sibling script ``scripts/generate_cli_types.mjs``
feeds these documents to json-schema-to-typescript and writes
``npm/src/types.generated.ts``.

What the export carries, and how:

- **Property names** come from each field's camelCase ``alias``, so the JSON
  property names are already the TypeScript property names.
- **Optionality** comes from Pydantic's ``required`` array (fields without
  defaults).  A field defaulted to ``None`` still serializes as ``anyOf
  [T, null]``; the generator strips the ``null`` for optional fields because
  ``?`` already expresses optionality in TS.
- **Choice unions** come from ``Literal[...]`` and the
  ``json_schema_extra={"enum": ...}`` lists, so no TS union needs hand
  authoring.
- **Doc comments** come from each model's docstring (class) and
  ``Field(description=...)`` (members), which json-schema-to-typescript
  renders as JSDoc — satisfying the typedoc ``notDocumented`` gate on the
  generated file.
- **Tuple-typed fields** (``tuple[Path, ...]``, ``tuple[str, ...] | None``)
  are marked with the standard JSON Schema ``readOnly: true`` keyword so the
  generator can emit ``readonly string[]`` and keep parity with the
  hand-written ``types.ts``.  Mutable ``list`` fields are not flagged.

Usage:
    uv run python scripts/export_cli_schemas.py [--out DIR]

Writes one ``<ModelName>.schema.json`` per model and prints the list to
stderr.  ``DIR`` defaults to ``.cli-schemas/`` (gitignored).
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
import types
from pathlib import Path
from typing import Union, get_args, get_origin, get_type_hints

_src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_src))

from wiki.schemas import COMMAND_MODELS  # noqa: E402 — path inserted above


def _is_tuple_annotation(annotation: object) -> bool:
    """Whether ``annotation`` is (possibly a union containing) a ``tuple[...]``.

    Resolves through ``tuple[Path, ...] | None`` to the ``tuple`` origin; a
    mutable ``list[...]`` field returns False.
    """
    origin = get_origin(annotation)
    if origin is tuple:
        return True
    if origin in (Union, types.UnionType):
        return any(_is_tuple_annotation(arg) for arg in get_args(annotation))
    return False


def _decorate(schema: dict, model_cls: type) -> None:
    """Add the model docstring and tuple ``readOnly`` markers to ``schema``."""
    if model_cls.__doc__:
        schema["description"] = inspect.cleandoc(model_cls.__doc__)
    hints = get_type_hints(model_cls)
    for field_name, field_info in model_cls.model_fields.items():
        if _is_tuple_annotation(hints.get(field_name)):
            alias = field_info.alias or field_name
            schema["properties"][alias]["readOnly"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".cli-schemas",
        help="Directory to write one <ModelName>.schema.json per model.",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    seen: set[str] = set()
    for model_cls in sorted(
        (cls for cls in COMMAND_MODELS.values()),
        key=lambda cls: cls.__name__,
    ):
        if model_cls.__name__ in seen:
            continue
        seen.add(model_cls.__name__)
        schema = model_cls.model_json_schema(by_alias=True)
        _decorate(schema, model_cls)
        dest = args.out / f"{model_cls.__name__}.schema.json"
        dest.write_text(json.dumps(schema, indent=2) + "\n")
        written.append(dest)

    print(f"Wrote {len(written)} JSON Schemas to {args.out}:", file=sys.stderr)
    for path in written:
        print(f"  - {path.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
