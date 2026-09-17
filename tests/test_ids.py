from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

from cannae_kernel import ids
from cannae_kernel._model import KernelModel
from cannae_kernel.ids import LifecycleId, ObligationId, encode_ulid
from tests.factories import fixed_clock, seeded_entropy, ulid

ALL_TYPES = [
    (ids.LifecycleId, ids.new_lifecycle_id, "lc_"),
    (ids.ScenarioId, ids.new_scenario_id, "scn_"),
    (ids.IntentId, ids.new_intent_id, "int_"),
    (ids.OrderId, ids.new_order_id, "ord_"),
    (ids.ExecutionId, ids.new_execution_id, "exe_"),
    (ids.AllocationId, ids.new_allocation_id, "alc_"),
    (ids.ObligationId, ids.new_obligation_id, "obl_"),
    (ids.EventId, ids.new_event_id, "evt_"),
    (ids.ActorId, ids.new_actor_id, "act_"),
    (ids.HaltId, ids.new_halt_id, "hlt_"),
]


def test_encode_ulid_matches_the_ulid_specification_example() -> None:
    # github.com/ulid/spec: 01ARZ3NDEK is the timestamp part for 1469922850259 ms.
    assert encode_ulid(1469922850259, bytes(10))[:10] == "01ARZ3NDEK"
    assert encode_ulid(0, bytes(10)) == "0" * 26
    assert encode_ulid((1 << 48) - 1, b"\xff" * 10) == "7" + "Z" * 25


@pytest.mark.parametrize(("ms", "rnd"), [(-1, bytes(10)), (1 << 48, bytes(10)), (0, bytes(9))])
def test_encode_ulid_rejects_out_of_range_input(ms: int, rnd: bytes) -> None:
    with pytest.raises(ValueError):
        encode_ulid(ms, rnd)


@pytest.mark.parametrize(("cls", "factory", "prefix"), ALL_TYPES)
def test_factory_is_deterministic_under_injected_clock_and_entropy(
    cls: type[str], factory: Callable[..., str], prefix: str
) -> None:
    a = factory(clock=fixed_clock(), entropy=seeded_entropy("s"))
    b = factory(clock=fixed_clock(), entropy=seeded_entropy("s"))
    c = factory(clock=fixed_clock(), entropy=seeded_entropy("other"))
    assert a == b != c
    assert type(a) is cls
    assert a.startswith(prefix)


def test_ids_sort_by_clock() -> None:
    early = ids.new_event_id(clock=fixed_clock(), entropy=seeded_entropy("z"))
    later = ids.new_event_id(
        clock=fixed_clock(datetime(2026, 9, 16, 21, 30, tzinfo=UTC) + timedelta(milliseconds=1)),
        entropy=seeded_entropy("a"),
    )
    assert early < later


@pytest.mark.parametrize(("cls", "factory", "prefix"), ALL_TYPES)
def test_wrong_prefix_is_rejected(cls: type[str], factory: object, prefix: str) -> None:
    other = "obl_" if prefix != "obl_" else "lc_"
    with pytest.raises(ValueError, match="must start with"):
        cls(other + ulid(1))


@pytest.mark.parametrize(
    "body",
    [
        ulid(1).lower(),  # lower case is not the canonical form
        ulid(1)[:-1],  # too short
        ulid(1) + "0",  # too long
        "8" + ulid(1)[1:],  # overflows 128 bits
        ulid(1)[:-1] + "U",  # U is not in Crockford base 32
    ],
)
def test_non_canonical_ulid_is_rejected(body: str) -> None:
    with pytest.raises(ValueError, match="canonical"):
        LifecycleId("lc_" + body)


def test_non_string_is_rejected() -> None:
    with pytest.raises(TypeError):
        LifecycleId(123)  # type: ignore[arg-type]


def test_naive_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ids.new_order_id(clock=lambda: datetime(2026, 1, 1), entropy=seeded_entropy("s"))


def test_aware_non_utc_clock_gives_the_same_instant() -> None:
    utc = datetime(2026, 1, 1, 12, tzinfo=UTC)
    plus2 = utc.astimezone(timezone(timedelta(hours=2)))
    a = ids.new_order_id(clock=lambda: utc, entropy=seeded_entropy("s"))
    b = ids.new_order_id(clock=lambda: plus2, entropy=seeded_entropy("s"))
    assert a == b


def test_short_entropy_is_rejected() -> None:
    with pytest.raises(ValueError, match="exactly 10 bytes"):
        ids.new_order_id(clock=fixed_clock(), entropy=lambda n: b"x")


class _Holder(KernelModel):
    lifecycle_id: LifecycleId


def test_model_field_rejects_another_id_type_and_restores_type_from_json() -> None:
    obl = ObligationId("obl_" + ulid(1))
    with pytest.raises(ValidationError):
        _Holder(lifecycle_id=obl)  # type: ignore[arg-type]
    held = _Holder.model_validate_json('{"lifecycle_id": "lc_' + ulid(1) + '"}')
    assert type(held.lifecycle_id) is LifecycleId
    assert isinstance(held, BaseModel)
