---
type: TechArticle
headline: Agent Memory Filesystems
description: Comparison of filesystem-metaphor approaches for long-term LLM agent memory, including Wiki CLI, SMFS, and MemFS.
---

# Agent Memory Filesystems

A growing class of tools gives LLM agents **persistent memory through a filesystem metaphor**: `ls`, `cat`, `grep`, and markdown-shaped trees instead of bespoke vector SDKs or unbounded chat context. Three prominent approaches—**[wiki](wiki.md)**, **[Supermemory SMFS](Supermemory_SMFS.md)**, and **[Letta MemFS](Letta_MemFS.md)**—all support the [LLM Wiki](LLM_Wiki.md) / [Personal Knowledge](Personal_Knowledge.md) vision but optimize for different backends and workflows.

## Shared idea

Traditional chat UIs are largely stateless. These systems let an agent (and often a human) **read and write durable artifacts** as files, compounding knowledge across sessions. They pair well with coding agents ([Obsidian Integration](Obsidian_Integration.md) as viewer, terminal tools as compiler) but differ in where truth lives and how recall works.

## Comparison with [wiki](wiki.md), [Letta MemFS](Letta_MemFS.md), and [Supermemory SMFS](Supermemory_SMFS.md)

### Feature matrix

|                          | [wiki](wiki.md)                                              | [Supermemory SMFS](Supermemory_SMFS.md)      | [Letta MemFS](Letta_MemFS.md)               |
| ------------------------ | ------------------------------------------------------------ | -------------------------------------------- | ------------------------------------------- |
| **Metaphor**             | Semantic markdown **wiki** / codebase                        | Cloud container as **mount** or virtual bash | **Git repo** of memory markdown             |
| **Authority**            | Your wiki on disk                                            | Supermemory API                              | Local Git (+ Letta Cloud for API agents)    |
| **Structured semantics** | YAML-LD, [SHACL](SHACL.md), JSON Schema, [SPARQL](SPARQL.md) | Memory paths + cloud graph                   | `description` frontmatter; optional folders |
| **Hot context**          | Agent chooses pages to open                                  | `profile.md` + semantic grep                 | `system/` loaded every turn                 |
| **Search**               | SPARQL, link graph, `wiki query`                             | Semantic `grep` (literal with flags)         | Tree + on-demand file read                  |
| **Validation**           | `wiki check` (SHACL, JSON Schema, layout)                    | Supermemory indexing rules                   | Git + agent discipline                      |
| **Publishing**           | Static site, RDF export                                      | N/A (runtime memory)                         | N/A (agent memory)                          |
| **Typical user**         | Wiki authors, PKM + semantics                                | Multi-modal, multi-source agents             | Letta Code coding agents                    |

### When to use which

**[wiki](wiki.md)** — You want a **local-first, explicit, interlinked wiki** that doubles as documentation: [Declarative Knowledge](Declarative_Knowledge.md) in frontmatter, [Procedural Knowledge](Procedural_Knowledge.md) in `wiki check` / `wiki render`, optional [Retrieval Augmented Generation](Retrieval_Augmented_Generation.md)-style synthesis via SPARQL instead of opaque embeddings. Fits [Farzapedia](Farzapedia.md)-style gardens with machine-checkable structure.

**[Supermemory SMFS](Supermemory_SMFS.md)** — You need **scale, semantic recall, and integrations** (documents, images, Slack, Notion, etc.) with minimal agent onboarding: mount `agent_memory/` or drop in `@supermemory/bash` for serverless. Accept cloud authority and background graph maintenance.

**[Letta MemFS](Letta_MemFS.md)** — You build on **Letta Code** and want **Git history, human-editable memory, and a fixed always-on `system/` slice** for persona and project facts, with everything else progressively disclosed.

## Complementary use

These are not always mutually exclusive. A team might maintain a published **[wiki](wiki.md)** wiki for product knowledge while a Letta agent keeps **private MemFS** notes, or mount **SMFS** for ingested corpora that feed summaries written into the wiki. The [wiki](wiki.md)’s strength is **shared, validated, link-stable markdown**; SMFS and MemFS optimize **per-agent runtime memory**.

## Related pages

- [Vivary](Vivary.md) — agent workspace standard (thin .vivary/ contract + tropo typed graph)
- [LLM Wiki](LLM_Wiki.md) — pattern origins (Andrej Karpathy, Farza Majeed)
- [Second Brain](Second_Brain.md) — PKM goals
- [Style Guide](Style_Guide.md) — conventions for this wiki
