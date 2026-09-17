"""Base model and the constrained scalar types every kernel model shares."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    StringConstraints,
)
from pydantic_core import CoreSchema, core_schema


class KernelModel(BaseModel):
    """Frozen, closed and strict: no mutation, no unknown fields, no type coercion."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)


def _require_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("datetime must be timezone-aware UTC")
    return value


def _finite(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("Decimal must be finite")
    return value


def _decimal_from_json_string(value: str) -> Decimal:
    try:
        return _finite(Decimal(value))
    except InvalidOperation:
        raise ValueError(f"not a decimal string: {value!r}") from None


class _StrictDecimal:
    """Schema for ``KernelDecimal``.

    Pydantic's strict mode still accepts a JSON number for a ``Decimal``, and a JSON number is
    parsed as a binary float that may already have lost the exact value. So JSON input must be
    a decimal string, Python input must be a ``Decimal``, and a float is refused either way.
    """

    def __get_pydantic_core_schema__(
        self, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_after_validator_function(
                _decimal_from_json_string, core_schema.str_schema(strict=True)
            ),
            python_schema=core_schema.no_info_after_validator_function(
                _finite, core_schema.is_instance_schema(Decimal)
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda d: format(d, "f"), when_used="json"
            ),
        )


UtcDatetime = Annotated[datetime, AfterValidator(_require_utc)]
"""A timezone-aware datetime whose offset is zero."""

KernelDecimal = Annotated[Decimal, _StrictDecimal()]
"""A finite Decimal that was never a binary float: a decimal string in JSON."""

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

MAX_SAFE_INTEGER = 2**53 - 1
"""The largest integer every JSON consumer (including JavaScript) represents exactly."""

SafeInt = Annotated[int, Field(ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER)]
"""An integer ``canonical_bytes`` can serialize (JUM-D-24)."""

# Separate types rather than ``SafeInt`` plus ``Field(ge=...)`` on the field: Pydantic keeps
# only one lower bound when the two are combined, and a dropped bound fails silently.
NonNegativeSafeInt = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
PositiveSafeInt = Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]
