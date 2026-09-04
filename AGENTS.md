# Agent Guidelines

Welcome! This document outlines the style, hygiene, and design guidelines for managing and contributing to this wiki. These guidelines are enforced by `wiki fmt` (mechanical markdown), `wiki check` (integrity), and `wiki lint` (conventions) in the Wiki CLI (`wazootech-wiki` on PyPI). Canonical wiki-authoring detail lives in the wiki [Style Guide](docs/wiki/Style_Guide.md).

This repository dogfoods the docs wiki at `docs/wiki.yml` (`docs/wiki/`). Use **`-c docs/wiki.yml`** on wiki commands here so local runs match CI.

### Product naming

- **Wiki** — overall product name in prose (docs, skills, CHANGELOG).
- **Wiki CLI** — specifically for the command-line interface (`wiki` command).
- **Wiki Library** (or **Wiki Python API**) — specifically for the Python API/Library.
- **`wiki`** — the command and subcommands (`wiki fmt`, `wiki check`, …). Use for PATH checks, install verification, and shell examples.
- **`wazootech-wiki`** — Package name on PyPI and NPM.
- **Do not** write `wiki-cli` in user-facing text. Keep hyphenated forms only where they are literal identifiers (repo slugs, URL paths, test fixtures, `wiki:` CURIEs).

## Wiki rules

### Clean filenames

- **Rule:** Default user-facing examples should prefer **Wikipedia-style** filenames for ordinary pages (e.g., `Opal_Security.md`, `Gregory_Davidson.md`) — preserved capitalization and underscores. Do not default to lowercase kebab-case (`opal-security.md`). Reserve `index.md` only for folder index routes. Avoid spaces and other unsafe route characters.
- **Enforcer:** `lint.filename_pattern` in `wiki.yaml` (warning by default). Route safety (spaces, unsafe URL characters) always fails as an error in `wiki check`.

### Placeholder names

- **Rule:** When writing example wiki pages or fixtures that need placeholder
  people, default to **"Ethan"**, **"Gregory"**, and **"Sandra"** — not
  "Alice", "Ben", "Chad", or similar generic names.
- **Enforcer:** none — naming convention only, mirroring the workspace root
  AGENTS.md.

### Internal links

- **Rule:** Use standard Markdown links to other wiki pages (`Page_Name.md`). GFM relative links are also accepted. Do not use Obsidian-style `[[slug]]` wikilinks in this wiki. Ensure internal links point at existing documents.
- **Enforcer:** `lint.broken_links` (warning by default) — wikilinks, markdown page links, heading fragments, assets, and `wiki:` CURIEs in frontmatter and microdata. `lint.link_style` (warning by default) flags wikilinks in body prose when `link.style` is `standard`. Repair with `wiki link --fix-broken`; suggest missing links with `wiki link` / `wiki link --apply` (separate from check/lint — see [Design Philosophies](docs/wiki/Design_Philosophies.md)).

### Style guidelines

- **Rule:** Use ATX `#` headings only (no Setext underlines); wiki tooling does not index underlined headings for title, TOC, or fragment links.
- **Rule:** Use title-case H1 headings (page title; align with `headline` frontmatter). Use sentence-case H2+ headings (capitalize only the first word and proper nouns). Avoid numbered headings; keep headings concise and clear.
- **Rule:** Avoid using horizontal rules (`---`) for thematic breaks within page bodies.
- **Enforcer:** `wiki fmt` converts Setext underlines to ATX `#` headings. `lint.headings` (off by default; set to `warning` or `error` in `wiki.yaml`) flags sentence-case H2+ and numbered headings — not ATX syntax.

### Markdown flavor

Use Markdown links for all internal and external URLs.

### Formatting (`wiki fmt`)

- **Rule:** After editing any wiki page under `docs/wiki/` (including reference docs such as [Wiki Configuration](docs/wiki/Wiki_Configuration.md)), run `wiki fmt` on the changed files before commit. Do not hand-align markdown tables or list spacing — mdformat owns mechanical layout; CI fails on drift.
- **Enforcer:** `wiki fmt --check` in CI (same order as [wiki lint](docs/wiki/wiki_lint.md): fmt → lint → check).

## Developer notes

### Scope boundaries

Wiki CLI aims to be a one-stop semantic Markdown wiki toolchain, similar in spirit to Go/Deno-style batteries-included tooling for its domain. Keep core scope focused on trust (`check`, `lint`, `fmt`), intelligence (`query`, `render`, `export`), and publish/preview (`build`, `serve`) workflows: graph construction, SHACL and JSON Schema validation, RDF/JSON-LD export, SPARQL query/render workflows, static HTML build, local preview, and CI-friendly checks.

Before adding a subcommand, ask whether it strengthens the semantic Markdown wiki toolchain. If it belongs to validation, graph construction, RDF/JSON-LD/SPARQL interoperability, static publishing, local preview, or CI-friendly checks, it may belong in Wiki CLI. If it is generic authoring, Obsidian app control, vault search, daily notes, task/tag dashboards, sync, history, PDF/print conversion, or generic file/process automation, use or document existing primitives instead.

Do not add Wiki CLI features that duplicate existing primitives unless there is a clear semantic-wiki reason:

- Use Obsidian CLI or Obsidian plugins for app/vault authoring workflows: daily notes, append/read current note, templates, task lists, tags, tag dashboards, vault search, plugin reload, DevTools, screenshots, DOM/CSS inspection, and sync.
- Use shell tools for generic file operations, printing, process composition, text filtering, and one-off automation.
- Use Git for history, diff, branching, sync, and collaboration workflows.
- Use Pandoc or dedicated document tools for PDF/print/export formats outside Wiki CLI's semantic RDF/static HTML outputs.
- Use static-site templates or downstream apps for custom publish surfaces; Wiki CLI owns the artifact contract, not every frontend.

Compatibility is allowed at the edges. Wiki CLI may parse, validate, preserve, and render Obsidian-authored Markdown, including wikilinks, but should not become an Obsidian automation layer. Prefer standard Markdown links in this docs wiki.

### TypeScript bindings

The npm TypeScript API is a thin binding over the Python CLI, not a second implementation. When changing `src/wiki/cli.py` subcommands, flags, choices, or positional arguments, update `npm/src/wiki.ts`, `npm/src/types.ts`, and `npm/test-wiki-api.js` in the same PR. Run `npm run test:npm` before landing those changes.

The option-bag types in `npm/src/types.ts` are generated from the Pydantic `COMMAND_MODELS` models (`src/wiki/schemas/cli.py`): after changing a model's fields, aliases, or docstrings, run `npm run gen:cli-types` and commit the regenerated `npm/src/types.generated.ts`. The drift test (`npm/test-cli-drift.js`) fails CI when the committed generated file falls out of sync with the models, and it also verifies every `--flag` string the wrapper methods in `npm/src/wiki.ts` emit against the real Click option strings — rename a Click flag and the wrapper must be updated in the same PR or CI fails. The drift test also verifies every config-key reference in the scaffold template (`src/wiki/templates/wiki.yml`) and the docs against the `Config` schema (`src/wiki/schemas/wiki_config.py`) — rename a config-schema field and the template or docs must be updated in the same PR or CI fails.

### Running validations

Before submitting commits, format the wiki and verify against the active schema and guidelines. In this repo, mirror CI:

```bash
# 0. Python static analysis (requires dev deps)
uv sync --group dev
uv run ruff check .

# 1. Format (apply, then verify)
wiki -c docs/wiki.yml fmt
wiki -c docs/wiki.yml fmt --check

# 2. Conventions: broken links, filename pattern, headings, link style
wiki -c docs/wiki.yml lint --strict

# 3. Integrity: SHACL, JSON Schema frontmatter, route safety, layout frontmatter
wiki -c docs/wiki.yml check --strict

# 4. Stale inline SPARQL result blocks
wiki -c docs/wiki.yml render --check

# Verbose output
wiki -c docs/wiki.yml check -v
wiki -c docs/wiki.yml lint -v
```

`wiki link` is **report-only by default** — it lists missing wikilink opportunities but does not write files or fail the build. `wiki link --fix-broken` supports link hygiene for publishable wikis. `wiki link --apply` is optional wiki-gardening: useful when desired, but not required for validation, publishing, or Obsidian compatibility. CI gates link hygiene only if `wiki link --check` is wired in.

For library-level validation and build in Python (without subprocess), see [Wiki Python Library](docs/wiki/Wiki_Programmatic_API.md). Unit tests target `Wiki` class methods under `tests/`.

### Deploy configuration

- Platform: GitHub Pages
- Production URL: https://wiki.wazoo.dev
- Deploy workflow: `.github/workflows/deploy.yml`
- Verification: after landing docs/site changes, wait for the **Deploy Wiki to Pages** workflow and verify the production URL loads.

### Release workflow

To ship a new version across PyPI and npm:

Use the release helper for the normal path:

```bash
uv run python scripts/release.py patch --message "Fix graph URI resolution" --issue 215 --full --push --watch
```

The helper bumps all enforced version surfaces (`pyproject.toml`, `package.json`, `package-lock.json`, `uv.lock`, `src/wiki/__init__.py`, and `docs/wiki/wiki.md`), updates `CHANGELOG.md`, regenerates inline SPARQL result blocks, formats docs, runs validation, commits, tags, pushes, and optionally watches GitHub Actions.

Manual fallback:

1. **Bump version** in all enforced places: `pyproject.toml`, `package.json`, `package-lock.json`, `uv.lock`, `src/wiki/__init__.py`, and `docs/wiki/wiki.md` (they must match — CI verifies this).
1. **Update `CHANGELOG.md`** with the new version's entries.
1. **Regenerate docs outputs** with `wiki -c docs/wiki.yml render`, then run `wiki -c docs/wiki.yml fmt` on touched docs.
1. **Commit and push** the version bump. Tag it with `v<VERSION>` (e.g., `v0.1.18`).
1. **Dispatch the release** — either push the `v*` tag, or run the workflow manually from `Actions > Release > Run workflow`. The workflow has skip-toggles for PyPI, npm, and standalone binaries.
1. **Verify** — the workflow publishes to PyPI (trusted publishing), npm (provenance), and attaches standalone binaries to a GitHub Release with auto-generated release notes.

The release workflow is at `.github/workflows/release.yml`. It is the **only** path for publishing to registries — do not `npm publish` or `uv publish` by hand.

Workflow inputs (all optional):

- `skip_pypi` — skip PyPI publish
- `skip_npm` — skip npm publish
- `skip_binaries` — skip standalone binaries and GitHub Release

### Config schema changes

When changing `wiki.yaml` schema or rejecting invalid keys:

- **Fail fast** with allowlist validation (`unknown top-level keys`, `Invalid wiki keys`, etc.).
- **Do not** add per-key rename hints in error messages (e.g. "`input_dirs` → use `wiki.input_dirs`"). These tables are bloat, drift from the schema, and often suggest wrong mappings.
- **Do not** add `wiki config migrate`, batched alias tables, or other backwards-compat loaders unless the user explicitly requests migration support.
- **Do** document breaking moves in `CHANGELOG.md` (Migration section) and [Wiki Configuration](docs/wiki/Wiki_Configuration.md).

Upgrade narrative belongs in docs and release notes, not in runtime error strings. **After editing `Wiki_Configuration.md`, run `wiki -c docs/wiki.yml fmt` on that file** (tables and long sections drift easily).

### Architecture

See [CONTEXT.md](CONTEXT.md) for domain language and [Wiki Configuration](docs/wiki/Wiki_Configuration.md) for config semantics (`check` vs `lint` vs `fmt`).