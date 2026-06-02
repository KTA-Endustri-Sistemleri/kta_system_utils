import frappe
from erpnextkta.kta_stock.label_manager import reprint_depo_label

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
def retry_job(log_name):
    """Tek bir başarısız print logunu yeniden basım için kuyruğa ekler."""
    log = frappe.get_doc("KTA Print Log", log_name)
    if log.label_doctype == "KTA Depo Etiketleri":
        reprint_depo_label(log.label_name)
        # Mevcut logun durumunu güncelleyelim veya yeni log oluşmasını bekleyelim.
        # Genelde reprint_depo_label yeni bir log üretecektir. Eskisini "Retried" yapalım
        log.status = "Success"  # veya eskiyi güncelleyebiliriz
        log.save()
        return {"status": "success", "message": "Yeniden basım kuyruğa eklendi."}
    return {"status": "error", "message": "Bilinmeyen etiket tipi."}

@frappe.whitelist()
def cancel_job(log_name):
    """Kuyruktaki bekleyen bir işi iptal eder (durumunu Failed yapar)."""
    log = frappe.get_doc("KTA Print Log", log_name)
    if log.status == "Pending":
        log.status = "Failed"
        log.error_message = "Kullanıcı tarafından iptal edildi."
        log.save()
        return {"status": "success", "message": "İş iptal edildi."}
    return {"status": "error", "message": "Sadece bekleyen işler iptal edilebilir."}

@frappe.whitelist()
def retry_all_failed():
    """Son 2 saatteki tüm başarısız işleri yeniden dener."""
    from erpnextkta.kta_stock.tasks import retry_failed_print_jobs
    retry_failed_print_jobs()
    return {"status": "success", "message": "Tüm başarısız işler yeniden başlatıldı."}
