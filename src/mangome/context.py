from __future__ import annotations

from .service import MangoMeService


class ContextCompiler:
    """Deterministic execution-context projection for IntakeGov/CogC downstream use."""

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    def compile(self, family_id: str, slice_id: str | None = None) -> dict:
        ctx = self.service.get_context(family_id)
        slices = ctx["slices"]
        selected = None
        if slice_id:
            selected = next((s for s in slices if s["entity_id"] == slice_id), None)
            if selected is None:
                raise KeyError(f"slice {slice_id} is not part of family {family_id}")
        else:
            active = [s for s in slices if s["entity_id"] in ctx["status"].get("active_slice_ids", [])]
            if active:
                selected = max(active, key=lambda s: s.get("last_activity_at") or s.get("started_at") or s["created_at"])
            elif ctx["status"].get("next_known_slice_ids"):
                next_id = ctx["status"]["next_known_slice_ids"][0]
                selected = next((s for s in slices if s["entity_id"] == next_id), None)

        contract_ids = set(selected.get("contract_ids", [])) if selected else set()
        relevant_contracts = [c for c in ctx["contracts"] if not contract_ids or c["entity_id"] in contract_ids]
        evidence_subjects = {family_id}
        if selected:
            evidence_subjects.add(selected["entity_id"])
        evidence = [e for e in ctx["evidence"] if e.get("subject_id") in evidence_subjects]
        return {
            "family": {
                "entity_id": ctx["family"]["entity_id"],
                "family_key": ctx["family"]["family_key"],
                "title": ctx["family"]["title"],
                "scope_ids": ctx["family"].get("scope_ids", []),
            },
            "current_state": ctx["status"],
            "effective_family": ctx["effective"],
            "current_spec": next((x for x in ctx.get("specs", []) if x.get("entity_id") == ctx["family"].get("current_spec_id")), None),
            "current_slice": selected,
            "active_plan_id": selected.get("active_plan_id") if selected else None,
            "relevant_contracts": relevant_contracts,
            "evidence": evidence,
            "instruction": (
                "Treat worker completion statements as claims. Mutations must stay bound to the active plan. "
                "Do not infer VERIFIED from DONE_CLAIMED and do not treat un-attested evidence as verification proof."
            ),
        }
