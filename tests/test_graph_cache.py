"""Tests for wiki fingerprinting and in-process graph cache."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from wiki import graph as graph_module
from wiki.config import Config
from wiki.graph import graph_stats, load_graph
from wiki.graph_cache import (
    cache_dir,
    clear_all_process_graphs,
    disk_cache_path,
    get_process_graph,
    wiki_fingerprint,
)


class TestGraphCache(unittest.TestCase):
    def setUp(self) -> None:
        clear_all_process_graphs()

    def tearDown(self) -> None:
        clear_all_process_graphs()

    def _config(self, wiki_dir: Path) -> Config:
        return Config(wiki={"input": [wiki_dir]}, config_root=wiki_dir)

    def test_second_load_reuses_cached_graph(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "page.md").write_text(
                "---\ntype: Person\ngivenName: Ada\n---\n",
                encoding="utf-8",
            )
            config = self._config(wiki_dir)

            g1 = load_graph(config, infer=False)
            self.assertGreater(graph_stats(g1)["triples"], 0)
            g2 = load_graph(config, infer=False)
            self.assertIs(g1, g2)

    def test_reload_rebuilds_graph(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "page.md"
            page.write_text("---\ntype: Person\ngivenName: Ada\n---\n", encoding="utf-8")
            config = self._config(wiki_dir)

            g1 = load_graph(config, infer=False)
            page.write_text("---\ntype: Person\ngivenName: Grace\n---\n", encoding="utf-8")
            g2 = load_graph(config, infer=False, reload=True)
            self.assertIsNot(g1, g2)

    def test_fingerprint_change_invalidates_cache_lookup(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "page.md"
            page.write_text("---\ntype: Person\ngivenName: Ada\n---\n", encoding="utf-8")
            config = self._config(wiki_dir)

            fp1 = wiki_fingerprint(config)
            load_graph(config, infer=False)
            self.assertIsNotNone(get_process_graph(config, infer=False))

            page.write_text("---\ntype: Person\ngivenName: Grace\n---\n", encoding="utf-8")
            fp2 = wiki_fingerprint(config)
            self.assertNotEqual(fp1, fp2)
            self.assertIsNone(get_process_graph(config, infer=False))

    def test_infer_and_asserted_caches_are_separate(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "page.md").write_text(
                "---\ntype: Person\ngivenName: Ada\n---\n",
                encoding="utf-8",
            )
            config = self._config(wiki_dir)

            asserted = load_graph(config, infer=False)
            inferred = load_graph(config, infer=True)
            self.assertIsNot(asserted, inferred)
            self.assertGreaterEqual(graph_stats(inferred)["triples"], graph_stats(asserted)["triples"])
            self.assertIsNotNone(get_process_graph(config, infer=False))
            self.assertIsNotNone(get_process_graph(config, infer=True))

    def test_config_change_changes_fingerprint(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "page.md").write_text(
                "---\ntype: Person\ngivenName: Ada\n---\n",
                encoding="utf-8",
            )
            config_a = Config(wiki={"input": [wiki_dir]}, graph={"base_iri": "https://a.example/"}, config_root=wiki_dir)
            config_b = Config(wiki={"input": [wiki_dir]}, graph={"base_iri": "https://b.example/"}, config_root=wiki_dir)

            self.assertNotEqual(wiki_fingerprint(config_a), wiki_fingerprint(config_b))

    def test_disk_cache_reuses_graph_across_cleared_process_cache(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "page.md").write_text(
                "---\ntype: Person\ngivenName: Ada\n---\n",
                encoding="utf-8",
            )
            config = self._config(wiki_dir)

            g1 = load_graph(config, infer=False, disk_cache=True)
            self.assertGreater(graph_stats(g1)["triples"], 0)
            self.assertTrue(disk_cache_path(config, infer=False).exists())

            clear_all_process_graphs()
            with patch("wiki.graph._build_graph_from_wiki", side_effect=AssertionError("should not rebuild wiki graph")):
                g2 = load_graph(config, infer=False, disk_cache=True)
            self.assertEqual(graph_stats(g1), graph_stats(g2))

    def test_disk_cache_invalidation_rebuilds_after_wiki_change(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            page = wiki_dir / "page.md"
            page.write_text("---\ntype: Person\ngivenName: Ada\n---\n", encoding="utf-8")
            config = self._config(wiki_dir)

            load_graph(config, infer=False, disk_cache=True)
            old_cache = disk_cache_path(config, infer=False)
            self.assertTrue(old_cache.exists())

            page.write_text("---\ntype: Person\ngivenName: Grace\n---\n", encoding="utf-8")
            clear_all_process_graphs()
            with patch("wiki.graph._build_graph_from_wiki", wraps=graph_module._build_graph_from_wiki) as wrapped_build:
                g2 = load_graph(config, infer=False, disk_cache=True)
                self.assertTrue(wrapped_build.called)
            self.assertGreater(graph_stats(g2)["triples"], 0)
            self.assertFalse(old_cache.exists())

    def test_reload_clears_current_disk_cache_entry(self) -> None:
        with TemporaryDirectory() as tmpdir:
            wiki_dir = Path(tmpdir)
            (wiki_dir / "page.md").write_text(
                "---\ntype: Person\ngivenName: Ada\n---\n",
                encoding="utf-8",
            )
            config = self._config(wiki_dir)

            load_graph(config, infer=False, disk_cache=True)
            cache_path = disk_cache_path(config, infer=False)
            self.assertTrue(cache_path.exists())

            load_graph(config, infer=False, disk_cache=True, reload=True)
            self.assertTrue(cache_path.exists())
            self.assertTrue(cache_dir(config).exists())


if __name__ == "__main__":
    unittest.main()
