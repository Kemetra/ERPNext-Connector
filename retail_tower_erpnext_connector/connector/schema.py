# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Gate G5 schema invariants — ensured on install AND every migrate (RT-58). ⏳ BENCH-VALIDATION.

Root cause (RT-54): Frappe's ``install_app`` marks every ``patches.txt`` entry completed WITHOUT
running it (``frappe.installer.set_all_patches_as_completed``). The two exactly-once indexes were
created only inside patches, so every FRESH install silently lacked them. The patches stay for the
upgrade path; this module makes the invariant hold everywhere:

  - ``after_install`` / ``after_migrate`` hooks (``hooks.py``) call :func:`ensure_g5_indexes`;
  - the Posting Log controller's ``on_doctype_update`` also ensures its own index on DocType sync
    (ERPNext's pattern: ``erpnext/stock/doctype/bin/bin.py`` ``on_doctype_update`` → ``add_unique``).

Both ensure steps are idempotent. If an index cannot be created — e.g. duplicate provenance rows
already exist — they FAIL LOUD (the migrate errors) instead of recording silent success; the
poller's runtime guard (``posting.index_guard``) keeps posting paused until it is fixed.
"""

from __future__ import annotations

import frappe

POSTING_LOG_INDEX = "unique_rt_posting_idem"
SALES_INVOICE_INDEX = "unique_rt_si_provenance"


class G5IndexError(RuntimeError):
	"""A Gate G5 unique index could not be created (fail-closed; posting stays paused)."""


def index_present(doctype: str, index_name: str) -> bool:
	"""True if ``tab<doctype>`` carries an index named ``index_name`` (the guard's probe)."""
	return bool(frappe.db.sql(f"SHOW INDEX FROM `tab{doctype}` WHERE Key_name = %s", (index_name,)))


def ensure_posting_log_index() -> None:
	"""Idempotently add ``unique_rt_posting_idem`` on Posting Log ``(source_system, external_id)``."""
	_ensure(
		"Posting Log",
		POSTING_LOG_INDEX,
		lambda: frappe.db.add_unique(
			"Posting Log", ["source_system", "external_id"], constraint_name=POSTING_LOG_INDEX
		),
	)


def ensure_sales_invoice_index() -> None:
	"""Idempotently ensure the provenance Custom Fields and ``unique_rt_si_provenance`` on Sales Invoice.

	Reuses the existing patch logic (it owns its column prerequisite and fails loud if the columns
	cannot be created), so there is one definition of the index for both install and upgrade paths.
	"""
	from retail_tower_erpnext_connector.patches import sales_invoice_unique_provenance

	_ensure("Sales Invoice", SALES_INVOICE_INDEX, sales_invoice_unique_provenance.execute)


def ensure_g5_indexes() -> None:
	"""Ensure both Gate G5 indexes (install + every migrate)."""
	ensure_posting_log_index()
	ensure_sales_invoice_index()


def after_install() -> None:
	ensure_g5_indexes()


def after_migrate() -> None:
	ensure_g5_indexes()


def _ensure(doctype: str, index_name: str, create) -> None:
	if index_present(doctype, index_name):
		return
	try:
		create()
	except Exception as exc:
		raise G5IndexError(
			f"Gate G5: could not create {index_name} on {doctype} ({type(exc).__name__}: {exc}). "
			"Duplicate provenance rows may exist; see docs/runbooks/staging-install.md. "
			"Posting stays paused until this index exists."
		) from exc
	if not index_present(doctype, index_name):
		raise G5IndexError(f"Gate G5: {index_name} on {doctype} still absent after creation")
