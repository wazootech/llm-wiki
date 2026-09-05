---
type: TechArticle
headline: Wiki Configuration
description: Reference for wiki.yaml, wiki.yml, and wiki.json (Config).
---

# Wiki Configuration

The CLI loads **Config** from `wiki.yml`, `wiki.yaml`, or `wiki.json` in the working directory (or from `-c path`).

The in-memory **Config** model uses the same nested blocks as the file (`wiki`, `graph`, `site`, `link`, `check`, `lint`, `fmt`, `sparql_service`). There is no separate flat runtime shape. `Config.load()` validates the file, injects `config_root` (the directory containing the config file), and resolves relative paths under `wiki` and `site`. Library and test code can construct configs with `Config(wiki={...}, config_root=path)` or `Config.for_root(path, wiki={...})`.

Config files are validated strictly through a Pydantic schema (`extra='forbid'` on every block). Unknown keys, removed aliases, wrong nested keys under `check`, `lint`, or `sparql_service`, invalid syntax, or a non-mapping top level all fail immediately instead of being ignored.

JSON configs may use `graph.context` or `graph.@context` for prefix maps (JSON-LD compatible).

## Overview

### Terminology

| Label               | Meaning                                                                                                                                                                 |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Schema optional** | Key or block may be omitted; Pydantic applies a default. No yaml key is strictly required for `Config.load()` to succeed.                                               |
| **Init**            | Written by `wiki init` ([`wiki.yml`](https://github.com/wazootech/wiki/blob/main/src/wiki/templates/wiki.yml)); omitting an Init key is the same as the schema default. |
| **Recommended**     | Not enforced by schema, but you typically set it for a real wiki (for example `graph.context.wiki`, `wiki.filename_pattern`, `site.layout`).                            |
| **Always on**       | Behavior not gated by yaml severities (route safety, URL collisions, built-in RDF prefixes).                                                                            |

### Audit lanes

Three audit lanes map to three commands:

| Lane       | Command      | YAML block | Purpose                                                         |
| ---------- | ------------ | ---------- | --------------------------------------------------------------- |
| Integrity  | `wiki check` | `check:`   | SHACL, JSON Schema frontmatter, layout file existence           |
| Convention | `wiki lint`  | `lint:`    | Links, filename pattern severity, headings, link style in prose |
| Formatting | `wiki fmt`   | `fmt:`     | Mechanical markdown (mdformat; inline mapping or TOML path)     |

**Rule placement:** Mechanical markdown belongs under **`fmt:`**. Wiki policy and link conventions belong under **`lint:`**. SHACL, JSON Schema, and layout keys belong under **`check:`** — never under `lint:`. See [Style Guide](Style_Guide.md) for the full matrix.

- Putting a regex under `check.filename_pattern` fails at load with a hint.
- `check.filename_pattern` and `check.headings` fail at load — use `lint.filename_pattern` and `lint.headings`.

Relative **`--input`** paths on the CLI resolve against the config file directory (same as paths in yaml), not the shell cwd.

### Blocks

Top-level blocks follow a **compile pipeline** plus **audit lanes**, not arbitrary grouping. `wiki init` and [docs/wiki.yml](https://github.com/wazootech/wiki/blob/main/docs/wiki.yml) use the same order as the packaged scaffold [`wiki.yml`](https://github.com/wazootech/wiki/blob/main/src/wiki/templates/wiki.yml).

| Block             | Role                                                  | Command(s)                        | Schema   | Init scaffold     |
| ----------------- | ----------------------------------------------------- | --------------------------------- | -------- | ----------------- |
| `wiki:`           | Corpus on disk — inputs, assets, filename regex       | `check`, `lint`, `build`, `serve` | optional | yes               |
| `graph:`          | RDF compile — prefixes, document IRIs, body literals  | `check`, `query`, `render`        | optional | yes               |
| `site:`           | Publish routing — layout path, URL prefix, path style | `build`, `serve`                  | optional | yes               |
| `link:`           | `wiki link` apply format and rename repair map        | `wiki link`                       | optional | yes               |
| `check:`          | Integrity severities                                  | `wiki check`                      | optional | yes               |
| `lint:`           | Convention severities                                 | `wiki lint`                       | optional | yes               |
| `sources:`        | External data sources (git repos)                     | `wiki install`, `wiki remove`     | optional | commented example |
| `sparql_service:` | Opt-in SPARQL HTTP on `wiki serve`                    | `wiki serve`                      | optional | commented example |
| `fmt:`            | Mechanical markdown via mdformat                      | `wiki fmt`                        | optional | inline mapping    |

**Order in the file:** source and semantics first (`wiki`, `graph`), then publish and authoring (`site`, `link`), then severity tables (`check`, `lint`), optional serve (`sparql_service`), then `fmt` last.

**Split keys** — policy lives in one block, severity or tooling in another:

- **`wiki.filename_pattern`** — the regex string. **`lint.filename_pattern`** — how strictly to flag violations (`error`, `warning`, or `off`).
- **`link.style`** — what `wiki link --apply` inserts (`standard` page links or `wikilink`). **`lint.link_style`** — whether Obsidian `[[wikilinks]]` in body prose are flagged when `link.style` is `standard`.

For why `check`, `lint`, `fmt`, and `wiki link` are separate commands, see [Design philosophies](Design_Philosophies.md#check-lint-fmt-and-link).

### Always on

These apply regardless of yaml severities:

- **Route safety** — unsafe URL characters and spaces in routes (`wiki check`).
- **Output URL collisions** — duplicate built routes (`wiki check`).
- **SHACL** — when shape documents exist in the corpus (`wiki check`).
- **Built-in RDF prefixes** — `schema`, `wiki`, `foaf`, `rdf`, `rdfs`, `xsd`, `owl`, `dc`, `dcterms`, `sh`, `wazoo` are always merged at runtime; yaml `graph.context` entries override or add.

## Wiki (`wiki:`)

```yaml
wiki:  # optional block
  input: [wiki]                    # default [wiki]; init writes
  assets: [assets]                  # default [assets] if assets/ exists, else []; init writes
  exclude: []                         # default []; init omits
  filename_pattern: "[A-Za-z0-9_()-]+\\.md"  # no default; recommended; init writes
```

| Key                | Required               | Default                                     | Init   | Audited by                                 |
| ------------------ | ---------------------- | ------------------------------------------- | ------ | ------------------------------------------ |
| `input`            | optional               | `[wiki]`                                    | writes | indexing (`build`, `check`, `lint`, `fmt`) |
| `assets`           | optional               | `[assets]` when `assets/` exists, else `[]` | writes | `wiki build` (static copy)                 |
| `exclude`          | optional               | `[]`                                        | omits  | indexing (skipped paths)                   |
| `filename_pattern` | optional (recommended) | unset — no regex check until set            | writes | `wiki lint` (`lint.filename_pattern`)      |

Page URLs come from paths under `wiki.input`: `wiki/Alice.md` → `/wiki/Alice/` with default `site.base_url` and `site.url_style: dir`. `index.md` in a folder owns that folder’s route (for example `wiki/index.md` → `/wiki/`).

See [Filename conventions](#filename-conventions) for regex patterns.

## Graph (`graph:`)

RDF and document URI settings for graph build, `wiki query`, microdata, and SHACL.

```yaml
graph:  # optional block
  # base_iri: unset → graph.context.wiki → https://wiki.example.org/
  content_predicate: schema:articleBody   # unset by default; init writes when flagged
  include_file_extension: false           # default false; init omits (commented)
  implicit_types: []                      # default []; init omits (commented)
  implicit_types_policy: fallback         # default fallback; init omits (commented)
  context:                                # merges with built-in prefixes; init writes
    schema: https://schema.org/
    wiki: https://example.org/wiki/       # recommended
    wazoo: https://schema.wazoo.dev/
    foaf: http://xmlns.com/foaf/0.1/
    dc: http://purl.org/dc/elements/1.1/
    dcterms: http://purl.org/dc/terms/
    sh: http://www.w3.org/ns/shacl#
    xsd: http://www.w3.org/2001/XMLSchema#
```

| Key                      | Required                       | Default                                                    | Init                                    | Audited by                                        |
| ------------------------ | ------------------------------ | ---------------------------------------------------------- | --------------------------------------- | ------------------------------------------------- |
| `base_iri`               | optional                       | unset → `graph.context.wiki` → `https://wiki.example.org/` | commented example                       | document IRIs, `wiki query`                       |
| `context` / `@context`   | optional (recommended: `wiki`) | built-in prefixes only when unset                          | writes extended map                     | CURIE expansion, SHACL, microdata                 |
| `content_predicate`      | optional                       | unset — no body literals in graph                          | writes when `--graph-content-predicate` | SPARQL full-text                                  |
| `include_file_extension` | optional                       | `false`                                                    | omits (commented)                       | document URI generation                           |
| `implicit_types`         | optional                       | `[]`                                                       | omits (commented)                       | default `rdf:type` on untyped pages               |
| `implicit_types_policy`  | optional                       | `fallback`                                                 | omits (commented)                       | `fallback` or `append` (SHACL shapes skip append) |

When `implicit_types_policy` is `append`, frontmatter types are unioned with `implicit_types` (deduped by resolved URI).

## Site (`site:`)

Default page layout and routing for `wiki build` / `wiki serve`. Branding and chrome → [Page layout](#page-layout).

```yaml
site:  # optional block
  layout: index.html   # unset → built-in minimal fallback layout
  base_url: /wiki                   # default /wiki; init writes
  url_style: dir                    # default dir; init writes
```

| Key         | Required               | Default                               | Init   | Audited by                                                                          |
| ----------- | ---------------------- | ------------------------------------- | ------ | ----------------------------------------------------------------------------------- |
| `layout`    | optional (recommended) | unset — packaged minimal `index.html` | writes | `wiki build`, `wiki serve`; `check.missing_layout_file` for per-page `wazoo:layout` |
| `base_url`  | optional               | `/wiki` (`""` allowed for site root)  | writes | routes, layout `%wiki.base_url%`                                                    |
| `url_style` | optional               | `dir` (`file` → `slug.html`)          | writes | output paths; overridable per CLI run                                               |

`site:` does not carry site name, theme color, favicon, or sidebar logo. If you want custom styling, write a custom layout template file and place custom assets under the `wiki.assets` directory, then configure `site.layout` to point to it.

CLI flags on `wiki build` and `wiki serve` can override `site.base_url` and `site.url_style` for a single run.

## Link (`link:`)

Settings for the `wiki link` command family (separate from `lint.link_style` severity).

```yaml
link:  # optional block
  style: standard       # default standard; init writes
  renames: {}           # default {}; init omits (commented example)
```

| Key       | Required | Default                               | Init              | Audited by               |
| --------- | -------- | ------------------------------------- | ----------------- | ------------------------ |
| `style`   | optional | `standard` (`wikilink` for wikilinks) | writes            | `wiki link --apply` only |
| `renames` | optional | `{}`                                  | commented example | `wiki link --fix-broken` |

`wiki link --fix-broken` preserves the existing link kind in each file; only `--apply` uses `link.style`.

## Integrity checks (`check:`)

Under `check`, each rule is `error`, `warning`, or `off`:

```yaml
check:  # optional block
  missing_layout_file: error    # default error; init writes
  frontmatter_schema: error     # default error; init writes
  missing_schema_ref: error   # default error; init writes
```

| Key                   | Required | Default | Init   | Audited by                           |
| --------------------- | -------- | ------- | ------ | ------------------------------------ |
| `missing_layout_file` | optional | `error` | writes | `wazoo:layout` paths missing on disk |
| `frontmatter_schema`  | optional | `error` | writes | JSON Schema validation failures      |
| `missing_schema_ref`  | optional | `error` | writes | unloadable `wazoo:jsonSchema` refs   |

Build-safety rules (unsafe URL characters, spaces in routes) and output URL collision detection always apply regardless of `check` settings.

### JSON Schema frontmatter (`wazoo:jsonSchema`)

`wiki check` validates frontmatter against JSON Schema in parallel with SHACL. Bind schemas on shape documents with **`wazoo:jsonSchema`** beside **`sh:targetClass`**; every page whose effective `type` matches that class must pass the bound schema(s). Individual pages may append extra schemas with their own `wazoo:jsonSchema` key (scalar or YAML list). Schema refs are local paths under the wiki config root (`.json` only) or remote `http(s)` URLs.

Shape binding documents are not validated as instances — only their schema refs are checked for loadability. Authoring detail: [SHACL](SHACL.md), [Style Guide](Style_Guide.md).

## Convention audits (`lint:`)

Under `lint`, each rule is `error`, `warning`, or `off`:

```yaml
lint:  # optional block
  broken_links: warning       # default warning; init writes
  filename_pattern: warning   # default warning; init writes
  headings: off               # default off; init omits
  heading_levels: off         # default off; init omits
  duplicate_headings: off     # default off; init omits
  thematic_breaks: off        # default off; init omits
  link_style: warning         # default warning; init writes
```

| Key                  | Required | Default   | Init   | Audited by                                                   |
| -------------------- | -------- | --------- | ------ | ------------------------------------------------------------ |
| `broken_links`       | optional | `warning` | writes | wikilinks, markdown links, fragments, assets, `wiki:` CURIEs |
| `filename_pattern`   | optional | `warning` | writes | full filename vs `wiki.filename_pattern`                     |
| `headings`           | optional | `off`     | omits  | ATX syntax, sentence-case H2+, numbered headings             |
| `heading_levels`     | optional | `off`     | omits  | heading level gaps (for example H1 then H3)                  |
| `duplicate_headings` | optional | `off`     | omits  | duplicate heading text on one page                           |
| `thematic_breaks`    | optional | `off`     | omits  | horizontal rules in body prose                               |
| `link_style`         | optional | `warning` | writes | Obsidian `[[wikilinks]]` when `link.style` is `standard`     |

ATX heading syntax is also enforced by **`wiki fmt`** (mdformat); Setext underlines are converted on format.

When `link.style` is `standard`, set `lint.link_style: off` to allow wikilinks in prose, or set `link.style: wikilink` for an Obsidian-style wiki.

## External data sources (`sources:`)

<!-- wiki:anchor external-data-sources-sources -->

Declare external git repositories that contribute wiki pages or RDF data to the graph. After adding a source, run `wiki install` to clone it and pin the resolved commit in `wiki.lock`.

Sources are read-only inputs during graph construction. Wiki composes root content and installed sources into one default query view, while preserving each installed source as a stable RDF named graph for provenance and SPARQL `GRAPH` clauses.

```yaml
sources:  # optional block
  - name: solar-system
    type: git
    url: https://github.com/EthanThatOneKid/solar-system-wiki.git
    ref: v0.1.0       # optional — branch, tag, or commit
    path: wiki        # optional — subdirectory within the repo
```

| Key    | Required | Default   | Init              | Command(s)     |
| ------ | -------- | --------- | ----------------- | -------------- |
| `name` | required | —         | omits (commented) | `wiki install` |
| `type` | required | `git`     | omits (commented) | `wiki install` |
| `url`  | required | —         | omits (commented) | `wiki install` |
| `ref`  | optional | `HEAD`    | omits (commented) | `wiki install` |
| `path` | optional | repo root | omits (commented) | `wiki install` |

Each source must have a unique `name`. The `type` field is currently limited to `git`. Unknown keys and unsupported types are rejected at config load time.

Run `wiki install` to fetch all declared sources and write `wiki.lock`. Check `wiki.lock` into version control for reproducible builds. The resolved source paths are automatically appended to `wiki.input` so the existing graph, check, and build pipeline picks them up.

Use `wiki graph list` to inspect the root graph and installed source graph URIs. Source graph URIs are derived from `graph.context.wiki`:

- Root corpus: `{graph.context.wiki}graphs/root`
- Installed source: `{graph.context.wiki}graphs/source/{source-name}`

Requested refs, resolved commits, source URLs, cache paths, and direct/transitive dependency metadata remain source metadata; they are not embedded in graph URIs.

**Transitive dependencies** are resolved recursively. After cloning each source, `wiki install` reads the source's own `wiki.yml` (or `wiki.yaml`/`wiki.json`) to discover its `sources:` block. Those transitive sources are fetched and locked too, forming a dependency tree. Circular dependency chains are detected and reported as errors. If two sources declare the same dependency name with different URLs or refs, install fails with a conflict error.

When a source is removed with `wiki remove`, transitive sources that are no longer needed by any remaining top-level source are automatically cleaned up (cache and lockfile entry removed).

After `wiki update`, newly declared transitive sources are installed, and orphaned sources are reported (but not auto-removed — run `wiki remove` to clean up).

The `.wiki/` source cache directory is not committed — `wiki init` scaffolds a `.gitignore` that excludes it (alongside the `_site/` build output).

To add a source without editing the config file by hand:

```bash
wiki install https://github.com/EthanThatOneKid/solar-system-wiki.git
# GitHub shorthand also works:
wiki install EthanThatOneKid/solar-system-wiki
```

The name is inferred from the URL (`solar-system`). To remove it:

```bash
wiki remove solar-system
```

See [wiki install](wiki_install.md) and [wiki remove](wiki_remove.md).

For the product framing behind recursive source composition, see [Recursive Semantic Datasets](Recursive_Semantic_Datasets.md).

## Serve API

Opt-in read-only SPARQL HTTP endpoint on `wiki serve`:

```yaml
sparql_service:  # optional block
  enabled: false        # default false; init omits (commented)
  path: /api/sparql     # default /api/sparql; init omits (commented)
```

| Key       | Required | Default       | Init              | Audited by                   |
| --------- | -------- | ------------- | ----------------- | ---------------------------- |
| `enabled` | optional | `false`       | commented example | `wiki serve` SPARQL endpoint |
| `path`    | optional | `/api/sparql` | commented example | reserved route on serve      |

`sparql_service.enabled` accepts YAML booleans and normalizes common string forms such as `true`, `false`, `on`, `off`, `yes`, `no`, `1`, and `0`; prefer native YAML booleans.

Example when enabled:

```yaml
sparql_service:
  enabled: true
  path: /api/sparql
```

The endpoint reuses the same SPARQL engine as `wiki query`. It is read-only and intended for local or development-oriented use. HTTP request forms, supported query types, and `Accept` negotiation are documented in [wiki serve](wiki_serve.md#sparql-endpoint).

It is **opt-in by default** because enabling it exposes raw graph-query access in addition to HTML preview.

`sparql_service.path` must not collide with the effective `site.base_url` page routes or the watch endpoint. Invalid values such as `/`, `/wiki`, `/wiki/foo`, or `/wiki/__watch` are rejected when `wiki serve` starts.

## Formatting (`fmt`)

Top-level **`fmt`** configures `wiki fmt` (mdformat). Two shapes are allowed — not both:

```yaml
fmt:  # optional block — inline mapping (init writes)
  wrap: "no"
  end_of_line: lf
  extensions: [gfm, front_matters, wikilink, toc, footnote]

# Pointer mode (optional alternative):
# fmt: .mdformat.toml
```

| Key / shape   | Required          | Default                                         | Init              | Audited by |
| ------------- | ----------------- | ----------------------------------------------- | ----------------- | ---------- |
| `wrap`        | optional (inline) | `"no"`                                          | writes            | `wiki fmt` |
| `end_of_line` | optional (inline) | `lf`                                            | writes            | `wiki fmt` |
| `extensions`  | optional (inline) | `[gfm, front_matters, wikilink, toc, footnote]` | writes            | `wiki fmt` |
| TOML path     | optional          | unset — see fallback chain below                | omits (commented) | `wiki fmt` |

Omit `fmt` entirely to use fallbacks: `config_root/.mdformat.toml`, then upward search from each markdown file, then **Wiki CLI fmt defaults** (`wrap: "no"`, `end_of_line: lf`, extensions `gfm`, `front_matters`, `wikilink`, `toc`, `footnote`). See [wiki fmt](wiki_fmt.md) for the full resolution order.

| Shape          | Example               | When to use                                 |
| -------------- | --------------------- | ------------------------------------------- |
| Inline mapping | `fmt: { wrap: "no" }` | Default; what `wiki init` writes            |
| Relative path  | `fmt: custom.toml`    | Share one TOML file or keep fmt out of yaml |

Invalid inline keys or values fail when the config loads. Invalid TOML syntax fails when `wiki fmt` reads the file.

In library code, loaded `Config.fmt` is a `FmtConfig` with `options` (inline mapping) or `toml` (resolved path under `config_root`).

## Page layout

When `site.layout` is set, the CLI renders every page through that page layout (`.html`). Per-page overrides use `wazoo:layout` in frontmatter; see [Wiki Page Layouts](Wiki_Page_Layouts.md).

### Layout strategy

The first-class presentation contract in this repository is layout files referenced from `site.layout` (for example `index.html`).

- The [wiki](wiki.md) owns the semantic markdown-to-HTML pipeline and layout slot contract.
- Wiki page layout files are the primary built-in extension point for presentation.
- Advanced themes or framework-specific sites such as Next.js, Mintlify, or other external docs stacks are treated as downstream integrations or separate layout/template repositories.

### Minimal fallback

Without a configured layout file (or when the path is missing), every page is rendered with the built-in minimal fallback layout (`index.html`), which outputs plain, unstyled HTML containing only `<h1>` and content. It does not link any default CSS or assets and does not include a sidebar, tabs, infobox, table of contents, backlinks, or categories out-of-the-box.

### Layout slots

Layout files use `%wiki.*%` slot substitution (not Jinja). On each page render, the CLI builds a slot map from the current page context and replaces every known slot in your layout file. Unknown `%wiki.*%` spellings are left unchanged.

Programmatic consumers and contract tests use `wiki.site.layout_tokens.build_layout_token_map` as the single boundary for slot production. See [Wiki Programmatic API](Wiki_Programmatic_API.md#layout-slot-contract).

Canonical slot list (3 slots):

| Slot              | Source                 | Substitution                                                  |
| ----------------- | ---------------------- | ------------------------------------------------------------- |
| `%wiki.base_url%` | `site.base_url`        | HTML-escaped text (`/wiki`, or `""` for site root)            |
| `%wiki.head%`     | built per page         | `<title>{page title} - Wiki CLI</title>` (title HTML-escaped) |
| `%wiki.body%`     | rendered markdown body | Pre-built HTML (not escaped)                                  |

**Packaged layouts**

| File         | When used                           | Typical slots                |
| ------------ | ----------------------------------- | ---------------------------- |
| `index.html` | `site.layout` unset or missing file | `%wiki.head%`, `%wiki.body%` |

Example excerpt (`index.html`):

```html
<!DOCTYPE html>
<html lang=en>
<head>
<meta charset=UTF-8>
<meta name=viewport content=width=device-width,initial-scale=1.0>
%wiki.head%
</head>
<body>
%wiki.body%
</body>
</html>
```

### Custom CSS

The Wiki CLI does not copy or link a default stylesheet out-of-the-box. To add styling to your pages:

1. **Edit the layout file** — set `site.layout` in `wiki.yml` to a custom layout file. Link stylesheets in `<head>`, or write inline styles.
1. **Link wiki assets** — place `.css` files under a directory listed in `wiki.assets`, then reference them from the layout, for example `<link rel="stylesheet" href="%wiki.base_url%/assets/site.css">`. Built assets are served at `%wiki.base_url%/assets/…` during `wiki serve` and copied into the build output.

### Custom logos and icons

To customize site logos, icons, favicons, or touch icons:

1. Place your asset files (such as `logo.svg`, `logo.png`, `favicon.ico`) under a directory listed in `wiki.assets`.
1. Reference the assets from your custom layout file, for example:

```html
<img src="%wiki.base_url%/assets/logo.svg" alt="" width="80" height="80">
```

You can also add `<link rel="icon">`, `<link rel="apple-touch-icon">`, or other `<head>` tags directly in your custom layout file.

Built assets are served at `%wiki.base_url%/assets/…` during `wiki serve` and copied into the build output.

See also [Wiki Page Layouts](Wiki_Page_Layouts.md) for `site.layout`, `wazoo:layout`, and packaged layout files.

The metadata pane uses the same RDF serialization path as `wiki export` (compacted JSON-LD, Turtle, N3, RDF/XML, N-Triples, TriG, N-Quads). A compact **Format** chip row switches views without JavaScript. In `wiki serve`, set the initial chip with `?metadata_format=FORMAT` (for example `turtle` or `json-ld`). In `wiki build`, all format views are embedded in the page HTML so the picker works offline.

### Built-in CSS classes and IDs

The wiki builder generates these selectors in the rendered page content:

| Selector                    | Where                                                                                             |
| --------------------------- | ------------------------------------------------------------------------------------------------- |
| `#article-top`              | Read-view `<article>` wrapper around rendered markdown body.                                      |
| `#firstHeading`             | Read-view page title `<h1>`; also Talk / Source / Metadata pane headings. TOC “(Top)” links here. |
| `#siteSub`                  | Subtitle under Talk / Source / Metadata pane headings.                                            |
| `article`                   | Wrapper around the rendered markdown body (`#article-top`).                                       |
| `.layout-label`             | Uppercase type or custom-layout badge in read view.                                               |
| `.toc` / `#toc`             | Table of contents container.                                                                      |
| `#catlinks` / `.catlinks`   | Category links box.                                                                               |
| `.backlinks` / `#backlinks` | Backlinks section.                                                                                |
| `.catlinks-label`           | Categories heading label.                                                                         |
| `.catlinks-list`            | Categories `<ul>`.                                                                                |
| `.infobox`                  | Typed frontmatter property table.                                                                 |
| `.page-meta`                | Infobox class (used for styling).                                                                 |
| `.template-SLUG`            | Per-template class on infobox (e.g. `template-person`).                                           |
| `toclevel-N` / `lN`         | TOC list item classes for heading level N.                                                        |
| `.wikilink`                 | Internal wiki page links.                                                                         |
| `pre[data-copy]`            | Block code with raw source for clipboard copy.                                                    |
| `.code-block`               | Wrapper injected around copyable pre blocks.                                                      |
| `.code-copy-btn`            | Copy button shown on code-block hover/focus.                                                      |

### JavaScript hooks

Custom layout files can utilize standard JavaScript hooks or customize their own. In premium layouts (such as template repositories), the following JavaScript features can be implemented:

| Function                       | Purpose                                              |
| ------------------------------ | ---------------------------------------------------- |
| `switchTab(viewName)`          | Switch between read / talk / source / metadata tabs. |
| `loadTalkNotes()`              | Load per-page local-storage notes.                   |
| `saveTalkNotes()`              | Save per-page notes to localStorage.                 |
| `clearTalkNotes()`             | Clear per-page notes.                                |
| `copySourceCode()`             | Copy markdown source to clipboard.                   |
| `copyPreContent()`             | Copy a `pre[data-copy]` block to clipboard.          |
| `initCodeCopyButtons()`        | Wrap copyable pre blocks and inject copy buttons.    |
| `toggleToc()`                  | Show/hide table of contents.                         |
| `goToRandomArticle()`          | Navigate to a random page.                           |
| `triggerSearch()`              | Execute search and navigate to first match.          |
| `onSearchInput(e)`             | Live search suggestions.                             |
| `handleSearchKey(e)`           | Keyboard navigation for search suggestions.          |
| `navigateSearch(slug)`         | Navigate to a search result.                         |
| `applyCategoryFilterFromUrl()` | Filter index page by `?category=` URL parameter.     |

If the configured page layout file does not exist, the packaged minimal `index.html` layout is used silently — no error.

## Filename conventions

The CLI does not hard-code kebab-case. Projects choose a convention with **`wiki.filename_pattern`**, matched against the **full filename** (including `.md`) on markdown files only.

**Wikipedia-style (recommended):** preserved capitalization and underscores — `Gregory_Davidson.md`, `Pokemon_Diamond_(copy_1).md`, `LLM_Wiki_CLI.md`. Use a pattern such as:

```yaml
wiki:
  filename_pattern: "[A-Za-z0-9_()-]+\\.md"
```

**Kebab-case (optional):** if you prefer `gregory-house.md`, set an explicit pattern (for example `[a-z0-9-]+\\.md`) and enforce it via `lint.filename_pattern`. Wikipedia-style and kebab-case should not be mixed in one wiki.

Page routes keep the casing from the filename; GitHub Pages URLs are case-sensitive.

`wiki link --fix-broken` preserves the existing link kind in each file; only `--apply` uses `link.style`.

When `link.style` is `standard`, `lint.link_style` (default `warning`) flags Obsidian wikilinks (`[[Page]]`) in body prose. Set `lint.link_style: off` to allow wikilinks while keeping standard links as the apply format, or set `link.style: wikilink` for an Obsidian-style wiki.

## Formatting (`fmt`)

Top-level **`fmt`** configures `wiki fmt` (mdformat). Two shapes are allowed — not both:

| Shape          | Example               | When to use                                 |
| -------------- | --------------------- | ------------------------------------------- |
| Inline mapping | `fmt: { wrap: "no" }` | Default; what `wiki init` writes            |
| Relative path  | `fmt: custom.toml`    | Share one TOML file or keep fmt out of yaml |

Omit `fmt` entirely to use fallbacks: `config_root/.mdformat.toml`, then upward search from each markdown file, then **Wiki CLI fmt defaults** (`wrap: "no"`, `end_of_line: lf`, extensions `gfm`, `front_matters`, `wikilink`, `toc`, `footnote`). See [wiki fmt](wiki_fmt.md) for the full resolution order.

Invalid inline keys or values fail when the config loads. Invalid TOML syntax fails when `wiki fmt` reads the file.

In library code, loaded `Config.fmt` is a `FmtConfig` with `options` (inline mapping) or `toml` (resolved path under `config_root`); yaml shapes above are unchanged.

## Integrity checks (`check`)

Under `check`, each rule is `error`, `warning`, or `off`:

| Rule key              | Default | What it audits                                                           |
| --------------------- | ------- | ------------------------------------------------------------------------ |
| `missing_layout_file` | `error` | `wazoo:layout` paths that do not resolve to a readable `.html` file      |
| `frontmatter_schema`  | `error` | Frontmatter that fails JSON Schema validation                            |
| `missing_schema_ref`  | `error` | `wazoo:jsonSchema` paths or URLs that cannot be loaded                   |
| `remote_schema_refs`  | `allow` | Policy for remote `http(s)` schema refs: `allow`, `deny`, or `allowlist` |
| `remote_schema_hosts` | `[]`    | Hostnames permitted when `remote_schema_refs` is `allowlist`             |

Build-safety rules (unsafe URL characters, spaces in routes) and output URL collision detection always apply regardless of `check` settings.

### JSON Schema frontmatter (`wazoo:jsonSchema`)

`wiki check` validates frontmatter against JSON Schema in parallel with SHACL. Bind schemas on shape documents with **`wazoo:jsonSchema`** beside **`sh:targetClass`**; every page whose effective `type` matches that class must pass the bound schema(s). Individual pages may append extra schemas with their own `wazoo:jsonSchema` key (scalar or YAML list). Schema refs are local paths under the wiki config root (`.json` only) or remote `http(s)` URLs. Remote refs can trigger outbound network requests; set `check.remote_schema_refs: deny` in CI over untrusted wikis, or `allowlist` with `check.remote_schema_hosts` for trusted hosts only.

Shape binding documents are not validated as instances — only their schema refs are checked for loadability. Authoring detail: [SHACL](SHACL.md), [Style Guide](Style_Guide.md).

## Convention audits (`lint`)

Under `lint`, each rule is `error`, `warning`, or `off`:

| Rule key           | Default   | What it audits                                                                                                 |
| ------------------ | --------- | -------------------------------------------------------------------------------------------------------------- |
| `broken_links`     | `warning` | Wikilinks, internal markdown links, heading fragments, assets, `wiki:` CURIEs                                  |
| `filename_pattern` | `warning` | Full filename vs `wiki.filename_pattern` regex                                                                 |
| `headings`         | `off`     | ATX `#` headings only (no Setext underlines), sentence-case H2+, H1 title case conventional, numbered headings |
| `thematic_breaks`  | `off`     | Horizontal rules (`---`, `***`, `___`) in body prose                                                           |
| `link_style`       | `warning` | Obsidian wikilinks (`[[Page]]`) in body prose when `link.style` is `standard`                                  |

## This repository

`docs/wiki.yml` is the dogfood wiki config for this repository. It follows the same block order as the packaged scaffold, but with project-specific overrides — `graph.context.wiki` for GitHub Pages and `graph.content_predicate: schema:articleBody` for SPARQL full-text.

## Related

- [wiki](wiki.md#global-options) — `-c` and `--input` global options
- [wiki init](wiki_init.md) — scaffold a new wiki project
- [wiki check](wiki_check.md) — integrity checks
- [wiki lint](wiki_lint.md) — convention audits
- [wiki query](wiki_query.md) — ad-hoc SPARQL
- [wiki render](wiki_render.md) — inline SPARQL tables
- [wiki serve](wiki_serve.md#sparql-endpoint) — `#serve-api` config block
- [Graph Cache](Graph_Cache.md) — `--cache` and graph reuse
- [Style Guide](Style_Guide.md) — shapes and frontmatter
