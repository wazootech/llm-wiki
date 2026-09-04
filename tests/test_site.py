import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from layout_helpers import write_layout
from wiki.config import Config
from wiki.init_scaffold import load_packaged_official_layout
from wiki.site import (
    build_index_html,
    build_page_html,
    build_site,
    render_copyable_pre,
    render_outline_title,
    render_wiki_markdown,
    strip_leading_title_heading,
)

_FULL_TEST_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
%wiki.head%
</head>
<body>
<article id="article-top">
%wiki.body%
</article>
</body>
</html>"""


def _full_test_layout(root: Path) -> Path:
    return write_layout(root, "layouts/full_test.html", _FULL_TEST_TEMPLATE)


def _default_layout(root: Path) -> Path:
    return write_layout(
        root,
        "layouts/index.html",
        load_packaged_official_layout("minimal"),
    )


class TestWikiSite(unittest.TestCase):
    def test_build_site_creates_one_page_per_markdown_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Bob.md").write_text("# Bob\n\n## Early Life\n\nBorn.\n\n## Early Life\n\nAgain.", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config, base_url="/wiki", url_style="dir")

            self.assertEqual(len(site.pages), 1)
            page = site.pages[0]
            self.assertEqual(page.full_slug, "Bob")
            self.assertNotIn('id="bob"', page.html)
            self.assertIn('id="early-life"', page.html)
            self.assertIn('id="early-life-1"', page.html)
            self.assertEqual([item.slug for item in page.outline], ["early-life", "early-life-1"])
            html = build_page_html(page, root, base_url="/wiki", url_style="dir", default_layout=_full_test_layout(root))
            self.assertIn('id="early-life"', html)
            self.assertIn('id="early-life-1"', html)

    def test_title_falls_back_to_humanized_route(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Pokemon_Diamond_(copy_1).md").write_text("No heading.", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config)

            self.assertEqual(site.pages[0].title, "Pokemon Diamond (copy 1)")

    def test_build_site_creates_pages_for_data_documents(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "person.yaml").write_text("type: Person\nname: Gregory Davidson\n", encoding="utf-8")
            (wiki / "place.yml").write_text("type: Place\nname: Princeton\n", encoding="utf-8")
            (wiki / "index.md").write_text("# Home", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config)

            page_by_slug = {page.full_slug: page for page in site.pages}
            self.assertIn("person", page_by_slug)
            self.assertEqual(page_by_slug["person"].title, "Gregory Davidson")
            self.assertIn("Gregory Davidson", page_by_slug["person"].html + str(page_by_slug["person"].frontmatter))
            self.assertIn("place", page_by_slug)
            self.assertEqual(page_by_slug["place"].title, "Princeton")

    def test_build_page_html_renders_tiny_layout_without_infobox_chrome(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Gregory_Davidson.yaml").write_text(
                """id: wiki:Gregory_Davidson
type: schema:Person
givenName: Gregory
familyName: Davidson
knows: wiki:Ethan_Davidson
owns: wiki:Bella_Davidson
softwareVersion: 1.2
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
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config, base_url="/wiki", url_style="dir")
            page = next(page for page in site.pages if page.full_slug == "Gregory_Davidson")
            html = build_page_html(page, root, base_url="/wiki", url_style="dir", default_layout=_full_test_layout(root))

            self.assertIsNone(page.layout_path)
            self.assertEqual(page.layout_stem, "default")
            self.assertIn("Gregory Davidson", html)
            self.assertNotIn('class="infobox page-meta"', html)
            self.assertNotIn("Infobox", html)

    def test_wazoo_layout_frontmatter_loads_custom_shell(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            layouts = root / "layouts"
            layouts.mkdir()
            custom_shell = """<!DOCTYPE html>
<html><body><div id="custom-shell">%wiki.body%</div></body></html>"""
            (layouts / "project.html").write_text(custom_shell, encoding="utf-8")
            (wiki / "project.md").write_text(
                """---
type: schema:CreativeWork
wazoo:layout: layouts/project.html
name: Project Atlas
related:
  - wiki:Project_Atlas
---
# Project Atlas
""",
                encoding="utf-8",
            )
            (wiki / "Project_Atlas.yaml").write_text(
                """id: wiki:Project_Atlas
type: schema:CreativeWork
name: Project Atlas Record
""",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config, base_url="/wiki", url_style="dir")
            page = next(page for page in site.pages if page.full_slug == "project")
            html = build_page_html(page, root, base_url="/wiki", url_style="dir", default_layout=_full_test_layout(root))

            self.assertEqual(page.layout_path, (layouts / "project.html").resolve())
            self.assertEqual(page.layout_stem, "project")
            self.assertIn('id="custom-shell"', html)
            self.assertNotIn('class="infobox page-meta"', html)
            self.assertNotIn("<dt>wazoo:layout</dt>", html)

    def test_template_frontmatter_does_not_select_layout(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "project.md").write_text(
                """---
type: schema:CreativeWork
template: layouts/project.html
wiki:template: layouts/project.html
name: Project Atlas
---
# Project Atlas
""",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config, base_url="/wiki", url_style="dir")
            page = next(page for page in site.pages if page.full_slug == "project")
            html = build_page_html(page, root, base_url="/wiki", url_style="dir", default_layout=_full_test_layout(root))

            self.assertIsNone(page.layout_path)
            self.assertEqual(page.layout_stem, "default")
            self.assertNotIn('id="custom-shell"', html)
            self.assertIn('id="article-top"', html)
            self.assertNotIn('class="layout-label"', html)
            self.assertNotIn("<dt>template</dt>", html)
            self.assertNotIn("<dt>wiki:template</dt>", html)

    def test_render_outline_title_renders_inline_code(self) -> None:
        html = render_outline_title("`Accept`")
        self.assertIn("<code>Accept</code>", html)
        self.assertNotIn("`Accept`", html)

    def test_render_outline_title_renders_wikilinks_without_nested_anchors(self) -> None:
        html = render_outline_title("Importance in the [[Semantic_Web|semantic web]]")
        self.assertIn('<span class="wikilink">semantic web</span>', html)
        self.assertNotIn("[[", html)
        self.assertNotIn("<a ", html)

    def test_build_page_html_renders_toc_heading_markdown(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text(
                "# Page\n\n## Request headers\n\n### `Accept`\n\n"
                "## Importance in the [[Semantic_Web|semantic web]]\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            page_layout = _full_test_layout(root)
            html = build_page_html(page, root, default_layout=page_layout)

            self.assertIn('<h3 id="accept"><code>Accept</code></h3>', html)
            self.assertIn('<a class="wikilink" href="/wiki/Semantic_Web/">semantic web</a>', html)
            self.assertNotIn('id="p-contents"', html)
            self.assertNotIn('id="toc"', html)

    def test_render_adds_github_heading_ids_to_all_heading_levels(self) -> None:
        html = render_wiki_markdown("# Title\n\n### API: read/write?\n")

        self.assertIn('id="title"', html)
        self.assertIn('id="api-readwrite"', html)

    def test_render_highlights_fenced_code_with_known_language(self) -> None:
        html = render_wiki_markdown('```python\nprint("<hello>")\n```\n')

        self.assertIn('class="highlight"', html)
        self.assertIn('class="language-python"', html)
        self.assertIn('data-copy="print(&quot;&lt;hello&gt;&quot;)\n"', html)
        self.assertIn("<span", html)
        self.assertIn("&lt;hello&gt;", html)

    def test_render_unknown_language_falls_back_to_plain_code(self) -> None:
        html = render_wiki_markdown("```not-a-real-language\n<tag>\n```\n")

        self.assertIn('class="language-not-a-real-language"', html)
        self.assertIn('data-copy="&lt;tag&gt;\n"', html)
        self.assertIn("&lt;tag&gt;", html)
        self.assertNotIn("<span", html)

    def test_render_unlabeled_fence_remains_plain_code(self) -> None:
        html = render_wiki_markdown("```\n<tag>\n```\n")

        self.assertIn('data-copy="&lt;tag&gt;\n"', html)
        self.assertIn("<pre data-copy=", html)
        self.assertIn("<code>", html)
        self.assertIn("&lt;tag&gt;", html)
        self.assertNotIn('class="highlight"', html)

    def test_render_wiki_markdown_does_not_pass_through_raw_html(self) -> None:
        html = render_wiki_markdown('<script>alert("x")</script>\n\nSafe paragraph.\n')
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Safe paragraph.", html)

        event_html = render_wiki_markdown('<img src=x onerror=alert(1)>\n')
        self.assertNotIn("<img", event_html)
        self.assertIn("&lt;img", event_html)

    def test_render_hidden_sparql_block_omits_query_from_html(self) -> None:
        markdown = (
            "<!-- sparql:start\n"
            "```sparql\nSELECT ?name WHERE { ?person foaf:name ?name }\n```\n"
            "-->\n\n"
            "| name |\n| --- |\n| Alice |\n\n"
            "<!-- sparql:end -->\n"
        )
        html = render_wiki_markdown(markdown)

        self.assertIn("Alice", html)
        self.assertIn("<table>", html)
        self.assertNotIn("language-sparql", html)
        self.assertNotIn('class="highlight"', html)
        self.assertNotIn("<pre data-copy=", html)

    def test_render_visible_sparql_block_shows_query_in_html(self) -> None:
        markdown = (
            "<!-- sparql:start -->\n"
            "```sparql\nSELECT ?name WHERE { ?person foaf:name ?name }\n```\n\n"
            "| name |\n| --- |\n| Alice |\n\n"
            "<!-- sparql:end -->\n"
        )
        html = render_wiki_markdown(markdown)

        self.assertIn("language-sparql", html)
        self.assertIn("SELECT ?name", html)

    def test_render_hidden_sparql_block_with_raw_html_does_not_execute_markup(self) -> None:
        markdown = (
            "<!-- sparql:start\n"
            "<script>alert(1)</script>\n"
            "```sparql\nSELECT ?name WHERE { ?person foaf:name ?name }\n```\n"
            "-->\n\n"
            "| name |\n| --- |\n| Alice |\n\n"
            "<!-- sparql:end -->\n"
        )
        html = render_wiki_markdown(markdown)

        self.assertIn("Alice", html)
        self.assertIn("<table>", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<!-- sparql:start", html)

    def test_render_outline_title_does_not_pass_through_raw_html(self) -> None:
        html = render_outline_title('<img src=x onerror=alert(1)>')
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img", html)

    def test_build_page_html_escapes_raw_html_in_headings(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text(
                "# Page\n\n## Safe section\n\n### <script>alert(1)</script>\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            page_layout = _full_test_layout(root)
            html = build_page_html(page, root, default_layout=page_layout)

            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn('id="toc"', html)
            self.assertNotIn('id="p-contents"', html)

    def test_render_copyable_pre_escapes_attribute_text(self) -> None:
        html = render_copyable_pre('line "one"\nline two', "&lt;tag&gt;")

        self.assertIn('data-copy="line &quot;one&quot;', html)
        self.assertIn('line two"', html)
        self.assertIn("<code>&lt;tag&gt;</code>", html)

    def test_build_page_html_does_not_embed_metadata_panel(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "person.md").write_text(
                """---
type: schema:Person
givenName: Gregory
familyName: Davidson
specialty: Diagnostics
---
# Gregory Davidson
""",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            site = build_site(config, base_url="/wiki", url_style="dir")
            page = next(page for page in site.pages if page.full_slug == "person")
            page_layout = _full_test_layout(root)
            html = build_page_html(page, root, base_url="/wiki", url_style="dir", default_layout=page_layout)

            self.assertNotIn("Metadata</a>", html)
            self.assertNotIn('href="#view-metadata-content"', html)
            self.assertNotIn('metadata-format-panel-json-ld-compacted', html)
            self.assertNotIn('metadata-format-panel-turtle', html)

    def test_obsidian_wikilinks_resolve_relative_to_current_file(self) -> None:
        html = render_wiki_markdown(
            "See [[../games/Pokemon_Diamond#Release History|history]].",
            base_url="/wiki",
            url_style="dir",
            current_route="people/Ethan_Davidson",
        )

        self.assertIn('href="/wiki/games/Pokemon_Diamond/#release-history"', html)
        self.assertIn('>history</a>', html)



    def test_markdown_links_normalize_to_canonical_page_urls(self) -> None:
        html = render_wiki_markdown(
            "See [game](../games/Pokemon_Diamond.md#Release%20History).",
            base_url="/wiki",
            url_style="dir",
            current_route="people/Ethan_Davidson",
        )

        self.assertIn('href="/wiki/games/Pokemon_Diamond/#release-history"', html)

    def test_fallback_index_uses_minimal_template(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Alice.md").write_text("# Alice\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            html = build_index_html(site, root)
            self.assertIn('<ul class="pages-list">', html)
            self.assertIn("Alice", html)
            self.assertNotIn("<style>", html)
            self.assertNotIn("/wiki/assets/wikipedia.css", html)
            self.assertNotIn("infobox page-meta", html)

    def test_strip_leading_title_heading_removes_matching_h1(self) -> None:
        markdown = "# My Article\n\nLead paragraph."
        self.assertEqual(
            strip_leading_title_heading(markdown, "My Article"),
            "Lead paragraph.",
        )

    def test_strip_leading_title_heading_keeps_non_matching_h1(self) -> None:
        markdown = "# Different Title\n\nLead paragraph."
        self.assertEqual(
            strip_leading_title_heading(markdown, "My Article"),
            markdown,
        )

    def test_strip_leading_title_heading_matches_inline_code_h1(self) -> None:
        markdown = "# `wiki lint`\n\nRun convention audits."
        self.assertEqual(
            strip_leading_title_heading(markdown, "wiki lint"),
            "Run convention audits.",
        )

    def test_build_site_strips_duplicate_title_from_rendered_html(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text(
                "---\nname: Content negotiation\ntype: TechArticle\n---\n\n"
                "# Content negotiation\n\nLead paragraph.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            self.assertIn("Lead paragraph.", page.html)
            self.assertNotIn("<h1", page.html)
            self.assertIn("# Content negotiation", page.markdown)

    def test_markdown_links_leave_wiki_curie_as_route_text(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (root / "wiki.yaml").write_text(
                "wiki:\n  input: [wiki]\ngraph:\n  context:\n    wiki: https://wiki.example.org/\n"
                "  context:\n    wiki: https://wiki.example.org/\n",
                encoding="utf-8",
            )
            (wiki / "Farzapedia.md").write_text(
                "---\ntype: TechArticle\nheadline: Farzapedia\nabout: wiki:wiki\n---\n\n[wiki](wiki:wiki)\n",
                encoding="utf-8",
            )
            (wiki / "wiki.md").write_text(
                "---\ntype: TechArticle\nname: Wiki CLI\n---\n\n# Wiki CLI\n",
                encoding="utf-8",
            )
            config = Config.load(root / "wiki.yaml")
            site = build_site(config, base_url="/wiki", url_style="dir")
            page = next(p for p in site.pages if p.full_slug == "Farzapedia")
            html = build_page_html(page, root, base_url="/wiki", url_style="dir", default_layout=_full_test_layout(root))
            self.assertIn('href="/wiki/wiki%3Awiki/"', html)
            self.assertIn(">wiki</a>", html)

    def test_fallback_article_uses_minimal_template(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text("---\ntype: Article\n---\n\n# My Article\n\nContent.", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            html = build_page_html(page, root)
            self.assertNotIn("<h1>My Article</h1>", page.html)
            self.assertIn("Content.", html)
            self.assertNotIn("<style>", html)
            self.assertNotIn("/wiki/assets/wikipedia.css", html)
            self.assertNotIn("infobox page-meta", html)
            self.assertNotIn("Backlinks", html)
            self.assertNotIn("On this page", html)

    def test_default_layout_read_view_includes_first_heading(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "wiki.md").write_text(
                "---\ntype: schema:SoftwareApplication\nname: Wiki CLI\n---\n\n"
                "# Wiki CLI\n\nLead paragraph.\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            html = build_page_html(page, root, default_layout=_default_layout(root))
            self.assertNotIn("<h1", page.html)
            self.assertIn("Lead paragraph.", html)

    def test_read_view_does_not_include_generic_site_sub(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text("# Page\n\nBody.", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            html = build_page_html(page, root, default_layout=_default_layout(root))
            self.assertNotIn("From Wiki CLI, the semantic knowledge base", html)

    def test_fallback_has_page_kind(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text("# Page\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            index_html = build_index_html(site, root)
            self.assertIn("All Pages", index_html)
            page = site.pages[0]
            article_html = build_page_html(page, root)
            self.assertIn("Page", article_html)

    def test_page_content_does_not_expand_documented_placeholder_tokens(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Placeholders.md").write_text(
                "---\nname: Placeholders\ntype: TechArticle\n---\n\n"
                "| Placeholder | Description |\n"
                "| --- | --- |\n"
                "| `{metadata_pane_html}` | Metadata pane |\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            page = site.pages[0]
            html = build_page_html(page, root, default_layout=_default_layout(root))
            self.assertIn("{metadata_pane_html}", html)
            self.assertNotIn("metadata-format-switch", html)

    def test_build_index_html_respects_url_style(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "alice.md").write_text("# Alice\n", encoding="utf-8")
            (wiki / "bob.md").write_text("# Bob\n", encoding="utf-8")

            dir_config = Config(wiki={"input": [wiki]}, site={"url_style": "dir"}, config_root=root)
            dir_site = build_site(dir_config)
            dir_index = build_index_html(dir_site, root, base_url="/wiki", url_style=dir_config.site.url_style)
            self.assertIn('href="/wiki/alice/"', dir_index)
            self.assertIn('href="/wiki/bob/"', dir_index)
            self.assertNotIn(".html", dir_index)

            file_config = Config(wiki={"input": [wiki]}, site={"url_style": "file"}, config_root=root)
            file_site = build_site(file_config)
            file_index = build_index_html(file_site, root, base_url="/wiki", url_style=file_config.site.url_style)
            self.assertIn('href="/wiki/alice.html"', file_index)
            self.assertIn('href="/wiki/bob.html"', file_index)

    def test_build_index_html_uses_tiny_layout_contract(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Alice.md").write_text("# Alice\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            html = build_index_html(site, root, default_layout=_full_test_layout(root))
            self.assertNotIn("%wiki.", html)
            self.assertNotIn('class="layout-label"', html)

    def test_build_index_html_emits_pages_list_with_categories(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Person_A.md").write_text("---\ntype: Person\n---\n# Person A\n", encoding="utf-8")
            (wiki / "Plain.md").write_text("# Plain\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            html = build_index_html(site, root, default_layout=_full_test_layout(root))
            article_start = html.index('<article id="article-top">')
            article_end = html.index("</article>", article_start)
            article = html[article_start:article_end]
            self.assertIn('<ul class="pages-list">', article)
            self.assertIn('data-categories="Person"', article)
            self.assertIn('data-categories=""', article)
    def test_build_index_html_uses_base_url_for_asset_paths(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text("# Page\n", encoding="utf-8")
            config = Config(
                wiki={"input": [wiki]},
                site={"base_url": "/wiki"},
                config_root=root,
            )
            site = build_site(config)
            html = build_index_html(
                site,
                root,
                default_layout=write_layout(
                    root,
                    "layouts/logo.html",
                    "%wiki.base_url%/assets/custom-logo.svg",
                ),
            )
            self.assertIn("/wiki/assets/custom-logo.svg", html)



    def test_build_index_html_emits_literal_theme_color_from_layout(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "page.md").write_text("# Page\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)
            site = build_site(config)
            html = build_index_html(
                site,
                root,
                default_layout=write_layout(
                    root,
                    "layouts/theme.html",
                    (
                        '<meta name="theme-color" content="#6366f1">'
                        '<meta name="msapplication-TileColor" content="#6366f1">'
                    ),
                ),
            )
            self.assertIn('<meta name="theme-color" content="#6366f1">', html)
            self.assertIn('<meta name="msapplication-TileColor" content="#6366f1">', html)


if __name__ == "__main__":
    unittest.main()
