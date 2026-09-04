import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import mdformat
from click.testing import CliRunner

from layout_helpers import write_layout
from wiki.cli import main
from wiki.config import Config
from wiki.fmt_util import (
    _resolve_fmt_toml_opts,
    describe_fmt_source,
    format_markdown,
)
from wiki.site import build_page_html, build_site


class TestWikiFmt(unittest.TestCase):
    def test_mdformat_preserves_wikilinks(self) -> None:
        """Test that mdformat with our plugin preserves Obsidian-style wikilinks."""
        # Simple wikilink
        content = "See [[Wiki_CLI]] for details."
        formatted = mdformat.text(content, extensions=["wikilink", "front_matters", "gfm", "toc", "footnote"])
        self.assertEqual(formatted.strip(), "See [[Wiki_CLI]] for details.")

        # Wikilink with alias/display name
        content_alias = "See [[Wiki_CLI|the CLI]] for details."
        formatted_alias = mdformat.text(content_alias, extensions=["wikilink", "front_matters", "gfm", "toc", "footnote"])
        self.assertEqual(formatted_alias.strip(), "See [[Wiki_CLI|the CLI]] for details.")

    def test_mdformat_aligns_tables(self) -> None:
        """Test that mdformat aligns and pads markdown tables with spaces."""
        unaligned = "| LongHeader | Short |\n|---|---|\n| cell | verylongcell |\n"
        expected = "| LongHeader | Short        |\n| ---------- | ------------ |\n| cell       | verylongcell |\n"
        formatted = mdformat.text(unaligned, extensions=["wikilink", "front_matters", "gfm", "toc", "footnote"])
        self.assertEqual(formatted, expected)

    def test_cli_fmt_in_place(self) -> None:
        """Test that the wiki fmt command reformats files in place."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            file_path = wiki_dir / "unformatted.md"
            # Write unformatted markdown (extra spacing and unformatted headers)
            file_path.write_text(
                "---\ntype: schema:WebPage\nname: Test\n---\n\n# Header\n\nSome text  \nwith extra spaces.\n",
                encoding="utf-8"
            )

            result = runner.invoke(main, ["--input", str(wiki_dir), "fmt", "-v"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Formatted unformatted.md", result.output)

            # Check that the file was indeed formatted (extra trailing spaces stripped)
            formatted_content = file_path.read_text(encoding="utf-8")
            self.assertNotIn("Some text  \n", formatted_content)

    def test_cli_fmt_check(self) -> None:
        """Test that wiki fmt --check flags unformatted files and passes on formatted ones."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            file_path = wiki_dir / "unformatted.md"
            file_path.write_text(
                "---\ntype: schema:WebPage\nname: Test\n---\n\n# Header\n\nSome text  \n",
                encoding="utf-8"
            )

            # 1. Run with --check: should fail since it's not formatted
            result_stale = runner.invoke(main, ["--input", str(wiki_dir), "fmt", "--check", "-v"])
            self.assertEqual(result_stale.exit_code, 1)
            self.assertIn("Error: The following files are not correctly formatted:", result_stale.output)
            self.assertIn("unformatted.md", result_stale.output)

            # File should be unmodified
            self.assertEqual(file_path.read_text(encoding="utf-8"), "---\ntype: schema:WebPage\nname: Test\n---\n\n# Header\n\nSome text  \n")

            # 2. Run without --check to format it
            runner.invoke(main, ["--input", str(wiki_dir), "fmt"])

            # 3. Run with --check again: should succeed
            result_clean = runner.invoke(main, ["--input", str(wiki_dir), "fmt", "--check", "-v"])
            self.assertEqual(result_clean.exit_code, 0)
            self.assertIn("All files are correctly formatted.", result_clean.output)

    def test_fmt_preserves_sparql_render_blocks(self) -> None:
        compact_table = "| class |\n| --- |\n| owl:Class |\n"
        original = (
            "<!-- sparql:start -->\n"
            "```sparql\nSELECT ?class WHERE { ?class a owl:Class }\n```\n"
            f"{compact_table}"
            "<!-- sparql:end -->\n"
        )
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "Query.md"
            file_path.write_text(original, encoding="utf-8")
            formatted = format_markdown(original, file_path, Config(config_root=Path(tmpdir)))
            self.assertIn("| class |", formatted)
            self.assertNotIn("| Class |", formatted)
            self.assertIn("```sparql", formatted)

    def test_fmt_preserves_hidden_sparql_render_blocks(self) -> None:
        compact_table = "| class |\n| --- |\n| owl:Class |\n"
        original = (
            "<!-- sparql:start\n"
            "```sparql\nSELECT ?class WHERE { ?class a owl:Class }\n```\n"
            "-->\n"
            f"{compact_table}"
            "<!-- sparql:end -->\n"
        )
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "Query.md"
            file_path.write_text(original, encoding="utf-8")
            formatted = format_markdown(original, file_path, Config(config_root=Path(tmpdir)))
            self.assertIn("| class |", formatted)
            self.assertNotIn("| Class |", formatted)
            self.assertIn("<!-- sparql:start\n", formatted)
            self.assertIn("```sparql", formatted)
            self.assertIn("-->\n", formatted)

    def test_read_view_uses_page_content_slot(self) -> None:
        seed_template = '<html><body><article id="article-top">%wiki.body%</article></body></html>'
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text(
                "---\ntype: TechArticle\nname: Catalog page\n---\n\n# Shelf layout\n\nBody.",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            html = build_page_html(page, root, default_layout=write_layout(root, "layouts/fmt.html", seed_template))
            self.assertIn('id="shelf-layout">Shelf layout</h1>', page.html)
            self.assertIn("Body.", html)

    def test_fmt_resolution_inline_beats_default_toml(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".mdformat.toml").write_text('wrap = "keep"\n', encoding="utf-8")
            file_path = root / "page.md"
            file_path.write_text("# Title\n", encoding="utf-8")
            config = Config(
                config_root=root,
                fmt={"wrap": "no", "extensions": ["gfm", "front_matters", "wikilink"]},
            )
            self.assertEqual(describe_fmt_source(file_path, config), "inline fmt in wiki config")

    def test_fmt_resolution_missing_pointer_falls_back_to_default_toml(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".mdformat.toml").write_text(
                'wrap = "no"\nextensions = ["gfm", "front_matters", "wikilink"]\n',
                encoding="utf-8",
            )
            file_path = root / "page.md"
            file_path.write_text("# Title\n", encoding="utf-8")
            config = Config(config_root=root, fmt=root / "missing.toml")
            self.assertEqual(describe_fmt_source(file_path, config), ".mdformat.toml at config root")

    def test_fmt_resolution_pointer_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            custom = root / "custom.toml"
            custom.write_text(
                'wrap = "no"\nextensions = ["gfm", "front_matters", "wikilink"]\n',
                encoding="utf-8",
            )
            file_path = root / "page.md"
            file_path.write_text("# Title\n", encoding="utf-8")
            config = Config(config_root=root, fmt=custom)
            self.assertEqual(describe_fmt_source(file_path, config), "fmt from custom.toml")

    def test_fmt_invalid_toml_at_pointer_raises(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bad = root / "bad.toml"
            bad.write_text('wrap = "no"\n[broken\n', encoding="utf-8")
            file_path = root / "page.md"
            file_path.write_text("# Title\n", encoding="utf-8")
            config = Config(config_root=root, fmt=bad)
            with self.assertRaisesRegex(ValueError, "Invalid TOML syntax"):
                format_markdown("# Title\n", file_path, config)

    def test_fmt_invalid_toml_at_default_raises(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".mdformat.toml").write_text("[broken\n", encoding="utf-8")
            file_path = root / "page.md"
            file_path.write_text("# Title\n", encoding="utf-8")
            config = Config(config_root=root)
            with self.assertRaisesRegex(ValueError, "Invalid TOML syntax"):
                format_markdown("# Title\n", file_path, config)

    def test_fmt_resolution_upward_walk(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            nested = wiki / "sub"
            nested.mkdir(parents=True)
            toml_path = wiki / ".mdformat.toml"
            toml_path.write_text(
                'wrap = "no"\nextensions = ["gfm", "front_matters", "wikilink"]\n',
                encoding="utf-8",
            )
            file_path = nested / "page.md"
            file_path.write_text("# Title\n", encoding="utf-8")
            config = Config(config_root=root, wiki={"input": [wiki]})
            source = describe_fmt_source(file_path, config)
            self.assertIn(".mdformat.toml", source)
            self.assertIn("wiki", source.replace("\\", "/"))

    def test_fmt_pointer_mode_uses_mdformat_toml(self) -> None:
        toml = (
            'wrap = "no"\n'
            'end_of_line = "lf"\n'
            'extensions = ["gfm", "front_matters", "wikilink"]\n'
        )
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".mdformat.toml").write_text(toml, encoding="utf-8")
            (root / "wiki.yaml").write_text(
                "wiki:\n  input: [wiki]\nfmt: .mdformat.toml\n",
                encoding="utf-8",
            )
            file_path = root / "wiki" / "page.md"
            file_path.parent.mkdir(parents=True)
            file_path.write_text("# Title\n\nSome text  \n", encoding="utf-8")
            config = Config.load(root)
            self.assertEqual(describe_fmt_source(file_path, config), "fmt from .mdformat.toml")
            formatted = format_markdown(file_path.read_text(encoding="utf-8"), file_path, config)
            self.assertNotIn("Some text  \n", formatted)

    def test_fmt_omit_key_uses_default_mdformat_toml(self) -> None:
        toml = (
            'wrap = "no"\n'
            'end_of_line = "lf"\n'
            'extensions = ["gfm", "front_matters", "wikilink"]\n'
        )
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".mdformat.toml").write_text(toml, encoding="utf-8")
            (root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")
            file_path = root / "wiki" / "page.md"
            file_path.parent.mkdir(parents=True)
            file_path.write_text("# Title\n\nSome text  \n", encoding="utf-8")
            config = Config.load(root)
            self.assertEqual(describe_fmt_source(file_path, config), ".mdformat.toml at config root")
            formatted = format_markdown(file_path.read_text(encoding="utf-8"), file_path, config)
            self.assertNotIn("Some text  \n", formatted)

    def test_fmt_inline_pointer_and_omit_match(self) -> None:
        toml = (
            'wrap = "no"\n'
            'end_of_line = "lf"\n'
            'extensions = ["gfm", "front_matters", "wikilink"]\n'
        )
        original = "# Title\n\nSome text  \n"
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "page.md"
            file_path.write_text(original, encoding="utf-8")

            inline_cfg = Config(
                config_root=root,
                fmt={
                    "wrap": "no",
                    "end_of_line": "lf",
                    "extensions": ["gfm", "front_matters", "wikilink"],
                },
            )
            inline_out = format_markdown(original, file_path, inline_cfg)

            pointer_root = root / "pointer"
            pointer_root.mkdir()
            (pointer_root / ".mdformat.toml").write_text(toml, encoding="utf-8")
            (pointer_root / "wiki.yaml").write_text(
                "wiki:\n  input: [wiki]\nfmt: .mdformat.toml\n",
                encoding="utf-8",
            )
            pointer_cfg = Config.load(pointer_root)
            pointer_out = format_markdown(original, file_path, pointer_cfg)

            omit_root = root / "omit"
            omit_root.mkdir()
            (omit_root / ".mdformat.toml").write_text(toml, encoding="utf-8")
            (omit_root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")
            omit_cfg = Config.load(omit_root)
            omit_out = format_markdown(original, file_path, omit_cfg)

            self.assertEqual(inline_out, pointer_out)
            self.assertEqual(inline_out, omit_out)

    def test_fmt_yaml_no_wrap_normalizes_to_string(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                "wiki:\n  input: [wiki]\nfmt:\n  wrap: no\n  end_of_line: lf\n"
                '  extensions: ["gfm", "front_matters", "wikilink"]\n',
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertEqual(config.fmt.options["wrap"], "no")

    def test_fmt_absent_uses_wiki_cli_defaults(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")
            file_path = root / "page.md"
            original = "# Title\n\nSome text  \n"
            file_path.write_text(original, encoding="utf-8")
            config = Config.load(root)
            self.assertEqual(describe_fmt_source(file_path, config), "Wiki CLI fmt defaults")
            formatted = format_markdown(original, file_path, config)
            self.assertNotIn("Some text  \n", formatted)
            opts, _ = _resolve_fmt_toml_opts(file_path, config)
            self.assertEqual(opts.get("wrap"), "no")

    def test_fmt_empty_inline_merges_defaults(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            file_path = root / "page.md"
            original = "# Title\n\nSome text  \n"
            file_path.write_text(original, encoding="utf-8")
            (root / "wiki.yaml").write_text("wiki:\n  input: [wiki]\n", encoding="utf-8")
            absent_config = Config.load(root)
            empty_config = Config(config_root=root, fmt={})
            absent_out = format_markdown(original, file_path, absent_config)
            empty_out = format_markdown(original, file_path, empty_config)
            self.assertEqual(absent_out, empty_out)
            self.assertEqual(describe_fmt_source(file_path, empty_config), "inline fmt in wiki config")


if __name__ == "__main__":
    unittest.main()
