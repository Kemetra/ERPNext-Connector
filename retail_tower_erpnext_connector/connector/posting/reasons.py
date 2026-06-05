# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Internal failure → 012 RejectionReason mapper + message hygiene (T050/T052).

The connector's internal failure kinds are mapped onto DP2's **closed**
``RejectionReason.category`` set (``validation | closed_period | unmapped_item |
unmapped_account | other``) — NO new wire reason is invented (FR-007). An unrecognised
failure kind RAISES rather than silently defaulting to ``other`` (Principle VI: never hide).

Per the posting decision table (resolution-concepts.md §3):
  - closed period at submit        → ``closed_period`` (row 4)
  - ERPNext validation failure     → ``validation``    (row 5)
  - unmapped unit (no UOM)         → ``validation``    (row 5 — there is NO ``unmapped_uom``)
  - unmapped ERPNext account       → ``unmapped_account`` (row 6)
  - disabled/non-sales Item submit → ``validation``    (row 7 — the Item IS mapped)
  - missing erpnextItemRef (R2)    → ``validation``    (row 8 — upstream contract violation)
  - other non-retryable error      → ``other``         (row 9)

Failure messages are scrubbed of secret/token/credential substrings before they leave the
process (Principle V / Gate G4). This module imports NO frappe.
"""

from __future__ import annotations

import enum
import re

from .contracts import RejectionReason


class FailureKind(enum.Enum):
    """Connector-internal, non-retryable failure kinds (mapped to the 012 closed set)."""

    CLOSED_PERIOD = "closed_period"
    VALIDATION = "validation"
    UNMAPPED_UNIT = "unmapped_unit"
    UNMAPPED_ACCOUNT = "unmapped_account"
    MISSING_ITEM_REF = "missing_item_ref"
    DISABLED_ITEM = "disabled_item"
    OTHER = "other"


class UnmappedFailureKind(Exception):
    """A failure kind not recognised by the mapper — raised, never silently bucketed."""


# Internal kind → 012 closed category. Every FailureKind appears exactly once.
_CATEGORY_BY_KIND: dict[FailureKind, str] = {
    FailureKind.CLOSED_PERIOD: "closed_period",
    FailureKind.VALIDATION: "validation",
    FailureKind.UNMAPPED_UNIT: "validation",  # no `unmapped_uom` in the 012 set
    FailureKind.UNMAPPED_ACCOUNT: "unmapped_account",
    FailureKind.MISSING_ITEM_REF: "validation",  # upstream contract violation (R2)
    FailureKind.DISABLED_ITEM: "validation",  # the Item is mapped; submit-validation failure
    FailureKind.OTHER: "other",
}

# Patterns whose VALUE is redacted from outgoing messages (token-like / credential-bearing).
# Covers `key=value`, `key: value`, and quoted/JSON forms (`"key": "value"`) since frappe
# often serializes exceptions as dicts/JSON (F-008), plus sk- and sk_ token prefixes.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+\S+"),
    re.compile(
        r"""(?i)["']?\b(token|password|secret|api[_-]?key|authorization)\b["']?"""
        r"""\s*[=:]\s*["']?[^\s"',}]+["']?"""
    ),
    re.compile(r"\bsk[-_][A-Za-z0-9_\-]{6,}"),
)


def scrub_message(message: str) -> str:
    """Redact secret/token/credential substrings from a human-readable failure message."""
    scrubbed = message
    for pattern in _SECRET_PATTERNS:
        scrubbed = pattern.sub("[redacted]", scrubbed)
    return scrubbed


def to_rejection_reason(kind: FailureKind, *, message: str) -> RejectionReason:
    """Build a 012 ``RejectionReason`` for a non-retryable failure.

    Raises :class:`UnmappedFailureKind` for an unrecognised kind (never invents a category).
    The message is scrubbed of secrets (Gate G4).
    """
    if not isinstance(kind, FailureKind) or kind not in _CATEGORY_BY_KIND:
        raise UnmappedFailureKind(f"no 012 category for failure kind {kind!r} (FR-007)")
    return RejectionReason(category=_CATEGORY_BY_KIND[kind], message=scrub_message(message))
