# Tier-2 live-flow e2e — connector DRIVE harness (runs INSIDE the frappe bench).
#
# Constructs the real connector path inline (NOT the gated poller stubs): a requests-backed
# status-aware HttpTransport -> PostingFeedClient -> frappe_glue.post_work_item, with the
# FrappePostingLogStore (Gate G5), a UomMap, and a PreResolvedWarehouse. This is the
# connector-side e2e harness the gated poller would otherwise own (see tier2-e2e-milestone memory).
#
# Run inside the bench:
#   docker exec -i devcontainer-frappe-1 bash -lc \
#     'cd /workspace/development/frappe-bench && bench --site retail.localhost console' < drive_connector.py
#
# RT_E2E_MODE env: "reject" (faithful, default) or "posted" (injects customer/company into the
# payload AFTER build_sales_invoice runs — harness-only; the connector builder stays untouched).

import os

import requests

from retail_tower_erpnext_connector.connector.posting import frappe_glue
from retail_tower_erpnext_connector.connector.posting.transport import PostingFeedClient
from retail_tower_erpnext_connector.connector.posting.frappe_store import FrappePostingLogStore
from retail_tower_erpnext_connector.connector.posting.uom import UomMap, PreResolvedWarehouse

def _shim_dp2_erpnext_item_ref(body):
    """HARNESS-ONLY compensation for a DP2 015 contract bug (see memory
    dp2-erpnextitemref-contract-bug): DP2 serves `erpnextItemRef` as a bare string, but the 012
    contract requires an object {doctype:"Item", name}. The connector is correct; DP2 is wrong.
    We wrap the string HERE (transport boundary), so the connector's contracts.py stays untouched
    and still fail-closes on a genuinely malformed ref. Remove once DP2 serves the object shape.
    """
    for item in body.get("items", []) or []:
        for line in (item.get("sale") or {}).get("lines", []) or []:
            ref = line.get("erpnextItemRef")
            if isinstance(ref, str):
                line["erpnextItemRef"] = {"doctype": "Item", "name": ref}
    return body


class _Resp:
    """Status-aware response for transport.post (the client reads .status/.headers/.body)."""

    def __init__(self, r):
        self.status = r.status_code
        self.headers = dict(r.headers)
        try:
            self.body = r.json()
        except Exception:
            self.body = {}


class RequestsTransport:
    """Real HTTP transport to DP2 over the spec-003 connectorBearer (Authorization: Bearer)."""

    def __init__(self, base, token):
        self._base = base.rstrip("/")
        self._auth = {"Authorization": "Bearer " + token}

    def get(self, path, *, params, headers):
        r = requests.get(
            self._base + path, params=params, headers={**self._auth, **headers}, timeout=15
        )
        r.raise_for_status()
        body = r.json()
        return _shim_dp2_erpnext_item_ref(body)

    def post(self, path, *, json, headers):
        # Return a status-aware object so PostingFeedClient._interpret_ack can read 201/200/409/404.
        r = requests.post(
            self._base + path, json=json, headers={**self._auth, **headers}, timeout=15
        )
        return _Resp(r)


def main():
    DP2_BASE = os.environ.get("RT_E2E_DP2_BASE", "http://172.20.0.1:3000")
    TOKEN = os.environ.get("RT_E2E_TOKEN", "rt_e2e_connector_token_0123456789abcdefghijABCD")
    STORE_ID = "22222222-2222-2222-2222-222222222222"
    MODE = os.environ.get("RT_E2E_MODE", "reject")

    print("=== RT connector live-flow drive | mode=%s | dp2=%s ===" % (MODE, DP2_BASE))
    correlation_id = "e2e-correlation-0001"  # stable X-Request-Id for the run (Principle V)

    transport = RequestsTransport(DP2_BASE, TOKEN)
    client = PostingFeedClient(transport, correlation_id=correlation_id)
    store = FrappePostingLogStore()
    # "each" must map (else build fails as UnmappedUnit before reaching submit). Use a UOM that
    # exists on the bench if any; on a bare bench the SI submit fails on Customer/Company first,
    # which is exactly the faithful reject-path we want to observe.
    uom_map = UomMap({"each": "Nos"})
    warehouses = PreResolvedWarehouse({STORE_ID: {"doctype": "Warehouse", "name": "Stores - E2E"}})

    # --- Posted-mode: monkeypatch the builder to inject customer/company AFTER it builds. -------
    # This lives ONLY in the harness; the connector's builder.build_sales_invoice is unchanged.
    if MODE == "posted":
        _orig_build = frappe_glue.build_sales_invoice

        def _build_with_customer(work_item, *, uom_for, warehouse_for):
            doc = _orig_build(work_item, uom_for=uom_for, warehouse_for=warehouse_for)
            doc["customer"] = os.environ.get("RT_E2E_CUSTOMER", "E2E Customer")
            doc["company"] = os.environ.get("RT_E2E_COMPANY", "E2E Co")
            return doc

        frappe_glue.build_sales_invoice = _build_with_customer
        print("[posted-mode] builder wrapped to inject customer/company (harness-only)")

    # --- Pull one page, post the single work-item, observe the outcome. ------------------------
    page = client.pull_postings(since=None, limit=100)
    print("PULLED items=%d cursor=%s next=%s" % (len(page.items), page.cursor, page.next_page_token))
    if not page.items:
        print("NO ITEMS — nothing to post (seed missing or already terminal). Aborting.")
        return

    wi = page.items[0]
    print("WORK ITEM ref=%s kind=%s lines=%d item0=%s" % (
        wi.work_item_ref, wi.kind, len(wi.sale.lines), wi.sale.lines[0].erpnext_item_ref.name))

    outcome = frappe_glue.post_work_item(
        wi,
        client=client,
        store=store,
        uom_map=uom_map,
        warehouses=warehouses,
        correlation_id=correlation_id,
    )
    print("OUTCOME=%s" % outcome)

    # Confirm DP2 recorded the outcome (the feed should no longer offer this ref).
    after = client.pull_postings(since=None, limit=100)
    still = any(i.work_item_ref == wi.work_item_ref for i in after.items)
    print("DP2 feed still offers this ref after ack? %s (expect False)" % still)
    print("=== DONE: outcome=%s, feed_cleared=%s ===" % (outcome, not still))
