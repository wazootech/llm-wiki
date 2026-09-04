# Wiki Audit Guide

What to check for when auditing a Wiki CLI project or vault repository. Use this checklist during the audit phase to identify violations, risks, and improvements.

A finding is only a finding with evidence. Do not guess; cite the exact file path, line number, or CLI tool output.

## Correctness and integrity

Critical structural problems that break the build or layout of the wiki:

- **Broken links**: Markdown internal links `[text](Missing_Page.md)` pointing to non-existent files, broken heading anchors `[text](Page.md#invalid-anchor)`, or `wiki:` CURIEs referencing undefined types/shapes.
- **Wikilinks style violations**: Obsidian-style `[[WikiLink]]` links present when `link.style` is set to `standard` in `wiki.yml`.
- **Layout parsing errors**: Missing template layout files mapped in `site.layout`, or invalid Liquid/Jinja tags inside HTML layouts.
- **Schema & SHACL failures**: JSON Schema validation errors in page frontmatter, or SHACL constraints failing on custom RDF metadata.
- **Route collisions & safety**: Duplicate titles mapping to the same output slug, or unsafe characters in filenames (like spaces, hashes, or question marks) that lead to invalid URLs.

## Style and formatting

Clean conventions and visual presentation of the wiki source files:

- **Filename conventions**: Filenames not matching the Wikipedia-style pattern (e.g. `Opal_Security.md` preserving capitalization and underscores), or `index.md` used for non-folder index routes.
- **Heading styles**: Use of Setext underlines (e.g., `===` or `---` under titles) instead of standard ATX `#` headings. Use of sentence-case headings for H2+ (only capitalize first word and proper nouns). Numbered headings (e.g., `## 1. Introduction`).
- **Thematic breaks**: Forbidden horizontal rules (`---`) in standard body text.
- **Format drift**: Trailing blank lines, inconsistent table indentation, or list spacing that has drifted from the format enforced by `wiki fmt` (Enforced by mdformat via `wiki fmt`).
- **Prose structure**: Standard pages missing a `## References` section at the end if citations are present.

## Configuration hygiene

Valid settings and keys in the `wiki.yml` or legacy `wiki.yaml` file:

- **Invalid keys**: Unknown top-level configuration keys that cause `wiki check` to fail.
- **Deprecated branding properties**: Presence of old `site.manifest`, `site.title`, or `site.theme_color` keys that are no longer part of the schema.
- **Inputs folder exclusions**: The `wiki.input` configuration listing directories like `skills/`, `.agents/`, `.git/`, or test folders, which imports agent instructions as content pages.
- **Base URL issues**: `site.base_url` undefined or lacking a leading slash (should be `""` or `/path`).

## Deploy and CI/CD alignment

Build and hosting verification for GitHub Pages:

- **Base URL mismatch**: `site.base_url` in `wiki.yml` does not match the `--site-base-url` argument in the CI `wiki build` step.
- **Artifact path mismatches**: The GitHub Action's `upload-pages-artifact` `path` is set to `_site` instead of `_site/subpath` when a non-empty `site.base_url` is used.
- **Legacy branch deploys**: Repos configured to build/push to a `gh-pages` branch instead of utilizing modern GitHub Actions direct uploads.
- **Build ignore rules**: Missing `_site/` or build directory in `.gitignore`, causing built HTML to be accidentally committed to the source branch.
- **CI runner mismatches**: Using `uv sync` in workflow without a `pyproject.toml` or `uv.lock` in the repository (should use the `pip install` template instead).

## Semantic metadata and SPARQL

Hygiene of structured RDF metadata and database queries:

- **Missing type predicates**: Pages defined with a specific semantic type in frontmatter but lacking type-specific predicates (e.g., `givenName` or `familyName` for `Person` pages; `headline` or `description` for `TechArticle`).
- **Stale inline SPARQL blocks**: Inline query result blocks that are out of sync with the underlying schema or data (meaning `wiki render --check` fails).
- **Namespace mismatches**: Custom frontmatter properties using undefined prefix mappings.

## Product direction and features

Roadmap suggestions grounded in the specific repository:

- **Unfinished content**: Stubs, placeholder pages, or pages with extensive `TODO` notes.
- **Missing documentation**: Important features, setup guidelines, or repository APIs that have zero corresponding wiki pages.
- **Navigation enhancements**: Suggestions for improving sidebar linkages, categories, or index maps.

## Style spot-check conventions

Use these guidelines when `lint.*` rules are `off` but conventions still matter (canonical details are defined in the docs wiki style guide):

| Area            | Convention                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------- |
| **Filenames**   | Wikipedia-style (`Page_Name.md`); `index.md` only for folder routes                         |
| **Headings**    | Title-case H1; sentence-case H2+; no numbered headings; ATX `#` only                        |
| **Links**       | Markdown `[text](Page.md)` when `link.style: standard`; Obsidian `[[Page]]` when `wikilink` |
| **Frontmatter** | `type` / shapes aligned; CURIEs use `graph.context`                                         |
| **SPARQL**      | People → `givenName`/`familyName`; TechArticle → `headline`/`description`                   |
| **Prose**       | No `---` thematic breaks in body; `## References` on standard pages                         |

## Finding format

Every audit finding must be reported in the following format:

```markdown
### [CATEGORY-NN] Short imperative title

- **Evidence**: `path/file.md:123` — one-sentence description of the issue. (Repeat per location; list up to 5 strongest locations, note "and ~N similar sites" if widespread).
- **Impact**: What goes wrong or what is broken because of this. Make it concrete: "breaks layout formatting in rendered HTML", "fails build in strict CI mode", etc.
- **Effort**: S (hours) / M (a day-ish) / L (multi-day) — estimate for the fix, including running formatters and tests.
- **Risk**: What the fix could break; LOW/MED/HIGH plus one line why.
- **Confidence**: HIGH (read the code, certain) / MED (strong signal, needs verification) / LOW (smell, needs investigation).
- **Fix sketch**: 1–3 sentences detailing how to repair it using the CLI or edits.
```

## Prioritization rubric

Order findings by **leverage = impact ÷ effort, discounted by confidence and fix-risk**.

1. **Correctness/Integrity** findings that fail the strict build/check rules float to the top.
1. **Deploy/CI alignment** issues that block publishing float next.
1. **Style/Formatting** nits follow.
1. "Not worth doing" items are omitted but listed under **Considered and rejected**.
