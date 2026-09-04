"""One-shot shape-(b) rename for #227. See design notes in the original."""

from pathlib import Path

ROOT = Path(__file__).parent

def sub(path: str, old: str, new: str, count: int) -> None:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    assert n == count, f"{path}: expected {count} of {old!r}, found {n}"
    p.write_text(s.replace(old, new), encoding="utf-8", newline="\n")
    print(f"  {path}: {n}x {old!r} -> {new!r}")

# --- Flag strings: --wiki-inputs -> --input ---
sub("src/wiki/cli.py", '"--wiki-inputs",', '"--input",', 2)
sub("npm/src/wiki.ts", '"--wiki-inputs"', '"--input"', 2)
sub("npm/test-wiki-api.js", "'--wiki-inputs'", "'--input'", 11)

for t in ("tests/test_cli.py", "tests/test_fmt.py"):
    p = ROOT / t
    s = p.read_text(encoding="utf-8")
    n = s.count("--wiki-inputs")
    assert n > 0, t
    s = s.replace("--wiki-inputs", "--input")
    p.write_text(s, encoding="utf-8", newline="\n")
    print(f"  {t}: {n}x --wiki-inputs -> --input")

# --- Doc comments referencing the flag ---
sub("npm/test-cli-drift.js", "--wiki-inputs", "--input", 1)
sub("scripts/export_cli_flags.py", "``--wiki-inputs``", "``--input``", 1)

# --- Config key prose: wiki.inputs -> wiki.input (python + docs + skills) ---
PY = [
    "src/wiki/graph.py", "src/wiki/graph_cache.py", "src/wiki/mcp.py",
    "src/wiki/paths.py", "src/wiki/publish.py", "src/wiki/serve.py",
    "src/wiki/wiki.py", "src/wiki/schemas/wiki_config.py",
    "src/wiki/schemas/cli.py", "src/wiki/cli.py",
]
for path in PY:
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    n = s.count("wiki.inputs")
    if n:
        s = s.replace("wiki.inputs", "wiki.input")
        p.write_text(s, encoding="utf-8", newline="\n")
        print(f"  {path}: {n}x wiki.inputs -> wiki.input")

MD = sorted((ROOT / "docs/wiki").rglob("*.md")) + sorted((ROOT / "skills/wiki").rglob("*.md")) + [ROOT / "README.md"]
for path in MD:
    s = path.read_text(encoding="utf-8")
    n = s.count("wiki.inputs")
    if n:
        s = s.replace("wiki.inputs", "wiki.input")
        path.write_text(s, encoding="utf-8", newline="\n")
        print(f"  {path}: {n}x wiki.inputs -> wiki.input")

# --- Flag strings in docs/skills/README prose ---
for path in MD:
    s = path.read_text(encoding="utf-8")
    n = s.count("--wiki-inputs")
    if n:
        s = s.replace("--wiki-inputs", "--input")
        path.write_text(s, encoding="utf-8", newline="\n")
        print(f"  {path}: {n}x --wiki-inputs -> --input")

# --- Schema aliases: wikiInputs -> input (MainOptions + InitOptions) ---
sub("src/wiki/schemas/cli.py", 'alias="wikiInputs"', 'alias="input"', 2)

# --- TS refs: wikiInputs -> input (wiki.ts, types.ts) ---
for path in ("npm/src/wiki.ts", "npm/src/types.ts", "npm/test-wiki-api.js"):
    p = ROOT / path
    s = p.read_text(encoding="utf-8")
    n = s.count("wikiInputs")
    if n:
        s = s.replace("wikiInputs", "input")
        p.write_text(s, encoding="utf-8", newline="\n")
        print(f"  {path}: {n}x wikiInputs -> input")

# --- Config schema field: WikiConfig.inputs -> input (+validator) ---
p = ROOT / "src/wiki/schemas/wiki_config.py"
s = p.read_text(encoding="utf-8")
old = "    inputs: list[Path] = Field(default_factory=lambda: [Path(\"wiki\")])"
new = "    input: list[Path] = Field(default_factory=lambda: [Path(\"wiki\")])"
assert s.count(old) == 1
s = s.replace(old, new)
old = '    @field_validator("inputs", mode="before")'
new = '    @field_validator("input", mode="before")'
assert s.count(old) == 1
s = s.replace(old, new)
old = "    def _validate_inputs(cls, value: object) -> list[Path]:"
new = "    def _validate_input(cls, value: object) -> list[Path]:"
assert s.count(old) == 1
s = s.replace(old, new)
old = '            "inputs": inputs,'
new = '            "input": inputs,'
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
p.write_text(s, encoding="utf-8", newline="\n")
print("  wiki_config.py: field+validator renamed to input")

# --- YAML keys: `inputs:` directly under `wiki:` -> `input:` ---
def fix_wiki_inputs_key(path: str) -> None:
    p = ROOT / path
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    changed = 0
    top = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out.append(line)
            continue
        if not line[:1].isspace() and ":" in line and not stripped.startswith("-"):
            key = stripped.split(":", 1)[0].strip().strip('"')
            top = key
            out.append(line)
            continue
        if top == "wiki" and stripped == "inputs:" and line.startswith("  "):
            out.append(line.replace("inputs:", "input:", 1))
            changed += 1
            continue
        out.append(line)
    assert changed > 0, path
    p.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"  {path}: {changed}x inputs: -> input: (under wiki:)")

fix_wiki_inputs_key("src/wiki/templates/wiki.yml")
fix_wiki_inputs_key("docs/wiki.yml")
for md in ("docs/wiki/SHACL.md", "docs/wiki/Recursive_Semantic_Datasets.md",
           "docs/wiki/Wiki_Configuration.md"):
    fix_wiki_inputs_key(md)

print("ALL RENAME EDITS APPLIED")
