---
name: wiki-sync
description: >-
  Keep a repository's code wiki (docs/) in sync with its source using a Git-anchored delta process.
  Use when asked to sync or refresh documentation after source changes, update wiki line references,
  verify documented test counts, re-run deno doc --json symbol inventories, or maintain a code wiki
  incrementally (e.g. wazootech/sparql-engine's docs/). Never regenerates a wiki from scratch — it
  diffs the commits since the last sync anchor and edits only the affected pages.
---

# `wiki-sync` skill

Keep a code wiki (`docs/`, typically a GitHub Pages Jekyll site) truthful to its
source tree with a **Git-anchored delta process** — the approach popularized by
LangChain's OpenWiki: treat the last-synced commit as an anchor, diff forward
through Git history, and apply only the additions and deletions the diff
demands. Never regenerate the whole wiki; never hand-wave line numbers or test
counts.

This is a *code-wiki* maintenance skill (repo `docs/` folders), distinct from
Wiki CLI's semantic-wiki authoring flows in the `wiki` skill. The wiki it was
built for: `wazootech/sparql-engine`, whose docs live in `docs/` (pages
`00`–`09`).

## When to run

- A source PR landed (or a branch changed) and the wiki must reflect it.
- Asked to "sync the docs", "refresh the wiki", "update the docs for the
  latest changes", or "check the docs are still accurate".
- A documented line reference, symbol, test count, or file path feels stale.

## Core invariants

1. **Delta, not regenerate.** Only pages touched by the diff get edited.
2. **The anchor is the source of truth for "what changed".** `docs/.sync-base`
   holds the commit SHA the wiki was last synced to. Everything after it is the
   delta; everything before it is assumed in sync.
3. **Execute to verify.** Line numbers come from `deno doc --json`, test counts
   come from running the test runners, file lists come from `git ls-tree` —
   never from memory or comments.
4. **Docs-only commits.** The sync PR must never change `src/`, `test/`, or
   `bench/` code.

## Procedure

### Step 1 — Anchor and fetch

```sh
git fetch origin
BASE=$(cat docs/.sync-base)          # last-synced commit
git log --oneline "$BASE"..origin/main          # the delta
git diff --stat "$BASE"..origin/main -- src test bench .github   # what moved
```

- No commits → the wiki is current; stop and say so.
- Docs-only commits → re-check the few touched pages, update `.sync-base`, done.
- Source/test/bench commits → continue.

### Step 2 — Classify the delta

| Change in                | Wiki surface to touch                                              |
| ------------------------ | ------------------------------------------------------------------ |
| `src/**/*.ts`            | `04-source-map.md` (symbol lines) + any page citing that file      |
| `deno.json` tasks        | `01-quickstart.md` task lists                                      |
| `test/**` (new/renamed)  | `04-source-map.md` test tables, `05-testing.md` covered areas      |
| `bench/**`               | `04-source-map.md` bench table, `07-benchmarking.md`               |
| new/removed files        | `04-source-map.md` file inventory                                  |
| behavior/fixes           | `02-architecture.md`, `03-api-contracts.md` prose                  |
| `.github/workflows/*`    | `05-testing.md` task-table "gating" column                          |

### Step 3 — Rebuild the symbol graph

Line references in the wiki are generated from `deno doc --json`. For each
changed file (and as a full sweep, every file), extract the **declaration**
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
Do a full-tree pass when in doubt (loop over `git ls-tree -r --name-only
origin/main -- src`), not just the changed files.

### Step 4 — Verify counts by running

Documented counts must match runner output, not comments or README prose
(comment counts have drifted before — e.g. the W3C suite was documented as
336/23 while the runner loads 345/31).

```sh
deno task test:w3c          # read the printed total/pass lines
deno task test:sparql12     # 249
deno task test:sparql12:gap # 41
deno test --allow-all src/  # unit count
```

Record the runner's printed totals verbatim in the docs. If the runner prints
something different from the docs, the docs are wrong.

### Step 5 — Verify file inventory

```sh
git ls-tree -r --name-only origin/main -- src test bench .github
```

Compare against the `04-source-map.md` tables. Add missing files (source,
test, bench, workflow), delete rows for removed files, and check every
referenced path in the wiki resolves on disk.

### Step 6 — Edit with the delta

- Edit only the pages in Step 2's mapping.
- **Additions**: new rows/tables/sections, byte-faithful snippets.
- **Deletions**: remove rows for files/symbols that no longer exist; never keep
  a "known gap" entry for something that was fixed.
- Keep prose edits minimal; cite exact paths and `L<line>` references.

### Step 7 — Validate

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

Then bump `docs/.sync-base` to the new `origin/main` HEAD.

### Step 8 — Land and verify live

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
- Corrected line refs, counts, and inventory — with the command that produced
  each number cited.

## Guiding principles

- **The runner is the oracle for counts; `deno doc --json` is the oracle for
  lines; `git ls-tree` is the oracle for files.** Trust none of them from
  memory.
- **One anchor, deterministic diffs.** If `docs/.sync-base` is missing or
  stale, fall back to the last commit that touched `docs/`
  (`git log -1 --format=%H -- docs/`), then write a fresh anchor.
- **Sweep periodically.** Every few source merges, run Steps 3–5 over the whole
  tree — incremental passes miss drift that accumulates (a 300-line file
  growth silently invalidates every line citation in it).
- **Never block on prompting.** This skill *is* the prompt; run it end to end
  and report what the delta contained.
