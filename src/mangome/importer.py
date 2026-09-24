from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

from .service import MangoMeService

# Extraction only. These expressions do not decide semantic truth.
DECLARED_ID_PATTERNS = [
    re.compile(r"\b((?:AVCOS|TE|SPARI|COGC|CHOMVIEW)[A-Z0-9/_-]{2,})\b", re.IGNORECASE),
    re.compile(r"\b(Contract[-_ ]?\d{2,})\b", re.IGNORECASE),
]
SLICE_PATTERN = re.compile(r"^\s{0,6}(?:#{1,6}\s*)?(?:slice|phase|workstream)\s+([A-Za-z0-9._-]+)\s*[:\-–]?\s*(.*)$", re.IGNORECASE)


@dataclass
class DiscoveryRecord:
    path: str
    logical_name: str
    sha256: str
    size: int
    artifact_type: str
    declared_ids: list[str]
    slice_markers: list[dict[str, str]]
    classification: str
    confidence: float
    reason: str


class BigBangScanner:
    """Non-destructive filesystem discovery.

    The scanner extracts cheap structural signals. It does not create canonical
    contracts or family relations. Canonicalization is a separate explicit step.
    """

    def __init__(self, service: MangoMeService | None = None) -> None:
        self.service = service

    def scan(self, roots: Iterable[str], extensions: set[str] | None = None, max_bytes: int = 2_000_000) -> list[DiscoveryRecord]:
        extensions = extensions or {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}
        results: list[DiscoveryRecord] = []
        for root in roots:
            base = Path(root).expanduser().resolve()
            if not base.exists():
                continue
            iterator = [base] if base.is_file() else base.rglob("*")
            for path in iterator:
                if not path.is_file() or path.suffix.lower() not in extensions:
                    continue
                try:
                    raw = path.read_bytes()
                except OSError:
                    continue
                sha = hashlib.sha256(raw).hexdigest()
                text = raw[:max_bytes].decode("utf-8", errors="replace")
                declared_ids = self._extract_ids(text, path.name)
                slices = self._extract_slices(text)
                artifact_type, classification, confidence, reason = self._classify(path, text, declared_ids, slices)
                record = DiscoveryRecord(
                    path=str(path),
                    logical_name=path.name,
                    sha256=sha,
                    size=len(raw),
                    artifact_type=artifact_type,
                    declared_ids=declared_ids,
                    slice_markers=slices,
                    classification=classification,
                    confidence=confidence,
                    reason=reason,
                )
                results.append(record)
                if self.service:
                    self.service.attach_artifact(
                        logical_name=path.name,
                        artifact_type=artifact_type,
                        storage_system="filesystem",
                        physical_location=str(path),
                        checksum=sha,
                        metadata={
                            "bigbang_classification": classification,
                            "bigbang_confidence": confidence,
                            "declared_ids": declared_ids,
                            "slice_markers": slices,
                        },
                    )
        return results

    @staticmethod
    def _extract_ids(text: str, filename: str) -> list[str]:
        found: list[str] = []
        sample = filename + "\n" + text[:200_000]
        for pattern in DECLARED_ID_PATTERNS:
            for match in pattern.finditer(sample):
                value = match.group(1).strip().upper().replace(" ", "-")
                if value not in found:
                    found.append(value)
        return found

    @staticmethod
    def _extract_slices(text: str) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        for line in text.splitlines()[:10000]:
            match = SLICE_PATTERN.match(line)
            if match:
                found.append({"marker": match.group(1), "title": match.group(2).strip()})
        return found

    @staticmethod
    def _classify(path: Path, text: str, ids: list[str], slices: list[dict[str, str]]) -> tuple[str, str, float, str]:
        lower_name = path.name.lower()
        head = text[:12000].lower()
        contract_signal = any(token in lower_name or token in head for token in ("contract", "vertrag", "acceptance", "akzeptanz"))
        report_signal = any(token in lower_name for token in ("report", "audit", "status", "handoff", "eval"))
        if ids and contract_signal:
            return "CONTRACT_DOCUMENT", "CONTRACT_CANDIDATE", 0.90, "explicit id plus contract/specification signal"
        if report_signal:
            return "REPORT", "SUPPORTING_ARTIFACT", 0.85, "report/audit/status filename signal"
        if slices:
            return "PLAN_OR_STATUS", "WORK_STRUCTURE_CANDIDATE", 0.75, "explicit slice/phase markers found"
        if ids:
            return "REFERENCE", "REFERENCE_ONLY", 0.65, "declared id found without contract admission evidence"
        return "OTHER", "UNRESOLVED", 0.25, "no deterministic contract/work marker"


def serialize_discovery(records: list[DiscoveryRecord]) -> list[dict[str, object]]:
    return [asdict(r) for r in records]
