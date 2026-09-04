"""Smoke tests for library-first Wiki session methods."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki import Wiki


class TestLibraryOps(unittest.TestCase):
    def _scaffold(self) -> tuple[Path, Path, Wiki]:
        tmpdir = TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        root = Path(tmpdir.name)
        wiki_dir = root / "wiki"
        wiki_dir.mkdir()
        (root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")
        page = wiki_dir / "Page.md"
        page.write_text(
            "---\ntype: schema:WebPage\nname: Page\n---\n\n# Page\n\nContent.\n",
            encoding="utf-8",
        )
        return root, page, Wiki.load(root)

    def test_wiki_build_writes_site(self) -> None:
        root, _, wiki = self._scaffold()
        output_dir = root / "_site"
        result = wiki.build(output_dir, no_check=True)
        self.assertTrue(result.ok, result.error_message)
        self.assertGreater(result.page_count, 0)
        self.assertTrue((output_dir / "wiki" / "Page" / "index.html").exists())

    def test_wiki_format_check_only(self) -> None:
        _, _, wiki = self._scaffold()
        report = wiki.format(check=True)
        self.assertTrue(report.ok)
        self.assertEqual(report.formatted_count, 0)

    def test_wiki_export_turtle(self) -> None:
        _, page, wiki = self._scaffold()
        result = wiki.export([page], format="turtle", mode="expanded")
        self.assertTrue(result.ok, result.error_message)
        self.assertTrue(result.output.strip())

    def test_wiki_render_check_only(self) -> None:
        _, _, wiki = self._scaffold()
        report = wiki.render(check=True)
        self.assertTrue(report.ok)
        self.assertEqual(report.updated_count, 0)

    def test_wiki_method_defaults_without_files(self) -> None:
        _, _, wiki = self._scaffold()

        # Test wiki.format with defaults
        report_fmt = wiki.format(check=True)
        self.assertTrue(report_fmt.ok)

        # Test wiki.render with defaults
        report_render = wiki.render(check=True)
        self.assertTrue(report_render.ok)

        # Test wiki.export with defaults
        report_export = wiki.export(format="turtle", mode="expanded")
        self.assertTrue(report_export.ok)

        # Test wiki.link with defaults
        report_link = wiki.link()
        self.assertTrue(report_link.ok)

    def test_wiki_instance_methods(self) -> None:
        root, _, wiki = self._scaffold()

        # Test wiki.build
        output_dir = root / "_site_instance"
        build_res = wiki.build(output_dir, no_check=True)
        self.assertTrue(build_res.ok)

        # Test wiki.format
        report_fmt = wiki.format(check=True)
        self.assertTrue(report_fmt.ok)

        # Test wiki.render
        report_render = wiki.render(check=True)
        self.assertTrue(report_render.ok)

        # Test wiki.export
        report_export = wiki.export(format="turtle", mode="expanded")
        self.assertTrue(report_export.ok)

        # Test wiki.link
        report_link = wiki.link()
        self.assertTrue(report_link.ok)

        # Test wiki.query
        query_res = wiki.query("SELECT ?s WHERE { ?s ?p ?o }")
        self.assertTrue(query_res.strip())
