"""Init scaffold option models."""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, field_validator

from .wiki_config import (
    _LEGACY_LINK_STYLE_MAP,
    _LINK_STYLES,
    IMPLICIT_TYPES_POLICIES,
)
from .wiki_config import (
    VALID_URL_STYLES as _VALID_URL_STYLES,
)

logger = logging.getLogger(__name__)


class InitOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    graph_context_wiki: str
    site_base_url: str = "/wiki"
    site_url_style: str = "dir"
    graph_content_predicate: str | None = None
    link_style: str | None = None
    site_layout: str | None = None
    wiki_inputs: list[str] | None = None
    graph_base_iri: str | None = None
    graph_implicit_types: list[str] | None = None
    graph_implicit_types_policy: str | None = None
    graph_include_file_extension: bool | None = None
    template: str | None = None


    @field_validator("site_url_style", mode="before")
    @classmethod
    def _validate_url_style(cls, value: object) -> str:
        normalized = str(value or "dir").strip().lower()
        if normalized not in _VALID_URL_STYLES:
            raise ValueError(f"Invalid site_url_style: {value}")
        return normalized

    @field_validator("link_style", mode="before")
    @classmethod
    def _validate_link_style(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"expected standard or wikilink, got {value!r}")
        normalized = value.strip().lower()
        if normalized in _LEGACY_LINK_STYLE_MAP:
            new_style = _LEGACY_LINK_STYLE_MAP[normalized]
            logger.warning(
                "link_style: '%s' is deprecated, use '%s' instead "
                "(edit config file link.style and re-run)",
                normalized,
                new_style,
            )
            return new_style
        if normalized not in _LINK_STYLES:
            raise ValueError(f"expected standard or wikilink, got {value!r}")
        return normalized

    @field_validator("graph_implicit_types_policy", mode="before")
    @classmethod
    def _validate_implicit_types_policy(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized not in IMPLICIT_TYPES_POLICIES:
            raise ValueError(f"expected fallback or append, got {value!r}")
        return normalized
