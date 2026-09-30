from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Iterable

AGENT_CONTEXT_VERSION = "MAC/1"

# MangoMe-native capacity profiles.  These are deliberately small and deterministic;
# they are not model quality claims.  A router/host may override the profile or budget
# through environment variables without changing canonical MangoMe state.
_TARGET_PROFILES: dict[str, dict[str, Any]] = {
    "generic-small-agent": {
        "context_budget": 4096,
        "optional_floor": 3,
        "notes": ["Prefer explicit constraints, current state and one bounded next action."],
    },
    "qwen-4b": {
        "context_budget": 4096,
        "optional_floor": 2,
        "notes": ["Keep one task boundary and compact optional background aggressively."],
    },
    "qwen-9b": {
        "context_budget": 8192,
        "optional_floor": 3,
        "notes": ["Retain broader evidence and limited supporting context."],
    },
    "frontier-specialist": {
        "context_budget": 16000,
        "optional_floor": 3,
        "notes": ["Preserve contradictions and richer supporting context when useful."],
    },
}

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "with", "work", "task", "current", "new",
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "und", "oder",
    "ist", "im", "in", "zu", "mit", "von", "für", "auf", "wir", "jetzt", "diese", "dieser",
    "dieses", "soll", "sollen", "muss", "müssen",
}

_C0_PATTERNS = (
    r"\bmust\s+not\b", r"\bmust\s+never\b", r"\bshall\s+not\b", r"\bnever\b",
    r"\bdo\s+not\b", r"^\s*no\b", r"\bforbidden\b", r"\bprohibited\b", r"\bwithout\s+explicit\s+approval\b",
    r"\bdarf\s+nicht\b", r"\bdürfen\s+nicht\b", r"\bniemals\b", r"\bverboten\b",
    r"\bnicht\s+zulässig\b", r"\bohne\s+ausdrückliche\s+freigabe\b",
)
_C1_PATTERNS = (
    r"\bmust\b", r"\bshall\b", r"\brequired\b", r"\bmandatory\b", r"\brequirement\b",
    r"\bfail[- ]closed\b", r"\bmuss\b", r"\bmüssen\b", r"\berforderlich\b", r"\bzwingend\b",
    r"\bdarf\s+nur\b", r"\bdürfen\s+nur\b", r"\bonly\b", r"\bnur\b", r"\bacceptance\b", r"\bakzeptanz\b",
)
_C2_PATTERNS = (
    r"\bshould\b", r"\bevidence\b", r"\bverify\b", r"\bverification\b", r"\bobserved\b",
    r"\bsollte\b", r"\bnachweis\b", r"\bverif", r"\bbeobachtet\b",
)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+)$")
_WORD_RE = re.compile(r"[\w-]{2,}", re.UNICODE)


class AgentContextError(RuntimeError):
    """Fail-closed error for deterministic worker-context projection."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class _Clause:
    handle: str
    text: str
    contract_id: str
    generation_id: str
    generation: int
    section_path: str
    line_start: int
    line_end: int
    content_hash: str
    criticality: int
    normative_type: str
    explicitly_bound: bool

    def source(self) -> dict[str, Any]:
        return {
            "source_type": "CONTRACT_CLAUSE",
            "contract_id": self.contract_id,
            "generation_id": self.generation_id,
            "generation": self.generation,
            "section_path": self.section_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "content_hash": self.content_hash,
            "explicitly_bound": self.explicitly_bound,
        }


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _token_estimate(text: str) -> int:
    # Provider-neutral planning estimate only.  Never claim tokenizer equivalence.
    return max(1, (len(str(text).encode("utf-8")) + 3) // 4)


def _tokens(value: Any) -> set[str]:
    return {
        token for token in (x.lower() for x in _WORD_RE.findall(str(value or "")))
        if token not in _STOPWORDS and not token.isdigit()
    }


def _criticality(text: str, *, kind: str = "context") -> tuple[int, str]:
    lower = text.lower()
    kind = str(kind or "context").lower()
    if kind in {"out_of_scope", "authorization", "security_constraint", "owner_instruction", "stop_condition"}:
        return 0, "MUST_NOT"
    if any(re.search(pattern, lower) for pattern in _C0_PATTERNS):
        return 0, "MUST_NOT"
    if kind in {"constraint", "requirement", "acceptance", "required_evidence"}:
        return 1, "MUST"
    if any(re.search(pattern, lower) for pattern in _C1_PATTERNS):
        return 1, "MUST"
    if kind in {"evidence", "current_state", "objective"}:
        return 2, "HIGH_VALUE"
    if any(re.search(pattern, lower) for pattern in _C2_PATTERNS):
        return 2, "SHOULD_OR_EVIDENCE"
    return 3, "INFO"


def _profile(name: str | None = None) -> dict[str, Any]:
    selected = str(name or os.environ.get("MANGOME_AGENT_CONTEXT_PROFILE") or "generic-small-agent").strip().lower()
    if selected not in _TARGET_PROFILES:
        raise AgentContextError(
            "AGENT_CONTEXT_PROFILE_UNKNOWN",
            f"unknown MangoMe agent context profile {selected!r}; available={sorted(_TARGET_PROFILES)}",
        )
    return {"name": selected, **_TARGET_PROFILES[selected]}


def _flush_block(
    blocks: list[tuple[int, int, str, str]],
    start: int | None,
    end: int | None,
    parts: list[str],
    section_path: str,
) -> tuple[None, None, list[str]]:
    text = " ".join(part.strip() for part in parts if part.strip()).strip()
    if start is not None and end is not None and text:
        blocks.append((start, end, section_path, text))
    return None, None, []


def _split_markdown(content: str) -> list[tuple[int, int, str, str]]:
    """Split canonical Markdown into deterministic paragraph/list clause blocks.

    This is deliberately syntax-light.  It preserves exact clause text and source line
    spans; it does not ask an LLM to infer a new normative document model.
    """

    lines = str(content or "").splitlines()
    headings: list[str] = []
    blocks: list[tuple[int, int, str, str]] = []
    start: int | None = None
    end: int | None = None
    parts: list[str] = []
    in_fence = False

    for number, raw in enumerate(lines, 1):
        stripped = raw.strip()
        heading = None if in_fence else _HEADING_RE.match(stripped)
        if heading:
            start, end, parts = _flush_block(blocks, start, end, parts, " / ".join(headings))
            level = len(heading.group(1))
            title = heading.group(2).strip()
            headings = headings[: level - 1]
            while len(headings) < level - 1:
                headings.append("")
            headings.append(title)
            continue

        if stripped.startswith("```") or stripped.startswith("~~~"):
            if start is None:
                start = number
            end = number
            parts.append(raw)
            in_fence = not in_fence
            continue

        if not stripped:
            if not in_fence:
                start, end, parts = _flush_block(blocks, start, end, parts, " / ".join(x for x in headings if x))
            elif start is not None:
                end = number
                parts.append(raw)
            continue

        list_match = None if in_fence else _LIST_RE.match(raw)
        if list_match:
            if start is not None:
                start, end, parts = _flush_block(blocks, start, end, parts, " / ".join(x for x in headings if x))
            start = number
            end = number
            parts = [list_match.group(1).strip()]
            continue

        if start is None:
            start = number
        end = number
        parts.append(raw)

    _flush_block(blocks, start, end, parts, " / ".join(x for x in headings if x))
    return blocks


def _unit(
    *,
    unit_id: str,
    text: str,
    kind: str,
    criticality: int | None = None,
    normative_type: str | None = None,
    source_refs: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
    score: float = 0.0,
) -> dict[str, Any]:
    level, inferred_type = _criticality(text, kind=kind)
    if criticality is not None:
        level = int(criticality)
    unit_metadata = dict(metadata or {})
    unit_metadata.setdefault("content_hash", hashlib.sha256(str(text).encode("utf-8")).hexdigest())
    return {
        "id": unit_id,
        "text": text,
        "kind": kind,
        "criticality": f"C{level}",
        "normative_type": normative_type or inferred_type,
        "source_refs": list(source_refs or [unit_id]),
        "metadata": unit_metadata,
        "score": round(float(score), 6),
    }


def _level(unit: dict[str, Any]) -> int:
    value = str(unit.get("criticality") or "C3").upper()
    try:
        return int(value[1:]) if value.startswith("C") else int(value)
    except ValueError:
        return 3


def _score(unit: dict[str, Any], query_tokens: set[str], order: int) -> float:
    level = _level(unit)
    text_tokens = _tokens(unit.get("text"))
    overlap = len(text_tokens & query_tokens)
    source = unit.get("metadata") or {}
    binding_bonus = 35.0 if source.get("explicitly_bound") else 0.0
    critical_bonus = {0: 1000.0, 1: 700.0, 2: 120.0, 3: 20.0, 4: 5.0, 5: 0.0}.get(level, 20.0)
    recency = max(0.0, 3.0 - order * 0.002)
    return critical_bonus + binding_bonus + overlap * 12.0 + recency


def _deduplicate(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for item in units:
        key = re.sub(r"\s+", " ", str(item.get("text") or "").strip()).casefold()
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            copied = dict(item)
            copied["source_refs"] = list(item.get("source_refs") or [])
            copied["metadata"] = dict(item.get("metadata") or {})
            seen[key] = copied
            out.append(copied)
            continue
        existing["source_refs"] = list(dict.fromkeys([
            *list(existing.get("source_refs") or []),
            *list(item.get("source_refs") or []),
        ]))
        if _level(item) < _level(existing):
            existing["criticality"] = item["criticality"]
            existing["normative_type"] = item.get("normative_type")
        duplicates = existing.setdefault("metadata", {}).setdefault("deduplicated_handles", [])
        duplicates.extend(ref for ref in item.get("source_refs") or [] if ref not in duplicates)
    return out


class AgentContextCompiler:
    """Compile canonical MangoMe state into a small worker-specific cognitive package.

    MangoMe remains the truth/governance layer.  This compiler is a disposable
    projection only: it does not create truth, Evidence, authority, Contract state or
    another memory database.  Routine contract context is read from canonical MongoDB
    generations; local contract files are not read here.
    """

    def __init__(self, service: Any) -> None:
        self.service = service

    def _contract_clauses(
        self,
        contract: dict[str, Any],
        *,
        explicitly_bound: bool,
    ) -> tuple[list[_Clause], dict[str, Any] | None, list[str]]:
        contract_id = str(contract.get("entity_id") or "")
        if not contract_id:
            return [], None, ["CONTRACT_ID_MISSING"]
        heads = self.service.store.find("contract_heads", {"contract_id": contract_id})
        if not heads:
            return [], None, [f"CONTRACT_GENERATION_MISSING:{contract_id}"]
        head = heads[0]
        generation_id = str(head.get("current_generation_id") or "")
        if not generation_id:
            return [], None, [f"CONTRACT_GENERATION_MISSING:{contract_id}"]
        generation = self.service.store.get("contract_generations", generation_id)
        if not generation:
            raise AgentContextError(
                "CONTRACT_GENERATION_BROKEN",
                f"contract head {contract_id!r} points to missing generation {generation_id!r}",
            )
        if str(generation.get("status") or "").upper() != "CANONICAL":
            raise AgentContextError(
                "CONTRACT_GENERATION_NOT_CANONICAL",
                f"contract {contract_id!r} current generation is not CANONICAL",
            )
        content = generation.get("content")
        if not isinstance(content, str):
            raise AgentContextError(
                "CONTRACT_GENERATION_CONTENT_INVALID",
                f"contract {contract_id!r} current generation has no canonical text body",
            )
        expected_hash = str(generation.get("content_hash") or "")
        actual_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if expected_hash and expected_hash != actual_hash:
            raise AgentContextError(
                "CONTRACT_GENERATION_HASH_MISMATCH",
                f"contract {contract_id!r} canonical generation content hash does not match stored content",
            )

        generation_number = int(generation.get("generation") or 0)
        clauses: list[_Clause] = []
        for index, (line_start, line_end, section_path, text) in enumerate(_split_markdown(content), 1):
            level, normative_type = _criticality(text)
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            handle = f"MC:{generation_id}:{index:04d}"
            clauses.append(_Clause(
                handle=handle,
                text=text,
                contract_id=contract_id,
                generation_id=generation_id,
                generation=generation_number,
                section_path=section_path,
                line_start=line_start,
                line_end=line_end,
                content_hash=content_hash,
                criticality=level,
                normative_type=normative_type,
                explicitly_bound=explicitly_bound,
            ))
        source = {
            "contract_id": contract_id,
            "declared_id": contract.get("declared_id"),
            "generation_id": generation_id,
            "generation": generation_number,
            "content_hash": actual_hash,
            "clause_count": len(clauses),
            "source": "MONGODB_CANONICAL_CONTRACT_GENERATION",
            "local_file_read": False,
        }
        return clauses, source, []

    def compile(
        self,
        *,
        family_id: str,
        family: dict[str, Any],
        current_spec: dict[str, Any] | None,
        current_slice: dict[str, Any] | None,
        relevant_contracts: list[dict[str, Any]],
        task_query: str | None = None,
        target_profile: str | None = None,
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        profile = _profile(target_profile)
        env_budget = os.environ.get("MANGOME_AGENT_CONTEXT_TOKEN_BUDGET", "").strip()
        budget = int(token_budget or (int(env_budget) if env_budget else profile["context_budget"]))
        if budget < 1:
            raise AgentContextError("AGENT_CONTEXT_BUDGET_INVALID", "agent context token budget must be positive")

        query_parts = [
            task_query or "",
            (current_slice or {}).get("objective") or "",
            (current_slice or {}).get("title") or "",
            (current_spec or {}).get("objective") or "",
            family.get("title") or "",
        ]
        query = " ".join(str(x).strip() for x in query_parts if str(x or "").strip()).strip() or family_id
        query_tokens = _tokens(query)

        units: list[dict[str, Any]] = []
        spec = current_spec or {}
        spec_id = str(spec.get("entity_id") or "CURRENT_SPEC")
        if spec.get("objective"):
            units.append(_unit(
                unit_id=f"MS:{spec_id}:OBJECTIVE",
                text=str(spec["objective"]), kind="objective", criticality=2,
                source_refs=[spec_id], metadata={"source_type": "SPECIFICATION", "field": "objective"},
            ))
        for field, kind, level in (
            ("constraints", "constraint", 1),
            ("out_of_scope", "out_of_scope", 0),
            ("acceptance_criteria", "acceptance", 1),
            ("required_evidence", "required_evidence", 1),
        ):
            for index, text in enumerate(spec.get(field) or [], 1):
                units.append(_unit(
                    unit_id=f"MS:{spec_id}:{field.upper()}:{index:03d}",
                    text=str(text), kind=kind, criticality=level,
                    source_refs=[spec_id], metadata={"source_type": "SPECIFICATION", "field": field, "index": index},
                ))

        slice_doc = current_slice or {}
        slice_id = str(slice_doc.get("entity_id") or "")
        if slice_doc.get("objective"):
            units.append(_unit(
                unit_id=f"SL:{slice_id or family_id}:OBJECTIVE",
                text=str(slice_doc["objective"]), kind="objective", criticality=2,
                source_refs=[slice_id or family_id],
                metadata={"source_type": "SLICE", "field": "objective", "explicitly_bound": True},
            ))
        for index, gate in enumerate(slice_doc.get("gates") or [], 1):
            if not isinstance(gate, dict) or not gate.get("description"):
                continue
            gate_level = 1 if str(gate.get("status") or "OPEN").upper() != "PASS" else 2
            units.append(_unit(
                unit_id=f"SL:{slice_id or family_id}:GATE:{index:03d}",
                text=str(gate["description"]), kind="requirement", criticality=gate_level,
                source_refs=[slice_id or family_id],
                metadata={"source_type": "SLICE_GATE", "status": gate.get("status"), "explicitly_bound": True},
            ))

        explicitly_bound_contracts = set(str(x) for x in (slice_doc.get("contract_ids") or []))
        contract_sources: list[dict[str, Any]] = []
        warnings: list[str] = []
        clause_units: list[dict[str, Any]] = []
        for contract in relevant_contracts:
            contract_id = str(contract.get("entity_id") or "")
            clauses, source, clause_warnings = self._contract_clauses(
                contract,
                explicitly_bound=(contract_id in explicitly_bound_contracts),
            )
            warnings.extend(clause_warnings)
            if source:
                contract_sources.append(source)
            for clause in clauses:
                clause_units.append(_unit(
                    unit_id=clause.handle,
                    text=clause.text,
                    kind="contract_clause",
                    criticality=clause.criticality,
                    normative_type=clause.normative_type,
                    source_refs=[clause.handle, clause.contract_id, clause.generation_id],
                    metadata=clause.source(),
                ))
        units.extend(clause_units)
        units = _deduplicate(units)

        for order, item in enumerate(units):
            item["score"] = round(_score(item, query_tokens, order), 6)

        critical = [item for item in units if _level(item) <= 1]
        optional = [item for item in units if _level(item) > 1 and _level(item) <= int(profile["optional_floor"])]
        critical.sort(key=lambda item: (-float(item.get("score") or 0.0), item["id"]))
        optional.sort(key=lambda item: (-float(item.get("score") or 0.0), item["id"]))

        fixed_tokens = _token_estimate(query) + 96
        critical_tokens = sum(_token_estimate(item["text"]) for item in critical)
        kept = list(critical)
        used = fixed_tokens + critical_tokens
        over_budget_due_to_critical = used > budget
        if not over_budget_due_to_critical:
            for item in optional:
                tokens = _token_estimate(item["text"])
                if used + tokens > budget:
                    continue
                kept.append(item)
                used += tokens

        kept_ids = {item["id"] for item in kept}
        omitted = [item for item in units if item["id"] not in kept_ids]
        expandable_handles = []
        for item in omitted:
            metadata = dict(item.get("metadata") or {})
            handle = {
                "handle": item["id"],
                "kind": item.get("kind"),
                "criticality": item.get("criticality"),
                "normative_type": item.get("normative_type"),
                "source_refs": list(item.get("source_refs") or []),
                "content_hash": metadata.get("content_hash") or hashlib.sha256(str(item.get("text") or "").encode("utf-8")).hexdigest(),
            }
            # Only metadata leaves the active context.  Omitted text is intentionally absent.
            for key in (
                "source_type", "contract_id", "generation_id", "generation", "section_path",
                "line_start", "line_end", "field", "index", "status", "explicitly_bound",
            ):
                if key in metadata:
                    handle[key] = metadata[key]
            expandable_handles.append(handle)

        critical_ids = {item["id"] for item in critical}
        retained_critical_ids = critical_ids & kept_ids
        fidelity = 1.0 if not critical_ids else len(retained_critical_ids) / len(critical_ids)
        source_complete = not warnings
        source_tokens = fixed_tokens + sum(_token_estimate(item["text"]) for item in units)
        compiled_tokens = fixed_tokens + sum(_token_estimate(item["text"]) for item in kept)
        source_state_hash = _json_hash({
            "family_id": family_id,
            "query": query,
            "profile": profile["name"],
            "sources": [
                [item["id"], item.get("criticality"), (item.get("metadata") or {}).get("content_hash") or _json_hash(item.get("text"))]
                for item in units
            ],
        })

        critical_out = [item for item in kept if _level(item) <= 1]
        facts_out = [item for item in kept if _level(item) > 1]
        status = "PARTIAL" if warnings else "READY"
        if not source_complete:
            routing_signal = "BLOCKED_CANONICAL_SOURCE_INCOMPLETE"
        elif over_budget_due_to_critical:
            routing_signal = "SPLIT_OR_ROUTE_LARGER_CONTEXT"
        else:
            routing_signal = "READY"
        return {
            "protocol": AGENT_CONTEXT_VERSION,
            "context_status": status,
            "target_profile": profile["name"],
            "token_budget": budget,
            "task_query": query,
            "immutable": critical_out,
            "facts": facts_out,
            "expandable_handles": expandable_handles,
            "contract_sources": contract_sources,
            "warnings": warnings,
            "receipt": {
                "source_units": len(units),
                "kept_units": len(kept),
                "omitted_units": len(omitted),
                "source_token_estimate": source_tokens,
                "compiled_token_estimate": compiled_tokens,
                "compression_ratio": round(compiled_tokens / max(1, source_tokens), 6),
                "source_state_hash": source_state_hash,
                "over_budget_due_to_critical": over_budget_due_to_critical,
                "token_estimator": "UTF8_BYTES_DIV_4_PLANNING_ESTIMATE",
            },
            "fidelity": {
                "passed": fidelity == 1.0 and source_complete,
                "critical_retention": round(fidelity, 6),
                "canonical_source_complete": source_complete,
                "critical_text_lossless": True,
                "missing_critical_ids": sorted(critical_ids - retained_critical_ids),
            },
            "routing_signal": routing_signal,
            "source_policy": {
                "routine_contract_source": "MONGODB_CANONICAL_CONTRACT_GENERATION",
                "local_contract_file_read": False,
                "full_contract_in_worker_context": False,
                "omitted_text_embedded_in_handles": False,
            },
            "rule": (
                "MANGOME_DEFINES_TRUTH; PCH_DEFINES_RESIDENCY; MAC_COMPILES_WORKER_CONTEXT; "
                "C0_C1_ARE_NEVER_DROPPED_FOR_BUDGET; OMITTED_TEXT_STAYS_EXTERNAL"
            ),
        }
