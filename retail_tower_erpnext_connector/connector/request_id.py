# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-39 — the Connector's outbound ``X-Request-Id`` correlation value.

Backend-Core's ``RequestIdInterceptor`` honours an inbound ``X-Request-Id`` ONLY when it is
UUID-shaped (``8-4-4-4-12`` hex, documented there as UUID v4 or v7) and otherwise mints its own,
so a non-UUID value (the former ``frappe.generate_hash(length=16)``) left the Connector and
Backend-Core logging two different ids for the same call. Minting an RFC 4122 UUIDv4 here makes
Backend-Core keep and echo the Connector's id unchanged.

One value is minted per poller tick and reused for every call of that tick (pull, post, ack,
report) and its structured logs. It is a correlation id only — never an ``Idempotency-Key``
(those stay derived from the work-item / requestRef), so idempotency semantics are untouched.

Pure Python (no frappe) so it is unit-testable without a bench.
"""

from __future__ import annotations

import uuid


def new_request_id() -> str:
	"""A fresh UUIDv4 string (lower-case, hyphenated) for the outbound ``X-Request-Id``."""
	return str(uuid.uuid4())
