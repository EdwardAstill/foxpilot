"""Durable selector memory for self-healing browser actions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from foxpilot.evidence import redact_text


@dataclass
class SelectorRecord:
    url: str
    domain: str
    action: str
    description: str
    tag: str = ""
    role: str = ""
    text: str = ""
    aria_label: str = ""
    placeholder: str = ""
    name: str = ""
    element_id: str = ""
    css_path: str = ""
    xpath: str = ""
    nearby_label_text: str = ""
    screenshot_crop_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": redact_url(self.url),
            "domain": normalize_domain(self.domain),
            "action": self.action,
            "description": redact_text(self.description),
            "tag": self.tag,
            "role": self.role,
            "text": self.text,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "name": self.name,
            "element_id": self.element_id,
            "css_path": self.css_path,
            "xpath": self.xpath,
            "nearby_label_text": self.nearby_label_text,
            "screenshot_crop_path": self.screenshot_crop_path,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SelectorRecord":
        values = {field_name: str(data.get(field_name, "")) for field_name in _STRING_FIELDS}
        created_at = str(data.get("created_at") or datetime.now(timezone.utc).isoformat())
        return cls(created_at=created_at, **values)


_STRING_FIELDS = (
    "url",
    "domain",
    "action",
    "description",
    "tag",
    "role",
    "text",
    "aria_label",
    "placeholder",
    "name",
    "element_id",
    "css_path",
    "xpath",
    "nearby_label_text",
    "screenshot_crop_path",
)


class SelectorMemory:
    """Append-only JSONL selector memory store."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def record_success(self, *, url: str, action: str, description: str, **clues: Any) -> SelectorRecord:
        record = SelectorRecord(
            url=redact_url(url),
            domain=normalize_domain(url),
            action=action,
            description=redact_text(description),
            tag=str(clues.get("tag", "")),
            role=str(clues.get("role", "")),
            text=str(clues.get("text", "")),
            aria_label=str(clues.get("aria_label", "")),
            placeholder=str(clues.get("placeholder", "")),
            name=str(clues.get("name", "")),
            element_id=str(clues.get("element_id") or clues.get("id") or ""),
            css_path=str(clues.get("css_path", "")),
            xpath=str(clues.get("xpath", "")),
            nearby_label_text=str(clues.get("nearby_label_text", "")),
            screenshot_crop_path=str(clues.get("screenshot_crop_path", "")),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def find_candidates(
        self,
        *,
        domain: str = "",
        url: str = "",
        action: str = "",
        description: str = "",
        limit: int = 5,
    ) -> list[SelectorRecord]:
        records = self._read_records()
        target_domain = normalize_domain(domain or url)
        scored: list[tuple[int, int, SelectorRecord]] = []
        for index, record in enumerate(records):
            if action and record.action != action:
                continue
            if target_domain and not domain_matches(record.domain, target_domain):
                continue
            score = _semantic_score(record, description)
            if url and _same_path_prefix(record.url, url):
                score += 2
            if score <= 0:
                continue
            scored.append((score, index, record))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [record for _, _, record in scored[:limit]]

    def _read_records(self) -> list[SelectorRecord]:
        if not self.path.exists():
            return []
        records: list[SelectorRecord] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                records.append(SelectorRecord.from_dict(data))
        return records


def normalize_domain(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = (parsed.hostname or value).lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def domain_matches(candidate: str, target: str) -> bool:
    candidate_domain = normalize_domain(candidate)
    target_domain = normalize_domain(target)
    return candidate_domain == target_domain or candidate_domain.endswith(f".{target_domain}")


def redact_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.query:
        return redact_text(value)
    return urlunparse(parsed._replace(query=redact_text(parsed.query)))


def _semantic_score(record: SelectorRecord, description: str) -> int:
    needle = _normalize_words(description)
    haystacks = [
        record.description,
        record.text,
        record.aria_label,
        record.placeholder,
        record.name,
        record.element_id,
        record.nearby_label_text,
    ]
    score = 0
    for haystack in haystacks:
        words = _normalize_words(haystack)
        if not words or not needle:
            continue
        if needle == words:
            score += 6
        elif needle in words or words in needle:
            score += 4
        elif set(needle.split()) & set(words.split()):
            score += 1
    if record.css_path:
        score += 1
    if record.xpath:
        score += 1
    return score


def _same_path_prefix(left: str, right: str) -> bool:
    left_path = urlparse(left).path.strip("/").split("/")
    right_path = urlparse(right).path.strip("/").split("/")
    return bool(left_path and right_path and left_path[0] == right_path[0])


def _normalize_words(value: str) -> str:
    return " ".join(str(value).lower().replace("_", " ").replace("-", " ").split())
