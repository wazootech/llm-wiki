# Initialize wiki

Scaffold a new [Wiki CLI](https://github.com/wazootech/wiki) project: `wiki init` (Phase A) plus a tweak step (Phase B). Requires **`wiki` on PATH** (PyPI package `wazootech-wiki`).

This workflow **only** scaffolds or customizes a wiki project. When done, summarize and **stop**. If the CLI is missing, state the blocker and stop — read [install.md](install.md) only when the user wants install help.

## Resolve wiki command

Run `bash skills/wiki/scripts/verify.sh` first.

Prefer `wiki` on PATH when exit code is `0`. In the **Wiki CLI repository checkout**, if PATH `wiki` is missing or stale, try `uv run wiki` or `python -m wiki`. If neither works, stop and recommend upgrading **`wazootech-wiki`** (one-liner only).

## Prerequisite gate

Before init or file edits:

```bash
wiki --help
wiki fmt --help
```

If either fails:

1. Say that **creating a wiki requires `wiki` on PATH** (install Wiki CLI — package **`wazootech-wiki`**).
1. If `--help` passes but `fmt` fails, note stale or shadowed `wiki` — upgrade/reinstall before init.
1. **Do not** run `wiki init`, write scaffold files, or paste a step-by-step pip guide.
1. **Stop.**

## Workflow (CLI present)

Prefer **flags** over interactive `wiki init` prompts (stdin blocks agents). Batch optional config preferences when defaults are fine; branding belongs in Phase B.

### Infer before asking

When context already supplies values, **do not re-prompt**:

- **`--repo owner/repo`** — from a GitHub repo attachment, `gh repo view --json nameWithOwner`, or `git remote get-url origin`
- **Link style** — default to standard page links (omit `--link-style`) unless the user asks for wikilinks
- **Logo, theme, sidebar title** — Phase B tweak comments (not init flags)
- **Inputs dir, URL style** — skip unless the user wants customization at init

### Choose mode

- **`wiki.yml` and `wiki.yaml` absent** → Phase A (init) then Phase B (tweak).
- **Either config file present** → **Wizard-only** (Phase B). Do not re-init; init requires a clean directory.

### Phase A: init

1. **Directory** — Confirm the wiki project root. `wiki init` writes to the **current directory**.
1. **Init options** — Run `wiki init --help` and map answers to **config flags** only. Prefer flags over bare `wiki init`.

| Topic                  | When to ask                                  | Flag                                                             |
| ---------------------- | -------------------------------------------- | ---------------------------------------------------------------- |
| GitHub Pages           | User publishes to `{owner}.github.io/{repo}` | `--repo owner/repo`                                              |
| Custom namespace       | No GitHub / custom site                      | `--graph-context-wiki https://…/` and optional `--site-base-url` |
| Git repository         | User wants `git init` now                    | `--git`                                                          |
| Link style             | Wikilinks vs standard page links             | `--link-style wikilink`                                          |
| Inputs directory       | Custom markdown folder                       | `--input myfolder`                                         |
| URL style              | File vs directory routes                     | `--site-url-style dir` or `file`                                 |
| Content predicate      | Body text RDF predicate                      | `--graph-content-predicate schema:articleBody`                   |
| Document IRIs          | IRIs differ from `wiki:` namespace           | `--graph-base-iri https://…/`                                    |
| Implicit types         | Wiki-wide default `rdf:type` CURIEs          | `--graph-implicit-types schema:TechArticle` (repeatable)         |
| Implicit types policy  | Merge vs fallback                            | `--graph-implicit-types-policy append` or `fallback`             |
| File extension in IRIs | Include `.md` in document URIs               | `--graph-include-file-extension`                                 |

If no preference for namespace and no `--repo`, pass `--graph-context-wiki https://wiki.example.org/`.

3. **Preflight** — Init fails if `wiki.yml`, `wiki.yaml`, `README.md`, or non-empty `wiki/` exist. Use a new directory or remove those files first.
1. **Run** — Example: `wiki init --repo owner/repo --git`

### Post-init smoke (new scaffold only)

After Phase A succeeds, **default:** run `wiki check --strict` with the resolved wiki command.

- **Opt-out:** skip when the user explicitly declines (e.g. “skip check”, “just init”).
- **On failure:** report CLI output; do not auto-fix.
- **Wizard-only mode:** do not run this step.

### Phase B: tweak

Review the scaffolded files with the user (config, README, empty `wiki/`):

| Topic           | Action                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------ |
| First page      | Add the user's first page under `wiki/` (scaffolded empty) |
| Config extras   | Uncomment optional blocks in `wiki.yml` — see the Preferences wizard section below         |
| Lint strictness | Only if user asks — see the Preferences wizard section below                               |

**Only edit files with explicit user approval.** After markdown or config edits, run `wiki fmt` on changed paths.

### What init creates

- `wiki.yml`
- `wiki/` (empty), `README.md`

## Post-init hygiene

With user approval, recommend adding `_site/` to `.gitignore`. Do not commit `.agents/skills/` unless the user explicitly wants vendored skills.

## Clean exit

Summarize: project path, init flags used, post-init `check --strict` result (if run), tweak edits (if any). For GitHub Pages CI, read [deploy.md](deploy.md) when the user is ready — not part of scaffolding.

**Do not** run `wiki lint` or `wiki serve` unsolicited. **`wiki check --strict` after new init is the one default exception** (unless the user opts out).

## Troubleshooting

| Issue                                        | Response                                          |
| -------------------------------------------- | ------------------------------------------------- |
| `wiki.yml` or `wiki.yaml` already exists     | Wizard-only (Phase B) or use a new directory      |
| `README.md` or non-empty `wiki/` blocks init | New directory or remove conflicting files         |
| Invalid `--repo`                             | Fix `owner/repo` or use `--graph-context-wiki`    |
| `--git` fails                                | Report error; init may have completed without git |
| `interactive`                                | Interactive prompt during init                    |

## Preferences wizard: wiki config tweaks

Use after `wiki init` when the user approves file edits. Fresh scaffolds write **`wiki.yml`**; legacy **`wiki.yaml`** still loads. Run `wiki fmt` on changed markdown paths.

### Init scaffold defaults

Fresh `wiki init` writes:

| Block   | Init content                                                                                        |
| ------- | --------------------------------------------------------------------------------------------------- |
| `site:` | `layout`, `base_url`, `url_style` only                                                              |
| `lint:` | `broken_links`, `filename_pattern`, `link_style` at `warning`                                       |
| `fmt:`  | Inline mapping in `wiki.yml` (wrap, end_of_line, extensions) — init does not write `.mdformat.toml` |

Other `lint.*` keys (e.g. `headings`, `heading_levels`) are valid but init omits them (defaults are `off`).

### Removed / invalid keys (config load fails)

Do not add these to new scaffolds; remove them when upgrading — invalid in the current schema:

- `site.manifest`, `site.title`, `site.theme_color`
- Jinja `{{ site.manifest.* }}` or `{{ site.* }}` in layouts — use `%wiki.*%` tokens and `%wiki.base_url%/assets/…` in custom page layouts
- `<link rel="manifest">` and built `manifest.webmanifest` — removed from build/serve

Upgrade steps: CHANGELOG Migration section and [Wiki Configuration](https://github.com/wazootech/wiki/blob/main/docs/wiki/Wiki_Configuration.md). No runtime rename hints or `wiki config migrate` shims.

### Site branding

Branding and styling are **not** managed by the CLI out-of-the-box, which outputs plain, unstyled HTML. To customize branding (such as site name, theme color, favicon, and sidebar chrome), write a custom layout template file and place custom assets under the `wiki.assets` directory, then set `site.layout` to point to your layout file path.

### Lint strictness (only if asked)

| Key                     | Values                    | Effect                                                              |
| ----------------------- | ------------------------- | ------------------------------------------------------------------- |
| `lint.headings`         | `off`, `warning`, `error` | Sentence-case H2+ and numbered headings (init omits; default `off`) |
| `lint.filename_pattern` | severity                  | Wikipedia-style filenames                                           |
| `lint.broken_links`     | severity                  | Unresolved internal links                                           |
| `lint.link_style`       | severity                  | Obsidian wikilinks in body when `link.style: standard`              |

Severity is `off`, `warning`, or `error`. Unknown top-level keys fail at config load.

### Config lanes (do not confuse)

| Block    | Command      | Purpose                             |
| -------- | ------------ | ----------------------------------- |
| `fmt:`   | `wiki fmt`   | Mechanical markdown                 |
| `lint:`  | `wiki lint`  | Conventions                         |
| `check:` | `wiki check` | SHACL, JSON Schema, routes, layouts |

Regex belongs in `wiki.filename_pattern`, not under `check:`.
