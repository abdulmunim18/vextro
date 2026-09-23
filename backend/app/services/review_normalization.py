"""Canonical normalization and identity rules for marketplace reviews."""

from datetime import UTC, date, datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Any


HTML_FRAGMENT_PATTERN = re.compile(r"<[A-Za-z][^>]*>")
WHITESPACE_PATTERN = re.compile(r"\s+", re.UNICODE)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def normalize_review_text(value: str | None) -> str | None:
    """Normalize layout whitespace while retaining case and punctuation."""

    if value is None:
        return None

    candidate = unescape(str(value))
    if HTML_FRAGMENT_PATTERN.search(candidate):
        parser = _TextExtractor()
        parser.feed(candidate)
        candidate = " ".join(parser.parts)

    normalized = WHITESPACE_PATTERN.sub(" ", candidate).strip()
    return normalized or None


def normalize_optional_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = WHITESPACE_PATTERN.sub(" ", str(value)).strip()
    return normalized or None


def normalize_reviewed_at(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("reviewed_at must include timezone information")
        return value.astimezone(UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def build_review_fingerprint(
    *,
    platform_code: str,
    listing_external_id: str,
    external_review_id: str | None,
    reviewer_external_id: str | None,
    reviewer_display_name: str | None,
    rating: int,
    review_text: str | None,
    reviewed_at: datetime | None,
) -> str:
    """Return a deterministic SHA-256 review identity."""

    if external_review_id:
        identity: dict[str, Any] = {
            "external_review_id": external_review_id,
        }
    else:
        identity = {
            "listing_external_id": listing_external_id,
            "reviewer_external_id": (
                reviewer_external_id.lower()
                if reviewer_external_id
                else None
            ),
            "reviewer_display_name": (
                reviewer_display_name.casefold()
                if reviewer_display_name
                else None
            ),
            "rating": rating,
            "review_text": review_text,
            "reviewed_at": (
                reviewed_at.isoformat()
                if reviewed_at is not None
                else None
            ),
        }

    encoded = json.dumps(
        {
            "platform": platform_code,
            **identity,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
