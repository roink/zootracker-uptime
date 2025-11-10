"""Protocol for email sending - allows swapping implementations in tests."""

from typing import Protocol


class EmailMessage(Protocol):
    """Protocol for an email message."""

    @property
    def subject(self) -> str: ...

    @property
    def to_addr(self) -> str: ...

    @property
    def from_addr(self) -> str: ...

    @property
    def body(self) -> str: ...


class EmailSender(Protocol):
    """Protocol for sending emails - can be mocked in tests."""

    def send_email(
        self,
        *,
        subject: str,
        to_addr: str,
        body: str,
        reply_to: str | None = None,
    ) -> None:
        """Send an email message."""
        ...


# Global instance - will be swapped in tests
_email_sender: EmailSender | None = None


def get_email_sender() -> EmailSender | None:
    """Get the current email sender instance."""
    return _email_sender


def set_email_sender(sender: EmailSender | None) -> None:
    """Set the email sender instance (for tests)."""
    global _email_sender
    _email_sender = sender
