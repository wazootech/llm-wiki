---
type: TechArticle
headline: Learning Systems
description: Continual learning versus recursive learning — how agent-managed wikis accumulate knowledge over time and refine themselves through iterative loops.
---

# Learning Systems

An [LLM Wiki](LLM_Wiki.md) grows smarter over time through two distinct learning modalities: **continual learning** (temporal accumulation and retention) and **recursive learning** (iterative self-application and refinement). Both are essential to the [Vivary](Vivary.md) agent loop and the [wiki](wiki.md) ecosystem, but they operate at different time scales and target different dimensions of the knowledge base.

## Continual learning

**Continual learning** is the forward accumulation of knowledge over time: each session, each document, each query adds to the corpus without catastrophic forgetting. The wiki grows as a compounding asset — pages are added, frontmatter is enriched, the RDF graph expands — and prior knowledge remains accessible and valid.

In this ecosystem, continual learning manifests as:

- The **[LLM Wiki](LLM_Wiki.md) pattern** — a persistent, interlinked Markdown corpus that an agent maintains across sessions. Raw inputs are compiled into structured pages; the knowledge base compounds rather than being regenerated each time.
- **[Farzapedia](Farzapedia.md)** — Farza's proof-of-concept: 2,500 unstructured entries became ~400 clean, linked wiki articles, then continued to grow and improve.
- **[wiki](wiki.md) validation** — `wiki check` and `wiki lint` ensure each new page meets structural and convention standards, so the corpus stays healthy as it accumulates.
- **[Agent Memory Filesystems](Agent_Memory_Filesystems.md)** — persistent memory stores (SMFS, MemFS, Wiki CLI) that survive session boundaries and let knowledge accrete.

The key property: **knowledge persists and compounds forward**. The agent does not start from zero each session.

## Recursive learning

**Recursive learning** is iterative self-application: prior outputs, learned structures, or verified states feed back into the next cycle as inputs. The agent refines its own process by examining what it produced and improving it.

In this ecosystem, recursive learning manifests as:

- The **[Vivary](Vivary.md) agent loop** — read `.vivary/context.md` first, act, verify with `tropo check`, and stop at deliberate human gates. Verification results and gate outcomes are recorded as receipts that later turns reuse.
- **[Vivary governance](Vivary.md#governance--capsules-receipts-and-policy)** — `tropo check` gates the whole graph, and Task Capsules + Execution Receipts bind what ran to one question and scope, so verification feeds the next cycle.
- **[Procedural Knowledge](Procedural_Knowledge.md)** — self-updating workflows: [SPARQL](SPARQL.md) blocks that [render](wiki_render.md) live results, [SHACL](SHACL.md) shapes that validate structure, and [wiki skills](Wiki_Skills.md) that encode repeatable processes.
- **[wiki render](wiki_render.md)** — `wiki render --check` detects stale SPARQL result blocks from a prior run and flags them for regeneration, closing the recursive loop.

The key property: **the system improves its own process by examining its output**. The loop feeds into itself.

## Comparison

| Dimension         | Continual learning                                          | Recursive learning                                                          |
| ----------------- | ----------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Time axis**     | Forward accumulation — each session adds                    | Cyclical refinement — each loop re-evaluates                                |
| **Storage model** | Growing corpus of documents and graph triples               | Self-modifying workflows, skills, and memory                                |
| **Agent role**    | Gardener — tends and expands the wiki                       | Meta-cognitive — reflects on and improves its own process                   |
| **Scale**         | Sessions to months                                          | Single turn to a few turns                                                  |
| **Risk**          | Stale or contradictory pages if unchecked                   | Infinite loops or over-optimization without gates                           |
| **Examples**      | Adding a new page, enriching frontmatter, growing the graph | `tropo check` gates in Vivary, `wiki render --check`, receipt-driven review |

## How they compose

Continual and recursive learning are complementary, not competing. A healthy agent-managed wiki uses both:

1. The agent adds and refines pages over time — **continual** growth of the knowledge base.
1. On each turn (or heartbeat), the agent verifies its latest output, learns from verification results, and updates its skills or memory — **recursive** refinement of process.
1. The recursive loop feeds the continual corpus: insights from verification become new frontmatter, corrected links, or updated shapes.

The **[LLM Wiki](LLM_Wiki.md)** pattern is the continual surface; the **[Vivary](Vivary.md) agent loop** is the recursive engine. They meet in the middle: a wiki that grows perpetually and improves itself on every interaction.

## Related

- [LLM Wiki](LLM_Wiki.md) — pattern origins and compounding knowledge base design
- [Vivary](Vivary.md) — agent workspace with typed records, verification gates, and receipts
- [Agent Memory Filesystems](Agent_Memory_Filesystems.md) — persistent memory across sessions
- [Declarative Knowledge](Declarative_Knowledge.md) — facts and structures that accumulate
- [Procedural Knowledge](Procedural_Knowledge.md) — workflows and processes that self-improve
- [Farzapedia](Farzapedia.md) — continual learning proof of concept
- [wiki render](wiki_render.md) — stale-block detection as recursive feedback
