from __future__ import annotations

from .service import MangoMeService


class MangoMaintainer:
    """Deterministic maintenance, not an LLM agent."""

    def __init__(self, service: MangoMeService) -> None:
        self.service = service

    def refresh_all_family_views(self) -> dict[str, int]:
        families = self.service.store.find("families")
        refreshed = 0
        for family in families:
            self.service.status(family["entity_id"])
            refreshed += 1
        return {"families_refreshed": refreshed}

    def detect_declared_id_collisions(self) -> dict[str, list[str]]:
        contracts = self.service.store.find("contracts")
        by_id: dict[str, list[str]] = {}
        for c in contracts:
            by_id.setdefault(c["declared_id"], []).append(c["entity_id"])
        return {declared: ids for declared, ids in by_id.items() if len(ids) > 1}
