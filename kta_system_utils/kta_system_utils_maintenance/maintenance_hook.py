import frappe
from frappe import _
from kta_system_utils.logger import get_logger


def before_request():
    """
    KTA Maintenance Mode Hook
    Frappe'nin standart maintenance_mode'u aktifken ve allow_reads_during_maintenance
    açıkken, normal kullanıcıları dışarı atmak ve admin/system manager için
    read_only kilidini kaldırmak için çalışır.
    """
    mode = int(frappe.local.conf.get("maintenance_mode") or 0)

    # Session temizleme mantığı (açılış/kapanış tespiti)
    if getattr(frappe, "db", None):
        last_mode = frappe.cache().get_value("kta_maintenance_mode_status")
        if last_mode is None:
            frappe.cache().set_value("kta_maintenance_mode_status", mode)
        elif mode == 1 and last_mode == 0:
            frappe.cache().set_value("kta_maintenance_mode_status", 1)
            frappe.db.sql("delete from `tabSessions`")
            from frappe.sessions import clear_all_sessions

            clear_all_sessions()
            get_logger().info("Maintenance mode AKTİF: Tüm sessionlar temizlendi.")
        elif mode == 0 and last_mode == 1:
            frappe.cache().set_value("kta_maintenance_mode_status", 0)
            get_logger().info("Maintenance mode KAPATILDI.")

    if mode != 1:
        return

    # Maintenance mode aktifse, bypass kurallarını kontrol et
    request = getattr(frappe.local, "request", None)
    if request:
        path = request.path
        # Login/logout ve asset isteklerine izin ver
        _AUTH_WHITELIST_PATHS = frozenset(("/login", "/api/method/login", "/api/method/logout"))
        _AUTH_WHITELIST_PREFIXES = (
            "/api/method/frappe.client.get_list",
            "/api/method/frappe.client.get_count",
            "/api/method/frappe.website.",
            "/api/method/frappe.www.",
            "/assets/",
        )

        if path in _AUTH_WHITELIST_PATHS:
            _disable_read_only()
            return
        cmd = getattr(frappe.local, "form_dict", {}).get("cmd")
        if cmd in ("login", "logout"):
            _disable_read_only()
            return
        for prefix in _AUTH_WHITELIST_PREFIXES:
            if path.startswith(prefix):
                return

    user = getattr(frappe.session, "user", None)
    if not user or user == "Guest":
        raise frappe.SessionStopped("Session Stopped")

    if user == "Administrator":
        _disable_read_only()
        return

    bypass_roles = frappe.local.conf.get("maintenance_bypass_roles", ["System Manager"])
    if isinstance(bypass_roles, str):
        bypass_roles = [bypass_roles]

    user_roles = frappe.get_roles(user)
    if bool(set(bypass_roles) & set(user_roles)):
        # Yetkili kullanıcı
        if frappe.local.conf.get("maintenance_bypass_full_access"):
            _disable_read_only()
            get_logger().info(f"Maintenance bypass: FULL ACCESS — user={user}")
        else:
            get_logger().info(f"Maintenance bypass: READ-ONLY — user={user}")
        return
    else:
        get_logger().info(f"Maintenance mode: erişim reddedildi — user={user}")
        raise frappe.SessionStopped("Session Stopped")


def _disable_read_only():
    frappe.flags.read_only = False
    if not frappe.conf.read_from_replica:
        # Commit the read-only transaction and start a read-write transaction
        frappe.db.commit()
        frappe.db.begin()
