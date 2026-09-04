"""Fix straggler tokens missed by the main rename (doc comments, test asserts)."""

from pathlib import Path

ROOT = Path(__file__).parent

def repl(path: str, old: str, new: str, count: int) -> None:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    assert n == count, f"{path}: expected {count} of {old!r}, found {n}"
    p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
    print(f"  {path}: {n}x {old!r} -> {new!r}")

repl("npm/src/types.ts", "Override ``wiki.inputs``", "Override ``wiki.input``", 1)
repl("npm/src/wiki.ts", "Overridden ``wiki.inputs`` paths.", "Overridden ``wiki.input`` paths.", 1)
repl("npm/src/wiki.ts", "Prepends ``--wiki-inputs`` and ``--config``", "Prepends ``--input`` and ``--config``", 1)
repl("tests/test_config.py", "config.wiki.inputs", "config.wiki.input", 4)
repl("skills/README.md", "do not add this folder to ``wiki.inputs``", "do not add this folder to ``wiki.input``", 1)

print("STRAggLER FIXES APPLIED")
