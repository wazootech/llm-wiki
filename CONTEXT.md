# Wiki CLI (`wazootech-wiki`)

Semantic knowledge **toolchain** for Markdown wikis: compile frontmatter and body into RDF, validate with SHACL and JSON Schema, infer with OWL-RL, query with SPARQL, and publish static HTML or serializations. Wiki CLI is the compiler and query engine — not the primary editor or note app. See [docs/wiki/wiki.md](docs/wiki/wiki.md) for scope, boundaries, and command reference.

## Architecture decision: Python core

Issue [#44](https://github.com/wazootech/wiki/issues/44): keep the **Python CLI as the source of truth** for parsing, validation, inference, querying, and export. Do not plan a full TypeScript rewrite of the engine.

- **Why Python** — `rdflib`, `pyshacl`, and `owlrl` compose a single coherent RDF/SHACL/OWL pipeline aligned with this repo’s core job.
- **TypeScript at the edges only** — the npm package is a thin delivery wrapper (private venv + matching PyPI engine), not a second implementation.
- **Revisit a rewrite only if** — a concrete npm-only distribution requirement, a web-first product that dominates the roadmap, or maintenance pain in Python that outweighs the RDF ecosystem advantage.

## Architecture decision: Library-first API

Issue [#112](https://github.com/wazootech/wiki/issues/112): expose a **stable Python library** (`Wiki`, typed `AuditReport` / operation results) with the Click CLI as a thin I/O wrapper. See [Wiki Programmatic API](docs/wiki/Wiki_Programmatic_API.md). Semver applies to symbols in `wiki.__all__`; audit dict helpers are removed in favor of Pydantic report models.

## Language

**Wiki**: An LLM-managed knowledge base of markdown files containing structured frontmatter. _Avoid_: Book, repository, database.

**Wiki** (or **Wiki corpus**): The semantic corpus the CLI loads from `wiki.input` plus installed read-only `sources:` when present. It is the on-disk home of **Documents**, shapes, raw RDF, and embedded SPARQL; the CLI compiles it into the RDF graph. A composed Wiki can feel like one corpus while preserving source boundaries as RDF named graphs. In this repository, `docs/wiki/`. _Avoid_: Book, generic database.

**Document**: An individual Markdown page in the wiki containing a metadata block. _Avoid_: Page, post, wiki page.

**Frontmatter**: A YAML or JSON metadata block at the top of a Document, mapping to a JSON-LD compliant representation. _Avoid_: Metadata, header.

**Context**: The namespace mapping and prefix bindings (similar to JSON-LD `@context`) embedded inside a Config. _Avoid_: Namespace list.

**Config**: The root configuration object loaded from `wiki.yml` (or legacy `wiki.yaml`) — same nested blocks as the file (`wiki`, `graph`, `site`, …) plus loader-injected `config_root`. Access paths via `config.wiki.input`, routing and layout path via `config.site.*` (`layout`, `base_url`, `url_style`); presentation and branding live in the page layout and `wiki.assets`, RDF via `config.graph.*` and the `config.context` property. Import as `from wiki.config import Config`. _Avoid_: parameters, settings, flat `input_dirs` fields.

**WikiConfig**: Reserved name for a future top-level `wiki:` yaml section (`{section}Config` pattern). Not loaded today. _Avoid_: Using this name for the root loader (use **Config**).

**Namespaces**: The mapping of prefix keys to URI values used for RDF conversion and SPARQL queries. _Avoid_: Prefixes, prefixes list.

**Inference**: The process of applying OWL-RL deductive reasoning to expand the RDF graph. _Avoid_: Reasoning, calculation.

**Axiom**: Ontological rules and schema definitions loaded from Turtle files to guide the inference process. _Avoid_: Rule, schema rule.

**Validation**: The process of checking Document frontmatter against SHACL shapes and optional JSON Schema bindings (`wazoo:jsonSchema`) to ensure structure and value compliance. _Avoid_: Formatting check, manual review.

**Shape**: A SHACL constraint definition loaded from Turtle files to validate the structure of Documents. _Avoid_: Rule, template.

**Query**: A SPARQL query executed against the semantic RDF graph of the Wiki. _Avoid_: Search, database lookup.

**Rendering**: The process of executing embedded SPARQL Queries within Documents and injecting the formatted results back into the files. _Avoid_: Exporting, updating.

**Graph cache**: The in-process RDF graph held for the lifetime of a CLI run so multiple SPARQL queries and renders share one **Wiki** build. _Avoid_: Disk cache, pickle store.

**Source graph**: A read-only RDF named graph for an installed source. Source graph URIs are stable handles for SPARQL `GRAPH` clauses and provenance inspection; they do not imply writable source mutation.

**Checking**: Integrity validation on the **Wiki** via `wiki check` — SHACL, JSON Schema frontmatter, route safety, collisions, and layout frontmatter.

**Linting**: Conventions and broken links via `wiki lint` (`lint.broken_links`, filename pattern, headings, link style).

**Linting**: Convention audits on the **Wiki** via `wiki lint` — configurable `filename_pattern`, `headings` (sentence-case H2+, numbering), `thematic_breaks`, and `link_style`. ATX heading syntax is enforced by **`wiki fmt`** (mdformat). _Avoid_: Checking (use `wiki check` for integrity).

**Formatting**: Markdown formatting via `wiki fmt` (mdformat). Separate from check and lint.

**Link hygiene**: Suggest missing wikilinks or repair unambiguous broken internal links via `wiki link` (`--apply`, `--fix-broken`). Broken-link detection lives in **Linting** (`lint.broken_links`); mutation is explicit and never part of `wiki build` preflight. _Avoid_: Treating enrichment as lint or folding repair into `wiki check`.

**Exporting**: The process of compiling and exporting the Frontmatter of all Documents into a single canonical JSON-LD representation. _Avoid_: Saving, dumping.

**CLI**: The command-line interface built with Click for managing the wiki.

## Relationships

- A **Wiki** (the wiki corpus) is the filesystem corpus of **Documents** and raw RDF listed by `wiki.input`, plus installed read-only source inputs resolved from `wiki.lock`
- A **Wiki** is composed of root corpus content and optional source graphs, compiled semantically at runtime
- A **Document** contains exactly one **Frontmatter** block
- The **CLI** manages, validates, and queries the **Wiki** using **Config**, which contains the **Context** and **Namespaces**
- **Inference** uses custom **Axioms** to expand the semantic RDF graph of the **Wiki**
- **Validation** checks **Documents** against custom **Shapes** to ensure data integrity
- **Checking** runs integrity checks on the **Wiki** via `wiki check`; **Linting** runs convention audits via `wiki lint`; **Link hygiene** is optional via `wiki link`; stale SPARQL blocks use `wiki render --check`
- **Query** executes custom SPARQL queries against the expanded RDF graph of the **Wiki**
- **Rendering** runs embedded **Queries** inside **Documents** and updates their dynamic sections inline
- **Graph cache** lets multiple **Queries** and **Rendering** steps in one CLI run reuse a single loaded RDF graph
- **Exporting** packages the **Frontmatter** of the **Wiki** into a unified JSON-LD graph

## Example dialogue

> **Dev:** "Does a **Document** always need `type` in **Frontmatter**?"
> **Domain expert:** "Without `graph.implicit_types`, a document with no `type` / `@type` produces no RDF triples and is invisible to SPARQL and SHACL. With `graph.implicit_types` configured, untyped documents inherit those CURIEs at graph build time; explicit types still win when `implicit_types_policy` is `fallback`."
