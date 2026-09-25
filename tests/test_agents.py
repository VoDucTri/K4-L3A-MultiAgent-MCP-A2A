from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from student_agent.agents.coordinator import CoordinatorRouter
from student_agent.agents.models import (
    OrderEvidenceBundle,
    PaymentEvidenceBundle,
    ShipmentEvidenceBundle,
)
from student_agent.agents.policy_agent import PolicyAgent
from student_agent.agents.verifier_agent import VerifierAgent
from student_agent.contracts import Contracts


@pytest.fixture
def contracts() -> Contracts:
    root = Path(__file__).resolve().parents[1]
    return Contracts(root / "contracts" / "schemas")


def test_verifier_accepts_valid_schema(contracts: Contracts) -> None:
    trace = MagicMock()
    verifier = VerifierAgent(contracts, trace)
    valid_draft = {
        "schema_version": "day09-l3a-output-v2",
        "case_id": "L3A_CASE_TEST",
        "assessment": {
            "primary_issue": "canceled_order_paid",
            "case_status": "action_required",
            "confidence": 0.95,
        },
        "affected_entities": {
            "order_ids": ["ord-12345678"],
            "item_ids": ["item-12345678"],
            "seller_ids": ["seller-12345678"],
            "payment_references": ["pay-ord-1"],
            "shipment_ids": ["ship-ord"],
        },
        "claim_assessments": [
            {
                "claim_id": "claim-001-a",
                "verdict": "supported",
                "confidence": 0.95,
                "evidence_refs": ["ev_12345678901234567890"],
            }
        ],
        "root_cause_analysis": {
            "ranked_causes": [{"cause_code": "ORDER_CANCELED_PAYMENT_CAPTURED", "rank": 1}],
            "responsible_parties": [{"party_type": "platform", "party_id": None}],
        },
        "evidence_refs": ["ev_12345678901234567890"],
        "data_conflicts": [],
        "financial_resolution": {
            "currency": "BRL",
            "recommended_refund_brl": 50.0,
            "refund_lines": [
                {"reason_code": "issue_refund", "amount_brl": 50.0, "entity_id": "ord-12345678"}
            ],
        },
        "resolution_actions": ["issue_refund"],
    }
    verified = verifier.verify(valid_draft, "L3A_CASE_TEST")
    assert verified["case_id"] == "L3A_CASE_TEST"
    assert trace.emit.called


def test_policy_agent_evaluates_canceled_order() -> None:
    import asyncio

    async def _run() -> None:
        gateway = MagicMock()
        gateway.call = AsyncMock(
            return_value={
                "schema_version": "day09-mcp-evidence-v1",
                "evidence_ref": "ev_policy_evidence_1234567890",
                "result_hash": "sha256:" + "0" * 64,
                "domain": "policy",
                "data": {
                    "currency": "BRL",
                    "rules": {
                        "canceled_order_paid": {
                            "case_status": "action_required",
                            "recommended_action": "issue_refund",
                            "refund_brl": 79.0,
                            "responsible_parties": [{"party_type": "platform", "party_id": None}],
                        }
                    },
                },
            }
        )
        trace = MagicMock()
        policy_agent = PolicyAgent(gateway, trace)

        order_bundle = OrderEvidenceBundle(
            order={"order_status": "canceled"},
            evidence_refs=["ev_order_12345678901234567890"],
            order_ids={"ord-1"},
        )
        payment_bundle = PaymentEvidenceBundle(
            payments=[{"payment_value": "79.00"}],
            evidence_refs=["ev_pay_12345678901234567890"],
            payment_references={"pay-1"},
        )
        shipment_bundle = ShipmentEvidenceBundle(
            evidence_refs=["ev_ship_12345678901234567890"],
            shipment_ids={"ship-1"},
        )

        output = await policy_agent.evaluate(
            case_id="L3A_CASE_TEST",
            order_id="ord-1",
            policy_version="EC_POLICY_V1",
            claims=[
                {"claim_id": "claim-1", "topic": "canceled_order_paid"},
                {"claim_id": "claim-2", "topic": "requested_full_refund"},
            ],
            order_bundle=order_bundle,
            payment_bundle=payment_bundle,
            shipment_bundle=shipment_bundle,
        )

        assert output["assessment"]["primary_issue"] == "canceled_order_paid"
        assert output["financial_resolution"]["recommended_refund_brl"] == 79.0
        assert len(output["claim_assessments"]) == 2
        assert output["claim_assessments"][0]["verdict"] == "supported"
        assert output["claim_assessments"][1]["verdict"] == "supported"

    asyncio.run(_run())


def test_policy_agent_evaluates_split_payment() -> None:
    import asyncio

    async def _run() -> None:
        gateway = MagicMock()
        gateway.call = AsyncMock(
            return_value={
                "schema_version": "day09-mcp-evidence-v1",
                "evidence_ref": "ev_policy_evidence_1234567890",
                "result_hash": "sha256:" + "0" * 64,
                "domain": "policy",
                "data": {
                    "currency": "BRL",
                    "rules": {
                        "valid_split_payment": {
                            "case_status": "no_action",
                            "recommended_action": "document_no_action",
                            "refund_brl": 0.0,
                            "responsible_parties": [{"party_type": "customer", "party_id": None}],
                        }
                    },
                },
            }
        )
        trace = MagicMock()
        policy_agent = PolicyAgent(gateway, trace)

        order_bundle = OrderEvidenceBundle(
            order={"order_status": "delivered"},
            order_refs=["ev_order_12345678901234567890"],
            order_ids={"ord-split"},
        )
        payment_bundle = PaymentEvidenceBundle(
            payments=[{"payment_value": "50.00"}, {"payment_value": "50.00"}],
            order_payment_refs=["ev_pay_12345678901234567890"],
            timeline_refs=["ev_timeline_12345678901234567890"],
            payment_references={"pay-1", "pay-2"},
        )
        shipment_bundle = ShipmentEvidenceBundle()

        output = await policy_agent.evaluate(
            case_id="L3A_CASE_005",
            order_id="ord-split",
            policy_version="EC_POLICY_V1",
            claims=[
                {"claim_id": "claim-005-a", "topic": "valid_split_payment"},
                {"claim_id": "claim-005-b", "topic": "requested_full_refund"},
            ],
            order_bundle=order_bundle,
            payment_bundle=payment_bundle,
            shipment_bundle=shipment_bundle,
        )

        assert output["assessment"]["primary_issue"] == "valid_split_payment"
        assert output["assessment"]["case_status"] == "no_action"
        assert output["financial_resolution"]["recommended_refund_brl"] == 0.0
        assert len(output["financial_resolution"]["refund_lines"]) == 0
        assert output["claim_assessments"][0]["verdict"] == "supported"
        assert output["claim_assessments"][1]["verdict"] == "unsupported"

    asyncio.run(_run())


def test_policy_agent_evaluates_unsupported_claim() -> None:
    import asyncio

    async def _run() -> None:
        gateway = MagicMock()
        gateway.call = AsyncMock(
            return_value={
                "schema_version": "day09-mcp-evidence-v1",
                "evidence_ref": "ev_policy_evidence_1234567890",
                "result_hash": "sha256:" + "0" * 64,
                "domain": "policy",
                "data": {
                    "currency": "BRL",
                    "rules": {
                        "unsupported_claim": {
                            "case_status": "no_action",
                            "recommended_action": "document_no_action",
                            "refund_brl": 0.0,
                            "responsible_parties": [{"party_type": "customer", "party_id": None}],
                        }
                    },
                },
            }
        )
        trace = MagicMock()
        policy_agent = PolicyAgent(gateway, trace)

        order_bundle = OrderEvidenceBundle(
            order={"order_status": "delivered"},
            order_refs=["ev_order_12345678901234567890"],
            order_ids={"ord-unsupported"},
        )
        payment_bundle = PaymentEvidenceBundle(
            payments=[{"payment_value": "100.00"}],
            order_payment_refs=["ev_pay_12345678901234567890"],
            payment_references={"pay-1"},
        )
        shipment_bundle = ShipmentEvidenceBundle()

        output = await policy_agent.evaluate(
            case_id="L3A_CASE_010",
            order_id="ord-unsupported",
            policy_version="EC_POLICY_V1",
            claims=[
                {"claim_id": "claim-010-a", "topic": "unsupported_claim"},
                {"claim_id": "claim-010-b", "topic": "requested_full_refund"},
            ],
            order_bundle=order_bundle,
            payment_bundle=payment_bundle,
            shipment_bundle=shipment_bundle,
        )

        assert output["assessment"]["primary_issue"] == "unsupported_claim"
        assert output["assessment"]["case_status"] == "no_action"
        assert output["financial_resolution"]["recommended_refund_brl"] == 0.0
        assert output["claim_assessments"][0]["verdict"] == "unsupported"
        assert output["claim_assessments"][1]["verdict"] == "unsupported"

    asyncio.run(_run())


