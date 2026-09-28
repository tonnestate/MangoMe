from __future__ import annotations

import hashlib
import os
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
        self.last_scan_stats: dict[str, int | bool] = {"visited_files": 0, "limit_reached": False}

    def scan(
        self,
        roots: Iterable[str],
        extensions: set[str] | None = None,
        max_bytes: int = 2_000_000,
        max_files: int = 10_000,
        max_depth: int = 16,
    ) -> list[DiscoveryRecord]:
        """Bounded, non-destructive candidate discovery.

        Traversal is pruned before descent into private/cache/build trees and stops
        after ``max_files`` supported files. This keeps an explicit discovery request
        bounded even when the requested root contains very large subtrees.
        """
        extensions = extensions or {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv"}
        excluded_parts = {
            ".git", ".ssh", ".gnupg", ".cache", ".venv", "venv", "env", "node_modules",
            "__pycache__", "site-packages", "dist-packages", "vendor", "dist", "build",
            ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".idea", "coverage",
            ".claude", ".codex", ".aws", ".azure", ".kube", ".docker",
        }
        sensitive_names = {".npmrc", ".pypirc", ".netrc", "id_rsa", "id_dsa", "credentials", "secrets"}
        file_limit = max(0, int(max_files))
        depth_limit = max(0, int(max_depth))
        if file_limit == 0:
            return []
        results: list[DiscoveryRecord] = []
        visited_files = 0
        self.last_scan_stats = {"visited_files": 0, "limit_reached": False}

        def candidates(base: Path) -> Iterable[Path]:
            if base.is_file():
                yield base
                return
            base_depth = len(base.parts)
            for current, dirs, files in os.walk(base, followlinks=False):
                current_path = Path(current)
                depth = len(current_path.parts) - base_depth
                kept_dirs: list[str] = []
                for name in sorted(dirs):
                    child = current_path / name
                    if name.lower() in excluded_parts or child.is_symlink():
                        continue
                    kept_dirs.append(name)
                dirs[:] = kept_dirs if depth < depth_limit else []
                for name in sorted(files):
                    yield current_path / name

        for root in roots:
            requested = Path(root).expanduser()
            try:
                if requested.is_symlink():
                    continue
                base = requested.resolve()
            except OSError:
                continue
            if not base.exists():
                continue
            for path in candidates(base):
                if visited_files >= file_limit:
                    self.last_scan_stats = {"visited_files": visited_files, "limit_reached": True}
                    return results
                visited_files += 1
                try:
                    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in extensions:
                        continue
                except OSError:
                    continue
                lowered_parts = {part.lower() for part in path.parts}
                if lowered_parts & excluded_parts:
                    continue
                name_lower = path.name.lower()
                if name_lower == ".env" or name_lower.startswith(".env.") or name_lower in sensitive_names or name_lower.startswith("credentials.") or name_lower.startswith("secrets."):
                    continue
                try:
                    stat = path.stat()
                    digest = hashlib.sha256()
                    sample = bytearray()
                    with path.open("rb") as handle:
                        while True:
                            chunk = handle.read(1024 * 1024)
                            if not chunk:
                                break
                            digest.update(chunk)
                            if len(sample) < max_bytes:
                                sample.extend(chunk[: max_bytes - len(sample)])
                    sha = digest.hexdigest()
                except OSError:
                    continue
                text = bytes(sample).decode("utf-8", errors="replace")
                declared_ids = self._extract_ids(text, path.name)
                slices = self._extract_slices(text)
                artifact_type, classification, confidence, reason = self._classify(path, text, declared_ids, slices)
                record = DiscoveryRecord(
                    path=str(path),
                    logical_name=path.name,
                    sha256=sha,
                    size=int(stat.st_size),
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
        self.last_scan_stats = {"visited_files": visited_files, "limit_reached": False}
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

    def scan_git_locations(
        self, roots: Iterable[str], *, max_depth: int = 8, max_repositories: int = 200, recent_commit_limit: int = 20
    ) -> list[GitDiscoveryRecord]:
        """Discover nested Git checkouts/worktrees inside explicitly allowed search roots.

        This is physical-location discovery only. It does not create Project/Family truth.
        Secret/cache/virtualenv/system-like hidden trees are skipped.
        """
        candidates: list[Path] = []
        excluded = {".git", ".ssh", ".gnupg", ".cache", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
        for raw in roots:
            base = Path(raw).expanduser().resolve()
            if not base.exists() or not base.is_dir():
                continue
            base_depth = len(base.parts)
            for current, dirs, _files in os.walk(base):
                cur = Path(current)
                depth = len(cur.parts) - base_depth
                if (cur / ".git").exists():
                    candidates.append(cur)
                    # Do not descend into the Git metadata directory itself.
                    dirs[:] = [d for d in dirs if d != ".git"]
                dirs[:] = [
                    d for d in dirs
                    if d not in excluded
                    and not (d.startswith(".") and d not in {".github", ".gitlab", ".devcontainer"})
                ]
                if depth >= max_depth:
                    dirs[:] = []
                if len(candidates) >= max_repositories:
                    break
            if len(candidates) >= max_repositories:
                break
        unique: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate.resolve())
            if key not in seen:
                seen.add(key)
                unique.append(key)
        return self.scan_git(unique, recent_commit_limit=recent_commit_limit)

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
