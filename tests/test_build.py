import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from click.testing import CliRunner

from layout_helpers import write_layout
from wiki.cli import main
from wiki.config import Config
from wiki.paths import page_output_path
from wiki.schemas import AuditReport
from wiki.wiki import Wiki


class TestWikiBuild(unittest.TestCase):
    def test_build_copies_configured_assets(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            assets = root / "assets" / "items"
            wiki.mkdir()
            assets.mkdir(parents=True)
            (root / "wiki.yaml").write_text("wiki:\n  inputs: [wiki]\n  assets: [assets]\n", encoding="utf-8")
            (wiki / "Item.md").write_text("# Item\n\n![label](../assets/items/label.jpg)", encoding="utf-8")
            (assets / "label.jpg").write_text("image", encoding="utf-8")
            output_dir = root / "_site"

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue((output_dir / "wiki" / "Item" / "index.html").exists())
            self.assertEqual((output_dir / "wiki" / "assets" / "items" / "label.jpg").read_text(encoding="utf-8"), "image")

    def test_build_runs_check_before_cleaning_output(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            owned = output_dir / "wiki"
            wiki.mkdir()
            owned.mkdir(parents=True)
            (owned / "old.html").write_text("old", encoding="utf-8")
            (root / "wiki.yaml").write_text("wiki:\n  inputs: [wiki]\nlint:\n  broken_links: error\n", encoding="utf-8")
            (wiki / "Page.md").write_text("# Page\n\n[[Missing]]", encoding="utf-8")

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 1)
            self.assertEqual((owned / "old.html").read_text(encoding="utf-8"), "old")

    def test_build_no_check_skips_configurable_checks_but_cleans_output(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            owned = output_dir / "wiki"
            wiki.mkdir()
            owned.mkdir(parents=True)
            (owned / "old.html").write_text("old", encoding="utf-8")
            (root / "wiki.yaml").write_text("wiki:\n  inputs: [wiki]\nlint:\n  broken_links: error\n", encoding="utf-8")
            (wiki / "Page.md").write_text("# Page\n\n[[Missing]]", encoding="utf-8")

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir), "--no-check"])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertFalse((owned / "old.html").exists())
            self.assertTrue((owned / "Page" / "index.html").exists())

    def test_root_index_md_replaces_generated_index(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            wiki.mkdir()
            (root / "wiki.yaml").write_text("wiki:\n  inputs: [wiki]\n", encoding="utf-8")
            (wiki / "index.md").write_text("# Custom Home\n\nWelcome.", encoding="utf-8")
            (wiki / "Page.md").write_text("# Page", encoding="utf-8")

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 0, result.output)
            index_content = (output_dir / "wiki" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Custom Home", index_content)
            self.assertNotIn("All Pages", index_content)

    def test_build_writes_pages_for_yaml_documents(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            wiki.mkdir()
            (root / "wiki.yaml").write_text("wiki:\n  inputs: [wiki]\n", encoding="utf-8")
            (wiki / "person.yaml").write_text("type: Person\nname: Gregory Davidson\n", encoding="utf-8")
            (wiki / "place.yml").write_text("type: Place\nname: Princeton\n", encoding="utf-8")

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertTrue((output_dir / "wiki" / "person" / "index.html").exists())
            self.assertTrue((output_dir / "wiki" / "place" / "index.html").exists())

    def test_build_uses_canonical_page_output_paths(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (root / "wiki.yaml").write_text("wiki:\n  inputs: [wiki]\n", encoding="utf-8")
            (wiki / "Page.md").write_text("# Page\n\nContent.", encoding="utf-8")

            for url_style in ("dir", "file"):
                with self.subTest(url_style=url_style):
                    output_dir = root / f"_site_{url_style}"
                    result = runner.invoke(
                        main,
                        [
                            "--config",
                            str(root),
                            "build",
                            "--output-dir",
                            str(output_dir),
                            "--site-url-style",
                            url_style,
                            "--no-check",
                        ],
                    )

                    self.assertEqual(result.exit_code, 0, result.output)
                    expected_path = page_output_path(output_dir / "wiki", "Page", url_style)
                    self.assertTrue(expected_path.exists())
                    self.assertIn("Content.", expected_path.read_text(encoding="utf-8"))

    def test_build_does_not_mutate_loaded_config_site_overrides(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Page.md").write_text("# Page\n\nContent.", encoding="utf-8")
            config = Config(wiki={"inputs": [wiki]}, site={"base_url": "/wiki", "url_style": "dir"}, config_root=root)

            with patch("wiki.cli.Wiki.load") as load_mock:
                load_mock.return_value = Wiki(config)
                with patch(
                    "wiki.wiki._run_lint",
                    return_value=AuditReport.empty(),
                ) as run_lint_mock, patch(
                    "wiki.wiki._run_check",
                    return_value=AuditReport.empty(),
                ) as run_check_mock:
                    result = runner.invoke(
                        main,
                        [
                            "--config",
                            str(root),
                            "build",
                            "--output-dir",
                            str(root / "_site"),
                            "--site-base-url",
                            "/custom",
                            "--site-url-style",
                            "file",
                        ],
                    )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(config.site.base_url, "/wiki")
            self.assertEqual(config.site.url_style, "dir")
            self.assertEqual(run_lint_mock.call_args[0][0].site.base_url, "/custom")
            self.assertEqual(run_lint_mock.call_args[0][0].site.url_style, "file")
            self.assertEqual(run_check_mock.call_args[0][0].site.base_url, "/custom")
            self.assertEqual(run_check_mock.call_args[0][0].site.url_style, "file")

    def test_build_leaves_removed_infobox_slot_literal(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            wiki.mkdir()
            test_template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
%wiki.head%
</head>
<body>
%wiki.nav.infobox%
%wiki.body%
</body>
</html>"""
            (root / "wiki.yaml").write_text(
                "wiki:\n  inputs: [wiki]\nsite:\n  layout: test_shell.html\n", encoding="utf-8"
            )
            write_layout(root, "test_shell.html", test_template)
            (wiki / "Gregory_Davidson.yaml").write_text(
                """id: wiki:Gregory_Davidson
type: schema:Person
givenName: Gregory
familyName: Davidson
knows: wiki:Ethan_Davidson
owns: wiki:Bella_Davidson
url: https://example.com/gregory-davidson
""",
                encoding="utf-8",
            )
            (wiki / "Ethan_Davidson.yaml").write_text(
                """id: wiki:Ethan_Davidson
type: schema:Person
givenName: Ethan
familyName: Davidson
""",
                encoding="utf-8",
            )
            (wiki / "Bella_Davidson.yaml").write_text(
                """id: wiki:Bella_Davidson
type: schema:Thing
name: Bella Davidson
""",
                encoding="utf-8",
            )

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 0, result.output)
            html = (output_dir / "wiki" / "Gregory_Davidson" / "index.html").read_text(encoding="utf-8")
            self.assertIn("%wiki.nav.infobox%", html)
            self.assertNotIn('class="infobox page-meta"', html)

    def test_build_leaves_removed_metadata_slot_literal(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            wiki.mkdir()
            template = """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"UTF-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">
%wiki.head%
</head>
<body>
%wiki.body%
%wiki.page.metadata.pane%
</body>
</html>"""
            (root / "wiki.yaml").write_text(
                "wiki:\n  inputs: [wiki]\nsite:\n  layout: test_shell.html\n", encoding="utf-8"
            )
            write_layout(root, "test_shell.html", template)
            (wiki / "Page.md").write_text(
                """---
type: Person
givenName: Alice
familyName: Smith
about: wiki:Alice_Theory
---
# Alice
""",
                encoding="utf-8",
            )

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 0, result.output)
            html = (output_dir / "wiki" / "Page" / "index.html").read_text(encoding="utf-8")
            self.assertIn("%wiki.page.metadata.pane%", html)
            self.assertNotIn("metadata-format-heading", html)

    def test_missing_configured_template_falls_back_silently(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            output_dir = root / "_site"
            wiki.mkdir()
            (root / "wiki.yaml").write_text(
                "wiki:\n  inputs: [wiki]\nsite:\n  layout: nonexistent.html\n", encoding="utf-8"
            )
            (wiki / "Page.md").write_text("# Page\n\nContent.", encoding="utf-8")
            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir)])
            self.assertEqual(result.exit_code, 0, result.output)
            html = (output_dir / "wiki" / "Page" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Content.", html)
            self.assertNotIn("<style>", html)

    def test_build_layout_uses_base_url_asset_path(self) -> None:
        runner = CliRunner()
        template = """<!DOCTYPE html>
<html><head>%wiki.head%</head>
<body><img src="%wiki.base_url%/assets/logo.svg" alt=""><span class="logo-text">Acme Docs</span>%wiki.body%</body></html>"""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            assets = root / "assets"
            output_dir = root / "_site"
            wiki.mkdir()
            assets.mkdir()
            (assets / "logo.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>',
                encoding="utf-8",
            )
            (root / "wiki.yaml").write_text(
                "wiki:\n  inputs: [wiki]\n  assets: [assets]\n"
                "site:\n  layout: test_shell.html\n",
                encoding="utf-8",
            )
            write_layout(root, "test_shell.html", template)
            (wiki / "Page.md").write_text("# Page\n\nContent.", encoding="utf-8")

            result = runner.invoke(main, ["--config", str(root), "build", "--output-dir", str(output_dir), "--no-check"])

            self.assertEqual(result.exit_code, 0, result.output)
            html = (output_dir / "wiki" / "Page" / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="/wiki/assets/logo.svg"', html)
            self.assertIn('<span class="logo-text">Acme Docs</span>', html)
            self.assertIn("<title>Page - Wiki CLI</title>", html)
            built_logo = (output_dir / "wiki" / "assets" / "logo.svg").read_text(encoding="utf-8")
            self.assertIn("<text>A</text>", built_logo)


if __name__ == "__main__":
    unittest.main()
