import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.audit import lint_heading_levels
from wiki.config import Config
from wiki.headings import parse_headings
from wiki.site import render_wiki_markdown
from wiki.site.markdown import extract_outline
from wiki.wiki_links import _heading_ids


class TestHeadings(unittest.TestCase):
    def test_parse_headings_collapses_duplicate_slugs(self) -> None:
        headings = parse_headings("# Title\n\n## Early Life\n\n## Early Life\n")

        self.assertEqual([heading.slug for heading in headings], ["title", "early-life", "early-life-1"])

    def test_shared_heading_parse_handles_inline_markup(self) -> None:
        markdown = (
            "# Page\n\n"
            "## Request headers\n\n"
            "### `Accept`\n\n"
            "## Importance in the [[Semantic_Web|semantic web]]\n"
        )

        headings = parse_headings(markdown)

        self.assertEqual(
            [heading.text for heading in headings],
            [
                "Page",
                "Request headers",
                "`Accept`",
                "Importance in the [[Semantic_Web|semantic web]]",
            ],
        )
        self.assertEqual(
            [item.slug for item in extract_outline(markdown)],
            [heading.slug for heading in headings if heading.level >= 2],
        )
        self.assertEqual(_heading_ids(markdown), {heading.slug for heading in headings})

        html = render_wiki_markdown(markdown)
        for heading in headings:
            self.assertIn(f'id="{heading.slug}"', html)

    def test_lint_heading_levels_uses_shared_heading_parse(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "Page.md").write_text(
                "---\ntype: TechArticle\n---\n# A\n\n### C\n",
                encoding="utf-8",
            )

            config = Config(wiki={"input": [wiki_dir]})
            warnings = lint_heading_levels(config)

            self.assertEqual(len(warnings), 1)
            self.assertIn("skips level h2", warnings[0])
