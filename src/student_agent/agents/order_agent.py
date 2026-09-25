from __future__ import annotations

import logging
from typing import Any

from ..mcp_gateway import EvidenceGateway
from ..trace import TraceWriter
from .models import OrderEvidenceBundle

logger = logging.getLogger(__name__)


class OrderAgent:
    """Specialist agent responsible for retrieving order, item, and seller evidence."""

    def __init__(self, gateway: EvidenceGateway, trace: TraceWriter) -> None:
        self.gateway = gateway
        self.trace = trace

    async def investigate(self, case_id: str, order_id: str) -> OrderEvidenceBundle:
        bundle = OrderEvidenceBundle()
        bundle.order_ids.add(order_id)

        # 1. Retrieve authoritative order record
        try:
            order_res = await self.gateway.call("get_order", case_id=case_id, order_id=order_id)
            ev_ref = order_res.get("evidence_ref")
            if ev_ref:
                bundle.evidence_refs.append(ev_ref)
                self.trace.emit(
                    case_id=case_id,
                    event_type="tool_result_consumed",
                    actor="order-agent",
                    tool_name="get_order",
                    evidence_refs=[ev_ref],
                )
            bundle.order = order_res.get("data")
        except Exception as exc:
            logger.warning("OrderAgent get_order failed for %s: %s", case_id, exc)

        # 2. Retrieve order items and associated sellers
        try:
            items_res = await self.gateway.call(
                "get_order_items", case_id=case_id, order_id=order_id
            )
            ev_ref = items_res.get("evidence_ref")
            if ev_ref:
                bundle.evidence_refs.append(ev_ref)
                self.trace.emit(
                    case_id=case_id,
                    event_type="tool_result_consumed",
                    actor="order-agent",
                    tool_name="get_order_items",
                    evidence_refs=[ev_ref],
                )
            data = items_res.get("data")
            if isinstance(data, list):
                bundle.items = data
                for item in data:
                    if isinstance(item, dict):
                        item_id = item.get("order_item_id")
                        if item_id:
                            bundle.item_ids.add(str(item_id))
                        seller_id = item.get("seller_id")
                        if seller_id:
                            bundle.seller_ids.add(str(seller_id))
        except Exception as exc:
            logger.warning("OrderAgent get_order_items failed for %s: %s", case_id, exc)

        # 3. Retrieve authoritative seller details if sellers are associated
        if bundle.seller_ids:
            try:
                seller_res = await self.gateway.call(
                    "get_sellers", case_id=case_id, order_id=order_id
                )
                ev_ref = seller_res.get("evidence_ref")
                if ev_ref:
                    bundle.evidence_refs.append(ev_ref)
                    self.trace.emit(
                        case_id=case_id,
                        event_type="tool_result_consumed",
                        actor="order-agent",
                        tool_name="get_sellers",
                        evidence_refs=[ev_ref],
                    )
                seller_data = seller_res.get("data")
                if isinstance(seller_data, list):
                    bundle.sellers = seller_data
            except Exception as exc:
                logger.debug("OrderAgent get_sellers failed for %s: %s", case_id, exc)

        return bundle
