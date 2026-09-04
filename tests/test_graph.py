import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pyshacl
from rdflib import RDF, BNode, Graph, Literal, URIRef
from rdflib.namespace import XSD

from wiki.audit import load_shapes
from wiki.config import Config
from wiki.context import Context
from wiki.graph import (
    frontmatter_to_graph,
    graph_descriptors,
    kebab_case,
    load_dataset,
    load_graph,
    resolve_object,
    resolve_predicate,
    source_graph_uri,
)
from wiki.schemas.sources import LockedSource, Lockfile


class TestRDFFrontmatter(unittest.TestCase):
    def setUp(self) -> None:
        self.config = Config()
        self.context = self.config.context

    def test_kebab_case(self) -> None:
        """Test kebab-case conversion helper."""
        self.assertEqual(kebab_case("John Smith! & Co."), "john-smith--co")
        self.assertEqual(kebab_case(""), "")
        self.assertEqual(kebab_case("some--double--dashes"), "some-double-dashes")

    def test_resolve_predicate(self) -> None:
        """Test resolve_predicate handles various prefixes and fallback mappings."""
        # Context with schema.org default vocab
        schema_context = Context(namespaces={"@vocab": "https://schema.org/"})

        # Custom namespace prefix
        self.assertEqual(
            resolve_predicate("foaf:name", schema_context),
            schema_context.namespaces["foaf"]["name"]
        )
        # Wiki prefix
        self.assertEqual(
            resolve_predicate("wiki.gregory", schema_context),
            schema_context.namespaces["wiki"]["gregory"]
        )
        # Unregistered prefix or default falls back to schema
        self.assertEqual(
            resolve_predicate("givenName", schema_context),
            schema_context.namespaces["schema"]["givenName"]
        )
        self.assertEqual(
            resolve_predicate("headline", schema_context),
            schema_context.namespaces["schema"]["headline"]
        )
        self.assertEqual(
            resolve_predicate("rdfs:label", schema_context),
            schema_context.namespaces["rdfs"]["label"]
        )
        self.assertEqual(
            resolve_predicate("label", schema_context),
            schema_context.namespaces["schema"]["label"]
        )
        self.assertEqual(
            resolve_predicate("unregistered:prop", schema_context),
            schema_context.namespaces["schema"]["unregistered:prop"]
        )

        # Context with NO default vocab
        no_vocab_context = Context(namespaces={})
        self.assertIsNone(resolve_predicate("givenName", no_vocab_context))
        self.assertIsNone(resolve_predicate("headline", no_vocab_context))
        self.assertIsNone(resolve_predicate("label", no_vocab_context))
        # Prefixed keys should still resolve
        self.assertEqual(
            resolve_predicate("foaf:name", no_vocab_context),
            no_vocab_context.namespaces["foaf"]["name"]
        )

    def test_resolve_object_datatypes(self) -> None:
        """Test resolve_object maps booleans, numbers, HTTP URIs, None, and strings correctly."""
        graph = Graph()
        subject = URIRef(self.context.namespaces["wiki"]["gregory"])
        
        # HTTP URI
        resolve_object("url", "https://google.com", graph, subject, self.context)
        url_pred = self.context.namespaces["schema"]["url"]
        self.assertTrue((subject, url_pred, URIRef("https://google.com")) in graph)
        
        # Boolean
        resolve_object("knows", True, graph, subject, self.context)
        knows_pred = self.context.namespaces["schema"]["knows"]
        self.assertTrue((subject, knows_pred, Literal(True, datatype=XSD.boolean)) in graph)
        
        # Numbers
        resolve_object("age", 30, graph, subject, self.context)
        age_pred = self.context.namespaces["schema"]["age"]
        self.assertTrue((subject, age_pred, Literal(30)) in graph)
        
        # None (should add nothing)
        resolve_object("nothing", None, graph, subject, self.context)
        nothing_pred = self.context.namespaces["schema"]["nothing"]
        self.assertEqual(len(list(graph.objects(subject, nothing_pred))), 0)

        # 4. Datetime object mapping
        from datetime import date, datetime
        bday_pred = self.context.namespaces["schema"]["birthDate"]
        resolve_object("birthDate", date(1990, 1, 1), graph, subject, self.context)
        self.assertTrue((subject, bday_pred, Literal(date(1990, 1, 1), datatype=XSD.date)) in graph)

        resolved_pred = self.context.namespaces["schema"]["resolvedAt"]
        resolve_object("resolvedAt", datetime(2025, 6, 15, 14, 30, 0), graph, subject, self.context)
        self.assertTrue((subject, resolved_pred, Literal(datetime(2025, 6, 15, 14, 30, 0), datatype=XSD.dateTime)) in graph)

        # 5. String with unregistered prefix (falls back to Literal)
        unreg_pred = self.context.namespaces["schema"]["unregistered"]
        resolve_object("unregistered", "bogus:value", graph, subject, self.context)
        self.assertTrue((subject, unreg_pred, Literal("bogus:value")) in graph)

        # 6. Generic object stringification fallback
        tuple_pred = self.context.namespaces["schema"]["tup"]
        resolve_object("tup", (1, 2), graph, subject, self.context)
        self.assertTrue((subject, tuple_pred, Literal("(1, 2)")) in graph)

    def test_nested_dict_creates_blank_node(self) -> None:
        """Test that a nested dictionary without explicit @type creates a blank node."""
        data = {
            "@type": "Person",
            "@id": "wiki:gregory",
            "givenName": "Gregory",
            "address": {
                "street": "123 Main St",
                "city": "Seattle"
            }
        }
        graph = frontmatter_to_graph(data, self.context)
        subject = URIRef(self.context.namespaces["wiki"]["gregory"])

        # Verify name predicate
        name_pred = self.context.namespaces["schema"]["givenName"]
        self.assertTrue((subject, name_pred, Literal("Gregory")) in graph)
        
        # Verify address predicate points to a blank node
        address_pred = self.context.namespaces["schema"]["address"]
        blank_nodes = list(graph.objects(subject, address_pred))
        self.assertEqual(len(blank_nodes), 1)
        blank = blank_nodes[0]
        self.assertIsInstance(blank, BNode)
        
        # Verify properties on the blank node
        street_pred = self.context.namespaces["schema"]["street"]
        city_pred = self.context.namespaces["schema"]["city"]

        self.assertTrue((blank, street_pred, Literal("123 Main St")) in graph)
        self.assertTrue((blank, city_pred, Literal("Seattle")) in graph)



    def test_nested_typed_dict_creates_typed_blank_node(self) -> None:
        """Test that a nested dictionary with @type creates a typed blank node."""
        data = {
            "@type": "Person",
            "@id": "wiki:gregory",
            "givenName": "Gregory",
            "address": {
                "@type": "PostalAddress",
                "street": "123 Main St"
            }
        }
        graph = frontmatter_to_graph(data, self.context)
        subject = URIRef(self.context.namespaces["wiki"]["gregory"])
        address_pred = self.context.namespaces["schema"]["address"]
        blank = list(graph.objects(subject, address_pred))[0]
        
        type_pred = RDF.type
        expected_type = self.context.namespaces["schema"]["PostalAddress"]
        self.assertTrue((blank, type_pred, expected_type) in graph)

    def test_nested_typed_dict_respects_custom_vocab(self) -> None:
        """Test that typed nested blank nodes resolve @type through @vocab (not hardcoded schema:)."""
        custom_context = Context(namespaces={
            "@vocab": "https://custom.example.org/vocab/",
            "wiki": "https://wiki.example.org/",
        })
        data = {
            "@type": "Document",
            "@id": "wiki:doc",
            "embed": {
                "@type": "CustomEmbed",
                "name": "test",
            }
        }
        graph = frontmatter_to_graph(data, custom_context)
        subject = URIRef(custom_context.namespaces["wiki"]["doc"])
        embed_pred = URIRef("https://custom.example.org/vocab/embed")
        blank = list(graph.objects(subject, embed_pred))[0]

        expected_type = URIRef("https://custom.example.org/vocab/CustomEmbed")
        self.assertTrue((blank, RDF.type, expected_type) in graph)
        # It should NOT have the schema.org type
        schema_type = URIRef("https://schema.org/CustomEmbed")
        self.assertFalse((blank, RDF.type, schema_type) in graph)

    def test_nested_referenced_dict_creates_uri_ref(self) -> None:
        """Test that a nested dictionary with @id maps directly to a URI reference."""
        data = {
            "@type": "Person",
            "@id": "wiki:gregory",
            "givenName": "Gregory",
            "spouse": {
                "@id": "wiki:bella"
            }
        }
        graph = frontmatter_to_graph(data, self.context)
        subject = URIRef(self.context.namespaces["wiki"]["gregory"])
        spouse_pred = self.context.namespaces["schema"]["spouse"]
        spouse_obj = list(graph.objects(subject, spouse_pred))[0]
        
        expected_spouse = URIRef(self.context.namespaces["wiki"]["bella"])
        self.assertEqual(spouse_obj, expected_spouse)

    def test_nested_list_of_dicts_creates_multiple_nodes(self) -> None:
        """Test that a list of nested dictionaries creates corresponding multiple blank nodes."""
        data = {
            "@type": "Person",
            "@id": "wiki:gregory",
            "address": [
                {"street": "123 Main St"},
                {"street": "456 Oak Ave"}
            ]
        }
        graph = frontmatter_to_graph(data, self.context)
        subject = URIRef(self.context.namespaces["wiki"]["gregory"])
        address_pred = self.context.namespaces["schema"]["address"]
        blanks = list(graph.objects(subject, address_pred))
        self.assertEqual(len(blanks), 2)
        
        street_pred = self.context.namespaces["schema"]["street"]
        streets = {str(graph.value(blank, street_pred)) for blank in blanks}
        self.assertEqual(streets, {"123 Main St", "456 Oak Ave"})

    def test_auto_inject_markdown_body(self) -> None:
        """Test that the markdown body is auto-injected into the graph if content_predicate is set."""
        data = {
            "@type": "Person",
            "@id": "wiki:gregory",
            "givenName": "Gregory"
        }
        self.config.graph.content_predicate = "schema:text"
        body_text = "Gregory is a software engineer."
        
        graph = frontmatter_to_graph(data, self.config, body=body_text)
        subject = URIRef(self.context.namespaces["wiki"]["gregory"])
        
        text_pred = self.context.namespaces["schema"]["text"]
        self.assertTrue((subject, text_pred, Literal(body_text)) in graph)

    def test_frontmatter_to_graph_empty_and_id_generation(self) -> None:
        """Test empty dictionary handling and fallback id generation logic."""
        base = str(self.context.namespaces["wiki"])
        
        # Empty dict or missing type -> Empty graph
        self.assertEqual(len(frontmatter_to_graph({}, self.config)), 0)
        
        # Missing type -> Empty graph
        self.assertEqual(len(frontmatter_to_graph({"givenName": "Alice"}, self.config)), 0)
        
        # Missing @id, with file_id -> uses file_id without .md
        g_file = frontmatter_to_graph({"@type": "WebPage"}, self.config, file_id="doc")
        self.assertTrue((URIRef(f"{base}doc"), RDF.type, self.context.namespaces["schema"]["WebPage"]) in g_file)
        
        # Missing @id, with file_id and include_file_extension=True -> uses file_id with .md
        g_file_ext = frontmatter_to_graph({"@type": "WebPage"}, self.config, file_id="doc", include_file_extension=True)
        self.assertTrue((URIRef(f"{base}doc.md"), RDF.type, self.context.namespaces["schema"]["WebPage"]) in g_file_ext)
        
        # Missing @id, no file_id -> Empty graph (no Person special-case fallback anymore)
        self.assertEqual(len(frontmatter_to_graph({"@type": "Person", "givenName": "Alice", "familyName": "Smith"}, self.config)), 0)
        self.assertEqual(len(frontmatter_to_graph({"@type": "WebPage", "givenName": "Some Page"}, self.config)), 0)
        self.assertEqual(len(frontmatter_to_graph({"@type": "Person", "givenName": "Cher"}, self.config)), 0)


    def test_blank_node_uniqueness_across_documents(self) -> None:
        """Test that identical nested frontmatter from different files get unique blank nodes (regression for #144).

        Python's id(value) was reused by the GC across files, causing blank node
        collisions when graphs were combined. BNode() avoids this entirely.
        """
        data1 = {
            "@type": "sh:NodeShape",
            "@id": "wiki:person-shape",
            "sh:property": [{"sh:path": "schema:name", "sh:datatype": "xsd:string"}],
        }
        data2 = {
            "@type": "sh:NodeShape",
            "@id": "wiki:pet-shape",
            "sh:property": [{"sh:path": "schema:name", "sh:datatype": "xsd:string"}],
        }

        g1 = frontmatter_to_graph(data1, self.context)
        g2 = frontmatter_to_graph(data2, self.context)

        # Combine graphs the same way _process_document_file does
        combined = g1 + g2

        sh_property_pred = self.context.namespaces["sh"]["property"]
        blanks = list(combined.objects(None, sh_property_pred))

        # Each document has 1 property shape -> 2 distinct blank nodes
        self.assertEqual(len(blanks), 2)
        self.assertEqual(len(set(blanks)), 2)
        for blank in blanks:
            self.assertIsInstance(blank, BNode)


class TestRDFLoadingAndResolution(unittest.TestCase):
    def test_implicit_types_fallback_for_untyped_page(self) -> None:
        config = Config(graph={"implicit_types": ["TechArticle"]})
        ctx = config.context
        data = {"headline": "Untitled"}
        g = frontmatter_to_graph(data, config, file_id="untitled")
        subj = URIRef(f"{ctx.base_iri}untitled")
        self.assertIn((subj, RDF.type, ctx.namespaces["schema"]["TechArticle"]), g)

    def test_implicit_types_fallback_preserves_explicit_type(self) -> None:
        config = Config(graph={"implicit_types": ["TechArticle"]})
        ctx = config.context
        data = {"@type": "Person", "@id": "wiki:alice", "givenName": "Alice"}
        g = frontmatter_to_graph(data, config)
        subj = URIRef(ctx.namespaces["wiki"]["alice"])
        types = list(g.objects(subj, RDF.type))
        self.assertEqual(len(types), 1)
        self.assertIn(ctx.namespaces["schema"]["Person"], types)

    def test_implicit_types_append_unions_and_dedupes(self) -> None:
        config = Config(
            graph={
                "implicit_types": ["TechArticle", "CreativeWork"],
                "implicit_types_policy": "append",
            }
        )
        ctx = config.context
        data = {"@type": ["TechArticle", "Person"], "@id": "wiki:doc", "headline": "Doc"}
        g = frontmatter_to_graph(data, config)
        subj = URIRef(ctx.namespaces["wiki"]["doc"])
        types = set(g.objects(subj, RDF.type))
        self.assertEqual(
            types,
            {
                ctx.namespaces["schema"]["TechArticle"],
                ctx.namespaces["schema"]["Person"],
                ctx.namespaces["schema"]["CreativeWork"],
            },
        )

    def test_implicit_types_append_skips_shacl_shapes(self) -> None:
        config = Config(
            graph={
                "implicit_types": ["TechArticle"],
                "implicit_types_policy": "append",
            }
        )
        ctx = config.context
        data = {"@type": "sh:NodeShape", "@id": "wiki:person-shape", "rdfs:label": "Person"}
        g = frontmatter_to_graph(data, config)
        subj = URIRef(ctx.namespaces["wiki"]["person-shape"])
        types = list(g.objects(subj, RDF.type))
        self.assertEqual(len(types), 1)
        self.assertIn(ctx.namespaces["sh"]["NodeShape"], types)

    def test_base_iri_override_differs_from_context_wiki(self) -> None:
        config = Config(
            graph={
                "context": {
                    "@vocab": "https://schema.org/",
                    "wiki": "https://example.test/wiki/",
                },
                "base_iri": "https://example.test/docs/",
            }
        )
        ctx = config.context
        data = {"@type": "WebPage", "headline": "Page"}
        g = frontmatter_to_graph(data, config, file_id="page")
        subj = URIRef("https://example.test/docs/page")
        self.assertIn((subj, RDF.type, ctx.namespaces["schema"]["WebPage"]), g)

    def test_multi_type_and_implicit_id_mapping(self) -> None:
        """Test multi-type arrays in frontmatter and implicit ID mapping fallback in loading sequence."""
        config = Config()
        ctx = config.context
        
        # Verify multi-type parsing logic executes and adds multiple types
        data = {
            "@type": ["Person", "Developer"],
            "@id": "wiki:multi",
            "givenName": "Multi Guy"
        }
        g = frontmatter_to_graph(data, ctx)
        subj = URIRef(ctx.namespaces["wiki"]["multi"])
        types = list(g.objects(subj, RDF.type))
        self.assertEqual(len(types), 2)
        self.assertIn(ctx.namespaces["schema"]["Person"], types)
        self.assertIn(ctx.namespaces["schema"]["Developer"], types)

    def test_frontmatter_to_graph_exports_wazoo_layout(self) -> None:
        config = Config()
        ctx = config.context
        data = {
            "@type": "Person",
            "@id": "wiki:ethan",
            "givenName": "Ethan",
            "wazoo:layout": "layouts/person.html",
        }
        g = frontmatter_to_graph(data, ctx)
        subject = URIRef(ctx.namespaces["wiki"]["ethan"])
        layout_pred = URIRef(ctx.namespaces["wazoo"]["layout"])
        self.assertIn((subject, layout_pred, Literal("layouts/person.html")), g)
        self.assertEqual(len(list(g.triples((None, None, None)))), 3)

    def test_load_graph_advanced_sources(self) -> None:
        """Test the unified graph loader handles multiple input dirs and gracefully ignores broken internal Turtle."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            imports = root / "imports"
            wiki.mkdir()
            imports.mkdir()

            # Create faulty import file to exercise exception catcher in standalone loader
            bad_ttl = imports / "error.ttl"
            bad_ttl.write_text("UNPARSABLE NONSENSE", encoding="utf-8")

            # A valid wiki file hosting a MALFORMED turtle codeblock AND a valid body payload
            valid_md = wiki / "safe.md"
            valid_md.write_text("""---
"@type": WebPage
name: Safe Page
---
This is body text loaded by content_predicate.
```turtle
@prefix : <#> .
:broken syntax !!!!!!
```
""", encoding="utf-8")

            # A secondary file in the imports dir with valid body payload to verify both loops
            extra_md = imports / "raw_discovery.md"
            extra_md.write_text("""---
"@type": Person
"@id": "wiki:raw_agent"
name: Raw Agent
---
Raw Body Text.
""", encoding="utf-8")

            config = Config(wiki={"input": [wiki, imports]})
            config.graph.content_predicate = "schema:text"
            
            # Load graph should not crash due to bad TTLs or broken syntax, and must ingest everything
            g = load_graph(config, infer=False)
            
            self.assertGreater(len(g), 0)
            # Verify bodies parsed successfully from all locations
            body_text_full = " ".join(str(o) for o in g.objects(None, config.context.namespaces["schema"]["text"]))
            self.assertIn("This is body text loaded by content_predicate.", body_text_full)
            self.assertIn("Raw Body Text.", body_text_full)
            
            # Must find entity from wiki dir
            self.assertTrue((None, None, Literal("Safe Page")) in g)
            # Must find entity from imports dir
            raw_agent_uri = config.context.namespaces["wiki"]["raw_agent"]
            self.assertTrue((raw_agent_uri, RDF.type, config.context.namespaces["schema"]["Person"]) in g)


    def test_load_graph_logs_warnings_on_bad_files(self) -> None:
        """Test that load_graph emits warnings for unparseable content instead of silent pass."""
        from wiki.graph import logger as graph_logger

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()

            # Valid wiki file
            valid_md = wiki / "good.md"
            valid_md.write_text("""---
"@type": WebPage
name: Good Page
---
""", encoding="utf-8")

            # Invalid .ttl file — triggers warning
            bad_ttl = wiki / "broken.ttl"
            bad_ttl.write_text("UNPARSABLE GARBAGE", encoding="utf-8")

            config = Config(wiki={"input": [wiki]})

            with self.assertLogs(graph_logger, level="WARNING") as log_cm:
                g = load_graph(config, infer=False)

            # Should have logged a warning about the broken.ttl file
            warning_messages = [r.getMessage() for r in log_cm.records]
            self.assertTrue(
                any("broken.ttl" in msg for msg in warning_messages),
                f"No warning about broken.ttl found in: {warning_messages}"
            )

            # Graph should still be loadable with valid content
            self.assertGreater(len(g), 0)




    def test_load_graph_reads_yaml_and_json_documents(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "bob.yml").write_text("type: Person\ngivenName: Bob\n", encoding="utf-8")
            (wiki_dir / "gregory.yaml").write_text("type: Person\ngivenName: Gregory\n", encoding="utf-8")
            (wiki_dir / "alice.json").write_text('{"type": "Person", "givenName": "Alice"}', encoding="utf-8")

            config = Config(wiki={"input": [wiki_dir]})
            g = load_graph(config, infer=False)

            self.assertTrue((None, None, Literal("Bob")) in g)
            self.assertTrue((None, None, Literal("Gregory")) in g)
            self.assertTrue((None, None, Literal("Alice")) in g)

            bob_uri = URIRef("https://wiki.example.org/bob")
            gregory_uri = URIRef("https://wiki.example.org/gregory")
            alice_uri = URIRef("https://wiki.example.org/alice")
            self.assertTrue((bob_uri, RDF.type, config.context.namespaces["schema"]["Person"]) in g)
            self.assertTrue((gregory_uri, RDF.type, config.context.namespaces["schema"]["Person"]) in g)
            self.assertTrue((alice_uri, RDF.type, config.context.namespaces["schema"]["Person"]) in g)

    def test_load_dataset_preserves_root_and_source_graphs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            source_dir.mkdir(parents=True)

            (wiki_dir / "Root.md").write_text("""---
type: Thing
name: Root Doc
---
""", encoding="utf-8")
            (source_dir / "Source.md").write_text("""---
type: Thing
name: Source Doc
---
""", encoding="utf-8")
            Lockfile(sources={
                "brain": LockedSource(
                    url="https://example.com/brain.git",
                    resolved_ref="abcdef1234567890",
                    path="wiki",
                    fetched_at="2026-01-01T00:00:00+00:00",
                    required_by=["root"],
                )
            }).save(root / "wiki.lock")

            config = Config(config_root=root, wiki={"input": [wiki_dir, source_dir]})
            dataset = load_dataset(config, infer=False)
            source_uri = source_graph_uri(config, "brain")

            result = dataset.query(
                f'SELECT ?name WHERE {{ GRAPH <{source_uri}> {{ ?s <https://schema.org/name> ?name }} }}'
            )

            self.assertEqual([str(row.name) for row in result], ["Source Doc"])
            union_result = dataset.query("SELECT ?name WHERE { ?s <https://schema.org/name> ?name } ORDER BY ?name")
            self.assertEqual([str(row.name) for row in union_result], ["Root Doc", "Source Doc"])

    def test_load_dataset_disk_cache_preserves_named_graphs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            source_dir.mkdir(parents=True)

            (source_dir / "Source.md").write_text("""---
type: Thing
name: Source Doc
---
""", encoding="utf-8")
            Lockfile(sources={
                "brain": LockedSource(
                    url="https://example.com/brain.git",
                    resolved_ref="abcdef1234567890",
                    path="wiki",
                    fetched_at="2026-01-01T00:00:00+00:00",
                    required_by=["root"],
                )
            }).save(root / "wiki.lock")

            config = Config(config_root=root, wiki={"input": [wiki_dir, source_dir]})
            source_uri = source_graph_uri(config, "brain")
            load_dataset(config, infer=False, disk_cache=True)
            cached = load_dataset(config, infer=False, disk_cache=True)

            result = cached.query(
                f'SELECT ?name WHERE {{ GRAPH <{source_uri}> {{ ?s <https://schema.org/name> ?name }} }}'
            )

            self.assertEqual([str(row.name) for row in result], ["Source Doc"])
            self.assertTrue(list((root / ".wiki" / "cache").glob("dataset-asserted-*.nq")))

    def test_graph_descriptors_include_locked_source_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            source_dir.mkdir(parents=True)
            Lockfile(sources={
                "brain": LockedSource(
                    url="https://example.com/brain.git",
                    ref="main",
                    resolved_ref="abcdef1234567890",
                    path="wiki",
                    fetched_at="2026-01-01T00:00:00+00:00",
                    required_by=["root"],
                )
            }).save(root / "wiki.lock")

            config = Config(config_root=root, wiki={"input": [wiki_dir, source_dir]})
            descriptors = graph_descriptors(config)

            self.assertEqual(descriptors[0].kind, "root")
            source = descriptors[1]
            self.assertEqual(source.name, "brain")
            self.assertEqual(source.kind, "source")
            self.assertEqual(source.url, "https://example.com/brain.git")
            self.assertEqual(source.ref, "main")
            self.assertEqual(source.resolved_ref, "abcdef1234567890")
            self.assertEqual(source.required_by, ["root"])

    def test_graph_descriptors_marks_direct_source_required_by_root(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            source_dir.mkdir(parents=True)
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

            config = Config(
                config_root=root,
                wiki={"input": [wiki_dir, source_dir]},
                sources=[{"name": "brain", "type": "git", "url": "https://example.com/brain.git"}],
            )

            source = next(descriptor for descriptor in graph_descriptors(config) if descriptor.name == "brain")
            self.assertEqual(source.required_by, ["root"])

    def test_graph_descriptors_warn_when_cache_exists_without_lockfile_sources(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            source_dir = root / ".wiki" / "sources" / "brain" / "repo" / "wiki"
            source_dir.mkdir(parents=True)

            config = Config(config_root=root, wiki={"input": [wiki_dir, source_dir]})
            with self.assertLogs("wiki.graph", level="WARNING") as log_cm:
                descriptors = graph_descriptors(config)

            self.assertEqual([descriptor.kind for descriptor in descriptors], ["root"])
            self.assertTrue(
                any("Source cache exists" in record.getMessage() for record in log_cm.records),
                [record.getMessage() for record in log_cm.records],
            )

    def test_load_graph_preserves_title_case_file_uri_refs(self) -> None:
        """Title-cased filename URIs must match title-cased wiki: CURIE references."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "Pokemon_Cartridge_Case.md").write_text("""---
type: schema:Place
name: Pokemon Cartridge Case
---
""", encoding="utf-8")
            (wiki_dir / "FindAction_2026-05-30_Pokemon_Diamond_(copy_1).md").write_text("""---
type: schema:FindAction
schema:location: wiki:Pokemon_Cartridge_Case
---
""", encoding="utf-8")

            config = Config(wiki={"input": [wiki_dir]})
            g = load_graph(config, infer=False)

            place_uri = URIRef("https://wiki.example.org/Pokemon_Cartridge_Case")
            action_uri = URIRef("https://wiki.example.org/FindAction_2026-05-30_Pokemon_Diamond_(copy_1)")
            schema = config.context.namespaces["schema"]
            self.assertTrue((place_uri, RDF.type, schema["Place"]) in g)
            self.assertTrue((action_uri, schema["location"], place_uri) in g)

    def test_include_file_extension_config_appends_md(self) -> None:
        """Test that include_file_extension=True produces .md in auto-generated page URIs."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "test.md").write_text("""---
type: WebPage
name: Test Page
---
""", encoding="utf-8")

            config = Config(wiki={"input": [wiki_dir]}, graph={"include_file_extension": True})
            g = load_graph(config, infer=False)
            expected = URIRef("https://wiki.example.org/test.md")
            self.assertTrue((expected, None, None) in g)

    def test_include_file_extension_uses_source_file_extension(self) -> None:
        """Test that include_file_extension=True uses the actual file extension for data documents."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "person.yaml").write_text("type: Person\ngivenName: Test\n", encoding="utf-8")

            config = Config(wiki={"input": [wiki_dir]}, graph={"include_file_extension": True})
            g = load_graph(config, infer=False)
            expected = URIRef("https://wiki.example.org/person.yaml")
            self.assertTrue((expected, None, None) in g)

    def test_vocab_null_ignores_unprefixed_keys(self) -> None:
        """Test that configuring @vocab as None/null causes unprefixed keys and types to be ignored."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text("""---
type: Person
givenName: Alice
schema:familyName: Smith
---
""", encoding="utf-8")

            config = Config(
                wiki={"input": [wiki_dir]},
                graph={
                    "context": {
                        "@vocab": None,
                        "schema": "https://schema.org/",
                    }
                }
            )
            g = load_graph(config, infer=False)
            
            # The subject URI should still exist
            alice_uri = URIRef("https://wiki.example.org/alice")
            
            # The unprefixed type and givenName should not be in the graph
            self.assertFalse((alice_uri, RDF.type, None) in g)
            self.assertFalse((alice_uri, URIRef("https://schema.org/givenName"), None) in g)
            
            # The prefixed schema:familyName should be in the graph
            self.assertTrue((alice_uri, URIRef("https://schema.org/familyName"), Literal("Smith")) in g)

    def test_shacl_multi_shape_no_blank_node_collision(self) -> None:
        """End-to-end regression test: two shape files with identical property shapes must not collide.

        Before the BNode() fix, id(value) reuse caused blank node collisions between
        property shapes across files, producing a ShapeLoadError ("An implicit PropertyShape
        cannot have more than one 'sh:path' predicate").
        """
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()

            # Two shape files with identical property shape structures
            (wiki_dir / "Person_Shape.md").write_text("""---
type: sh:NodeShape
sh:targetClass: schema:Person
sh:property:
  - sh:path: schema:name
    sh:minCount: 1
    sh:datatype: xsd:string
---
""", encoding="utf-8")

            (wiki_dir / "Pet_Shape.md").write_text("""---
type: sh:NodeShape
sh:targetClass: schema:Pet
sh:property:
  - sh:path: schema:name
    sh:minCount: 1
    sh:datatype: xsd:string
---
""", encoding="utf-8")

            config = Config(wiki={"input": [wiki_dir]})
            data_graph = load_graph(config, infer=True)
            shapes_graph = load_shapes(data_graph)

            # This must not raise ShapeLoadError
            conforms, _, results_text = pyshacl.validate(
                data_graph,
                shacl_graph=shapes_graph,
                inference="rdfs",
                abort_on_first=False,
            )
            self.assertTrue(conforms, f"SHACL validation failed:\n{results_text}")

    def test_vocab_custom_resolves_unprefixed_keys(self) -> None:
        """Test that configuring @vocab as a custom URI resolves unprefixed keys to that URI."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "alice.md").write_text("""---
type: CustomPerson
name: Alice
---
""", encoding="utf-8")

            config = Config(
                wiki={"input": [wiki_dir]},
                graph={
                    "context": {
                        "@vocab": "https://custom.example.org/vocab/",
                    }
                }
            )
            g = load_graph(config, infer=False)
            
            alice_uri = URIRef("https://wiki.example.org/alice")
            self.assertTrue((alice_uri, RDF.type, URIRef("https://custom.example.org/vocab/CustomPerson")) in g)
            self.assertTrue((alice_uri, URIRef("https://custom.example.org/vocab/name"), Literal("Alice")) in g)


if __name__ == "__main__":
    unittest.main()
