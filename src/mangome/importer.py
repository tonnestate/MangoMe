from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .service import MangoMeService

# Generic lexical extraction only. These expressions do not decide semantic truth.
DEFAULT_DECLARED_ID_PATTERNS = [
    r"\b([A-Z][A-Z0-9]{1,20}(?:[-_/][A-Z0-9][A-Z0-9._]{0,30}){1,7})\b",
    r"\b(Contract[-_ ]?\d{2,})\b",
]
SLICE_PATTERN = re.compile(
    r"^\s{0,6}(?:#{1,6}\s*)?(?:slice|phase|workstream)\s+([A-Za-z0-9._-]+)\s*[:\-–]?\s*(.*)$",
    re.IGNORECASE,
)


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


@dataclass
class GitDiscoveryRecord:
    root: str
    repository: str | None
    head: str | None
    branches: list[str]
    worktrees: list[str]
    recent_commits: list[dict[str, str]]
    error: str | None = None


class BigBangScanner:
    """Non-destructive filesystem and optional Git discovery."""

    def __init__(self, service: MangoMeService | None = None, id_patterns: list[str] | None = None) -> None:
        self.service = service
        patterns = id_patterns or DEFAULT_DECLARED_ID_PATTERNS
        self.declared_id_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def scan(
        self,
        roots: Iterable[str],
        extensions: set[str] | None = None,
        max_bytes: int = 2_000_000,
    ) -> list[DiscoveryRecord]:
        extensions = extensions or {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv"}
        results: list[DiscoveryRecord] = []
        for root in roots:
            base = Path(root).expanduser().resolve()
            if not base.exists():
                continue
            iterator = [base] if base.is_file() else base.rglob("*")
            for path in iterator:
                if not path.is_file() or path.suffix.lower() not in extensions:
                    continue
                if ".git" in path.parts:
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

    def scan_git(self, roots: Iterable[str], recent_commit_limit: int = 20) -> list[GitDiscoveryRecord]:
        results: list[GitDiscoveryRecord] = []
        for root in roots:
            base = Path(root).expanduser().resolve()
            if not base.exists() or not base.is_dir():
                continue
            try:
                top = self._git(base, ["rev-parse", "--show-toplevel"]).strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
            repo_root = Path(top)
            try:
                remote = self._git(repo_root, ["config", "--get", "remote.origin.url"]).strip() or None
                head = self._git(repo_root, ["rev-parse", "HEAD"]).strip() or None
                branches = [x.strip() for x in self._git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads/"]).splitlines() if x.strip()]
                worktrees = []
                raw_worktrees = self._git(repo_root, ["worktree", "list", "--porcelain"])
                for line in raw_worktrees.splitlines():
                    if line.startswith("worktree "):
                        worktrees.append(line[len("worktree "):].strip())
                log = self._git(
                    repo_root,
                    ["log", f"-{recent_commit_limit}", "--pretty=format:%H%x09%aI%x09%s"],
                )
                commits = []
                for line in log.splitlines():
                    parts = line.split("\t", 2)
                    if len(parts) == 3:
                        commits.append({"sha": parts[0], "authored_at": parts[1], "subject": parts[2]})
                results.append(
                    GitDiscoveryRecord(
                        root=str(repo_root), repository=remote, head=head, branches=branches,
                        worktrees=worktrees, recent_commits=commits,
                    )
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                results.append(
                    GitDiscoveryRecord(
                        root=str(repo_root), repository=None, head=None, branches=[], worktrees=[], recent_commits=[], error=str(exc)
                    )
                )
        # de-duplicate roots reached from nested scan roots
        unique: dict[str, GitDiscoveryRecord] = {r.root: r for r in results}
        return list(unique.values())

    @staticmethod
    def _git(root: Path, args: list[str]) -> str:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=10,
        )

    def _extract_ids(self, text: str, filename: str) -> list[str]:
        found: list[str] = []
        sample = filename + "\n" + text[:200_000]
        for pattern in self.declared_id_patterns:
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
        contract_signal = any(token in lower_name or token in head for token in ("contract", "vertrag", "acceptance", "akzeptanz", "specification"))
        report_signal = any(token in lower_name for token in ("report", "audit", "status", "handoff", "eval", "evidence"))
        if ids and contract_signal:
            return "CONTRACT_DOCUMENT", "CONTRACT_CANDIDATE", 0.90, "declared id plus contract/specification signal"
        if report_signal:
            return "REPORT", "SUPPORTING_ARTIFACT", 0.85, "report/audit/status filename signal"
        if slices:
            return "PLAN_OR_STATUS", "WORK_STRUCTURE_CANDIDATE", 0.75, "explicit slice/phase markers found"
        if ids:
            return "REFERENCE", "REFERENCE_ONLY", 0.65, "declared id found without contract admission evidence"
        return "OTHER", "UNRESOLVED", 0.25, "no deterministic contract/work marker"


class BigBangReconciler:
    """Compare discovery records with canonical state without mutating semantic truth."""

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    def reconcile(self, records: list[DiscoveryRecord | dict[str, object]]) -> dict[str, object]:
        matched: list[dict[str, object]] = []
        collisions: list[dict[str, object]] = []
        unresolved: list[dict[str, object]] = []
        for item in records:
            record = item if isinstance(item, DiscoveryRecord) else DiscoveryRecord(**item)  # type: ignore[arg-type]
            candidates: list[dict[str, object]] = []
            for declared_id in record.declared_ids:
                contracts = self.service.store.find("contracts", {"declared_id": declared_id})
                if len(contracts) == 1:
                    contract = contracts[0]
                    candidates.append({
                        "declared_id": declared_id,
                        "contract_id": contract["entity_id"],
                        "family_id": contract["family_id"],
                        "confidence": 1.0,
                        "basis": "exact declared_id",
                    })
                elif len(contracts) > 1:
                    collisions.append({
                        "path": record.path,
                        "declared_id": declared_id,
                        "contract_ids": [c["entity_id"] for c in contracts],
                    })
            if len(candidates) == 1:
                matched.append({"path": record.path, "match": candidates[0], "slice_markers": record.slice_markers})
            elif not candidates:
                unresolved.append({
                    "path": record.path,
                    "classification": record.classification,
                    "declared_ids": record.declared_ids,
                    "slice_markers": record.slice_markers,
                })
            else:
                collisions.append({"path": record.path, "matches": candidates, "reason": "multiple exact contract matches"})
        return {
            "matched": matched,
            "collisions": collisions,
            "unresolved": unresolved,
            "canonical_mutations": 0,
            "note": "Reconciliation is advisory; semantic admission remains explicit.",
        }


def serialize_discovery(records: list[DiscoveryRecord]) -> list[dict[str, object]]:
    return [asdict(r) for r in records]


def serialize_git_discovery(records: list[GitDiscoveryRecord]) -> list[dict[str, object]]:
    return [asdict(r) for r in records]


def load_id_patterns_json(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    value = json.loads(raw)
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError("id pattern JSON must be a list of regex strings")
    return value
