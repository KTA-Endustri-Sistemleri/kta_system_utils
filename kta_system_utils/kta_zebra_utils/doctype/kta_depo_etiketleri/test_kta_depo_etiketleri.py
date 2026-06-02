# Copyright (c) 2025, Framras AS and Contributors
# See license.txt

import frappe
import socket
from unittest.mock import patch
from frappe.tests.utils import FrappeTestCase
from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager, MockZebraPrinter, ZebraPrinter
from erpnextkta.kta_stock.label_manager import LabelPrinter, reprint_depo_label, check_queue_health

class TestKTADepoEtiketleri(FrappeTestCase):
	def setUp(self):
		# Setup test templates and printers
		if not frappe.db.exists("KTA Zebra Templates", "KTA Depo Etiketleri"):
			frappe.get_doc({
				"doctype": "KTA Zebra Templates",
				"name": "KTA Depo Etiketleri",
				"zebra_template": "^XA^FD{data.item_code}^FS^XZ"
			}).insert()

		if not frappe.db.exists("KTA Zebra Printers", "Test Primary Printer"):
			frappe.get_doc({
				"doctype": "KTA Zebra Printers",
				"printer_name": "Test Primary Printer",
				"ip": "192.168.1.100",
				"port": 9100
			}).insert()

		if not frappe.db.exists("KTA Zebra Printers", "Test Fallback Printer"):
			frappe.get_doc({
				"doctype": "KTA Zebra Printers",
				"printer_name": "Test Fallback Printer",
				"ip": "192.168.1.101",
				"port": 9100
			}).insert()

		if not frappe.db.exists("KTA Zebra Printers", "MOCK_PRINTER"):
			frappe.get_doc({
				"doctype": "KTA Zebra Printers",
				"printer_name": "MOCK_PRINTER",
				"ip": "127.0.0.1",
				"port": 9100
			}).insert()

		# Setup default printer for current user
		frappe.db.delete("KTA User Zebra Printers", {"user": frappe.session.user})
		frappe.get_doc({
			"doctype": "KTA User Zebra Printers",
			"user": frappe.session.user,
			"printer": "Test Primary Printer",
			"fallback_printer": "Test Fallback Printer",
			"disabled": 0
		}).insert()

		# Setup a dummy KTA Depo Etiketleri label with do_not_split=0
		self.label = frappe.get_doc({
			"doctype": "KTA Depo Etiketleri",
			"item_code": "10023209",
			"item_name": "Test Item Name",
			"item_group": "Products",
			"qty": 5,
			"uom": "Adet",
			"supplier_delivery_note": "INV-10203",
			"sut_barcode": "SUT-BARCODE",
			"gr_posting_date": "2026-06-01",
			"quality_ref": "QR-999",
			"do_not_split": 0,
			"print_count": 0
		}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_mock_printing_creates_log(self):
		# When frappe.flags.in_test is True, get_printer_for_user returns MockZebraPrinter.
		# Let's verify that running the printer prints, updates count, and logs it.
		LabelPrinter.print_pr_labels(label=self.label.name)

		# 1. Print count is updated on KTA Depo Etiketleri
		count = frappe.db.get_value("KTA Depo Etiketleri", self.label.name, "print_count")
		self.assertEqual(count, 1)

		# 2. A print log with 'Success' is created
		logs = frappe.get_all("KTA Print Log", filters={"label_name": self.label.name})
		self.assertEqual(len(logs), 1)
		
		log = frappe.get_doc("KTA Print Log", logs[0].name)
		self.assertEqual(log.status, "Success")
		self.assertEqual(log.user, frappe.session.user)

	def test_reprint_button_behavior(self):
		# reprint_depo_label should increment counter
		reprint_depo_label(self.label.name)
		count = frappe.db.get_value("KTA Depo Etiketleri", self.label.name, "print_count")
		self.assertEqual(count, 1)

	def test_fallback_printer_switching(self):
		# Disable in_test mode momentarily for get_printer_for_user to run connection checks
		orig_in_test = frappe.flags.in_test
		orig_use_mock = frappe.conf.get("use_mock_zebra_printer")
		try:
			frappe.flags.in_test = False
			frappe.conf.use_mock_zebra_printer = 0
			def mock_connect(address, timeout=None):
				ip, port = address
				if ip == "192.168.1.100":
					raise socket.timeout("Primary printer timeout")
				elif ip == "192.168.1.101":
					# Connection success for fallback
					class MockSocket:
						def __enter__(self): return self
						def __exit__(self, *args): pass
					return MockSocket()
				raise OSError("No route to host")

			with patch("socket.create_connection", side_effect=mock_connect):
				printer = ZebraPrinterManager.get_printer_for_user(user=frappe.session.user)
				self.assertIsNotNone(printer)
				self.assertEqual(printer.printer_name, "Test Fallback Printer")
		finally:
			frappe.flags.in_test = orig_in_test
			if orig_use_mock is not None:
				frappe.conf.use_mock_zebra_printer = orig_use_mock
			else:
				frappe.conf.pop("use_mock_zebra_printer", None)

	def test_user_can_print_permission(self):
		# Create a permission record for Test Primary Printer that requires the "System Manager" role
		frappe.db.delete("KTA Printer Permission", {"printer": "Test Primary Printer"})
		
		# If no KTA Printer Permission exists, anyone can print
		self.assertTrue(ZebraPrinterManager._user_can_print(frappe.session.user, "Test Primary Printer"))

		# Add permission record for System Manager
		frappe.get_doc({
			"doctype": "KTA Printer Permission",
			"printer": "Test Primary Printer",
			"role": "System Manager",
			"can_print": 1
		}).insert()

		# User should still be allowed if they have System Manager role
		with patch("frappe.get_roles", return_value=["System Manager", "All"]):
			self.assertTrue(ZebraPrinterManager._user_can_print("test@example.com", "Test Primary Printer"))

		# User should be blocked if they do not have the role
		with patch("frappe.get_roles", return_value=["Guest", "All"]):
			self.assertFalse(ZebraPrinterManager._user_can_print("test@example.com", "Test Primary Printer"))

	def test_queue_health_check(self):
		# Test check_queue_health method by mocking rq Worker
		with patch("rq.Worker.all") as mock_workers:
			class MockWorker:
				def queue_names(self):
					return ["short"]
			mock_workers.return_value = [MockWorker()]
			self.assertTrue(check_queue_health())

	def test_queue_status_apis(self):
		# Import page APIs
		from kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue import (
			get_queue_status, retry_job, cancel_job, retry_all_failed
		)

		# Create a pending log and a failed log
		pending_log = frappe.get_doc({
			"doctype": "KTA Print Log",
			"label_doctype": "KTA Depo Etiketleri",
			"label_name": self.label.name,
			"printer": "Test Primary Printer",
			"status": "Pending",
			"attempted_at": frappe.utils.now(),
			"zpl_payload": "^XA"
		}).insert()

		failed_log = frappe.get_doc({
			"doctype": "KTA Print Log",
			"label_doctype": "KTA Depo Etiketleri",
			"label_name": self.label.name,
			"printer": "Test Primary Printer",
			"status": "Failed",
			"attempted_at": frappe.utils.now(),
			"zpl_payload": "^XA",
			"error_message": "Some socket timeout"
		}).insert()

		# Test get_queue_status
		status = get_queue_status()
		self.assertTrue(any(p.name == pending_log.name for p in status["pending"]))
		self.assertTrue(any(f.name == failed_log.name for f in status["failed"]))

		# Test cancel_job
		res = cancel_job(pending_log.name)
		self.assertEqual(res["status"], "success")
		self.assertEqual(frappe.db.get_value("KTA Print Log", pending_log.name, "status"), "Failed")

		# Test retry_job
		res = retry_job(failed_log.name)
		self.assertEqual(res["status"], "success")
		self.assertEqual(frappe.db.get_value("KTA Print Log", failed_log.name, "status"), "Success")
