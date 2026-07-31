---
type: TechArticle
headline: Getting Started
description: Install the wiki CLI and scaffold a new wiki.
---

# Getting Started

## Install

### From PyPI

```bash
pip install wazootech-wiki
wiki --help
```

### From npm

```bash
npm install -g wazootech-wiki
wiki --help
```

This installs **`wiki`** on PATH. The npm package creates a private Python virtual environment and installs the matching PyPI **`wazootech-wiki`** release. Python 3.12 or newer is required on the machine.

The npm package also exposes a type-safe TypeScript SDK for Node projects. See [Wiki Programmatic API](Wiki_Programmatic_API.md#typescript-sdk) for SDK installation and usage.

Zero-install (no global install):

```bash
npx wazootech-wiki init
npx wazootech-wiki check
```

`npx wazootech-wiki` and `uvx wazootech-wiki` accept the same subcommands and flags as `wiki`.

### Editable install from this repository

```bash
uv pip install -e .
```

## Scaffold a new wiki

From an empty directory:

```bash
wiki init

# GitHub Pages defaults from owner/repo
wiki init --repo wazootech/wiki

# Also initialize a Git repository explicitly
wiki init --git
```

`wiki init` writes `wiki.yml`, `README.md`, and a starter `wiki/` folder (`Person_Shape.md`, `Ethan_Davidson.md`). Use `--repo owner/repo` to infer GitHub Pages URLs without a prompt, or pass `--graph-context-wiki` / `--site-base-url` explicitly. By default it does not create a Git repository; use `--git` if you want that explicitly. Init requires a clean directory (no existing `wiki.yml`, `README.md`, or non-empty `wiki/`). See [wiki init](wiki_init.md) for all flags.

### Branding

Styling and branding (such as site name, theme color, logo, and favicon) are not managed by the CLI out-of-the-box, which outputs plain, unstyled HTML. To add custom styling, write a custom layout template file and place custom assets under the `wiki.assets` directory, then configure `site.layout` in your `wiki.yml`. See [Wiki Configuration — Custom CSS](Wiki_Configuration.md#custom-css) and [wiki init](wiki_init.md).

Alternatively, start from a GitHub template: [wiki-templates/generic](https://github.com/wazootech/wiki-templates/tree/main/generic) (generic wiki project) or the [LLM Wiki](LLM_Wiki.md) starter [wiki-templates/llm-wiki](https://github.com/wazootech/wiki-templates/tree/main/llm-wiki). See [Wiki CLI templates](wiki.md#ecosystem-templates).

## Daily workflow

```bash
# Validate integrity (SHACL, JSON Schema, routes, layout; silent on success)
wiki check

# Validate conventions (filename pattern, headings, link style)
wiki lint

# Refresh embedded SPARQL tables
wiki render

# Reuse a warm graph across repeated one-shot shells
wiki render --cache

# Preview at http://127.0.0.1:8080/wiki/ (default)
wiki serve

# Preferred long-lived preview loop while editing
wiki serve --watch

# Or build static HTML for deployment
wiki build --output-dir _site
```

Use `wiki check -v` / `wiki lint -v` to see warnings. In CI, run both with `--strict` so warnings fail the job.

## Work in this repository’s docs wiki

The published site under `docs/wiki/` is built with:

```bash
wiki -c docs/wiki.yml check --strict -v
wiki -c docs/wiki.yml lint --strict -v
python -m wiki -c docs/wiki.yml serve --watch
wiki -c docs/wiki.yml render --cache
wiki -c docs/wiki.yml build --output-dir _site --site-base-url /wiki
```

See [Deploying to GitHub Pages](Deploying_to_GitHub_Pages.md) for the GitHub Actions workflow.

## Agent skills

Coding agents can use the consolidated **`wiki`** skill documented in [Wiki Skills](Wiki_Skills.md).

After upgrading Wiki CLI or when skills behave unexpectedly, refresh agent skills:

```bash
npx skills add wazootech/wiki@wiki -g -y
```

Do not commit `.agents/skills/` to your wiki repo unless you intentionally vendor a snapshot — stale copies miss fixes like deploy workflow templates.

## Next steps

- [wiki](wiki.md) — command reference home
- [Wiki Configuration](Wiki_Configuration.md) — tune `wiki`, `graph`, `site`, `link`, and check severities
- [Style Guide](Style_Guide.md) — document types, shapes, and wikilinks
- [Linked Markdown](Linked_Markdown.md) — the wazootech/linked-markdown protocol specification
- [wiki check](wiki_check.md) — integrity validation and CI checks
- [wiki lint](wiki_lint.md) — convention audits (broken links, filenames, headings)
- [wiki query](wiki_query.md) — ad-hoc SPARQL from the terminal
- [wiki render](wiki_render.md) — refresh inline SPARQL tables
- [wiki serve](wiki_serve.md) — local preview and optional SPARQL endpoint
- [wiki build](wiki_build.md) — static HTML for deployment
- [Graph Cache](Graph_Cache.md) — graph reuse and `--cache`
