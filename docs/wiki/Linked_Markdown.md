---
type:
  - schema:TechArticle
  - schema:SoftwareApplication
headline: Linked Markdown
name: Linked_Markdown
description: The protocol specifying how semantic frontmatter and Markdown cross-links compile to an RDF graph.
codeRepository: https://github.com/wazootech/linked-markdown
---

# Linked Markdown

The **Linked Markdown protocol** (specifically the `wazootech/linked-markdown` protocol implemented by `wazootech-wiki`) specifies how a directory of Markdown files with structured metadata and hyperlink connections is compiled into a semantic RDF graph.

It bridges the gap between readable Markdown documents (Zettelkasten notes or documentation sites) and graph-based data querying, enabling validation using [SHACL](SHACL.md) and extraction using [SPARQL](SPARQL.md).

## Core concepts

Under the Linked Markdown protocol:

- **Documents as subjects** — Each Markdown document is a node (resource subject) in the RDF graph. Its IRI is determined by the document's file path.
- **Frontmatter as predicates** — YAML or JSON frontmatter at the top of a document maps directly to properties (predicates) and values (objects).
- **Links as semantic edges** — Markdown links and WikiLinks act as semantic relationships, connecting document subjects in the graph.
- **Prose microdata** — HTML Microdata embeds structured nodes directly within the document body (supported in a future specification).

## Subject URI resolution

The subject IRI of a document is inferred from its relative filepath from the wiki root (under `wiki.input`). The default namespace prefix is `wiki:`, resolving to the configured base IRI.

For example, a file located at `wiki/people/Alice_Smith.md` resolves to:

- **Subject IRI:** `https://wiki.example.org/people/Alice_Smith` (or CURIE `wiki:people/Alice_Smith`)

If an explicit `@id` or `id` key is present in the frontmatter, it overrides the default file-based IRI.

## Frontmatter mapping

Frontmatter keys are resolved to full RDF predicate URIs according to the following order:

1. **Explicit CURIE** — Keys with a prefix (for example, `rdfs:label` or `foaf:name`) are expanded using namespaces configured under `graph.context` in `wiki.yml`.
1. **Wiki namespace** — Keys starting with `wiki.` (such as `wiki.status`) map to the local `wiki:` vocabulary.
1. **Default schema** — Keys without a prefix (such as `headline` or `description`) resolve to the **schema.org** namespace by default (yielding `schema:headline`).

### Frontmatter example

```yaml
---
type: schema:Person
givenName: Alice
familyName: Smith
foaf:knows: wiki:people/Bob_Jones
---
```

This compiles into the following RDF triples:

```turtle
@prefix people: <https://wiki.example.org/people/> .
@prefix schema: <https://schema.org/> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .

people:Alice_Smith a schema:Person ;
    schema:givenName "Alice" ;
    schema:familyName "Smith" ;
    foaf:knows people:Bob_Jones .
```

## Link graph integration

Hyperlinks between Markdown pages represent semantic relationships. Link paths are normalized and resolved to page route IDs.

### Standard Markdown links

An inline link pointing to another page:

`Alice has been collaborating with [Bob Jones](Bob_Jones.md).`

### WikiLinks

Bi-directional wikilink syntax is also supported:

`Alice has been collaborating with [[Bob_Jones]].`

In the compiled RDF graph, these links are stored as directional relations allowing backlink indexing, dependency resolution, and integrity checks using `wiki lint` to identify broken links.

## HTML microdata in prose

For now, the Linked Markdown protocol does not officially support HTML microdata inside the document body, but there are plans to define and support it in future specifications.

## Validation and schema compliance

The compiled graph can be checked using shape definitions in the wiki:

- **SHACL shapes** — Defined using `type: sh:NodeShape` in document frontmatter to validate data types and cardinality.
- **JSON Schema** — Configured via `wazoo:jsonSchema` in frontmatter to enforce validation on metadata fields.

## Related

- [Style Guide](Style_Guide.md)
- [wiki](wiki.md)
- [Wiki Configuration](Wiki_Configuration.md)
- [SHACL](SHACL.md)
- [RDF](RDF.md)
