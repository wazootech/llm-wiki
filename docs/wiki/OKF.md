---
type: TechArticle
headline: OKF v0.2 provenance in Wiki CLI
description: Audit of Open Knowledge Format v0.2 page-level provenance against Wiki CLI, with a first-party convention and export-profile recommendation.
---

# OKF v0.2 Provenance in Wiki CLI

This page audits **Open Knowledge Format (OKF) v0.2** against the current Wiki CLI and recommends how to use its page-level provenance, trust, and lifecycle conventions without changing Wiki CLI's RDF-native storage model.

## Decision summary

Adopt the OKF v0.2 field families as an **optional first-party frontmatter convention** for generated and curated pages. Do not make them required, do not treat `wiki check` or `wiki lint` as content verification, and do not add an RDF storage schema for OKF. A page that omits the families remains valid and behaves exactly as it does today.

Defer `wiki export --okf` until a Wazoo consumer and bundle fixture exist. The export profile is a reasonable follow-on, but the current CLI exports RDF or JSON-LD payloads rather than portable Markdown bundles, and no checked-out Wazoo consumer currently reads OKF bundles.

The immediate implementation task should be a small, opt-in OKF profile for generated-page producers: emit `sources` and `generated`, preserve unknown fields, and only emit `verified`, `status`, or `stale_after` when the producer has evidence for them. This is the useful intersection of [LLM Wiki](LLM_Wiki.md), [Learning Systems](Learning_Systems.md), and the memory-first model described by [Memory Repo Best Practices](Memory_Repo_Best_Practices.md).

## Audit scope and evidence

The audit covered the canonical OKF v0.2 specification, the OpenWiki migration proposal, the Wiki CLI parser, graph compiler, context bindings, export command, configuration, and the related Wazoo memory and Worlds repositories.

The relevant Wiki CLI anchors are:

- `src/wiki/parser.py:20-24, 67-78` parses Markdown frontmatter as a YAML mapping, preserves nested values, adds a default `@context`, and optionally adds the body under the configured content predicate.
- `src/wiki/graph.py:146-159` resolves frontmatter keys as CURIEs, `wiki.*` keys, or terms under `@vocab`; it does not contain OKF-specific aliases.
- `src/wiki/graph.py:175-223` recursively converts mappings to blank nodes, absolute HTTP values to URI objects, known CURIEs to URI objects, and unknown CURIE-like values to literals.
- `src/wiki/graph.py:289-342` skips only `id`, `type`, and `@type` as structural keys, then passes every other frontmatter field through to RDF.
- `src/wiki/context.py:10-29` provides `schema`, `dcterms`, `foaf`, `dc`, and `wazoo` bindings, but a binding alone does not map an unprefixed OKF key to a different predicate.
- `src/wiki/cli.py:426-479` and `src/wiki/wiki.py:348-427` implement the current export surface: `dict`, `json-ld`, Turtle, XML, N3, N-Triples, TriG, and N-Quads.
- `docs/wiki.yml:16-34` sets `@vocab` to `https://schema.org/`, configures `schema:articleBody`, and does not define `raw:` or `memory:` prefixes.

A direct export probe using the proposed fields confirmed the current behavior: `sources`, `generated`, `verified`, `status`, `stale_after`, and `okf_version` become `schema:*` predicates under this wiki configuration; nested mappings become blank nodes; `stale_after` becomes an `xsd:dateTime` literal; and an unknown value such as `raw:calendar/abc` remains a literal rather than becoming a URI.

## Validated mapping

OKF is a Markdown/frontmatter interchange convention, not an RDF vocabulary. The table therefore distinguishes the normative OKF key from the predicate that **current Wiki CLI actually emits**.

| OKF v0.2 field            | Current Wiki CLI predicate in this wiki         | Current behavior                                                                                               | Recommendation                                                                                            |
| ------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `sources`                 | `schema:sources`                                | Array entries become repeated blank nodes.                                                                     | Keep the exact OKF key; require `resource` within each entry in the producer profile.                     |
| `sources[].id`            | `schema:id` on the source blank node            | A scalar literal used as the stable footnote join key.                                                         | Use a stable producer-owned ID; do not treat it as a URI.                                                 |
| `sources[].resource`      | `schema:resource` on the source blank node      | HTTP URLs become URI objects; `raw:` and `memory://` remain literals unless a prefix is explicitly configured. | Preserve the original reference and accept a union of local descriptors, bundle paths, and external URLs. |
| `sources[].title`         | `schema:title` on the source blank node         | Optional scalar literal.                                                                                       | Preserve when available.                                                                                  |
| `sources[].author`        | `schema:author` on the source blank node        | Optional scalar; actor strings with unknown prefixes remain literals.                                          | Use the OKF actor convention without requiring a new namespace.                                           |
| `sources[].usage_count`   | `schema:usage_count` on the source blank node   | Optional numeric literal.                                                                                      | Emit only when measured; do not interpret it as a credibility score.                                      |
| `sources[].last_modified` | `schema:last_modified` on the source blank node | Optional date/datetime literal, depending on YAML input.                                                       | Preserve source modification time separately from page generation time.                                   |
| `usage_window`            | `schema:usage_window`                           | Mapping becomes a blank node with `schema:from` and `schema:to`.                                               | Keep as a sibling of `sources`; a per-source override is allowed by OKF.                                  |
| `generated`               | `schema:generated`                              | Mapping becomes a blank node with `schema:by` and `schema:at`.                                                 | Emit on generated pages. Use `wazootech-wiki/<version>` as the producer actor.                            |
| `verified`                | `schema:verified`                               | Each list item becomes a blank node; a bare mapping has the same graph shape as one item.                      | Emit only after an actual source/content verification event.                                              |
| `status`                  | `schema:status`                                 | Scalar literal; no enum enforcement today.                                                                     | Optional values: `draft`, `stable`, or `deprecated`.                                                      |
| `stale_after`             | `schema:stale_after`                            | Absolute YAML datetime becomes `xsd:dateTime`.                                                                 | Use an absolute ISO 8601 datetime with an explicit UTC offset.                                            |
| bundle-root `okf_version` | `schema:okf_version` if placed in a normal page | Current export has no bundle root and does not create `index.md`.                                              | Emit only in a future bundle-root `index.md`, as `"0.2"`.                                                 |

The proposed table in the ticket listed `dcterms:source`, `schema:citation`, `schema:dateCreated`, and `schema:creator` as possible bindings. Those are not automatic bindings today. They are emitted only when a page explicitly uses those prefixed keys. Adding aliases would be a separate implementation decision and must not silently change the meaning of existing arbitrary frontmatter.

## Optional first-party convention

The following is the recommended producer shape. It is intentionally valid whether or not a consumer knows OKF.

```yaml
sources:
  - id: gmail-message-abc123
    resource: raw:gmail/gmail-message-abc123
    title: Source message
    author: process:gmail-connector
    last_modified: 2026-09-04T20:00:00Z
usage_window:
  from: 2026-09-01T00:00:00Z
  to: 2026-09-04T20:00:00Z
generated:
  by: wazootech-wiki/0.1.21
  at: 2026-09-04T22:00:00Z
verified:
  - by: process:source-reconciliation
    at: 2026-09-04T22:05:00Z
status: stable
stale_after: 2026-10-04T00:00:00Z
```

### Sources

A `sources` value is an array of mappings. Each mapping must contain a `resource`; `id`, `title`, `author`, `usage_count`, and `last_modified` are optional. `usage_window` is a sibling of `sources` and contains `from` and `to`; a source may carry an overriding window when necessary.

Use `id` as an opaque, stable key for Markdown footnotes. A body claim can then use a keyed footnote such as `[^gmail-message-abc123]`. Do not use list position as attribution: reordering sources must not change the source attached to a claim.

Keep the source reference space as a union rather than forcing every source into one URI scheme. A `memory://` reference, a `raw:gmail/...` descriptor, a bundle-relative path, and an HTTPS URL carry different portability and resolution meanings. A future OKF exporter can convert a local file reference to a bundle-relative path only when that file is actually included in the exported bundle; otherwise it should preserve the original descriptor.

### Generated and verified

`generated.by` is required within `generated`; `generated.at` records the last meaningful content change. The recommended actor is `wazootech-wiki/<version>`, matching the package identity in `pyproject.toml` and `package.json`. Do not emit both a package actor and an unrelated CLI actor for the same event; actor identity should remain stable and unambiguous.

`verified` is a list of independent events, each with `by` and `at`. A producer may accept a bare mapping when reading, but should emit the list form. `wiki check`, `wiki lint`, and `wiki fmt` establish structural and presentation integrity; they do **not** verify claims against their sources. A successful CI run must not by itself cause a page to receive `verified`.

The derived OKF trust tiers are:

- no `verified` field: **unverified**;
- only non-human verification actors: **machine-confirmed**;
- at least one `human:<id>` verification actor: **human-reviewed**.

### Lifecycle

`status` is optional and defaults to `stable` for OKF consumers. When present, use only `draft`, `stable`, or `deprecated`. `stale_after` is an optional absolute instant; a page is stale when the current instant is greater than or equal to it. It is not a relative TTL.

All OKF timestamps should be ISO 8601 datetimes with an explicit UTC offset. The producer must distinguish `generated.at` (when the page changed) from `sources[].last_modified` (when evidence changed) and `verified[].at` (when a check occurred).

## SHACL shape design

Do not add an active `OKF_Shape.md` in this research-only change. A shape file would be indexed as a live SHACL document and could change `wiki check` behavior before the optional profile has an agreed enforcement boundary.

The implementation-ready design for a later `OKF_Shape.md` is:

1. Use `sh:targetSubjectsOf` for `schema:sources`, `schema:generated`, `schema:verified`, `schema:status`, and `schema:stale_after`, so the shape applies only when an optional family is present. Do not target every page by `schema:TechArticle` or a generic inferred class.
1. Set `sh:minCount: 0` on the top-level optional properties. Missing families must never fail validation.
1. When a family is present, validate its blank nodes: `sources` entries require `schema:resource`; `generated` requires `schema:by` and `schema:at`; verification entries require `schema:by` and `schema:at`; `status` uses an `sh:in` list; and `stale_after` uses an `xsd:dateTime` datatype.
1. Treat one `verified` mapping and a list of mappings identically. The graph compiler already produces repeated blank nodes for list entries and one blank node for a bare mapping.
1. Preserve unknown frontmatter fields and do not constrain unknown `type` values. This is the product shape layered on top of OKF's permissive baseline, not a replacement for it.

The future shape should be paired with fixtures for absent families, a complete family, a bare `verified` mapping, an unknown extension field, an invalid status, and a source entry missing `resource`. It should be introduced only alongside an explicit `check` profile or documented opt-in; the baseline `wiki check` path must remain permissive.

## `wiki export --okf` profile

The current export machinery is the wrong layer for producing OKF directly. `src/wiki/wiki.py:348-427` loads frontmatter and serializes RDF; it does not copy Markdown bodies, preserve the original YAML spelling, create bundle directories, or write indexes. An OKF profile must therefore be a bundle exporter, not an RDF serializer with a different label.

A future `wiki export --okf` should:

- accept an output directory rather than treating `-o` as only a single serialized file;
- copy or render each selected Markdown document while preserving its body and unknown frontmatter fields;
- create a bundle-root `index.md` whose only frontmatter declaration is `okf_version: "0.2"`, with an index body generated from exported documents;
- preserve standard Markdown links and make any rewritten bundle-relative links portable;
- populate `sources` from producer-recorded evidence and existing page references such as `memory://`, `raw:<source>/`, local raw paths, and external URLs;
- never invent `verified`, credibility signals, or freshness dates from the fact that export succeeded;
- leave Attested Computation concepts and full computation/receipt semantics out of the first cut;
- retain Git history as the preferred distribution mechanism where available.

The profile should copy the source frontmatter first and only add missing OKF fields when the producer has authoritative data. It should not reconstruct YAML from RDF: the current graph representation turns nested mappings into blank nodes and can turn unknown CURIE-like strings into literals, which is insufficient for lossless OKF round-tripping.

## Consumer check and recommendation

There is a real external ecosystem: Google maintains the canonical OKF v0.2 specification and Knowledge Catalog tooling that maps OKF fields into a catalog aspect, while OpenWiki has adopted v0.2 output and its own validator. Those consumers establish that the format is not purely hypothetical.

There is not yet a Wazoo consumer that justifies shipping `--okf` in Wiki CLI. The checked-out `wazootech/memory` repository uses raw captures, enrichment scripts, Markdown pages, and Wiki CLI checks, but has no OKF reader or `okf_version` bundle. Worlds exposes RDF quad import/export and SPARQL, not OKF bundle ingestion. Consequently, `--okf` would currently be a producer-side compatibility promise without an in-repo acceptance fixture.

**Recommendation: spec-only now; defer the export profile.** Adopt and document the optional convention now, then create a focused `wayfinder:task` only when one of these is true: a Wazoo consumer is committed to reading an OKF bundle, Google Knowledge Catalog interop is an active deployment goal, or a real downstream agent needs a portable Markdown bundle. That task should begin with a checked-in fixture and round-trip test, then implement the bundle writer and only afterward add the CLI flag.

## Boundary with the claims runtime

OKF answers page-level questions: what materials a page derives from, who generated it, what verification events occurred, and whether its lifecycle says it is stale or deprecated. It does not establish claim-level truth, compute a credibility score, or provide an attestation runtime.

The claim-level surface belongs to the fact ledger and Worlds: asserted quads, named-graph provenance, source identity, and SPARQL queries. A page may point to those records through `sources` or a resource reference, but OKF should not duplicate the claims sidecar. In particular:

- `sources` says where the page or concept derives from; it does not prove every claim in the body.
- `verified` records a check event; it does not make the page true and must not be set merely because structural checks passed.
- an Attested Computation is explicitly out of scope for the first Wiki CLI profile; its executor, receipt, and attester lifecycle belong to a future runtime contract.

This keeps the RDF-native Wiki CLI model intact while giving generated pages a portable trust summary.

## Wayfinder recommendation

Promote one narrow implementation task after this research ticket:

> Add an opt-in OKF v0.2 producer profile for generated pages: emit `sources` and `generated`, preserve unknown fields, expose a permissive family validator behind an explicit profile, and add fixtures for source IDs, keyed footnotes, verification events, lifecycle dates, and stable actor values.

Do not promote `wiki export --okf` yet. Cross-list the implementation task with [#267](https://github.com/wazootech/wiki/issues/267), because the experience-to-wiki loop is the first producer that needs deterministic generation stamps and source IDs, and [#261](https://github.com/wazootech/wiki/issues/261), because the memory-first repositories provide the source-capture boundary that `sources` must preserve. Keep [#208](https://github.com/wazootech/wiki/issues/208) separate: Agent Skills management is adjacent to OKF but does not define provenance for wiki pages.

## Related pages

- [Declarative Knowledge](Declarative_Knowledge.md) — claim and graph semantics remain separate from page-level trust.
- [Procedural Knowledge](Procedural_Knowledge.md) — generated procedures need source and lifecycle context.
- [Learning Systems](Learning_Systems.md) — provenance is useful for recursive, agent-maintained knowledge.
- [LLM Wiki](LLM_Wiki.md) — the principal generated-page use case.
- [Recursive Semantic Datasets](Recursive_Semantic_Datasets.md) — source datasets and derived semantic projections.
- [Memory Repo Best Practices](https://wiki.wazoo.dev/Memory_Repo_Best_Practices/) — raw capture and causal provenance boundary; this page is maintained outside this repository.

## References

- [OKF v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md), especially §§5, 6, 7, 10, 11, 12, and 13.
- [OpenWiki OKF v0.2 adoption issue](https://github.com/langchain-ai/openwiki/issues/580) — producer migration from `timestamp` to `generated` and addition of `sources`.
- [OpenWiki implementation review](https://openknowledgeformat.com/implementations/openwiki) — practical separation of baseline conformance from richer product validation.
- [Wiki CLI export documentation](wiki_export.md) — current RDF and JSON-LD export contract.
- [Wiki CLI configuration](Wiki_Configuration.md) — graph context, input, and validation configuration.
- [Wiki CLI design philosophies](Design_Philosophies.md) — Git history and semantic-wiki boundaries.
