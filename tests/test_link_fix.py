import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.audit import collect_broken_links, lint_broken_links
from wiki.config import Config
from wiki.link_fix import (
    apply_broken_link_fixes,
    find_broken_link_fixes,
    remaining_broken_links,
)


class TestLinkFix(unittest.TestCase):
    def test_fixes_typo_slug_with_unique_fuzzy_match(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            (Path(tmpdir) / "target-page.md").write_text("content", encoding="utf-8")
            source = Path(tmpdir) / "source-page.md"
            source.write_text("See [[target-pag]] for details.\n", encoding="utf-8")

            fixes = find_broken_link_fixes(config)
            self.assertEqual(len(fixes), 1)
            self.assertEqual(fixes[0].replacement_target, "target-page")

            apply_broken_link_fixes(config, fixes, dry_run=False)
            self.assertIn("[[target-page]]", source.read_text(encoding="utf-8"))
            self.assertEqual(lint_broken_links(config), [])

    def test_link_renames_take_precedence(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(
                wiki={"input": [tmpdir]},
                link={"renames": {"Old_Name": "New_Name"}},
            )
            (Path(tmpdir) / "New_Name.md").write_text("content", encoding="utf-8")
            source = Path(tmpdir) / "source-page.md"
            source.write_text("See [[Old_Name]].\n", encoding="utf-8")

            fixes = find_broken_link_fixes(config)
            self.assertEqual(len(fixes), 1)
            self.assertEqual(fixes[0].replacement_target, "New_Name")

    def test_skips_ambiguous_fuzzy_matches(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            (Path(tmpdir) / "ab-page.md").write_text("a", encoding="utf-8")
            (Path(tmpdir) / "ac-page.md").write_text("b", encoding="utf-8")
            Path(tmpdir, "source-page.md").write_text("See [[a-page]].\n", encoding="utf-8")

            self.assertEqual(find_broken_link_fixes(config), [])

    def test_remaining_broken_links_after_virtual_fix(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            (Path(tmpdir) / "target-page.md").write_text("content", encoding="utf-8")
            Path(tmpdir, "source-page.md").write_text(
                "Broken [[target-pag]] and [[missing-page]].\n",
                encoding="utf-8",
            )

            fixes = find_broken_link_fixes(config)
            remaining = remaining_broken_links(config, fixes=fixes)
            self.assertEqual(len(collect_broken_links(config)), 2)
            self.assertEqual(len(remaining), 1)
            self.assertIn("missing-page", remaining[0].raw_target)


if __name__ == "__main__":
    unittest.main()
