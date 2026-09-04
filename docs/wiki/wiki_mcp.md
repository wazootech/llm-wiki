---
type: TechArticle
headline: wiki mcp
description: Run a read-only MCP server for querying the wiki graph.
---

# `wiki mcp`

Start a local [Model Context Protocol](https://modelcontextprotocol.io/) server for the configured Wiki graph. The server is read-only and query-first: it exposes SPARQL execution and graph context for agents, not page editing, formatting, link repair, build, or filesystem automation.

## Usage

```bash
wiki mcp
wiki -c docs/wiki.yml mcp
wiki --wiki-inputs docs/wiki mcp
wiki mcp --mode stdio
wiki mcp --cache
```

`stdio` is the default and only transport in the first version.

## Claude Code setup

Register the local server with Claude Code:

```bash
claude mcp add wiki -- wiki -c docs/wiki.yml mcp
```

Generic stdio MCP clients should run the same command shape:

```bash
wiki -c docs/wiki.yml mcp
```

## Options

| Flag      | Default | Description                                                  |
| --------- | ------- | ------------------------------------------------------------ |
| `--mode`  | `stdio` | MCP transport mode.                                          |
| `--cache` | off     | Persist graph artifacts under `.wiki/cache` across launches. |

## Tools

### `query_sparql`

Execute SPARQL against the compiled wiki graph.

Parameters:

```json
{
  "query": "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
  "format": "json",
  "inference": true,
  "reload": false
}
```

Allowed query forms: `SELECT`, `ASK`, `CONSTRUCT`, and `DESCRIBE`. SPARQL Update and unsupported query forms are rejected before execution.

`format` reuses [wiki query](wiki_query.md) names and aliases: `table`, `json`, `csv`, `tsv`, `turtle`, `n3`, and `markdown`. The MCP default is `json`.

The tool returns a structured object:

```json
{
  "format": "json",
  "query_form": "SELECT",
  "result": "..."
}
```

### `describe_wiki`

Return factual context for writing grounded SPARQL:

- Wiki CLI version
- Config path and inputs
- Namespace bindings from the built graph
- Graph stats for the default inferred graph
- Observed vocabulary from the graph

The vocabulary summary is intentionally load-bearing for agent use. It lists real classes and predicates so agents can avoid inventing predicates, getting empty results, and treating a bad query as missing data.

Example shape:

```json
{
  "version": "0.1.22",
  "config": "docs/wiki.yml",
  "inputs": ["docs/wiki"],
  "namespaces": {
    "schema": "https://schema.org/",
    "wiki": "https://wiki.example.org/"
  },
  "graph": {
    "triples": 1234,
    "subjects": 120,
    "predicates": 45,
    "objects": 900,
    "inference": true
  },
  "vocabulary": {
    "classes": [
      { "iri": "https://schema.org/Person", "curie": "schema:Person", "count": 12 }
    ],
    "predicates": [
      { "iri": "https://schema.org/name", "curie": "schema:name", "count": 42 }
    ]
  }
}
```

Vocabulary limits are intentionally compact: top 25 classes by `rdf:type` usage and top 50 predicates by triple count.

## Resources

| Resource            | MIME type          | Purpose                                                        |
| ------------------- | ------------------ | -------------------------------------------------------------- |
| `wiki://info`       | `application/json` | Version, config, inputs, graph settings, stats, and vocabulary |
| `wiki://namespaces` | `application/json` | Prefix map for SPARQL authoring                                |
| `wiki://graph.ttl`  | `text/turtle`      | Current inferred graph serialized as Turtle                    |

## Safety model

`wiki mcp` is read-only by default:

- No wiki source mutation
- No build output writes
- No formatting changes
- No link repair
- No generic file read/write tools
- No Obsidian automation
- No SPARQL Update

The command reuses the same graph cache behavior as other Wiki CLI operations: in-process caching is always used within one running MCP server, and `--cache` enables filesystem persistence under `.wiki/cache` for faster reuse across MCP launches. `reload=true` on `query_sparql` rebuilds the in-memory graph before executing the query; with `--cache`, the rebuilt graph is also written back to the filesystem cache.

## Related

- [wiki query](wiki_query.md)
- [wiki serve](wiki_serve.md#sparql-endpoint)
- [Graph Cache](Graph_Cache.md)
- [SPARQL](SPARQL.md)
