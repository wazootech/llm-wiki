---
type: TechArticle
headline: Wiki Programmatic API
description: Stable Python and TypeScript entry points for loading a wiki, validating, building, and querying from code.
---

# Wiki Programmatic API

The **Wiki** package exposes programmatic APIs for CI pipelines, tests, application code, and agent automation. The `wiki` command (Wiki CLI) remains the primary user surface; programmatic callers can use either the in-process Python library or the type-safe TypeScript SDK shipped by the npm package.

See [Design Philosophies](Design_Philosophies.md) for the CLI vs library split. The Python engine remains the source of truth; the TypeScript SDK is a thin binding over the Python CLI, not a second implementation.

## Python library

The **Wiki** package (`wazootech-wiki` on PyPI) exposes a **library-first** Python API. Python calls return typed results and raise domain exceptions instead of printing or exiting. Semver applies to symbols in `wiki.__all__` (listed below); other `wiki.*` modules are internal unless documented on this page.

Generated reference docs are available at [Python API Reference](Python_API_Reference.md).

### Install and imports

```bash
pip install wazootech-wiki
```

Import stable symbols from the top-level package:

```python
from wiki import Wiki, AuditReport, BuildResult
```

Symbols listed in `wiki.__all__` are semver-stable. Other modules (`wiki.site`, `wiki.graph`, …) are internal unless documented here.

The package ships a [PEP 561](https://peps.python.org/pep-0561/) marker (`py.typed`).

### Wiki session

`Wiki` wraps a loaded [Config](Wiki_Configuration.md) and graph lifecycle:

```python
from pathlib import Path
from wiki import Wiki

w = Wiki.load("wiki.yml")
# or override inputs (same as --input):
w = Wiki.load("wiki.yml", wiki_inputs=["docs/wiki"])

report = w.check()
if not report.ok:
    for issue in report.errors:
        print(issue.code, issue.path, issue.message)

# File-scoped check (SHACL + JSON Schema per file; no full-wiki-only rules):
report = w.check([Path("docs/wiki/Some_Page.md")])

lint_report = w.lint()
preflight = w.preflight()  # lint merged with check — same as wiki build preflight

graph = w.graph(infer=True, reload=False)
```

`Wiki.graph()` returns the compatibility union graph. For read-only provenance across installed sources, inspect named graph descriptors:

```python
for graph in w.graphs():
    print(graph.name, graph.kind, graph.uri, graph.resolved_ref)
```

SPARQL `GRAPH` clauses are supported through `Wiki.query()` and the CLI query command. Unscoped queries continue to read the default union view.

Runtime overrides (CLI `--site-base-url` / `--site-url-style`; Python `base_url` / `url_style` kwargs):

```python
w = w.with_runtime(base_url="/wiki", url_style="dir")
```

### Validation reports

Validation operations (`Wiki.check` and `Wiki.lint`) return an `AuditReport`:

| Field      | Meaning                                      |
| ---------- | -------------------------------------------- |
| `ok`       | No errors (warnings allowed unless promoted) |
| `errors`   | List of `Issue` with `severity="error"`      |
| `warnings` | List of `Issue` with `severity="warning"`    |

Each `Issue` has a stable machine-readable `code` (aligned with config rule keys such as `broken_links`, `shacl_violation`, `frontmatter_schema`) and a human `message` for CLI-style output.

```python
from pathlib import Path
from wiki import Wiki

w = Wiki.load("wiki.yml")
report = w.check()
strict = report.apply_strict()  # promote warnings to errors
errors, warnings = report.messages()
merged = report.merge(other_report)
```

### Build

Invoke builds directly on the `Wiki` instance using CLI-aligned arguments:

```python
from pathlib import Path
from wiki import Wiki

w = Wiki.load("wiki.yml")
result = w.build(
    output_dir=Path("_site"),
    render=False,
    no_check=False,
    verbose=False,
)
if not result.ok:
    # preflight AuditReport on result.preflight when lint/check failed
    ...
print(result.page_count, result.written_paths)
```

`BuildError` is raised when the output directory overlaps wiki inputs or config root.

### Link, render, export, format, and query

`Wiki` instances expose direct, option-free methods for executing wiki operations matching the CLI parameters:

```python
# Run on the whole wiki with clean OOP methods:
link_report = w.link(check=True)
render_report = w.render(check=True)
export_result = w.export(format="turtle", mode="expanded")
fmt_report = w.format(check=True)

# Run a SPARQL query directly:
query_res = w.query("SELECT ?s WHERE { ?s ?p ?o }")

# Start local server:
w.serve(port=8080)

# Or target specific files:
from pathlib import Path
fmt_report = w.format([Path("docs/wiki/Some_Page.md")])
```

### Scaffold

Init logic is available as a static helper:

```python
from pathlib import Path
from wiki import Wiki, InitOptions

options = InitOptions(...)  # see wiki.schemas.init
result = Wiki.init(Path.cwd(), options, git=False)
print(result.written_paths)
```

Interactive `wiki init` still owns prompts, `--git`, and preflight guards in the CLI.

## TypeScript SDK

The npm package ships a type-safe TypeScript SDK for Node projects. It uses the same private Python environment as the npm `wiki` command and shells out to the Python CLI with safe argv arrays.

```bash
npm install wazootech-wiki
```

ESM usage:

```ts
import { Wiki } from "wazootech-wiki";

const wiki = Wiki.load({ config: "docs/wiki.yml" });

await wiki.check({ strict: true });

const results = await wiki.query({
  query: "SELECT ?s WHERE { ?s ?p ?o }",
  format: "json",
});
```

CommonJS usage:

```js
const { Wiki } = require("wazootech-wiki");
```

The SDK exposes methods that mirror the CLI surface: `check`, `lint`, `fmt`, `render`, `build`, `export`, `link`, `query`, `graphList`, `serve`, `init`, `install`, `update`, `remove`, `mcp`, and `upgrade`. Options use TypeScript-friendly camelCase names and map to the corresponding CLI flags.

Most report-producing methods return a `WikiCommandResult` containing `ok`, `exitCode`, `stdout`, `stderr`, and the executed command argv. JSON-capable commands can parse structured output: `query({ format: "json" })` returns parsed JSON by default, and `export({ format: "dict" })` or `export({ format: "json-ld" })` includes parsed `data`.

Generated reference docs are available at [TypeScript API Reference](TypeScript_API_Reference.md).

Because the SDK is a thin binding, updates to `src/wiki/cli.py` subcommands or flags must be reflected in `npm/src/wiki.ts`, `npm/src/types.ts`, and `npm/test-wiki-api.js` in the same change.

## Layout slot contract

Page layouts substitute `%wiki.*%` slots. `build_layout_context` validates a typed `LayoutContext` (internal schema in `wiki.schemas.layout`) before markup and slot substitution. The contract boundary for tests and downstream layout tools is `wiki.site.layout_tokens.build_layout_token_map`. Contract tests assert the context key tree, markup paths, and that every supported slot is produced by that map. See [Wiki Configuration](Wiki_Configuration.md#layout-slots).

## Exceptions

| Exception      | Typical cause                          |
| -------------- | -------------------------------------- |
| `WikiError`    | Base class for domain failures         |
| `BuildError`   | Unsafe or overlapping build output dir |
| `UpgradeError` | Frozen binary or pip upgrade failure   |

## CLI parity

Library operations mirror subcommands documented under [wiki](wiki.md). The CLI adds silence-on-success, `--strict`, pipe formats, and exit codes. For agent workflows that shell out, prefer `skills/wiki/scripts/audit.sh`; for in-process CI, prefer `Wiki` and typed reports.

## Related

- [wiki](wiki.md) — command reference
- [Wiki Configuration](Wiki_Configuration.md) — config semantics
- [Design Philosophies](Design_Philosophies.md) — silent success, composable stdout
