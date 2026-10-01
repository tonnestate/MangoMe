from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .runtime import ensure_workspace_binding, get_service, health_snapshot, workspace_attachment_snapshot
from .service import workspace_project_key
from .structural import StructuralIntelligence

HUMAN_STATUS_PROTOCOL = "HUMAN_STATUS/1"


def _folder_name(path: Path, root: Path) -> str | None:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return None
    if not rel.parts or len(rel.parts) == 1:
        return "."
    return rel.parts[0]


def _workspace_local_paths(bindings: list[dict[str, Any]], root: Path) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for binding in bindings:
        raw = str(binding.get("physical_location") or "").strip()
        if not raw or "://" in raw:
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve(strict=False)
        except OSError:
            continue
        folder = _folder_name(resolved, root)
        if folder is not None:
            rows.append((resolved, folder))
    return rows


def _cached_folder_counts(root: Path) -> tuple[str, int, Counter[str]]:
    """Read the process-local SIM/1 cache without causing a structural scan."""
    engine = StructuralIntelligence(root)
    status = engine.structural_status()
    state = str(status.get("status") or "UNINDEXED")
    if state == "UNINDEXED":
        return state, 0, Counter()

    cache = StructuralIntelligence._caches.get(str(engine.root))  # package-internal read-only projection
    if cache is None or cache.observation is None:
        return "UNINDEXED", 0, Counter()

    counts: Counter[str] = Counter()
    for rel in cache.files:
        parts = Path(rel).parts
        folder = parts[0] if len(parts) > 1 else "."
        counts[folder] += 1
    return state, len(cache.files), counts


def _contract_summary(svc: Any, family_ids: list[str], root: Path) -> tuple[dict[str, int], dict[str, Counter[str]]]:
    totals: Counter[str] = Counter()
    by_folder: dict[str, Counter[str]] = defaultdict(Counter)

    contracts = [
        contract
        for family_id in family_ids
        for contract in svc.store.find("contracts", {"family_id": family_id})
    ]
    totals["known"] = len(contracts)

    for contract in contracts:
        try:
            state = svc.contract_state(contract["entity_id"], include_content=False)
        except Exception:
            totals["unreadable"] += 1
            continue

        canonical = bool(state.get("canonical_content_present"))
        if canonical:
            totals["canonical"] += 1
        else:
            totals["registered_only"] += 1

        local_paths = _workspace_local_paths(list(state.get("storage_bindings") or []), root)
        folders = sorted({folder for _, folder in local_paths})
        for folder in folders:
            by_folder[folder]["contracts"] += 1

        existing = [(path, folder) for path, folder in local_paths if path.is_file()]
        if existing:
            totals["local_found"] += 1
            for folder in sorted({folder for _, folder in existing}):
                by_folder[folder]["local_found"] += 1
        elif local_paths:
            totals["missing"] += 1
            for folder in folders:
                by_folder[folder]["missing"] += 1
            continue
        else:
            if canonical:
                totals["captured_only"] += 1
            else:
                totals["unbound"] += 1
            continue

        if not canonical:
            continue

        expected_hash = str(state.get("current_content_hash") or "")
        if not expected_hash:
            totals["captured_only"] += 1
            continue

        binding_states: list[tuple[str, str]] = []
        for path, folder in existing:
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                binding_states.append((folder, "unreadable"))
                continue
            actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            binding_states.append((folder, "current" if actual_hash == expected_hash else "drifted"))

        readable_states = [state_name for _, state_name in binding_states if state_name != "unreadable"]
        if readable_states and all(state_name == "current" for state_name in readable_states):
            totals["current"] += 1
        elif any(state_name == "drifted" for state_name in readable_states):
            totals["drifted"] += 1
        else:
            totals["unreadable"] += 1

        for folder, state_name in binding_states:
            by_folder[folder][state_name] += 1

    return dict(totals), by_folder


def _work_summary(overview: dict[str, Any] | None) -> dict[str, int]:
    if overview is None:
        return {"active": 0, "blocked": 0, "done_claimed": 0, "verified": 0}
    counts = dict(overview.get("slice_counts") or {})
    return {
        "active": int(counts.get("ACTIVE", 0)) + int(counts.get("STARTED", 0)),
        "blocked": int(counts.get("BLOCKED", 0)),
        "done_claimed": int(counts.get("DONE_CLAIMED", 0)),
        "verified": int(counts.get("ASSURANCE_VERIFIED", 0)) + int(counts.get("ASSURANCE_ACCEPTED", 0)),
    }


def human_status_snapshot(workspace_root: str | None = None, *, max_folders: int = 8) -> dict[str, Any]:
    """Return a small display-only folder summary.

    The projection is deliberately dumb: no LLM, no semantic reconstruction, no full
    contract content, no IDs/hashes, no discovery admission and no structural scan.
    It reuses the current process-local structural cache when one already exists and
    reads only enough canonical/local contract state to report aggregate health/drift.
    """
    max_folders = max(1, min(int(max_folders), 12))
    attachment = workspace_attachment_snapshot()
    if workspace_root is not None:
        requested = Path(workspace_root).expanduser().resolve()
        current = str((attachment or {}).get("workspace_root") or "")
        try:
            same_root = bool(current) and Path(current).expanduser().resolve() == requested
        except OSError:
            same_root = False
        if not same_root:
            attachment = ensure_workspace_binding(str(requested))
    elif attachment is None:
        attachment = ensure_workspace_binding()
    root = Path(
        str((attachment or {}).get("workspace_root") or workspace_root or Path.cwd())
    ).expanduser().resolve()

    health = health_snapshot()
    health_ok = bool(health.get("ok"))
    database_ready = bool(health.get("database_ready"))
    version = str(health.get("version") or "unknown")

    structural_state, indexed_files, folder_files = _cached_folder_counts(root)

    overview: dict[str, Any] | None = None
    svc = None
    projection_warnings = 0
    try:
        svc = get_service()
        overview = svc.project_overview(workspace_project_key(str(root)))
    except KeyError:
        overview = None
    except Exception:
        overview = None
        projection_warnings += 1

    family_ids = [
        str(row.get("family_id"))
        for row in list((overview or {}).get("families") or [])
        if row.get("family_id")
    ]
    contracts: dict[str, int] = {
        "known": 0, "local_found": 0, "canonical": 0, "current": 0,
        "drifted": 0, "missing": 0, "registered_only": 0, "captured_only": 0,
        "unbound": 0, "unreadable": 0,
    }
    contract_folders: dict[str, Counter[str]] = {}
    if svc is not None and family_ids:
        observed, contract_folders = _contract_summary(svc, family_ids, root)
        contracts.update(observed)

    work = _work_summary(overview)
    warning_count = len(list((overview or {}).get("warnings") or [])) + projection_warnings
    admitted = overview is not None

    folder_names = set(folder_files) | set(contract_folders)
    folder_rows: list[dict[str, Any]] = []
    for name in folder_names:
        c = contract_folders.get(name, Counter())
        folder_rows.append({
            "name": name,
            "files": int(folder_files.get(name, 0)),
            "contracts": int(c.get("contracts", 0)),
            "current": int(c.get("current", 0)),
            "drifted": int(c.get("drifted", 0)),
            "missing": int(c.get("missing", 0)),
        })
    folder_rows.sort(key=lambda row: (-int(row["contracts"] > 0), -row["files"], row["name"]))
    omitted = max(0, len(folder_rows) - max_folders)
    folder_rows = folder_rows[:max_folders]

    health_label = "OK" if health_ok and database_ready else "DEGRADED"
    workspace_label = "KNOWN" if admitted else "UNADMITTED"
    discovery_label = structural_state

    lines = [
        f"MangoMe {version} · {root.name or 'workspace'}",
        f"HEALTH      {health_label} · DB {'ready' if database_ready else 'not ready'}",
        f"WORKSPACE   {workspace_label}",
        f"DISCOVERY   {discovery_label} · {indexed_files} indexed files · no scan triggered",
    ]

    if contracts["known"] == 0:
        lines.append("CONTRACTS   none known")
    else:
        contract_bits = [
            f"{contracts['known']} known",
            f"{contracts['local_found']} local",
            f"{contracts['canonical']} canonical",
            f"{contracts['current']} current",
        ]
        if contracts["drifted"]:
            contract_bits.append(f"{contracts['drifted']} drifted")
        if contracts["missing"]:
            contract_bits.append(f"{contracts['missing']} missing")
        if contracts["registered_only"]:
            contract_bits.append(f"{contracts['registered_only']} identity-only")
        if contracts["captured_only"]:
            contract_bits.append(f"{contracts['captured_only']} canonical-only")
        if contracts["unreadable"]:
            contract_bits.append(f"{contracts['unreadable']} unreadable")
        lines.append("CONTRACTS   " + " · ".join(contract_bits))

    if admitted:
        work_bits = [f"{work['active']} active", f"{work['verified']} verified"]
        if work["done_claimed"]:
            work_bits.append(f"{work['done_claimed']} done-claimed")
        if work["blocked"]:
            work_bits.append(f"{work['blocked']} blocked")
        lines.append("WORK        " + " · ".join(work_bits))
    else:
        lines.append("WORK        no admitted workspace state")

    lines.append(f"WARNINGS    {warning_count if warning_count else 'none'}")

    if folder_rows:
        lines.append("FOLDERS")
        for row in folder_rows:
            bits = [f"{row['files']} files"]
            if row["contracts"]:
                bits.append(f"{row['contracts']} contracts")
                if row["current"]:
                    bits.append(f"{row['current']} current")
                if row["drifted"]:
                    bits.append(f"{row['drifted']} drifted")
                if row["missing"]:
                    bits.append(f"{row['missing']} missing")
            suffix = "/" if row["name"] != "." else ""
            lines.append(f"  {row['name']}{suffix}  " + " · ".join(bits))
        if omitted:
            lines.append(f"  … +{omitted} folders")

    return {
        "ok": health_ok,
        "protocol": HUMAN_STATUS_PROTOCOL,
        "rendered": "\n".join(lines),
        "scan_performed": False,
        "canonical_mutations": 0,
    }
