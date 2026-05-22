"""In-memory message store for admin-to-user communication."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agt.secrets import UserRegistry

MessageType = Literal["info", "warning", "critical"]
MessageChannel = Literal["banner", "email", "both"]
Recipients = list[str] | Literal["all"]


@dataclass(slots=True)
class Message:
    id: str
    type: MessageType
    text: str
    recipients: Recipients
    channel: MessageChannel
    created_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class _PendingEntry:
    message_id: str
    dismissed: bool = False


class MessageStore:
    def __init__(self) -> None:
        self._messages: dict[str, Message] = {}
        self._pending: dict[str, list[_PendingEntry]] = {}  # slug -> entries

    def create(
        self,
        *,
        type: MessageType,
        text: str,
        recipients: Recipients,
        channel: MessageChannel,
    ) -> Message:
        msg = Message(
            id=str(uuid.uuid4()),
            type=type,
            text=text,
            recipients=recipients,
            channel=channel,
        )
        self._messages[msg.id] = msg
        return msg

    def get_pending(self, slug: str) -> list[Message]:
        entries = self._pending.get(slug, [])
        result: list[Message] = []
        for entry in entries:
            if not entry.dismissed and entry.message_id in self._messages:
                result.append(self._messages[entry.message_id])
        for msg in self._messages.values():
            already = any(e.message_id == msg.id for e in entries)
            if not already and (msg.recipients == "all" or slug in msg.recipients):
                result.append(msg)
        return result

    def dismiss(self, slug: str, message_id: str) -> bool:
        msg = self._messages.get(message_id)
        if msg is None:
            return False
        if msg.recipients != "all" and slug not in msg.recipients:
            return False
        entries = self._pending.setdefault(slug, [])
        for entry in entries:
            if entry.message_id == message_id:
                entry.dismissed = True
                return True
        entries.append(_PendingEntry(message_id=message_id, dismissed=True))
        return True

    def list_all(self) -> list[Message]:
        return list(self._messages.values())


async def dispatch_message_emails(
    msg: Message,
    registry: UserRegistry,
    *,
    api_key: str,
    from_address: str,
) -> None:
    """Send email for a message with channel 'email' or 'both'."""
    if msg.channel not in ("email", "both"):
        return

    import structlog  # noqa: PLC0415

    from agt.email import send_email  # noqa: PLC0415

    log = structlog.get_logger()
    users = registry.get_all()

    if msg.recipients == "all":
        to_addresses = [e.email for e in users.values() if e.email]
    else:
        to_addresses = [
            users[slug].email for slug in msg.recipients if slug in users and users[slug].email
        ]

    if not to_addresses:
        log.info("email_dispatch_no_recipients", message_id=msg.id)
        return

    subject = f"[SciAgent] {'⚠ ' if msg.type == 'warning' else '🚨 ' if msg.type == 'critical' else ''}Message from admin"
    try:
        await send_email(
            api_key=api_key,
            from_address=from_address,
            to=to_addresses,
            subject=subject,
            text=msg.text,
        )
    except Exception:
        log.exception("email_dispatch_failed", message_id=msg.id)
