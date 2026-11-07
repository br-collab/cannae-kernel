"""Cross-repository account status vocabulary and attested document shape."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from cannae_kernel._model import KernelModel, NonEmptyStr, PositiveSafeInt, UtcDatetime


class AccountStatus(StrEnum):
    APPLIED = "APPLIED"
    APPROVED = "APPROVED"
    RESTRICTED = "RESTRICTED"
    FUNDED = "FUNDED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class AccountStatusEntry(KernelModel):
    account_id: NonEmptyStr
    status: AccountStatus
    last_event_id: NonEmptyStr


class AccountStatusDocument(KernelModel):
    schema_version: Literal["cannae.account_status/1"] = "cannae.account_status/1"
    as_of: UtcDatetime
    maximum_age_seconds: PositiveSafeInt
    synthetic: Literal[True] = True
    accounts: tuple[AccountStatusEntry, ...] = Field(min_length=1)


class AttestedAccountStatusDocument(KernelModel):
    schema_version: Literal["cannae.attested_account_status/1"] = (
        "cannae.attested_account_status/1"
    )
    payload_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    payload: NonEmptyStr
