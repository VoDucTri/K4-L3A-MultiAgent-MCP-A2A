from __future__ import annotations

import logging
from typing import Any

from ..mcp_gateway import EvidenceGateway
from ..trace import TraceWriter
from .models import ShipmentEvidenceBundle

logger = logging.getLogger(__name__)


class ShipmentAgent:
    """Specialist agent responsible for retrieving delivery and shipment event evidence."""

    def __init__(self, gateway: EvidenceGateway, trace: TraceWriter) -> None:
        self.gateway = gateway
        self.trace = trace

    async def investigate(
        self, case_id: str, order_id: str, claim_topics: set[str] | None = None
    ) -> ShipmentEvidenceBundle:
        bundle = ShipmentEvidenceBundle()

        try:
            ship_res = await self.gateway.call(
                "get_shipment_summary", case_id=case_id, order_id=order_id
            )
            ev_ref = ship_res.get("evidence_ref")
            if ev_ref:
                bundle.evidence_refs.append(ev_ref)
                bundle.shipment_refs.append(ev_ref)
                self.trace.emit(
                    case_id=case_id,
                    event_type="tool_result_consumed",
                    actor="shipment-agent",
                    tool_name="get_shipment_summary",
                    evidence_refs=[ev_ref],
                )
            data = ship_res.get("data")
            if isinstance(data, dict):
                bundle.shipment = data
                bundle.events = data.get("events", [])
                bundle.shipment_ids.add(f"ship-{order_id[:8]}")
        except Exception as exc:
            logger.warning("ShipmentAgent get_shipment_summary failed for %s: %s", case_id, exc)

        return bundle
