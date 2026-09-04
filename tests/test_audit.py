import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from wiki.audit import (
    _run_lint as run_lint,
)
from wiki.audit import (
    check_layout_frontmatter,
    check_shacl_all,
    check_shacl_file,
    lint_broken_links,
    lint_duplicate_headings,
    lint_filenames,
    lint_heading_levels,
    lint_headings,
    lint_link_style,
    lint_thematic_breaks,
    load_shapes,
)
from wiki.config import Config


class TestChecking(unittest.TestCase):
    def test_lint_filenames_validation(self) -> None:
        """Test auditing of filenames for lowercase kebab-case naming standard."""
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir], "filename_pattern": r"[a-z0-9-]+\.md"})
            
            # Create valid and invalid files
            valid_path = Path(tmpdir) / "valid-kebab-case.md"
            invalid_path = Path(tmpdir) / "Invalid_Name.md"
            
            valid_path.write_text("content", encoding="utf-8")
            invalid_path.write_text("content", encoding="utf-8")
            
            warnings = lint_filenames(config)
            self.assertEqual(len(warnings), 1)
            self.assertIn("Filename 'Invalid_Name.md' does not match filename_pattern.", warnings[0])

    def test_lint_broken_links_validation(self) -> None:
        """Test auditing of internal link structures (WikiLinks and Markdown links)."""
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            
            # Create one target file
            target_path = Path(tmpdir) / "target-page.md"
            target_path.write_text("content", encoding="utf-8")
            
            # Create a source file with both valid and broken links
            source_content = """---
id: wiki:source
type: Person
---
Here is a valid WikiLink [[target-page]] and a broken WikiLink [[non-existent-page]].
And a valid Markdown link [Target](target-page.md) and a broken Markdown link [Broken](missing.md).
"""
            source_path = Path(tmpdir) / "source-page.md"
            source_path.write_text(source_content, encoding="utf-8")
            
            warnings = lint_broken_links(config)
            
            # Verify exactly the two broken links are reported
            self.assertEqual(len(warnings), 2)
            self.assertTrue(any("Broken WikiLink [non-existent-page]" in w for w in warnings))
            self.assertTrue(any("Broken Markdown link [missing.md]" in w for w in warnings))

    def test_audit_broken_wiki_curie_in_frontmatter(self) -> None:
        """Frontmatter wiki: CURIEs must resolve to an existing document route."""
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "wiki.md").write_text("---\ntype: SoftwareApplication\n---\n", encoding="utf-8")
            Path(tmpdir, "Farzapedia.md").write_text(
                "---\ntype: TechArticle\nabout: wiki:wiki-cli\n---\n",
                encoding="utf-8",
            )

            warnings = lint_broken_links(config)
            self.assertEqual(len(warnings), 1)
            self.assertIn("wiki:wiki-cli", warnings[0])
            self.assertIn("Metadata reference", warnings[0])

    def test_wiki_curie_with_fragment_resolves_to_page_route(self) -> None:
        """wiki:Page#fragment refers to the same wiki route as wiki:Page."""
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Microdata.md").write_text(
                '---\ntype: TechArticle\n---\n<div itemid="wiki:Microdata#example"></div>\n',
                encoding="utf-8",
            )
            self.assertEqual(lint_broken_links(config), [])

    def test_markdown_can_link_to_yaml_document(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})

            yml_target = Path(tmpdir) / "yml-target.yml"
            yml_target.write_text("type: Thing\nname: YML\n", encoding="utf-8")
            yaml_target = Path(tmpdir) / "yaml-target.yaml"
            yaml_target.write_text("type: Thing\nname: YAML\n", encoding="utf-8")

            source_path = Path(tmpdir) / "source-page.md"
            source_path.write_text("See [[yml-target]], [[yaml-target]].", encoding="utf-8")

            warnings = lint_broken_links(config)
            self.assertEqual(warnings, [])

    def test_lint_filenames_skips_yaml_documents(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir], "filename_pattern": r"[a-z0-9-]+\.md"})

            Path(tmpdir, "Invalid_Name.yml").write_text("type: Thing\n", encoding="utf-8")
            Path(tmpdir, "Invalid_Name.yaml").write_text("type: Thing\n", encoding="utf-8")
            Path(tmpdir, "valid-name.md").write_text("content", encoding="utf-8")

            warnings = lint_filenames(config)
            self.assertEqual(warnings, [])

    def test_load_shapes_edge_cases(self) -> None:
        """Test load_shapes behaves predictably with different underlying graph states."""
        from rdflib import Graph

        from wiki.graph import load_graph

        # Empty graph
        with TemporaryDirectory() as tmpdir:
            data_graph = Graph()
            shapes = load_shapes(data_graph)
            self.assertEqual(len(shapes), 0)
            
            # Loading from configuration with missing directories
            config = Config(wiki={"input": [Path(tmpdir) / "non-existent"]})
            data_graph_conf = load_graph(config, infer=False)
            shapes_conf = load_shapes(data_graph_conf)
            self.assertEqual(len(shapes_conf), 0)

    def test_check_shacl_file_and_all(self) -> None:
        """Test check_shacl_file and check_shacl_all for conformance."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            
            # Create a basic shape file alongside the wiki files
            shape_content = """
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
    ] .
"""
            (wiki_dir / "person-shape.ttl").write_text(shape_content, encoding="utf-8")
            config = Config(wiki={"input": [wiki_dir]})
            
            # 1. No frontmatter -> check_shacl_file returns None
            no_fm_file = wiki_dir / "no-fm.md"
            no_fm_file.write_text("just text", encoding="utf-8")
            self.assertIsNone(check_shacl_file(no_fm_file, config))
            
            # 2. File with valid Person (givenName present)
            valid_person = wiki_dir / "valid-person.md"
            valid_person.write_text("""---
type: Person
givenName: Gregory
---
""", encoding="utf-8")
            res_valid = check_shacl_file(valid_person, config)
            self.assertIsNotNone(res_valid)
            self.assertTrue(res_valid[0])  # conforms
            
            # 3. File with invalid Person (missing givenName)
            invalid_person = wiki_dir / "invalid-person.md"
            invalid_person.write_text("""---
type: Person
---
""", encoding="utf-8")
            res_invalid = check_shacl_file(invalid_person, config)
            self.assertIsNotNone(res_invalid)
            self.assertFalse(res_invalid[0])  # does not conform
            
            # 4. Test check_shacl_all integrates both
            conforms_all, results_all = check_shacl_all(config)
            self.assertFalse(conforms_all)

    def test_run_lint_severity_and_promotion(self) -> None:
        """Test run_lint respects configuration for warning levels and promotions."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)

            invalid_file = wiki_dir / "Invalid_Name.md"
            invalid_file.write_text("""---
type: schema:WebPage
---
""", encoding="utf-8")

            config_warning = Config(
                wiki={"input": [wiki_dir], "filename_pattern": r"[a-z0-9-]+\.md"},
                lint={"filename_pattern": "warning"},
            )
            res_warning = run_lint(config_warning)
            self.assertTrue(res_warning.ok)
            self.assertEqual(len(res_warning.warnings), 1)
            self.assertEqual(len(res_warning.errors), 0)

            config_error = Config(
                wiki={"input": [wiki_dir], "filename_pattern": r"[a-z0-9-]+\.md"},
                lint={"filename_pattern": "error"},
            )
            res_error = run_lint(config_error)
            self.assertFalse(res_error.ok)
            self.assertEqual(len(res_error.warnings), 0)
            self.assertEqual(len(res_error.errors), 1)

            config_off = Config(
                wiki={"input": [wiki_dir], "filename_pattern": r"[a-z0-9-]+\.md"},
                lint={"filename_pattern": "off"},
            )
            res_off = run_lint(config_off)
            self.assertTrue(res_off.ok)
            self.assertEqual(len(res_off.warnings), 0)
            self.assertEqual(len(res_off.errors), 0)

    def test_filename_pattern_reports_non_matching_names(self) -> None:
        """Custom filename_pattern controls filename hygiene without preset styles."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "Ethan_Davidson.md").write_text("---\ntype: schema:Person\n---\n", encoding="utf-8")
            (wiki_dir / "ethan-davidson.md").write_text("---\ntype: schema:Person\n---\n", encoding="utf-8")

            config = Config(wiki={"input": [wiki_dir], "filename_pattern": r"[A-Z][A-Za-z0-9_]*\.md"})
            res = run_lint(config)

            self.assertTrue(res.ok)
            self.assertEqual(len(res.warnings), 1)
            self.assertIn("ethan-davidson.md", res.warnings[0].message)

    def test_wikilink_resolution_requires_path_specifier_target(self) -> None:
        """Wikilinks use path specifiers and do not space-normalize targets."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "Ethan_Davidson.md").write_text("---\ntype: schema:Person\n---\n", encoding="utf-8")
            (wiki_dir / "Source.md").write_text(
                "---\ntype: schema:CreativeWork\n---\n\nSee [[Ethan Davidson]].",
                encoding="utf-8",
            )

            config = Config(wiki={"input": [wiki_dir]})
            res = run_lint(config)

            self.assertTrue(any("Broken WikiLink [Ethan Davidson]" in w.message for w in res.warnings))

    def test_lint_headings_numbered_and_thematic_break(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            page = Path(tmpdir) / "Bad.md"
            page.write_text(
                "---\ntype: TechArticle\n---\n## 1. First step\n\n---\n\nBody.\n",
                encoding="utf-8",
            )
            heading_warnings = lint_headings(config)
            thematic_warnings = lint_thematic_breaks(config)
            self.assertTrue(any("Numbered heading" in w for w in heading_warnings))
            self.assertFalse(any("Thematic break" in w for w in heading_warnings))
            self.assertTrue(any("Thematic break" in w for w in thematic_warnings))

    def test_lint_headings_title_case(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Related Standards Guide\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertTrue(any("title case" in w for w in warnings))

    def test_lint_headings_h1_title_case_not_flagged(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n# Agent Memory Filesystems\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("title case" in w for w in warnings))

    def test_lint_headings_h2_title_case_flagged(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Agent Memory Filesystems\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertTrue(any("title case" in w for w in warnings))

    def test_lint_headings_setext_not_warned(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\nMy Title\n=======\n\nBody.\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("Setext heading" in w for w in warnings))

    def test_lint_headings_setext_h2_not_warned(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\nSection title\n---------\n\nBody.\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("Setext heading" in w for w in warnings))

    def test_lint_headings_atx_does_not_warn_setext(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n# My Title\n\n## Section title\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("Setext heading" in w for w in warnings))

    def test_lint_headings_skips_setext_inside_fenced_code(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Example.md").write_text(
                "---\ntype: TechArticle\n---\n```markdown\nTitle\n===\n```\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("Setext heading" in w for w in warnings))

    def test_lint_headings_skips_thematic_break_inside_fenced_code(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Example.md").write_text(
                "---\ntype: TechArticle\n---\n```yaml\n---\nname: Example\n---\n```\n",
                encoding="utf-8",
            )
            warnings = lint_thematic_breaks(config)
            self.assertFalse(any("Thematic break" in w for w in warnings))

    def test_lint_headings_allows_proper_noun_headings(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Deploy.md").write_text(
                "---\ntype: TechArticle\n---\n# Deploying to GitHub Pages\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("title case" in w for w in warnings))

    def test_lint_headings_ignores_capitalized_link_text_in_headings(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Compare.md").write_text(
                "---\ntype: TechArticle\n---\n"
                "## Comparison with [Wiki CLI](wiki.md) and [Letta MemFS](Letta_MemFS.md)\n",
                encoding="utf-8",
            )
            warnings = lint_headings(config)
            self.assertFalse(any("title case" in w for w in warnings))

    def test_lint_heading_levels_skip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n# A\n\n### C\n",
                encoding="utf-8",
            )
            warnings = lint_heading_levels(config)
            self.assertEqual(len(warnings), 1)
            self.assertIn("skips level h2", warnings[0])

    def test_lint_heading_levels_ok_increment(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n# A\n\n## B\n\n### C\n",
                encoding="utf-8",
            )
            self.assertEqual(lint_heading_levels(config), [])

    def test_lint_heading_levels_first_h2_ok(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Intro\n",
                encoding="utf-8",
            )
            self.assertEqual(lint_heading_levels(config), [])

    def test_lint_heading_levels_skips_fenced_code(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Real\n\n```md\n# Fake\n### Also fake\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(lint_heading_levels(config), [])

    def test_lint_duplicate_headings_h2(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Foo\n\nBody.\n\n## Foo\n",
                encoding="utf-8",
            )
            warnings = lint_duplicate_headings(config)
            self.assertEqual(len(warnings), 1)
            self.assertIn("Duplicate heading", warnings[0])
            self.assertIn("first at line", warnings[0])

    def test_lint_duplicate_headings_h1_allowed(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n# Foo\n\n# Foo\n",
                encoding="utf-8",
            )
            self.assertEqual(lint_duplicate_headings(config), [])

    def test_lint_duplicate_headings_case_insensitive(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Foo\n\n## foo\n",
                encoding="utf-8",
            )
            warnings = lint_duplicate_headings(config)
            self.assertEqual(len(warnings), 1)

    def test_lint_duplicate_headings_skips_fenced_code(self) -> None:
        with TemporaryDirectory() as tmpdir:
            config = Config(wiki={"input": [tmpdir]})
            Path(tmpdir, "Page.md").write_text(
                "---\ntype: TechArticle\n---\n## Foo\n\n```\n## Foo\n```\n",
                encoding="utf-8",
            )
            self.assertEqual(lint_duplicate_headings(config), [])

    def test_lint_link_style_flags_wikilinks_when_standard(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = Path(tmpdir) / "wiki"
            wiki.mkdir()
            (wiki / "Target.md").write_text("# Target\n", encoding="utf-8")
            (wiki / "Guide.md").write_text(
                "# Guide\n\nSee [[Target]] for details.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=Path(tmpdir))
            warnings = lint_link_style(config)
            self.assertEqual(len(warnings), 1)
            self.assertIn("Wikilink '[[Target]]'", warnings[0])

    def test_lint_link_style_skips_inline_code_and_wikilink_config(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = Path(tmpdir) / "wiki"
            wiki.mkdir()
            (wiki / "Guide.md").write_text(
                "# Guide\n\nLiteral `[[Target]]` and fenced:\n\n```\n[[Target]]\n```\n",
                encoding="utf-8",
            )
            standard_config = Config(wiki={"input": [wiki]}, config_root=Path(tmpdir))
            self.assertEqual(lint_link_style(standard_config), [])

            wikilink_config = Config(
                wiki={"input": [wiki]},
                config_root=Path(tmpdir),
                link={"style": "wikilink"},
            )
            (wiki / "Guide.md").write_text(
                "# Guide\n\nSee [[Target]] for details.\n",
                encoding="utf-8",
            )
            self.assertEqual(lint_link_style(wikilink_config), [])

    def test_run_lint_link_style_severity(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki = Path(tmpdir) / "wiki"
            wiki.mkdir()
            (wiki / "Guide.md").write_text("# Guide\n\nSee [[Target]].\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=Path(tmpdir), lint={"link_style": "error"})
            res = run_lint(config)
            self.assertFalse(res.ok)
            self.assertTrue(any("Wikilink" in e.message for e in res.errors))

    def test_run_lint_headings_severity(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            (wiki_dir / "x.md").write_text(
                "---\ntype: TechArticle\n---\n## 1. Bad\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki_dir]}, lint={"headings": "error"})
            res = run_lint(config)
            self.assertFalse(res.ok)
            self.assertTrue(any("Numbered heading" in e.message for e in res.errors))

    def test_run_lint_heading_levels_severity(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            (wiki_dir / "x.md").write_text(
                "---\ntype: TechArticle\n---\n# A\n\n### C\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki_dir]}, lint={"heading_levels": "error"})
            res = run_lint(config)
            self.assertFalse(res.ok)
            self.assertTrue(any("skips level" in e.message for e in res.errors))

    def test_run_lint_duplicate_headings_severity(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            (wiki_dir / "x.md").write_text(
                "---\ntype: TechArticle\n---\n## Foo\n\n## Foo\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki_dir]}, lint={"duplicate_headings": "error"})
            res = run_lint(config)
            self.assertFalse(res.ok)
            self.assertTrue(any("Duplicate heading" in e.message for e in res.errors))

    def test_frontmatter_defined_shapes(self) -> None:
        """Test that SHACL shapes defined in markdown frontmatter are loaded and enforced."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()

            config = Config(wiki={"input": [wiki_dir]})

            # Create a shape inside markdown frontmatter
            shape_file = wiki_dir / "project-shape.md"
            shape_file.write_text("""---
id: wiki:ProjectShape
type: sh:NodeShape
sh:targetClass: schema:Project
sh:property:
  - sh:path: schema:name
    sh:minCount: 1
    sh:datatype: xsd:string
---
# Project Shape
""", encoding="utf-8")

            # Create an invalid project (missing name)
            invalid_project = wiki_dir / "invalid-project.md"
            invalid_project.write_text("""---
type: Project
---
""", encoding="utf-8")

            # Create a valid project
            valid_project = wiki_dir / "valid-project.md"
            valid_project.write_text("""---
type: Project
name: Wiki CLI
---
""", encoding="utf-8")

            # Validate the invalid project
            res_invalid = check_shacl_file(invalid_project, config)
            self.assertIsNotNone(res_invalid)
            self.assertFalse(res_invalid[0])  # Should NOT conform because of missing name

            # Validate the valid project
            res_valid = check_shacl_file(valid_project, config)
            self.assertIsNotNone(res_valid)
            self.assertTrue(res_valid[0])  # Should conform

    def test_check_layout_frontmatter_requires_existing_html_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text(
                "---\ntype: TechArticle\nwazoo:layout: layouts/missing.html\n---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            issues = check_layout_frontmatter(config)
            self.assertEqual(len(issues), 1)
            self.assertIn("layouts/missing.html", issues[0])

    def test_check_layout_frontmatter_accepts_html_layout(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            layouts = root / "layouts"
            layouts.mkdir()
            wiki.mkdir()
            (layouts / "plain.html").write_text("<html>%wiki.body%</html>", encoding="utf-8")
            (wiki / "page.md").write_text(
                "---\ntype: TechArticle\nwazoo:layout: layouts/plain.html\n---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            issues = check_layout_frontmatter(config)
            self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()
