from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrderEvidenceBundle:
    order: dict[str, Any] | None = None
    items: list[dict[str, Any]] = field(default_factory=list)
    sellers: list[dict[str, Any]] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    order_refs: list[str] = field(default_factory=list)
    item_refs: list[str] = field(default_factory=list)
    seller_refs: list[str] = field(default_factory=list)
    order_ids: set[str] = field(default_factory=set)
    item_ids: set[str] = field(default_factory=set)
    seller_ids: set[str] = field(default_factory=set)


@dataclass
class PaymentEvidenceBundle:
    payments: list[dict[str, Any]] = field(default_factory=list)
    payment_timeline: dict[str, Any] | None = None
    refund_timeline: dict[str, Any] | None = None
    evidence_refs: list[str] = field(default_factory=list)
    order_payment_refs: list[str] = field(default_factory=list)
    timeline_refs: list[str] = field(default_factory=list)
    refund_refs: list[str] = field(default_factory=list)
    payment_references: set[str] = field(default_factory=set)


@dataclass
class ShipmentEvidenceBundle:
    shipment: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    shipment_refs: list[str] = field(default_factory=list)
    shipment_ids: set[str] = field(default_factory=set)


@dataclass
class PolicyEvidenceBundle:
    policy: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)

