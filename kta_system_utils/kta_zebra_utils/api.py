import frappe
from kta_system_utils.kta_zebra_utils.printer_manager import ZebraPrinterManager, ZebraPrinter, MockZebraPrinter

@frappe.whitelist()
def get_printer_status(printer_name):
    """
    Frontend'den çağrılan whitelisted metod.
    Logic tamamen ZebraPrinterManager içindedir.
    """
    manager = ZebraPrinterManager()
    return manager.check_printer_status(printer_name)

@frappe.whitelist()
def get_all_printers_status():
    """
    Tüm yazıcıların durumunu paralel olarak sorgular.
    Herhangi bir database veya Frappe context ihtiyacını thread'lerin dışına çıkararak
    thread-safe hale getirilmiştir.
    """
    import concurrent.futures
    # Ana thread'de tüm yazıcıların bilgilerini tek seferde çekiyoruz (ignore_permissions ile yetki hatasını önler)
    printers = frappe.get_all("KTA Zebra Printers", fields=["name", "ip", "port"], ignore_permissions=True)
    
    use_mock = frappe.conf.get("use_mock_zebra_printer") or frappe.flags.in_test
    
    def check(p):
        if use_mock:
            printer = MockZebraPrinter()
        else:
            printer = ZebraPrinter(
                printer_name=p.name,
                ip=p.ip,
                port=p.port or 9100
            )
        return p.name, printer.get_detailed_status()
        
    status_map = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check, printers)
        for name, status in results:
            status_map[name] = status
            
    return status_map
