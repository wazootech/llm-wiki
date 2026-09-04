# Install Wiki CLI

Install and verify the [Wiki CLI](https://github.com/wazootech/wiki) (`wiki` command, PyPI package **`wazootech-wiki`**).

This workflow **only** installs and verifies the CLI. When done, say the CLI is ready and **stop**. Do not suggest `wiki init`, creating a wiki project, or other workflows unless the user asks.

Run `bash skills/wiki/scripts/verify.sh` first (`.agents/skills/wiki/scripts/verify.sh` when vendored).

## Detect

```bash
wiki --help
wiki fmt --help
```

If that fails, go to **Install when CLI is missing** or **Stale CLI** below.

- **Both pass** → confirm briefly, then **`wiki` is on PATH and ready to go.** Exit.
- **`--help` passes but `fmt` fails** → stale or wrong `wiki` on PATH; go to **Stale CLI** (do not say ready-to-go).

## Install when CLI is missing

Tell the user the CLI was not found. Offer install paths in this order unless the user prefers otherwise:

**PyPI (requires Python 3.12+):**

```bash
pip install wazootech-wiki
wiki --help
wiki fmt --help
```

**npm (requires Node 18+ and Python 3.12+ on the machine):**

```bash
npm install -g wazootech-wiki
wiki --help
wiki fmt --help
```

Global npm install puts **`wiki`** on PATH. The npm package bootstraps a private Python venv with the matching PyPI release.

**Zero-install (no global install):**

```bash
npx wazootech-wiki --help
npx wazootech-wiki fmt --help
```

Treat **`npx wazootech-wiki <args>`** (or **`uvx --from wazootech-wiki wiki <args>`**) as **`wiki <args>`** for all subcommands and flags.

**Standalone binary (no Python):** download the archive for their OS from [GitHub Releases](https://github.com/wazootech/wiki/releases), verify `SHA256SUMS`, extract, and run `./wiki --help` (or `wiki.exe` on Windows).

You may offer to run `pip install wazootech-wiki` or `npm install -g wazootech-wiki` **only if the user explicitly approves**.

If `wiki upgrade --yes` reports a standalone-binary message (`pip upgrade is not available`), point them to GitHub Releases instead of pip.

**Contributors in the Wiki CLI repository** may instead use:

```bash
uv pip install -e .
uv run wiki --help
```

Use `uv run wiki` only when the current working directory is this checkout and the user is developing the CLI — not as the default for end users.

## Verify

After install (user-run or agent-run with approval), run `wiki --help` and `wiki fmt --help` again, or re-run `verify.sh`.

- **Both pass** → **`wiki` is on PATH and ready to go.** Exit.
- **Failure** → Report the error output. Exit.

## Stale CLI (`--help` works, `fmt` missing)

Treat as an outdated or shadowed install — not ready:

1. Recommend `pip install --upgrade wazootech-wiki` or `python3 -m pip install --upgrade wazootech-wiki` (with user approval).
1. When the package is installed: `wiki upgrade --check` then `wiki upgrade --yes` (unless standalone binary — use GitHub Releases).
1. On Windows, multiple `wiki.exe` on PATH can shadow the upgraded install — run `where wiki` (or `which wiki`) and align PATH with the Python environment that owns `wazootech-wiki`.
1. Re-run capability probe before saying ready-to-go.

## Install troubleshooting

| Issue                                 | Response                                                                                                    |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `wiki --help` works but `fmt` missing | Stale or wrong `wiki` on PATH — upgrade/reinstall per **Stale CLI**                                         |
| npm venv broken or incomplete         | `npm rebuild -g wazootech-wiki` (or reinstall the npm package)                                              |
| `pip install` fails                   | Confirm Python 3.12+; retry `python3 -m pip install wazootech-wiki`; optional `pipx install wazootech-wiki` |
| IDE pip tool fails on macOS           | Prefer **`python3 -m pip install wazootech-wiki` in the user's shell**                                      |

## Do not

- Suggest `wiki init` or scaffolding as a required next step.
- Auto-run `pip install` without user approval.
- Say **ready to go** when the capability probe fails.
- Duplicate full wiki or configuration documentation.

## Programmatic API (Python)

Use the CLI for agent workflows (`audit.sh`, `verify-cli.sh`). Use the library when CI or tests need in-process calls without subprocess overhead.

```python
from pathlib import Path
from wiki import Wiki

w = Wiki.load("wiki.yml")
if not w.preflight().ok:
    raise SystemExit("preflight failed")

result = w.build(output_dir=Path("_site"))
```

Stable exports: `Wiki`, `AuditReport`, `Issue`, and related report and options types — see `wiki.__all__`.

Full reference: [Wiki Programmatic API](https://github.com/wazootech/wiki/blob/main/docs/wiki/Wiki_Programmatic_API.md).
