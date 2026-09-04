"""Tests for RDF serialization and metadata view helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.config import Config
from wiki.format import (
    METADATA_VIEWS,
    markdown_format,
    normalize_metadata_format,
    normalize_metadata_mode,
    pretty_table_format,
    process_rdf_format,
    resolve_metadata_pygments_lexer,
    resolve_metadata_view,
    run_query,
)
from wiki.graph import load_graph


class MetadataViewHelpersTest(unittest.TestCase):
    def test_normalize_metadata_mode(self) -> None:
        self.assertEqual(normalize_metadata_mode("compacted"), "compacted")
        self.assertEqual(normalize_metadata_mode("COMPACTED"), "compacted")
        self.assertEqual(normalize_metadata_mode("expanded"), "expanded")
        self.assertEqual(normalize_metadata_mode(None), "expanded")

    def test_normalize_metadata_format_aliases(self) -> None:
        self.assertEqual(normalize_metadata_format("json-ld"), "json-ld")
        self.assertEqual(normalize_metadata_format("jsonld"), "json-ld")
        self.assertEqual(normalize_metadata_format("ttl"), "turtle")
        self.assertEqual(normalize_metadata_format("rdf"), "xml")
        self.assertEqual(normalize_metadata_format("application/rdf+xml"), "xml")
        self.assertEqual(normalize_metadata_format("unknown"), "json-ld")

    def test_resolve_metadata_view_json_ld_is_always_compacted(self) -> None:
        self.assertEqual(resolve_metadata_view("json-ld", "expanded"), "json-ld-compacted")
        self.assertEqual(resolve_metadata_view("json-ld", "compacted"), "json-ld-compacted")
        self.assertEqual(resolve_metadata_view("jsonld", "compacted"), "json-ld-compacted")

    def test_resolve_metadata_view_non_json_ld_ignores_mode(self) -> None:
        self.assertEqual(resolve_metadata_view("turtle", "compacted"), "turtle")
        self.assertEqual(resolve_metadata_view("ttl", "expanded"), "turtle")

    def test_metadata_views_cover_export_formats(self) -> None:
        formats = {view.format for view in METADATA_VIEWS}
        self.assertIn("json-ld", formats)
        self.assertIn("turtle", formats)
        self.assertIn("xml", formats)
        self.assertIn("nquads", formats)

    def test_resolve_metadata_pygments_lexer_aliases_missing_rdf_lexers(self) -> None:
        self.assertEqual(resolve_metadata_pygments_lexer("n3"), "turtle")
        self.assertEqual(resolve_metadata_pygments_lexer("trig"), "turtle")
        self.assertEqual(resolve_metadata_pygments_lexer("nt"), "turtle")

    def test_resolve_metadata_pygments_lexer_passthrough(self) -> None:
        self.assertEqual(resolve_metadata_pygments_lexer("turtle"), "turtle")
        self.assertEqual(resolve_metadata_pygments_lexer("xml"), "xml")
        self.assertEqual(resolve_metadata_pygments_lexer("json"), "json")


class MarkdownFormatTest(unittest.TestCase):
    def test_markdown_format_uses_unmodified_variable_names_as_headers(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text(
                """---
type: Person
givenName: Alice
familyName: Smith
---""",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki_dir]}, config_root=wiki_dir)
            graph = load_graph(config, infer=False)
            result = graph.query(
                "SELECT ?givenName ?familyName WHERE { ?s <https://schema.org/givenName> ?givenName ; "
                "<https://schema.org/familyName> ?familyName }"
            )
            output = markdown_format(result)
            self.assertIn("| givenName | familyName |", output)
            self.assertNotIn("| Givenname |", output)


class CompactJsonLdContextTest(unittest.TestCase):
    def test_compacted_json_ld_context_includes_only_used_prefixes(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            config = Config(wiki={"input": [wiki_dir]}, config_root=wiki_dir)
            frontmatter = {
                "type": "TechArticle",
                "headline": "wiki query",
                "description": "Run SPARQL SELECT or CONSTRUCT against the wiki graph.",
            }
            compacted = process_rdf_format(
                frontmatter,
                "wiki_query",
                config.context,
                "json-ld",
                mode="compacted",
            )
            self.assertIsInstance(compacted, dict)
            context = compacted["@context"]
            self.assertIn("schema", context)
            self.assertIn("wiki", context)
            self.assertNotIn("dc", context)
            self.assertNotIn("foaf", context)
            self.assertNotIn("owl", context)
            self.assertNotIn("sh", context)
            self.assertNotIn("wazoo", context)


class PrettyTableFormatTest(unittest.TestCase):
    def test_pretty_table_format_renders_headers_and_rows(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text(
                """---
type: Person
givenName: Alice
familyName: Smith
---""",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki_dir]}, config_root=wiki_dir)
            graph = load_graph(config, infer=False)
            output = run_query(
                graph,
                "SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }",
                pretty=True,
            )
            self.assertIn("givenName", output)
            self.assertIn("Alice", output)

    def test_pretty_table_format_empty_results(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            config = Config(wiki={"input": [wiki_dir]}, config_root=wiki_dir)
            graph = load_graph(config, infer=False)
            result = graph.query("SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }")
            self.assertEqual(pretty_table_format(result), "(no results)")


if __name__ == "__main__":
    unittest.main()
