import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from click.testing import CliRunner

from wiki.cli import main
from wiki.graph_cache import cache_dir
from wiki.mcp import (
    describe_wiki,
    graph_ttl_resource,
    info_resource,
    namespaces_resource,
    query_sparql,
)
from wiki.wiki import Wiki


class TestWikiMcp(unittest.TestCase):
    def _make_wiki(self, tmpdir: str) -> Wiki:
        root = Path(tmpdir)
        wiki_dir = root / "docs" / "wiki"
        wiki_dir.mkdir(parents=True)
        (root / "docs" / "wiki.yml").write_text(
            "wiki:\n  input: wiki\n",
            encoding="utf-8",
        )
        (wiki_dir / "Alice.md").write_text(
            "---\n"
            "type: Person\n"
            "givenName: Alice\n"
            "familyName: Smith\n"
            "---\n",
            encoding="utf-8",
        )
        return Wiki.load(root / "docs" / "wiki.yml")

    def test_query_sparql_returns_structured_result(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            result = query_sparql(
                wiki,
                "SELECT ?given WHERE { ?s <https://schema.org/givenName> ?given }",
                format="json",
                inference=False,
            )

        self.assertEqual(result["format"], "json")
        self.assertEqual(result["query_form"], "SELECT")
        parsed = json.loads(result["result"])
        self.assertEqual(parsed["results"]["bindings"][0]["given"]["value"], "Alice")

    def test_query_sparql_accepts_format_aliases(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            result = query_sparql(
                wiki,
                "SELECT ?given WHERE { ?s <https://schema.org/givenName> ?given }",
                format="text/csv",
                inference=False,
            )

        self.assertEqual(result["format"], "csv")
        self.assertIn("Alice", result["result"])

    def test_query_sparql_rejects_update_and_unsupported_forms(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            with self.assertRaisesRegex(ValueError, "SPARQL Update"):
                query_sparql(wiki, "INSERT DATA { <urn:s> <urn:p> <urn:o> }")
            with self.assertRaisesRegex(ValueError, "Could not determine"):
                query_sparql(wiki, "PREFIX schema: <https://schema.org/> BAD QUERY")

    def test_describe_wiki_includes_observed_vocabulary(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            description = describe_wiki(wiki)

        self.assertEqual(description["config"], "wiki.yml")
        self.assertEqual(description["inputs"], ["wiki"])
        self.assertGreater(description["graph"]["triples"], 0)
        self.assertTrue(description["graph"]["inference"])
        class_iris = {entry["iri"] for entry in description["vocabulary"]["classes"]}
        predicate_iris = {entry["iri"] for entry in description["vocabulary"]["predicates"]}
        self.assertIn("https://schema.org/Person", class_iris)
        self.assertIn("https://schema.org/givenName", predicate_iris)
        person = next(entry for entry in description["vocabulary"]["classes"] if entry["iri"] == "https://schema.org/Person")
        self.assertEqual(person["curie"], "schema:Person")
        self.assertEqual(person["count"], 1)

    def test_describe_wiki_can_persist_graph_cache(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            describe_wiki(wiki, disk_cache=True)

            cache_files = list(cache_dir(wiki.config).glob("graph-infer-*.nt"))

        self.assertEqual(len(cache_files), 1)

    def test_query_sparql_can_persist_graph_cache(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            query_sparql(
                wiki,
                "SELECT ?given WHERE { ?s <https://schema.org/givenName> ?given }",
                inference=False,
                cache=True,
            )

            cache_files = list(cache_dir(wiki.config).glob("graph-asserted-*.nt"))

        self.assertEqual(len(cache_files), 1)

    def test_resources_return_json_and_turtle_bodies(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = self._make_wiki(tmpdir)
            info = json.loads(info_resource(wiki))
            namespaces = json.loads(namespaces_resource(wiki))
            ttl = graph_ttl_resource(wiki)

        self.assertIn("vocabulary", info)
        self.assertIn("schema", namespaces)
        self.assertIn("schema:givenName", ttl)

    def test_cli_registers_mcp_command(self) -> None:
        result = CliRunner().invoke(main, ["mcp", "--help"])

        self.assertEqual(result.exit_code, 0, msg=result.output)
        self.assertIn("Start a read-only MCP server", result.output)
        self.assertIn("--mode", result.output)
        self.assertIn("--cache", result.output)


if __name__ == "__main__":
    unittest.main()
