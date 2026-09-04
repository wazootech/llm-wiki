# Changelog

## Unreleased

## 0.1.22 — 2026-09-04

### Added

- `wiki init --template` scaffolds new wikis from the
  [wiki-templates](https://github.com/wazootech/wiki-templates) monorepo.
  ([#233](https://github.com/wazootech/wiki/issues/233))
- `i` alias for the `wiki install` subcommand.
  ([#265](https://github.com/wazootech/wiki/pull/265))
- Query-first wiki MCP server (`wiki mcp`), documented in `docs/wiki/wiki_mcp.md`.
  ([#209](https://github.com/wazootech/wiki/issues/209))
- TypeScript SDK methods for `install`, `update`, `remove`, `mcp`, and
  `graphList`, with CLI option types generated from the Pydantic
  `COMMAND_MODELS`. ([#283](https://github.com/wazootech/wiki/pull/283),
  [#287](https://github.com/wazootech/wiki/pull/287))
- wiki-sync skill for Git-anchored code-wiki maintenance.
  ([#247](https://github.com/wazootech/wiki/pull/247))

### Changed

- The CLI↔TypeScript mirror contract is now enforced in CI: every CLI command
  and `--flag` must have a corresponding SDK method and option.
  ([#288](https://github.com/wazootech/wiki/pull/288))
- Memory orchestration moved to a GitHub Actions cron.
  ([#263](https://github.com/wazootech/wiki/pull/263))
- Docs reorganized: `Wiki_CLI`/`Wiki_Subcommand_*` pages renamed to
  `wiki`/`wiki_*`, and template references point at the wiki-templates
  monorepo. ([#223](https://github.com/wazootech/wiki/issues/223),
  [#242](https://github.com/wazootech/wiki/issues/242))
- Pre-commit hook runs prettier on staged files; LF line endings enforced via
  `.gitattributes`.

### Fixed

- `wiki init` on non-interactive stdin no longer hangs on the namespace
  prompt; it scaffolds an empty wiki instead.
  ([#289](https://github.com/wazootech/wiki/pull/289))
- Sphinx docs fail the build on any warning; typedoc fails on undocumented
  public API. ([#285](https://github.com/wazootech/wiki/pull/285),
  [#284](https://github.com/wazootech/wiki/pull/284))
- Markdown formatting fixes applied with `wiki fmt`.
  ([#230](https://github.com/wazootech/wiki/pull/230))
## 0.1.21 — 2026-07-12

### Fixed

- Preserve title-cased file-derived graph URIs so `wiki:` CURIE references match Wikipedia-style filenames, and keep nested frontmatter blank nodes collision-safe with RDFLib `BNode` instances. ([#215](https://github.com/wazootech/wiki/issues/215))
- Use the standard `macos-13` Intel runner for standalone release builds so the release workflow starts reliably.

## 0.1.19 — 2026-07-01

### Fixed

- `datetime.datetime` values are now correctly serialized as `xsd:dateTime` instead of `xsd:date`. ([#172](https://github.com/wazootech/wiki/issues/172), [#176](https://github.com/wazootech/wiki/pull/176))
- Removed redundant `"markdown"` / `"obsidian"` values from `_LINK_STYLES` (legacy aliases remain supported via `_LEGACY_LINK_STYLE_MAP`). ([#174](https://github.com/wazootech/wiki/issues/174), [#178](https://github.com/wazootech/wiki/pull/178))
- Deduplicated `_LINK_STYLES` and `_LEGACY_LINK_STYLE_MAP` constants between `wiki_config.py` and `init.py` — the latter now imports from the former. ([#171](https://github.com/wazootech/wiki/issues/171), [#178](https://github.com/wazootech/wiki/pull/178))
- Silently swallowed exceptions in `parser.py` (`document_data_from_path`, `frontmatter_from_path`, `split_document_body`) now log at debug level. ([#173](https://github.com/wazootech/wiki/issues/173), [#179](https://github.com/wazootech/wiki/pull/179))
- `InitOptions.graph_implicit_types_policy` now validates against `{"fallback", "append"}` instead of accepting any string. ([#175](https://github.com/wazootech/wiki/issues/175), [#180](https://github.com/wazootech/wiki/pull/180))

### Added

- `wiki install` command — fetch and lock external git sources declared in `sources:` block of `wiki.yml`. With a URL argument, adds the source to wiki.yml first. Supports `#ref` pinning. ([#148](https://github.com/wazootech/wiki/issues/148), [#164](https://github.com/wazootech/wiki/pull/164))
- `wiki remove` command — remove a source from wiki.yml, its `.wiki/sources/` cache, and wiki.lock. ([#164](https://github.com/wazootech/wiki/pull/164))
- `wiki update` command — check locked sources for newer commits and update wiki.lock. Supports `--dry-run` and per-source filtering. ([#164](https://github.com/wazootech/wiki/pull/164))
- `sources:` config block in wiki.yml — declare external git repos with optional `ref` (branch/tag/commit) and `path` (subdirectory). Validated with `extra=forbid` like all other blocks. ([#148](https://github.com/wazootech/wiki/issues/148))
- `wiki.lock` lockfile — machine-authored JSON recording resolved commit SHAs for reproducible builds. ([#148](https://github.com/wazootech/wiki/issues/148))
- Resolved source paths auto-appended to `wiki.inputs` in `Wiki.load()` so graph, check, and build pipelines pick them up transparently.
- `wiki install` now accepts GitHub `owner/repo` shorthand — `wiki install EthanThatOneKid/solar-system-wiki` expands to the full `https://github.com/EthanThatOneKid/solar-system-wiki.git` URL automatically.
- `wiki init` now scaffolds a `.gitignore` that excludes `.wiki/` (source cache) and `_site/` (build output).
- **Recursive (transitive) dependency resolution** — `wiki install` reads each cloned source's `wiki.yml` to discover its own `sources:` block, recursively fetching and locking transitive dependencies. Circular dependency chains are detected and raise an error. Name-and-ref conflicts are detected and raise an error.
- **Lockfile v2** — `LockedSource` now tracks `required_by: list[str]` recording which sources depend on each entry (empty for top-level sources declared in the root `wiki.yml`). Backward-compatible: v1 lockfiles load with `required_by` defaulting to `[]`.
- **Orphan cleanup on `wiki remove`** — when a source is removed, transitive sources that are no longer required by any remaining top-level source are automatically cleaned up (cache and lockfile entry removed), cascading through the dependency tree.
- **Transitive re-sync on `wiki update`** — after fetching new commits, `wiki update` re-discovers each source's declared transitive dependencies. Newly declared sources are installed and locked; orphaned sources are reported as warnings (not auto-removed).

### Dependency

- Added `ruamel.yaml` for comment-preserving YAML writes when `wiki install`/`wiki remove` edits wiki.yml.

## 0.1.18 — 2026-06-28

### Fixed

- `wiki upgrade` no longer fails when `wiki.yml` contains legacy `link.style: markdown` or `link.style: obsidian`. Old values are now accepted and automatically mapped to `standard` and `wikilink` respectively, with a deprecation warning. ([#134](https://github.com/wazootech/wiki/issues/134))

## 0.1.17 — 2026-06-28

### Added

- `wiki --version` flag prints the installed version ([#132](https://github.com/wazootech/wiki/issues/132)).
- `wiki init --site-layout` CLI flag for setting a custom page layout file ([#138](https://github.com/wazootech/wiki/pull/138)).
- Wikipedia-themed build files for the docs wiki: `docs/build.py`, `docs/layouts/wikipedia.html`, `docs/assets/wikipedia.js`.
- **Library-first Python API** ([#112](https://github.com/wazootech/wiki/issues/112)) — `Wiki` session, typed `AuditReport` / `Issue` and operation result models, direct `Wiki.build`, `Wiki.init`, `Wiki.link`, `Wiki.render`, `Wiki.export`, and `Wiki.format` methods, curated `wiki.__all__`, and `py.typed`. See [Wiki Programmatic API](docs/wiki/Wiki_Programmatic_API.md).
- Typed **layout context** models (`LayoutContext`) validated at `build_layout_context` with expanded layout slot contract tests ([#106](https://github.com/wazootech/wiki/issues/106)).

### Fixed

- Escape all raw HTML in wiki markdown rendering uniformly, including TOC/sidebar outline labels; strip SPARQL comment wrappers before site HTML rendering instead of passthrough ([#91](https://github.com/wazootech/wiki/issues/91), PR [#102](https://github.com/wazootech/wiki/pull/102))

### Changed

- Init/branding docs: Getting Started branding subsection; clarify tweak-comment workflow ([#107](https://github.com/wazootech/wiki/issues/107)).
- Page layouts use **`%wiki.*%` layout slots** instead of Jinja. Packaged layouts: `layouts/wikipedia.html` (Vector UI, copied on init), `index.html` (minimal full page when `site.layout` is unset). Bundled styles ship as linked `assets/wikipedia.css` (layout + metadata-format + Pygments merged); runtime `site.inline_css` removed.
- Document npm/npx install parity with `wiki` subcommands (README, Getting Started, Wiki CLI, wiki agent skill).
- Consolidate agent skills — `wiki-install`, `wiki-create`, `wiki-improve`, and `wiki-deploy` merge into single **`wiki`** skill under `skills/wiki/` with workflow references and `verify-cli.sh` / `audit.sh` scripts.
- Rename `link.style` values: `markdown` → `standard`, `obsidian` → `wikilink` (`wiki init --link-style`, validators, docs). Old values fail at load (no aliases).
- Rename release workflow to [`.github/workflows/release.yml`](.github/workflows/release.yml) (update npm and PyPI trusted publisher workflow filenames to match).
- Rename Pages deploy workflow to [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml).
- `wiki init` removes `--force`, `--site-name`, and `--site-theme-color`. Init requires a clean directory; re-scaffold in a new directory or remove existing scaffold files manually. Branding uses `<!-- wiki tweak: … -->` comments in scaffolded `assets/logo.svg` and `layouts/wikipedia.html`.

### Migration

- **Library API:** If you imported audit dict helpers or relied on `run_check` / `run_lint` returning `dict[str, Any]`, switch to `AuditReport` and `Issue` (`report.ok`, `report.errors`, `issue.code`). Prefer `from wiki import Wiki, AuditReport` for new integrations.

- Remove `--force`, `--site-name`, and `--site-theme-color` from scripts and CI. To customize logo letter or theme after init, edit tweak comments in `assets/logo.svg` and `layouts/wikipedia.html` instead.

- Replace Jinja `{{ page.* }}` / `{{ site.* }}` in custom layouts with `%wiki.*%` slots (see [Layout slots](docs/wiki/Wiki_Configuration.md#layout-slots)). Remove `<style>{{ site.inline_css }}</style>`; link `%wiki.base_url%/assets/wikipedia.css` instead.

- Fresh `wiki init` writes **`wiki.yml`** (scaffold source: `src/wiki/templates/wiki.yml`), `layouts/wikipedia.html`, `assets/wikipedia.css`, and sets `site.layout: layouts/wikipedia.html` by default. Existing **`wiki.yaml`** configs still load; rename manually to `wiki.yml` or remove before re-init. `--site-layout minimal` omits `site.layout` (packaged `index.html` fallback).

- Projects that copied `layouts/shell.html` from an earlier unreleased build should replace it with `layouts/wikipedia.html` and update `site.layout` accordingly. Use monolithic page layouts with `%wiki.body%` for rendered page content.

- Rename `site.layout` and `wazoo:layout` paths from `*.html.j2` to `*.html` if you have not already.

- Reinstall the consolidated skill: `npx skills add wazootech/wiki@wiki -g -y`

- Remove stale copies from `~/.agents/skills/` or project `.agents/skills/`: `wiki-install`, `wiki-create`, `wiki-improve`, `wiki-deploy`

- Wiki doc pages merged into [Wiki Skill](docs/wiki/Wiki_Skill.md); per-skill pages removed

- In `link:` rename `style: markdown` → `style: standard` and `style: obsidian` → `style: wikilink`:

```yaml
# Before
link:
  style: markdown   # or obsidian

# After
link:
  style: standard   # or wikilink
```

## 0.1.15 — 2026-06-14

### Fixed

- Release workflow keeps canonical `release.yaml` filename for npm OIDC trusted publishing; npm publish skips existing versions and verify step retries registry propagation.

## 0.1.14 — 2026-06-14

### Changed

- Consolidate [Wiki CLI templates](docs/wiki/wiki.md#ecosystem-templates) registry in Wiki_CLI: single shipped/planned table, SPARQL single-repo (`wiki-yasgui-template` absorbs Virtuoso scope), `wiki-{stack}-template` integration slugs, planned `wiki-astro-template` ([#96](https://github.com/wazootech/wiki/issues/96)). Slim README and downstream wiki pages to point at the canonical section; retire stale slugs (`sparql-service-template`, bare `nextjs-template`, `obsidian-quartz-template`, etc.).
- Remove `site.manifest` and `manifest.webmanifest`. Branding (site name, theme color, favicon, sidebar logo) lives in `site.layout` only; `wiki.yaml` `site:` keeps `layout`, `base_url`, and `url_style`. A brief 0.1.14 release added `--site-name` and `--site-theme-color` for logo SVG only; those init flags were removed before the next release — see Unreleased migration for the tweak-comment workflow.
- `wiki init` omits `lint:` keys that default to `off` (`headings`, `heading_levels`, `duplicate_headings`, `thematic_breaks`).
- Docs and agent skills use title-case H1 headings and sentence-case H2+ without numbered headings.

### Migration

- Delete the entire `site.manifest` block from `wiki.yaml`.
- Move branding into your `site.layout` file (for example `layouts/wikipedia.html`): edit sidebar label, `theme-color` meta tags, and asset URLs such as `%wiki.base_url%/assets/logo.svg`. Use `%wiki.*%` layout slots, not Jinja (see Unreleased migration).
- Replace legacy manifest placeholders and Jinja `{{ site.manifest.* }}` paths with literals or `%wiki.base_url%/assets/…` in custom layouts.
- Remove `<link rel="manifest">` and any dependency on built/served `manifest.webmanifest`.

## 0.1.13 — 2026-06-10

### Added

- `wiki-install` and `wiki-create` agent skills under `skills/` — install the CLI and scaffold a workspace with `wiki init` plus a light preferences wizard

### Fixed

- setuptools package discovery includes `wiki.schemas`, `wiki.site`, and `wiki.mdit_py_plugins` subpackages
- Default page layout spacing and copy-button click dead band
- Compacted JSON-LD output prunes `@context` to prefixes used in the document

### Changed

- Release workflow uses Node 24 for npm OIDC trusted publishing

## 0.1.11 — 2026-06-09

### Added

- `site.manifest` — Web App Manifest-shaped block (`name`, `short_name`, `theme_color`, `background_color`, `start_url`, `display`, `icons`) drives layout chrome, `{{ site.manifest.json }}` / `{{ site.manifest.url }}` placeholders, and `manifest.webmanifest` on `wiki build` / `wiki serve`
- `graph.implicit_types` and `graph.implicit_types_policy` (`fallback` | `append`) — vault-wide default `rdf:type` CURIEs for documents missing `type` / `@type`, or merged with explicit types when policy is `append` (SHACL shape documents skip append)

## Unreleased

### Added

- Hidden SPARQL queries in inline render blocks — wrap the fenced query in an HTML comment (`<!-- sparql:start` … `-->`) so built pages show only the results table; visible-query syntax is unchanged ([#73](https://github.com/wazootech/wiki/issues/73))
- JSON Schema frontmatter validation in `wiki check` — bind schemas on SHACL shape documents with `wazoo:jsonSchema` + `sh:targetClass`, or append per-page schemas; configurable via `check.frontmatter_schema` and `check.missing_schema_ref` ([#71](https://github.com/wazootech/wiki/issues/71))
- Standalone `wiki` executables for Linux, macOS, and Windows via PyInstaller — published to GitHub Releases with `SHA256SUMS` on each `v*` tag ([#77](https://github.com/wazootech/wiki/issues/77))
- Unified [`.github/workflows/release.yml`](.github/workflows/release.yml): PyPI, npm, and GitHub Release binaries in one workflow (replaces separate release workflows)
- `wiki-deploy` agent skill — GitHub Pages setup aligned with [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml); pip and uv workflow templates, deploy anti-patterns, and Pages `build_type` verification

### Changed

- `wiki init` no longer scaffolds starter JSON Schema files — SHACL-only `Person_Shape.md` is the default; add `wazoo:jsonSchema` bindings when you want JSON Schema validation
- Agent skills — restore `wiki-improve/scripts/audit.sh` (was empty in rename commit); `wiki-install` capability probe (`wiki fmt --help`) catches stale PATH installs; `wiki-create` default-on post-init `check --strict` with opt-out; stale-CLI handling aligned across create/deploy/improve; eval updates
- `wiki-create` skill — init flag reference is `wiki init --help` (removed duplicated `init-options.md`); README preflight and post-init `.gitignore` guidance; infer `--repo` from git/attachment; batch optional prefs; wiki-deploy handoff at clean exit
- `wiki-install` skill — `python3 -m pip` and pipx troubleshooting fallbacks; IDE pip tool vs terminal install on macOS
- `wiki-deploy` skill — forbid `uv pip install` without venv on standalone repos; eval for CI “No virtual environment found” footgun; embed uv/pip workflow templates wholesale (no install hybridization)
- [Getting Started](docs/wiki/Getting_Started.md) and [Wiki Skills](docs/wiki/Wiki_Skills.md) — refresh agent skills after Wiki CLI upgrades; avoid committing stale `.agents/skills/`
- `wiki upgrade` on standalone binaries prints GitHub Releases re-download instructions instead of calling pip
- `link.style` value `wikilink` renamed to `obsidian` (standard Markdown vs Obsidian wikilinks); `wiki init --link-style` and docs use the new names

### Fixed

- `wiki init --graph-implicit-types-policy` accepts `fallback` or `append` (was incorrectly `override`) ([#72](https://github.com/wazootech/wiki/issues/72))

### Changed (breaking)

- Layout template context uses nested namespaces (`site.*`, `page.*`, `wiki.*`) instead of flat keys (`page_title`, `site_manifest_name`, …); update custom `.html.j2` layouts (see Migration)

- `wiki-best-practices` agent skill renamed to `wiki-improve` — reinstall with `npx skills add wazootech/wiki@wiki-improve -g -y`; improve-style advisor framing and prioritized findings report; `audit.sh` pipeline unchanged

- Remove `site.title` and `site.theme_color`; use `site.manifest.name` and `site.manifest.theme_color` instead

- Remove `graph.wiki_base`; auto-generated document IRIs default from `graph.context.wiki` with optional `graph.base_iri` override

- Rename init flag `--graph-wiki-base` → `--graph-context-wiki` (sets `graph.context.wiki` in the scaffold)

- Rename `graph.uri_ext` → `graph.include_file_extension`, `graph.default_types` → `graph.implicit_types`, and `graph.default_types_policy` → `graph.implicit_types_policy`

- **CLI flags** align with `wiki.yaml` block paths: `--wiki-inputs` (was `--vault-inputs`, was `--input-dir`), `--site-base-url` (was `--base-url`), `--site-url-style` (was `--url-style` / serve `--style`), `--graph-context-wiki` (was `--wiki-base` / `--graph-wiki-base`), `--graph-content-predicate` (was `--content-predicate`); `--link-style` unchanged. Remove `--wazoo` / `--graph-wazoo`; `graph.context.wazoo` stays fixed in the init scaffold like other built-in prefixes.

- Rename `wiki.input_dirs` → `wiki.inputs` and `wiki.asset_dirs` → `wiki.assets` (was `vault.xxx` before the top-level block rename)

- Load `wiki.yaml` / `wiki.json` through strict Pydantic schema validation (`extra='forbid'` on every block)

- **Unified Config:** remove the flat runtime `Config` and `WikiFileConfig` / `from_file_config()` bridge; the loaded model matches yaml blocks (`config.wiki.inputs`, `config.site.base_url`, etc.). Programmatic callers must use nested construction or `Config.for_root()`.

- Rename root loader type `WikiConfig` → `Config` (`from wiki.config import Config`); **`WikiConfig`** reserved for a future `wiki:` yaml section

- Rename exported section types: `VaultBlock` → `VaultConfig` → `WikiConfig`, …; add `FmtConfig` for `Config.fmt` (`.options` / `.toml`)

- Rename `DEFAULT_CHECK_RULES` / `DEFAULT_LINT_RULES` → `DEFAULT_CHECK_CONFIG` / `DEFAULT_LINT_CONFIG`

### Changed

- Page layouts render through Jinja2 (`.html.j2`) instead of `{placeholder}` string substitution; `wiki init` copies `layouts/default.html.j2` from the packaged template
- Packaged default CSS is `layout_default.css` (plain CSS, not a Jinja template)

### Changed (breaking)

- Rename `site.layout` and `wazoo:layout` targets from `*.html` to `*.html.j2`
- Replace `{key}` layout tokens with Jinja `{{ key }}`; CLI-injected HTML/JSON slots use safe markup (or explicit `| safe` for hand-authored template HTML)

### Changed

- Packaged init templates renamed to `layout_default.html.j2` and `layout_default.css`; default page CSS moved out of `site.py` into the template bundle
- Internal domain types (`PageRoute`, `BrokenLink`, `VirtualPage`, `InitOptions`, etc.) live under `wiki.schemas` as Pydantic models; `Config.check` and `Config.lint` are `CheckConfig` / `LintConfig` instances (not plain dicts)
- `Context` (RDF prefix bindings) lives in `wiki.context`; `Config.context` is a computed property from `graph.context`

### Migration

- Agent skill `wiki-best-practices` → `wiki-improve`: `npx skills add wazootech/wiki@wiki-improve -g -y` (remove stale `wiki-best-practices` from `~/.agents/skills/` or project `.agents/skills/` if present). Wiki doc page renamed to [Wiki Skill improve](docs/wiki/Wiki_Skill_improve.md).
- **Layout template variables (breaking):** flat keys removed; use nested paths in custom `.html.j2` files:

| Flat (remove)                   | Nested (use)                                   |
| ------------------------------- | ---------------------------------------------- |
| `site_base_url`                 | `site.base_url`                                |
| `site_url_style`                | `site.url_style`                               |
| `site_manifest_name`            | `site.manifest.name`                           |
| `site_manifest_theme_color`     | `site.manifest.theme_color`                    |
| `site_manifest_url`             | `site.manifest.url`                            |
| `manifest_json`                 | `site.manifest.json`                           |
| `logo_svg`                      | `site.logo_svg`                                |
| `inline_css`                    | `site.inline_css`                              |
| `page_title`                    | `page.title`                                   |
| `page_content`                  | `page.content`                                 |
| `page_kind`                     | `page.kind`                                    |
| `body_class`                    | `page.body_class`                              |
| `layout_class` / `layout_label` | `page.layout.class` / `page.layout.label`      |
| `type_label`                    | `page.type_label`                              |
| `infobox_html` / `toc_html` / … | `page.nav.infobox` / `page.nav.toc` / …        |
| `metadata_*_html`               | `page.metadata.tool` / `.tab` / `.pane`        |
| `source_markdown`               | `page.source`                                  |
| `all_pages_json`                | `wiki.pages_json`                              |
| `current_slug_json`             | `page.slug_json` (plus new `page.slug` string) |

See [Wiki Configuration — Template variables](docs/wiki/Wiki_Configuration.md#template-variables).

1. In `wiki:` rename path keys:
   - `input_dirs` → `inputs`
   - `asset_dirs` → `assets`
1. In `graph:` rename keys:
   - `uri_ext` → `include_file_extension`
   - `default_types` → `implicit_types`
   - `default_types_policy` → `implicit_types_policy`
   - `wiki_base` → remove; set `context.wiki` instead (optional `base_iri` when document IRIs must differ from the `wiki:` namespace)
1. Programmatic imports: root loader is `Config` from `wiki.config` (was `WikiConfig`); section types from `wiki.schemas` (`WikiConfig` (was `VaultConfig`), `CheckConfig`, `FmtConfig`, etc.); `DEFAULT_CHECK_CONFIG` / `DEFAULT_LINT_CONFIG` from `wiki.config`; `Config.fmt` is `FmtConfig | None` with `.options` / `.toml`
1. In `site:` move branding into `manifest:`:
   - `title` → `manifest.name`
   - `theme_color` → `manifest.theme_color`
1. In `link:` rename `style: wikilink` → `style: obsidian` (default remains `markdown`)
1. Page layouts:
   - Rename `site.layout` and `wazoo:layout` paths from `*.html` to `*.html.j2`
   - Replace flat template keys with nested Jinja paths (`{{ page.title }}`, `{{ site.manifest.name }}`, …; see [Template variables](docs/wiki/Wiki_Configuration.md#template-variables))

## 0.1.9 — 2026-06-08

### Added

- `link.style` (`markdown` default, or `wikilink`) controls `wiki link --apply` output format
- `lint.link_style` convention audit flags wikilinks in body prose when `link.style` is `markdown`
- `site.title` drives layout chrome (`{site_title}`) and the logo glyph on build/serve

### Changed (breaking)

- **Nested config blocks only:** settings live under `vault:`, `graph:`, `site:`, and `link:`; unknown top-level keys fail at load (no `wiki config migrate`)
- Remove `check.forbidden_layout_keys`; `template` / `wiki:template` frontmatter are ordinary properties (layout selection uses `wazoo:layout` only)
- Move `check.broken_links` to `lint.broken_links` in `wiki.yaml` (unknown `check` keys fail at load)
- **`wiki build`** preflight runs `lint` then `check` (unless `--no-check`)
- Split audit lanes: **`wiki check`** = integrity (SHACL, routes, collisions, layout); **`wiki lint`** = conventions including `lint.broken_links`
- Move `filename_pattern` and `headings` severities from `check:` to `lint:` in `wiki.yaml` (old keys fail at load)

### Changed

- `lint.headings` applies sentence-case checks to H2+ only; H1 title case is conventional
- `lint.headings` flags Setext underlined headings; vaults should use ATX `#` headings only
- Heading auditor skips thematic `---` inside fenced code and ignores capitalized link text in headings

### Migration

1. Group former top-level keys under blocks (unknown top-level keys fail at load):
   - `input_dirs`, `asset_dirs`, `exclude`, `filename_pattern` → `vault:`
   - `wiki_base`, `content_predicate`, `context` / `@context`, `uri_ext` → `graph:`
   - `site_title`, `wiki_page_layout` / `page_layout`, `base_url`, `url_style` → `site:` (`title`, `layout`, `base_url`, `url_style`)
   - `link_renames`, `link_style` → `link:` (`renames`, `style`)
   - `serve_api` → `sparql_service`
1. Move `check.broken_links` to `lint.broken_links`
1. Move `check.filename_pattern` and `check.headings` to `lint:` if still present
1. Add `\.md` to your `vault.filename_pattern` regex
1. Run `wiki lint` then `wiki check` in CI

## 0.1.8 — 2026-06-05

### Changed

- Require `snake_case` config keys only for top-level `wiki.yaml` settings
- Require `snake_case` nested `check` rule keys: `filename_pattern`, `broken_links`, and `headings`
- Fail fast on invalid config files, unknown keys, removed aliases, and malformed nested config blocks

### Fixed

- Surface config-load errors consistently through the CLI instead of silently falling back to defaults

## 0.1.7 — 2026-06-05

### Added

- `wiki fmt` subcommand for formatting wiki content
- Optional disk-backed graph cache support
- Configurable HTML template scaffolding for generated sites
- Heading and broken-link audits in `wiki check`
- Expanded docs and generated site content for CLI subcommands and wiki concepts

### Changed

- Simplified `wiki init` scaffolding and prompts
- Refined site generation and HTML template extraction

### Fixed

- Markdown link and microdata CURIE scanning in link audits
- Flaky SPARQL query ordering in docs checks

## 0.1.5 — 2026-06-01

### Added

- `wiki view <file>` command for terminal document rendering with Rich
- Rich dependency for ASCII-safe terminal output
- YAML, YML, and JSON document support alongside Markdown
- CURIE expansion for HTML microdata attributes
- Typed HTML rendering with infoboxes and `wiki:template` support
- In-process RDF graph cache so multiple SPARQL operations in one run share a single graph build; `--reload` on `query`, `render`, and `build --render`
- `wiki serve --watch` rebuilds the in-memory graph and SPARQL blocks when vault files change

### Changed

- Replaced on-disk graph cache (`.wiki/cache/`) and incremental render-state with runtime-only caching

### Fixed

- Linkify only known document slugs in SPARQL results
- Regenerate stale SPARQL blocks in docs

### Removed

- Loose blank node resolution keyed on name/givenName+familyName (`build_person_name_map`, `resolve_blank_nodes`)
- `--all`, `--rebuild-cache`, and `--no-cache` flags
