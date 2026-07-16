"""Dev-mode email delivery.

No real email provider is configured yet. Instead of sending mail, outgoing
messages are logged and kept in a capped in-memory outbox per recipient so the
frontend can retrieve them during local development (see the
``/auth/dev-outbox`` route, which is disabled outside development/test).

To swap in a real provider later, replace the body of ``send_email`` with a
call to that provider's API/SMTP client; callers do not need to change.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime

logger = logging.getLogger("pathly.mailer")

_MAX_MESSAGES_PER_RECIPIENT = 5
_outbox: dict[str, list[dict[str, str]]] = defaultdict(list)


def send_email(to: str, subject: str, body: str) -> None:
    recipient = to.strip().lower()
    logger.info("dev-mode email to %s: %s\n%s", recipient, subject, body)
    messages = _outbox[recipient]
    messages.append({"subject": subject, "body": body, "sent_at": datetime.now(UTC).isoformat()})
    del messages[:-_MAX_MESSAGES_PER_RECIPIENT]


def get_outbox(to: str) -> list[dict[str, str]]:
    return list(_outbox.get(to.strip().lower(), []))
