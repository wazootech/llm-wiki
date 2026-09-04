---
type: TechArticle
headline: wiki render
description: Update inline SPARQL result tables in markdown files.
---

# `wiki render`

Find `&lt;!-- sparql:start --&gt;` ... `&lt;!-- sparql:end --&gt;` regions in markdown, run the embedded query against the wiki graph, and rewrite the table (or `(no results)`) in place.

Silent on success by default. See [Design Philosophies](Design_Philosophies.md).

## Usage

```bash
wiki render
wiki render wiki/Report.md
wiki render wiki/people/alpha.md wiki/projects/beta.md
wiki render wiki/people/*.md
wiki render -v
wiki render --check
wiki render --no-inference
wiki render --reload
wiki render --cache
```

## Options

| Flag              | Description                                                                            |
| ----------------- | -------------------------------------------------------------------------------------- |
| `FILE...`         | Optional `.md` paths; otherwise entire wiki (shell globs expand to multiple FILE args) |
| `--check`         | Dry-run; exit 1 if any block is stale                                                  |
| `--no-inference`  | Skip OWL-RL                                                                            |
| `--reload`        | Rebuild graph before rendering                                                         |
| `--cache`         | Persist a warm graph under `.wiki/cache/` for reuse across new processes               |
| `-v`, `--verbose` | Print update counts                                                                    |

## Block format

See [Style Guide](Style_Guide.md) for the `sparql:start` / `sparql:end` wrapper and fenced `sparql` code block. Close the start comment before the fence to show the query in built HTML. Leave it open and close after the fence to hide the query from published pages while `wiki render` still updates the table.

## Examples

### List all people (visible query)

The default visible block style shows the query in published HTML so readers can see and learn from it.

<!-- sparql:start -->

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?person ?givenName ?familyName WHERE {
  ?person rdf:type schema:Person .
  ?person schema:givenName ?givenName .
  ?person schema:familyName ?familyName .
}
ORDER BY ?familyName
```

| person                                      | givenName | familyName |
| ------------------------------------------- | --------- | ---------- |
| [Jeff_Kazzee](Jeff_Kazzee.md)               | Jeff      | Kazzee     |
| https://wiki.example.org/people/Alice_Smith | Alice     | Smith      |

<!-- sparql:end -->

### List all software applications (hidden query)

The hidden query style keeps the SPARQL inside an HTML comment — invisible in published pages, but still executed by `wiki render`.

<!-- sparql:start
```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?app ?name ?version WHERE {
  ?app rdf:type schema:SoftwareApplication .
  ?app schema:name ?name .
  OPTIONAL { ?app schema:softwareVersion ?version . }
}
ORDER BY ?name
```
-->

| app | name | version |
| --- | --- | --- |
| [Linked_Markdown](Linked_Markdown.md) | Linked Markdown |  |
| [Obsidian](Obsidian.md) | Obsidian |  |
| [Vivary](Vivary.md) | Vivary | 0.1.0 |
| [wiki](wiki.md) | wiki | 0.1.22 |

<!-- sparql:end -->

### More query patterns

Paste one of these SPARQL queries into a `sparql:start` block on any wiki page and run `wiki render` to see results.

**All TechArticles with headlines and descriptions:**

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?headline ?description WHERE {
  ?doc rdf:type schema:TechArticle .
  ?doc schema:headline ?headline .
  OPTIONAL { ?doc schema:description ?description . }
}
ORDER BY ?headline
```

**Full-text search for pages that mention a term in their body:**

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?headline WHERE {
  ?doc rdf:type schema:TechArticle .
  ?doc schema:headline ?headline .
  ?doc schema:articleBody ?body .
  FILTER(CONTAINS(?body, &quot;your-search-term&quot;))
}
ORDER BY ?headline
```

**Backlinks to a target page via body text:**

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?headline WHERE {
  ?doc rdf:type schema:TechArticle .
  ?doc schema:headline ?headline .
  ?doc schema:articleBody ?body .
  FILTER(CONTAINS(?body, &quot;Target_Page&quot;))
}
ORDER BY ?headline
```

Replace `&quot;Target_Page&quot;` with a page filename (without `.md`) to find pages that link to it.

**Recent changes by date (requires date frontmatter):**

Add `dateCreated` or `dateModified` to your page frontmatter with a YAML date (e.g. `dateCreated: 2026-06-28`). The wiki graph automatically types these as `xsd:date`. Then query:

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX schema: <https://schema.org/>

SELECT ?headline ?created WHERE {
  ?doc rdf:type schema:TechArticle .
  ?doc schema:headline ?headline .
  ?doc schema:dateCreated ?created .
}
ORDER BY DESC(?created)
```

## Related

- [SPARQL](SPARQL.md)
- [Style Guide](Style_Guide.md) — `sparql:start` / `sparql:end` block format
- [Graph Cache](Graph_Cache.md)
- [wiki query](wiki_query.md)
- [wiki build](wiki_build.md) — `wiki build --render`
