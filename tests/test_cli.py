import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import urlopen

import yaml
from click.testing import CliRunner

from wiki import __version__
from wiki.cli import FILE_COMMANDS, main
from wiki.config import Config
from wiki.init_scaffold import (
    InitOptions,
    render_wiki_yaml,
)


class TestCLI(unittest.TestCase):


    def test_cli_check_succeeds_and_fails(self) -> None:
        """Test that wiki check succeeds on valid documents and fails on violations."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            # 1. Running check on empty directory conforms silently (success)
            result = runner.invoke(main, ["--wiki-inputs", tmpdir, "check"])
            self.assertEqual(result.exit_code, 0)
            self.assertEqual(result.output, "")
            
            # 2. Add a build-unsafe filename and test that strict mode fails
            invalid_file = Path(tmpdir) / "Invalid Name.md"
            invalid_file.write_text("""---
id: wiki:invalid
type: schema:WebPage
name: Invalid Page
---
""", encoding="utf-8")
            
            result_strict = runner.invoke(main, ["--wiki-inputs", tmpdir, "check", "--strict", "-v"])
            self.assertEqual(result_strict.exit_code, 1)
            self.assertIn("Errors:", result_strict.output)
            self.assertIn("spaces are not allowed", result_strict.output)

    def test_cli_version_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, f"wiki, version {__version__}\n")

    def test_cli_lint_reports_filename_pattern(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            wiki_dir = config_dir / "wiki"
            wiki_dir.mkdir()
            (config_dir / "wiki.yaml").write_text(
                yaml.dump(
                    {
                        "wiki": {
                            "inputs": ["wiki"],
                            "filename_pattern": r"[A-Za-z0-9_()-]+\.md",
                        },
                        "lint": {"filename_pattern": "warning"},
                    }
                ),
                encoding="utf-8",
            )
            (wiki_dir / "bad.name.md").write_text("---\ntype: schema:WebPage\n---\n", encoding="utf-8")
            result = runner.invoke(
                main,
                [
                    "-c",
                    str(config_dir),
                    "lint",
                    "--strict",
                    "-v",
                ],
            )
            self.assertEqual(result.exit_code, 1)
            self.assertIn("Errors:", result.output)
            self.assertIn("filename_pattern", result.output)

    def test_cli_input_dir_resolves_relative_to_config_root(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            extra_dir = config_dir / "extra"
            extra_dir.mkdir()
            (config_dir / "wiki.yaml").write_text("wiki:\n  inputs:\n    - wiki\n", encoding="utf-8")
            (extra_dir / "note.md").write_text(
                "---\ntype: schema:WebPage\nname: Extra\n---\n",
                encoding="utf-8",
            )

            result = runner.invoke(
                main,
                [
                    "-c",
                    str(config_dir),
                    "--wiki-inputs",
                    "extra",
                    "query",
                    "--no-inference",
                    "SELECT ?name WHERE { ?s <https://schema.org/name> ?name }",
                    "-f",
                    "json",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Extra", result.output)

    def test_cli_check_does_not_normalize_frontmatter(self) -> None:
        """Test that check performs no frontmatter key normalization (strict SHACL on exact keys)."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            shape_path = wiki_dir / "person-shape.ttl"
            shape_path.write_text("""
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix schema: <https://schema.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

schema:PersonShape
  a sh:NodeShape ;
  sh:targetClass schema:Person ;
  sh:property [
    sh:path schema:givenName ;
    sh:minCount 1 ;
    sh:datatype xsd:string ;
  ] ;
  sh:property [
    sh:path schema:familyName ;
    sh:minCount 1 ;
    sh:datatype xsd:string ;
  ] .
""", encoding="utf-8")

            file_path = wiki_dir / "alice.md"
            file_path.write_text("""---
type: Person
given_name: Alice
family_name: Anderson
---
# Alice
""", encoding="utf-8")

            # Without --fix: should FAIL SHACL because keys don't match expected schema:givenName/familyName.
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "check", str(file_path), "-v"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("SHACL Validation Violation", result.output)
            content = file_path.read_text(encoding="utf-8")
            self.assertIn("given_name: Alice", content)
            self.assertIn("family_name: Anderson", content)
            self.assertNotIn("givenName:", content)
            self.assertNotIn("familyName:", content)

    def test_cli_check_single_file(self) -> None:
        """Test wiki check with a single file specified."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            valid_file = wiki_dir / "valid-file.md"
            valid_file.write_text("""---
id: wiki:valid-file
type: schema:WebPage
name: Valid File
---
""", encoding="utf-8")
            
            # Conforming single file check
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "check", str(valid_file)])
            self.assertEqual(result.exit_code, 0)
            
            # Non-conforming single file check
            invalid_file = wiki_dir / "Invalid Name.md"
            invalid_file.write_text("""---
id: wiki:invalid-name
type: schema:WebPage
name: Invalid Name
---
""", encoding="utf-8")
            result_invalid = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "check", str(invalid_file), "--strict"])
            self.assertEqual(result_invalid.exit_code, 1)

    def test_file_argument_accepts_multiple_paths(self) -> None:
        """FILE positionals on check/lint/link/render/export/fmt use nargs=-1."""
        for name in FILE_COMMANDS:
            with self.subTest(command=name):
                param = next(p for p in main.commands[name].params if p.name == "files")
                self.assertEqual(param.nargs, -1)
                self.assertFalse(param.required)

    def test_cli_accepts_multiple_file_arguments(self) -> None:
        """Multiple FILE paths scope lint and fmt to those documents."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            wiki_dir = config_dir / "wiki"
            wiki_dir.mkdir()
            (config_dir / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"inputs": ["wiki"]}}),
                encoding="utf-8",
            )
            first = wiki_dir / "first.md"
            second = wiki_dir / "second.md"
            frontmatter = "---\ntype: schema:WebPage\nname: Page\n---\n"
            first.write_text(frontmatter, encoding="utf-8")
            second.write_text(frontmatter + "\n# First\n", encoding="utf-8")

            result_lint = runner.invoke(
                main,
                ["-c", str(config_dir), "lint", str(first), str(second)],
            )
            self.assertEqual(result_lint.exit_code, 0)

            result_fmt = runner.invoke(
                main,
                ["-c", str(config_dir), "fmt", "--check", str(first), str(second)],
            )
            self.assertEqual(result_fmt.exit_code, 0)

    def test_cli_check_multiple_files_shacl_only(self) -> None:
        """Multiple FILE paths on check run per-file SHACL without full-wiki checks."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            wiki_dir = config_dir / "wiki"
            wiki_dir.mkdir()
            (config_dir / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"inputs": ["wiki"]}}),
                encoding="utf-8",
            )
            first = wiki_dir / "first.md"
            second = wiki_dir / "second.md"
            first.write_text("---\ntype: schema:WebPage\nname: First\n---\n", encoding="utf-8")
            second.write_text("---\ntype: schema:WebPage\nname: Second\n---\n", encoding="utf-8")

            result = runner.invoke(
                main,
                ["-c", str(config_dir), "check", str(first), str(second)],
            )
            self.assertEqual(result.exit_code, 0)

    def test_cli_check_scoped_frontmatter_schema(self) -> None:
        """Scoped wiki check runs JSON Schema validation via file_paths wiring."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            wiki_dir = config_dir / "wiki"
            wiki_dir.mkdir()
            schemas_dir = config_dir / "schemas"
            schemas_dir.mkdir()
            (schemas_dir / "article.json").write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["headline", "description"],
                        "properties": {
                            "headline": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (config_dir / "wiki.yaml").write_text(
                yaml.dump({"wiki": {"inputs": ["wiki"]}}),
                encoding="utf-8",
            )
            (wiki_dir / "Article_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:TechArticle\n"
                "wazoo:jsonSchema: schemas/article.json\n"
                "---\n",
                encoding="utf-8",
            )
            valid = wiki_dir / "Valid.md"
            valid.write_text(
                "---\ntype: TechArticle\nheadline: Ok\ndescription: Fine\n---\n",
                encoding="utf-8",
            )
            broken = wiki_dir / "Broken.md"
            broken.write_text("---\ntype: TechArticle\nheadline: Only\n---\n", encoding="utf-8")
            other = wiki_dir / "Other_Broken.md"
            other.write_text("---\ntype: TechArticle\nheadline: Other\n---\n", encoding="utf-8")

            ok = runner.invoke(main, ["-c", str(config_dir), "check", str(valid)])
            self.assertEqual(ok.exit_code, 0, msg=ok.output)

            fail = runner.invoke(main, ["-c", str(config_dir), "check", str(broken)])
            self.assertEqual(fail.exit_code, 1, msg=fail.output)
            self.assertIn("description", fail.output)

            scoped = runner.invoke(main, ["-c", str(config_dir), "check", str(valid)])
            self.assertEqual(scoped.exit_code, 0, msg=scoped.output)
            self.assertNotIn("Other_Broken", scoped.output)

    def test_cli_query_formats(self) -> None:
        """Test that wiki query executes successfully with various output formats."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            # Create a simple page
            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---
""", encoding="utf-8")
            
            # Run simple query SELECT name
            query_str = "SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }"
            
            # Table format
            res_table = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", query_str])
            self.assertEqual(res_table.exit_code, 0)
            self.assertIn("Alice", res_table.output)
            
            # JSON format
            res_json = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "-f", "json", "--no-inference", query_str])
            self.assertEqual(res_json.exit_code, 0)
            parsed = json.loads(res_json.output)
            self.assertIn("results", parsed)
            
            # Error mode - invalid SPARQL syntax
            res_err = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "INVALID QUERY"])
            self.assertEqual(res_err.exit_code, 1)

    def test_cli_query_jq_filter(self) -> None:
        """Test that wiki query --jq extracts values from JSON output."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---
""", encoding="utf-8")

            query_str = "SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }"

            # --jq auto-switches to JSON and extracts the value
            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "query", "--no-inference", query_str,
                "--jq", "results.bindings[].givenName.value"
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Alice", result.output)

            # --jq with no matches produces no output
            result_empty = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "query", "--no-inference", query_str,
                "--jq", "results.nonexistent"
            ])
            self.assertEqual(result_empty.exit_code, 0)
            self.assertEqual(result_empty.output.strip(), "")

    def test_cli_query_output_file(self) -> None:
        """Test that wiki query -o writes results to a file."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---""", encoding="utf-8")

            query_str = "SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }"
            out_file = Path(tmpdir) / "results.json"

            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "query", "--no-inference", query_str,
                "-f", "json", "-o", str(out_file)
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Written results to", result.output)
            self.assertTrue(out_file.exists())
            parsed = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertIn("results", parsed)

    def test_cli_query_all_formats(self) -> None:
        """Test every --format choice for query (csv, tsv, markdown, mime aliases)."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---""", encoding="utf-8")

            query_str = "SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }"

            # CSV
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "-f", "csv", query_str])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

            # TSV (previously broken — now works with inline formatter)
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "-f", "tsv", query_str])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

            # Markdown table
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "-f", "markdown", query_str])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)
            self.assertIn("|", res.output)

            # MIME alias — "text/csv" resolves to "csv"
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "-f", "text/csv", query_str])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

            # Case-insensitive — "JSON" accepted via case_sensitive=False
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "-f", "JSON", query_str])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

    def test_cli_render_inline_sparql(self) -> None:
        """Test that wiki render updates inline SPARQL blocks correctly."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            
            # Create a source file with SPARQL block
            source_content = """---
type: Person
givenName: Gregory
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
"""
            file_path = wiki_dir / "gregory.md"
            file_path.write_text(source_content, encoding="utf-8")
            
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", "-v"])
            self.assertEqual(result.exit_code, 0)
            
            # Verify the SPARQL block was rendered and updated inline
            updated_content = file_path.read_text(encoding="utf-8")
            self.assertIn("Gregory", updated_content)

    def test_cli_render_check(self) -> None:
        """Test that wiki render --check reports stale files correctly without updating them."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            source_content = """---
type: Person
givenName: Gregory
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
"""
            file_path = wiki_dir / "gregory.md"
            file_path.write_text(source_content, encoding="utf-8")
            
            # 1. Check should FAIL because the table is missing (stale)
            result_stale = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", "--check"])
            self.assertEqual(result_stale.exit_code, 1)
            self.assertIn("Error: Inline SPARQL blocks are out of date", result_stale.output)
            
            # Verify the file remained UNCHANGED (no disk write)
            current_content = file_path.read_text(encoding="utf-8")
            self.assertEqual(current_content, source_content)
            self.assertNotIn("Gregory", current_content.split("```")[-1])
            
            # 2. Now, actually render it
            result_render = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference"])
            self.assertEqual(result_render.exit_code, 0)
            
            # 3. Now, check should SUCCEED since it's up to date
            result_clean = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", "--check", "-v"])
            self.assertEqual(result_clean.exit_code, 0)
            self.assertIn("All dynamic SPARQL blocks are fully up to date", result_clean.output)

    def test_cli_init_scaffolds_wiki_files(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                result = runner.invoke(
                    main,
                    [
                        "init",
                        "--graph-context-wiki",
                        "https://wiki.example.org/",
                    ],
                    catch_exceptions=False,
                )

                self.assertEqual(result.exit_code, 0)
                
                # Check wiki.yml exists
                config_content = Path("wiki.yml").read_text(encoding="utf-8")
                self.assertIn("wiki: https://wiki.example.org/", config_content)
                self.assertNotIn("wiki_base:", config_content)
                self.assertIn("sh: http://www.w3.org/ns/shacl#", config_content)

                # Check README.md exists and contains commands
                readme_content = Path("README.md").read_text(encoding="utf-8")
                self.assertIn("A semantic markdown knowledge base powered by the Wiki CLI.", readme_content)
                self.assertIn("wiki check", readme_content)

                # Check wiki/Person_Shape.md exists and contains schema:givenName/familyName
                shape_content = Path("wiki") / "Person_Shape.md"
                content = shape_content.read_text(encoding="utf-8")
                self.assertIn("sh:path: schema:givenName", content)
                self.assertIn("sh:path: schema:familyName", content)

                # Check wiki/Ethan_Davidson.md exists
                person_content = (Path("wiki") / "Ethan_Davidson.md").read_text(encoding="utf-8")
                self.assertIn("wiki tweak: replace with your first page", person_content)
                self.assertIn("givenName: Ethan", person_content)
                self.assertIn("familyName: Davidson", person_content)
                self.assertNotIn("wazoo:layout:", person_content)

                # Check layout and assets are commented/unused in config
                self.assertNotIn("manifest:", config_content)
                self.assertIn("layout: custom.html", config_content)
                self.assertIn("# layout: custom.html", config_content)
                self.assertIn("assets:", config_content)
                self.assertIn("- assets", config_content)
                
                # Ensure no Wikipedia templates or styles were written
                self.assertFalse((Path("layouts") / "wikipedia.html").exists())
                self.assertFalse((Path("assets") / "wikipedia.css").exists())
                self.assertFalse((Path("assets") / "logo.svg").exists())

                expected_content = render_wiki_yaml(
                    InitOptions(
                        graph_context_wiki="https://wiki.example.org/",
                    ),
                )
                self.assertEqual(config_content, expected_content)
                self.assertIn('wrap: "no"', config_content)
                self.assertFalse(Path(".mdformat.toml").exists())
                self.assertIn("wazoo: https://schema.wazoo.dev/", config_content)

                result2 = runner.invoke(
                    main,
                    [
                        "init",
                        "--graph-context-wiki",
                        "https://wiki.example.org/",
                    ],
                )
                self.assertNotEqual(result2.exit_code, 0)
                self.assertIn("already exists", result2.output)

                self.assertFalse((Path(".git")).exists())

    def test_cli_init_with_repo_flag(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                result = runner.invoke(
                    main,
                    ["init", "--repo", "wazootech/wiki"],
                    catch_exceptions=False,
                )
                self.assertEqual(result.exit_code, 0)
                config_content = Path("wiki.yml").read_text(encoding="utf-8")
                self.assertIn("wiki: https://wazootech.github.io/wiki/", config_content)
                self.assertNotIn("wiki_base:", config_content)
                self.assertIn("wiki: https://wazootech.github.io/wiki/", config_content)
                self.assertIn("base_url: /wiki", config_content)
                self.assertIn("wazoo: https://schema.wazoo.dev/", config_content)


    def test_cli_init_implicit_types_policy_append(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                result = runner.invoke(
                    main,
                    [
                        "init",
                        "--graph-context-wiki",
                        "https://wiki.example.org/",
                        "--graph-implicit-types",
                        "schema:TechArticle",
                        "--graph-implicit-types-policy",
                        "append",
                    ],
                    catch_exceptions=False,
                )
                self.assertEqual(result.exit_code, 0)
                config_content = Path("wiki.yml").read_text(encoding="utf-8")
                self.assertIn("implicit_types:", config_content)
                self.assertIn("- schema:TechArticle", config_content)
                self.assertIn("implicit_types_policy: append", config_content)

    def test_cli_init_rejects_invalid_implicit_types_policy(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                result = runner.invoke(
                    main,
                    [
                        "init",
                        "--graph-context-wiki",
                        "https://wiki.example.org/",
                        "--graph-implicit-types-policy",
                        "override",
                    ],
                    catch_exceptions=False,
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("append", result.output)

    def test_cli_init_context_wiki_overrides_repo(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                result = runner.invoke(
                    main,
                    [
                        "init",
                        "--repo",
                        "wazootech/wiki",
                        "--graph-context-wiki",
                        "https://example.org/custom/",
                        "--site-base-url",
                        "/custom",
                    ],
                    catch_exceptions=False,
                )
                self.assertEqual(result.exit_code, 0)
                config_content = Path("wiki.yml").read_text(encoding="utf-8")
                self.assertIn("wiki: https://example.org/custom/", config_content)
                self.assertIn("wiki: https://example.org/custom/", config_content)
                self.assertIn("base_url: /custom", config_content)

    @patch("wiki.init_scaffold.detect_origin_repo", return_value="wazootech/wiki")
    def test_cli_init_detects_git_remote(self, _detect_mock) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                (Path(".git")).mkdir()
                result = runner.invoke(main, ["init"], catch_exceptions=False)
                self.assertEqual(result.exit_code, 0)
                config_content = Path("wiki.yml").read_text(encoding="utf-8")
                self.assertIn("wiki: https://wazootech.github.io/wiki/", config_content)
                self.assertNotIn("wiki_base:", config_content)
                self.assertIn("base_url: /wiki", config_content)

    def test_cli_init_rejects_existing_wiki_yaml(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                Path("wiki.yaml").write_text("wiki:\n  inputs: [wiki]\n", encoding="utf-8")
                result = runner.invoke(
                    main,
                    ["init", "--graph-context-wiki", "https://wiki.example.org/"],
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("already exists", result.output)

    def test_cli_init_invalid_repo_exits(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                result = runner.invoke(main, ["init", "--repo", "not-valid"], catch_exceptions=False)
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("Invalid GitHub repo", result.output)


    def test_config_rejects_unknown_html_template_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "wiki.yaml"
            config_path.write_text("wiki:\n  inputs: [wiki]\nhtml_template: layouts/default.html\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                Config.load(config_path)
            self.assertIn("unknown top-level keys: html_template", str(ctx.exception))

    def test_config_rejects_unknown_wiki_page_layout_key(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "wiki.yaml"
            config_path.write_text("wiki:\n  inputs: [wiki]\nwiki_page_layout: layouts/default.html\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                Config.load(config_path)
            self.assertIn("unknown top-level keys: wiki_page_layout", str(ctx.exception))

    def test_cli_init_git_opt_in_runs_git_init(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                with patch("shutil.which", return_value="git"), patch("subprocess.run") as run_mock:
                    result = runner.invoke(
                        main,
                        ["init", "--git", "--graph-context-wiki", "https://wiki.example.org/"],
                        catch_exceptions=False,
                    )

                self.assertEqual(result.exit_code, 0)
                run_mock.assert_called_once_with(
                    ["git", "init"],
                    cwd=Path.cwd(),
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertIn("Ran git init", result.output)

    def test_cli_render_single_file_scope(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            alpha = wiki_dir / "alpha.md"
            beta = wiki_dir / "beta.md"
            source = """---
type: Person
givenName: {name}
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE {{ ?s <https://schema.org/givenName> ?givenName }}
```
<!-- sparql:end -->
"""
            alpha.write_text(source.format(name="Alpha"), encoding="utf-8")
            beta.write_text(source.format(name="Beta"), encoding="utf-8")

            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", str(alpha), "--no-inference"])
            self.assertEqual(result.exit_code, 0)

            self.assertIn("Alpha", alpha.read_text(encoding="utf-8"))
            self.assertNotRegex(beta.read_text(encoding="utf-8"), r"\| givenName\s+\|")

    def test_cli_render_multiple_file_scope(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            people_dir = wiki_dir / "people"
            projects_dir = wiki_dir / "projects"
            people_dir.mkdir(parents=True)
            projects_dir.mkdir()
            source = """---
type: Person
givenName: {name}
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE {{ ?s <https://schema.org/givenName> ?givenName }}
```
<!-- sparql:end -->
"""
            person = people_dir / "alpha.md"
            project = projects_dir / "beta.md"
            person.write_text(source.format(name="Alpha"), encoding="utf-8")
            project.write_text(source.format(name="Beta"), encoding="utf-8")

            result = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "render", str(person), "--no-inference"],
            )
            self.assertEqual(result.exit_code, 0)

            self.assertRegex(person.read_text(encoding="utf-8"), r"\| givenName\s+\|")
            self.assertNotRegex(project.read_text(encoding="utf-8"), r"\| givenName\s+\|")

    def test_cli_render_rejects_non_markdown_file(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            record = wiki_dir / "person.yaml"
            record.write_text("type: Person\ngivenName: Gregory\n", encoding="utf-8")

            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", str(record), "--no-inference"])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("only supports .md files", result.output)

    def test_cli_render_second_invocation_reports_no_updates_when_current(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            source = """---
type: Person
givenName: Gregory
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
"""
            (wiki_dir / "gregory.md").write_text(source, encoding="utf-8")
            runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference"])
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", "-v"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Updated 0 files", result.output)

    def test_cli_render_cache_creates_disk_cache_artifact(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                wiki_dir = Path("wiki")
                wiki_dir.mkdir()
                source = """---
type: Person
givenName: Gregory
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
"""
                (wiki_dir / "gregory.md").write_text(source, encoding="utf-8")

                result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", "--cache"])
                self.assertEqual(result.exit_code, 0)
                cache_root = Path(".wiki") / "cache"
                self.assertTrue(cache_root.exists())
                self.assertGreater(len(list(cache_root.glob("graph-asserted-*.nt"))), 0)

    def test_cli_query_pretty(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text(
                """---
type: Person
givenName: Alice
familyName: Smith
---""",
                encoding="utf-8",
            )
            query_str = "SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }"

            result = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "--pretty", query_str],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("givenName", result.output)
            self.assertIn("Alice", result.output)

            out_file = Path(tmpdir) / "results.txt"
            result_output = runner.invoke(
                main,
                [
                    "--wiki-inputs",
                    str(wiki_dir),
                    "query",
                    "--no-inference",
                    "--pretty",
                    query_str,
                    "-o",
                    str(out_file),
                ],
            )
            self.assertEqual(result_output.exit_code, 1)
            self.assertIn("stdout only", result_output.output)

            result_json = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "query", "--no-inference", "--pretty", "-f", "json", query_str],
            )
            self.assertEqual(result_json.exit_code, 1)
            self.assertIn("table format", result_json.output)

    def test_cli_export(self) -> None:
        """Test that wiki export supports bulk and single file exports."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            
            # Create a simple page
            valid_file = wiki_dir / "gregory.md"
            valid_file.write_text("""---
type: Person
givenName: Gregory
---
""", encoding="utf-8")
            
            # Bulk export (raw default)
            result_bulk = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export"])
            self.assertEqual(result_bulk.exit_code, 0)
            data_bulk = json.loads(result_bulk.output)
            self.assertEqual(len(data_bulk), 1)
            self.assertEqual(data_bulk[0]["rdf"]["givenName"], "Gregory")
            
            # Single file export (raw default)
            result_single = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(valid_file)])
            self.assertEqual(result_single.exit_code, 0)
            data_single = json.loads(result_single.output)
            self.assertEqual(data_single["rdf"]["givenName"], "Gregory")
            
            # Single file export failure (no frontmatter)
            no_fm_file = wiki_dir / "no-fm.md"
            no_fm_file.write_text("Hello", encoding="utf-8")
            result_fail = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(no_fm_file)])
            self.assertEqual(result_fail.exit_code, 1)

            second = wiki_dir / "alice.md"
            second.write_text("""---
type: Person
givenName: Alice
---
""", encoding="utf-8")
            result_multi = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "export", str(valid_file), str(second)],
            )
            self.assertEqual(result_multi.exit_code, 0)
            data_multi = json.loads(result_multi.output)
            self.assertEqual(len(data_multi), 2)
            names = {entry["rdf"]["givenName"] for entry in data_multi}
            self.assertEqual(names, {"Gregory", "Alice"})

            result_raw_multi = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "export", "-f", "turtle", str(valid_file), str(second)],
            )
            self.assertEqual(result_raw_multi.exit_code, 1)
            self.assertIn("single FILE", result_raw_multi.output)

    def test_cli_export_supports_yaml_and_json_documents(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            yaml_file = wiki_dir / "gregory.yaml"
            json_file = wiki_dir / "alice.json"
            yaml_file.write_text("type: Person\ngivenName: Gregory\n", encoding="utf-8")
            json_file.write_text('{"type": "Person", "givenName": "Alice"}', encoding="utf-8")

            result_bulk = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export"])
            self.assertEqual(result_bulk.exit_code, 0)
            data_bulk = json.loads(result_bulk.output)
            self.assertEqual(len(data_bulk), 2)

            result_yaml = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(yaml_file)])
            self.assertEqual(result_yaml.exit_code, 0)
            self.assertEqual(json.loads(result_yaml.output)["rdf"]["givenName"], "Gregory")

            result_json = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(json_file)])
            self.assertEqual(result_json.exit_code, 0)
            self.assertEqual(json.loads(result_json.output)["rdf"]["givenName"], "Alice")
    
    def test_cli_export_formats(self) -> None:
        """Test that wiki export supports various --format options."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "alice.md"
            page.write_text("""---
type: Person
givenName: Alice
familyName: Smith
about: wiki:Alice_Theory
---
""", encoding="utf-8")
            
            # json-ld format returns expanded JSON-LD
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "json-ld"])
            self.assertEqual(result.exit_code, 0)
            data = json.loads(result.output)
            self.assertIsInstance(data["rdf"], list)
            self.assertIn("@id", data["rdf"][0])
            self.assertIn("https://schema.org/givenName", data["rdf"][0])

            # compacted JSON-LD includes @context and compacted predicates
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "json-ld", "--mode", "compacted"])
            self.assertEqual(result.exit_code, 0)
            compacted = json.loads(result.output)
            self.assertIn("@context", compacted["rdf"])
            self.assertEqual(compacted["rdf"]["@type"], "schema:Person")
            self.assertEqual(compacted["rdf"]["schema:givenName"], "Alice")
            self.assertEqual(compacted["rdf"]["schema:about"]["@id"], "wiki:Alice_Theory")
            
            # turtle format returns raw serialized turtle (no JSON wrapper)
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "turtle", "--mode", "compacted"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("schema:givenName", result.output)  # turtle has prefix:name
            self.assertIn("Alice", result.output)
            
            # xml format returns raw serialized RDF/XML
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "xml"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("rdf:Description", result.output)
            
            # nt format returns raw N-Triples
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "nt"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Alice", result.output)
            self.assertIn(".", result.output.strip()[-1])  # N-Triples ends with dot

    def test_cli_export_output_flag(self) -> None:
        """Test that wiki export -o writes to a file."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "alice.md"
            page.write_text("""---
type: Person
givenName: Alice
familyName: Smith
---""", encoding="utf-8")

            out_file = Path(tmpdir) / "export.json"
            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "export", str(page),
                "-o", str(out_file)
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Written payload", result.output)
            self.assertTrue(out_file.exists())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(data["rdf"]["givenName"], "Alice")

    def test_cli_export_short_format_flag(self) -> None:
        """Test that wiki export -f short form works for format selection."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "alice.md"
            page.write_text("""---
type: Person
givenName: Alice
familyName: Smith
---""", encoding="utf-8")

            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "export", str(page),
                "-f", "turtle"
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("schema:givenName", result.output)
            self.assertIn("Alice", result.output)

    def test_cli_export_more_formats(self) -> None:
        """Test n3, trig export formats (previously uncovered)."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "alice.md"
            page.write_text("""---
type: Person
givenName: Alice
familyName: Smith
---""", encoding="utf-8")

            # N3
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "n3"])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

            # Trig
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "trig"])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

            # MIME alias — "text/n3" resolves to "n3"
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "text/n3"])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

            # Case-insensitive — "TURTLE" accepted
            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "TURTLE"])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("Alice", res.output)

    def test_cli_export_nquads(self) -> None:
        """Test nquads export format (uses Dataset wrapper internally)."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "doc.md"
            page.write_text("""---
type: schema:WebPage
id: wiki:doc
name: TestDoc
---""", encoding="utf-8")

            res = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "export", str(page), "--format", "nquads"])
            self.assertEqual(res.exit_code, 0)
            # Raw N-Quads output: angle-bracketed URIs, not JSON
            self.assertNotIn("{", res.output, msg="Raw nquads output should not be JSON")
            self.assertIn("<", res.output, msg="N-Quads output should contain URIs")
            self.assertIn('"TestDoc"', res.output, msg="N-Quads output should contain the literal value")

    def test_cli_graph_list(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            source_dir.mkdir(parents=True)
            (root / "wiki.yml").write_text("""wiki:
  inputs:
    - wiki
    - .wiki/sources/brain/repo/wiki
sources:
  - name: brain
    type: git
    url: https://example.com/brain.git
""", encoding="utf-8")
            (root / "wiki.lock").write_text(json.dumps({
                "version": 2,
                "sources": {
                    "brain": {
                        "url": "https://example.com/brain.git",
                        "resolved_ref": "abcdef1234567890",
                        "path": "wiki",
                        "fetched_at": "2026-01-01T00:00:00+00:00",
                        "required_by": [],
                    }
                },
            }), encoding="utf-8")

            res = runner.invoke(main, ["-c", str(root), "graph", "list"])

            self.assertEqual(res.exit_code, 0)
            self.assertIn("graphs/root", res.output)
            self.assertIn("brain", res.output)
            self.assertIn("graphs/source/brain", res.output)
            self.assertIn("abcdef123456", res.output)
            self.assertIn("root", res.output)

    def test_cli_build_with_render_named_graph_query(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            wiki_dir.mkdir()
            source_dir.mkdir(parents=True)
            (root / "wiki.yaml").write_text(
                yaml.dump({
                    "wiki": {"inputs": ["wiki", ".wiki/sources/brain/repo/wiki"]},
                    "site": {"base_url": "/wiki"},
                }),
                encoding="utf-8",
            )
            (root / "wiki.lock").write_text(json.dumps({
                "version": 2,
                "sources": {
                    "brain": {
                        "url": "https://example.com/brain.git",
                        "resolved_ref": "abcdef1234567890",
                        "path": "wiki",
                        "fetched_at": "2026-01-01T00:00:00+00:00",
                        "required_by": ["root"],
                    }
                },
            }), encoding="utf-8")
            page = wiki_dir / "report.md"
            page.write_text(
                """# Report
<!-- sparql:start -->
```sparql
SELECT ?graph ?name WHERE { GRAPH ?graph { ?s <https://schema.org/name> ?name } }
```
<!-- sparql:end -->
""",
                encoding="utf-8",
            )
            (source_dir / "source.md").write_text("---\ntype: Person\nname: Source Person\n---\n", encoding="utf-8")

            result = runner.invoke(
                main,
                ["-c", str(root), "build", "--output-dir", str(root / "_site"), "--render", "--no-check"],
            )

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("Source Person", page.read_text(encoding="utf-8"))
            html = (root / "_site" / "wiki" / "report" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Source Person", html)

    def test_cli_build(self) -> None:
        """Test that wiki build generates static HTML site with clean directory URLs by default."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()

            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---
# Alice
Hello from Alice.

See also [[bob]].""", encoding="utf-8")

            (wiki_dir / "bob.md").write_text("""---
type: Person
givenName: Bob
---
# Bob
Hello from Bob.

## Early Life
Bob was born.""", encoding="utf-8")

            output_dir = Path(tmpdir) / "_site"

            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "build", "--output-dir", str(output_dir), "-v"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Built", result.output)

            self.assertTrue((output_dir / "wiki" / "index.html").exists())
            self.assertTrue((output_dir / "wiki" / "alice" / "index.html").exists())
            self.assertTrue((output_dir / "wiki" / "bob" / "index.html").exists())
            self.assertFalse((output_dir / "wiki" / "bob" / "early-life" / "index.html").exists())

            index_content = (output_dir / "wiki" / "index.html").read_text()
            self.assertIn("Alice", index_content)
            self.assertIn("Bob", index_content)
            self.assertIn('href="/wiki/alice/"', index_content)
            self.assertIn('href="/wiki/bob/"', index_content)
            self.assertNotIn("early-life", index_content)

            alice_content = (output_dir / "wiki" / "alice" / "index.html").read_text()
            self.assertIn("Hello from Alice", alice_content)
            self.assertIn('/wiki/bob/', alice_content)

    def test_cli_build_with_render(self) -> None:
        """Test that wiki build --render updates dynamic blocks before generating site."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()

            file_path = wiki_dir / "person.md"
            file_path.write_text("""---
type: Person
givenName: Charlie
---
# Charlie
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
""", encoding="utf-8")

            output_dir = Path(tmpdir) / "_site"

            # Run build with --render and -v
            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "build", "--output-dir", str(output_dir), "--render", "-v"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Rendered SPARQL dynamic blocks", result.output)

            # Check that the source file itself was updated inline
            updated_content = file_path.read_text(encoding="utf-8")
            self.assertIn("Charlie", updated_content)
            self.assertRegex(updated_content, r"\| givenName\s+\|")  # It constructs a markdown table

            # Check that the generated HTML contains the rendered content
            html_content = (output_dir / "wiki" / "person" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Charlie", html_content)

    def test_cli_render_check_is_idempotent_for_sparql_blocks(self) -> None:
        """Rendered SPARQL blocks must be stable across render and render --check."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            page = wiki_dir / "person.md"
            page.write_text(
                """---
type: Person
givenName: Charlie
---
<!-- sparql:start -->
```sparql
SELECT ?givenName WHERE { ?s <https://schema.org/givenName> ?givenName }
```
<!-- sparql:end -->
""",
                encoding="utf-8",
            )

            render = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", str(page)],
            )
            self.assertEqual(render.exit_code, 0)

            check = runner.invoke(
                main,
                ["--wiki-inputs", str(wiki_dir), "render", "--no-inference", "--check", str(page)],
            )
            self.assertEqual(check.exit_code, 0, check.output)

    def test_cli_build_dir_style(self) -> None:
        """Test that wiki build --site-url-style dir produces <slug>/index.html with clean links."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()

            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---
# Alice
Hello from Alice.

See also [[bob]].""", encoding="utf-8")

            (wiki_dir / "bob.md").write_text("""---
type: Person
givenName: Bob
---
# Bob
Hello from Bob.

## Early Life
Bob was born.""", encoding="utf-8")

            output_dir = Path(tmpdir) / "_site"

            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "build", "--output-dir", str(output_dir), "--site-url-style", "dir", "-v"])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Built", result.output)

            self.assertTrue((output_dir / "wiki" / "index.html").exists())
            self.assertTrue((output_dir / "wiki" / "alice" / "index.html").exists())
            self.assertTrue((output_dir / "wiki" / "bob" / "index.html").exists())
            self.assertFalse((output_dir / "wiki" / "bob" / "early-life" / "index.html").exists())

            index_content = (output_dir / "wiki" / "index.html").read_text()
            self.assertIn('href="/wiki/alice/"', index_content)
            self.assertIn('href="/wiki/bob/"', index_content)
            self.assertNotIn('href="/wiki/bob/early-life/"', index_content)

            alice_content = (output_dir / "wiki" / "alice" / "index.html").read_text()
            self.assertIn("Hello from Alice", alice_content)
            self.assertIn('href="/wiki/bob/"', alice_content)

    def test_cli_build_with_base_url(self) -> None:
        """Test that wiki build --site-base-url prefixes all paths."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()

            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---
# Alice
Hello from [[bob]].""", encoding="utf-8")

            (wiki_dir / "bob.md").write_text("""---
type: Person
givenName: Bob
---
# Bob
Hello from [[alice]].""", encoding="utf-8")

            output_dir = Path(tmpdir) / "_site"

            result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "build", "--output-dir", str(output_dir), "--site-base-url", "/my-wiki"])
            self.assertEqual(result.exit_code, 0)

            alice_content = (output_dir / "my-wiki" / "alice" / "index.html").read_text()
            self.assertIn('/my-wiki/bob/', alice_content)
            self.assertIn('/my-wiki/', alice_content)

            index_content = (output_dir / "my-wiki" / "index.html").read_text()
            self.assertIn('/my-wiki/', index_content)

    def test_cli_build_no_wiki_dir(self) -> None:
        """Test that wiki build errors when wiki directory missing."""
        runner = CliRunner()
        result = runner.invoke(main, ["--wiki-inputs", "nonexistent", "build"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Error", result.output)

    def test_cli_build_rejects_output_overlapping_config_root(self) -> None:
        """Build must not wipe the config root when --output-dir overlaps it."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            wiki_dir = config_dir / "wiki"
            wiki_dir.mkdir()
            page = wiki_dir / "page.md"
            page.write_text("# Page\n", encoding="utf-8")
            (config_dir / "wiki.yaml").write_text("wiki:\n  inputs:\n    - wiki\n", encoding="utf-8")

            result = runner.invoke(main, [
                "-c", str(config_dir),
                "build",
                "--output-dir", str(config_dir),
                "--site-base-url", "",
                "--no-check",
            ])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("refusing to clean build output path", result.output)
            self.assertTrue(page.exists())

    def test_cli_build_rejects_output_containing_wiki_inputs(self) -> None:
        """Build must not wipe a parent directory that contains wiki inputs."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            page = wiki_dir / "page.md"
            page.write_text("# Page\n", encoding="utf-8")

            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "build",
                "--output-dir", str(root),
                "--site-base-url", "",
                "--no-check",
            ])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("overlaps wiki input", result.output)
            self.assertTrue(page.exists())

    def test_cli_build_rejects_output_equal_to_wiki_input(self) -> None:
        """Build must not use the wiki input directory itself as page output."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            page = wiki_dir / "page.md"
            page.write_text("# Page\n", encoding="utf-8")

            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "build",
                "--output-dir", str(wiki_dir),
                "--site-base-url", "",
                "--no-check",
            ])
            self.assertEqual(result.exit_code, 1)
            self.assertIn("overlaps wiki input", result.output)
            self.assertTrue(page.exists())

    def test_global_raw_dir_flag(self) -> None:
        """Test --wiki-inputs with multiple directories: loads files from both."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            wiki_dir = config_dir / "wiki"
            wiki_dir.mkdir()
            raw_dir = config_dir / "raw"
            raw_dir.mkdir()
            (config_dir / "wiki.yaml").write_text("""wiki:
  inputs:
    - wiki
    - raw
""", encoding="utf-8")
            (wiki_dir / "doc.md").write_text("""---
type: schema:WebPage
id: wiki:doc
name: FromWiki
---""", encoding="utf-8")
            (raw_dir / "note.md").write_text("""---
type: schema:WebPage
id: wiki:note
name: FromRaw
---""", encoding="utf-8")

            result = runner.invoke(main, [
                "-c", str(config_dir),
                "query", "--no-inference",
                "SELECT ?name WHERE { ?s <https://schema.org/name> ?name } ORDER BY ?name",
                "-f", "json",
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("FromWiki", result.output)
            self.assertIn("FromRaw", result.output)

    def test_global_import_dir_flag(self) -> None:
        """Test repeatable --wiki-inputs: loads external .ttl into the graph."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            imports_dir = Path(tmpdir) / "imports"
            imports_dir.mkdir()
            (wiki_dir / "doc.md").write_text("""---
type: schema:WebPage
id: wiki:doc
---""", encoding="utf-8")
            (imports_dir / "extra.ttl").write_text("""
@prefix ex: <http://example.org/> .
ex:foo ex:bar "from-import-dir" .
""", encoding="utf-8")

            result = runner.invoke(main, [
                "--wiki-inputs", str(wiki_dir),
                "--wiki-inputs", str(imports_dir),
                "query", "--no-inference",
                "SELECT ?o WHERE { ?s <http://example.org/bar> ?o }",
                "-f", "json",
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("from-import-dir", result.output)

    def test_server_serve_real_request(self) -> None:
        """Test wiki serve with real --host/--port via HTTP request."""
        import socket

        from wiki.config import Config
        from wiki.serve import run_server

        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
familyName: Smith
---
# Alice
Hello from server test.
""", encoding="utf-8")

            # Find a free port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()

            config = Config(wiki={"inputs": [wiki_dir]}, config_root=wiki_dir)
            server_thread = threading.Thread(
                target=run_server,
                args=(config,),
                kwargs={"host": "127.0.0.1", "port": port},
                daemon=True,
            )
            server_thread.start()
            time.sleep(0.5)

            try:
                resp = urlopen(f"http://127.0.0.1:{port}/wiki/alice", timeout=5)
                html = resp.read().decode("utf-8")
                self.assertIn("Hello from server test", html)
                self.assertIn("Alice", html)
            except URLError:
                self.fail("Server did not respond in time")

    def test_server_serve_custom_base_url(self) -> None:
        """Test wiki serve with custom --site-base-url."""
        import socket

        from wiki.config import Config
        from wiki.serve import run_server

        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "bob.md").write_text("""---
type: Person
givenName: Bob
---
# Bob
Custom base URL test.
""", encoding="utf-8")

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()

            config = Config(wiki={"inputs": [wiki_dir]}, config_root=wiki_dir)
            server_thread = threading.Thread(
                target=run_server,
                args=(config,),
                kwargs={"host": "127.0.0.1", "port": port, "base_url": ""},
                daemon=True,
            )
            server_thread.start()
            time.sleep(0.5)

            try:
                resp = urlopen(f"http://127.0.0.1:{port}/bob", timeout=5)
                html = resp.read().decode("utf-8")
                self.assertIn("Custom base URL test", html)
                self.assertIn("Bob", html)
            except URLError:
                self.fail("Server did not respond in time")

    def test_global_config_flag(self) -> None:
        """Test -c/--config: loads wiki.yaml from a specified directory."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            (wiki_dir / "doc.md").write_text("""---
type: schema:WebPage
id: wiki:doc
name: ConfigTest
---""", encoding="utf-8")
            (config_dir / "wiki.yaml").write_text("wiki:\n  inputs: ../wiki\n", encoding="utf-8")

            result = runner.invoke(main, [
                "-c", str(config_dir),
                "query", "--no-inference",
                "SELECT ?name WHERE { ?s <https://schema.org/name> ?name }",
                "-f", "json",
            ])
            self.assertEqual(result.exit_code, 0)
            self.assertIn("ConfigTest", result.output)

    def test_cli_errors_on_invalid_config_keys(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "wiki.yaml").write_text("inputDirs: wiki\n", encoding="utf-8")

            result = runner.invoke(main, ["-c", str(root), "check"])

            self.assertEqual(result.exit_code, 1)
            self.assertIn("Invalid config file wiki.yaml", result.output)
            self.assertIn("unknown top-level keys", result.output)

    def test_cli_link_apply_and_check(self) -> None:
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            (wiki_dir / "wiki.md").write_text("# Wiki CLI\n", encoding="utf-8")
            guide = wiki_dir / "Guide.md"
            guide.write_text("# Guide\n\nRead the Wiki CLI guide.\n", encoding="utf-8")

            report = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "link", "--check"])
            self.assertEqual(report.exit_code, 1)
            self.assertIn("Wiki CLI", report.output)

            apply_result = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "link", "--apply"])
            self.assertEqual(apply_result.exit_code, 0)
            self.assertIn("[Wiki CLI](wiki.md)", guide.read_text(encoding="utf-8"))

            clean = runner.invoke(main, ["--wiki-inputs", str(wiki_dir), "link", "--check"])
            self.assertEqual(clean.exit_code, 0)


    def test_cli_init_with_template(self) -> None:
        """Test that wiki init --template clones and copies a template."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                from unittest.mock import patch, MagicMock
                import shutil
                from pathlib import Path as P

                # Create a fake wiki-templates monorepo with a generic template
                fake_templates_dir = P(tmpdir) / "fake-templates"
                fake_templates_dir.mkdir()
                generic_dir = fake_templates_dir / "generic"
                generic_dir.mkdir()
                (generic_dir / "wiki.yml").write_text(
                    "wiki:\n  inputs:\n    - wiki\n", encoding="utf-8"
                )
                (generic_dir / "README.md").write_text(
                    "# Generic Wiki\n", encoding="utf-8"
                )
                wiki_subdir = generic_dir / "wiki"
                wiki_subdir.mkdir()
                (wiki_subdir / "Page.md").write_text(
                    "---\ntype: schema:WebPage\n---\n", encoding="utf-8"
                )

                def fake_run(args, **kwargs):
                    if "clone" in args:
                        clone_dest = P(args[-1])
                        shutil.copytree(fake_templates_dir, clone_dest)
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
                    return result

                with patch("wiki.init_scaffold.subprocess.run", side_effect=fake_run):
                    result = runner.invoke(
                        main,
                        ["init", "--template", "generic"],
                        catch_exceptions=False,
                    )

                self.assertEqual(result.exit_code, 0)
                self.assertIn("generic", result.output)
                self.assertTrue(Path("wiki.yml").exists())
                self.assertTrue(Path("README.md").exists())
                self.assertTrue((Path("wiki") / "Page.md").exists())
                content = Path("wiki.yml").read_text(encoding="utf-8")
                self.assertIn("inputs:", content)
                self.assertIn("wiki", content)

    def test_cli_init_with_template_and_repo(self) -> None:
        """Test that wiki init --template --repo works."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                from unittest.mock import patch, MagicMock
                import shutil
                from pathlib import Path as P

                fake_templates_dir = P(tmpdir) / "fake-templates"
                fake_templates_dir.mkdir()
                generic_dir = fake_templates_dir / "generic"
                generic_dir.mkdir()
                (generic_dir / "wiki.yml").write_text(
                    "wiki:\n  inputs:\n    - wiki\n", encoding="utf-8"
                )
                (generic_dir / "README.md").write_text(
                    "# Generic Wiki\n", encoding="utf-8"
                )
                wiki_subdir = generic_dir / "wiki"
                wiki_subdir.mkdir()
                (wiki_subdir / "Page.md").write_text(
                    "---\ntype: schema:WebPage\n---\n", encoding="utf-8"
                )

                def fake_run(args, **kwargs):
                    if "clone" in args:
                        clone_dest = P(args[-1])
                        shutil.copytree(fake_templates_dir, clone_dest)
                    result = MagicMock()
                    result.returncode = 0
                    result.stdout = ""
                    result.stderr = ""
                    return result

                with patch("wiki.init_scaffold.subprocess.run", side_effect=fake_run):
                    result = runner.invoke(
                        main,
                        ["init", "--template", "generic", "--repo", "wazootech/wiki"],
                        catch_exceptions=False,
                    )

                self.assertEqual(result.exit_code, 0)
                self.assertIn("generic", result.output)
                self.assertTrue(Path("wiki.yml").exists())
                self.assertTrue(Path("README.md").exists())

    def test_cli_init_with_template_rejects_existing_config(self) -> None:
        """Test that wiki init --template fails if wiki.yml already exists."""
        runner = CliRunner()
        with TemporaryDirectory() as tmpdir:
            with runner.isolated_filesystem(temp_dir=tmpdir):
                Path("wiki.yml").write_text("wiki:\n  inputs:\n    - wiki\n", encoding="utf-8")
                result = runner.invoke(
                    main,
                    ["init", "--template", "generic"],
                )
                self.assertNotEqual(result.exit_code, 0)
                self.assertIn("already exists", result.output)


if __name__ == "__main__":
    unittest.main()
