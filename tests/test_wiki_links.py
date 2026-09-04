import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.config import Config
from wiki.site import build_site
from wiki.wiki_links import LinkIndex


class TestVaultLinks(unittest.TestCase):
    def _config(self, root: Path, wiki: Path) -> Config:
        return Config(wiki={"input": [wiki]}, config_root=root)

    def test_wikilink_backlink(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Alpha.md").write_text("# Alpha\n\nSee [[Beta]].", encoding="utf-8")
            (wiki / "Beta.md").write_text("# Beta\n\nContent.", encoding="utf-8")
            config = self._config(root, wiki)

            index = LinkIndex.from_config(config)
            self.assertEqual(index.backlinks_to("Beta"), ["Alpha"])

    def test_markdown_link_backlink(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Alpha.md").write_text("# Alpha\n\nSee [Beta](Beta.md).", encoding="utf-8")
            (wiki / "Beta.md").write_text("# Beta\n\nContent.", encoding="utf-8")
            config = self._config(root, wiki)

            index = LinkIndex.from_config(config)
            self.assertEqual(index.backlinks_to("Beta"), ["Alpha"])

    def test_asset_link_not_counted_as_backlink(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            assets = root / "assets"
            wiki.mkdir()
            assets.mkdir()
            (wiki / "Page.md").write_text("# Page\n\n![img](../assets/logo.png)", encoding="utf-8")
            config = self._config(root, wiki)

            index = LinkIndex.from_config(config)
            self.assertEqual(index.backlinks_to("logo"), [])

    def test_broken_links_delegates_to_index(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Page.md").write_text("# Page\n\n[[Missing]].", encoding="utf-8")
            config = self._config(root, wiki)

            issues = LinkIndex.from_config(config).broken_links()
            self.assertTrue(any(issue.issue_kind == "missing_document" for issue in issues))

    def test_build_site_uses_link_index_for_markdown_backlinks(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Alpha.md").write_text("# Alpha\n\n[Beta](Beta.md)", encoding="utf-8")
            (wiki / "Beta.md").write_text("# Beta\n\nBody", encoding="utf-8")
            config = self._config(root, wiki)

            site = build_site(config, base_url="/wiki", url_style="dir")
            beta = next(page for page in site.pages if page.file_slug == "Beta")
            self.assertEqual(beta.backlink_slugs, ["Alpha"])


if __name__ == "__main__":
    unittest.main()
