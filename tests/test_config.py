import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from pydantic import ValidationError
from rdflib import Graph, Namespace

from wiki.config import (
    DEFAULT_CHECK_CONFIG,
    DEFAULT_LINT_CONFIG,
    DEFAULT_NAMESPACES,
    Config,
    Context,
)
from wiki.schemas import FmtConfig

MINIMAL_WIKI_YAML = "wiki:\n  input: [wiki]\n"


class TestContext(unittest.TestCase):
    def test_context_default_initialization(self) -> None:
        """Test Context is initialized with default namespaces when none are passed."""
        context = Context()
        self.assertIn("schema", context.namespaces)
        self.assertEqual(context.namespaces["schema"], DEFAULT_NAMESPACES["schema"])

    def test_context_custom_initialization(self) -> None:
        """Test Context correctly registers custom namespace mappings."""
        custom_prefixes = {
            "ex": "http://example.org/",
            "another": Namespace("http://another.org/")
        }
        context = Context(custom_prefixes)
        self.assertIn("ex", context.namespaces)
        self.assertIn("another", context.namespaces)
        self.assertEqual(str(context.namespaces["ex"]), "http://example.org/")
        self.assertEqual(context.namespaces["another"], Namespace("http://another.org/"))

    def test_context_bind_namespaces(self) -> None:
        """Test Context binds registered namespaces to an RDFLib Graph."""
        context = Context({"ex": "http://example.org/"})
        graph = Graph()
        context.bind_namespaces(graph)

        namespaces = dict(graph.namespaces())
        self.assertIn("ex", namespaces)
        self.assertEqual(str(namespaces["ex"]), "http://example.org/")


class TestConfig(unittest.TestCase):
    def test_Config_default_init(self) -> None:
        """Test Config has proper defaults."""
        config = Config()
        self.assertEqual(config.wiki.input, [config.config_root.absolute() / "wiki"])
        self.assertEqual(config.wiki.assets, [])
        self.assertFalse(config.graph.include_file_extension)
        self.assertEqual(config.site.base_url, "/wiki")
        self.assertEqual(config.site.url_style, "dir")
        self.assertIsNone(config.wiki.filename_pattern)
        self.assertEqual(config.check, DEFAULT_CHECK_CONFIG)
        self.assertEqual(config.lint, DEFAULT_LINT_CONFIG)
        self.assertIsNotNone(config.context)
        self.assertFalse(config.sparql_service.enabled)
        self.assertEqual(config.sparql_service.path, "/api/sparql")
        self.assertEqual(config.link.style, "standard")

    def test_Config_load_no_files(self) -> None:
        """Test Config.load falls back to defaults when no files exist."""
        with TemporaryDirectory() as tmpdir:
            config = Config.load(Path(tmpdir))
            self.assertEqual(config.wiki.input, [config.config_root.absolute() / "wiki"])

    def test_Config_load_yaml(self) -> None:
        """Test Config.load correctly parses wiki.yaml."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            yaml_content = {
                "wiki": {
                    "input": "custom_wiki",
                    "assets": ["assets", "media/photos"],
                    "exclude": ["wiki/drafts/**", "assets/private/**"],
                    "filename_pattern": "[A-Za-z0-9_()-]+\\.md",
                },
                "site": {
                    "base_url": "/docs",
                    "url_style": "file",
                },
                "graph": {
                    "context": {
                        "custom_pref": "http://custom-pref.org/"
                    }
                },
                "check": {
                    "missing_layout_file": "error",
                    "frontmatter_schema": "error",
                    "missing_schema_ref": "warning",
                },
                "lint": {
                    "broken_links": "error",
                    "filename_pattern": "error"
                },
                "sparql_service": {"enabled": False, "path": "/sparql"},
            }
            (base_path / "wiki.yaml").write_text(yaml.dump(yaml_content), encoding="utf-8")

            config = Config.load(base_path)
            self.assertEqual(config.wiki.input, [base_path.absolute() / "custom_wiki"])
            self.assertEqual(config.wiki.assets, [base_path.absolute() / "assets", base_path.absolute() / "media/photos"])
            self.assertEqual(config.wiki.exclude, ["wiki/drafts/**", "assets/private/**"])
            self.assertEqual(config.check.missing_layout_file, "error")
            self.assertEqual(config.check.frontmatter_schema, "error")
            self.assertEqual(config.check.missing_schema_ref, "warning")
            self.assertEqual(config.lint.broken_links, "error")
            self.assertEqual(config.lint.filename_pattern, "error")
            self.assertEqual(config.wiki.filename_pattern, "[A-Za-z0-9_()-]+\\.md")
            self.assertEqual(config.site.base_url, "/docs")
            self.assertEqual(config.site.url_style, "file")
            self.assertFalse(config.sparql_service.enabled)
            self.assertEqual(config.sparql_service.path, "/sparql")
            self.assertIn("custom_pref", config.namespaces)

    def test_Config_load_site_block(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "layouts").mkdir()
            (base_path / "layouts" / "custom.html").write_text("<html></html>", encoding="utf-8")
            (base_path / "wiki.yaml").write_text(
                "site:\n  layout: layouts/custom.html\n",
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertEqual(config.page_layout, (base_path / "layouts" / "custom.html").resolve())

    def test_Config_rejects_site_manifest_block(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                "site:\n  manifest:\n    name: Acme Docs\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                Config.load(base_path)

    def test_Config_rejects_removed_site_title_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text("site:\n  title: Acme Docs\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                Config.load(base_path)

    def test_Config_rejects_removed_site_theme_color_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text("site:\n  theme_color: '#f00'\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                Config.load(base_path)

    def test_Config_rejects_unknown_flat_top_level_keys(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                "inputs: wiki\nlink_style: markdown\nwiki_base: https://example.org/wiki/\n",
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                Config.load(base_path)
            message = str(ctx.exception)
            self.assertIn("unknown top-level keys", message)
            self.assertIn("inputs", message)
            self.assertIn("link_style", message)
            self.assertIn("wiki_base", message)

    def test_Config_rejects_unknown_site_keys(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text("site:\n  favicon: /icon.png\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                Config.load(base_path)
            self.assertIn("unknown site keys", str(ctx.exception))

    def test_Config_load_link_style(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text("link:\n  style: standard\n", encoding="utf-8")
            config = Config.load(base_path)
            self.assertEqual(config.link.style, "standard")

    def test_Config_load_wikilink_link_style(self) -> None:
        config = Config(link={"style": "wikilink"})
        self.assertEqual(config.link.style, "wikilink")

    def test_Config_accepts_legacy_markdown_link_style(self) -> None:
        config = Config(link={"style": "markdown"})
        self.assertEqual(config.link.style, "standard")

    def test_Config_accepts_legacy_obsidian_link_style(self) -> None:
        config = Config(link={"style": "obsidian"})
        self.assertEqual(config.link.style, "wikilink")

    def test_Config_rejects_invalid_link_style(self) -> None:
        with self.assertRaises(ValidationError):
            Config(link={"style": "not-a-style"})

    def test_Config_implicit_types_defaults(self) -> None:
        config = Config()
        self.assertEqual(config.graph.implicit_types, [])
        self.assertEqual(config.graph.implicit_types_policy, "fallback")

    def test_Config_load_implicit_types(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                "graph:\n  implicit_types: [schema:TechArticle]\n  implicit_types_policy: append\n",
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertEqual(config.graph.implicit_types, ["schema:TechArticle"])
            self.assertEqual(config.graph.implicit_types_policy, "append")

    def test_Config_rejects_invalid_implicit_types_policy(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Config(graph={"implicit_types_policy": "replace"})

    def test_Config_base_iri_defaults_to_context_wiki(self) -> None:
        config = Config(graph={"context": {"wiki": "https://example.org/wiki/"}})
        self.assertEqual(config.base_iri, "https://example.org/wiki/")

    def test_Config_base_iri_override(self) -> None:
        config = Config(
            graph={
                "context": {"wiki": "https://example.org/wiki/"},
                "base_iri": "https://example.org/docs/",
            }
        )
        self.assertEqual(config.base_iri, "https://example.org/docs/")

    def test_Config_rejects_graph_wiki_base_key(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Config(graph={"wiki_base": "https://example.org/wiki/"})

    def test_Config_load_json(self) -> None:
        """Test Config.load correctly parses wiki.json."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            json_content = {
                "wiki": {"input": "json_wiki"},
                "graph": {
                    "@context": {
                        "json_pref": "http://json-pref.org/"
                    }
                },
            }
            (base_path / "wiki.json").write_text(json.dumps(json_content), encoding="utf-8")

            config = Config.load(base_path)
            self.assertEqual(config.wiki.input, [base_path.absolute() / "json_wiki"])
            self.assertIn("json_pref", config.namespaces)

    def test_Config_load_camel_case_top_level_keys_raise_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            yaml_content = {
                "inputDirs": "camel_wiki",
                "assetDirs": ["assets"],
                "wikiBase": "https://example.org/wiki/",
                "baseUrl": "/docs",
                "urlStyle": "file",
                "contentPredicate": "schema:text",
                "uriExt": True,
                "filenamePattern": "[a-z]+",
                "serveApi": {"enabled": True, "path": "/sparql"},
            }
            (base_path / "assets").mkdir()
            (base_path / "wiki.yaml").write_text(yaml.dump(yaml_content), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "unknown top-level keys"):
                Config.load(base_path)

    def test_Config_load_unknown_check_keys_raise_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "check": {"brokenLinks": "error"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown check keys"):
                Config.load(base_path)

    def test_Config_load_unknown_sparql_service_keys_raise_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "sparql_service": {"enable": True}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown sparql_service keys"):
                Config.load(base_path)

    def test_Config_rejects_unknown_serve_api_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "serve_api": {"enabled": True}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown top-level keys: serve_api"):
                Config.load(base_path)

    def test_Config_default_asset_dir_when_present(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "assets").mkdir()
            (base_path / "wiki.yaml").write_text(MINIMAL_WIKI_YAML, encoding="utf-8")

            config = Config.load(base_path)
            self.assertEqual(config.wiki.assets, [base_path.absolute() / "assets"])

    def test_Config_exclude_matches_config_root_relative_paths(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir).absolute()
            config = Config(config_root=base_path, wiki={"exclude": ["wiki/drafts/**", "**/.env*"]})

            self.assertTrue(config.is_excluded(base_path / "wiki" / "drafts" / "note.md"))
            self.assertTrue(config.is_excluded(base_path / "assets" / ".env.local"))
            self.assertFalse(config.is_excluded(base_path / "wiki" / "published.md"))

    def test_Config_load_rejects_moved_check_keys(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump(
                    {
                        "wiki": {"input": "wiki"},
                        "check": {"filename_pattern": "warning", "broken_links": "warning"},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown check keys"):
                Config.load(base_path)

    def test_Config_rejects_moved_check_keys_at_init(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Config(check={"filename_pattern": "[A-Za-z]+"})

    def test_Config_load_lint_broken_links(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "lint": {"broken_links": "error"}}),
                encoding="utf-8",
            )

            config = Config.load(base_path)
            self.assertEqual(config.lint.broken_links, "error")

    def test_Config_load_unknown_lint_keys_raise_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "lint": {"brokenLinks": "error"}}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "unknown lint keys"):
                Config.load(base_path)

    def test_Config_rejects_check_broken_links_at_init(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Config(check={"broken_links": "error"})

    def test_Config_invalid_severity_raises(self) -> None:
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            Config(lint={"broken_links": "maybe"})

    def test_Config_load_invalid_syntax_raises_error(self) -> None:
        """Test Config.load raises on config syntax errors."""
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text("[invalid_yaml", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Failed to load config file wiki.yaml"):
                Config.load(base_path)

    def test_Config_load_inline_fmt(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump(
                    {
                        "wiki": {"input": "wiki"},
                        "fmt": {
                            "wrap": "no",
                            "extensions": ["gfm", "front_matters", "wikilink"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertIsInstance(config.fmt, FmtConfig)
            self.assertEqual(config.fmt.options["wrap"], "no")

    def test_Config_load_fmt_pointer_relative(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "fmt": "custom.toml"}),
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertIsInstance(config.fmt, FmtConfig)
            self.assertEqual(config.fmt.toml, base_path / "custom.toml")
            self.assertIsNone(config.fmt.options)

    def test_Config_rejects_absolute_fmt_path(self) -> None:
        absolute_fmt = (
            "C:/etc/mdformat.toml" if os.name == "nt" else "/etc/mdformat.toml"
        )
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "fmt": absolute_fmt}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "fmt path must be relative"):
                Config.load(base_path)

    def test_Config_rejects_invalid_fmt_type(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "fmt": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "fmt must be a mapping or path string"):
                Config.load(base_path)

    def test_Config_rejects_unknown_inline_fmt_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"input": "wiki"}, "fmt": {"typo_key": True}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Invalid key 'typo_key'"):
                Config.load(base_path)

    def test_Config_load_inline_fmt_from_json(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.json").write_text(
                json.dumps(
                    {
                        "wiki": {"input": ["wiki"]},
                        "fmt": {
                            "wrap": "no",
                            "extensions": ["gfm", "front_matters", "wikilink"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertIsInstance(config.fmt, FmtConfig)
            self.assertEqual(config.fmt.options["extensions"], ["gfm", "front_matters", "wikilink"])

    def test_check_remote_schema_policy(self) -> None:
        config = Config.for_root(
            ".",
            check={
                "remote_schema_refs": "allowlist",
                "remote_schema_hosts": ["schemas.example.org"],
            },
        )
        self.assertEqual(config.check.remote_schema_refs, "allowlist")
        self.assertEqual(config.check.remote_schema_hosts, ["schemas.example.org"])

    def test_sparql_service_enabled_string_false(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                "sparql_service:\n  enabled: \"false\"\n",
                encoding="utf-8",
            )
            config = Config.load(base_path)
            self.assertFalse(config.sparql_service.enabled)

    def test_sparql_service_enabled_string_variants(self) -> None:
        for raw, expected in (
            ("0", False),
            ("no", False),
            ("off", False),
            ("true", True),
            ("1", True),
            ("yes", True),
            ("on", True),
        ):
            with self.subTest(raw=raw):
                config = Config.for_root(".", sparql_service={"enabled": raw})
                self.assertEqual(config.sparql_service.enabled, expected)

    def test_sparql_service_enabled_invalid_string(self) -> None:
        with self.assertRaises(ValueError):
            Config.for_root(".", sparql_service={"enabled": "maybe"})


if __name__ == "__main__":
    unittest.main()
