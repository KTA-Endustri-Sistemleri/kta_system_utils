import frappe

@frappe.whitelist()
def get_queue_status():
    """Bekleyen ve Son Başarısız etiket basım işlerini döner."""
    pending = frappe.get_all(
        "KTA Print Log",
        filters={"status": "Pending"},
        fields=["name", "label_doctype", "label_name", "printer", "user", "attempted_at"],
        order_by="attempted_at desc",
        limit=50
    )
    failed = frappe.get_all(
        "KTA Print Log",
        filters={"status": "Failed"},
        fields=["name", "label_doctype", "label_name", "printer", "user", "attempted_at", "error_message"],
        order_by="attempted_at desc",
        limit=50
    )
    return {
        "pending": pending,
        "failed": failed
    }


@frappe.whitelist()
def get_queue_stats():
    """
    Yazıcı anlık durumları + bugünkü basım istatistiklerini döner.
    Print Queue sayfasının üst widget'ı için kullanılır.
    """
    from kta_system_utils.kta_zebra_utils.api import get_all_printers_status

    today = frappe.utils.today()

    # Bugünkü durum bazlı istatistikler (yazıcı + durum gruplu)
    raw_stats = frappe.db.sql("""
        SELECT
            COALESCE(printer, '__unknown__') AS printer,
            status,
            COUNT(*) AS cnt
        FROM `tabKTA Print Log`
        WHERE DATE(attempted_at) = %s
        GROUP BY printer, status
    """, today, as_dict=True)

    # Yazıcı bazlı özet sözlüğü
    printer_stats = {}
    total_today = {"success": 0, "failed": 0, "retried": 0, "pending": 0}
    for row in raw_stats:
        p = row.printer
        if p not in printer_stats:
            printer_stats[p] = {"success": 0, "failed": 0, "retried": 0, "pending": 0}
        key = row.status.lower()
        if key in printer_stats[p]:
            printer_stats[p][key] = row.cnt
        if key in total_today:
            total_today[key] += row.cnt

    # Anlık yazıcı durumları (paralel TCP sorgusu)
    try:
        printer_statuses = get_all_printers_status()
    except Exception as e:
        frappe.log_error(f"get_queue_stats printer status error: {e}", "KTA Print Queue")
        printer_statuses = {}

    return {
        "printer_statuses": printer_statuses,
        "printer_stats": printer_stats,
        "total_today": total_today,
    }


@frappe.whitelist()
def retry_job(log_name):
    """Tek bir başarısız print logunu yeniden basım için kuyruğa ekler."""
    log = frappe.get_doc("KTA Print Log", log_name)

    if log.status not in ("Failed", "Retried"):
        return {"status": "error", "message": "Sadece başarısız veya yeniden denenen işler tekrarlanabilir."}

    if log.label_doctype == "KTA Stock Label":
        try:
            fn = frappe.get_attr("erpnextkta.kta_stock.label_manager.reprint_depo_label")
            fn(log.label_name)
        except Exception as e:
            frappe.log_error(f"KTA Stock Label retry error: {e}", "KTA Print Queue")
            return {"status": "error", "message": f"Etiket basımı başlatılamadı: {e}"}
    else:
        return {"status": "error", "message": f"Bilinmeyen etiket tipi: {log.label_doctype}"}

    # Eski logu "Retried" olarak işaretle — gerçek başarı yeni log kaydıyla takip edilir
    log.status = "Retried"
    log.save(ignore_permissions=True)
    return {"status": "success", "message": "Yeniden basım kuyruğa eklendi."}


@frappe.whitelist()
def cancel_job(log_name):
    """Kuyruktaki bekleyen bir işi iptal eder (durumunu Failed yapar)."""
    log = frappe.get_doc("KTA Print Log", log_name)
    if log.status == "Pending":
        log.status = "Failed"
        log.error_message = "Kullanıcı tarafından iptal edildi."
        log.save(ignore_permissions=True)
        return {"status": "success", "message": "İş iptal edildi."}
    return {"status": "error", "message": "Sadece bekleyen işler iptal edilebilir."}
