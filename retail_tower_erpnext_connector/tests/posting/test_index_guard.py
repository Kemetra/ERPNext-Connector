# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""RT-58 — local unit tests for the Gate G5 index guard decision (no frappe).

Root cause (RT-54): a fresh ``install-app`` marks every patch completed WITHOUT running it, so the
exactly-once indexes were silently absent and a crash-window replay duplicated the Sales Invoice and
its stock movement. The poller must therefore refuse to post whenever either index is missing OR is
not the exact unique constraint (Codex P1, PR #43: a same-named non-unique / wrong-column index must
not pass), and must never post when it cannot even tell (a read failure is "not ok").
"""

import pytest

from retail_tower_erpnext_connector.connector.posting import index_guard as ig

_SI = ("Sales Invoice", "unique_rt_si_provenance", ("rt_source_system", "rt_external_id"))
_PL = ("Posting Log", "unique_rt_posting_idem", ("source_system", "external_id"))


def _present(*available):
	def check(doctype, index, columns):
		return (doctype, index, columns) in available

	return check


def _rows(columns, *, non_unique=0):
	# Shaped like frappe.db.sql("SHOW INDEX ...", as_dict=True) rows for one key.
	return [
		{"Key_name": "k", "Non_unique": non_unique, "Seq_in_index": i, "Column_name": c}
		for i, c in enumerate(columns, start=1)
	]


class TestRequiredIndexes:
	def test_guards_exactly_the_two_gate_g5_constraints(self):
		# Kept in lockstep with patches/sales_invoice_unique_provenance.py + posting_log_unique_idem.py.
		assert set(ig.G5_INDEXES) == {_SI, _PL}


class TestIndexMatches:
	def test_exact_unique_definition_matches(self):
		assert ig.index_matches(_rows(_SI[2]), _SI[2]) is True

	def test_rows_out_of_order_still_match_by_sequence(self):
		assert ig.index_matches(list(reversed(_rows(_SI[2]))), _SI[2]) is True

	def test_absent_index_does_not_match(self):
		assert ig.index_matches([], _SI[2]) is False

	def test_non_unique_index_with_the_right_name_does_not_match(self):
		assert ig.index_matches(_rows(_SI[2], non_unique=1), _SI[2]) is False

	def test_wrong_columns_do_not_match(self):
		assert ig.index_matches(_rows(("rt_source_system",)), _SI[2]) is False

	def test_prefix_unique_index_does_not_match(self):
		# Codex P2 (PR #43): a UNIQUE prefix index (col(20), col(20)) would make distinct valid ids that
		# share a prefix collide. Only full-column indexes (Sub_part NULL) count.
		rows = [{**r, "Sub_part": 20} for r in _rows(_SI[2])]
		assert ig.index_matches(rows, _SI[2]) is False

	def test_full_column_rows_with_explicit_null_sub_part_match(self):
		rows = [{**r, "Sub_part": None} for r in _rows(_SI[2])]
		assert ig.index_matches(rows, _SI[2]) is True

	def test_wrong_column_order_does_not_match(self):
		assert ig.index_matches(_rows(tuple(reversed(_SI[2]))), _SI[2]) is False


class TestEvaluate:
	def test_both_present_allows_posting(self):
		result = ig.evaluate(_present(_SI, _PL))
		assert result.ok is True
		assert result.missing == ()

	def test_missing_sales_invoice_index_blocks_posting(self):
		result = ig.evaluate(_present(_PL))
		assert result.ok is False
		assert result.missing == ("Sales Invoice.unique_rt_si_provenance",)

	def test_missing_posting_log_index_blocks_posting(self):
		result = ig.evaluate(_present(_SI))
		assert result.ok is False
		assert result.missing == ("Posting Log.unique_rt_posting_idem",)

	def test_both_missing_reports_both(self):
		result = ig.evaluate(_present())
		assert result.ok is False
		assert len(result.missing) == 2

	def test_a_read_failure_never_allows_posting(self):
		def boom(doctype, index, columns):
			raise RuntimeError("db unavailable")

		result = ig.evaluate(boom)
		assert result.ok is False
		assert "db unavailable" in (result.error or "")

	@pytest.mark.parametrize("value", [0, None, "", ()])
	def test_falsy_presence_counts_as_missing(self, value):
		result = ig.evaluate(lambda d, i, c: value)
		assert result.ok is False
