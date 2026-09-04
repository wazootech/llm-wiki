"""Unified Config model matching the wiki config file nested block structure."""

from __future__ import annotations

import fnmatch
import json
import logging
import tomllib
from pathlib import Path
from typing import Any, Self

import yaml
from mdformat._conf import InvalidConfError, _validate_keys, _validate_values
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

from ..context import Context
from .rules import CheckConfig, LintConfig
from .sources import SourceConfig

logger = logging.getLogger(__name__)

_LINK_STYLES = frozenset({"standard", "wikilink"})
_LEGACY_LINK_STYLE_MAP = {"markdown": "standard", "obsidian": "wikilink"}
DEFAULT_LINK_STYLE = "standard"
DEFAULT_BASE_URL = "/wiki"
DEFAULT_URL_STYLE = "dir"
DEFAULT_WIKI_BASE = "https://wiki.example.org/"
VALID_URL_STYLES = {"dir", "file"}


def normalize_base_iri(value: str) -> str:
    """Ensure a document base IRI ends with a trailing slash."""
    return str(value).rstrip("/") + "/"
IMPLICIT_TYPES_POLICIES = frozenset({"fallback", "append"})
IMPLICIT_TYPES_POLICY = "fallback"

CONFIG_FILENAMES = ("wiki.yml", "wiki.yaml", "wiki.json", "wiki.toml")

_BLOCK_LABELS = {
    "wiki": "wiki",
    "graph": "graph",
    "site": "site",
    "link": "link",
    "check": "check",
    "lint": "lint",
    "sources": "sources",
    "sparql_service": "sparql_service",
}


def _coerce_str_or_list(value: object) -> list[str]:
    if value is None:
        return ["wiki"]
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"expected string or list of strings, got {type(value).__name__}")


def _coerce_optional_str_or_list(value: object) -> list[str] | None:
    if value is None:
        return None
    return _coerce_str_or_list(value)


def _coerce_path_list(value: object) -> list[Path]:
    if value is None:
        return [Path("wiki")]
    if isinstance(value, (str, Path)):
        return [Path(value)]
    if isinstance(value, list):
        return [Path(item) for item in value]
    raise ValueError(f"expected string, path, or list, got {type(value).__name__}")


def _looks_like_regex(value: str) -> bool:
    return any(ch in value for ch in "[]()\\")


def _severity_error(block_name: str, field: str, bad: object) -> ValueError:
    if block_name == "check" and field == "filename_pattern" and _looks_like_regex(str(bad)):
        return ValueError(
            "check.filename_pattern must be error, warning, or off; "
            "put the regex in wiki.filename_pattern"
        )
    return ValueError(
        f"Invalid {block_name}.{field} severity: {bad!r} (expected error, warning, or off)"
    )


def format_config_validation_error(config_name: str, exc: ValidationError) -> ValueError:
    extras: dict[str, list[str]] = {}
    top_level_extras: list[str] = []

    for error in exc.errors():
        if error["type"] == "extra_forbidden":
            loc = error["loc"]
            if len(loc) == 1:
                top_level_extras.append(str(loc[0]))
            elif len(loc) == 2 and loc[0] in _BLOCK_LABELS:
                block = str(loc[0])
                extras.setdefault(block, []).append(str(loc[1]))

    if top_level_extras:
        keys = ", ".join(sorted(top_level_extras))
        return ValueError(f"Invalid config file {config_name}: unknown top-level keys: {keys}")

    for block, keys in sorted(extras.items()):
        label = _BLOCK_LABELS[block]
        return ValueError(
            f"Invalid config file {config_name}: unknown {label} keys: {', '.join(sorted(keys))}"
        )

    for error in exc.errors():
        loc = error["loc"]
        msg = error.get("msg", "")
        if error["type"] == "extra_forbidden":
            continue
        if len(loc) == 1 and loc[0] == "fmt" and "fmt must be a mapping or path string" in msg:
            return ValueError(f"Invalid config file {config_name}: fmt must be a mapping or path string")
        if len(loc) >= 2 and loc[0] in _BLOCK_LABELS:
            block = str(loc[0])
            field = str(loc[1]) if len(loc) > 1 else ""
            if "expected error, warning, or off" in msg:
                bad = error.get("input")
                severity_exc = _severity_error(block, field, bad)
                return ValueError(f"Invalid config file {config_name}: {severity_exc}")
            if block == "link" and field == "style":
                bad = error.get("input")
                return ValueError(
                    f"Invalid config file {config_name}: Invalid link_style: {bad!r} (expected standard or wikilink)"
                )
        if len(loc) >= 2 and loc[0] == "lint":
            field = str(loc[1])
            if "expected error, warning, or off" in msg:
                bad = error.get("input")
                severity_exc = _severity_error("lint", field, bad)
                return ValueError(f"Invalid config file {config_name}: {severity_exc}")
        if len(loc) >= 2 and loc[0] == "check":
            field = str(loc[1])
            if "expected error, warning, or off" in msg:
                bad = error.get("input")
                severity_exc = _severity_error("check", field, bad)
                return ValueError(f"Invalid config file {config_name}: {severity_exc}")

    if len(exc.errors()) == 1:
        error = exc.errors()[0]
        loc = error["loc"]
        if len(loc) == 1 and loc[0] in _BLOCK_LABELS:
            block = str(loc[0])
            if error["type"] == "model_type":
                return ValueError(f"Invalid config file {config_name}: {block} must be a mapping")

    return ValueError(f"Invalid config file {config_name}: {exc}")


class FmtConfig(BaseModel):
    """Resolved fmt: inline mdformat options or a path to a TOML file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    options: dict[str, Any] | None = None
    toml: Path | None = None

    @classmethod
    def parse_raw(cls, fmt_data: Any, config_name: str, base_dir: Path) -> FmtConfig | None:
        if fmt_data is None:
            return None
        if isinstance(fmt_data, FmtConfig):
            return fmt_data
        if isinstance(fmt_data, dict):
            options = dict(fmt_data)
            if options.get("wrap") is False:
                options["wrap"] = "no"
            conf_label = Path(f"{config_name} fmt")
            try:
                _validate_keys(options, conf_label)
                _validate_values(options, conf_label)
            except InvalidConfError as exc:
                raise ValueError(f"Invalid config file {config_name}: {exc}") from exc
            return cls(options=options)
        if isinstance(fmt_data, str):
            text = fmt_data.strip()
            if not text:
                raise ValueError(f"Invalid config file {config_name}: fmt path must not be empty")
            path_obj = Path(text)
            if path_obj.is_absolute():
                raise ValueError(
                    f"Invalid config file {config_name}: fmt path must be relative to the config file"
                )
            return cls(toml=base_dir / path_obj)
        if isinstance(fmt_data, Path):
            if fmt_data.is_absolute():
                try:
                    fmt_data.relative_to(base_dir)
                except ValueError as exc:
                    raise ValueError(
                        f"Invalid config file {config_name}: fmt path must be relative to the config file"
                    ) from exc
                return cls(toml=fmt_data)
            return cls(toml=base_dir / fmt_data)
        raise ValueError(
            f"Invalid config file {config_name}: fmt must be a mapping or path string"
        )


def _resolve_path(value: str | Path, base_dir: Path) -> Path:
    path_obj = Path(value)
    return path_obj if path_obj.is_absolute() else base_dir / path_obj


def _parse_page_layout_path(layout_raw: str | Path | None, base_dir: Path) -> Path | None:
    if layout_raw is None:
        return None
    if isinstance(layout_raw, Path):
        return layout_raw.resolve() if layout_raw.is_absolute() else (base_dir / layout_raw).resolve()
    if not str(layout_raw).strip():
        return None
    p = Path(str(layout_raw).strip())
    return (p if p.is_absolute() else base_dir / p).resolve()


def normalize_url_style(value: str | None) -> str:
    normalized = str(value or DEFAULT_URL_STYLE).strip().lower()
    if normalized not in VALID_URL_STYLES:
        raise ValueError(f"Invalid url_style: {value}")
    return normalized


def normalize_api_path(value: str | None) -> str:
    raw = str(value or "/api/sparql").strip()
    if not raw.startswith("/"):
        raise ValueError(f"Invalid sparql_service.path: {value}")
    normalized = raw.rstrip("/")
    return normalized or "/"


def find_config_path(path: Path) -> Path | None:
    """Return wiki config file path when path is a file or searchable directory."""
    if path.is_file():
        return path
    for name in CONFIG_FILENAMES:
        candidate = path / name
        if candidate.exists():
            return candidate
    return None


class WikiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: list[Path] = Field(default_factory=lambda: [Path("wiki")])
    assets: list[Path] | None = None
    exclude: list[str] = Field(default_factory=list)
    filename_pattern: str | None = None

    @field_validator("input", mode="before")
    @classmethod
    def _validate_input(cls, value: object) -> list[Path]:
        return _coerce_path_list(value)

    @field_validator("assets", mode="before")
    @classmethod
    def _validate_assets(cls, value: object) -> list[Path] | None:
        if value is None:
            return None
        return _coerce_path_list(value)

    @field_validator("exclude", mode="before")
    @classmethod
    def _validate_exclude(cls, value: object) -> list[str]:
        if value is None:
            return []
        return _coerce_str_or_list(value)


class GraphConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    base_iri: str | None = None
    content_predicate: str | None = None
    include_file_extension: bool = False
    implicit_types: list[str] = Field(default_factory=list)
    implicit_types_policy: str = IMPLICIT_TYPES_POLICY
    context: dict[str, str | None] | None = Field(
        default=None,
        validation_alias=AliasChoices("context", "@context"),
    )

    @field_validator("base_iri", mode="before")
    @classmethod
    def _validate_base_iri(cls, value: object) -> str | None:
        if value is None:
            return None
        return normalize_base_iri(str(value))

    @field_validator("implicit_types", mode="before")
    @classmethod
    def _validate_implicit_types(cls, value: object) -> list[str]:
        if value is None:
            return []
        return _coerce_str_or_list(value)

    @field_validator("implicit_types_policy", mode="before")
    @classmethod
    def _validate_implicit_types_policy(cls, value: object) -> str:
        if value is None:
            return IMPLICIT_TYPES_POLICY
        normalized = str(value).strip().lower()
        if normalized not in IMPLICIT_TYPES_POLICIES:
            raise ValueError(f"expected fallback or append, got {value!r}")
        return normalized


class SiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layout: str | Path | None = None
    base_url: str | None = None
    url_style: str | None = None


class LinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str = DEFAULT_LINK_STYLE
    renames: dict[str, str] | None = None

    @field_validator("style", mode="before")
    @classmethod
    def _validate_style(cls, value: object) -> str:
        if value is None:
            return DEFAULT_LINK_STYLE
        if not isinstance(value, str):
            raise ValueError(f"expected standard or wikilink, got {value!r}")
        normalized = value.strip().lower()
        if normalized in _LEGACY_LINK_STYLE_MAP:
            new_style = _LEGACY_LINK_STYLE_MAP[normalized]
            logger.warning(
                "link.style: '%s' is deprecated, use '%s' instead "
                "(edit config file link.style and re-run)",
                normalized,
                new_style,
            )
            return new_style
        if normalized not in _LINK_STYLES:
            raise ValueError(f"expected standard or wikilink, got {value!r}")
        return normalized


class SparqlServiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    path: str = "/api/sparql"

    @field_validator("enabled", mode="before")
    @classmethod
    def _coerce_enabled(cls, value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            if value in (0, 1):
                return bool(value)
            raise ValueError(f"expected boolean enabled value, got {value!r}")
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"false", "0", "no", "off"}:
                return False
            if normalized in {"true", "1", "yes", "on"}:
                return True
            raise ValueError(f"expected boolean enabled value, got {value!r}")
        raise ValueError(f"expected boolean enabled value, got {value!r}")


class Config(BaseModel):
    """Wiki configuration: nested yaml blocks plus loader-injected config_root."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    wiki: WikiConfig = Field(default_factory=WikiConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    site: SiteConfig = Field(default_factory=SiteConfig)
    link: LinkConfig = Field(default_factory=LinkConfig)
    check: CheckConfig = Field(default_factory=CheckConfig)
    lint: LintConfig = Field(default_factory=LintConfig)
    sources: list[SourceConfig] = Field(default_factory=list)
    fmt: FmtConfig | dict[str, Any] | str | Path | None = None
    sparql_service: SparqlServiceConfig = Field(default_factory=SparqlServiceConfig)
    config_root: Path = Field(default_factory=Path.cwd)

    @field_validator("sources", mode="before")
    @classmethod
    def _validate_sources(cls, value: object) -> list[SourceConfig]:
        if value is None:
            return []
        if isinstance(value, list):
            seen: set[str] = set()
            result = []
            for item in value:
                if not isinstance(item, dict):
                    raise ValueError("each source must be a mapping")
                if "name" not in item:
                    raise ValueError("each source must have a name")
                name = item["name"]
                if name in seen:
                    raise ValueError(f"Duplicate source name: {name!r}")
                seen.add(name)
                result.append(SourceConfig(**item))
            return result
        raise ValueError("sources must be a list")

    @field_validator("fmt", mode="before")
    @classmethod
    def _validate_fmt(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, (dict, str, Path)):
            return value
        raise ValueError("fmt must be a mapping or path string")

    @model_validator(mode="after")
    def _resolve_runtime(self, info: ValidationInfo) -> Self:
        base_dir = self.config_root.absolute()
        config_name = ""
        if info.context:
            config_name = str(info.context.get("config_name", ""))

        def resolve_list(paths: list[Path]) -> list[Path]:
            return [_resolve_path(p, base_dir) for p in paths]

        inputs = resolve_list(self.wiki.input)
        if self.wiki.assets is None:
            assets_raw = [Path("assets")] if (base_dir / "assets").is_dir() else []
        else:
            assets_raw = list(self.wiki.assets)
        assets = resolve_list(assets_raw)

        exclude = [str(p).replace("\\", "/") for p in self.wiki.exclude]

        base_url = (self.site.base_url if self.site.base_url is not None else DEFAULT_BASE_URL).rstrip("/")
        url_style = normalize_url_style(self.site.url_style)
        layout = _parse_page_layout_path(self.site.layout, base_dir)

        sparql_path = normalize_api_path(self.sparql_service.path)

        fmt = FmtConfig.parse_raw(self.fmt, config_name, base_dir)

        object.__setattr__(self, "wiki", self.wiki.model_copy(update={
            "input": inputs,
            "assets": assets,
            "exclude": exclude,
        }))
        object.__setattr__(self, "site", self.site.model_copy(update={
            "base_url": base_url,
            "url_style": url_style,
            "layout": layout,
        }))
        object.__setattr__(self, "sparql_service", self.sparql_service.model_copy(update={
            "path": sparql_path,
        }))
        object.__setattr__(self, "fmt", fmt)
        return self

    @property
    def base_iri(self) -> str:
        if self.graph.base_iri:
            return self.graph.base_iri
        if self.graph.context and "wiki" in self.graph.context:
            return normalize_base_iri(self.graph.context["wiki"])
        return DEFAULT_WIKI_BASE

    @property
    def page_layout(self) -> Path | None:
        layout = self.site.layout
        if layout is None:
            return None
        if isinstance(layout, Path):
            return layout
        return _parse_page_layout_path(layout, self.config_root.absolute())

    @property
    def context(self) -> Context:
        prefixes: dict[str, str | None] | None = None
        if self.graph.context:
            prefixes = {
                k: v for k, v in self.graph.context.items()
                if (not k.startswith("@") or k == "@vocab") and (v is None or isinstance(v, str))
            }
        return Context(prefixes, base_iri=self.base_iri)

    @property
    def namespaces(self) -> dict[str, Any]:
        return self.context.namespaces

    def bind_namespaces(self, graph: Any) -> None:
        self.context.bind_namespaces(graph)

    def relative_to_root(self, path: Path) -> str:
        try:
            rel = path.resolve().relative_to(self.config_root.resolve())
        except ValueError:
            rel = path
        return rel.as_posix().strip("/")

    def is_excluded(self, path: Path) -> bool:
        rel = self.relative_to_root(path)
        return any(fnmatch.fnmatchcase(rel, pattern) for pattern in self.wiki.exclude)

    @classmethod
    def for_root(cls, root: Path | str, **overrides: Any) -> Config:
        """Construct a resolved Config for tests and programmatic use."""
        data: dict[str, Any] = dict(overrides)
        data["config_root"] = Path(root)
        return cls.model_validate(data)

    @classmethod
    def load(cls, path: Path = Path("."), *, config_name: str = "") -> Config:
        """Load Config from an explicit file path or search standard names in a directory."""
        if path.is_file():
            potential_paths = [path]
        else:
            potential_paths = [path / name for name in CONFIG_FILENAMES]

        for config_path in potential_paths:
            if config_path.exists():
                try:
                    content = config_path.read_text(encoding="utf-8")
                    if config_path.suffix == ".json":
                        data = json.loads(content)
                    elif config_path.suffix == ".toml":
                        data = tomllib.loads(content)
                    else:
                        data = yaml.safe_load(content)

                    if not isinstance(data, dict):
                        raise ValueError(
                            f"Invalid config file {config_path.name}: top-level content must be a mapping"
                        )

                    name = config_name or config_path.name
                    base_dir = config_path.parent.absolute()
                    try:
                        return cls.model_validate(
                            {**data, "config_root": base_dir},
                            context={"config_name": name},
                        )
                    except ValidationError as exc:
                        raise format_config_validation_error(name, exc) from exc
                except ValueError:
                    raise
                except Exception as e:
                    raise ValueError(f"Failed to load config file {config_path.name}: {e}") from e

        return cls()
