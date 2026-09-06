---
type: schema:SoftwareApplication
name: Vivary
softwareVersion: 0.4.2
description: An agent-native workspace standard and scaffolder — a thin .vivary/ governed-context contract, typed Markdown records, verification receipts, and deliberate human gates.
codeRepository: https://github.com/vivary-dev/vivary
---

# Vivary

[Vivary](https://vivary.vercel.app/) is a **standard plus scaffolder for agent-native workspaces**: `create-vivary` seeds a thin governed `.vivary/` contract that agents read first, a typed knowledge graph of Markdown records, verification receipts, and deliberate human gates — plain Markdown and TOML, any editor, any agent runtime, no lock-in.

Source and docs: [github.com/vivary-dev/vivary](https://github.com/vivary-dev/vivary). PyPI packages use the `vivary-*` prefix (for example `create-vivary`, `vivary-tropo`); npm scaffolds use `@vivary/*`.

```bash
npm create @vivary my-workspace
# or: npx @vivary/create my-workspace
pip install create-vivary vivary-tropo
create-vivary init my-workspace --preset coding
create-vivary doctor my-workspace
```

MIT · Python 3.11+ · zero third-party dependencies on the core engines · on [PyPI](https://pypi.org/project/create-vivary/) and npm.

## The problem Vivary solves

Every AI-agent project starts the same way: a pile of spec files, a `notes.md`, some rules, a memory dump. Then it rots. Vivary makes the workspace a **known, structured, navigable thing** — the way [create-t3-app](https://create.t3.gg/) did for web stacks.

The design law: the framework must cost almost nothing to load, or it steals the context the work needs.

## The thin workspace contract (v0.3)

Current Vivary workspaces (0.4.x) run a deliberately **thin** contract. A default greenfield `init` writes exactly five files — `AGENTS.md`, `STATE.md`, `.gitignore`, and two under `.vivary/`:

| File                     | Purpose                                                 |
| ------------------------ | ------------------------------------------------------- |
| `.vivary/context.md`     | The first typed project node / governed-context capsule |
| `.vivary/workspace.toml` | The thin workspace contract and policy                  |

Everything else under `.vivary/` appears only as work earns it:

- `.vivary/records/` — typed Markdown records, created one at a time via `create-vivary record` (for example `.vivary/records/changes/verified-slice.md`), never seeded or bulk-loaded
- `.vivary/private/` — private material, gitignored and excluded from the graph
- `.vivary/runtime/` — runtime artifacts, gitignored and excluded from the graph
- `.vivary/receipts.jsonl` — optional local JSONL run-receipt log (`--receipt` or `VIVARY_RECEIPT_LOG`)
- `.vivary/storage.toml` — optional opt-in storage/vector config (embedded local-hash vectors, cloud backends)

Brownfield `create-vivary adopt` is capped at three Vivary payload files (`.vivary/context.md`, `.vivary/workspace.toml`, and `STATE.md` when absent) plus bounded `AGENTS.md` / `.gitignore` blocks; conflicts fail closed. Older pre-0.4 "legacy-full" workspaces stay read-compatible — Doctor keeps them readable without migrating them.

## tropo — the typed knowledge graph

**tropo** is the typed knowledge graph layer. **Location is type**: a document's type is the folder it lives in, declared by `[types.*]` blocks in `.vivary/workspace.toml` (folder, `required` / `optional` fields, `enum:` values). `id` and `title` are derived, so a record can be fully typed with minimal or no frontmatter; `ref` / `ref-list` fields become graph edges.

```toml
version = 1
exclude = [".git", ".agents", ".vivary/private", ".vivary/runtime"]

[workspace]
contract = "thin-v0.3"
preset = "coding"
state = "STATE.md"
private = [".vivary/private"]
runtime = [".vivary/runtime"]
capabilities = []

[base]
derive = ["id", "title"]
allow_untyped = true

[types.change]
folder = "changes"
required = { project = "string", status = "enum:planned|active|done|blocked|deferred", slice = "string" }
optional = { branch = "string", related_modules = "ref-list", related_changes = "ref-list" }
```

Key commands:

| Command                     | Purpose                                                                                                                       |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `tropo check`               | Validate every document and the graph — warnings fail by default                                                              |
| `tropo find --governed`     | Bounded graph-backed context for a question                                                                                   |
| `tropo query --mode vector` | Vector search, preferring stored embeddings when `.vivary/storage.toml` enables them (`source: stored` / `computed` / `text`) |

## Governance — capsules, receipts, and policy

- **Task Capsules** (`vivary.task-capsule/v0`) — fingerprinted governed-context artifacts compiled for one question and declared scope; they carry the context and effective checks but never execute them.
- **Execution Receipts** (`vivary.execution-receipt/v0`) — records of what actually ran, bound to one capsule and workspace fingerprint; provenance is never treated as proof of correctness.
- **Local run receipts** — optional JSONL at `.vivary/receipts.jsonl` (`--receipt` / `VIVARY_RECEIPT_LOG`), one `vivary.run_receipt.v1` envelope per line: schema version, tool/version, command, flag names, argument count, exit code, duration, Python version, platform. Not telemetry — no stdout, stderr, file contents, or paths, and nothing is sent anywhere.
- **Policy** — `.vivary/workspace.toml` is the thin base policy; a root or nested `tropo.toml` may tighten but never expand it, and competing thin roots fail closed.

## Agent integration

- Generated `AGENTS.md` instructs agents to **read `.vivary/context.md` first**; it routes bounded project context, verification receipts, privacy, current state, and deliberate human gates.
- One orchestrator or human owns `STATE.md`; workers return receipts instead of editing it concurrently.
- The CLI is the baseline agent API — every command works non-interactively with structured output; MCP stays off until installed and enabled.
- Optional MCP: `vivary-mcp --workspace project .` exposes four tools that read and query only, and never authorize a write.
- `--active-context cocoindex-code` declares a CocoIndex code-index capability — it changes only policy (`capabilities` + excludes in `workspace.toml`, a gitignore rule for `.cocoindex_code/`) and copies no skill, guide, graph node, or template.

## Design principles

- **Signal over noise.** If a value can be derived (`id`, `title`), never make a human write it.
- **Location is type.** The directory tree is the type hierarchy, declared in `workspace.toml`.
- **Tighten, never loosen.** Overlays and `tropo.toml` add constraints only.
- **Minimalism law.** The baseline stays zero-dependency; storage and MCP are opt-in.
- **Fail closed.** Missing or negated privacy rules, unknown config, and competing thin roots refuse to run.
- **No lock-in.** Plain Markdown + TOML; any editor, any agent runtime.

## Vivary vs [wiki](wiki.md)

| Dimension          | Vivary (tropo)                                                     | [wiki](wiki.md)                          |
| ------------------ | ------------------------------------------------------------------ | ---------------------------------------- |
| Primary goal       | Standardized **agent workspace**                                   | Semantic wiki **toolchain**              |
| Workspace contract | Thin `.vivary/` — `context.md` + `workspace.toml` (v0.3)           | `wiki.yaml` config                       |
| Schema model       | Folder-as-type + `[types.*]` in `workspace.toml`                   | SHACL, JSON Schema, `wiki.yaml`          |
| Metadata style     | Derive `id`, `title`; minimal frontmatter                          | YAML-LD frontmatter + shapes             |
| Graph              | Typed nodes/edges from `ref` fields                                | Full RDF compile + [SPARQL](SPARQL.md)   |
| Records            | `.vivary/records/` — one typed Markdown per `create-vivary record` | Documents with frontmatter + shapes      |
| Validation         | `tropo check` + Doctor (strict gate)                               | `wiki check`, `wiki lint`                |
| Governance         | Task Capsules, Execution Receipts, local run receipts              | Link graph, SHACL                        |
| Privacy            | `.vivary/private/`, `.vivary/runtime/` gitignored + graph-excluded | Config excludes only                     |
| Agent loop         | `AGENTS.md` → `.vivary/context.md`, receipts, human gates          | [Wiki Skills](Wiki_Skills.md) (optional) |
| Publishing         | Not the focus (workspace OS)                                       | `wiki build`, static HTML, RDF export    |
| MCP                | Optional read-only `vivary-mcp` (4 tools)                          | Optional read-only `wiki mcp` (SPARQL)   |
| Dependencies       | Zero on core engines; storage/MCP opt-in                           | PyPI `wazootech-wiki`                    |

**Wiki CLI** targets wikis that become queryable, publishable [semantic web](Semantic_Web.md) artifacts; Vivary targets the **agent-native workspace** pattern in the [LLM Wiki](LLM_Wiki.md) era — thin governed contract + typed graph + verification receipts + human gates — without RDF compilation.

The stacks can complement each other: Vivary for day-to-day agent workspace hygiene; Wiki CLI when the same Markdown should become a validated public wiki with SPARQL and static site output.

## Lineage

Vivary composes ideas from [Jeff Kazzee](Jeff_Kazzee.md)'s earlier tools — **braincheck → loam → tropo**, the knowledge-layer validation lineage that settled on folder-as-type, and **throughline + flywheel**, per-turn and heartbeat loops that shaped the agent-facing workspace contract. Current development lives at [vivary-dev/vivary](https://github.com/vivary-dev/vivary).

## Related

- [Jeff Kazzee](Jeff_Kazzee.md) — author and tool lineage
- [wiki](wiki.md) — semantic compiler for Markdown wikis
- [LLM Wiki](LLM_Wiki.md) — compounding agent-maintained knowledge pattern
- [Agent Memory Filesystems](Agent_Memory_Filesystems.md) — filesystem-metaphor memory tools compared
- [Obsidian](Obsidian.md) — optional authoring surface
- [Personal Knowledge](Personal_Knowledge.md) — domain context for knowledge-base workspaces
