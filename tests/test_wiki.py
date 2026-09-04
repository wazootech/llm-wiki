"""Tests for Wiki session API."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wiki.config import Config
from wiki.schemas import AuditReport, Issue
from wiki.wiki import Wiki, _uses_named_graphs


class TestNamedGraphDetection(unittest.TestCase):
    def test_detects_graph_clause(self) -> None:
        self.assertTrue(_uses_named_graphs("SELECT ?s WHERE { GRAPH ?g { ?s ?p ?o } }"))

    def test_ignores_graph_substrings(self) -> None:
        self.assertFalse(_uses_named_graphs("SELECT ?graph WHERE { ?s ?p ?graph }"))
        self.assertFalse(_uses_named_graphs("SELECT ?graphCount WHERE { ?s ?p ?graphCount }"))
        self.assertFalse(_uses_named_graphs("SELECT ?s WHERE { ?s ?p <https://example.org/graphs/root> }"))


class TestWiki(unittest.TestCase):
    def test_load_and_check_whole_wiki(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            (wiki_dir / "Page.md").write_text("# Page\n\nContent.", encoding="utf-8")
            (root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")

            wiki = Wiki.load(root)
            with patch("wiki.wiki._run_check", return_value=AuditReport.empty()) as mock_check:
                report = wiki.check()
            self.assertTrue(report.ok)
            mock_check.assert_called_once()

    def test_file_scoped_check_passes_file_paths(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            page = wiki_dir / "Page.md"
            page.write_text("---\ntype: schema:WebPage\n---\n", encoding="utf-8")
            (root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")

            wiki = Wiki.load(root)
            with patch("wiki.wiki._run_check", return_value=AuditReport.empty()) as mock_check:
                wiki.check([page])
            _, kwargs = mock_check.call_args
            self.assertIsNotNone(kwargs.get("file_paths"))

    def test_with_runtime_overrides_site(self) -> None:
        config = Config(wiki={"input": [Path("/tmp/wiki")]}, site={"base_url": "/wiki"})
        wiki = Wiki(config)
        runtime = wiki.with_runtime(base_url="/custom", url_style="file")
        self.assertEqual(runtime.config.site.base_url, "/custom")
        self.assertEqual(runtime.config.site.url_style, "file")
        self.assertEqual(wiki.config.site.base_url, "/wiki")

    def test_preflight_merges_lint_and_check(self) -> None:
        config = Config(wiki={"input": [Path("/tmp/wiki")]})
        wiki = Wiki(config)
        lint_report = AuditReport(
            warnings=[Issue(code="headings", message="warn", severity="warning")],
        )
        check_report = AuditReport(
            errors=[Issue(code="shacl_violation", message="fail", severity="error")],
            ok=False,
        )
        with patch("wiki.wiki._run_lint", return_value=lint_report), patch(
            "wiki.wiki._run_check",
            return_value=check_report,
        ):
            report = wiki.preflight()
        self.assertFalse(report.ok)
        self.assertEqual(len(report.errors), 1)
        self.assertEqual(len(report.warnings), 1)
