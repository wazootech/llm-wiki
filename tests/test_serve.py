"""Tests for the wiki serve subcommand."""

from __future__ import annotations

import json
import socket
import threading
import unittest
from collections.abc import Generator
from http.client import HTTPConnection
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from unittest.mock import patch

from click.testing import CliRunner

from layout_helpers import write_layout
from wiki.cli import main
from wiki.config import Config
from wiki.serve import (
    _parse_sparql_http_request,
    _watch_for_changes,
    build_site,
    create_server,
    refresh_wiki,
    run_server,
)
from wiki.wiki import Wiki


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


_RICH_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
%wiki.head%
</head>
<body>
%wiki.body%
</body>
</html>"""


_METADATA_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
%wiki.head%
</head>
<body>
%wiki.page.metadata.tool%
%wiki.page.metadata.tab%
%wiki.page.metadata.pane%
%wiki.body%
</body>
</html>"""


def _serve_in_thread(wiki_dir: Path) -> Generator[int, None, None]:
    port = _free_port()
    config = Config(wiki={"inputs": [wiki_dir]}, config_root=wiki_dir)
    server = create_server(config, host="127.0.0.1", port=port)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    for _ in range(100):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/")
            conn.getresponse()
            conn.close()
            break
        except ConnectionRefusedError:
            sleep(0.05)
    yield port
    server.shutdown()


def _serve_with_template(wiki_dir: Path, template: str = _RICH_TEMPLATE) -> Generator[int, None, None]:
    port = _free_port()
    template_path = write_layout(wiki_dir, "test_shell.html", template)
    config = Config(
        wiki={"inputs": [wiki_dir]},
        site={"layout": template_path},
        config_root=wiki_dir,
    )
    server = create_server(config, host="127.0.0.1", port=port)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    for _ in range(100):
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/")
            conn.getresponse()
            conn.close()
            break
        except ConnectionRefusedError:
            sleep(0.05)
    yield port
    server.shutdown()


class TestServe(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = TemporaryDirectory()
        self.wiki_dir = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write(self, name: str, content: str) -> Path:
        p = self.wiki_dir / name
        p.write_text(content, encoding="utf-8")
        return p

    def _get(self, port: int, path: str) -> tuple[int, str]:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        return resp.status, body

        self._write("hello-world.md", "# Hello World\n\nSome content.")
        self._write("foo-bar.md", "# Foo Bar\n\nContent.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/")
        self.assertEqual(status, 200)
        self.assertIn("All Pages", body)
        self.assertIn("Hello World", body)
        self.assertIn("Foo Bar", body)
        self.assertIn("/wiki/hello-world/", body)
        self.assertIn("/wiki/foo-bar/", body)

    def test_index_links_use_config_file_url_style(self) -> None:
        self._write("hello-world.md", "# Hello World\n\nSome content.")
        config = Config(wiki={"inputs": [self.wiki_dir]}, site={"url_style": "file"}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        status, body = self._get(port, "/")
        server.shutdown()
        self.assertEqual(status, 200)
        self.assertIn("/wiki/hello-world.html", body)
        self.assertNotIn("/wiki/hello-world/", body)

    def test_render_page(self) -> None:
        self._write("hello.md", "# Hello\n\nParagraph text.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/hello")
        self.assertEqual(status, 200)
        self.assertIn("Hello", body)
        self.assertIn("Paragraph text.", body)

    def test_wikilinks_rendered(self) -> None:
        self._write("alpha.md", "# Alpha\n\nSee [[beta]] for details.")
        self._write("beta.md", "# Beta\n\nContent.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/alpha")
        self.assertEqual(status, 200)
        self.assertIn('class="wikilink"', body)
        self.assertIn("/wiki/beta", body)

    def test_wikilinks_with_display(self) -> None:
        self._write("alpha.md", "# Alpha\n\nSee [[beta|Beta]].")
        self._write("beta.md", "# Beta\n\nContent.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/alpha")
        self.assertEqual(status, 200)
        self.assertIn('class="wikilink"', body)
        self.assertIn("/wiki/beta", body)

    def test_h2_headings_are_in_page_anchors_not_virtual_pages(self) -> None:
        self._write("guide.md", "# Guide\n\nIntro.\n\n## Setup\n\nSetup content.\n\n## Usage\n\nUsage content.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/guide/setup")
            page_status, page_body = self._get(port, "/wiki/guide")
            self.assertEqual(status, 404)
            self.assertEqual(page_status, 200)
            self.assertIn('id="setup"', page_body)
            self.assertIn('id="usage"', page_body)

            status2, _ = self._get(port, "/wiki/guide/usage")
            self.assertEqual(status2, 404)

    def test_toc_h3_to_h6(self) -> None:
        self._write("doc.md", "# Doc\n\n## Section\n\n### Sub A\n\nContent A\n\n#### SubSub\n\nDeep.\n\n### Sub B\n\nContent B")
        for port in _serve_with_template(self.wiki_dir):
            status, body = self._get(port, "/wiki/doc")
        self.assertEqual(status, 200)
        self.assertNotIn("On this page", body)
        self.assertIn("Sub A", body)
        self.assertIn("Sub B", body)
        self.assertIn("SubSub", body)
        self.assertIn('id="sub-a"', body)
        self.assertIn('id="sub-b"', body)
        self.assertIn('id="subsub"', body)

    def test_backlinks(self) -> None:
        self._write("alpha.md", "# Alpha\n\nLinks to [[beta]].")
        self._write("beta.md", "# Beta\n\nContent.")
        for port in _serve_with_template(self.wiki_dir):
            status, body = self._get(port, "/wiki/beta")
        self.assertEqual(status, 200)
        self.assertNotIn("Backlinks", body)
        self.assertNotIn("Alpha", body)

    def test_frontmatter_metadata(self) -> None:
        self._write("page.md", "---\ntitle: My Page\ntype: Article\n---\n\n# My Page\n\nContent.")
        for port in _serve_with_template(self.wiki_dir):
            status, body = self._get(port, "/wiki/page")
        self.assertEqual(status, 200)
        self.assertIn("My Page", body)
        self.assertNotIn("Article", body)

    def test_removed_metadata_slot_stays_literal(self) -> None:
        self._write("page.md", "---\ntype: Article\nname: My Page\nabout: wiki:My_Page\n---\n\n# My Page\n")
        for port in _serve_with_template(self.wiki_dir, template=_METADATA_TEMPLATE):
            status, body = self._get(port, "/wiki/page")

        self.assertEqual(status, 200)
        self.assertIn("%wiki.page.metadata.pane%", body)
        self.assertNotIn('value="json-ld-compacted" checked="checked"', body)
        self.assertNotIn('&quot;@context&quot;', body)

    def test_404(self) -> None:
        self._write("exists.md", "# Exists")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/nonexistent")
        self.assertEqual(status, 404)

    def test_multiple_files_index(self) -> None:
        self._write("a.md", "# A Page")
        self._write("b.md", "# B Page")
        self._write("c.md", "# C Page")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/")
        self.assertEqual(status, 200)
        for title in ["A Page", "B Page", "C Page"]:
            self.assertIn(title, body)
        for slug in ["a", "b", "c"]:
            self.assertIn(f"/wiki/{slug}", body)

    def test_no_wiki_dir(self) -> None:
        empty_dir = Path(self.tmpdir.name) / "empty"
        empty_dir.mkdir()
        site = build_site(empty_dir)
        self.assertEqual(len(site.pages), 0)

    def test_no_css_in_fallback(self) -> None:
        self._write("style-test.md", "# Style")
        for port in _serve_in_thread(self.wiki_dir):
            _, body = self._get(port, "/")
        self.assertIn("All Pages - Wiki CLI", body)
        self.assertNotIn("<style>", body)

        for port in _serve_in_thread(self.wiki_dir):
            _, body = self._get(port, "/wiki/style-test")
        self.assertIn("Style", body)
        self.assertNotIn("<style>", body)

    def test_wikilinks_resolve_wiki_path(self) -> None:
        self._write("source.md", "# Source\n\nSee [[target-page]].")
        self._write("target-page.md", "# Target Page")
        for port in _serve_in_thread(self.wiki_dir):
            _, body = self._get(port, "/wiki/source")
        self.assertIn("/wiki/target-page", body)

    def test_case_preserved_routes_and_wikilinks(self) -> None:
        self._write("Source.md", "# Source\n\nSee [[Ethan_Davidson]].")
        self._write("Ethan_Davidson.md", "# Ethan Davidson")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/Source")
            target_status, _ = self._get(port, "/wiki/Ethan_Davidson")
        self.assertEqual(status, 200)
        self.assertEqual(target_status, 200)
        self.assertIn("/wiki/Ethan_Davidson", body)

    def test_h1_page_as_full_document(self) -> None:
        self._write("full.md", "# Full Doc\n\nIntro.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/full")
        self.assertEqual(status, 200)
        self.assertIn("Full Doc", body)
        self.assertIn("Section A</h2>", body)
        self.assertIn("Section B</h2>", body)
        self.assertIn("Content A.", body)
        self.assertIn("Content B.", body)

    def test_page_without_frontmatter(self) -> None:
        self._write("plain.md", "# Plain Page\n\nJust content.")
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/wiki/plain")
        self.assertEqual(status, 200)
        self.assertIn("Plain Page", body)
        self.assertNotIn("Metadata", body)

    def test_index_empty_dir(self) -> None:
        for port in _serve_in_thread(self.wiki_dir):
            status, body = self._get(port, "/")
        self.assertEqual(status, 200)
        self.assertIn("All Pages", body)

    def test_serve_cli_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--host", result.output)
        self.assertIn("--port", result.output)
        self.assertIn("--site-base-url", result.output)

    def test_serve_cli_defaults(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        self.assertIn("[default: 8080]", result.output)
        self.assertIn("[default: 127.0.0.1]", result.output)
        self.assertIn("--site-base-url", result.output)

    def test_refresh_wiki_renders_sparql_and_builds_site(self) -> None:
        source = """---
type: Person
givenName: Gregory
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
"""
        page = self.wiki_dir / "gregory.md"
        page.write_text(source, encoding="utf-8")
        config = Config(wiki={"inputs": [self.wiki_dir]}, config_root=self.wiki_dir)

        site = refresh_wiki(config, changed_paths={page})

        self.assertRegex(page.read_text(encoding="utf-8"), r"\| givenName\s+\|")
        self.assertGreater(len(site.pages), 0)

    def test_sparql_endpoint_get_service_description_turtle(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/sparql", headers={"Accept": "text/turtle"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "text/turtle; charset=utf-8")
        self.assertIn("sd:endpoint", body)
        self.assertIn(f"<http://127.0.0.1:{port}/api/sparql>", body)
        self.assertIn("sd:SPARQL11Query", body)

    def test_parse_sparql_http_request_handles_get_and_post(self) -> None:
        class Headers(dict):
            def get(self, key: str, default: str = "") -> str:
                return super().get(key, default)

        query, output_format, infer, reload_graph = _parse_sparql_http_request(
            "GET",
            "query=SELECT%20*%20WHERE%20%7B%20%3Fs%20%3Fp%20%3Fo%20%7D&inference=false&reload=true",
            Headers({"Accept": "application/sparql-results+json"}),
            BytesIO(b""),
        )
        self.assertTrue(query.startswith("SELECT"))
        self.assertEqual(output_format, "json")
        self.assertFalse(infer)
        self.assertTrue(reload_graph)

        query, output_format, infer, reload_graph = _parse_sparql_http_request(
            "POST",
            "",
            Headers({"Content-Type": "application/sparql-query", "Content-Length": "41", "Accept": "text/turtle"}),
            BytesIO(b"CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"),
        )
        self.assertTrue(query.startswith("CONSTRUCT"))
        self.assertEqual(output_format, "turtle")
        self.assertTrue(infer)
        self.assertFalse(reload_graph)

    def test_sparql_endpoint_get_service_description_rdf_xml(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/sparql", headers={"Accept": "application/rdf+xml"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "application/rdf+xml; charset=utf-8")
        self.assertIn("sd:endpoint", body)
        self.assertIn(f"http://127.0.0.1:{port}/api/sparql", body)

    def test_sparql_endpoint_get_select_json(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/sparql?query=SELECT%20%3Fname%20WHERE%20%7B%20%3Fs%20%3Chttps%3A//schema.org/givenName%3E%20%3Fname%20%7D", headers={"Accept": "application/sparql-results+json"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "application/sparql-results+json; charset=utf-8")
        self.assertIn("Alice", body)

    def test_sparql_endpoint_named_graph_query_uses_dataset(self) -> None:
        root = self.wiki_dir
        wiki_dir = root / "wiki"
        source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
        wiki_dir.mkdir()
        source_dir.mkdir(parents=True)
        (wiki_dir / "root.md").write_text("---\ntype: Person\nname: Root Person\n---\n", encoding="utf-8")
        (source_dir / "source.md").write_text("---\ntype: Person\nname: Source Person\n---\n", encoding="utf-8")
        (root / "wiki.lock").write_text(json.dumps({
            "version": 2,
            "sources": {
                "brain": {
                    "url": "https://example.com/brain.git",
                    "resolved_ref": "abcdef1234567890",
                    "path": "wiki",
                    "fetched_at": "2026-01-01T00:00:00+00:00",
                    "required_by": ["root"],
                }
            },
        }), encoding="utf-8")
        config = Config(
            wiki={"inputs": [wiki_dir, source_dir]},
            sparql_service={"enabled": True},
            config_root=root,
        )
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/sparql",
            body="SELECT ?graph ?name WHERE { GRAPH ?graph { ?s <https://schema.org/name> ?name } }",
            headers={"Content-Type": "application/sparql-query", "Accept": "application/sparql-results+json"},
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()

        self.assertEqual(resp.status, 200, body)
        self.assertIn("Source Person", body)
        self.assertIn("graphs/source/brain", body)

    def test_sparql_endpoint_post_construct_turtle(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/sparql",
            body="CONSTRUCT { ?s <https://schema.org/givenName> ?givenName } WHERE { ?s <https://schema.org/givenName> ?givenName }",
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "text/turtle",
            },
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "text/turtle; charset=utf-8")
        self.assertIn("schema:givenName", body)
        self.assertIn("Alice", body)

    def test_sparql_endpoint_can_be_disabled(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        port = _free_port()
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": False}, config_root=self.wiki_dir)
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/sparql?query=SELECT%20*%20WHERE%20%7B%20%3Fs%20%3Fp%20%3Fo%20%7D")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 404)
        self.assertIn("SPARQL endpoint is disabled", body)

    def test_sparql_endpoint_custom_path(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        port = _free_port()
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True, "path": "/sparql"}, config_root=self.wiki_dir)
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/sparql?query=SELECT%20%3Fname%20WHERE%20%7B%20%3Fs%20%3Chttps%3A//schema.org/givenName%3E%20%3Fname%20%7D", headers={"Accept": "application/sparql-results+json"})
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 200)
        self.assertIn("Alice", body)

    def test_sparql_endpoint_rejects_update_queries(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/sparql",
            body="INSERT DATA { <https://example.org/a> <https://schema.org/givenName> \"Alice\" }",
            headers={
                "Content-Type": "application/sparql-query",
                "Accept": "application/sparql-results+json",
            },
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 405)
        self.assertIn("SPARQL Update is not supported", body)

    def test_sparql_endpoint_allows_literals_with_update_keywords(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Delete\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True}, config_root=self.wiki_dir)
        port = _free_port()
        server = create_server(config, host="127.0.0.1", port=port)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        for _ in range(100):
            try:
                conn = HTTPConnection("127.0.0.1", port, timeout=1)
                conn.request("GET", "/")
                conn.getresponse()
                conn.close()
                break
            except ConnectionRefusedError:
                sleep(0.05)
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "GET",
            "/api/sparql?query=SELECT%20%3Fname%20WHERE%20%7B%20%3Fs%20%3Chttps%3A//schema.org/givenName%3E%20%3Fname%20.%20FILTER(%3Fname%20%3D%20%22Delete%22)%20%7D",
            headers={"Accept": "application/sparql-results+json"},
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        server.shutdown()
        server.server_close()
        self.assertEqual(resp.status, 200)
        self.assertIn("Delete", body)

    def test_sparql_endpoint_invalid_root_path_rejected(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True, "path": "/"}, config_root=self.wiki_dir)
        with self.assertRaisesRegex(ValueError, "shadow the entire server"):
            create_server(config, host="127.0.0.1", port=_free_port())

    def test_sparql_endpoint_invalid_base_url_path_rejected(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True, "path": "/wiki"}, config_root=self.wiki_dir)
        with self.assertRaisesRegex(ValueError, "collides with page routes"):
            create_server(config, host="127.0.0.1", port=_free_port())

    def test_sparql_endpoint_invalid_page_subpath_rejected(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True, "path": "/wiki/foo"}, config_root=self.wiki_dir)
        with self.assertRaisesRegex(ValueError, "collides with page routes"):
            create_server(config, host="127.0.0.1", port=_free_port())

    def test_sparql_endpoint_invalid_watch_path_rejected(self) -> None:
        self._write("person.md", "---\ntype: Person\ngivenName: Alice\n---\n")
        config = Config(wiki={"inputs": [self.wiki_dir]}, sparql_service={"enabled": True, "path": "/wiki/__watch"}, config_root=self.wiki_dir)
        with self.assertRaisesRegex(ValueError, "collides with the watch endpoint"):
            create_server(config, host="127.0.0.1", port=_free_port())

    def test_watch_loop_repeated_refreshes_increment_build_id(self) -> None:
        page = self._write("alpha.md", "# Alpha\n")
        watch_dirs = [self.wiki_dir]
        initial = {str(page): 1.0}
        second = {str(page): 2.0}
        third = {str(page): 3.0}
        snapshots = iter([second, third, third])
        stop_event = threading.Event()

        class FakeServer:
            def __init__(self) -> None:
                self.state = type("State", (), {"build_id": 0, "site": None})()

        server = FakeServer()

        def fake_snapshot(_: list[Path]) -> dict[str, float]:
            state = next(snapshots)
            if state == third:
                stop_event.set()
            return state

        refreshed_sites = [object(), object()]
        with patch("wiki.serve.refresh_wiki", side_effect=refreshed_sites) as refresh_mock, patch("wiki.serve.time.sleep", return_value=None):
            _watch_for_changes(
                Config(wiki={"inputs": [self.wiki_dir]}, config_root=self.wiki_dir),
                watch_dirs=watch_dirs,
                base_url="/wiki",
                url_style="dir",
                mtimes=initial,
                server=server,
                stop_event=stop_event,
                poll_interval=0,
                snapshot_func=fake_snapshot,
            )

        self.assertEqual(refresh_mock.call_count, 2)
        self.assertEqual(server.state.build_id, 2)
        self.assertIs(server.state.site, refreshed_sites[-1])

    def test_run_server_shutdowns_on_keyboard_interrupt(self) -> None:
        class FakeServer:
            def __init__(self) -> None:
                self.shutdown_called = False
                self.server_close_called = False

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def shutdown(self) -> None:
                self.shutdown_called = True

            def server_close(self) -> None:
                self.server_close_called = True

        fake_server = FakeServer()
        config = Config(wiki={"inputs": [self.wiki_dir]}, config_root=self.wiki_dir)

        with patch("wiki.serve.create_server", return_value=fake_server):
            run_server(config)

        self.assertTrue(fake_server.shutdown_called)
        self.assertTrue(fake_server.server_close_called)

    def test_serve_does_not_mutate_loaded_config_site_overrides(self) -> None:
        runner = CliRunner()
        config = Config(wiki={"inputs": [self.wiki_dir]}, site={"base_url": "/wiki", "url_style": "dir"}, config_root=self.wiki_dir)

        with patch("wiki.cli.Wiki.load", return_value=Wiki(config)), patch(
            "wiki.serve.run_server"
        ) as run_server_mock:
            result = runner.invoke(
                main,
                [
                    "--config",
                    str(self.wiki_dir),
                    "serve",
                    "--site-base-url",
                    "/custom",
                    "--site-url-style",
                    "file",
                ],
            )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(config.site.base_url, "/wiki")
        self.assertEqual(config.site.url_style, "dir")
        run_server_mock.assert_called_once()
        runtime_config = run_server_mock.call_args[0][0]
        self.assertEqual(runtime_config.site.base_url, "/custom")
        self.assertEqual(runtime_config.site.url_style, "file")


if __name__ == "__main__":
    unittest.main()
