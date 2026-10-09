# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt
"""RT-331 — the real glue consumes the frozen resolution (Backend-Core RT-332), no bench.

* A fresh post uses the feed's ``sale.warehouseRef`` (the frozen warehouse) instead of the local
  warehouse map, and echoes ``resolutionVersion`` on the ``posted`` ack.
* A replay-guard hit verifies the EXISTING invoice against the frozen resolution before acking:
  a match acks ``posted`` (echoing the version); a mismatch acks ``reconciliation_required`` with
  the existing ``documentRef``; an unreadable invoice acks ``failed_transient`` (never a blind
  ``posted``).
* A work item without ``resolutionVersion`` (older Backend-Core) behaves exactly as before: the
  replay echoes ``posted`` without reading the invoice.

``frappe_glue`` imports frappe, so it is loaded against a minimal stand-in (the RT-71 / RT-78 /
RT-171 pattern).
"""

import importlib
import sys
import types
from decimal import Decimal

import pytest

from retail_tower_erpnext_connector.connector.posting import contracts as c
from retail_tower_erpnext_connector.connector.posting.tender import TenderModeMap
from retail_tower_erpnext_connector.connector.posting.uom import (
	PreResolvedWarehouse,
	StoreCustomerMap,
	UomMap,
)

_GLUE = "retail_tower_erpnext_connector.connector.posting.frappe_glue"
_PKG = "retail_tower_erpnext_connector.connector.posting"
_MISSING = object()
_STORE = "33333333-3333-4333-8333-333333333333"
_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_REF = "18181818-1818-4181-8181-181818181818"
_EXISTING = c.ErpnextDocumentRef(doctype="Sales Invoice", name="ACC-SINV-2026-18000")


class _Logger:
	def __init__(self):
		self.records = []

	def info(self, record):
		self.records.append(record)

	warning = error = info


class _Invoice:
	def __init__(self, payload, fake):
		self.payload, self._fake, self.name = payload, fake, "ACC-SINV-2026-18999"

	def insert(self):
		grand = sum(Decimal(i["amount"]) for i in self.payload["items"])
		self.values = {
			"grand_total": float(grand),
			"paid_amount": 0.0,
			"change_amount": 0.0,
			"write_off_amount": 0.0,
			"outstanding_amount": float(grand),
		}

	def get(self, field):
		return self.values.get(field)

	def submit(self):
		self._fake.events.append("submit")


class _Frappe(types.ModuleType):
	"""``invoice`` is what the EXISTING Sales Invoice holds: docstatus + item rows."""

	def __init__(self, *, docstatus=1, items=(), unreadable=False):
		super().__init__("frappe")
		self.ValidationError = type("ValidationError", (Exception,), {})
		self.exceptions = types.SimpleNamespace(
			UniqueValidationError=type("UniqueValidationError", (self.ValidationError,), {})
		)
		self._logger = _Logger()
		self.logger = lambda name=None: self._logger
		self.events, self.payloads, self.reads = [], [], []
		self.docstatus, self.items, self.unreadable = docstatus, list(items), unreadable
		self.db = types.SimpleNamespace(
			get_value=self._get_value,
			savepoint=lambda name: None,
			rollback=lambda save_point=None: None,
		)
		self.utils = types.SimpleNamespace(get_system_timezone=lambda: "UTC")

	def _get_value(self, doctype, filters, fields=None, **_):
		if isinstance(filters, dict):
			return None  # no provenance hit for a fresh post
		self._read(filters)
		return self.docstatus

	def _read(self, name):
		self.reads.append(name)
		if self.unreadable:
			raise TimeoutError("Lock wait timeout exceeded")

	def get_all(self, doctype, **kwargs):
		if doctype == "Sales Invoice Item":
			self._read(kwargs["filters"]["parent"])
			return [dict(row) for row in self.items]
		return []

	def get_doc(self, payload):
		self.payloads.append(payload)
		return _Invoice(payload, self)


class _Client:
	def __init__(self):
		self.acks = []

	def ack_outcome(self, ref, request, idempotency_key):
		self.acks.append({"ack": request.to_wire(), "key": idempotency_key})


class _Store:
	def __init__(self, existing=None):
		self.existing, self.writes = existing, []

	def get_document_ref(self, key):
		return self.existing

	def record_posted(self, key, ref):
		self.writes.append((key, ref))


@pytest.fixture
def load_glue():
	pkg = importlib.import_module(_PKG)
	saved = [
		(sys.modules, "frappe", sys.modules.get("frappe", _MISSING)),
		(sys.modules, _GLUE, sys.modules.get(_GLUE, _MISSING)),
		(vars(pkg), "frappe_glue", vars(pkg).get("frappe_glue", _MISSING)),
	]

	def _load(fake):
		sys.modules["frappe"] = fake
		sys.modules.pop(_GLUE, None)
		return importlib.import_module(_GLUE)

	yield _load
	for namespace, name, value in saved:
		namespace.pop(name, None)
		if value is not _MISSING:
			namespace[name] = value


def _work_item(*, version=2, warehouse="Frozen WH"):
	sale = {
		"saleRef": "22222222-2222-4222-8222-222222222222",
		"storeId": _STORE,
		"currencyCode": "EGP",
		"posTotal": "100.00",
		"occurredAt": "2026-06-01T10:00:00Z",
		"businessDate": "2026-06-01",
		"sourceSystem": "pos-pulse",
		"externalId": "POS-18101",
		"lines": [
			{
				"lineRef": _A,
				"lineName": "Item A",
				"unitPrice": "100.00",
				"currencyCode": "EGP",
				"quantity": "1",
				"lineAmount": "100.00",
				"unit": "each",
				"erpnextItemRef": {"doctype": "Item", "name": "ITEM-A"},
			}
		],
	}
	if warehouse is not None:
		sale["warehouseRef"] = {"doctype": "Warehouse", "name": warehouse}
	wire = {
		"workItemRef": _REF,
		"kind": "sale_post",
		"sourceSystem": "pos-pulse",
		"externalId": "POS-18101",
		"payloadHash": "a" * 64,
		"businessDate": "2026-06-01",
		"itemCursor": "9",
		"sale": sale,
	}
	if version is not None:
		wire["resolutionVersion"] = version
	return c.PostingWorkItem.from_wire(wire)


def _post(glue, work_item, store):
	client = _Client()
	outcome = glue.post_work_item(
		work_item,
		client=client,
		store=store,
		uom_map=UomMap({"each": "Nos"}),
		warehouses=PreResolvedWarehouse({_STORE: {"doctype": "Warehouse", "name": "Map WH"}}),
		customers=StoreCustomerMap({_STORE: "Walk-in"}),
		tenders=TenderModeMap({"cash": "Cash"}),
		correlation_id="rt331-test",
	)
	return outcome, client


class TestFreshPost:
	def test_uses_the_frozen_warehouse_and_echoes_the_version(self, load_glue):
		fake = _Frappe()
		glue = load_glue(fake)
		outcome, client = _post(glue, _work_item(), _Store())
		assert outcome == "posted"
		assert {item["warehouse"] for item in fake.payloads[0]["items"]} == {"Frozen WH"}
		assert client.acks[0]["ack"]["outcome"] == "posted"
		assert client.acks[0]["ack"]["resolutionVersion"] == 2

	def test_without_a_frozen_warehouse_the_local_map_applies(self, load_glue):
		fake = _Frappe()
		glue = load_glue(fake)
		_post(glue, _work_item(warehouse=None), _Store())
		assert {item["warehouse"] for item in fake.payloads[0]["items"]} == {"Map WH"}


class TestReplayVerification:
	def test_a_matching_existing_invoice_acks_posted_with_the_version(self, load_glue):
		fake = _Frappe(items=[{"item_code": "ITEM-A", "warehouse": "Frozen WH", "rt_line_ref": _A}])
		glue = load_glue(fake)
		outcome, client = _post(glue, _work_item(), _Store(existing=_EXISTING))
		assert outcome == "posted"
		assert client.acks == [
			{
				"ack": {
					"outcome": "posted",
					"documentRef": {"doctype": "Sales Invoice", "name": "ACC-SINV-2026-18000"},
					"resolutionVersion": 2,
				},
				"key": f"{_REF}:posted",
			}
		]

	def test_a_mismatching_existing_invoice_acks_reconciliation_required(self, load_glue):
		fake = _Frappe(items=[{"item_code": "ITEM-OTHER", "warehouse": "Frozen WH", "rt_line_ref": _A}])
		glue = load_glue(fake)
		outcome, client = _post(glue, _work_item(), _Store(existing=_EXISTING))
		assert outcome == "reconciliation_required"
		ack = client.acks[0]
		assert ack["key"] == f"{_REF}:reconciliation_required"
		assert ack["ack"]["outcome"] == "reconciliation_required"
		assert ack["ack"]["documentRef"] == {"doctype": "Sales Invoice", "name": "ACC-SINV-2026-18000"}
		assert ack["ack"]["reason"]["category"] == "validation"
		assert fake.events.count("submit") == 0  # never a second document

	def test_an_unreadable_existing_invoice_acks_failed_transient(self, load_glue):
		fake = _Frappe(unreadable=True)
		glue = load_glue(fake)
		outcome, client = _post(glue, _work_item(), _Store(existing=_EXISTING))
		assert outcome == "failed_transient"
		assert client.acks[0]["ack"] == {"outcome": "failed_transient"}
		assert client.acks[0]["key"] == f"{_REF}:failed_transient:9"

	def test_a_legacy_work_item_echoes_posted_without_reading_the_invoice(self, load_glue):
		fake = _Frappe(items=[{"item_code": "ITEM-OTHER", "warehouse": "X", "rt_line_ref": _A}])
		glue = load_glue(fake)
		outcome, client = _post(glue, _work_item(version=None), _Store(existing=_EXISTING))
		assert outcome == "posted"
		assert fake.reads == []
		assert "resolutionVersion" not in client.acks[0]["ack"]


class TestReconciliationReasonIsBounded:
	def test_a_long_mismatch_reason_fits_the_ack_message_limit(self, load_glue):
		rows = [
			{"item_code": f"ITEM-LONG-CODE-{i:05d}", "warehouse": "Frozen WH", "rt_line_ref": None}
			for i in range(300)
		]
		fake = _Frappe(items=rows)
		glue = load_glue(fake)
		outcome, client = _post(glue, _work_item(), _Store(existing=_EXISTING))
		assert outcome == "reconciliation_required"
		message = client.acks[0]["ack"]["reason"]["message"]
		assert 1 <= len(message) <= 1000
