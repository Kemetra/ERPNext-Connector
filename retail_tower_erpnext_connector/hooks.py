app_name = "retail_tower_erpnext_connector"
app_title = "Retail Tower ERPNext Connector"
app_publisher = "Retail Tower OS"
app_description = (
	"Integration layer between Retail Tower OS (via Data-Pulse-2) and ERPNext / Frappe. "
	"Foundation only: app scaffold and Connector Settings placeholder. No business mutation."
)
app_email = "admin@rahmaqanater.org"
app_license = "mit"

# ERPNext is the ERP/accounting/inventory backend this connector integrates with.
# Declaring it here ensures the app cannot be installed on a site without ERPNext.
# This declares the dependency; the supported VERSION range is documented as policy
# (docs/decisions/version-pin-upgrade-policy.md), not enforced as install-blocking logic.
required_apps = ["erpnext"]

# -----------------------------------------------------------------------------
# Foundation scope (spec 001): this app registers NO document-event handlers,
# NO scheduled jobs, and NO overrides that create, update, or delete product,
# stock, price, or sales data. See the project constitution, Principle VII
# (.specify/memory/constitution.md) and spec FR-005.
#
# doc_events, scheduler_events, override_doctype_class, etc. are intentionally
# left unset at the foundation layer. They are introduced by later specs
# (003 auth, 004 product export, 005 inventory, 006 sales posting) against
# their own reviewed contracts.
# -----------------------------------------------------------------------------
