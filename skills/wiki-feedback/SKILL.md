---
name: wiki-feedback
description: >-
  Drafts and files repeatable Wiki CLI integration/template proposals. Use when the user asks
  to evaluate a new integration, create a template proposal issue, compare an external tool with
  the Wiki toolchain, or turn integration feedback into a GitHub issue. Reviews existing
  template issues in the wazootech/wiki-templates monorepo first, identifies the integration
  category, preserves Wiki CLI's source-layer boundary, and recommends the GitHub issue form for
  final filing.
---

# Wiki Feedback Skill

Use this skill for Wiki CLI ecosystem feedback, especially new integration or template proposals.

## Core rule

Every integration proposal must make the boundary explicit:

- Wiki CLI owns the semantic Markdown source layer: `wiki.yml`, documents, frontmatter, SHACL, JSON Schema, lint, fmt, SPARQL, RDF/JSON-LD export, render, build, and serve.
- The integration owns a distinct role: runtime memory, retrieval, publishing surface, agent workflow, issue-tracker bridge, domain model, or downstream application.
- Derived indexes, generated memories, PR comments, vector stores, and external runtimes are not the canonical Wiki corpus unless explicitly promoted into Wiki pages and validated.

## Workflow

1. Review existing open issues with label `template` in the
   [wazootech/wiki-templates](https://github.com/wazootech/wiki-templates) repo
   (`gh search issues --repo wazootech/wiki-templates --label template --state open`).
1. Classify the proposed integration:
   - Agent workflow / coding agent
   - Runtime memory / retrieval
   - Static site / publishing surface
   - Issue tracker / work management
   - Domain-specific knowledgebase
   - Ontology / linked data
   - RAG / GraphRAG / search
1. Identify nearby existing issues and avoid duplicate scope.
1. Draft the proposal using the `integration-template.yml` issue form in
   [wazootech/wiki-templates](https://github.com/wazootech/wiki-templates).
1. Recommend filing through the GitHub issue form when the user wants durable feedback.
1. If asked to execute, create the issue in `wazootech/wiki-templates` with label `template`.

## Proposal sections

Use these sections when drafting by hand:

1. Goal
1. Why this matters
1. Boundary between Wiki CLI and the integration
1. Recommended architecture
1. Template subdirectory
1. Template contents
1. Wiki corpus examples
1. Validation and CI
1. README positioning
1. Non-goals
1. Acceptance criteria
1. Open questions
1. Related issues and references

## Quality bar

A good proposal:

- states the proposed template as a subdirectory of the
  [wazootech/wiki-templates](https://github.com/wazootech/wiki-templates)
  monorepo, e.g. `wazootech/wiki-templates/<integration>/` (templates are
  monorepo subdirectories, not standalone `wazootech/wiki-*-template` repos);
- explains what Wiki CLI owns and what the integration owns;
- includes deterministic validation commands;
- avoids requiring private credentials in CI;
- includes provenance and citation expectations;
- names related template issues;
- cites primary external documentation;
- explains whether the template is standalone or should fold into an existing template.

## Default validation block

```bash
wiki -c wiki.yml fmt --check
wiki -c wiki.yml lint --strict
wiki -c wiki.yml check --strict
wiki -c wiki.yml render --check
```

Use `docs/wiki.yml` instead of `wiki.yml` when the template follows this repository's dogfooding layout.

## Filing guidance

Template proposals are tracked in the [wazootech/wiki-templates](https://github.com/wazootech/wiki-templates)
repo, not in `wazootech/wiki`. Prefer the GitHub issue form there:

`.github/ISSUE_TEMPLATE/integration-template.yml`

If filing via `gh issue create`, preserve the same structure and apply the `template` label:

```bash
gh issue create --repo wazootech/wiki-templates --label template --body-file proposal.md
```

The [template program umbrella issue](https://github.com/wazootech/wiki-templates/issues/4)
tracks the ranked backlog; the proposal can reference its bucket when relevant.
