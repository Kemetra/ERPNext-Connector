# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""ERPNext stock-view (Bin) read — the connector side of DP2 spec 019.

The connector PULLS wanted Bin-view reads from DP2 (`binViewPullRequests`), reads the
live ERPNext `Bin` on-hand per item for the requested warehouse, and REPORTS the
point-in-time snapshot back (`binViewReportSnapshot`). DP2 makes no outbound call;
the connector is the only ERPNext-touching component (spec 019 / Principle IX).
"""
