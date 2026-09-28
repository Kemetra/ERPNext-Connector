# Runbook: Install the Connector on a Staging ERPNext Site

**Spec**: 001 — Frappe App Foundation | **Implements**: FR-009 | **Date**: 2026-06-04

Canonical staging install guide for `retail_tower_erpnext_connector`. **Staging only** —
production install is gated by [`upgrade-compatibility.md`](./upgrade-compatibility.md)
(constitution Principle III). This is the operational copy of the spec-local
`specs/001-frappe-app-foundation/quickstart.md`.

---

## Prerequisites

- A Frappe **bench** on the supported line: **Frappe v15 / ERPNext v15** (see
  [`../decisions/version-pin-upgrade-policy.md`](../decisions/version-pin-upgrade-policy.md)).
- A **staging** ERPNext site you can install apps onto (never production for this feature).
- Shell access to the bench directory.

> Version compatibility is **declared and documented, not enforced at install time**. A site
> outside the supported v15 line is unsupported; align versions before installing.

## Install steps

From the bench root:

```bash
# 1. Fetch the app into the bench
bench get-app retail_tower_erpnext_connector <repo-url>

# 2. Install onto the staging site
bench --site <staging-site> install-app retail_tower_erpnext_connector

# 3. Run migrations (no-op at the foundation; patches.txt has no patches)
bench --site <staging-site> migrate
```

## Verification

| Check | Command / action | Expected | Maps to |
|-------|------------------|----------|---------|
| App installed | `bench --site <staging-site> list-apps` | lists `retail_tower_erpnext_connector` | US1 / SC-001 |
| Site loads | open the ERPNext desk | loads without error | US1 |
| Metadata clear | inspect the app entry | name, description, publisher, license shown | US1 / FR-002 |
| Settings exist | search "Connector Settings" in the desk | opens the single config record | US2 / SC-002 |
| No business mutation | compare product/stock/sales counts | unchanged from before install | US1 / SC-003 / FR-005 |

## Run the foundation tests (on the bench)

```bash
bench --site <staging-site> run-tests --app retail_tower_erpnext_connector
```

These assert install + metadata, no business mutation, no ERPNext fork, and the Connector
Settings singleton (`tests/test_foundation.py`).

## Stock-posting prerequisites (RT-48)

POS sales post as Sales Invoices with `update_stock=1`: each submitted sale moves stock out of
the store's mapped warehouse, and a full void's return invoice moves it back. Owner decisions:
RT-47 (comment 10287) and RT-48 (comment 10291). Before the first POS sale, an ERP operator
sets the site up **in ERPNext Desk**. Retail Tower does not load stock or change these settings.

1. **Negative stock is allowed site-wide.** Set Stock Settings → *Allow Negative Stock* =
   `1` (`allow_negative_stock`). A POS sale must never be blocked because ERPNext on-hand is
   temporarily wrong. A negative Bin is an **operational stock discrepancy**: resolve it with
   the correct ERPNext stock operation (receipt, transfer, stock count). Never auto-correct it
   and never fabricate a receipt or adjustment.
   ```bash
   bench --site <site> execute frappe.db.set_single_value --args "['Stock Settings', 'allow_negative_stock', 1]"
   ```
2. **Perpetual-inventory accounts are configured** on the Company: default inventory, stock
   adjustment and cost-of-goods-sold accounts. A stock-moving sale also posts cost-of-goods GL
   entries.
3. **Every sellable mapped Item has a valuation source.** Use any of: an opening Stock
   Reconciliation with a valuation rate, Item `valuation_rate` or `standard_rate`, or a buying
   Item Price. Without one, ERPNext refuses the first stock-moving sale of that Item ("Valuation
   Rate for the Item … is required") even with negative stock allowed. The connector rejects that
   sale as `permanently_rejected / validation`. Once the Item master is fixed, recover it with the
   Backend-Core posting repair (`re_post`). The connector never posts a zero valuation.
4. **Opening stock** comes from an ERPNext **Stock Reconciliation** (purpose *Opening Stock*)
   per store warehouse, with quantity and valuation rate, dated **before** the first POS sale.
   It is strongly recommended for a correct baseline, but a missing balance does not block sales
   (see 1).
5. **Pilot Items are non-batch and non-serial** (`has_batch_no = 0`, `has_serial_no = 0`). The
   connector rejects a stock-moving invoice that contains a batch- or serial-tracked Item
   (`validation`), so one tracked line rejects the whole basket. Batch/expiry is a separate
   pharmacy capability (RT-50). This technical pilot is **not** pharmacy readiness.

6. **Confirm the exactly-once indexes exist (Gate G5) before go-live and after every upgrade.**
   Stock now moves inside the Sales Invoice submit, so a missing index duplicates **stock as well
   as revenue** when a crash-window re-offer happens.

   Why they could be missing (RT-54): Frappe's `install-app` marks every `patches.txt` entry
   completed **without running it**, and the indexes used to be created only by patches. Since
   RT-58 the connector ensures both indexes itself, idempotently and failing loudly:
   - the `after_install` and `after_migrate` hooks (`connector.schema`);
   - the Posting Log `on_doctype_update`.

   The posting poller also refuses to post while either index is missing. It logs
   `posting.guard.missing_index`, sales stay pending in Data-Pulse-2, and nothing is lost or
   duplicated. Still verify:
   ```sql
   SHOW INDEX FROM `tabSales Invoice` WHERE Key_name = 'unique_rt_si_provenance';  -- expect 2 rows
   SHOW INDEX FROM `tabPosting Log`   WHERE Key_name = 'unique_rt_posting_idem';   -- expect 2 rows
   ```
   If either returns no rows, run `bench --site <site> migrate`. `after_migrate` re-creates the
   indexes.

   If migrate then fails with `Gate G5: could not create …`, duplicate provenance rows already
   exist. Find them:
   ```sql
   SELECT rt_source_system, rt_external_id, COUNT(*) FROM `tabSales Invoice`
    WHERE rt_external_id IS NOT NULL GROUP BY 1, 2 HAVING COUNT(*) > 1;
   SELECT source_system, external_id, COUNT(*) FROM `tabPosting Log`
    GROUP BY 1, 2 HAVING COUNT(*) > 1;
   ```
   Resolve each duplicate as follows. Never delete rows; every step leaves an audit trail.

   1. **Choose the surviving Sales Invoice.** This is the one the Posting Log row points to
      (`document_name`) and that Data-Pulse-2 recorded as `documentRef`. The others are extras.
      Deciding this is an **accounting and stock decision**.
   2. **Cancel each extra Sales Invoice in ERPNext Desk.** This reverses its stock and GL.
      Cancelling alone is **not enough**: a cancelled invoice keeps its provenance key, and the
      unique index covers cancelled rows too.
   3. **Re-tag the cancelled extra's provenance key** so it no longer conflicts, and leave an
      audit comment. In `bench --site <site> console`:
      ```python
      name = "<extra SI name>"
      ext = frappe.db.get_value("Sales Invoice", name, "rt_external_id")
      assert frappe.db.get_value("Sales Invoice", name, "docstatus") == 2  # cancelled first
      frappe.db.set_value("Sales Invoice", name, "rt_external_id", f"{ext}:dup-cancelled-{name}", update_modified=False)
      frappe.get_doc("Sales Invoice", name).add_comment("Comment", f"Gate G5 dedupe: provenance re-tagged from {ext} (duplicate of the surviving invoice).")
      frappe.db.commit()
      ```
   4. **Posting Log duplicates.** Keep the row whose `document_name` is the surviving invoice.
      Re-tag the others the same way, never delete them:
      ```python
      frappe.db.set_value("Posting Log", "<row name>", "external_id", f"{ext}:dup-{'<row name>'}", update_modified=False)
      frappe.db.commit()
      ```
   5. **Re-run `bench --site <site> migrate`,** confirm both `SHOW INDEX` checks return 2 rows,
      and record the dedupe on the pilot issue. Posting resumes automatically on the next poller
      tick.

   If migrate reports `exists but is not UNIQUE on …`, an index with the right name has the
   wrong definition (for example after a manual repair). Drop it
   (`ALTER TABLE <table> DROP INDEX <name>`) and re-run `migrate`.

Returns: a full void restores stock only if the original invoice moved it. Invoices posted
before this change (`update_stock=0`) get an accounting-only credit note. Refunds never move
stock until line-aware refunds land (RT-14/RT-16).

## Uninstall (safety check)

```bash
bench --site <staging-site> uninstall-app retail_tower_erpnext_connector
```

**Expected**: the app and its Connector Settings singleton are removed; ERPNext product,
stock, and sales data are **unchanged** (FR-010 / SC-003) — the app introduced no business
mutations to reverse.

## Validation result (local Docker Frappe v15 dev)

On **2026-06-04**, install / migrate / tests were validated on a local Docker Frappe dev
site (`retail.localhost`, Frappe 15.110.0, ERPNext 15.110.0, connector 0.1.0):

- `install-app` — **PASS**
- `migrate` — **PASS** (no-op)
- `run-tests` — **PASS** (8 tests, OK)
- `list-apps` — connector listed at 0.1.0

**Caveat**: this was local dev validation; Frappe warned MariaDB 11.8 is newer than its
tested range — not a production/staging DB recommendation. The full quickstart end-to-end
(including the uninstall safety check below) is **not yet run**. Full record:
[`specs/001-frappe-app-foundation/bench-validation.md`](../../specs/001-frappe-app-foundation/bench-validation.md).

## Out of scope (later specs)

Data-Pulse-2 authentication (003), product/price export (004), inventory export (005),
sales posting (006), tax/fiscal fields (007), and the full upgrade runbook (008) are not
part of this install. The foundation is structure + documentation only.
