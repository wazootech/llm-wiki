"""Tests for wiki init scaffold helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import yaml

from wiki.config import Config
from wiki.fmt_util import DEFAULT_FMT_OPTS
from wiki.init_scaffold import (
    InitOptions,
    _scaffold_wiki,
    detect_origin_repo,
    fetch_template,
    infer_github_pages_urls,
    load_packaged_official_layout,
    normalize_base_url,
    parse_github_repo,
    render_wiki_yaml,
    resolve_init_options,
)
from wiki.schemas.wiki_config import normalize_base_iri


class TestParseGithubRepo(TestCase):
    def test_owner_repo_shorthand(self) -> None:
        self.assertEqual(parse_github_repo("wazootech/wiki"), ("wazootech", "wiki"))

    def test_https_url(self) -> None:
        self.assertEqual(
            parse_github_repo("https://github.com/wazootech/wiki.git"),
            ("wazootech", "wiki"),
        )

    def test_ssh_url(self) -> None:
        self.assertEqual(
            parse_github_repo("git@github.com:wazootech/wiki-cli.git"),
            ("wazootech", "wiki-cli"),
        )

    def test_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_github_repo("not-a-repo")


class TestInferGithubPagesUrls(TestCase):
    def test_project_site(self) -> None:
        context_wiki, base_url = infer_github_pages_urls("wazootech", "wiki")
        self.assertEqual(context_wiki, "https://wazootech.github.io/wiki/")
        self.assertEqual(base_url, "/wiki")

    def test_hyphenated_repo(self) -> None:
        context_wiki, base_url = infer_github_pages_urls("wazootech", "wiki-cli")
        self.assertEqual(context_wiki, "https://wazootech.github.io/wiki-cli/")
        self.assertEqual(base_url, "/wiki-cli")


class TestNormalize(TestCase):
    def test_base_iri_trailing_slash(self) -> None:
        self.assertEqual(normalize_base_iri("https://example.org/wiki"), "https://example.org/wiki/")

    def test_base_url_leading_slash(self) -> None:
        self.assertEqual(normalize_base_url("wiki"), "/wiki")


class TestDetectOriginRepo(TestCase):
    def test_returns_none_without_git_dir(self) -> None:
        with TemporaryDirectory() as tmpdir:
            self.assertIsNone(detect_origin_repo(Path(tmpdir)))

    @patch("wiki.init_scaffold.subprocess.run")
    def test_parses_https_remote(self, run_mock) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            run_mock.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="https://github.com/wazootech/wiki.git\n", stderr=""
            )
            self.assertEqual(detect_origin_repo(root), "wazootech/wiki")


class TestRenderWikiYaml(TestCase):
    def test_renders_optional_fields(self) -> None:
        rendered = render_wiki_yaml(
            InitOptions(
                graph_context_wiki="https://wazootech.github.io/wiki/",
                site_base_url="/wiki",
                site_url_style="dir",
                graph_content_predicate="schema:articleBody",
                link_style="standard",
            ),
        )
        self.assertIn("wiki: https://wazootech.github.io/wiki/", rendered)
        self.assertNotIn("wiki_base:", rendered)
        self.assertIn("wazoo: https://schema.wazoo.dev/", rendered)
        self.assertIn("base_url: /wiki", rendered)
        self.assertIn("content_predicate: schema:articleBody", rendered)
        self.assertIn("style: standard", rendered)
        self.assertIn("link:", rendered)
        self.assertNotIn("headings: off", rendered)
        self.assertNotIn("heading_levels: off", rendered)
        self.assertNotIn("duplicate_headings: off", rendered)
        self.assertNotIn("thematic_breaks: off", rendered)
        self.assertIn("missing_layout_file: error", rendered)
        self.assertIn("frontmatter_schema: error", rendered)
        self.assertIn("missing_schema_ref: error", rendered)
        self.assertIn('wrap: "no"', rendered)
        self.assertIn("extensions: [gfm, front_matters, wikilink, toc, footnote]", rendered)
        self.assertIn("assets:", rendered)
        self.assertIn("- assets", rendered)
        self.assertIn("layout: custom.html", rendered)
        self.assertIn("# layout: custom.html", rendered)
        self.assertNotIn("manifest:", rendered)
        self.assertIn("# fmt: .mdformat.toml", rendered)
        self.assertNotIn("{#", rendered)
        self.assertNotIn("__", rendered)

    def test_rendered_fmt_matches_default_fmt_opts(self) -> None:
        rendered = render_wiki_yaml(InitOptions(graph_context_wiki="https://wiki.example.org/"))
        parsed = yaml.safe_load(rendered)
        self.assertEqual(parsed["fmt"], DEFAULT_FMT_OPTS)

    def test_omits_optional_fields_when_unset(self) -> None:
        rendered = render_wiki_yaml(
            InitOptions(graph_context_wiki="https://wiki.example.org/"),
        )
        self.assertIn("# content_predicate: schema:articleBody", rendered)
        self.assertNotIn("\ncontent_predicate:", rendered)

    def test_rendered_yaml_parses_and_loads(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "wiki.yaml"
            config_path.write_text(
                render_wiki_yaml(InitOptions(graph_context_wiki="https://wiki.example.org/")),
                encoding="utf-8",
            )
            parsed = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("wiki_base", parsed["graph"])
            self.assertEqual(parsed["graph"]["context"]["wiki"], "https://wiki.example.org/")
            config = Config.load(config_path)
            self.assertEqual(config.base_iri, "https://wiki.example.org/")

    def test_load_packaged_official_layout_minimal(self) -> None:
        rendered = load_packaged_official_layout("minimal")
        self.assertIn("%wiki.head%", rendered)
        self.assertIn("%wiki.body%", rendered)
        self.assertNotIn("%wiki.page.title%", rendered)
        self.assertNotIn("wikipedia.css", rendered)
        self.assertNotIn("mw-navigation", rendered)


class TestResolveInitOptions(TestCase):
    def test_repo_flag_skips_prompt(self) -> None:
        opts = resolve_init_options(
            repo="wazootech/wiki",
            graph_context_wiki=None,
            site_base_url=None,
            site_url_style=None,
            graph_content_predicate=None,
            link_style=None,
            cwd=Path("."),
            init_git=False,
            prompt_context_wiki=lambda _: self.fail("prompt should not run"),
        )
        self.assertEqual(opts.graph_context_wiki, "https://wazootech.github.io/wiki/")
        self.assertEqual(opts.site_base_url, "/wiki")

    def test_context_wiki_overrides_repo(self) -> None:
        opts = resolve_init_options(
            repo="wazootech/wiki",
            graph_context_wiki="https://example.org/custom/",
            site_base_url="/custom",
            site_url_style=None,
            graph_content_predicate=None,
            link_style=None,
            cwd=Path("."),
            init_git=False,
            prompt_context_wiki=lambda _: self.fail("prompt should not run"),
        )
        self.assertEqual(opts.graph_context_wiki, "https://example.org/custom/")
        self.assertEqual(opts.site_base_url, "/custom")

    @patch("wiki.init_scaffold.detect_origin_repo", return_value="wazootech/wiki")
    def test_detects_git_remote_when_git_present(self, _detect_mock) -> None:
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".git").mkdir()
            opts = resolve_init_options(
                repo=None,
                graph_context_wiki=None,
                site_base_url=None,
                site_url_style=None,
                graph_content_predicate=None,
                link_style=None,
                cwd=Path(tmpdir),
                init_git=False,
                prompt_context_wiki=lambda _: self.fail("prompt should not run"),
            )
        self.assertEqual(opts.graph_context_wiki, "https://wazootech.github.io/wiki/")


INIT_OPTIONS_TO_CONFIG_PATH = {
    "graph_context_wiki": ("graph", "context", "wiki"),
    "site_base_url": ("site", "base_url"),
    "site_url_style": ("site", "url_style"),
    "site_layout": ("site", "layout"),
    "graph_content_predicate": ("graph", "content_predicate"),
    "link_style": ("link", "style"),
    "wiki_inputs": ("wiki", "input"),
    "graph_base_iri": ("graph", "base_iri"),
    "graph_implicit_types": ("graph", "implicit_types"),
    "graph_implicit_types_policy": ("graph", "implicit_types_policy"),
    "graph_include_file_extension": ("graph", "include_file_extension"),
}

# Init-only CLI flags with no matching config path (used only during init).
INIT_ONLY_OPTIONS: frozenset[str] = frozenset({"template"})

# Fields whose flag does not follow the --kebab-case-of-field convention.
# wiki_inputs stays snake internally (shape of the #227 rename) while its
# Click flag is --input, not --wiki-inputs.
FIELD_TO_FLAG_OVERRIDES: dict[str, str] = {"wiki_inputs": "--input"}


class TestInitLockstep(TestCase):
    def test_init_options_fields_match_cli_options(self) -> None:
        """Ensure every field in InitOptions has a matching --kebab-case Click CLI option."""
        from wiki.cli import init as init_cmd
        cli_option_names = {opt.opts[0] for opt in init_cmd.params if opt.opts}
        for field in InitOptions.model_fields.keys():
            expected_opt = FIELD_TO_FLAG_OVERRIDES.get(field, "--" + field.replace("_", "-"))
            # We allow options with both / and without / (e.g. --graph-include-file-extension/--no-graph-include-file-extension)
            # Click splits these but let's check prefix or inclusion
            found = False
            for opt_name in cli_option_names:
                if opt_name.startswith(expected_opt):
                    found = True
                    break
            self.assertTrue(
                found,
                f"InitOptions field '{field}' is missing a matching CLI option '{expected_opt}' in click 'init' command."
            )

    def test_init_options_map_to_valid_config_paths(self) -> None:
        """Ensure every InitOptions field maps to a valid Pydantic model path on Config."""
        from typing import Union, get_args, get_origin

        from pydantic import BaseModel
        for field, path in INIT_OPTIONS_TO_CONFIG_PATH.items():
            self.assertIn(field, InitOptions.model_fields, f"Mapped field '{field}' is not in InitOptions.")
            
            current_model = Config
            for part in path:
                if hasattr(current_model, "model_fields"):
                    self.assertIn(part, current_model.model_fields, f"Path part '{part}' for field '{field}' is not a valid field in {current_model.__name__}.")
                    field_info = current_model.model_fields[part]
                    annotation = field_info.annotation
                    
                    origin = get_origin(annotation)
                    if origin is Union:
                        next_model = None
                        for arg in get_args(annotation):
                            if isinstance(arg, type) and issubclass(arg, BaseModel):
                                next_model = arg
                                break
                        current_model = next_model
                    elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                        current_model = annotation
                    else:
                        current_model = None
                else:
                    break
        
        for field in InitOptions.model_fields:
            if field in INIT_ONLY_OPTIONS:
                continue
            self.assertIn(field, INIT_OPTIONS_TO_CONFIG_PATH, f"InitOptions field '{field}' is not mapped in INIT_OPTIONS_TO_CONFIG_PATH.")


class TestScaffoldGitignore(TestCase):
    def test_scaffold_creates_gitignore(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = _scaffold_wiki(
                root,
                InitOptions(graph_context_wiki="https://example.org/wiki/"),
            )
            self.assertTrue(result.ok)
            gitignore = root / ".gitignore"
            self.assertTrue(gitignore.exists())
            content = gitignore.read_text(encoding="utf-8")
            self.assertIn(".wiki/", content)
            self.assertIn("_site/", content)

    def test_scaffold_skips_existing_gitignore(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            existing = root / ".gitignore"
            existing.write_text("# custom\n.env/\n", encoding="utf-8")
            result = _scaffold_wiki(
                root,
                InitOptions(graph_context_wiki="https://example.org/wiki/"),
            )
            self.assertTrue(result.ok)
            content = existing.read_text(encoding="utf-8")
            self.assertIn(".env/", content)


class TestFetchTemplate(TestCase):
    @patch("wiki.init_scaffold.subprocess.run")
    def test_fetch_template_clones_and_copies(self, run_mock) -> None:
        """Test that fetch_template clones the repo and copies template files."""
        import shutil
        from unittest.mock import MagicMock

        # Create a fake wiki-templates monorepo with a generic template
        with TemporaryDirectory() as fake_templates_dir:
            fake_templates = Path(fake_templates_dir)
            generic_dir = fake_templates / "generic"
            generic_dir.mkdir()
            (generic_dir / "wiki.yml").write_text(
                "wiki:\n  input:\n    - wiki\n", encoding="utf-8"
            )
            (generic_dir / "README.md").write_text(
                "# Generic Wiki\n", encoding="utf-8"
            )
            wiki_dir = generic_dir / "wiki"
            wiki_dir.mkdir()
            (wiki_dir / "Page.md").write_text(
                "---\ntype: schema:WebPage\n---\n", encoding="utf-8"
            )
            # Also add a hidden .github dir that should be skipped
            github_dir = generic_dir / ".github"
            github_dir.mkdir()
            (github_dir / "workflows").mkdir()

            def fake_run(args, **kwargs):
                # Simulate successful clone by copying fake repo
                if "clone" in args:
                    clone_dest = Path(args[-1])
                    shutil.copytree(fake_templates, clone_dest)
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
                    return result
                result = MagicMock()
                result.returncode = 0
                return result

            run_mock.side_effect = fake_run

            with TemporaryDirectory() as target_dir:
                target = Path(target_dir)
                fetch_template(target, "generic")

                # Verify files were copied
                self.assertTrue((target / "wiki.yml").exists())
                self.assertTrue((target / "README.md").exists())
                self.assertTrue((target / "wiki").is_dir())
                self.assertTrue((target / "wiki" / "Page.md").exists())
                # .github should be skipped
                self.assertFalse((target / ".github").exists())

    @patch("wiki.init_scaffold.subprocess.run")
    def test_fetch_template_raises_on_missing(self, run_mock) -> None:
        """Test that fetch_template raises RuntimeError for unknown templates."""
        from unittest.mock import MagicMock

        with TemporaryDirectory() as fake_templates_dir:
            fake_templates = Path(fake_templates_dir)
            # Create a repo with no matching template
            (fake_templates / "other").mkdir()

            def fake_run(args, **kwargs):
                if "clone" in args:
                    clone_dest = Path(args[-1])
                    import shutil
                    shutil.copytree(fake_templates, clone_dest)
                result = MagicMock()
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
                return result

            run_mock.side_effect = fake_run

            with TemporaryDirectory() as target_dir:
                target = Path(target_dir)
                with self.assertRaises(RuntimeError) as ctx:
                    fetch_template(target, "nonexistent")
                self.assertIn("nonexistent", str(ctx.exception))
                self.assertIn("Available", str(ctx.exception))
