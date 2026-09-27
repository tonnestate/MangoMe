from __future__ import annotations

from typing import Any

from .ids import new_id
from .models import utcnow
from .schema import CURRENT_SCHEMA_VERSION
from .service import MangoMeError, MangoMeService

FJD_POLICY_VERSION = "FJD/1"
DEFAULT_USE_SIGNAL_CONFIDENCE = 0.80
DEFAULT_REVIEW_CONFIDENCE = 0.60

DECISION_TYPES = {"BOOL", "SCORE", "CHOICE"}
DECISION_ROLES = {"CLASSIFICATION", "TRIAGE", "ROUTING", "ACTIVATION", "PRIORITIZATION"}

_ALLOWED_USES = [
    "CLASSIFICATION",
    "TRIAGE",
    "ROUTING",
    "ACTIVATION",
    "PRIORITIZATION",
]
_FORBIDDEN_USES = [
    "CANONICAL_TRUTH",
    "EVIDENCE",
    "ASSURANCE",
    "VERIFICATION",
    "ACCEPTANCE",
    "MUTATION_AUTHORITY",
    "NORMATIVE_PROMOTION",
]


class FastJudgmentError(MangoMeError):
    pass


def _norm_type(value: Any) -> str:
    decision_type = str(value or "").strip().upper()
    if decision_type not in DECISION_TYPES:
        raise FastJudgmentError(f"decision type must be one of {sorted(DECISION_TYPES)}")
    return decision_type


def _norm_role(value: Any) -> str:
    role = str(value or "CLASSIFICATION").strip().upper()
    if role not in DECISION_ROLES:
        raise FastJudgmentError(f"decision role must be one of {sorted(DECISION_ROLES)}")
    return role


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FastJudgmentError("confidence must be a number between 0 and 1")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise FastJudgmentError("confidence must be between 0 and 1")
    return confidence


def _validated_value(decision: dict[str, Any], decision_type: str) -> Any:
    value = decision.get("value")
    if decision_type == "BOOL":
        if not isinstance(value, bool):
            raise FastJudgmentError("BOOL decision value must be a boolean")
        return value

    if decision_type == "SCORE":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise FastJudgmentError("SCORE decision value must be numeric")
        minimum = float(decision.get("min", 0.0))
        maximum = float(decision.get("max", 1.0))
        if minimum >= maximum:
            raise FastJudgmentError("SCORE min must be lower than max")
        numeric = float(value)
        if not minimum <= numeric <= maximum:
            raise FastJudgmentError(f"SCORE value must be within [{minimum}, {maximum}]")
        return numeric

    options = [str(item) for item in (decision.get("options") or [])]
    if not options:
        raise FastJudgmentError("CHOICE decision requires non-empty options")
    if str(value) not in options:
        raise FastJudgmentError("CHOICE value must be one of the declared options")
    return str(value)


class FastJudgmentService:
    """Provider-neutral typed System-1-style judgments with hard epistemic boundaries.

    FJD/1 does not perform model inference. Hosts may obtain a BOOL/SCORE/CHOICE result
    from a local classifier, heuristic, small model, or any other engine and pass that
    result here for strict validation and confidence-based gating. The result remains
    worker judgment: it may influence routing/activation/triage but can never create
    canonical truth, Evidence, assurance, verification, or mutation authority.
    """

    def __init__(self, service: MangoMeService | None = None) -> None:
        self.service = service

    def assess(
        self,
        *,
        purpose: str,
        decisions: list[dict[str, Any]],
        source: str = "HOST",
        model_ref: str | None = None,
        use_signal_confidence: float = DEFAULT_USE_SIGNAL_CONFIDENCE,
        review_confidence: float = DEFAULT_REVIEW_CONFIDENCE,
        high_impact: bool = False,
    ) -> dict[str, Any]:
        purpose = str(purpose or "").strip()
        if not purpose:
            raise FastJudgmentError("purpose is required")
        if not decisions:
            raise FastJudgmentError("at least one typed decision is required")

        use_threshold = _confidence(use_signal_confidence)
        review_threshold = _confidence(review_confidence)
        if review_threshold >= use_threshold:
            raise FastJudgmentError("review_confidence must be lower than use_signal_confidence")

        normalized: list[dict[str, Any]] = []
        for index, decision in enumerate(decisions):
            name = str(decision.get("name") or "").strip()
            if not name:
                raise FastJudgmentError(f"decision[{index}] requires name")
            decision_type = _norm_type(decision.get("type"))
            role = _norm_role(decision.get("role"))
            confidence = _confidence(decision.get("confidence"))
            value = _validated_value(decision, decision_type)

            if high_impact:
                disposition = "REVIEW_REQUIRED"
            elif confidence >= use_threshold:
                disposition = "USE_SIGNAL"
            elif confidence >= review_threshold:
                disposition = "REVIEW"
            else:
                disposition = "ESCALATE"

            row: dict[str, Any] = {
                "name": name,
                "type": decision_type,
                "role": role,
                "value": value,
                "confidence": round(confidence, 6),
                "disposition": disposition,
            }
            if decision_type == "SCORE":
                row["range"] = [float(decision.get("min", 0.0)), float(decision.get("max", 1.0))]
            elif decision_type == "CHOICE":
                row["options"] = [str(item) for item in decision.get("options") or []]
            normalized.append(row)

        dispositions = {row["disposition"] for row in normalized}
        if "ESCALATE" in dispositions:
            batch_disposition = "ESCALATE"
        elif "REVIEW_REQUIRED" in dispositions:
            batch_disposition = "REVIEW_REQUIRED"
        elif "REVIEW" in dispositions:
            batch_disposition = "REVIEW"
        else:
            batch_disposition = "USE_SIGNAL"

        fallback = None if batch_disposition == "USE_SIGNAL" else "STRONGER_REASONING_OR_DETERMINISTIC_CHECK"
        return {
            "protocol": FJD_POLICY_VERSION,
            "purpose": purpose,
            "source": str(source or "HOST"),
            "model_ref": str(model_ref) if model_ref else None,
            "epistemic_role": "WORKER_JUDGMENT",
            "high_impact": bool(high_impact),
            "thresholds": {
                "use_signal_confidence": use_threshold,
                "review_confidence": review_threshold,
            },
            "decisions": normalized,
            "batch_disposition": batch_disposition,
            "fallback": fallback,
            "allowed_uses": list(_ALLOWED_USES),
            "forbidden_uses": list(_FORBIDDEN_USES),
            "authority": {
                "may_create_canonical_truth": False,
                "may_create_evidence": False,
                "may_verify": False,
                "may_accept": False,
                "may_grant_mutation": False,
            },
            "principles": [
                "CONFIDENCE_IS_NOT_TRUTH",
                "FAST_JUDGMENT_IS_NOT_EVIDENCE",
                "FAST_JUDGMENT_IS_NOT_AUTHORITY",
                "LOW_CONFIDENCE_ESCALATES",
                "HIGH_IMPACT_REQUIRES_REVIEW",
                "PROVIDER_IS_REPLACEABLE",
            ],
        }

    def record(
        self,
        *,
        work_id: str,
        actor_id: str,
        purpose: str,
        decisions: list[dict[str, Any]],
        source: str = "HOST",
        model_ref: str | None = None,
        context_refs: list[str] | None = None,
        use_signal_confidence: float = DEFAULT_USE_SIGNAL_CONFIDENCE,
        review_confidence: float = DEFAULT_REVIEW_CONFIDENCE,
        high_impact: bool = False,
    ) -> dict[str, Any]:
        if self.service is None:
            raise FastJudgmentError("recording requires a MangoMe service")
        work = self.service.store.get("work_identities", str(work_id))
        if work is None:
            raise FastJudgmentError(f"unknown WorkIdentity {work_id}")
        if not str(actor_id or "").strip():
            raise FastJudgmentError("actor_id is required")

        result = self.assess(
            purpose=purpose,
            decisions=decisions,
            source=source,
            model_ref=model_ref,
            use_signal_confidence=use_signal_confidence,
            review_confidence=review_confidence,
            high_impact=high_impact,
        )
        now = utcnow()
        doc = {
            "entity_id": new_id(),
            "schema_version": CURRENT_SCHEMA_VERSION,
            "revision": 0,
            "created_at": now,
            "updated_at": now,
            "protocol": FJD_POLICY_VERSION,
            "persistence_level": "PROGRESSIVE",
            "epistemic_role": "WORKER_JUDGMENT",
            "work_id": str(work_id),
            "family_id": str(work.get("family_id") or ""),
            "actor_id": str(actor_id),
            "purpose": result["purpose"],
            "source": result["source"],
            "model_ref": result["model_ref"],
            "context_refs": list(dict.fromkeys(str(item) for item in (context_refs or []) if str(item).strip())),
            "high_impact": result["high_impact"],
            "thresholds": result["thresholds"],
            "decisions": result["decisions"],
            "batch_disposition": result["batch_disposition"],
            "fallback": result["fallback"],
            "authority": result["authority"],
            "principles": result["principles"],
        }
        stored = self.service.store.insert("fast_judgments", doc)
        return {
            "judgment": stored,
            "rule": (
                "FJD/1 persists only progressive worker judgment. It may guide classification, triage, routing, "
                "activation or prioritization, but it never creates truth, Evidence, assurance or authority."
            ),
        }

    def status(self, judgment_id: str) -> dict[str, Any]:
        if self.service is None:
            raise FastJudgmentError("status requires a MangoMe service")
        row = self.service.store.get("fast_judgments", str(judgment_id))
        if row is None:
            raise FastJudgmentError(f"unknown fast judgment {judgment_id}")
        return {"judgment": row}
