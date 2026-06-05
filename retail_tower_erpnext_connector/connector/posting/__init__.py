# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Sales Posting Adapter (connector spec 006) — consume/post side.

Turns a Data-Pulse-2 posting work-item (a validated 008 sale projection delivered over the
fixed 012 posting-feed contract) into an ERPNext sales document, and acks a typed outcome.

Module layout (the frappe/no-frappe split is load-bearing — constitution VII, no local bench):

  Pure-Python core (NO ``import frappe``; locally unit-tested, RED→GREEN):
    - ``contracts.py``      — frozen 012 work-item / outcome DTOs (T010)
    - ``transport.py``      — pull/ack transport behind a Protocol (T011)
    - ``builder.py``        — work-item → Sales-Invoice payload transform (T030/T033/T034)
    - ``idempotency.py``    — idempotency-store Protocol + replay logic (T040/T042)
    - ``reasons.py``        — internal failure → 012 closed RejectionReason mapper (T050/T052)
    - ``uom.py``            — unit → ERPNext-UOM map (T070); warehouse + money helpers (T071/T072)

  Frappe-coupled glue (imports ``frappe``; ⏳ BENCH-VALIDATION, NOT run locally — standing-rules §6):
    - ``frappe_glue.py``    — posting submit / ack / observability adapters (T031/T032/T041/T051/T090)

Forbidden surfaces (NOT in this lane — explicit per-surface approval required, standing-rules §3):
    - the idempotency-store Frappe DocType JSON (concrete T020 adapter)
    - the poller ``scheduler_events`` registration in ``hooks.py`` (T093)
"""
