# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-58 — local unit tests for the Gate G5 index guard decision (no frappe).

Root cause (RT-54): a fresh ``install-app`` marks every patch completed WITHOUT running it, so the
exactly-once indexes were silently absent and a crash-window replay duplicated the Sales Invoice and
its stock movement. The poller must therefore refuse to post whenever either index is missing, and
must never post when it cannot even tell (a read failure is "not ok", never "ok").
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import index_guard as ig


def _present(*available):
	def check(doctype, index):
		return (doctype, index) in available

	return check


_BOTH = (("Sales Invoice", "unique_rt_si_provenance"), ("Posting Log", "unique_rt_posting_idem"))


class TestRequiredIndexes:
	def test_guards_exactly_the_two_gate_g5_constraints(self):
		# Kept in lockstep with patches/sales_invoice_unique_provenance.py + posting_log_unique_idem.py.
		assert set(ig.G5_INDEXES) == set(_BOTH)


class TestEvaluate:
	def test_both_present_allows_posting(self):
		result = ig.evaluate(_present(*_BOTH))
		assert result.ok is True
		assert result.missing == ()

	def test_missing_sales_invoice_index_blocks_posting(self):
		result = ig.evaluate(_present(_BOTH[1]))
		assert result.ok is False
		assert result.missing == ("Sales Invoice.unique_rt_si_provenance",)

	def test_missing_posting_log_index_blocks_posting(self):
		result = ig.evaluate(_present(_BOTH[0]))
		assert result.ok is False
		assert result.missing == ("Posting Log.unique_rt_posting_idem",)

	def test_both_missing_reports_both(self):
		result = ig.evaluate(_present())
		assert result.ok is False
		assert len(result.missing) == 2

	def test_a_read_failure_never_allows_posting(self):
		def boom(doctype, index):
			raise RuntimeError("db unavailable")

		result = ig.evaluate(boom)
		assert result.ok is False
		assert "db unavailable" in (result.error or "")

	@pytest.mark.parametrize("value", [0, None, "", ()])
	def test_falsy_presence_counts_as_missing(self, value):
		result = ig.evaluate(lambda d, i: value)
		assert result.ok is False
