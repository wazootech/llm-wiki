---
type: TechArticle
headline: Memory Repo Best Practices
description: The memory-first convention for per-owner wiki repositories — structure, naming, and continuity rules for durable, append-only second-brain repos managed with the wiki toolchain.
---

# Memory Repo Best Practices

A **memory repo** is a per-owner wiki graph repository that is the durable store for one owner or organization's knowledge: typed wiki pages, per-source immutable datasets, connector code, and validation all live in one repository. This is the "wiki repository memory-first" model. This document is the spec that the [memory-first wiki repos issue](https://github.com/wazootech/wiki/issues/261) implements and that [connector memory wiring](https://github.com/EthanThatOneKid/ethanpedia/issues/45) builds against.

## Model

The wiki repository _is_ the memory. There is no separate data tier: raw captures, normalized records, cursors, and bookkeeping live in the same repository as the knowledge graph, so the graph and its sources cannot drift.

```
EthanThatOneKid/
  .github/       # identity, meta, policies         (uniform owner special repo)
  workspace/     # dev-surface harness               (uniform owner special repo)
  memory/        # the memory wiki repo               (uniform owner special repo)
```

## Naming

- **Uniform per-owner name:** the memory repo is named `memory` under each owner or organization, joining `.github` and `workspace` as the third uniform owner special repo. Examples: `EthanThatOneKid/memory`, `wazootech/memory`.
- **Role suffix:** the `-pedia` suffix previously designated knowledge repos (`ethanpedia`, `wazoopedia`). Going forward it describes the memory role: data repositories use the `memory` family, not `-pedia`.
- **Per-source datasets are subtrees**, not repositories: `raw/<source>/` inside the memory repo.
- **Escape hatch:** if a single source outgrows the shared repo (volume, access control, or CI isolation), split that subtree to a per-source repo named `<product>-<source>-memory` (e.g. `ethanpedia-calendar-memory`). Do not split preemptively.
- **Transcription:** repo and directory names use hyphens (`x-bookmarks`, `gemini-notes`); connector Python packages keep underscores (`x_bookmarks`, `gemini_notes`).
- **Page filenames:** standard wiki conventions (title-case, underscore, one file per entity).

## Repository structure

```
memory/
  README.md
  wiki/                         # typed knowledge graph (living documents)
  raw/<source>/                 # immutable captures, append-only (data)
    <capture-files>             # unique per-item filenames
  raw/<source>/cursor           # monotonic opaque cursor
  raw/<source>/SUMMARY.json     # run bookkeeping
  connectors/<name>/            # connector code (centralized, not per-repo)
  queries/                      # saved SPARQL queries
  wiki.yml                      # graph context, validation config
  .github/workflows/
    memory-check.yml            # append-only + SUMMARY-schema invariant
    check.yml                   # wiki check + wiki fmt --check
```

`wiki/` pages are living documents. Everything under `raw/` is immutable and append-only.

## Continuity contract

A memory repo must be stable, unchanged, and replayable over time. It is the durable store that an ephemeral sandbox trusts — reproducibility is the property that makes host loss safe.

1. **Append-only by construction.** Capture files use unique per-item or per-run filenames (timestamp- or source-ID-based) and are never overwritten. Re-cloning therefore never conflicts on `git pull`, because append-only files cannot collide.
1. **No history surgery.** Never `force-push`, `reset`, or rewrite memory repo history. Enforce with branch protection: force-push and deletion disabled on `main`, administrator overrides off.
1. **Monotonic cursor.** Cursors advance only forward. Replays are idempotent and never regress state.
1. **Dedup by source identifier.** Every capture carries a source ID (`schema:identifier`); duplicate IDs within or across runs are skipped.
1. **No TTL, no pruning.** Memory is the second-brain promise: nothing expires because of age. The repo is the memory, not a cache of it.
1. **Run bookkeeping.** Each source keeps a `SUMMARY.json` that records the last run and its result; it doubles as the connector `status` output.
1. **Provenance, not copies.** Wiki pages reference captures through stable URLs or URIs (`raw:<source>/...` inside the repo, or `memory://<owner>/<source>/<path>` across repos) rather than inlining raw content.

## Datasets per source

Every connector owns one dataset subtree, `raw/<source>/`, with:

- **Immutable captures:** append-only files written once per item, named from the source identifier plus a readable slug (e.g. `raw/gmail/<message-id>-<slug>.md`).
- **cursor:** an opaque, monotonic position marker the connector reads at fetch start and writes only after the run succeeds.
- **SUMMARY.json** — the standardized bookkeeping contract:

```json
{
  "status": "ok",
  "connector": "<source>",
  "fetched": 42,
  "ingested": 5,
  "skipped_by_appraisal": 37,
  "actionable_candidates": 5,
  "cursor": "opaque-cursor-value",
  "lastRun": "2026-08-27T06:00:00-07:00"
}
```

Connectors expose a shared CLI: `python -m connectors.<name> status`, `fetch`, and `process <file>`. The shared accounting (cursor, capture, dedup, summary, CLI) is provided by `ConnectorBase`; the per-connector extraction, appraisal, and capture formatting are the only unique code.

## Connectivity and auth

The connector auth approach is intentionally **deferred (TBD)**: no third-party OAuth middleware (for example Nango or Composio) is prescribed. The preference is to hand-roll per-connector auth. Candidate mechanisms to evaluate before wiring each fetch:

- Google family (calendar, gmail, drive): OAuth device flow with refresh tokens stored in the secrets vault (and cloud secrets for the agent runtime)
- Signal: `signal-cli` on a persistent host
- X bookmarks: local fixture

Credentials never enter the repository; they live in the secrets vault and are injected by the orchestrator at run time.

## Runtime and orchestration

Daily automation runs as a Letta cloud agent (cloud sandbox + GitHub app; commits carry the bot identity). Per run the agent:

1. Clones the memory repo fresh.
1. Runs `python -m connectors.<source> fetch` for each scheduled source; captures and bookkeeping land in the same clone.
1. Generates and updates wiki pages from normalized data.
1. Gates: `wiki check` then `wiki fmt` (use `wiki check --strict` for full filename and link validation).
1. Commits one atomic change per run and pushes to `main` of the same repo.

Hard gates are structurally enforced: the validation step runs before commit, and repository CI (`check.yml` + `memory-check.yml`) is the tripwire on push. Natural-language operators follow the atomic persistence protocol: one coherent transaction per commit, checkpoint commits when blocked, no destructive history operations without approval.

## Escape hatch criteria

Split a source to `<product>-<source>-memory` only when the shared repo is genuinely constrained:

- Raw volume or repository growth dominates the wiki's graph
- A source needs separate access control (e.g. personal data permissions differ from the rest)
- A source needs independent CI

Each split is its own reviewable change: move the subtree, re-point provenance links, and re-run validation.

## Roll-out

- **Step 1 (this document):** conventions agreed.
- **Step 2 — reference deployment:** rename the current personal wiki to `EthanThatOneKid/memory`, structure `raw/` as per-source datasets, add `SUMMARY.json` and cursor conventions, enable branch protection and `memory-check.yml`. Tracked in [wazootech/wiki#261](https://github.com/wazootech/wiki/issues/261).
- **Step 3 — Calendar reference connector:** `ConnectorBase` + Google Calendar end-to-end through fetch, bookkeeping, page generation, and the daily Letta loop. Tracked in [ethanpedia#45](https://github.com/EthanThatOneKid/ethanpedia/issues/45).
- **Step 4 — replicate:** move each remaining connector onto the same pattern; stream-only provider imports stay gated on the [deferred imports ruling](https://github.com/EthanThatOneKid/ethanpedia/issues/28).

## Related

- [Second Brain](Second_Brain.md) — the conceptual model a memory repo implements
- [Personal Knowledge](Personal_Knowledge.md)
- [Recursive Semantic Datasets](Recursive_Semantic_Datasets.md) — composing git-backed wiki sources with named-graph provenance
- [Letta MemFS](Letta_MemFS.md)
