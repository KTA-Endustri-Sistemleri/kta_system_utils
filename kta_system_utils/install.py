# kta_system_utils/install.py
#
# App kurulum hook'ları:
# - after_install: site_config.json'a maintenance bypass ayarlarını ekler

import frappe
from frappe.installer import update_site_config
from kta_system_utils.logger import get_logger


# Maintenance bypass varsayılan ayarları
_MAINTENANCE_BYPASS_DEFAULTS = {
    "maintenance_bypass_roles": ["System Manager"],
    "maintenance_bypass_full_access": False,
    "kta_system_utils_logging": 1,
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
            get_logger().info(
                f"after_install: site_config'e '{key}' = {default_value!r} eklendi"
            )
        else:
            get_logger().info(
                f"after_install: '{key}' zaten mevcut, atlanıyor"
            )
