---
type: TechArticle
headline: LLM Wiki
description: A persistent knowledge codebase for AI-assisted knowledge management.
---

# LLM Wiki

An **LLM Wiki** is a modern design pattern for [Personal Knowledge](Personal_Knowledge.md) (PKM). It treats a user's [personal knowledge](Personal_Knowledge.md) repository as a clean, interlinked, machine-readable "codebase" that growing AI agents can operate on over time.

This replaces fleeting AI chats and unstructured RAG databases with a persistent, compounding core of intelligence.

The **LLM Wiki** is a modern design pattern for [personal knowledge](Personal_Knowledge.md) management (PKM) popularized by **[Andrej Karpathy](https://x.com/karpathy/status/2039805659525644595)** in early April 2026. It represents a paradigm shift from traditional **[Retrieval-Augmented Generation](Retrieval_Augmented_Generation.md) (RAG)**—where an AI searches through unstructured files on the fly—to a **compiled, persistent, and compounding knowledge base**.

## Karpathy's viral analogy

Karpathy summarized the ultimate relationship between the human, the AI, and the files with his famous analogy:

> "[Obsidian](Obsidian.md) is the IDE; the LLM is the programmer; the wiki is the codebase."

He highlighted that traditional AI chat windows are "stateless" and fleeting, forcing you to reconstruct context every time you start a session. In contrast, an LLM Wiki compiles your unstructured raw inputs (diaries, PDFs, articles, research notes) into a clean, interlinked Markdown codebase (`[slug]`) that grows more intelligent and interconnected over time.

## Farza's follow-up and [Farzapedia](Farzapedia.md)

Developer **Farza** (founder of buildspace) created [Farzapedia](Farzapedia.md) as the definitive real-world proof of concept for the LLM Wiki pattern:

- **The Input**: Fed approximately **2,500 unstructured entries** (comprising personal diary entries, Apple Notes, and raw iMessage histories) to an LLM agent.

- **The Compilation**: The LLM agent parsed, categorized, and synthesized the raw materials, outputting **~400 beautifully structured, clean, and heavily interlinked wiki articles**.

- **The Takeaway**: [Farzapedia](Farzapedia.md) demonstrated that an LLM can act as an objective, disciplined "gardener" of a human's mind, creating a private, local, and navigably explicit knowledge base that can be queried by any downstream AI.

## Integrating the LLM Wiki in this wiki

This [wiki](wiki.md) repository is built directly on the principles of the LLM Wiki design pattern. The wiki grows through two complementary learning modalities — **continual** (temporal accumulation) and **recursive** (iterative self-refinement) — documented in [Learning Systems](Learning_Systems.md). It enforces:

1. **Declarative Frontmatter**: Structuring YAML-LD metadata to make pages machine-readable.

1. **Procedural Automation**: Using subcommands like [wiki check](wiki_check.md) to validate SHACL shapes and JSON Schema frontmatter, and [wiki render](wiki_render.md) to execute [SPARQL](SPARQL.md) queries dynamically, compiling the graph's intelligence back into static Markdown.

## References

- [Andrej Karpathy on X: LLM Knowledge Bases](https://x.com/karpathy/status/2039805659525644595) — April 2026 thread on raw ingest, LLM compilation into markdown wikis, Obsidian as IDE, and incremental Q&A without RAG.

## Related

- [wiki](wiki.md) — including [Wiki CLI templates](wiki.md#ecosystem-templates) ([wiki-templates/llm-wiki](https://github.com/wazootech/wiki-templates/llm-wiki))
- [Learning Systems](Learning_Systems.md) — continual versus recursive learning
- [Declarative Knowledge](Declarative_Knowledge.md)
- [Procedural Knowledge](Procedural_Knowledge.md)
- [Farzapedia](Farzapedia.md)
- [Getting Started](Getting_Started.md)
- [SPARQL](SPARQL.md)
