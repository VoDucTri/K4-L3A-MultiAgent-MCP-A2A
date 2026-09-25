from __future__ import annotations

import logging
from typing import Any

from ..mcp_gateway import EvidenceGateway
from ..trace import TraceWriter
from .models import PaymentEvidenceBundle

logger = logging.getLogger(__name__)


class PaymentAgent:
    """Specialist agent responsible for retrieving payment and refund evidence."""

    def __init__(self, gateway: EvidenceGateway, trace: TraceWriter) -> None:
        self.gateway = gateway
        self.trace = trace

    async def investigate(
        self, case_id: str, order_id: str, claim_topics: set[str] | None = None
    ) -> PaymentEvidenceBundle:
        bundle = PaymentEvidenceBundle()
        topics = claim_topics or set()

        # 1. Retrieve base order payments
        try:
            pay_res = await self.gateway.call(
                "get_order_payments", case_id=case_id, order_id=order_id
            )
            ev_ref = pay_res.get("evidence_ref")
            if ev_ref:
                bundle.evidence_refs.append(ev_ref)
                bundle.order_payment_refs.append(ev_ref)
                self.trace.emit(
                    case_id=case_id,
                    event_type="tool_result_consumed",
                    actor="payment-agent",
                    tool_name="get_order_payments",
                    evidence_refs=[ev_ref],
                )
            data = pay_res.get("data")
            if isinstance(data, list):
                bundle.payments = data
                for idx, p in enumerate(data):
                    seq = p.get("payment_sequential", idx + 1)
                    bundle.payment_references.add(f"pay-{order_id[:8]}-{seq}")
        except Exception as exc:
            logger.warning("PaymentAgent get_order_payments failed for %s: %s", case_id, exc)

        # 2. Retrieve payment timeline only for payment discrepancies or split payments
        payment_dispute_topics = {"duplicate_charge", "payment_mismatch", "valid_split_payment"}
        if topics.intersection(payment_dispute_topics):
            try:
                tl_res = await self.gateway.call(
                    "get_payment_timeline", case_id=case_id, order_id=order_id
                )
                ev_ref = tl_res.get("evidence_ref")
                if ev_ref:
                    bundle.evidence_refs.append(ev_ref)
                    bundle.timeline_refs.append(ev_ref)
                    self.trace.emit(
                        case_id=case_id,
                        event_type="tool_result_consumed",
                        actor="payment-agent",
                        tool_name="get_payment_timeline",
                        evidence_refs=[ev_ref],
                    )
                bundle.payment_timeline = tl_res.get("data")
            except Exception as exc:
                logger.debug("PaymentAgent get_payment_timeline failed for %s: %s", case_id, exc)

        # 3. Retrieve refund timeline only for explicit refund disputes
        refund_dispute_topics = {"refund_pending", "refund_failed"}
        if topics.intersection(refund_dispute_topics):
            try:
                ref_res = await self.gateway.call(
                    "get_refund_timeline", case_id=case_id, order_id=order_id
                )
                ev_ref = ref_res.get("evidence_ref")
                if ev_ref:
                    bundle.evidence_refs.append(ev_ref)
                    bundle.refund_refs.append(ev_ref)
                    self.trace.emit(
                        case_id=case_id,
                        event_type="tool_result_consumed",
                        actor="payment-agent",
                        tool_name="get_refund_timeline",
                        evidence_refs=[ev_ref],
                    )
                bundle.refund_timeline = ref_res.get("data")
            except Exception as exc:
                logger.debug("PaymentAgent get_refund_timeline not found or failed for %s: %s", case_id, exc)

        return bundle
