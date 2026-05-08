import frappe
from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager

@frappe.whitelist()
def get_printer_status(printer_name):
    """
    Frontend'den çağrılan whitelisted metod.
    Logic tamamen ZebraPrinterManager içindedir.
    """
    manager = ZebraPrinterManager()
    return manager.check_printer_status(printer_name)
