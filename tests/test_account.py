from datetime import UTC, datetime

from cannae_kernel.account import AccountStatus, AccountStatusDocument, AccountStatusEntry


def test_account_status_document_is_strict_and_synthetic() -> None:
    document = AccountStatusDocument(
        as_of=datetime(2026, 11, 7, tzinfo=UTC),
        maximum_age_seconds=300,
        accounts=(
            AccountStatusEntry(
                account_id="SYN-ACCOUNT-001",
                status=AccountStatus.APPLIED,
                last_event_id="SYN-EVENT-001",
            ),
        ),
    )
    assert document.synthetic is True
    assert document.accounts[0].status is AccountStatus.APPLIED
