---
name: wiki
description: >-
  Manages Wiki CLI end to end — install and verify wazootech-wiki, scaffold with wiki init,
  audit vault hygiene (fmt, lint, check, render), enrich wikis from raw source material,
  plan and execute vault improvements, deploy to GitHub Pages, and keep code wikis
  (docs/) in sync with their source via Git-anchored delta sync.
  Use whenever the user mentions wiki, Wiki CLI, wazootech-wiki, wiki init, wiki.yml, wiki.yaml, broken links,
  lint/check failures, pre-PR wiki review, GitHub Pages for a wiki, docs drift, syncing documentation
  after source changes, or getting started with semantic markdown — even if they do not say "skill".
  Route to one workflow reference, complete that job, and stop.
---

# Wiki CLI Skill

Procedural knowledge for coding agents working with [Wiki CLI](https://github.com/wazootech/wiki) (`wiki` command, PyPI **`wazootech-wiki`**).

Skills under `skills/` are agent knowledge — **not** wiki pages. Do not add `skills/` to `wiki.input`.

## Principles

1. **Deterministic work belongs in scripts and the CLI** — run `skills/wiki/scripts/verify.sh` and `skills/wiki/scripts/audit.sh` instead of reimplementing validator pipelines in prose.
1. **One workflow per turn** — read the matching reference below, finish that job, stop. Do not chain install → create → deploy unless the user asked for the full flow.
1. **Advisor-executor model for vault changes** — survey and plan changes as a read-only advisor; dispatch executor subagents to apply edits in isolated worktrees, and review their diffs. Never directly edit user files without approval.
1. **Deploy uses wholesale templates** — embed [workflow-template-uv.yml](references/workflow-template-uv.yml) or [workflow-template-pip.yml](references/workflow-template-pip.yml) in full; substitute placeholders only.
1. **No config migration shims** — unknown wiki config keys fail at load; document upgrades in CHANGELOG and wiki docs only.

## Route first

| User intent                                  | Read                                           | Stop when                        |
| -------------------------------------------- | ---------------------------------------------- | -------------------------------- |
| CLI missing, stale, or verify install        | [references/install.md](references/install.md) | CLI verified or blocker reported |
| New wiki, `wiki init`, tweak step            | [references/init.md](references/init.md)       | Scaffold summarized              |
| Audit, improve, pre-PR, lint/check failures  | [references/improve.md](references/improve.md) | Findings report delivered        |
| Formatting, linting, check categories detail | [references/audit.md](references/audit.md)     | Audit criteria verified          |
| Ingest raw material into wiki pages         | [references/enrich.md](references/enrich.md)   | Change report delivered          |
| Generate handoff plans, plans layout         | [references/plan.md](references/plan.md)       | Plan file written                |
| Execute plans, review diff, publish issues   | [references/loop.md](references/loop.md)       | Executor output verified         |
| GitHub Pages, deploy workflow, CI publish    | [references/deploy.md](references/deploy.md)   | Workflow + URLs summarized       |
| Docs out of sync after source changes, drift check | [references/sync.md](references/sync.md) | Sync PR opened and validated     |

When the user asks for multiple intents in one message, pick the **blocking** workflow first (usually install), or the workflow they emphasized. Offer the next step in plain language.

## Shared CLI resolution

Before any wiki command:

1. Run `bash skills/wiki/scripts/verify.sh` (or `.agents/skills/wiki/scripts/verify.sh` when vendored).
1. Exit `0` → use PATH `wiki`.
1. Exit `2` (stale) → upgrade **`wazootech-wiki`** per [install.md](references/install.md).
1. Exit `1` (missing) → install or stop with one-line PyPI hint; read [install.md](references/install.md) for paths.

In the **Wiki CLI repository checkout**, if PATH `wiki` fails but `pyproject.toml` exists, use `uv run wiki` or `python -m wiki` when both `--help` and `fmt` capability pass.

Zero-install equivalent: `npx wazootech-wiki <args>` or `uvx --from wazootech-wiki wiki <args>` in place of `wiki <args>`.

## Deterministic scripts

```bash
bash skills/wiki/scripts/verify.sh
bash skills/wiki/scripts/audit.sh -c path/to/wiki.yml [FILE...]
```

`audit.sh` runs fmt → lint → check → render (`--strict` / `--check`), then `wiki link --check` only when wired in `.github/workflows/`. In this repo: `-c docs/wiki.yml`.

## Reference index

| File                                           | Purpose                                                                   |
| ---------------------------------------------- | ------------------------------------------------------------------------- |
| [references/install.md](references/install.md) | Install and verify CLI (includes programmatic API)                        |
| [references/init.md](references/init.md)       | `wiki init` + configuration wizard tweaks                                 |
| [references/improve.md](references/improve.md) | Recon, audit, vet, and planning workflow                                  |
| [references/audit.md](references/audit.md)     | Audit check categories and style spot-check                               |
| [references/enrich.md](references/enrich.md)   | Ingest raw material into canonical wiki pages with semantic frontmatter    |
| [references/plan.md](references/plan.md)       | Hand-off plans format and layout                                          |
| [references/loop.md](references/loop.md)       | Running executors, reviewing work, reconciling backlog, publishing issues |
| [references/deploy.md](references/deploy.md)   | GitHub Pages workflow and alignment checklist                             |
| [references/sync.md](references/sync.md)       | Git-anchored delta sync of a code wiki (`docs/`) with its source tree     |
| [references/workflow-template-wiki-sync.yml](references/workflow-template-wiki-sync.yml) | Scheduled CI sync template — embed wholesale |

Human docs: [Wiki Skills](https://github.com/wazootech/wiki/blob/main/docs/wiki/Wiki_Skills.md), [Getting Started](https://github.com/wazootech/wiki/blob/main/docs/wiki/Getting_Started.md), [Wiki Programmatic API](https://github.com/wazootech/wiki/blob/main/docs/wiki/Wiki_Programmatic_API.md).
