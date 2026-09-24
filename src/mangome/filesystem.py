from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .enums import EvidenceClass, EvidenceTrust, EvidenceVerdict
from .service import MangoMeService

# Filesystem inventory is deliberately lexical and deterministic. It discovers facts;
# it never upgrades a contract, slice, evidence item, or audit claim by itself.
DEFAULT_DECLARED_ID_PATTERNS = [
    r"\b([A-Z][A-Z0-9]{1,20}(?:[-_/][A-Z0-9][A-Z0-9._]{0,30}){1,7})\b",
    r"\b(Contract[-_ ]?\d{2,})\b",
]

_TEXT_EXTENSIONS = {
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".csv",
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rs", ".php",
    ".rb", ".sh", ".bash", ".ps1", ".sql", ".xml", ".html", ".css", ".scss", ".vue",
}
_SOURCE_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rs", ".php",
    ".rb", ".sh", ".bash", ".ps1", ".sql", ".vue",
}
_CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml"}
_EXCLUDED_DIRS = {
    ".git", ".ssh", ".gnupg", ".cache", ".venv", "venv", "env", "__pycache__", "node_modules",
    "site-packages", "dist-packages", "vendor", "dist", "build", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".tox", ".idea", "coverage", ".coverage", "tmp", "temp",
}
# Hidden work/config directories that are useful evidence locations and are not skipped merely for being hidden.
_ALLOWED_HIDDEN_DIRS = {".github", ".gitlab", ".devcontainer"}
_SECRET_FILE_PATTERNS = (
    re.compile(r"^\.env(?:\..*)?$", re.IGNORECASE),
    re.compile(r"^(?:credentials?|secrets?)(?:\.[^.]+)?$", re.IGNORECASE),
    re.compile(r"^(?:id_rsa|id_ed25519|id_ecdsa|id_dsa)(?:\.pub)?$", re.IGNORECASE),
    re.compile(r"^(?:\.npmrc|\.pypirc|\.netrc)$", re.IGNORECASE),
)
_ADMISSIBLE_REUSE_CLASSES = {
    EvidenceClass.TEST_RESULT.value,
    EvidenceClass.RUNTIME_OBSERVATION.value,
    EvidenceClass.STATIC_ANALYSIS.value,
    EvidenceClass.ARTIFACT_CHECK.value,
    EvidenceClass.HUMAN_ATTESTATION.value,
    EvidenceClass.EXTERNAL_REVIEW.value,
}
_ADMISSIBLE_REUSE_TRUST = {
    EvidenceTrust.VERIFIER_ATTESTED.value,
    EvidenceTrust.OWNER_ATTESTED.value,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class FileInventoryRecord:
    path: str
    root_path: str
    relative_path: str
    role: str
    sha256: str | None
    hash_status: str
    size: int
    mtime_ns: int
    declared_ids: list[str]
    git_root: str | None = None
    git_head: str | None = None


class FilesystemScanner:
    """Bounded deterministic filesystem inventory for evidence lookup and freshness checks."""

    def __init__(self, service: MangoMeService, id_patterns: list[str] | None = None) -> None:
        self.service = service
        patterns = id_patterns or DEFAULT_DECLARED_ID_PATTERNS
        self.declared_id_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def scan(
        self,
        roots: Iterable[str],
        *,
        max_files: int = 50_000,
        max_depth: int = 16,
        max_hash_bytes: int = 64 * 1024 * 1024,
        max_text_bytes: int = 256_000,
        result_limit: int = 200,
    ) -> dict[str, Any]:
        normalized_roots = self._normalize_roots(roots)
        scan_id = _stable_id("FSSCAN", f"{utcnow().isoformat()}:{'|'.join(normalized_roots)}")
        all_changed: list[str] = []
        all_removed: list[str] = []
        root_summaries: list[dict[str, Any]] = []
        total_files = 0
        total_unchanged = 0
        coverage_complete = True

        remaining = max_files
        for root in normalized_roots:
            if remaining <= 0:
                coverage_complete = False
                break
            summary = self._scan_root(
                root,
                scan_id=scan_id,
                max_files=remaining,
                max_depth=max_depth,
                max_hash_bytes=max_hash_bytes,
                max_text_bytes=max_text_bytes,
            )
            remaining -= summary["file_count"]
            total_files += summary["file_count"]
            total_unchanged += summary["unchanged_count"]
            all_changed.extend(summary["changed_paths"])
            all_removed.extend(summary["removed_paths"])
            coverage_complete = coverage_complete and summary["coverage_complete"]
            root_summaries.append(summary)

        return {
            "scan_id": scan_id,
            "roots": normalized_roots,
            "file_count": total_files,
            "changed_count": len(all_changed),
            "unchanged_count": total_unchanged,
            "removed_count": len(all_removed),
            "coverage_complete": coverage_complete,
            "changed_paths": all_changed[:result_limit],
            "removed_paths": all_removed[:result_limit],
            "results_truncated": len(all_changed) > result_limit or len(all_removed) > result_limit,
            "root_summaries": root_summaries,
            "note": "Filesystem inventory records observable facts only; it does not verify implementation or trust audit prose.",
        }

    def references(self, declared_id: str, *, present_only: bool = True, limit: int = 200) -> dict[str, Any]:
        normalized = declared_id.strip().upper().replace(" ", "-")
        rows = self.service.store.find("filesystem_entries", {"declared_ids__contains": normalized})
        if present_only:
            rows = [row for row in rows if row.get("present", True)]
        rows.sort(key=lambda row: (row.get("role", ""), row.get("path", "")))
        return {
            "declared_id": normalized,
            "count": len(rows),
            "entries": [self._public_entry(row) for row in rows[:limit]],
            "truncated": len(rows) > limit,
        }

    def paths(self, paths: Iterable[str]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for raw in paths:
            resolved = str(Path(raw).expanduser().resolve())
            matches = self.service.store.find("filesystem_entries", {"path": resolved})
            if matches:
                results.append(self._public_entry(matches[0]))
        return results

    def evidence_freshness(self, evidence_id: str, *, live_check: bool = True) -> dict[str, Any]:
        evidence = self.service.store.get("evidence", evidence_id)
        if evidence is None:
            raise KeyError(f"unknown evidence:{evidence_id}")
        if evidence.get("evidence_class") not in _ADMISSIBLE_REUSE_CLASSES:
            return self._freshness_result(evidence, "INADMISSIBLE", "evidence class is not reusable proof")
        if evidence.get("trust") not in _ADMISSIBLE_REUSE_TRUST:
            return self._freshness_result(evidence, "INADMISSIBLE", "evidence is not verifier/owner attested")
        if evidence.get("verdict") != EvidenceVerdict.PASS.value:
            return self._freshness_result(evidence, "INADMISSIBLE", "only PASS evidence can be reused")

        bindings = self._evidence_bindings(evidence)
        if not bindings:
            return self._freshness_result(evidence, "UNBOUND", "no filesystem hash binding is attached")

        checks: list[dict[str, Any]] = []
        stale = False
        unknown = False
        for binding in bindings:
            path_text = str(binding.get("path") or "")
            expected = str(binding.get("sha256") or "")
            if not path_text or not expected:
                checks.append({"path": path_text or None, "status": "INVALID_BINDING"})
                unknown = True
                continue
            path = Path(path_text).expanduser()
            indexed = self.service.store.find("filesystem_entries", {"path": str(path.resolve())})
            indexed_row = indexed[0] if indexed else None
            current_hash: str | None = None
            status = "MATCH"
            if live_check:
                try:
                    if not path.is_file() or path.is_symlink() or self._is_secret_file(path):
                        status = "MISSING_OR_EXCLUDED"
                        stale = True
                    else:
                        current_hash = _sha256_file(path)
                        if current_hash != expected:
                            status = "HASH_MISMATCH"
                            stale = True
                except OSError:
                    status = "UNREADABLE"
                    unknown = True
            else:
                if not indexed_row:
                    status = "NOT_INDEXED"
                    unknown = True
                elif not indexed_row.get("present", True):
                    status = "MISSING"
                    stale = True
                else:
                    current_hash = indexed_row.get("sha256")
                    if not current_hash:
                        status = "UNHASHED"
                        unknown = True
                    elif current_hash != expected:
                        status = "HASH_MISMATCH"
                        stale = True
            checks.append({
                "path": str(path),
                "expected_sha256": expected,
                "current_sha256": current_hash,
                "status": status,
                "indexed": indexed_row is not None,
            })

        state = "STALE" if stale else ("UNKNOWN" if unknown else "REUSABLE")
        reason = {
            "REUSABLE": "all bound filesystem hashes still match",
            "STALE": "one or more bound filesystem facts changed or disappeared",
            "UNKNOWN": "one or more bound filesystem facts could not be checked",
        }[state]
        return {
            "evidence_id": evidence_id,
            "subject_id": evidence.get("subject_id"),
            "state": state,
            "reason": reason,
            "live_check": live_check,
            "checks": checks,
            "rule": "Freshness never creates verification or acceptance; it only determines whether an existing attested PASS proof remains reusable.",
        }

    def _scan_root(
        self,
        root: str,
        *,
        scan_id: str,
        max_files: int,
        max_depth: int,
        max_hash_bytes: int,
        max_text_bytes: int,
    ) -> dict[str, Any]:
        base = Path(root)
        previous = {row["path"]: row for row in self.service.store.find("filesystem_entries", {"root_path": root})}
        seen: set[str] = set()
        records: list[FileInventoryRecord] = []
        changed_paths: list[str] = []
        unchanged = 0
        coverage_complete = True
        repo_heads: dict[str, str | None] = {}

        if base.is_file():
            candidate_paths = [base]
        else:
            candidate_paths = []
            for current, dirs, files in os.walk(base, followlinks=False):
                current_path = Path(current)
                depth = len(current_path.relative_to(base).parts)
                if depth > max_depth:
                    dirs[:] = []
                    coverage_complete = False
                    continue
                if ".git" in dirs:
                    repo_heads[str(current_path.resolve())] = self._git_head(current_path)
                dirs[:] = [d for d in dirs if self._include_dir(d) and not (current_path / d).is_symlink()]
                for name in files:
                    candidate_paths.append(current_path / name)
                    if len(candidate_paths) >= max_files:
                        coverage_complete = False
                        break
                if len(candidate_paths) >= max_files:
                    break

        for path in candidate_paths[:max_files]:
            try:
                if not path.is_file() or path.is_symlink() or self._is_secret_file(path):
                    continue
                stat = path.stat()
                resolved = str(path.resolve())
                seen.add(resolved)
                sha = _sha256_file(path) if stat.st_size <= max_hash_bytes else None
                text = self._text_sample(path, max_text_bytes) if path.suffix.lower() in _TEXT_EXTENSIONS else ""
                declared_ids = self._extract_ids(text, path.name) if text or path.suffix.lower() in _TEXT_EXTENSIONS else self._extract_ids("", path.name)
                role = self._classify_role(path, base, text)
                git_root, git_head = self._nearest_git(resolved, repo_heads)
                record = FileInventoryRecord(
                    path=resolved,
                    root_path=root,
                    relative_path=str(path.resolve().relative_to(base.resolve())) if base.is_dir() else path.name,
                    role=role,
                    sha256=sha,
                    hash_status="SHA256" if sha else "SKIPPED_OVERSIZE",
                    size=int(stat.st_size),
                    mtime_ns=int(stat.st_mtime_ns),
                    declared_ids=declared_ids,
                    git_root=git_root,
                    git_head=git_head,
                )
                records.append(record)
                old = previous.get(resolved)
                if old and self._same_entry(old, record):
                    unchanged += 1
                else:
                    self._persist_entry(record, scan_id=scan_id, existing=old)
                    changed_paths.append(resolved)
            except (OSError, ValueError):
                continue

        removed_paths: list[str] = []
        if coverage_complete:
            for path_text, row in previous.items():
                if path_text in seen or not row.get("present", True):
                    continue
                self.service.store.update(
                    "filesystem_entries",
                    row["entity_id"],
                    {"present": False, "missing_since_scan_id": scan_id, "updated_at": utcnow()},
                    expected_revision=int(row.get("revision", 0)),
                )
                removed_paths.append(path_text)

        tree_payload = "\n".join(
            f"{r.relative_path}\t{r.sha256 or '-'}\t{r.size}\t{r.role}" for r in sorted(records, key=lambda item: item.relative_path)
        )
        tree_hash = hashlib.sha256(tree_payload.encode("utf-8")).hexdigest()
        root_id = _stable_id("FSROOT", root)
        root_doc = {
            "entity_id": root_id,
            "root_path": root,
            "tree_hash": tree_hash,
            "file_count": len(records),
            "changed_count": len(changed_paths),
            "unchanged_count": unchanged,
            "removed_count": len(removed_paths),
            "coverage_complete": coverage_complete,
            "scan_id": scan_id,
            "git_heads": repo_heads,
            "scanned_at": utcnow(),
            "updated_at": utcnow(),
        }
        existing_root = self.service.store.get("filesystem_roots", root_id)
        if existing_root is None:
            root_doc.update({"created_at": utcnow(), "revision": 0})
            self.service.store.insert("filesystem_roots", root_doc)
        else:
            root_doc.pop("entity_id")
            self.service.store.update(
                "filesystem_roots", root_id, root_doc, expected_revision=int(existing_root.get("revision", 0))
            )

        return {
            "root_path": root,
            "tree_hash": tree_hash,
            "file_count": len(records),
            "changed_count": len(changed_paths),
            "unchanged_count": unchanged,
            "removed_count": len(removed_paths),
            "coverage_complete": coverage_complete,
            "changed_paths": changed_paths,
            "removed_paths": removed_paths,
        }

    def _persist_entry(self, record: FileInventoryRecord, *, scan_id: str, existing: dict[str, Any] | None) -> None:
        now = utcnow()
        payload = {
            **asdict(record),
            "present": True,
            "last_changed_scan_id": scan_id,
            "missing_since_scan_id": None,
            "updated_at": now,
        }
        entity_id = _stable_id("FS", record.path)
        if existing is None:
            self.service.store.insert("filesystem_entries", {
                "entity_id": entity_id,
                **payload,
                "created_at": now,
                "revision": 0,
            })
        else:
            self.service.store.update(
                "filesystem_entries", entity_id, payload, expected_revision=int(existing.get("revision", 0))
            )

    @staticmethod
    def _same_entry(existing: dict[str, Any], record: FileInventoryRecord) -> bool:
        current = asdict(record)
        return existing.get("present", True) and all(existing.get(key) == value for key, value in current.items())

    @staticmethod
    def _normalize_roots(roots: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for raw in roots:
            path = Path(raw).expanduser()
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if not resolved.exists() or resolved.is_symlink():
                continue
            text = str(resolved)
            if text not in normalized:
                normalized.append(text)
        return normalized

    @staticmethod
    def _include_dir(name: str) -> bool:
        lowered = name.lower()
        if lowered in _EXCLUDED_DIRS or "secret" in lowered or "credential" in lowered:
            return False
        if name.startswith(".") and name not in _ALLOWED_HIDDEN_DIRS:
            return False
        return True

    @staticmethod
    def _is_secret_file(path: Path) -> bool:
        lowered_suffix = path.suffix.lower()
        if lowered_suffix in {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}:
            return True
        return any(pattern.search(path.name) for pattern in _SECRET_FILE_PATTERNS)

    @staticmethod
    def _text_sample(path: Path, max_bytes: int) -> str:
        try:
            with path.open("rb") as handle:
                raw = handle.read(max_bytes)
        except OSError:
            return ""
        if b"\x00" in raw[:4096]:
            return ""
        return raw.decode("utf-8", errors="replace")

    def _extract_ids(self, text: str, filename: str) -> list[str]:
        found: list[str] = []
        sample = filename + "\n" + text
        for pattern in self.declared_id_patterns:
            for match in pattern.finditer(sample):
                value = match.group(1).strip().upper().replace(" ", "-")
                if value not in found:
                    found.append(value)
        return found

    @staticmethod
    def _classify_role(path: Path, base: Path, text: str) -> str:
        rel_parts = [part.lower() for part in (path.resolve().relative_to(base.resolve()).parts if base.is_dir() else (path.name,))]
        name = path.name.lower()
        suffix = path.suffix.lower()
        joined = "/".join(rel_parts)
        if "test" in rel_parts or "tests" in rel_parts or name.startswith(("test_", "spec_")) or name.endswith(("_test.py", ".spec.ts", ".test.ts", ".spec.js", ".test.js")):
            return "TEST"
        if ".github/workflows" in joined or ".gitlab-ci" in name or "workflow" in name:
            return "WORKFLOW"
        if any(token in name for token in ("contract", "vertrag")) or (suffix in {".md", ".txt"} and any(token in text[:12000].lower() for token in ("contract", "vertrag", "acceptance criteria", "akzeptanzkriterien"))):
            return "CONTRACT"
        if any(token in name for token in ("audit", "report", "eval", "handoff", "evidence")):
            return "AUDIT_OR_REPORT"
        if suffix in _SOURCE_EXTENSIONS:
            return "SOURCE"
        if suffix in _CONFIG_EXTENSIONS:
            return "CONFIG"
        if suffix in {".md", ".txt", ".rst"}:
            return "DOCUMENTATION"
        return "OTHER"

    @staticmethod
    def _git_head(root: Path) -> str | None:
        try:
            return subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=3,
            ).strip() or None
        except (OSError, subprocess.SubprocessError):
            return None

    @staticmethod
    def _nearest_git(path: str, repo_heads: dict[str, str | None]) -> tuple[str | None, str | None]:
        matches = [root for root in repo_heads if path == root or path.startswith(root.rstrip(os.sep) + os.sep)]
        if not matches:
            return None, None
        root = max(matches, key=len)
        return root, repo_heads[root]

    def _evidence_bindings(self, evidence: dict[str, Any]) -> list[dict[str, str]]:
        raw = evidence.get("payload", {}).get("filesystem_bindings") or []
        bindings: list[dict[str, str]] = []
        for item in raw:
            if isinstance(item, dict):
                bindings.append({"path": str(item.get("path") or ""), "sha256": str(item.get("sha256") or "")})
        artifact_id = evidence.get("artifact_id")
        if artifact_id:
            artifact = self.service.store.get("artifacts", artifact_id)
            if artifact and artifact.get("physical_location") and artifact.get("checksum"):
                candidate = {"path": str(artifact["physical_location"]), "sha256": str(artifact["checksum"])}
                if candidate not in bindings:
                    bindings.append(candidate)
        return bindings

    @staticmethod
    def _freshness_result(evidence: dict[str, Any], state: str, reason: str) -> dict[str, Any]:
        return {
            "evidence_id": evidence["entity_id"],
            "subject_id": evidence.get("subject_id"),
            "state": state,
            "reason": reason,
            "checks": [],
            "rule": "Freshness never creates verification or acceptance; it only determines whether an existing attested PASS proof remains reusable.",
        }

    @staticmethod
    def _public_entry(row: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "entity_id", "path", "root_path", "relative_path", "role", "sha256", "hash_status", "size",
            "mtime_ns", "declared_ids", "git_root", "git_head", "present", "last_changed_scan_id",
        )
        return {key: row.get(key) for key in keys}
