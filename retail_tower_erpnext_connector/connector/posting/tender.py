# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

"""Tender → ERPNext Mode of Payment resolution (RT-78, RT-10 D5).

The operator maps each posting-feed tender method to an ERPNext Mode of Payment in Connector
Settings (config, injected — never hardcoded). An unmapped method fails closed
(:class:`UnmappedTender`) → ``permanently_rejected`` / ``validation``: there is no default Mode of
Payment and the connector never guesses one or its account (Principle VI).

This module imports NO frappe.
"""

from __future__ import annotations

from collections.abc import Mapping


class UnmappedTender(Exception):
    """A tender method has no configured ERPNext Mode of Payment (RT-10 D5 fail-closed)."""

    def __init__(self, method: str) -> None:
        super().__init__(
            f"tender method {method!r} has no ERPNext Mode of Payment mapping — fail-closed → "
            "validation (RT-10 D5: configure the Connector Settings tender map; never guessed)"
        )
        self.method = method


class TenderModeMap:
    """Applies the operator-configured tender-method → Mode of Payment map (fail-closed on a miss)."""

    def __init__(self, mapping: Mapping[str, str]) -> None:
        self._map = dict(mapping)

    def resolve(self, method: str) -> str:
        """Return the ERPNext Mode of Payment for ``method``; raise :class:`UnmappedTender` if absent."""
        try:
            return self._map[method]
        except KeyError:
            raise UnmappedTender(method) from None
