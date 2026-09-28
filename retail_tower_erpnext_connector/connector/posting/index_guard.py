# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Gate G5 index guard — the pure "may we post?" decision (RT-58).

Posting is exactly-once only while BOTH composite unique indexes exist:

  - ``unique_rt_si_provenance`` on Sales Invoice ``(rt_source_system, rt_external_id)`` — the
    crash-window dedup (F-002): a second submit of an already-posted sale fails at the DB;
  - ``unique_rt_posting_idem`` on Posting Log ``(source_system, external_id)`` — the connector's own
    replay record.

RT-54 proved they can be silently absent: a fresh ``install-app`` marks every patch completed
without running it, and a crash-window replay then duplicated the Sales Invoice AND (since RT-48)
its stock movement. The poller asks this module before every tick; anything other than "both
present" — including an unreadable schema — means **do not post** (sales stay pending in DP2,
nothing is rejected, lost or duplicated). This module imports NO frappe; the glue supplies the
``index_present(doctype, index_name)`` probe.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

G5_INDEXES: tuple[tuple[str, str], ...] = (
	("Sales Invoice", "unique_rt_si_provenance"),
	("Posting Log", "unique_rt_posting_idem"),
)


@dataclass(frozen=True)
class GuardResult:
	"""``ok`` only when every required index is present; ``missing`` names the absent ones."""

	ok: bool
	missing: tuple[str, ...] = ()
	error: str | None = None


def evaluate(
	index_present: Callable[[str, str], object],
	required: tuple[tuple[str, str], ...] = G5_INDEXES,
) -> GuardResult:
	"""Decide whether posting may proceed. A probe failure is NOT ok (never assume the index exists)."""
	missing: list[str] = []
	for doctype, index in required:
		try:
			present = bool(index_present(doctype, index))
		except Exception as exc:  # an unreadable schema must block posting, not wave it through
			return GuardResult(ok=False, missing=tuple(missing), error=f"{type(exc).__name__}: {exc}"[:300])
		if not present:
			missing.append(f"{doctype}.{index}")
	return GuardResult(ok=not missing, missing=tuple(missing))
