import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import RDF, RDFS, Namespace, URIRef

from wiki.config import Config
from wiki.graph import load_graph
from wiki.infer import apply_inference


class TestReasoning(unittest.TestCase):
    def test_full_reasoning_pipeline(self) -> None:
        """Test that custom axioms flow into the central graph and expand it successfully."""
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir) / "wiki"
            wiki_dir.mkdir()
            
            # Create an axiom: Person subClassOf Agent
            axiom_content = """
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix schema: <https://schema.org/> .
schema:Person rdfs:subClassOf schema:Agent .
"""
            (wiki_dir / "custom-axiom.ttl").write_text(axiom_content, encoding="utf-8")
            
            # Create a mini wiki page stating Gregory is a Person
            (wiki_dir / "gregory.md").write_text("""---
type: Person
givenName: Gregory
---
""", encoding="utf-8")
            
            # 1. Configure and Load
            config = Config(wiki={"input": [wiki_dir]})
            
            # Disable auto inference in loader to confirm pre/post state
            graph = load_graph(config, infer=False)
            
            schema = Namespace("https://schema.org/")
            gregory = URIRef("https://wiki.example.org/gregory")
            
            # Confirm pre-state: has axiom, has type, but NO inferred Agent yet
            self.assertTrue((schema.Person, RDFS.subClassOf, schema.Agent) in graph)
            self.assertFalse((gregory, RDF.type, schema.Agent) in graph)
            
            # 2. Run Inference
            expanded_graph = apply_inference(graph, config)
            
            # 3. Confirm post-state: Derivation worked!
            self.assertTrue((gregory, RDF.type, schema.Agent) in expanded_graph)

if __name__ == "__main__":
    unittest.main()
