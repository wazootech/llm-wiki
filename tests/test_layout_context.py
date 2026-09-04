"""Tests for nested layout template context."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from markupsafe import Markup

from wiki.config import Config
from wiki.site import build_site
from wiki.site.layout_context import LAYOUT_CONTEXT_MARKUP_PATHS, build_layout_context


class TestLayoutContext(unittest.TestCase):
    def test_index_context_shape(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text("# Page\n", encoding="utf-8")

            context = build_layout_context(
                base_url="/wiki",
                content="<ul></ul>",
            )

            self.assertIn("site", context)
            self.assertIn("page", context)
            self.assertIn("body", context)
            self.assertEqual(context["site"]["base_url"], "/wiki")
            self.assertEqual(context["page"]["title"], "All Pages")
            self.assertIsInstance(context["body"], Markup)

    def test_article_context_includes_slug(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Bob.md").write_text("# Bob\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]

            context = build_layout_context(
                base_url="/wiki",
                page=page,
                content=page.html,
            )

            self.assertEqual(context["page"]["title"], "Bob")
            self.assertEqual(context["body"], page.html)

    def test_markup_paths_include_content(self) -> None:
        self.assertIn(("body",), LAYOUT_CONTEXT_MARKUP_PATHS)


if __name__ == "__main__":
    unittest.main()
