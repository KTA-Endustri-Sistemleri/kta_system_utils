# kta_system_utils/install.py
#
# App kurulum hook'ları:
# - after_install: site_config.json'a maintenance bypass ayarlarını ekler

import frappe
from frappe.installer import update_site_config


# Maintenance bypass varsayılan ayarları
_MAINTENANCE_BYPASS_DEFAULTS = {
    "maintenance_bypass_roles": ["System Manager"],
    "maintenance_bypass_full_access": False,
}


def after_install():
    """
    kta_system_utils app kurulduğunda site_config.json'a
    maintenance bypass ayarlarını ekler.

    Eğer ayarlar zaten mevcutsa, üzerlerine yazılmaz
    (kullanıcının mevcut konfigürasyonu korunur).
    """
    for key, default_value in _MAINTENANCE_BYPASS_DEFAULTS.items():
        if frappe.conf.get(key) is None:
            update_site_config(key, default_value)
            frappe.logger("kta_system_utils").info(
                f"after_install: site_config'e '{key}' = {default_value!r} eklendi"
            )
        else:
            frappe.logger("kta_system_utils").info(
                f"after_install: '{key}' zaten mevcut, atlanıyor"
            )
