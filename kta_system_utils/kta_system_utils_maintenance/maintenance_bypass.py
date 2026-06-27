import frappe

def prevent_login_if_maintenance(login_manager):
    """
    Login hook: Maintenance mode aktifken, yetkisi olmayanların giriş yapmasını engeller.
    Yetkili kişilerin ise "read_only" kilidini kaldırarak oturum açabilmelerini sağlar.
    """
    mode = int(frappe.local.conf.get("maintenance_mode") or 0)
    if mode != 1:
        return

    user = login_manager.user
    if user in ("Guest", "Administrator"):
        if user == "Administrator":
            _disable_read_only()
        return

    bypass_roles = frappe.local.conf.get("maintenance_bypass_roles", ["System Manager"])
    if isinstance(bypass_roles, str):
        bypass_roles = [bypass_roles]

    user_roles = frappe.get_roles(user)
    if not bool(set(bypass_roles) & set(user_roles)):
        frappe.throw("Sistem şu anda bakımda. Giriş yapamazsınız.", frappe.SessionStopped)
    
    # Kullanıcı yetkili ise veritabanı okuma/yazma kilidini kaldır (Login tabSessions güncellenmesi için gerekli)
    if frappe.local.conf.get("maintenance_bypass_full_access"):
        _disable_read_only()

def _disable_read_only():
    frappe.flags.read_only = False
    if not frappe.conf.read_from_replica:
        # Read-only transaction commit edilip, yeni read-write transaction başlatılır
        frappe.db.commit()
        frappe.db.begin()
