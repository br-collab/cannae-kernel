"""Typed identifiers: a type prefix plus a ULID (Universally Unique Lexicographically Sortable
Identifier), for example ``obl_01J9Z3K4M5N6P7Q8R9S0T1V2W3``.

Each identifier type is a distinct ``str`` subclass, so a type checker catches an
``ObligationId`` passed where a ``LifecycleId`` belongs, and construction rejects a value
carrying the wrong prefix at runtime. The ULID part is the canonical form: 26 upper-case
Crockford base-32 characters.

The ``new_*`` factories never read the system clock or an entropy source themselves. The
caller injects both, which keeps library code deterministic and tests replayable.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

__all__ = [
    "ActorId",
    "AllocationId",
    "Clock",
    "EntropySource",
    "EventId",
    "ExecutionId",
    "HaltId",
    "IntentId",
    "LifecycleId",
    "ObligationId",
    "OrderId",
    "ScenarioId",
    "encode_ulid",
    "new_actor_id",
    "new_allocation_id",
    "new_event_id",
    "new_execution_id",
    "new_halt_id",
    "new_intent_id",
    "new_lifecycle_id",
    "new_obligation_id",
    "new_order_id",
    "new_scenario_id",
]

Clock = Callable[[], datetime]
"""Returns the current time as a timezone-aware datetime."""

EntropySource = Callable[[int], bytes]
"""Returns exactly ``n`` random bytes (for example ``os.urandom``)."""

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26
_TIMESTAMP_BITS = 48
_RANDOM_BYTES = 10
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def encode_ulid(timestamp_ms: int, randomness: bytes) -> str:
    """Encode a 48-bit millisecond timestamp and 80 random bits as a canonical ULID string."""
    if not 0 <= timestamp_ms < 1 << _TIMESTAMP_BITS:
        raise ValueError("ULID timestamp must fit in 48 bits of milliseconds since 1970")
    if len(randomness) != _RANDOM_BYTES:
        raise ValueError(f"ULID randomness must be exactly {_RANDOM_BYTES} bytes")
    value = (timestamp_ms << 80) | int.from_bytes(randomness, "big")
    chars = []
    for _ in range(_ULID_LENGTH):
        value, index = divmod(value, 32)
        chars.append(_CROCKFORD[index])
    return "".join(reversed(chars))


def _is_canonical_ulid(text: str) -> bool:
    # The first character carries only 3 bits; anything above "7" overflows 128 bits.
    return len(text) == _ULID_LENGTH and all(c in _CROCKFORD for c in text) and text[0] <= "7"


class _TypedId(str):
    prefix: ClassVar[str]

    def __new__(cls, value: str) -> Self:
        if not isinstance(value, str):
            raise TypeError(f"{cls.__name__} must be built from a str")
        if not value.startswith(cls.prefix):
            raise ValueError(f"{cls.__name__} must start with {cls.prefix!r}: {value!r}")
        if not _is_canonical_ulid(value[len(cls.prefix) :]):
            raise ValueError(
                f"{cls.__name__} must be {cls.prefix!r} followed by a canonical upper-case "
                f"ULID: {value!r}"
            )
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(strict=True),
            serialization=core_schema.to_string_ser_schema(),
        )

    @classmethod
    def new(cls, *, clock: Clock, entropy: EntropySource) -> Self:
        now = clock()
        if now.tzinfo is None:
            raise ValueError("clock must return a timezone-aware datetime")
        timestamp_ms = (now - _EPOCH) // timedelta(milliseconds=1)
        return cls(cls.prefix + encode_ulid(timestamp_ms, entropy(_RANDOM_BYTES)))


class LifecycleId(_TypedId):
    prefix = "lc_"


class ScenarioId(_TypedId):
    prefix = "scn_"


class IntentId(_TypedId):
    prefix = "int_"


class OrderId(_TypedId):
    prefix = "ord_"


class ExecutionId(_TypedId):
    prefix = "exe_"


class AllocationId(_TypedId):
    prefix = "alc_"


class ObligationId(_TypedId):
    prefix = "obl_"


class EventId(_TypedId):
    prefix = "evt_"


class ActorId(_TypedId):
    prefix = "act_"


class HaltId(_TypedId):
    prefix = "hlt_"


def new_lifecycle_id(*, clock: Clock, entropy: EntropySource) -> LifecycleId:
    return LifecycleId.new(clock=clock, entropy=entropy)


def new_scenario_id(*, clock: Clock, entropy: EntropySource) -> ScenarioId:
    return ScenarioId.new(clock=clock, entropy=entropy)


def new_intent_id(*, clock: Clock, entropy: EntropySource) -> IntentId:
    return IntentId.new(clock=clock, entropy=entropy)


def new_order_id(*, clock: Clock, entropy: EntropySource) -> OrderId:
    return OrderId.new(clock=clock, entropy=entropy)


def new_execution_id(*, clock: Clock, entropy: EntropySource) -> ExecutionId:
    return ExecutionId.new(clock=clock, entropy=entropy)


def new_allocation_id(*, clock: Clock, entropy: EntropySource) -> AllocationId:
    return AllocationId.new(clock=clock, entropy=entropy)


def new_obligation_id(*, clock: Clock, entropy: EntropySource) -> ObligationId:
    return ObligationId.new(clock=clock, entropy=entropy)


def new_event_id(*, clock: Clock, entropy: EntropySource) -> EventId:
    return EventId.new(clock=clock, entropy=entropy)


def new_actor_id(*, clock: Clock, entropy: EntropySource) -> ActorId:
    return ActorId.new(clock=clock, entropy=entropy)


def new_halt_id(*, clock: Clock, entropy: EntropySource) -> HaltId:
    return HaltId.new(clock=clock, entropy=entropy)
