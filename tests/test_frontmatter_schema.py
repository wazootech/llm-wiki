import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

from wiki.audit import _run_check as run_check
from wiki.config import Config
from wiki.frontmatter_schema import (
    JSON_SCHEMA_KEY,
    TARGET_CLASS_KEY,
    build_type_schema_registry,
    check_frontmatter_schema,
    coerce_schema_refs,
    is_schema_binding_document,
    validation_payload,
)
from wiki.schemas import AuditReport


class TestFrontmatterSchemaHelpers(unittest.TestCase):
    def test_coerce_schema_refs_scalar_and_list(self) -> None:
        self.assertEqual(coerce_schema_refs("schemas/a.json"), ["schemas/a.json"])
        self.assertEqual(
            coerce_schema_refs(["schemas/a.json", "schemas/b.json"]),
            ["schemas/a.json", "schemas/b.json"],
        )
        self.assertIsNone(coerce_schema_refs(None))

    def test_coerce_schema_refs_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            coerce_schema_refs(42)
        with self.assertRaises(ValueError):
            coerce_schema_refs(["schemas/a.json", 1])

    def test_is_schema_binding_document(self) -> None:
        self.assertTrue(
            is_schema_binding_document(
                {
                    "type": "sh:NodeShape",
                    TARGET_CLASS_KEY: "schema:Person",
                    JSON_SCHEMA_KEY: "schemas/person.json",
                }
            )
        )
        self.assertFalse(is_schema_binding_document({TARGET_CLASS_KEY: "schema:Person"}))

    def test_validation_payload_excludes_schema_and_shacl_keys(self) -> None:
        payload = validation_payload(
            {
                "type": "TechArticle",
                "headline": "Title",
                JSON_SCHEMA_KEY: "schemas/extra.json",
                TARGET_CLASS_KEY: "schema:TechArticle",
                "sh:property": [],
            }
        )
        self.assertEqual(payload, {"type": "TechArticle", "headline": "Title"})


class TestFrontmatterSchemaValidation(unittest.TestCase):
    def _write_schema(self, root: Path, rel: str, schema: dict) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema), encoding="utf-8")

    def _person_schema(self) -> dict:
        return {
            "type": "object",
            "required": ["givenName", "familyName"],
            "properties": {
                "givenName": {"type": "string", "minLength": 1},
                "familyName": {"type": "string", "minLength": 1},
            },
        }

    def test_type_binding_validates_matching_documents(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(root, "schemas/person.json", self._person_schema())
            (wiki / "Person_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Person\n"
                "wazoo:jsonSchema: schemas/person.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Valid.md").write_text(
                "---\ntype: schema:Person\ngivenName: Ada\nfamilyName: Lovelace\n---\n",
                encoding="utf-8",
            )
            (wiki / "Invalid.md").write_text(
                "---\ntype: schema:Person\ngivenName: Ada\n---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 1)
            self.assertIn("In Invalid:", validation[0])
            self.assertIn("familyName", validation[0])

    def test_binding_document_is_not_validated_as_instance(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(
                root,
                "schemas/shape-only.json",
                {"type": "object", "required": ["headline"], "properties": {"headline": {"type": "string"}}},
            )
            (wiki / "Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Person\n"
                "wazoo:jsonSchema: schemas/shape-only.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(missing, [])
            self.assertEqual(validation, [])

    def test_per_page_schema_appends_to_type_binding(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(root, "schemas/person.json", self._person_schema())
            self._write_schema(
                root,
                "schemas/extra.json",
                {"type": "object", "required": ["nickname"], "properties": {"nickname": {"type": "string"}}},
            )
            (wiki / "Person_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Person\n"
                "wazoo:jsonSchema: schemas/person.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Page.md").write_text(
                "---\n"
                "type: schema:Person\n"
                "givenName: Ada\n"
                "familyName: Lovelace\n"
                "wazoo:jsonSchema: schemas/extra.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 1)
            self.assertIn("nickname", validation[0])

    def test_missing_local_schema_ref(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Person_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Person\n"
                "wazoo:jsonSchema: schemas/missing.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Page.md").write_text(
                "---\ntype: schema:Person\ngivenName: Ada\nfamilyName: Lovelace\n---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(validation, [])
            self.assertEqual(len(missing), 2)
            self.assertTrue(any("missing.json" in issue for issue in missing))

    def test_scoped_check_uses_full_registry(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(root, "schemas/person.json", self._person_schema())
            (wiki / "Person_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Person\n"
                "wazoo:jsonSchema: schemas/person.json\n"
                "---\n",
                encoding="utf-8",
            )
            invalid = wiki / "Invalid.md"
            invalid.write_text("---\ntype: schema:Person\ngivenName: Ada\n---\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config, file_paths=[invalid])
            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 1)

    def test_remote_schema_ref(self) -> None:
        remote_schema = {
            "type": "object",
            "required": ["label"],
            "properties": {"label": {"type": "string"}},
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, max_bytes: int):
                return json.dumps(remote_schema).encode("utf-8")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Remote_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Thing\n"
                "wazoo:jsonSchema: https://example.org/schema.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Good.md").write_text(
                "---\ntype: schema:Thing\nlabel: ok\n---\n",
                encoding="utf-8",
            )
            (wiki / "Bad.md").write_text(
                "---\ntype: schema:Thing\n---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            with patch("wiki.frontmatter_schema.urlopen", return_value=FakeResponse()):
                missing, validation = check_frontmatter_schema(config)

            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 1)
            self.assertIn("In Bad:", validation[0])

    def test_remote_schema_ref_denied_without_network(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Remote_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Thing\n"
                "wazoo:jsonSchema: https://example.org/schema.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(
                wiki={"input": [wiki]},
                config_root=root,
                check={"remote_schema_refs": "deny"},
            )

            with patch("wiki.frontmatter_schema.urlopen", side_effect=AssertionError("network call")):
                missing, validation = check_frontmatter_schema(config)

            self.assertEqual(len(missing), 1)
            self.assertIn("remote schema refs are disabled", missing[0])
            self.assertEqual(validation, [])

    def test_remote_schema_ref_allowlist_blocks_unknown_host(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Remote_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Thing\n"
                "wazoo:jsonSchema: https://example.org/schema.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(
                wiki={"input": [wiki]},
                config_root=root,
                check={
                    "remote_schema_refs": "allowlist",
                    "remote_schema_hosts": ["schemas.example.org"],
                },
            )

            with patch("wiki.frontmatter_schema.urlopen", side_effect=AssertionError("network call")):
                missing, validation = check_frontmatter_schema(config)

            self.assertEqual(len(missing), 1)
            self.assertIn("not allowed by check.remote_schema_hosts", missing[0])
            self.assertEqual(validation, [])

    def test_remote_schema_ref_allowlist_allows_matching_host(self) -> None:
        remote_schema = {
            "type": "object",
            "required": ["label"],
            "properties": {"label": {"type": "string"}},
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self, max_bytes: int):
                return json.dumps(remote_schema).encode("utf-8")

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Remote_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Thing\n"
                "wazoo:jsonSchema: https://example.org/schema.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Good.md").write_text(
                "---\ntype: schema:Thing\nlabel: ok\n---\n",
                encoding="utf-8",
            )
            (wiki / "Bad.md").write_text(
                "---\ntype: schema:Thing\n---\n",
                encoding="utf-8",
            )
            config = Config(
                wiki={"input": [wiki]},
                config_root=root,
                check={
                    "remote_schema_refs": "allowlist",
                    "remote_schema_hosts": ["example.org"],
                },
            )

            with patch("wiki.frontmatter_schema.urlopen", return_value=FakeResponse()) as mock_urlopen:
                missing, validation = check_frontmatter_schema(config)

            mock_urlopen.assert_called_once()
            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 1)
            self.assertIn("In Bad:", validation[0])

    def test_build_type_schema_registry_dedupes_refs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            for name in ("A_Shape.md", "B_Shape.md"):
                (wiki / name).write_text(
                    "---\n"
                    "type: sh:NodeShape\n"
                    "sh:targetClass: schema:Person\n"
                    "wazoo:jsonSchema: schemas/person.json\n"
                    "---\n",
                    encoding="utf-8",
                )
            config = Config(wiki={"input": [wiki]}, config_root=root)
            registry = build_type_schema_registry(config)
            self.assertEqual(registry["https://schema.org/Person"], ["schemas/person.json"])

    def test_run_check_includes_frontmatter_schema_errors(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(
                root,
                "schemas/article.json",
                {
                    "type": "object",
                    "required": ["headline", "description"],
                    "properties": {
                        "headline": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            )
            (wiki / "Article_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:TechArticle\n"
                "wazoo:jsonSchema: schemas/article.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Broken.md").write_text("---\ntype: TechArticle\nheadline: Only\n---\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            results = run_check(config)
            self.assertFalse(results.ok)
            self.assertTrue(any("description" in err.message for err in results.errors))

    def _setup_severity_fixture(self, root: Path) -> Path:
        wiki = root / "wiki"
        wiki.mkdir()
        self._write_schema(
            root,
            "schemas/article.json",
            {
                "type": "object",
                "required": ["headline", "description"],
                "properties": {
                    "headline": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        )
        (wiki / "Article_Shape.md").write_text(
            "---\n"
            "type: sh:NodeShape\n"
            "sh:targetClass: schema:TechArticle\n"
            "wazoo:jsonSchema: schemas/article.json\n"
            "---\n",
            encoding="utf-8",
        )
        (wiki / "Gadget_Shape.md").write_text(
            "---\n"
            "type: sh:NodeShape\n"
            "sh:targetClass: schema:Product\n"
            "wazoo:jsonSchema: schemas/missing.json\n"
            "---\n",
            encoding="utf-8",
        )
        (wiki / "Broken.md").write_text("---\ntype: TechArticle\nheadline: Only\n---\n", encoding="utf-8")
        (wiki / "Product.md").write_text("---\ntype: schema:Product\nname: Gadget\n---\n", encoding="utf-8")
        return wiki

    @staticmethod
    def _issue_messages(report: AuditReport) -> list[str]:
        errors, warnings = report.messages()
        return errors + warnings

    @staticmethod
    def _missing_ref_messages(results: AuditReport) -> list[str]:
        return [msg for msg in TestFrontmatterSchemaValidation._issue_messages(results) if "missing.json" in msg]

    @staticmethod
    def _validation_messages(results: AuditReport) -> list[str]:
        return [msg for msg in TestFrontmatterSchemaValidation._issue_messages(results) if "description" in msg]

    def test_run_check_frontmatter_schema_severity_matrix(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = self._setup_severity_fixture(root)
            base = {"wiki": {"input": [wiki]}, "config_root": root}

            for severity, expect_errors, expect_warnings, expect_conforms in (
                ("off", 0, 0, True),
                ("warning", 0, 1, True),
                ("error", 1, 0, False),
            ):
                with self.subTest(severity=severity):
                    config = Config(
                        **base,
                        check={
                            "frontmatter_schema": severity,
                            "missing_schema_ref": "off",
                        },
                    )
                    results = run_check(config)
                    validation_errors = [
                        issue.message for issue in results.errors if "description" in issue.message
                    ]
                    validation_warnings = [
                        issue.message for issue in results.warnings if "description" in issue.message
                    ]
                    self.assertEqual(len(validation_errors), expect_errors)
                    self.assertEqual(len(validation_warnings), expect_warnings)
                    self.assertEqual(results.ok, expect_conforms)

    def test_run_check_missing_schema_ref_severity_matrix(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = self._setup_severity_fixture(root)
            base = {"wiki": {"input": [wiki]}, "config_root": root}

            for severity, expect_errors, expect_warnings, expect_conforms in (
                ("off", 0, 0, True),
                ("warning", 0, 1, True),
                ("error", 1, 0, False),
            ):
                with self.subTest(severity=severity):
                    config = Config(
                        **base,
                        check={
                            "frontmatter_schema": "off",
                            "missing_schema_ref": severity,
                        },
                    )
                    results = run_check(config)
                    missing_errors = [
                        issue.message for issue in results.errors if "missing.json" in issue.message
                    ]
                    missing_warnings = [
                        issue.message for issue in results.warnings if "missing.json" in issue.message
                    ]
                    self.assertGreaterEqual(len(missing_errors), expect_errors)
                    self.assertGreaterEqual(len(missing_warnings), expect_warnings)
                    if severity == "off":
                        self.assertEqual(missing_errors, [])
                        self.assertEqual(missing_warnings, [])
                    elif severity == "warning":
                        self.assertEqual(missing_errors, [])
                        self.assertGreater(len(missing_warnings), 0)
                    else:
                        self.assertGreater(len(missing_errors), 0)
                        self.assertEqual(missing_warnings, [])
                    self.assertEqual(results.ok, expect_conforms)

    def test_run_check_both_schema_rules_off_skips_validation(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = self._setup_severity_fixture(root)
            config = Config(
                wiki={"input": [wiki]},
                config_root=root,
                check={"frontmatter_schema": "off", "missing_schema_ref": "off"},
            )

            results = run_check(config)
            self.assertTrue(results.ok)
            self.assertEqual(self._missing_ref_messages(results), [])
            self.assertEqual(self._validation_messages(results), [])

    def test_page_list_schema_union(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(
                root,
                "schemas/a.json",
                {"type": "object", "required": ["foo"], "properties": {"foo": {"type": "string"}}},
            )
            self._write_schema(
                root,
                "schemas/b.json",
                {"type": "object", "required": ["bar"], "properties": {"bar": {"type": "string"}}},
            )
            (wiki / "Page.md").write_text(
                "---\n"
                "type: schema:WebPage\n"
                "name: List union\n"
                "foo: ok\n"
                "wazoo:jsonSchema:\n"
                "  - schemas/a.json\n"
                "  - schemas/b.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 1)
            self.assertIn("bar", validation[0])

            (wiki / "Page.md").unlink()
            (wiki / "PageBoth.md").write_text(
                "---\n"
                "type: schema:WebPage\n"
                "name: Both missing\n"
                "wazoo:jsonSchema:\n"
                "  - schemas/a.json\n"
                "  - schemas/b.json\n"
                "---\n",
                encoding="utf-8",
            )
            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(missing, [])
            self.assertEqual(len(validation), 2)
            self.assertTrue(any("foo" in issue for issue in validation))
            self.assertTrue(any("bar" in issue for issue in validation))

    def test_missing_schema_ref_outside_config_root(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            outside = root.parent / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            (wiki / "Page.md").write_text(
                "---\n"
                "type: schema:WebPage\n"
                "name: Escape\n"
                "wazoo:jsonSchema: ../outside.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(validation, [])
            self.assertEqual(len(missing), 1)
            self.assertIn("under the wiki config root", missing[0])

    def test_missing_schema_ref_non_json_extension(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            self._write_schema(root, "schemas/rules.yaml", {"type": "object"})
            (wiki / "Page.md").write_text(
                "---\n"
                "type: schema:WebPage\n"
                "name: Wrong ext\n"
                "wazoo:jsonSchema: schemas/rules.yaml\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            missing, validation = check_frontmatter_schema(config)
            self.assertEqual(validation, [])
            self.assertEqual(len(missing), 1)
            self.assertIn(".json", missing[0])

    def test_missing_schema_ref_invalid_json_schema_document(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            broken = root / "schemas" / "broken.json"
            broken.parent.mkdir(parents=True, exist_ok=True)
            broken.write_text(json.dumps({"type": "object"}), encoding="utf-8")
            (wiki / "Page.md").write_text(
                "---\n"
                "type: schema:WebPage\n"
                "name: Bad schema\n"
                "wazoo:jsonSchema: schemas/broken.json\n"
                "---\n",
                encoding="utf-8",
            )
            config = Config(wiki={"input": [wiki]}, config_root=root)

            with patch(
                "wiki.frontmatter_schema.Draft202012Validator",
                side_effect=ValueError("schema document is invalid"),
            ):
                missing, validation = check_frontmatter_schema(config)

            self.assertEqual(validation, [])
            self.assertEqual(len(missing), 1)
            self.assertIn("invalid JSON Schema", missing[0])

    def test_remote_schema_ref_http_error(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Remote_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Thing\n"
                "wazoo:jsonSchema: https://example.org/schema.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Page.md").write_text("---\ntype: schema:Thing\nlabel: ok\n---\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            def raise_http_error(*args, **kwargs):
                raise HTTPError(
                    url="https://example.org/schema.json",
                    code=404,
                    msg="Not Found",
                    hdrs=None,
                    fp=None,
                )

            with patch("wiki.frontmatter_schema.urlopen", side_effect=raise_http_error):
                missing, validation = check_frontmatter_schema(config)

            self.assertEqual(validation, [])
            self.assertGreater(len(missing), 0)
            self.assertTrue(any("HTTP 404" in issue for issue in missing))

    def test_remote_schema_ref_timeout(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wiki = root / "wiki"
            wiki.mkdir()
            (wiki / "Remote_Shape.md").write_text(
                "---\n"
                "type: sh:NodeShape\n"
                "sh:targetClass: schema:Thing\n"
                "wazoo:jsonSchema: https://example.org/schema.json\n"
                "---\n",
                encoding="utf-8",
            )
            (wiki / "Page.md").write_text("---\ntype: schema:Thing\nlabel: ok\n---\n", encoding="utf-8")
            config = Config(wiki={"input": [wiki]}, config_root=root)

            with patch("wiki.frontmatter_schema.urlopen", side_effect=TimeoutError):
                missing, validation = check_frontmatter_schema(config)

            self.assertEqual(validation, [])
            self.assertGreater(len(missing), 0)
            self.assertTrue(any("timed out" in issue for issue in missing))


if __name__ == "__main__":
    unittest.main()
