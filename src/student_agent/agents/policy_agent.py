from __future__ import annotations

import logging
from typing import Any

from ..mcp_gateway import EvidenceGateway
from ..trace import TraceWriter
from .models import (
    OrderEvidenceBundle,
    PaymentEvidenceBundle,
    PolicyEvidenceBundle,
    ShipmentEvidenceBundle,
)

logger = logging.getLogger(__name__)

CAUSE_CODES: dict[str, str] = {
    "canceled_order_paid": "ORDER_CANCELED_PAYMENT_CAPTURED",
    "unavailable_order_paid": "ORDER_UNAVAILABLE_PAYMENT_CAPTURED",
    "late_delivery_seller": "SELLER_HANDOFF_DELAY",
    "late_delivery_logistics": "CARRIER_TRANSIT_DELAY",
    "valid_split_payment": "CUSTOMER_SPLIT_PAYMENT_AUTHORIZED",
    "payment_mismatch": "AMOUNT_MISMATCH_RECORDED",
    "duplicate_charge": "DUPLICATE_PAYMENT_CAPTURED",
    "refund_pending": "REFUND_SETTLEMENT_IN_PROGRESS",
    "refund_failed": "GATEWAY_REFUND_ERROR",
    "unsupported_claim": "CUSTOMER_UNSUPPORTED_DISPUTE",
    "insufficient_evidence": "INSUFFICIENT_EVIDENCE",
}


class PolicyAgent:
    """Specialist agent responsible for evaluating evidence against business policy and formulating resolution."""

    def __init__(self, gateway: EvidenceGateway, trace: TraceWriter) -> None:
        self.gateway = gateway
        self.trace = trace

    async def evaluate(
        self,
        *,
        case_id: str,
        order_id: str,
        policy_version: str,
        claims: list[dict[str, Any]],
        order_bundle: OrderEvidenceBundle,
        payment_bundle: PaymentEvidenceBundle,
        shipment_bundle: ShipmentEvidenceBundle,
    ) -> dict[str, Any]:
        policy_bundle = PolicyEvidenceBundle()

        # 1. Fetch authoritative policy rules for this case
        try:
            policy_res = await self.gateway.call(
                "get_policy", case_id=case_id, policy_version=policy_version
            )
            ev_ref = policy_res.get("evidence_ref")
            if ev_ref:
                policy_bundle.evidence_refs.append(ev_ref)
                self.trace.emit(
                    case_id=case_id,
                    event_type="tool_result_consumed",
                    actor="policy-agent",
                    tool_name="get_policy",
                    evidence_refs=[ev_ref],
                )
            policy_bundle.policy = policy_res.get("data", {})
        except Exception as exc:
            logger.warning("PolicyAgent get_policy failed for %s: %s", case_id, exc)

        rules = policy_bundle.policy.get("rules", {})
        currency = policy_bundle.policy.get("currency", "BRL")

        # 2. Collect all evidence refs across all specialists
        all_evidence_refs: list[str] = []
        for ref in (
            order_bundle.evidence_refs
            + payment_bundle.evidence_refs
            + shipment_bundle.evidence_refs
            + policy_bundle.evidence_refs
        ):
            if ref and ref not in all_evidence_refs:
                all_evidence_refs.append(ref)

        # 3. Determine the primary issue from evidence signals
        primary_issue = self._determine_primary_issue(
            claims=claims,
            order_bundle=order_bundle,
            payment_bundle=payment_bundle,
            shipment_bundle=shipment_bundle,
            rules=rules,
        )

        rule = rules.get(primary_issue, {})
        case_status = rule.get("case_status", "action_required")
        recommended_action = rule.get("recommended_action", "document_no_action")
        refund_brl = float(rule.get("refund_brl", 0.0))
        responsible_parties = rule.get("responsible_parties", [])
        if not responsible_parties:
            responsible_parties = [{"party_type": "unknown", "party_id": None}]

        cause_code = CAUSE_CODES.get(primary_issue, "INSUFFICIENT_EVIDENCE")

        # 4. Assess individual customer claims
        claim_assessments = []
        for c in claims:
            cid = c.get("claim_id", "")
            topic = c.get("topic", "")
            if topic == primary_issue:
                verdict = "supported"
            elif topic == "requested_full_refund":
                if recommended_action == "issue_refund":
                    verdict = "supported"
                elif refund_brl > 0:
                    verdict = "partially_supported"
                else:
                    verdict = "unsupported"
            else:
                verdict = "unsupported"

            claim_assessments.append(
                {
                    "claim_id": cid,
                    "verdict": verdict,
                    "confidence": 0.95,
                    "evidence_refs": all_evidence_refs[:20],
                }
            )

        # 5. Formulate financial resolution
        refund_lines = []
        if refund_brl > 0:
            refund_lines.append(
                {
                    "reason_code": recommended_action,
                    "amount_brl": refund_brl,
                    "entity_id": order_id,
                }
            )

        financial_resolution = {
            "currency": currency,
            "recommended_refund_brl": refund_brl,
            "refund_lines": refund_lines,
        }

        # 6. Build affected entities
        affected_entities = {
            "order_ids": sorted(list(order_bundle.order_ids))[:20],
            "item_ids": sorted(list(order_bundle.item_ids))[:20],
            "seller_ids": sorted(list(order_bundle.seller_ids))[:20],
            "payment_references": sorted(list(payment_bundle.payment_references))[:20],
            "shipment_ids": sorted(list(shipment_bundle.shipment_ids))[:20],
        }

        resolution_actions = [recommended_action] if recommended_action else ["document_no_action"]

        draft_output = {
            "schema_version": "day09-l3a-output-v2",
            "case_id": case_id,
            "assessment": {
                "primary_issue": primary_issue,
                "case_status": case_status,
                "confidence": 0.95,
            },
            "affected_entities": affected_entities,
            "claim_assessments": claim_assessments,
            "root_cause_analysis": {
                "ranked_causes": [{"cause_code": cause_code, "rank": 1}],
                "responsible_parties": responsible_parties,
            },
            "evidence_refs": all_evidence_refs[:30],
            "data_conflicts": [],
            "financial_resolution": financial_resolution,
            "resolution_actions": resolution_actions,
        }

        # Emit policy_decided trace event
        self.trace.emit(
            case_id=case_id,
            event_type="policy_decided",
            actor="policy-agent",
            decision_code=primary_issue,
            evidence_refs=all_evidence_refs[:20],
            attributes={
                "primary_issue": primary_issue,
                "case_status": case_status,
                "refund_brl": refund_brl,
            },
        )

        return draft_output

    def _determine_primary_issue(
        self,
        *,
        claims: list[dict[str, Any]],
        order_bundle: OrderEvidenceBundle,
        payment_bundle: PaymentEvidenceBundle,
        shipment_bundle: ShipmentEvidenceBundle,
        rules: dict[str, Any],
    ) -> str:
        # Check specific issue topic mentioned in claims
        specific_claimed_topic = None
        for c in claims:
            t = c.get("topic")
            if t and t != "requested_full_refund":
                specific_claimed_topic = t
                break

        order_status = (order_bundle.order or {}).get("order_status")

        # 1. Canceled order
        if order_status == "canceled":
            return "canceled_order_paid"

        # 2. Unavailable order
        if order_status == "unavailable":
            return "unavailable_order_paid"

        # 3. Shipment events for late delivery
        shipment_events = shipment_bundle.events
        for ev in shipment_events:
            if ev.get("event_type") == "delivered_late":
                actor = ev.get("actor")
                if actor == "seller":
                    return "late_delivery_seller"
                if actor in ("logistics_provider", "carrier"):
                    return "late_delivery_logistics"

        # 4. Refund timeline issues
        if payment_bundle.refund_timeline:
            ref_events = payment_bundle.refund_timeline.get("events", [])
            for rev in ref_events:
                status = rev.get("status")
                if status == "failed":
                    return "refund_failed"
                if status in ("pending", "processing"):
                    return "refund_pending"

        # 5. Payment duplicate charge or mismatch
        payments = payment_bundle.payments
        if len(payments) > 1:
            # Check duplicate charge
            vals = [p.get("payment_value") for p in payments if p.get("payment_value")]
            if specific_claimed_topic == "duplicate_charge":
                return "duplicate_charge"
            if specific_claimed_topic == "payment_mismatch":
                return "payment_mismatch"
            if specific_claimed_topic == "valid_split_payment":
                return "valid_split_payment"

        # 6. If claimed topic is valid_split_payment and order is delivered normally
        if specific_claimed_topic == "valid_split_payment":
            return "valid_split_payment"

        # 7. If claimed topic matches an available rule and no evidence contradicts it
        if specific_claimed_topic and specific_claimed_topic in rules:
            return specific_claimed_topic

        # Default fallback: unsupported claim or insufficient evidence
        if specific_claimed_topic == "unsupported_claim":
            return "unsupported_claim"

        return "unsupported_claim" if rules else "insufficient_evidence"
