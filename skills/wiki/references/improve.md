# Wiki Improve — Audit, Plan, and Loop Closure

Senior wiki **advisor, not implementer**. Run validators, cite evidence, and deliver a prioritized findings report. Generate structured handoff plans for executor models to perform edits.

The founding rule: **the advisor never directly modifies wiki pages or config files** unless explicitly asked by the user. Plans are written to the `plans/` directory (or `advisor-plans/` when `plans/` is occupied) for a separate executor to carry out.

## Hard rules

1. **Never edit wiki files yourself** unless the user explicitly requests immediate inline repairs.
1. **Never guess** — cite the exact `file:line` or CLI output for every finding.
1. **No config migration shims** — unknown config keys must fail fast at load; document upgrades in CHANGELOG and docs only.
1. **Skills are not wiki inputs** — never index, build, or list the `skills/` or `.agents/` folder under `wiki.input`.
1. **No secret values** — if credentials or tokens are discovered, refer to their type and location only. Suggest rotation, never copy the value.

## Workflow

### Phase 1: recon

Understand the specific wiki configuration before auditing:

- Locate the config file (prefer `wiki.yml`; fallback to legacy `wiki.yaml`).
- Read configuration settings: `wiki.input`, `lint:`, `check:`, `link.style`, `wiki.filename_pattern`, `site.layout`.
- Identify resolved commands and environment requirements by running:
  `bash skills/wiki/scripts/verify.sh`
- Note project conventions: filename cases, heading structures, links style, and metadata schemas.

### Phase 2: audit

Run the automated checks and perform spot-checks:

- Execute the audit script:
  `bash skills/wiki/scripts/audit.sh -c path/to/wiki.yml`
- The script runs the standard pipeline: `fmt --check` → `lint --strict` → `check --strict` → `render --check`.
- Map findings against the categories defined in [references/audit.md](audit.md):
  1. `integrity` (broken links, schema failures)
  1. `formatting` / `style` (casing, underlines)
  1. `config` (invalid settings, deprecated keys)
  1. `deploy` (base URL, upload artifacts)
  1. `metadata` (SPARQL, missing RDF types)
  1. `direction` (missing content, stubs)
- Audit depth is controlled by the user's focus (e.g. `quick` vs `deep` settings).

### Phase 3: vet and prioritize

Confirm each finding before presenting:

- Open the cited file and verify the issue. Remove false positives.
- Filter out standard platform conventions or intentionally designed choices.
- Format the findings using the standardized finding format from [references/audit.md](audit.md).
- List rejected findings under the **Considered and rejected** section.
- Present findings ordered by leverage (impact ÷ effort).

### Phase 4: plan generation

Generate self-contained plans for the chosen findings:

- Write independent plan files under `plans/NNN-short-slug.md` following the template in [references/plan.md](plan.md).
- Ensure all context (excerpts, file paths, commands) is fully inlined so the executor requires no external context.
- Create/update `plans/README.md` containing the execution order and status table.

## Invocation variants

- **Bare invocation**: Runs full Recon, Audit, and Vet phases, presenting the findings table.
- **`quick` / `deep`**: Adjusts audit scope (hotspots vs full vault sweep).
- **Focus arguments** (`integrity`, `conventions`, `deploy`): Restricts audit to that category.
- **`branch`**: Audits only files changed in the active branch against the default branch base.
- **`plan <description>`**: Skips the audit; directly researches and writes a single plan for the given task.
- **`execute <plan>`**: Dispatches a cheaper executor subagent in a worktree, reviews its diff, and verifies the done criteria. (See [references/loop.md](loop.md)).
- **`reconcile`**: Rechecks the status of existing plans, verifying DONE, refreshing TODO, and identifying BLOCKED items.
- **`--issues`**: Publishes generated plans as GitHub issues using the `gh` CLI. Warns first if the repository is public.
