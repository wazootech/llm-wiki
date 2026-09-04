"""Tests for inline SPARQL block rendering."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.config import Config
from wiki.graph import load_graph, load_query_graph
from wiki.render import _sparql_table_matches, render_markdown_files


class RenderMarkdownFilesTest(unittest.TestCase):
    def test_sparql_table_matches_ignores_mdformat_padding(self) -> None:
        compact = "| class |\n| --- |\n| https://schema.org/TechArticle |\n"
        padded = (
            "| Class                                  |\n"
            "| -------------------------------------- |\n"
            "| https://schema.org/TechArticle         |\n"
        )
        self.assertTrue(_sparql_table_matches(padded, compact))

    def test_render_preserves_query_fence_formatting(self) -> None:
        """Render should update only the result table, not the fenced SPARQL query."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "commands.md"
            page.write_text(
                """---
type: Person
givenName: Alice
familyName: Smith
---
<!-- sparql:start -->

```sparql
SELECT ?givenName WHERE {
  ?s <https://schema.org/givenName> ?givenName .
  FILTER(STRSTARTS(STR(?s), "https://wiki.example.org/"))
}
```
<!-- sparql:end -->
""",
                encoding="utf-8",
            )
            config = Config(
                wiki={"input": [wiki_dir]},
                config_root=wiki_dir,
                graph={
                    "context": {
                        "@vocab": "https://schema.org/",
                        "wiki": "https://wiki.example.org/",
                    }
                },
            )
            graph = load_graph(config, infer=False)

            render_markdown_files(config, graph, explicit_files=(page,))
            rendered = page.read_text(encoding="utf-8")

            self.assertIn("  ?s <https://schema.org/givenName> ?givenName .", rendered)
            self.assertRegex(rendered, r"\| givenName\s+\|")
            self.assertIn("Alice", rendered)

            _, _, stale, _ = render_markdown_files(config, graph, dry_run=True, explicit_files=(page,))
            self.assertEqual(stale, [])

    def test_render_hidden_query_preserves_comment_structure(self) -> None:
        """Hidden-query blocks update the table but keep the query inside HTML comments."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "hidden.md"
            page.write_text(
                """---
type: Person
givenName: Bob
familyName: Jones
---
<!-- sparql:start
```sparql
SELECT ?givenName WHERE {
  ?s <https://schema.org/givenName> ?givenName .
  FILTER(STRSTARTS(STR(?s), "https://wiki.example.org/"))
}
```
-->

<!-- sparql:end -->
""",
                encoding="utf-8",
            )
            config = Config(
                wiki={"input": [wiki_dir]},
                config_root=wiki_dir,
                graph={
                    "context": {
                        "@vocab": "https://schema.org/",
                        "wiki": "https://wiki.example.org/",
                    }
                },
            )
            graph = load_graph(config, infer=False)

            render_markdown_files(config, graph, explicit_files=(page,))
            rendered = page.read_text(encoding="utf-8")

            self.assertIn("<!-- sparql:start\n", rendered)
            self.assertIn("```sparql\n", rendered)
            self.assertIn("-->\n\n", rendered)
            self.assertIn("  ?s <https://schema.org/givenName> ?givenName .", rendered)
            self.assertRegex(rendered, r"\| givenName\s+\|")
            self.assertIn("Bob", rendered)

            _, _, stale, _ = render_markdown_files(config, graph, dry_run=True, explicit_files=(page,))
            self.assertEqual(stale, [])

    def test_render_named_graph_query_uses_dataset(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            wiki_dir.mkdir()
            source_dir.mkdir(parents=True)
            page = wiki_dir / "report.md"
            page.write_text(
                """# Report
<!-- sparql:start -->
```sparql
SELECT ?graph ?name WHERE { GRAPH ?graph { ?s <https://schema.org/name> ?name } }
```
<!-- sparql:end -->
""",
                encoding="utf-8",
            )
            (source_dir / "source.md").write_text("---\ntype: Person\nname: Source Person\n---\n", encoding="utf-8")
            (root / "wiki.lock").write_text(
                '{"version":2,"sources":{"brain":{"url":"https://example.com/brain.git",'
                '"resolved_ref":"abcdef123456","path":"wiki","fetched_at":"2026-01-01T00:00:00+00:00",'
                '"required_by":["root"]}}}',
                encoding="utf-8",
            )
            config = Config(config_root=root, wiki={"input": [wiki_dir, source_dir]})

            render_markdown_files(
                config,
                query_graph=lambda query: load_query_graph(config, query, infer=False),
                explicit_files=(page,),
            )

            rendered = page.read_text(encoding="utf-8")
            self.assertIn("Source Person", rendered)
            self.assertIn("graphs/source/brain", rendered)


if __name__ == "__main__":
    unittest.main()
