"""Tests for AuditReport and stable Issue codes."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.audit import _run_lint as run_lint
from wiki.config import Config
from wiki.schemas import AuditReport, Issue


class TestAuditReports(unittest.TestCase):
    def test_audit_report_merge(self) -> None:
        first = AuditReport(
            errors=[Issue(code="broken_links", message="broken", severity="error")],
            ok=False,
        )
        second = AuditReport(
            warnings=[Issue(code="headings", message="heading", severity="warning")],
        )
        merged = first.merge(second)
        self.assertFalse(merged.ok)
        self.assertEqual(len(merged.errors), 1)
        self.assertEqual(len(merged.warnings), 1)
        self.assertEqual(merged.errors[0].code, "broken_links")

    def test_run_lint_issue_codes_match_rule_keys(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "Page.md").write_text("---\ntype: schema:WebPage\n---\n\n[[Missing]]", encoding="utf-8")
            (wiki_dir / "Wikilink_Page.md").write_text(
                "---\ntype: schema:WebPage\n---\n\nSee [[Other]].",
                encoding="utf-8",
            )
            config = Config(
                wiki={"input": [wiki_dir]},
                lint={"broken_links": "error", "link_style": "error"},
                link={"style": "standard"},
            )
            report = run_lint(config)
            codes = {issue.code for issue in report.errors}
            self.assertIn("broken_links", codes)

    def test_apply_strict_promotes_warnings(self) -> None:
        report = AuditReport(
            warnings=[Issue(code="headings", message="warn", severity="warning")],
        )
        strict = report.apply_strict()
        self.assertFalse(strict.ok)
        self.assertEqual(len(strict.errors), 1)
        self.assertEqual(strict.warnings, [])
