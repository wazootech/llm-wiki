---
name: wiki-sync
description: >-
  Keep a repository's code wiki (docs/) in sync with its source using a Git-anchored delta process.
  Use when asked to sync or refresh documentation after source changes, verify the wiki still matches
  the tree (file inventory, task tables, symbol links, behavior prose), re-run deno doc --json symbol
  inventories, or maintain a code wiki incrementally (e.g. wazootech/sparql-engine's docs/). Defaults
  to drift-free docs — no line numbers, machine-specific measurements, or test counts — with an
  opt-in detail_level directive in the repo's AGENTS.md for consumers who want them. Never regenerates a wiki
  from scratch — it diffs the commits since the last sync anchor and edits only the affected pages. Ships a
  GitHub Actions template for scheduled CI syncs.
---

# `wiki-sync` skill

Keep a code wiki (`docs/`, typically a GitHub Pages Jekyll site) truthful to its
source tree with a **Git-anchored delta process** — the approach popularized by
LangChain's OpenWiki: treat the last-synced commit as an anchor, diff forward
through Git history, and apply only the additions and deletions the diff
demands. Never regenerate the whole wiki; never hand-wave structure that can be
checked against the tree.

**The documented default is the drift-free style.** Wiki pages carry no line
numbers, no machine-specific measurement numbers, and no test counts — artifacts
that go stale when a file grows a line, a Deno version or machine re-times a
benchmark, or a test is added, without telling a reader anything structural
about the code. The detailed style stays fully available as an opt-in
`detail_level` directive in the wiki-owning repo's `AGENTS.md`; "execute to
verify" applies only to numbers a repo has opted into.

This is a *code-wiki* maintenance skill (repo `docs/` folders), distinct from
Wiki CLI's semantic-wiki authoring flows in the `wiki` skill. The wiki it was
built for: `wazootech/sparql-engine`, whose docs live in `docs/` (pages
`00`–`09`).

## When to run

- A source PR landed (or a branch changed) and the wiki must reflect it.
- Asked to "sync the docs", "refresh the wiki", "update the docs for the
  latest changes", or "check the docs are still accurate".
- A documented symbol reference, file path, test count, or (when opted in) line
  reference feels stale.

## Detail levels

The wiki's detail level is declared in the **wiki-owning repo's `AGENTS.md`** —
the instruction channel every agent already loads when working in that repo —
not in a config file. An explicit directive looks like:

```markdown
<!-- in the repo's AGENTS.md, next to its docs-maintenance notes -->
We keep `docs/` in sync with the `wiki-sync` skill at `detail_level:
line-numbers` (see skills/wiki-sync/SKILL.md).
```

No explicit directive (or no `AGENTS.md`) means `minimal` — the default.

| `detail_level`      | Style                                                                  |
| ------------------- | ---------------------------------------------------------------------- |
| `minimal` (default) | Drift-free: names and links only — no line numbers, measurements, or counts |
| `line-numbers`      | Minimal + `L<line>` citations verified via `deno doc --json`            |
| `measurements`      | Minimal + machine-specific benchmark/size/memory snapshots from `deno task bench` |
| `full`              | Minimal + line numbers + measurements + test counts                     |

**Default (`minimal` — drift-free).** Wiki docs carry only what changes when
the source structure changes:

1. **No line numbers in wiki docs.** Symbol citations reference the symbol by
   name, linked to its JSR doc page (root exports) or GitHub blob (deep
   imports) — never `L<line>`. `deno doc --json` stays in the procedure as a
   *verification* tool (confirm the symbol exists and is publicly exported)
   instead of a source of citation lines.
2. **No machine-specific measurement numbers in wiki docs.** Latency, size,
   and memory numbers (ms/iter, MiB, peak heap) live only in README.md — the
   single source of truth, where they are already regenerated from
   `bench/*-data.json`. Wiki pages keep the *methodology* prose (how a
   benchmark verifies results, what a gate measures, how to run it) and link to
   README.md's Results section; they drop the number tables.
3. **No test counts in wiki docs.** Say "the full suite passes" or link the CI
   badge; the runner is the oracle for CI, not for docs. Drop counts like suite
   totals and file line-counts.
4. **Keep what does not drift.** File inventory (path + role), task tables,
   symbol inventory (name + role + entrypoint), and prose about
   behavior/contracts still belong in the wiki — those change only when the
   structure changes.

**Opt-in (`line-numbers` | `measurements` | `full`).** Consumers who want the
detailed style declare it in their `AGENTS.md` and the skill's "execute to
verify" procedure applies to those numbers: `deno doc --json` for lines,
runner output for counts, bench snapshots for measurements — never memory or
comments. The opt-in is per repo, so each consumer chooses the style that fits
its readers.

## Core invariants

1. **Delta, not regenerate.** Only pages touched by the diff get edited.
2. **The anchor is the source of truth for "what changed".** `docs/.sync-base`
   holds the commit SHA the wiki was last synced to. Everything after it is the
   delta; everything before it is assumed in sync.
3. **The detail level is read first.** The wiki-owning repo's `AGENTS.md`
   declares what numbers, if any, the wiki carries; no explicit directive
   means `minimal`.
4. **Execute to verify — for opted-in numbers only.** Line numbers come from
   `deno doc --json`, test counts come from running the test runners, file
   lists come from `git ls-tree` — never from memory or comments. In the
   default style the check is inverted: no new `L<line>` citations or bare
   measurement units (ms/iter, MiB) may appear in `docs/`.
5. **Docs-only commits.** The sync PR must never change `src/`, `test/`, or
   `bench/` code.
6. **Anchor last.** The `.sync-base` bump happens only after validation passes
   and rides inside the docs-only commit — merging the PR and anchoring the
   wiki are the same event. An interrupted run leaves the anchor untouched, so
   the next run safely redoes the whole delta; no run-status bookkeeping is
   needed.

## Procedure

### Step 1 — Anchor and fetch

```sh
git fetch origin
BASE=$(cat docs/.sync-base)          # last-synced commit
git log --oneline "$BASE"..origin/main          # the delta
if ! git diff --quiet "$BASE"..origin/main -- src test bench .github; then
  git diff --stat "$BASE"..origin/main -- src test bench .github   # what moved
fi
```

- No commits → the wiki is current; stop and say so.
- Commits exist but none touch `src`, `test`, `bench`, or `.github` → no
  wiki-relevant delta: re-check the few touched `docs/` pages, update
  `.sync-base`, done. This path-scoped quiet check is the gate that keeps
  scheduled runs cheap ([Scheduled syncs](#scheduled-syncs-ci)) — an empty
  delta exits before verification passes or agent work begin.
- Source/test/bench commits → continue.

### Step 2 — Read the detail level

```sh
grep -i "detail_level" AGENTS.md   # minimal (default) | line-numbers | measurements | full
```

`minimal` (or absent) → the drift-free edit rules in Step 7. Opted-in levels →
the matching "execute to verify" sub-steps in Steps 4–5.

### Step 3 — Classify the delta

| Change in                | Wiki surface to touch                                              |
| ------------------------ | ------------------------------------------------------------------ |
| `src/**/*.ts`            | `04-source-map.md` symbol inventory (name + role + entrypoint link) + any page citing that file; `L<line>` refs only when opted in |
| `deno.json` tasks        | `01-quickstart.md` task lists                                      |
| `test/**` (new/renamed)  | `04-source-map.md` test tables, `05-testing.md` covered areas (counts only when opted in) |
| `bench/**`               | `04-source-map.md` bench table, `07-benchmarking.md` methodology (numbers only when opted in) |
| new/removed files        | `04-source-map.md` file inventory                                  |
| behavior/fixes           | `02-architecture.md`, `03-api-contracts.md` prose                  |
| `.github/workflows/*`    | `05-testing.md` task-table "gating" column                          |

### Step 4 — Verify the symbol graph

Default style: for each changed file, confirm every cited symbol still exists
and is publicly exported (the citation is the symbol's name + link, so no lines
to renumber):

```sh
deno doc --json src/<file>.ts | python -c "
import json, sys
d = json.load(sys.stdin)
mod = list(d['nodes'].values())[0]
for s in mod['symbols']:
    print(s['name'])
"
```

Any symbol the wiki cites by name must be in that list; drop or relink any that
is not. Do a full-tree pass when in doubt (loop over `git ls-tree -r --name-only
origin/main -- src`), not just the changed files.

Opted in (`line-numbers` or `full`): also extract the **declaration**
locations — the v2 schema nests them:

```sh
deno doc --json src/<file>.ts | python -c "
import json, sys
d = json.load(sys.stdin)
mod = list(d['nodes'].values())[0]
for s in mod['symbols']:
    print(f\"{s['name']} L{s['declarations'][0]['location']['line']}\")
"
```

Diff the output against the wiki's documented lines; update every drifted one.

### Step 5 — Verify counts and measurements (only when opted in)

Documented counts must match runner output, not comments or README prose
(comment counts have drifted before — e.g. the W3C suite was documented as
336/23 while the runner loads 345/31).

```sh
deno task test:w3c          # read the printed total/pass lines
deno task test:sparql12     # 249
deno task test:sparql12:gap # 41
deno test --allow-all src/  # unit count
deno task bench             # measurements snapshots (measurements | full)
```

Record the runner's printed totals verbatim in the docs. If the runner prints
something different from the docs, the docs are wrong. In the default
`minimal` style there are no counts or measurement tables to verify — skip this
step.

### Step 6 — Verify file inventory

```sh
git ls-tree -r --name-only origin/main -- src test bench .github
```

Compare against the `04-source-map.md` tables. Add missing files (source,
test, bench, workflow), delete rows for removed files, and check every
referenced path in the wiki resolves on disk.

### Step 7 — Edit with the delta

- Edit only the pages in Step 3's mapping.
- **Additions**: new rows/tables/sections, byte-faithful snippets.
- **Deletions**: remove rows for files/symbols that no longer exist; never keep
  a "known gap" entry for something that was fixed.
- Keep prose edits minimal; cite exact paths and, when opted in, `L<line>`
  references.
- **Default style**: cite symbols by name with a link (JSR doc page for root
  exports, GitHub blob for deep imports); never introduce `L<line>` citations,
  number tables, or counts. When the diff added a benchmark or a test, add the
  methodology prose and link to README.md's numbers instead of duplicating
  them.

### Step 8 — Validate

```sh
deno fmt --check docs/      # the wiki is formatted at width 80
# nav + front matter + link resolution (all pages, all .md links exist)
python - <<'EOF'
import yaml, glob, os
nav = yaml.safe_load(open("docs/_data/navigation.yml"))
for e in nav:
    src = "docs/README.md" if e["url"] in ("/", "/README.html") else "docs/" + e["url"].lstrip("/").replace(".html", ".md")
    assert os.path.exists(src), f"nav target missing: {src}"
for f in glob.glob("docs/*.md"):
    fm = open(f, encoding="utf-8").read().split("---", 2)
    assert len(fm) >= 3 and "layout: default" in fm[1], f"bad front matter: {f}"
print("nav + front matter ok")
EOF
pandoc -f gfm -t html docs/<page>.md > /dev/null   # renders?
```

**Guardrail — the drift check.** In the default style, flag drift-prone
artifacts that crept back in (a warning to fix before landing; skip it when the
repo opted into the detailed style):

```sh
grep -rnE "\bL[0-9]+\b" docs --include="*.md" | grep -v sync-base || true   # L<line> citations
grep -rnE "\b(ms/iter|MiB)\b" docs --include="*.md" || true                # bare measurement units
```

Then bump `docs/.sync-base` to the new `origin/main` HEAD.

### Step 9 — Land and verify live

```sh
# fresh worktree off origin/main (never commit from a dirty checkout)
git -C repos/<repo> worktree add "$PWD/worktrees/<repo>/docs-sync" -b docs/sync origin/main
# edit, then:
git push -u origin docs/sync && gh pr create --title "docs: sync with <summary>"
gh pr merge <n> --merge
# wait for the Pages build, then spot-check the live site:
gh api repos/<owner>/<repo>/pages/builds/latest --jq '{status, commit, error}'
curl -s https://<owner>.github.io/<repo>/README.html | grep -c "expect-content"
```

Merge only when the Pages build reports `built` with no error, and confirm the
expected new content is actually served.

## What a good sync PR contains

- Only `docs/` changes (plus `docs/.sync-base`), zero code.
- A body that lists the source commits synced (`BASE..HEAD`) and what each
  landed change touched in the wiki.
- In the default style: a structural diff only — no renumbered citations, no
  refreshed snapshot tables. When opted in: corrected line refs, counts, and
  inventory — with the command that produced each number cited.

## Scheduled syncs (CI)

The procedure's default posture is **local generation**: an agent runs this
skill directly in a checkout that already holds its model credentials, on
demand after source changes land. The shipped GitHub Actions wrapper makes the
same procedure runnable in CI. Ship `workflows/wiki-sync.yml` from this
skill's directory into the wiki-owning repo as
`.github/workflows/wiki-sync.yml` — copy-to-install, so operator
customizations survive skill updates. The template encodes this contract:

- **Triggers.** The wrapper is dispatch-only (`workflow_dispatch`) — a manual
  convenience, never the primary path. A weekly cron ships as a commented
  scaffold for operators with an always-available model credential; enabling
  it is a deliberate choice, not an expected step. Without such a credential,
  sync locally — it needs no workflow at all.
- **Checkout** uses `fetch-depth: 0` so the anchor diff sees full history.
- **Delta gate first.** Recompute the Step 1 quiet check before anything
  expensive runs; exit cleanly when nothing wiki-relevant changed.
- **Resume state machine.**

  | State                   | Action                                                         |
  | ----------------------- | -------------------------------------------------------------- |
  | Empty delta, no open PR | skip                                                           |
  | Delta, no open PR       | branch `docs/sync-ci` off `origin/main`; agent edits; push; PR |
  | Delta, open PR          | checkout `docs/sync-ci`; rerun agent over its own `$BASE..origin/main`; force-push |
  | Empty delta, open PR    | skip; the existing PR stands until merged                      |

  Reading `.sync-base` from the checked-out branch — not `main` — is what
  makes resume correct: the branch carries its own anchor.
- **Content-level no-op guard.** If the agent changes nothing under `docs/`,
  nothing is committed and no PR opens or updates.
- **Anchor semantics.** The agent bumps `.sync-base` after validation, inside
  the docs-only commit (invariant 6); merging anchors the wiki. Interrupted
  runs leave the remote anchor untouched, so the next run redoes the delta.
  Re-running the repo's doc validators in a workflow step *after* the agent
  and *before* the commit makes this mechanical: failed validation lands
  nothing.
- **Authorship and permissions.** Commits are authored by
  `github-actions[bot]` via `GITHUB_TOKEN` (job permissions:
  `contents: write`, `pull-requests: write`); machine syncs stay visually
  distinct from human `docs/sync` branches in history.
- **Concurrency.** One `concurrency.group` serializes ticks so two runs never
  race on the branch.
- **Agent invocation seam.** One replaceable step drives any coding agent with
  this SKILL.md as the prompt; uncomment exactly one wiring and set its
  credential secret. Documented wirings: OpenCode (`opencode run`), Pi
  (`pi -p`), Claude Code (`claude -p`), Codex (`codex exec`) — pick by
  available credentials or preference; any harness that reads files and runs
  `git`/`gh` in the checkout works. In CI there is no runtime user preference:
  the instantiator chooses once, and the secret decides the provider.
- **Verification rides the PR.** Docs-only PRs trigger the repo's existing
  path-gated checks; merge only when green (Step 9). Install whatever
  toolchain the validators need before the agent step.

## Guiding principles

- **The tree is the oracle for structure; the runner for numbers — only when
  opted in.** `git ls-tree` is the oracle for files, `deno doc --json` for
  public exports (and, when opted in, lines), runner output for counts, bench
  snapshots for measurements. Trust none of them from memory.
- **One anchor, deterministic diffs.** If `docs/.sync-base` is missing or
  stale, fall back to the last commit that touched `docs/`
  (`git log -1 --format=%H -- docs/`), then write a fresh anchor.
- **Default to drift-free; opt in deliberately.** The default style needs no
  sweeps: a 300-line file growth changes nothing in the wiki. Only opted-in
  numbers drift — run the full-tree verification passes (Steps 4–5) over the
  whole tree every few source merges, since incremental passes miss drift that
  accumulates in line citations and snapshot tables.
- **Never block on prompting.** This skill *is* the prompt; run it end to end
  and report what the delta contained.
