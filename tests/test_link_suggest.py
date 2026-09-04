import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.audit import lint_broken_links
from wiki.config import Config
from wiki.link_suggest import apply_link_opportunities, find_link_opportunities


class TestLinkSuggest(unittest.TestCase):
    def test_finds_plain_text_mention_of_another_page(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "wiki.md").write_text("# Wiki CLI\n", encoding="utf-8")
            (wiki / "Getting_Started.md").write_text(
                "# Getting started\n\nRead the Wiki CLI guide before you begin.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            opportunities = find_link_opportunities(config)

            self.assertEqual(len(opportunities), 1)
            item = opportunities[0]
            self.assertEqual(item.source_route, "Getting_Started")
            self.assertEqual(item.target_route, "wiki")
            self.assertEqual(item.matched_text, "Wiki CLI")

    def test_skips_existing_wikilinks_and_code(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "wiki.md").write_text("# Wiki CLI\n", encoding="utf-8")
            (wiki / "Guide.md").write_text(
                "# Guide\n\nAlready linked [[Wiki_CLI]] and literal `Wiki CLI` in code.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            opportunities = find_link_opportunities(config)

            self.assertEqual(opportunities, [])

    def test_skips_short_single_word_acronyms(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "HTML.md").write_text("# HTML\n", encoding="utf-8")
            (wiki / "Guide.md").write_text(
                "# Guide\n\nPages are served as HTML documents.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            opportunities = find_link_opportunities(config)

            self.assertEqual(opportunities, [])

    def test_prefers_longest_alias_match(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Wiki.md").write_text("# Wiki\n", encoding="utf-8")
            (wiki / "Wiki_CLI.md").write_text("# Wiki CLI\n", encoding="utf-8")
            (wiki / "Guide.md").write_text(
                "# Guide\n\nInstall the Wiki CLI first.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            opportunities = find_link_opportunities(config)

            self.assertEqual(len(opportunities), 1)
            self.assertEqual(opportunities[0].target_route, "Wiki_CLI")
            self.assertEqual(opportunities[0].matched_text, "Wiki CLI")

    def test_apply_inserts_markdown_links_by_default(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "wiki.md").write_text("# Wiki CLI\n", encoding="utf-8")
            guide = wiki / "Getting_Started.md"
            guide.write_text(
                "# Getting started\n\nRead the Wiki CLI guide before you begin.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            opportunities = find_link_opportunities(config)
            changed = apply_link_opportunities(config, opportunities, dry_run=False)

            self.assertEqual(changed, [guide])
            self.assertIn("[Wiki CLI](wiki.md)", guide.read_text(encoding="utf-8"))
            self.assertEqual(find_link_opportunities(config), [])
            self.assertEqual(lint_broken_links(config), [])

    def test_apply_respects_frontmatter(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "wiki.md").write_text("# Wiki CLI\n", encoding="utf-8")
            page = wiki / "Guide.md"
            page.write_text(
                "---\ntype: TechArticle\n---\n\nInstall the Wiki CLI first.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            apply_link_opportunities(config, find_link_opportunities(config), dry_run=False)

            content = page.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\ntype: TechArticle\n---\n\n"))
            self.assertIn("[Wiki CLI](wiki.md)", content)

    def test_apply_uses_wikilinks_when_link_style_configured(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "wiki.md").write_text("# Wiki CLI\n", encoding="utf-8")
            guide = wiki / "Getting_Started.md"
            guide.write_text(
                "# Getting started\n\nRead the Wiki CLI guide before you begin.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, link={"style": "wikilink"}, config_root=root)

            opportunities = find_link_opportunities(config)
            apply_link_opportunities(config, opportunities, dry_run=False)

            self.assertIn("[[wiki|Wiki CLI]]", guide.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
