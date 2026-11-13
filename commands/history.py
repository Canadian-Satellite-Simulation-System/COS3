"""
The log of commands COS3 sent (or tried to send) to COSMOS, newest first.

Kept in memory for the life of the server, capped at LIMIT records. Commands that
never left COS3 (invalid values, hazardous ones awaiting confirmation) aren't recorded.
"""

import itertools
import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

LIMIT = 500


class Status:
    SENT = "sent"  # COSMOS accepted the command and sent it to the flight software
    REJECTED = "rejected"  # COSMOS refused it (e.g. out of range); nothing was sent
    FAILED = "failed"  # COSMOS didn't answer; it may or may not have been sent


class UnknownRecord(LookupError):
    """No history record with that id."""


@dataclass(frozen=True)
class CommandRecord:
    id: int
    time: str  # ISO 8601, UTC
    target: str
    name: str
    path: str  # DEBUG or RADIO
    values: dict  # parameter values as the operator entered them (blank ones left out)
    status: str
    error: str = None
    hazardous_confirmed: bool = False
    resend_of: int = None  # id of the record this one re-sent

    def to_dict(self):
        return asdict(self)


class CommandHistory:
    def __init__(self, limit=LIMIT):
        self._records = deque(maxlen=limit)
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    def add(self, **fields):
        """Record a command. Returns the new CommandRecord."""
        with self._lock:
            record = CommandRecord(id=next(self._ids), time=datetime.now(timezone.utc).isoformat(), **fields)
            self._records.appendleft(record)
        return record

    def list(self):
        """All records, newest first."""
        with self._lock:
            return list(self._records)

    def get(self, record_id):
        with self._lock:
            for record in self._records:
                if record.id == record_id:
                    return record
        raise UnknownRecord(record_id)
