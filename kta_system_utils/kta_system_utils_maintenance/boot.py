# kta_system_utils/kta_system_utils_maintenance/boot.py
#
# Boot session hook: Kullanıcı giriş yaptığında hard-reload
# sinyalini bootinfo payload'ına ekler.
# JS handler (cache_reload_handler.js) bu değeri okur.

import frappe

_RELOAD_FLAG_KEY = "kta_system_utils_hard_reload_required"


def boot_session(bootinfo):
    """
    Frappe extend_boot_session hook'u.
    Gece cache temizleme sonrası Redis'te set edilen flag varsa
    bootinfo'ya kta_system_utils_hard_reload_required = 1 ekler.
    """
    try:
        flag = frappe.cache.get_value(_RELOAD_FLAG_KEY)
        bootinfo.kta_system_utils_hard_reload_required = 1 if flag else 0
    except Exception:
        bootinfo.kta_system_utils_hard_reload_required = 0
