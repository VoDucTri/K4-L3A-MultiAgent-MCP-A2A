from __future__ import annotations

import asyncio
from typing import Any

from ..contracts import Contracts
from ..mcp_gateway import EvidenceGateway
from ..trace import TraceWriter
from .order_agent import OrderAgent
from .payment_agent import PaymentAgent
from .policy_agent import PolicyAgent
from .shipment_agent import ShipmentAgent
from .verifier_agent import VerifierAgent


class CoordinatorRouter:
    """Coordinator and router orchestrating A2A multi-agent workflow."""

    def __init__(
        self, gateway: EvidenceGateway, trace: TraceWriter, contracts: Contracts
    ) -> None:
        self.gateway = gateway
        self.trace = trace
        self.contracts = contracts

    async def run(self, case: dict[str, Any]) -> dict[str, Any]:
        case_id = case["case_id"]
        customer_request = case.get("customer_request", {})
        order_id = customer_request.get("claimed_order_id", "")
        claims = customer_request.get("claims", [])
        policy_version = case.get("policy_version", "EC_POLICY_V1")
        claim_topics = {c.get("topic") for c in claims if c.get("topic")}

        # Step 1: Assign tasks to specialist agents
        self.trace.emit(
            case_id=case_id,
            event_type="task_assigned",
            actor="coordinator",
            target="specialists",
            decision_code="parallel_investigation",
            attributes={"order_id": order_id},
        )

        order_agent = OrderAgent(self.gateway, self.trace)
        payment_agent = PaymentAgent(self.gateway, self.trace)
        shipment_agent = ShipmentAgent(self.gateway, self.trace)

        # Step 2: Concurrently gather evidence across domains
        order_bundle, payment_bundle, shipment_bundle = await asyncio.gather(
            order_agent.investigate(case_id, order_id, claim_topics),
            payment_agent.investigate(case_id, order_id, claim_topics),
            shipment_agent.investigate(case_id, order_id, claim_topics),
        )

        # Step 3: Handoff evidence to Policy Agent
        self.trace.emit(
            case_id=case_id,
            event_type="handoff",
            actor="coordinator",
            target="policy-agent",
            decision_code="evidence_collected",
            attributes={
                "order_evidence_count": len(order_bundle.evidence_refs),
                "payment_evidence_count": len(payment_bundle.evidence_refs),
                "shipment_evidence_count": len(shipment_bundle.evidence_refs),
            },
        )

        policy_agent = PolicyAgent(self.gateway, self.trace)
        draft_output = await policy_agent.evaluate(
            case_id=case_id,
            order_id=order_id,
            policy_version=policy_version,
            claims=claims,
            order_bundle=order_bundle,
            payment_bundle=payment_bundle,
            shipment_bundle=shipment_bundle,
        )

        # Step 4: Handoff draft output to Verifier Agent
        self.trace.emit(
            case_id=case_id,
            event_type="handoff",
            actor="coordinator",
            target="verifier",
            decision_code="draft_ready",
        )

        verifier = VerifierAgent(self.contracts, self.trace)
        final_output = verifier.verify(draft_output, case_id)

        return final_output
