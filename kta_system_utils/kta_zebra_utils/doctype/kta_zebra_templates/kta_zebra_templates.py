# Copyright (c) 2025, Framras AS and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class KTAZebraTemplates(Document):
	def on_update(self):
		frappe.cache().delete_value(f"kta_zebra_template_{self.name}")
