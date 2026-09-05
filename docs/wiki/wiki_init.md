---
type: TechArticle
headline: wiki init
description: Scaffold wiki.yml and an empty wiki/ folder for markdown pages.
---

# `wiki init`

Create a new wiki project in the **current directory**: `wiki.yml`, `README.md`, and an empty `wiki/` folder for your markdown pages.

Does not use loaded Config; safe to run before a config exists. Init runs once per clean directory — if `wiki.yml`, `README.md`, or a non-empty `wiki/` already exist, use a new directory or remove those files before re-running.

## Usage

```bash
wiki init
wiki init --git
wiki init --repo wazootech/wiki
wiki init --graph-context-wiki https://example.org/mywiki/ --site-base-url /mywiki
```

## Config vs scaffold

**Config flags** write keys into `wiki.yml` via the packaged template ([`wiki.yml`](https://github.com/wazootech/wiki/blob/main/src/wiki/templates/wiki.yml)).

**Scaffold-only** effects copy files (`README.md`, `wiki/*.md`) or run `git init`.

## Options

| Flag                             | Description                                                                                    | `wiki.yml` key                                   |
| -------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `--git`                          | Run `git init` after scaffolding                                                               | —                                                |
| `--repo`                         | GitHub `owner/repo`; infer `graph.context.wiki` and `site.base_url` for GitHub Pages           | `graph.context.wiki`, `site.base_url` (inferred) |
| `--graph-context-wiki`           | Override `graph.context.wiki` (overrides `--repo` inference)                                   | `graph.context.wiki`                             |
| `--site-base-url`                | Override `site.base_url` (default `/wiki` or inferred from `--repo`)                           | `site.base_url`                                  |
| `--site-url-style`               | Override `site.url_style`: `dir` or `file` (default `dir`)                                     | `site.url_style`                                 |
| `--site-layout`                  | Override `site.layout` (default depends on the selected scaffold or template)                  | `site.layout`                                    |
| `--graph-content-predicate`      | Override `graph.content_predicate` CURIE (e.g. `schema:articleBody`)                           | `graph.content_predicate`                        |
| `--link-style`                   | Override `link.style`: standard page links (`standard`) or wikilinks (`wikilink`)              | `link.style`                                     |
| `--input`                        | Override `wiki.input` list (can be specified multiple times, default `[wiki]`)                 | `wiki.input`                                     |
| `--graph-base-iri`               | Override `graph.base_iri` URI                                                                  | `graph.base_iri`                                 |
| `--graph-implicit-types`         | Override `graph.implicit_types` (can be specified multiple times)                              | `graph.implicit_types`                           |
| `--graph-implicit-types-policy`  | Override `graph.implicit_types_policy`: `fallback` or `append`                                 | `graph.implicit_types_policy`                    |
| `--graph-include-file-extension` | Override `graph.include_file_extension` flag (defaults to `--no-graph-include-file-extension`) | `graph.include_file_extension`                   |
| `--template`                     | Use a starter template from wazootech/wiki-templates (e.g. generic, llm-wiki, astro)           | —                                                |

## URL resolution

When `--graph-context-wiki` is not passed, init resolves `graph.context.wiki` in this order:

1. **`--repo`** — GitHub Pages project site: `https://{owner}.github.io/{repo}/` and `site.base_url: /{repo}` (accepts `owner/repo`, HTTPS, or SSH URLs).
1. **Git remote** — If `.git` already exists or `--git` was passed, parse `git remote get-url origin` when it points at GitHub.
1. **Interactive prompt** — **Custom wiki namespace IRI** (default `https://wiki.example.org/`). The prompt is skipped when stdin is not an interactive terminal (CI, scripts, agent tools); the default is used instead.

`--graph-context-wiki` always wins over `--repo` and remote detection. `--site-base-url` overrides the inferred path from `--repo`.

Document subject IRIs default to `graph.context.wiki`. Set optional `graph.base_iri` in `wiki.yml` when auto-generated document IRIs must differ from the `wiki:` namespace (see [Wiki Configuration](Wiki_Configuration.md)).

## Prompts

When no flag or git remote supplies `graph.context.wiki`, init prompts once:

1. **Custom wiki namespace IRI** (default `https://wiki.example.org/`) → `wiki:` in `graph.context`

When the namespace came from that prompt, the prompt ends and initialization proceeds.

The prompt only appears when stdin is an interactive terminal. In non-interactive contexts (CI, scripts, agent tools), init detects the lack of a TTY and uses the default `https://wiki.example.org/`, printing a note to stderr — pass `--repo` or `--graph-context-wiki` to control the namespace without prompting.

Always includes `schema`, `wiki`, `wazoo`, `foaf`, `dc`, `dcterms`, `sh`, and `xsd` prefixes. The `wazoo` URI is fixed in the scaffold (`https://schema.wazoo.dev/`), like the other built-in prefixes.

## Generated config

New wiki projects receive a plain `wiki.yml` rendered from [`wiki.yml`](https://github.com/wazootech/wiki/blob/main/src/wiki/templates/wiki.yml). Jinja variables (such as `graph_context_wiki`, `site_base_url`, `graph_content_predicate`, and `link_style`) map from init CLI flags into nested blocks.

For every key — schema default, whether init writes it, and which command audits it — see [Wiki Configuration → Overview](Wiki_Configuration.md#overview) and the per-block defaults tables in [Wiki Configuration](Wiki_Configuration.md).

## Generated files

- `README.md` — starter wiki overview and common commands
- `wiki/` — empty directory for your markdown pages with semantic frontmatter

## Related

- [Getting Started](Getting_Started.md)
- [Wiki Configuration](Wiki_Configuration.md)
- [Wiki Page Layouts](Wiki_Page_Layouts.md)
