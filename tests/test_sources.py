import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import yaml

from wiki.config import Config
from wiki.schemas.sources import LOCKFILE_VERSION, LockedSource, Lockfile, SourceConfig
from wiki.sources import (
    _discover_sources,
    _expand_source_url,
    _install_tree,
    _remove_orphans,
)


class TestSourceConfig(unittest.TestCase):
    def test_minimal_source(self) -> None:
        source = SourceConfig(name="test", type="git", url="https://example.com/repo.git")
        self.assertEqual(source.name, "test")
        self.assertEqual(source.type, "git")
        self.assertEqual(source.url, "https://example.com/repo.git")
        self.assertIsNone(source.ref)
        self.assertIsNone(source.path)

    def test_full_source(self) -> None:
        source = SourceConfig(name="test", type="git", url="https://example.com/repo.git", ref="v1.0.0", path="wiki")
        self.assertEqual(source.ref, "v1.0.0")
        self.assertEqual(source.path, "wiki")

    def test_rejects_extra_fields(self) -> None:
        with self.assertRaises(ValueError):
            SourceConfig(name="test", type="git", url="https://example.com/repo.git", unknown="bad")

    def test_rejects_invalid_type(self) -> None:
        with self.assertRaises(ValueError):
            SourceConfig(name="test", type="http", url="https://example.com/repo.git")


class TestLockfile(unittest.TestCase):
    def test_empty_lockfile(self) -> None:
        lf = Lockfile()
        self.assertEqual(lf.version, LOCKFILE_VERSION)
        self.assertEqual(lf.sources, {})

    def test_load_non_existent(self) -> None:
        lf = Lockfile.load(Path("/nonexistent/wiki.lock"))
        self.assertEqual(lf.sources, {})

    def test_save_and_load_roundtrip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "wiki.lock"
            lf = Lockfile(
                sources={
                    "test": LockedSource(
                        url="https://example.com/repo.git",
                        resolved_ref="abc123def456",
                        ref="v1.0.0",
                        fetched_at="2025-01-01T00:00:00+00:00",
                    )
                }
            )
            lf.save(lock_path)
            self.assertTrue(lock_path.exists())

            loaded = Lockfile.load(lock_path)
            self.assertEqual(loaded.version, LOCKFILE_VERSION)
            self.assertIn("test", loaded.sources)
            self.assertEqual(loaded.sources["test"].url, "https://example.com/repo.git")
            self.assertEqual(loaded.sources["test"].resolved_ref, "abc123def456")

    def test_load_corrupted(self) -> None:
        with TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "wiki.lock"
            lock_path.write_text("{invalid json", encoding="utf-8")
            lf = Lockfile.load(lock_path)
            self.assertEqual(lf.sources, {})

    def test_timestamp_format(self) -> None:
        ts = Lockfile.timestamp()
        self.assertIn("T", ts)
        self.assertIn("+", ts)

    def test_required_by_roundtrip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "wiki.lock"
            lf = Lockfile(
                sources={
                    "leaf": LockedSource(
                        url="https://example.com/leaf.git",
                        resolved_ref="aaa",
                        fetched_at="2025-01-01T00:00:00+00:00",
                        required_by=["root"],
                    ),
                    "root": LockedSource(
                        url="https://example.com/root.git",
                        resolved_ref="bbb",
                        fetched_at="2025-01-01T00:00:00+00:00",
                        required_by=[],
                    ),
                }
            )
            lf.save(lock_path)
            loaded = Lockfile.load(lock_path)
            self.assertEqual(loaded.sources["leaf"].required_by, ["root"])
            self.assertEqual(loaded.sources["root"].required_by, [])

    def test_v1_backward_compat(self) -> None:
        """V1 lockfiles lack required_by; it should default to []."""
        with TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "wiki.lock"
            v1_data = {
                "version": 1,
                "sources": {
                    "old": {
                        "url": "https://example.com/old.git",
                        "resolved_ref": "abc",
                        "fetched_at": "2025-01-01T00:00:00+00:00",
                    }
                },
            }
            lock_path.write_text(json.dumps(v1_data), encoding="utf-8")
            loaded = Lockfile.load(lock_path)
            self.assertEqual(loaded.version, 1)
            self.assertEqual(loaded.sources["old"].required_by, [])

    def test_required_by_preserved_through_version_bump(self) -> None:
        """On save, required_by should be serialized and loadable."""
        with TemporaryDirectory() as tmpdir:
            lock_path = Path(tmpdir) / "wiki.lock"
            original = Lockfile(
                sources={
                    "mid": LockedSource(
                        url="https://example.com/mid.git",
                        resolved_ref="ccc",
                        fetched_at="2025-01-01T00:00:00+00:00",
                        required_by=["top"],
                    ),
                }
            )
            original.save(lock_path)
            raw = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertIn("required_by", raw["sources"]["mid"])
            self.assertEqual(raw["sources"]["mid"]["required_by"], ["top"])


class TestConfigSources(unittest.TestCase):
    def test_sources_list_syntax(self) -> None:
        config = Config(
            config_root=Path("."),
            sources=[
                {"name": "src1", "type": "git", "url": "https://example.com/a.git"},
                {"name": "src2", "type": "git", "url": "https://example.com/b.git"},
            ],
        )
        self.assertEqual(len(config.sources), 2)
        self.assertEqual(config.sources[0].name, "src1")
        self.assertEqual(config.sources[1].name, "src2")

    def test_sources_none(self) -> None:
        config = Config(config_root=Path("."))
        self.assertEqual(config.sources, [])

    def test_sources_rejects_duplicate_names(self) -> None:
        with self.assertRaises(ValueError):
            Config(
                config_root=Path("."),
                sources=[
                    {"name": "src1", "type": "git", "url": "https://example.com/a.git"},
                    {"name": "src1", "type": "git", "url": "https://example.com/b.git"},
                ],
            )

    def test_sources_rejects_missing_name(self) -> None:
        with self.assertRaises(ValueError):
            Config(
                config_root=Path("."),
                sources=[{"type": "git", "url": "https://example.com/a.git"}],
            )

    def test_sources_loaded_from_yaml(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            yaml_content = {
                "wiki": {"input": "wiki"},
                "sources": [
                    {"name": "taxonomy", "type": "git", "url": "https://example.com/taxonomy.git", "ref": "v1.0"},
                    {"name": "community", "type": "git", "url": "https://example.com/community.git"},
                ],
            }
            (base_path / "wiki.yaml").write_text(yaml.dump(yaml_content), encoding="utf-8")
            config = Config.load(base_path)
            self.assertEqual(len(config.sources), 2)
            self.assertEqual(config.sources[0].name, "taxonomy")
            self.assertEqual(config.sources[0].ref, "v1.0")

    def test_sources_unknown_keys_rejected(self) -> None:
        with TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            (base_path / "wiki.yaml").write_text(
                yaml.dump({
                    "wiki": {"input": "wiki"},
                    "sources": [{"name": "bad", "type": "git", "url": "https://x.com", "extra": True}],
                }),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                Config.load(base_path)

    def test_sources_rejects_dict_syntax(self) -> None:
        with self.assertRaises(ValueError):
            Config(config_root=Path("."), sources={"src1": {"type": "git", "url": "https://x.com"}})


class TestExpandSourceUrl(unittest.TestCase):
    def test_owner_repo_shorthand(self) -> None:
        self.assertEqual(
            _expand_source_url("EthanThatOneKid/solar-system-wiki"),
            "https://github.com/EthanThatOneKid/solar-system-wiki.git",
        )

    def test_owner_repo_with_dot_git(self) -> None:
        self.assertEqual(
            _expand_source_url("EthanThatOneKid/solar-system-wiki.git"),
            "https://github.com/EthanThatOneKid/solar-system-wiki.git",
        )

    def test_full_https_url_passthrough(self) -> None:
        url = "https://github.com/EthanThatOneKid/solar-system-wiki.git"
        self.assertEqual(_expand_source_url(url), url)

    def test_ssh_url_passthrough(self) -> None:
        url = "git@github.com:EthanThatOneKid/solar-system-wiki.git"
        self.assertEqual(_expand_source_url(url), url)

    def test_third_party_url_passthrough(self) -> None:
        url = "https://gitlab.com/owner/repo.git"
        self.assertEqual(_expand_source_url(url), url)

    def test_single_word_no_slash_passthrough(self) -> None:
        url = "myrepo"
        self.assertEqual(_expand_source_url(url), url)

    def test_triple_path_segment_passthrough(self) -> None:
        url = "a/b/c"
        self.assertEqual(_expand_source_url(url), url)


class TestDiscoverSources(unittest.TestCase):
    def test_no_config_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            sources = _discover_sources(Path(tmpdir))
            self.assertEqual(sources, [])

    def test_no_sources_block(self) -> None:
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "wiki.yml").write_text(
                yaml.dump({"wiki": {"input": "pages"}}), encoding="utf-8"
            )
            sources = _discover_sources(Path(tmpdir))
            self.assertEqual(sources, [])

    def test_has_sources(self) -> None:
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "wiki.yml").write_text(
                yaml.dump({
                    "wiki": {"input": "pages"},
                    "sources": [
                        {"name": "dep-a", "type": "git", "url": "https://example.com/a.git"},
                        {"name": "dep-b", "type": "git", "url": "https://example.com/b.git", "ref": "v1.0"},
                    ],
                }),
                encoding="utf-8",
            )
            sources = _discover_sources(Path(tmpdir))
            self.assertEqual(len(sources), 2)
            self.assertEqual(sources[0].name, "dep-a")
            self.assertEqual(sources[0].url, "https://example.com/a.git")
            self.assertEqual(sources[1].name, "dep-b")
            self.assertEqual(sources[1].ref, "v1.0")

    def test_prefers_wiki_yml_over_yaml(self) -> None:
        """wiki.yml should be found before wiki.yaml (CONFIG_FILENAMES order)."""
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "wiki.yml").write_text(
                yaml.dump({"sources": [{"name": "from-yml", "type": "git", "url": "https://x.com"}]}),
                encoding="utf-8",
            )
            (Path(tmpdir) / "wiki.yaml").write_text(
                yaml.dump({"sources": [{"name": "from-yaml", "type": "git", "url": "https://y.com"}]}),
                encoding="utf-8",
            )
            sources = _discover_sources(Path(tmpdir))
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0].name, "from-yml")

    def test_malformed_yaml_returns_empty(self) -> None:
        with TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "wiki.yml").write_text("{invalid: yaml: [[[", encoding="utf-8")
            sources = _discover_sources(Path(tmpdir))
            self.assertEqual(sources, [])


def _make_mock_git(
    config_root: Path,
    *,
    repo_factory: dict[str, list[SourceConfig]],
    fake_sha: str = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
):
    """Create mock patches for git operations.

    ``repo_factory`` maps source names to their transitive deps, or ``[]``
    for leaf sources.  Each mock repo directory gets a ``wiki.yml`` written
    when the source has transitive deps.
    """
    def mock_clone_or_fetch(source, cache_dir):
        repo_dir = cache_dir / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        deps = repo_factory.get(source.name, [])
        if deps:
            (repo_dir / "wiki.yml").write_text(
                yaml.dump({
                    "wiki": {"input": "pages"},
                    "sources": [d.model_dump() for d in deps],
                }),
                encoding="utf-8",
            )
        return repo_dir

    def mock_prepare_ref(source, repo_dir):
        pass

    def mock_resolve_ref(ref, repo_dir):
        return fake_sha

    return (
        patch("wiki.sources._git_clone_or_fetch", side_effect=mock_clone_or_fetch),
        patch("wiki.sources._git_prepare_ref", side_effect=mock_prepare_ref),
        patch("wiki.sources._git_resolve_ref", side_effect=mock_resolve_ref),
    )


class TestInstallTree(unittest.TestCase):
    def _make_config(self, root: Path, sources: list[dict]) -> Config:
        return Config(
            config_root=root,
            wiki={"input": ["wiki"]},
            sources=sources,
        )

    def test_install_leaf_source(self) -> None:
        """A single source with no transitive deps."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = self._make_config(root, [
                {"name": "leaf", "type": "git", "url": "https://example.com/leaf.git"},
            ])
            lockfile = Lockfile()

            mock_a, mock_b, mock_c = _make_mock_git(root, repo_factory={"leaf": []})
            with mock_a, mock_b, mock_c:
                _install_tree(
                    config, config.sources, lockfile,
                    parent=None, visited=set(), path=[],
                )

            self.assertIn("leaf", lockfile.sources)
            self.assertEqual(lockfile.sources["leaf"].required_by, [])
            self.assertEqual(lockfile.sources["leaf"].resolved_ref, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")

    def test_install_transitive(self) -> None:
        """A depends on B; both should be locked with correct required_by."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = self._make_config(root, [
                {"name": "A", "type": "git", "url": "https://example.com/A.git"},
            ])
            lockfile = Lockfile()

            dep_b = [SourceConfig(name="B", type="git", url="https://example.com/B.git")]
            mock_a, mock_b, mock_c = _make_mock_git(
                root, repo_factory={"A": dep_b, "B": []},
            )
            with mock_a, mock_b, mock_c:
                _install_tree(
                    config, config.sources, lockfile,
                    parent=None, visited=set(), path=[],
                )

            self.assertIn("A", lockfile.sources)
            self.assertIn("B", lockfile.sources)
            self.assertEqual(lockfile.sources["A"].required_by, [])
            self.assertEqual(lockfile.sources["B"].required_by, ["A"])

    def test_cycle_detection(self) -> None:
        """A -> B -> A raises RuntimeError."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = self._make_config(root, [
                {"name": "A", "type": "git", "url": "https://example.com/A.git"},
            ])
            lockfile = Lockfile()

            dep_a = [SourceConfig(name="A", type="git", url="https://example.com/A.git")]
            dep_b = [SourceConfig(name="B", type="git", url="https://example.com/B.git")]
            # A -> B -> A
            mock_a, mock_b, mock_c = _make_mock_git(
                root, repo_factory={"A": dep_b, "B": dep_a},
            )
            with mock_a, mock_b, mock_c:
                with self.assertRaises(RuntimeError) as ctx:
                    _install_tree(
                        config, config.sources, lockfile,
                        parent=None, visited=set(), path=[],
                    )
            self.assertIn("Circular dependency", str(ctx.exception))
            self.assertIn("A -> B -> A", str(ctx.exception))

    def test_dedup(self) -> None:
        """A and B both depend on C; single lockfile entry with both parents."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = self._make_config(root, [
                {"name": "A", "type": "git", "url": "https://example.com/A.git"},
                {"name": "B", "type": "git", "url": "https://example.com/B.git"},
            ])
            lockfile = Lockfile()

            dep_c = [SourceConfig(name="C", type="git", url="https://example.com/C.git")]
            mock_a, mock_b, mock_c = _make_mock_git(
                root, repo_factory={"A": dep_c, "B": dep_c, "C": []},
            )
            with mock_a, mock_b, mock_c:
                _install_tree(
                    config, config.sources, lockfile,
                    parent=None, visited=set(), path=[],
                )

            self.assertIn("C", lockfile.sources)
            self.assertCountEqual(lockfile.sources["C"].required_by, ["A", "B"])

    def test_ref_conflict(self) -> None:
        """A and B declare same name with different refs → error."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lockfile = Lockfile()

            # Simulate A already installing dep "shared" at v1
            lockfile.sources["shared"] = LockedSource(
                url="https://example.com/shared.git",
                resolved_ref="aaa",
                ref="v1.0",
                fetched_at="2025-01-01T00:00:00+00:00",
                required_by=["A"],
            )

            # B tries to install the same name at v2 — conflict
            visited: set[str] = set(lockfile.sources.keys())
            conflict_source = SourceConfig(
                name="shared", type="git",
                url="https://example.com/shared.git", ref="v2.0",
            )

            with self.assertRaises(RuntimeError) as ctx:
                _install_tree(
                    config=self._make_config(root, []),
                    sources=[conflict_source],
                    lockfile=lockfile,
                    parent="B",
                    visited=visited,
                    path=[],
                )
            self.assertIn("conflict", str(ctx.exception))
            self.assertIn("shared", str(ctx.exception))

    def test_url_conflict(self) -> None:
        """A and B declare same name with different URLs → error."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lockfile = Lockfile()
            lockfile.sources["shared"] = LockedSource(
                url="https://example.com/old.git",
                resolved_ref="aaa",
                fetched_at="2025-01-01T00:00:00+00:00",
                required_by=["A"],
            )

            visited: set[str] = set(lockfile.sources.keys())
            conflict_source = SourceConfig(
                name="shared", type="git",
                url="https://example.com/new.git",
            )

            with self.assertRaises(RuntimeError) as ctx:
                _install_tree(
                    config=self._make_config(root, []),
                    sources=[conflict_source],
                    lockfile=lockfile,
                    parent="B",
                    visited=visited,
                    path=[],
                )
            self.assertIn("conflict", str(ctx.exception))

    def test_three_deep_chain(self) -> None:
        """A -> B -> C; all three locked."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = self._make_config(root, [
                {"name": "A", "type": "git", "url": "https://example.com/A.git"},
            ])
            lockfile = Lockfile()

            dep_b = [SourceConfig(name="B", type="git", url="https://example.com/B.git")]
            dep_c = [SourceConfig(name="C", type="git", url="https://example.com/C.git")]
            mock_a, mock_b, mock_c = _make_mock_git(
                root, repo_factory={"A": dep_b, "B": dep_c, "C": []},
            )
            with mock_a, mock_b, mock_c:
                _install_tree(
                    config, config.sources, lockfile,
                    parent=None, visited=set(), path=[],
                )

            self.assertEqual(lockfile.sources["A"].required_by, [])
            self.assertEqual(lockfile.sources["B"].required_by, ["A"])
            self.assertEqual(lockfile.sources["C"].required_by, ["B"])


class TestRemoveOrphans(unittest.TestCase):
    def _make_config(self, root: Path, sources: list[dict]) -> Config:
        return Config(
            config_root=root,
            wiki={"input": ["wiki"]},
            sources=sources,
        )

    def test_remove_orphan_cascade(self) -> None:
        """A -> B -> C; remove A, B and C orphaned and cleaned up."""
        root = Path("/mock")
        config = self._make_config(root, [
            {"name": "A", "type": "git", "url": "https://example.com/A.git"},
        ])
        lockfile = Lockfile()
        lockfile.sources["A"] = LockedSource(
            url="https://example.com/A.git", resolved_ref="aaa",
            required_by=[],
        )
        lockfile.sources["B"] = LockedSource(
            url="https://example.com/B.git", resolved_ref="bbb",
            required_by=["A"],
        )
        lockfile.sources["C"] = LockedSource(
            url="https://example.com/C.git", resolved_ref="ccc",
            required_by=["B"],
        )

        _remove_orphans(config, lockfile, "A")

        self.assertNotIn("B", lockfile.sources)
        self.assertNotIn("C", lockfile.sources)

    def test_shared_orphan_preserved(self) -> None:
        """A -> C and B -> C; remove A, C preserved because B still needs it."""
        root = Path("/mock")
        config = self._make_config(root, [
            {"name": "A", "type": "git", "url": "https://example.com/A.git"},
            {"name": "B", "type": "git", "url": "https://example.com/B.git"},
        ])
        lockfile = Lockfile()
        lockfile.sources["A"] = LockedSource(
            url="https://example.com/A.git", resolved_ref="aaa",
            required_by=[],
        )
        lockfile.sources["B"] = LockedSource(
            url="https://example.com/B.git", resolved_ref="bbb",
            required_by=[],
        )
        lockfile.sources["C"] = LockedSource(
            url="https://example.com/C.git", resolved_ref="ccc",
            required_by=["A", "B"],
        )

        _remove_orphans(config, lockfile, "A")

        self.assertIn("C", lockfile.sources)
        self.assertEqual(lockfile.sources["C"].required_by, ["B"])

    def test_top_level_source_not_orphaned(self) -> None:
        """A is still in config.sources so it should not be orphaned."""
        root = Path("/mock")
        config = self._make_config(root, [
            {"name": "A", "type": "git", "url": "https://example.com/A.git"},
        ])
        lockfile = Lockfile()
        lockfile.sources["A"] = LockedSource(
            url="https://example.com/A.git", resolved_ref="aaa",
            required_by=[],
        )

        _remove_orphans(config, lockfile, "does-not-exist")

        self.assertIn("A", lockfile.sources)

    def test_cache_removed_for_orphans(self) -> None:
        """Orphan's cache dir should be rm -rf'd."""
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = self._make_config(root, [
                {"name": "A", "type": "git", "url": "https://example.com/A.git"},
            ])

            # Create cache dirs for A, B
            (root / ".wiki" / "sources" / "A" / "repo").mkdir(parents=True)
            (root / ".wiki" / "sources" / "B" / "repo").mkdir(parents=True)

            lockfile = Lockfile()
            lockfile.sources["A"] = LockedSource(
                url="https://example.com/A.git", resolved_ref="aaa",
                required_by=[],
            )
            lockfile.sources["B"] = LockedSource(
                url="https://example.com/B.git", resolved_ref="bbb",
                required_by=["A"],
            )

            _remove_orphans(config, lockfile, "A")

            self.assertFalse((root / ".wiki" / "sources" / "B").exists())
            # A's cache is still there (the caller removed A separately)
            self.assertTrue((root / ".wiki" / "sources" / "A").exists())


if __name__ == "__main__":
    unittest.main()
