---
type: TechArticle
headline: SPARQL
description: Standard query language and protocol for RDF.
---

# SPARQL

**SPARQL** (Recursive acronym for SPARQL Protocol and RDF Query Language) is an [RDF](RDF.md) query language—that is, a semantic query language for databases—able to retrieve and manipulate data stored in RDF format.

In the [wiki](wiki.md), SPARQL powers [wiki query](wiki_query.md), inline tables refreshed by [wiki render](wiki_render.md), and (when enabled) a read-only HTTP endpoint on [wiki serve](wiki_serve.md#sparql-endpoint).

## Common prefixes

The [wiki](wiki.md) automatically binds your namespace prefixes dynamically from the `wiki.yaml` file. The primary prefix mappings are:

- **`schema:`** `https://schema.org/` (Standard schema vocabulary)
- **`wiki:`** `https://wazootech.github.io/wiki/wiki/` (Your local wiki namespace)
- **`rdf:`** `http://www.w3.org/1999/02/22-rdf-syntax-ns#` (Standard RDF attributes)

## Example query types

### Simple SELECT query

Extracts specific properties from your notes. For people, prefer `schema:givenName` and `schema:familyName` (see [Style Guide](Style_Guide.md)):

```sparql
PREFIX schema: <https://schema.org/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?person ?given ?family WHERE {
  ?person rdf:type schema:Person .
  ?person schema:givenName ?given .
  ?person schema:familyName ?family .
}
```

### Filtered query

Uses standard string or URI filters to constrain your results. For TechArticle pages, `schema:headline` and `schema:description` are the display fields:

```sparql
PREFIX schema: <https://schema.org/>

SELECT ?doc ?headline ?description WHERE {
  ?doc rdf:type schema:TechArticle .
  ?doc schema:headline ?headline .
  OPTIONAL { ?doc schema:description ?description . }
  FILTER(STRSTARTS(STR(?doc), "https://wazootech.github.io/wiki/wiki/"))
}
```

## Active database summary

The table below queries the active graph to list all distinct classes currently instantiated in your wiki:

<!-- sparql:start -->

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?class WHERE {
  ?s rdf:type ?class .
  FILTER(STRSTARTS(STR(?class), "https://schema.org/"))
}
ORDER BY ?class
```

| class                                  |
| -------------------------------------- |
| https://schema.org/Person              |
| https://schema.org/SoftwareApplication |
| https://schema.org/TechArticle         |

<!-- sparql:end -->

## Related

- [wiki query](wiki_query.md) — ad-hoc queries from the terminal
- [wiki render](wiki_render.md) — refresh inline SPARQL result tables in markdown
- [wiki serve](wiki_serve.md#sparql-endpoint) — optional read-only HTTP endpoint on `wiki serve`
- [wiki-templates/yasgui](https://github.com/wazootech/wiki-templates/yasgui) — external YASGUI template repository ([Wiki CLI templates](wiki.md#ecosystem-templates))
- [Style Guide](Style_Guide.md) — `sparql:start` / `sparql:end` block conventions

## References

- [SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/): Query language for RDF graphs.
