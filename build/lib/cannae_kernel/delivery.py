"""Settlement path vocabulary (Research Charter §19.7; CL-JUM-001 §9)."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ClearingMethod", "DeliveryPattern"]


class DeliveryPattern(StrEnum):
    DVP = "DVP"
    """Delivery versus payment."""
    PVP = "PVP"
    """Payment versus payment."""
    FOP = "FOP"
    """Free of payment."""
    PAYMENT_ONLY = "PAYMENT_ONLY"
    OTHER_CONTINGENT = "OTHER_CONTINGENT"


class ClearingMethod(StrEnum):
    GROSS = "GROSS"
    BILATERAL_NET = "BILATERAL_NET"
    MULTILATERAL_NET = "MULTILATERAL_NET"
    NOVATED_NETTED = "NOVATED_NETTED"
