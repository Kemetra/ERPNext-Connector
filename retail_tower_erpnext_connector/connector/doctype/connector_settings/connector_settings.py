# Copyright (c) 2026, Retail Tower OS and contributors
# For license information, please see license.txt

# Connector Settings — Single DocType placeholder (spec 001).
# Intentionally carries NO business logic at the foundation layer. Configuration
# fields and behavior are added by later specs (003+) against reviewed contracts.
# See the project constitution, Principle VII.

from frappe.model.document import Document


class ConnectorSettings(Document):
	pass
