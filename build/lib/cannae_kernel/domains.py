"""The domains that produce events and that a halt can cover."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Domain"]


class Domain(StrEnum):
    AUREON = "AUREON"
    """Pre-trade: governed, approved intent."""

    LC = "LC"
    """Legiones Cannenses: the synthetic middle layer."""

    ATREIDES = "ATREIDES"
    """Post-trade: settlement, finality, reconciliation."""

    C2 = "C2"
    """The Cannae Legion top-level command and control harness."""

    EMULATOR = "EMULATOR"
    """An external-system emulator: venue, clearing house, rail."""
