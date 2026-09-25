from __future__ import annotations

import logging
import math
from typing import Any

from ..contracts import Contracts
from ..trace import TraceWriter

logger = logging.getLogger(__name__)


class VerifierAgent:
    """Specialist agent responsible for enforcing verification invariants before case finalization."""

    def __init__(self, contracts: Contracts, trace: TraceWriter) -> None:
        self.contracts = contracts
        self.trace = trace

    def verify(self, draft_output: dict[str, Any], case_id: str) -> dict[str, Any]:
        # Invariant 1: Case ID match
        if draft_output.get("case_id") != case_id:
            raise ValueError(f"Verifier failed: case_id mismatch {draft_output.get('case_id')} != {case_id}")

        # Invariant 2: Financial reconciliation
        fin = draft_output.get("financial_resolution", {})
        rec_refund = float(fin.get("recommended_refund_brl", 0.0))
        lines = fin.get("refund_lines", [])
        line_sum = sum(float(l.get("amount_brl", 0.0)) for l in lines)
        if not math.isclose(rec_refund, line_sum, abs_tol=0.01):
            raise ValueError(
                f"Verifier failed: financial mismatch recommended {rec_refund} != lines sum {line_sum}"
            )

        status = draft_output.get("assessment", {}).get("case_status")
        if status == "no_action" and (rec_refund != 0.0 or len(lines) > 0):
            # Enforce zero refund for no_action
            fin["recommended_refund_brl"] = 0.0
            fin["refund_lines"] = []

        # Invariant 3: Unique resolution actions
        actions = draft_output.get("resolution_actions", [])
        unique_actions = []
        for act in actions:
            if act not in unique_actions:
                unique_actions.append(act)
        draft_output["resolution_actions"] = unique_actions[:8]

        # Invariant 4: Confidence range
        conf = draft_output.get("assessment", {}).get("confidence", 0.95)
        draft_output["assessment"]["confidence"] = max(0.0, min(1.0, float(conf)))
        for ca in draft_output.get("claim_assessments", []):
            c_conf = ca.get("confidence", 0.95)
            ca["confidence"] = max(0.0, min(1.0, float(c_conf)))

        # Invariant 5: Unique evidence refs
        ev_refs = draft_output.get("evidence_refs", [])
        unique_ev = []
        for ref in ev_refs:
            if ref not in unique_ev:
                unique_ev.append(ref)
        draft_output["evidence_refs"] = unique_ev[:30]

        # Invariant 6: JSON Schema compliance check
        self.contracts.validate_output(draft_output, f"verifier_check_{case_id}")

        # Emit verification_completed trace event
        self.trace.emit(
            case_id=case_id,
            event_type="verification_completed",
            actor="verifier",
            decision_code="verification_passed",
            evidence_refs=draft_output["evidence_refs"][:20],
        )

        return draft_output
