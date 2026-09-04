---
type: TechArticle
headline: Recursive Semantic Datasets
description: How Wiki composes installed Git-backed Wiki/RDF sources into one read-only query workspace with named graph provenance.
---

# Recursive Semantic Datasets

Wiki source management composes Git-backed Wiki/RDF sources into one semantic corpus without flattening ownership boundaries.

The first product slice is deliberately read-only:

- `wiki.yml` declares root inputs and external `sources:`.
- `wiki.lock` pins exact source commits for reproducible builds.
- `wiki install` materializes sources under `.wiki/sources/`.
- `wiki query` reads a default union view so the composed corpus feels like one Wiki.
- `wiki graph list` exposes root and source graph URIs so SPARQL can inspect provenance with `GRAPH`.

## Why named graphs

An umbrella second brain should let a user query across personal, team, and reference brains together. It should also answer which source owns a result. RDF named graphs provide that boundary without inventing a new query model.

The graph URIs are stable handles:

- Root corpus: `{graph.context.wiki}graphs/root`
- Installed source: `{graph.context.wiki}graphs/source/{source-name}`

Git URLs, requested refs, resolved commits, cache paths, and dependency owners remain metadata. They do not change the graph URI every time a source updates.

## What this is not

This slice does not implement writable source mutation.

Deferred work includes:

- SPARQL Update mapped back to Markdown or YAML files.
- Editing installed source caches in place.
- Fork, branch, worktree, or pull request workflows for upstream contribution.
- Live remote SPARQL federation.
- DVC-backed artifact storage.
- Worlds runtime execution over composed graphs.

Those may become separate capabilities, but they need the read-only provenance layer first.

## Example

```yaml
wiki:
  input:
    - wiki

sources:
  - name: company-brain
    type: git
    url: git@github.com:acme/company-brain.git
    ref: main
    path: wiki
```

After `wiki install`, inspect graph boundaries:

```bash
wiki graph list
```

Query the whole umbrella corpus:

```sparql
SELECT ?s ?name WHERE {
  ?s schema:name ?name .
}
```

Query only the company brain:

```sparql
SELECT ?s ?name WHERE {
  GRAPH <https://example.org/wiki/graphs/source/company-brain> {
    ?s schema:name ?name .
  }
}
```

Ask which graph supplied each result:

```sparql
SELECT ?g ?s ?name WHERE {
  GRAPH ?g {
    ?s schema:name ?name .
  }
}
```

## Related

- [Second Brain](Second_Brain.md)
- [Wiki Configuration](Wiki_Configuration.md#external-data-sources-sources)
- [wiki graph](wiki_graph.md)
- [wiki query](wiki_query.md)
