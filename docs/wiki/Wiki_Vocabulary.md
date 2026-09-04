---
type: TechArticle
headline: Wiki Vocabulary
description: The shared toolchain vocabulary for the wiki project — a small set of wiki: terms expanded identically in every wiki, a reserved wazoo: namespace, and a reuse-first policy for standard RDF vocabularies.
---

# Wiki Vocabulary

The wiki toolchain defines a small **toolchain vocabulary** under the `wiki:` prefix so that every wiki expands it identically. Site-specific concepts stay in per-repository site namespaces (`memory:`, `docs:`, …) with an explicit `graph.base_iri`; `wazoo:` is reserved for wazoo/worlds vocabulary; standard RDF vocabularies are reused before any new term is invented.

This page is the specification. The machine-readable vocabulary is published at [`/vocab/wiki.ttl`](vocab/wiki.ttl) (Turtle) alongside this page. Tracking issue: [wazootech/wiki#272](https://github.com/wazootech/wiki/issues/272).

## Status

Published as the Phase 0 seed (2026-09-03): `wiki:layout` and `wiki:jsonSchema` moved into this vocabulary, and the observed `sourceRepository` provenance pattern resolved to `dcterms:source`. Term adoption follows the governance rules below; until a term is adopted here it is not part of the toolchain vocabulary.

## Scope

The `wiki:` vocabulary is for concepts owned by the wiki toolchain itself. A concept belongs here only when every wiki needs the same identifier for it and no standard vocabulary defines it. Concepts that belong to a site or owner — even when the toolchain processes them — belong in that site's own namespace or in the relevant standard vocabulary.

- **Toolchain concepts** (page layout, schema binding): `wiki:`.
- **Site concepts** (this page, that person, a repo's own properties): the site namespace (`memory:`, …).
- **Standard concepts** (authorship, provenance, types): `schema:`, `dcterms:`, `foaf:`, `sh:`, … — never `wiki:`.

## Namespace declaration

Wikis SHOULD declare the following prefixes in `graph.context`; the expansion of `wiki:` is identical in every wiki:

| Prefix    | IRI                                 | Use                                            |
| --------- | ----------------------------------- | ---------------------------------------------- |
| `@vocab`  | `https://schema.org/`               | Default property vocabulary                    |
| `schema`  | `https://schema.org/`               | Standards reuse                                |
| `dcterms` | `http://purl.org/dc/terms/`         | Standards reuse (provenance)                   |
| `foaf`    | `http://xmlns.com/foaf/0.1/`        | Standards reuse (agents)                       |
| `sh`      | `http://www.w3.org/ns/shacl#`       | Validation shapes                              |
| `xsd`     | `http://www.w3.org/2001/XMLSchema#` | Datatypes                                      |
| `wiki`    | `https://wiki.wazoo.dev/vocab/`     | **Toolchain vocabulary (same in every wiki)**  |
| `<site>`  | `<site base IRI>`                   | Per-repo site namespace alias (e.g. `memory:`) |
| `wazoo`   | `https://schema.wazoo.dev/`         | wazoo/worlds vocabulary only                   |

`wazoo:` is reserved for wazoo/worlds vocabulary and MUST NOT be used for toolchain terms. This repository's own docs wiki still maps `wiki:` to its site namespace ([`docs/wiki.yml`](wiki.yml)) — the legacy shape this vocabulary replaces; see [Deprecation and migration](#deprecation-and-migration).

## Terms

| Term              | Canonical IRI                             | Definition                                                                                                                                                                        | Status                                    |
| ----------------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `wiki:layout`     | `https://wiki.wazoo.dev/vocab/layout`     | Path (`.html`) overriding the site-default page layout for a page.                                                                                                                | move from `wazoo:layout` (2026-09-03)     |
| `wiki:jsonSchema` | `https://wiki.wazoo.dev/vocab/jsonSchema` | JSON Schema reference (local path or `http(s)` URL) bound beside `sh:targetClass` on a shape document, or appended on a page.                                                     | move from `wazoo:jsonSchema` (2026-09-03) |
| `dcterms:source`  | `http://purl.org/dc/terms/source`         | Repository from which a page's data is derived or captured. Adopted instead of inventing a `wiki:` term; replaces the ad-hoc `sourceRepository` property observed in early wikis. | reuse-first (2026-09-03)                  |

## Reuse-first policy

Before proposing a `wiki:` term, map the concept onto an existing standard: `schema:`, `dcterms:`, `foaf:`, `sh:`, or `owl:`/`rdfs:`. Invent a `wiki:` term only when no standard equivalent exists. Provenance of wiki page data is the first documented application: it resolves to `dcterms:source`, not to a new term.

## Deprecation and migration

- `wazoo:layout` and `wazoo:jsonSchema` are deprecated toolchain keys, replaced by the `wiki:` terms above. Toolchain support for the `wazoo:` forms may be removed once an audit shows zero users (see the CLI issue).
- The CLI accepts `wiki:` terms in the same positions where `wazoo:` forms were accepted, so no wiki content migration is required to keep building.
- Site namespaces that currently occupy `wiki:` (every wiki scaffolded before 2026-09-03, including this docs wiki) are not broken by this vocabulary: they coexist until migrated to a per-repo alias with an explicit `graph.base_iri`.

## Governance

New `wiki:` terms are adopted through an issue in [wazootech/wiki](https://github.com/wazootech/wiki) proposing the term, its definition, and the reuse-first mapping analysis. This page and the machine vocabulary update together when a term is adopted.

## Related

- [Design Philosophies](Design_Philosophies.md)
- [Wiki Configuration](Wiki_Configuration.md)
- [Wiki Page Layouts](Wiki_Page_Layouts.md)
- [SHACL](SHACL.md)
- [JSON](JSON.md)
- [Memory Repo Best Practices](Memory_Repo_Best_Practices.md)

## References

- [wazootech/wiki#272 — Proposal: stable `wiki:` toolchain vocabulary](https://github.com/wazootech/wiki/issues/272)
- `src/wiki/layout.py` — `wazoo:layout` constant (moved)
- `src/wiki/frontmatter_schema.py` — `wazoo:jsonSchema` constant (moved)
- `src/wiki/templates/wiki.yml` — scaffold context block
- [Dublin Core Terms](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/) — `dcterms:source`
