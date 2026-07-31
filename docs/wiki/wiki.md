---
type: schema:SoftwareApplication
name: wiki
softwareVersion: 0.1.21
description: Command-line interface for querying, validating, and publishing semantic markdown wikis.
codeRepository: https://github.com/wazootech/wiki
---

# `wiki`

This page is the **documentation home** for **Wiki CLI** (`wiki` on PyPI and npm as [**`wazootech-wiki`**](https://pypi.org/project/wazootech-wiki/)): the semantic knowledge **toolchain** for Markdown wikis — validate with [SHACL](SHACL.md) and JSON Schema, infer and query with [SPARQL](SPARQL.md), and publish static HTML. It compiles wikis into RDF and sits **beneath** note apps and LLM-assisted workflows — progressive enhancement, not a migration.

```bash
pip install wazootech-wiki
wiki --help
```

Install options: PyPI (`pip install wazootech-wiki`), npm ([`wazootech-wiki` on npm](https://www.npmjs.com/package/wazootech-wiki) → `wiki` on PATH), or zero-install (`npx wazootech-wiki` / `uvx wazootech-wiki` — same subcommands as `wiki`). See [Getting Started](Getting_Started.md#install).

## Quickstart

```bash
pip install wazootech-wiki
mkdir my-wiki && cd my-wiki
wiki init
wiki check
wiki lint
wiki serve
```

See [Getting Started](Getting_Started.md) for a full walkthrough.

## What wiki is

- The **compiler / validator / query engine** for Markdown knowledge bases with semantic frontmatter
- An **OOTB wiki builder** — links, navigation, SHACL and JSON Schema checks, SPARQL, and static HTML from a folder of `.md` files
- A **memory layer** — ingest or watch an existing wiki without owning the editor
- **Interop-first** — works alongside [Obsidian](Obsidian_Integration.md), [LLM Wiki](LLM_Wiki.md) setups, and any Markdown editor

Adoption path: `wiki init` → `wiki check` → `wiki serve`, then add `lint`, `query`, `render`, and `build` as the wiki matures.

Wiki CLI is intentionally batteries-included for semantic Markdown wikis: validation, formatting, querying, rendering, exporting, building, and local preview belong together. The boundary is not "minimal CLI only"; the boundary is "semantic wiki toolchain, not editor/app automation."

## What wiki is not

- The **primary editor** or daily note-taking surface
- A **replacement** for Obsidian, Logseq, or another wiki UI
- A **note app clone**, CMS, or authenticated multi-user web product
- An **auth layer** — local-first CLI and static publish; see deferred scope in [Wiki CLI templates](#ecosystem-templates) below
- A vault automation CLI for daily notes, note append/read workflows, task lists, tags, plugin development, or Obsidian app control
- A replacement for shell tools, Git, Pandoc, or editor-native commands

Humans and agents keep writing where they already write. `wiki` makes that content **trustworthy** (SHACL, JSON Schema, and conventions), **searchable** (SPARQL + OWL-RL), and **publishable** (static HTML, JSON-LD, Turtle, optional read-only SPARQL over `wiki serve`).

## Memory layer and ingestion

Rather than owning your editor or data store, **Wiki** functions as a **read-only memory layer** over your wiki. It parses, indexes, and queries the Markdown documents on your filesystem without mutating them or locking you into a proprietary format.

- **Ingestion:** The CLI reads YAML/JSON frontmatter and HTML microdata from your files, compiling them into an in-memory RDF graph that can be queried with SPARQL or verified against SHACL shapes and JSON Schema bindings.
- **Watching:** Running `wiki serve --watch` instructs the CLI to watch the wiki directory. Any edits you make in your preferred editor are immediately processed, updating the graph in the background and keeping your preview server synchronized.

## Toolchain vs authoring surface

| Layer                   | Role                                                                   | Examples                                                    |
| ----------------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------- |
| Authoring surface       | Create, edit, search, and organize notes                               | Obsidian CLI, Obsidian, VS Code, shell                      |
| Wiki CLI semantic layer | Compile wiki → RDF graph; check, lint, fmt; query; render; build/serve | `wiki check`, `wiki query`, `wiki build`                    |
| Existing primitives     | History, sync, print/PDF, and generic text processing                  | Git, shell tools, Pandoc                                    |
| Outputs                 | Deployable semantic artifacts                                          | GitHub Pages HTML, export files, `/api/sparql` when enabled |

This separation is intentional: the strongest differentiator is the **machine layer** (SHACL, OWL-RL, SPARQL, typed HTML) that most note apps do not provide. **Wiki** avoids competing with editor-centric tools while making incremental adoption obvious.

When an existing primitive already owns a workflow, Wiki CLI integrates rather than replaces it. Obsidian CLI owns Obsidian app/vault automation; Git owns history and collaboration; shell tools own generic file/process composition; Pandoc and document tools own non-semantic document conversion.

`wiki link --fix-broken` supports link hygiene for publishable wikis. `wiki link --apply` is optional wiki-gardening: useful when desired, but not required for validation, publishing, or Obsidian compatibility.

## Interop-first workflows

### Obsidian

Run `wiki` against the folder that contains `wiki.yml` or `wiki.yaml`. Use Shell Commands for on-save `wiki check`, hotkey `wiki render`, or `wiki serve --watch` for preview. Details: [Obsidian integration](Obsidian_Integration.md) and [Dataview integration](Dataview_Integration.md).

### LLM wikis

Treat the wiki as a compounding codebase agents maintain over time. Structured frontmatter and link conventions make SPARQL and SHACL meaningful on agent output. Pattern overview: [LLM Wiki](LLM_Wiki.md).

### Plain Markdown

No Obsidian or agent stack required. `wiki init` scaffolds a wiki; conventions are documented in [Style Guide](Style_Guide.md).

## Three capabilities of the CLI

| Capability   | Commands                           | Value                                                              |
| ------------ | ---------------------------------- | ------------------------------------------------------------------ |
| Trust        | `check`, `lint`, `fmt`             | Integrity contracts and authoring conventions                      |
| Intelligence | `query`, `mcp`, `render`, `export` | SPARQL, MCP graph access, inline result blocks, RDF serializations |
| Publish      | `build`, `serve`, `link`           | Static site, local preview, wikilink hygiene                       |
| Sources      | `install`, `update`, `remove`      | Fetch, lock, update, and manage external sources                   |
| Provenance   | `graph list`                       | Inspect read-only named graph boundaries                           |

Design rationale for silence, pipes, and flat subcommands: [Design philosophies](Design_Philosophies.md).

## Ecosystem templates

GitHub **template repositories** in the [wazootech](https://github.com/wazootech) org sit at the edges of the toolchain — publish surfaces, query UIs, and starter vaults — while Wiki CLI owns the semantic layer ([Design philosophies](Design_Philosophies.md)). This section is the canonical registry.

| Template                                                                     | Description                                                                                   |
| ---------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| [generic](https://github.com/wazootech/wiki-templates/tree/main/generic)     | Generic Wiki CLI project (`wiki init` parity plus deploy)                                     |
| [yasgui](https://github.com/wazootech/wiki-templates/tree/main/yasgui)       | SPARQL query editor UI (YASGUI); `wiki serve` `/api/sparql`, export TTL                       |
| [llm-wiki](https://github.com/wazootech/wiki-templates/tree/main/llm-wiki)   | [LLM Wiki](LLM_Wiki.md) starter vault with agent-oriented pages and gardening hooks           |
| [nextjs](https://github.com/wazootech/wiki-templates/tree/main/nextjs)       | Next.js SSG consumer of `wiki export` JSON-LD                                                 |
| [quartz](https://github.com/wazootech/wiki-templates/tree/main/quartz)       | Quartz static site from a compatible vault plus `wiki check` CI                               |
| [cocoindex](https://github.com/wazootech/wiki-templates/tree/main/cocoindex) | CocoIndex incremental sidecar for Wiki-derived memory, RAG, and provenance-preserving indexes |
| [mintlify](https://github.com/wazootech/wiki-templates/tree/main/mintlify)   | Mintlify or Holocron docs site from a compatible vault                                        |
| [holocron](https://github.com/wazootech/wiki-templates/tree/main/holocron)   | Holocron docs site from a Wiki CLI-compatible vault                                           |
| [astro](https://github.com/wazootech/wiki-templates/tree/main/astro)         | Astro SSG consumer of `wiki export` JSON-LD                                                   |
| [wikipedia](https://github.com/wazootech/wiki-templates/tree/main/wikipedia) | Wikipedia-themed layout using the Wiki Python API                                             |
| [camunda](https://github.com/wazootech/wiki-templates/tree/main/camunda)     | Camunda BPMN/DMN governance knowledge base with SHACL shapes                                  |

### Artifact contract

External templates consume Wiki CLI outputs — they do not replace the compiler:

- **`wiki.yml`** / **`wiki.yaml`** — config root; `wiki.inputs`, `graph.*`, `site.*`
- **`wiki export`** — JSON-LD, Turtle, TriG, and other RDF serializations
- **`wiki build`** — static HTML under `site.base_url`

### Retired slugs

Do not use these in new prose: `sparql-service-template` (→ `wiki-templates/yasgui`); `wiki-virtuoso-template` (→ folded into `wiki-templates/yasgui`); `wiki-obsidian-quartz-template`, `obsidian-quartz-template` (→ `wiki-templates/quartz`); bare `nextjs-template`, `mintlify-template`, `astro-template` (→ `wiki-templates/*`); `wiki-template`, `llm-wiki-template`, `wiki-yasgui-template`, `wiki-nextjs-template`, `wiki-quartz-template`, `wiki-cocoindex-template`, `wiki-mintlify-template`, `wiki-astro-template` (all retired — use `wiki-templates/<subdir>` instead).

## Features

- **Check** — SHACL and JSON Schema integrity, route safety, layout frontmatter ([wiki check](wiki_check.md))
- **Lint** — broken links, filename pattern, and heading conventions ([wiki lint](wiki_lint.md))
- **Link** — repair broken internal links and optionally insert suggested links as wiki-gardening ([wiki link](wiki_link.md))
- **Fmt** — mdformat for markdown ([wiki fmt](wiki_fmt.md))
- **Query** — SPARQL with OWL-RL and optional `--pretty` Rich tables ([wiki query](wiki_query.md), [Graph Cache](Graph_Cache.md))
- **Graph list** — inspect root and source named graphs for SPARQL `GRAPH` provenance ([wiki graph](wiki_graph.md))
- **MCP** — read-only query-first MCP server for local agents ([wiki mcp](wiki_mcp.md))
- **Render** — live tables from inline SPARQL ([wiki render](wiki_render.md))
- **Build / serve** — static site, local preview, and optional read-only SPARQL endpoint ([wiki build](wiki_build.md), [wiki serve](wiki_serve.md#sparql-endpoint))
- **Export** — JSON-LD and RDF serializations ([wiki export](wiki_export.md))
- **Install** — fetch and lock external data sources ([wiki install](wiki_install.md))
- **Update** — check locked sources for newer commits ([wiki update](wiki_update.md))
- **Remove** — delete a source from wiki.yml, cache, and lockfile ([wiki remove](wiki_remove.md))
- **Init** — scaffold `wiki.yml` ([wiki init](wiki_init.md))
- **Upgrade** — PyPI updates ([wiki upgrade](wiki_upgrade.md))

## Supported file formats

### Input pipelines

Wiki CLI processes files through two distinct pipelines. Files in `wiki.inputs` are classified as either **documents** (frontmatter parsed, IRI derived from file path, link-checked) or **raw RDF sources** (loaded directly via rdflib, no document processing):

| Category            | Extensions                                               | Pipeline             | Key behavior                                                                                  |
| ------------------- | -------------------------------------------------------- | -------------------- | --------------------------------------------------------------------------------------------- |
| Wiki documents      | `.md`, `.yaml`, `.yml`, `.json`, `.toml`                 | Frontmatter → graph  | Parsed for frontmatter/data; document IRI derived from file path; link-checked and exportable |
| Data-only documents | `.yaml`, `.yml`, `.json`, `.toml`                        | Frontmatter → graph  | Subset of wiki documents without a markdown body — entire file is the data dict               |
| Raw RDF sources     | `.ttl`, `.trig`, `.nt`, `.nq`, `.rdf`, `.xml`, `.jsonld` | rdflib parse → graph | Loaded as raw triples; no route, no link checking, no frontmatter pipeline                    |
| Inline Turtle       | Inside `.md` as ```` ```turtle ```` blocks               | rdflib parse → graph | Fenced turtle blocks inside markdown files are parsed and merged into the graph               |

### Document pipeline

Markdown files are parsed via the [Linked Markdown](Linked_Markdown.md) protocol: the YAML/JSON frontmatter between `---` delimiters is extracted as the data dict, and the body text is optionally added to the graph via `content_predicate`. Data-only documents (`.yaml`, `.yml`, `.json`, `.toml`) skip the body split — the entire file is the data.

All document formats have their `@context` auto-populated with `wiki:` and `foaf:` default prefixes if none is present. An explicit `@id` or `id` key in frontmatter overrides the file-path-based IRI ([Linked Markdown](Linked_Markdown.md#subject-uri-resolution)).

### Raw RDF pipeline

Files with raw RDF extensions are parsed directly by rdflib using the format mapped from their extension. They bypass all document processing — no route registration, no link validation, no frontmatter coercion. They contribute triples to the same graph but are invisible to `wiki export` (which operates on documents) and `wiki link`.

**Important nuance:** `.jsonld` is raw RDF (rdflib `json-ld` format) — it is NOT a wiki document. It does not get a document IRI, does not go through `ensure_context()`, and is not subject to link checking. A `.json` file with the same content *is* a wiki document and follows the frontmatter pipeline. These are disjoint processing paths.

### Output formats

| Context                                   | Formats                                                                    |
| ----------------------------------------- | -------------------------------------------------------------------------- |
| `wiki export`                             | `dict` (default), `json-ld`, `turtle`, `xml`, `n3`, `nt`, `trig`, `nquads` |
| `wiki query`                              | `table` (default), `json`, `csv`, `tsv`, `turtle`, `n3`, `markdown`        |
| `wiki serve` / `wiki build` metadata view | `json-ld`, `turtle`, `n3`, `xml`, `nt`, `trig`, `nquads`                   |

### Key nuances

- **`.jsonld` vs `.json`** — Different pipelines for the same data shape. See raw RDF pipeline note above.
- **N3 is output-only** — Notation3 (`.n3`) is available for `wiki export` and `wiki query` CONSTRUCT results but is not recognized as an input graph source extension.
- **`@context` auto-injection** — Document files that lack an `@context` key get default `wiki:` and `foaf:` prefixes injected. If `@context` is present as a dict, those defaults are merged in.
- **Only `.md` carries body text** — Data-only formats cannot carry a body literal in the graph; the entire file content is the data dict.
- **Inline ```` ```turtle ``` ```` blocks** — Any fenced code block with `turtle` language inside a `.md` file is parsed as Turtle RDF and merged into the wiki graph. This is separate from SPARQL result blocks.
- **`.toml` is a document format** — TOML files under `wiki.inputs` are treated as data-only wiki documents, subject to `@context` injection and route generation.

### Related

- [Linked Markdown](Linked_Markdown.md) — document-to-RDF protocol and IRI resolution
- [RDF](RDF.md) — RDF data model and serialization references
- Individual format pages: [Turtle](Turtle.md), [TriG](TriG.md), [N-Triples](N_Triples.md), [N-Quads](N_Quads.md), [RDF/XML](RDF_XML.md), [Notation3](Notation3.md), [JSON-LD](JSON_LD.md)

## Agent skills

Procedural knowledge for coding agents: [Wiki Skills](Wiki_Skills.md) (`skills/wiki/` in the repository).

## Start here

- [Getting Started](Getting_Started.md) — install, `wiki init`, first `check` and `serve`
- [Wiki Configuration](Wiki_Configuration.md) — `wiki.yml` / `wiki.yaml` options
- [Style Guide](Style_Guide.md) — frontmatter, shapes, internal links, SPARQL blocks
- [Graph Cache](Graph_Cache.md) — in-process RDF graph reuse
- [Design Philosophies](Design_Philosophies.md) — silence is golden, pipes, flat commands

## Global Options

These options apply to config-loading subcommands (`check`, `lint`, `link`, `query`, `mcp`, `render`, `build`, `export`, `serve`, `fmt`, `install`, `remove`). `init` and `upgrade` do not load a config file.

### `-c, --config PATH`

Path to `wiki.yml`, `wiki.yaml`, `wiki.json`, or a directory containing one of those files. Defaults to the current directory (`.`).

Example:

```bash
wiki -c docs/wiki.yml check
```

### `--wiki-inputs PATH` (repeatable)

Override or extend `wiki.inputs` from config for a single invocation. Relative paths resolve against the config file directory. Useful for one-off queries against a subdirectory.

Example:

```bash
wiki --wiki-inputs ./wiki --wiki-inputs ./imported query "SELECT * WHERE { ?s ?p ?o } LIMIT 5"
```

## Command reference

Each subcommand has a dedicated page:

<!-- sparql:start
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <https://schema.org/>

SELECT ?command ?description WHERE {
  ?command rdf:type schema:TechArticle .
  FILTER(STRSTARTS(STR(?command), "https://wazootech.github.io/wiki/wiki_"))
  OPTIONAL { ?command schema:description ?description }
}
ORDER BY ?command
```
-->

| command                         | description                                                                                         |
| ------------------------------- | --------------------------------------------------------------------------------------------------- |
| [wiki_build](wiki_build.md)     | Generate a static HTML site from the wiki.                                                          |
| [wiki_check](wiki_check.md)     | Integrity checks — SHACL validation, JSON Schema frontmatter, route safety, and layout frontmatter. |
| [wiki_export](wiki_export.md)   | Export document frontmatter as RDF or JSON-LD.                                                      |
| [wiki_fmt](wiki_fmt.md)         | Format markdown wiki pages using mdformat with wikilink preservation.                               |
| [wiki_graph](wiki_graph.md)     | List read-only RDF named graphs for root and installed source provenance.                           |
| [wiki_init](wiki_init.md)       | Scaffold wiki.yml and starter wiki pages interactively.                                             |
| [wiki_install](wiki_install.md) | Fetch and lock external data sources declared in wiki.yml.                                          |
| [wiki_link](wiki_link.md)       | Suggest missing wikilinks and repair unambiguous broken internal links.                             |
| [wiki_lint](wiki_lint.md)       | Convention audits for broken links, filename patterns, heading style, and internal link style.      |
| [wiki_mcp](wiki_mcp.md)         | Run a read-only MCP server for querying the wiki graph.                                             |
| [wiki_query](wiki_query.md)     | Run SPARQL SELECT or CONSTRUCT against the wiki graph.                                              |
| [wiki_remove](wiki_remove.md)   | Remove a data source from wiki.yml, its cache, and wiki.lock.                                       |
| [wiki_render](wiki_render.md)   | Update inline SPARQL result tables in markdown files.                                               |
| [wiki_serve](wiki_serve.md)     | Local HTTP server for live HTML preview and optional read-only SPARQL endpoint.                     |
| [wiki_update](wiki_update.md)   | Check locked sources for newer commits and update wiki.lock.                                        |
| [wiki_upgrade](wiki_upgrade.md) | Check PyPI for updates and upgrade wazootech-wiki.                                                  |

<!-- sparql:end -->

Global flags: `-c`, `--wiki-inputs`.

## Publishing

- [Deploying to GitHub Pages](Deploying_to_GitHub_Pages.md) — CI workflow for this site
- [Obsidian Integration](Obsidian_Integration.md) — Shell Commands plugin workflows

## Managing drift and schema evolution

A common challenge in text-based memory bases is metadata drift—especially when files are updated programmatically by external LLM agents. The Wiki CLI provides two strategies to keep a compounding codebase clean over long periods:

### Automated cleaning harness

To prevent drift mechanically, you can wire a local Git hook or CI workflow that executes the following checks in order:

1. **[wiki fmt](wiki_fmt.md)**: Auto-formats Markdown structures and standardizes YAML frontmatter layout.
1. **[wiki lint](wiki_lint.md) `--strict`**: Flags broken links, non-conforming filename patterns, and heading casing warnings as hard errors.
1. **[wiki check](wiki_check.md) `--strict`**: Ensures frontmatter conforms to [SHACL](SHACL.md) shapes and bound JSON Schema documents (`wazoo:jsonSchema`).

### Resilient schema evolution

Enforcing schemas on text databases can become problematic as structures evolve. The Wiki CLI avoids schema rigidity using semantic web principles:

- **Additive RDF properties**: Since frontmatter is compiled into a graph, new or unconstrained keys do not cause parsing failures. They are ingested as open-world triples that can be queried or ignored.
- **Decoupled validation**: SHACL and JSON Schema validation are diagnostic steps, not execution blockers. Files with invalid schemas can still be compiled, parsed, and queried.
- **Class-scoped shapes**: Shapes target specific classes (e.g., `sh:targetClass schema:TechArticle`). Introducing a new document type only requires writing a new shape constraint, leaving legacy documents untouched.
- **Namespace contexts**: Properties map to URIs via `graph.context` in [Wiki Configuration](Wiki_Configuration.md). You can rename or alias fields at the config layer without physically editing every source document.

## Design

The CLI follows a flat, scriptable surface and [Design Philosophies](Design_Philosophies.md) (silent success, composable stdout). For programmatic use from Python or TypeScript, see [Wiki Programmatic API](Wiki_Programmatic_API.md).

## Pattern context

This repository implements the [LLM Wiki](LLM_Wiki.md) pattern for [Personal Knowledge](Personal_Knowledge.md) wikis. Examples in the wild include [Farzapedia](Farzapedia.md) and coverage from Andrej Karpathy.

Similar **agent memory filesystem** approaches include [Supermemory SMFS](Supermemory_SMFS.md), [Letta MemFS](Letta_MemFS.md), and [Agent Memory Filesystems](Agent_Memory_Filesystems.md).

For a **standardized agent workspace** (typed graph, loop, blast-radius review), see [Vivary](Vivary.md).

## Repository

- Source and issues: [github.com/wazootech/wiki](https://github.com/wazootech/wiki)
- [Wiki CLI templates](#ecosystem-templates) — all templates live in the [wiki-templates](https://github.com/wazootech/wiki-templates) monorepo

## Background

- [Semantic Web](Semantic_Web.md) — RDF, Turtle, OWL, and related formats
- [Software Application Shape](Software_Application_Shape.md) — SHACL shape for `SoftwareApplication` pages (including this page)
