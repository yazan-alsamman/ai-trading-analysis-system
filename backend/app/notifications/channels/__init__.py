"""Channel senders and their error model.

- :class:`RateLimited`: the provider asked us to wait (``retry_after`` seconds); retried, does
  not count toward the circuit breaker.
- :class:`TransientError`: timeouts, connection errors, 5xx; retried with backoff and counted
  by the circuit breaker.
- :class:`PermanentError`: retrying cannot help (blocked bot, invalid token, rejected
  recipient). ``action`` tells the caller what to clean up (``unlink`` / ``delete_device``).

Error messages are built by us from status codes and provider descriptions, never from
exception strings that may contain a URL with a secret (the Telegram token is in the path).
"""

from __future__ import annotations

from app.core.config import get_settings

MAX_ERROR = 280


class ChannelError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(scrub(message)[:MAX_ERROR])

    @property
    def message(self) -> str:
        return str(self)


class TransientError(ChannelError):
    pass


class RateLimited(ChannelError):
    def __init__(self, message: str, retry_after: float) -> None:
        super().__init__(message)
        self.retry_after = max(1.0, float(retry_after))


class PermanentError(ChannelError):
    def __init__(self, message: str, action: str | None = None) -> None:
        super().__init__(message)
        self.action = action  # "unlink" | "delete_device" | None


def scrub(message: str) -> str:
    """Remove configured secrets from a message (defence in depth)."""
    settings = get_settings()
    for secret in (settings.telegram_bot_token, settings.smtp_password):
        if secret:
            message = message.replace(secret, "***")
    return message


def enabled_channels() -> dict[str, bool]:
    """Whether each external channel is configured on this server."""
    from app.notifications.channels import email, push, telegram

    return {
        "telegram": telegram.enabled(),
        "email": email.enabled(),
        "push": push.enabled(),
    }
