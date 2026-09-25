from __future__ import annotations

from typing import Any

from .agents.coordinator import CoordinatorRouter
from .mcp_gateway import EvidenceGateway
from .trace import TraceWriter


async def solve_case(
    case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
) -> dict[str, Any]:
    """Execute the L3A multi-agent workflow for one case.

    Coordinates OrderAgent, PaymentAgent, ShipmentAgent, PolicyAgent, and VerifierAgent
    to gather authoritative MCP evidence, resolve business policy, and produce verified output.
    """
    coordinator = CoordinatorRouter(gateway, trace, trace.contracts)
    return await coordinator.run(case)
