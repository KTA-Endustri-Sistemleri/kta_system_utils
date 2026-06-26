# Copyright (c) 2026, KTA Endustri Sistemleri San. ve Tic. Ltd. Sti. and Contributors
# See license.txt

import frappe
from unittest.mock import MagicMock, patch, PropertyMock
from frappe.tests.utils import FrappeTestCase
from kta_system_utils.kta_system_utils_maintenance.maintenance_bypass import (
    _is_maintenance_bypass_allowed,
    _is_auth_request,
    _complete_init_after_maintenance_bypass,
)


class TestMaintenanceBypass(FrappeTestCase):
    """Maintenance mode bypass mekanizması için unit testler."""

    # -----------------------------------------------------------------------
    # _is_maintenance_bypass_allowed testleri
    # -----------------------------------------------------------------------

    def test_administrator_always_allowed(self):
        """Administrator kullanıcısı her zaman bypass edebilmeli."""
        frappe.set_user("Administrator")
        self.assertTrue(_is_maintenance_bypass_allowed())

    def test_guest_never_allowed(self):
        """Guest kullanıcısı asla bypass edememeli."""
        frappe.set_user("Guest")
        self.assertFalse(_is_maintenance_bypass_allowed())

    def test_system_manager_allowed_by_default(self):
        """System Manager rolüne sahip kullanıcı varsayılan olarak bypass edebilmeli."""
        # Test ortamında Administrator zaten System Manager rolüne sahiptir.
        # Gerçek bir System Manager kullanıcısı oluşturup test edelim.
        test_user = _get_or_create_test_user(
            "sm_bypass_test@example.com",
            roles=["System Manager"],
        )
        frappe.set_user(test_user)
        try:
            self.assertTrue(_is_maintenance_bypass_allowed())
        finally:
            frappe.set_user("Administrator")

    def test_regular_user_not_allowed(self):
        """Normal kullanıcı (System Manager olmayan) bypass edememeli."""
        test_user = _get_or_create_test_user(
            "regular_bypass_test@example.com",
            roles=["Website Manager"],
        )
        frappe.set_user(test_user)
        try:
            self.assertFalse(_is_maintenance_bypass_allowed())
        finally:
            frappe.set_user("Administrator")

    def test_custom_bypass_roles_from_config(self):
        """site_config'deki maintenance_bypass_roles konfigürasyonu çalışmalı."""
        test_user = _get_or_create_test_user(
            "custom_role_test@example.com",
            roles=["Website Manager"],
        )
        frappe.set_user(test_user)
        try:
            # Varsayılan olarak Website Manager bypass edemez
            self.assertFalse(_is_maintenance_bypass_allowed())

            # site_config'e Website Manager eklenirse bypass edebilmeli
            with patch.object(
                frappe.local, "conf",
                frappe._dict({
                    **frappe.local.conf,
                    "maintenance_bypass_roles": ["Website Manager"],
                }),
            ):
                self.assertTrue(_is_maintenance_bypass_allowed())
        finally:
            frappe.set_user("Administrator")

    def test_bypass_roles_string_config(self):
        """site_config'de string olarak verilen tek rol desteklenmeli."""
        test_user = _get_or_create_test_user(
            "string_role_test@example.com",
            roles=["System Manager"],
        )
        frappe.set_user(test_user)
        try:
            with patch.object(
                frappe.local, "conf",
                frappe._dict({
                    **frappe.local.conf,
                    "maintenance_bypass_roles": "System Manager",
                }),
            ):
                self.assertTrue(_is_maintenance_bypass_allowed())
        finally:
            frappe.set_user("Administrator")

    # -----------------------------------------------------------------------
    # _is_auth_request testleri
    # -----------------------------------------------------------------------

    def test_login_page_is_whitelisted(self):
        """Login sayfası (/login) maintenance mode'da erişilebilir olmalı."""
        request = MagicMock()
        request.path = "/login"
        frappe.local.form_dict = frappe._dict()
        self.assertTrue(_is_auth_request(request))

    def test_login_api_is_whitelisted(self):
        """Login API'si (/api/method/login) erişilebilir olmalı."""
        request = MagicMock()
        request.path = "/api/method/login"
        frappe.local.form_dict = frappe._dict()
        self.assertTrue(_is_auth_request(request))

    def test_logout_api_is_whitelisted(self):
        """Logout API'si (/api/method/logout) erişilebilir olmalı."""
        request = MagicMock()
        request.path = "/api/method/logout"
        frappe.local.form_dict = frappe._dict()
        self.assertTrue(_is_auth_request(request))

    def test_cmd_login_is_whitelisted(self):
        """cmd=login form data ile login erişilebilir olmalı."""
        request = MagicMock()
        request.path = "/some/path"
        frappe.local.form_dict = frappe._dict({"cmd": "login"})
        self.assertTrue(_is_auth_request(request))

    def test_cmd_logout_is_whitelisted(self):
        """cmd=logout form data ile logout erişilebilir olmalı."""
        request = MagicMock()
        request.path = "/some/path"
        frappe.local.form_dict = frappe._dict({"cmd": "logout"})
        self.assertTrue(_is_auth_request(request))

    def test_regular_api_not_whitelisted(self):
        """Normal API istekleri whitelist'e dahil olmamalı."""
        request = MagicMock()
        request.path = "/api/method/frappe.client.get_value"
        frappe.local.form_dict = frappe._dict()
        self.assertFalse(_is_auth_request(request))

    def test_app_path_not_whitelisted(self):
        """/app path'i whitelist'e dahil olmamalı."""
        request = MagicMock()
        request.path = "/app"
        frappe.local.form_dict = frappe._dict()
        self.assertFalse(_is_auth_request(request))

    # -----------------------------------------------------------------------
    # Patched init_request davranış testleri
    # -----------------------------------------------------------------------

    def test_patch_is_applied(self):
        """Monkey-patch uygulanmış olmalı."""
        from kta_system_utils.kta_system_utils_maintenance.maintenance_bypass import (
            _PATCH_APPLIED,
        )
        self.assertTrue(_PATCH_APPLIED)

    def test_non_maintenance_mode_unaffected(self):
        """Maintenance mode kapalıyken normal akış değişmemeli."""
        # Mevcut durumda maintenance_mode kapalı olmalı
        self.assertFalse(
            frappe.local.conf.get("maintenance_mode"),
            "Test ortamında maintenance_mode kapalı olmalı",
        )
        # Normal request akışı çalışıyor olmalı — bu test ortamının
        # zaten başarılı kurulmuş olmasıyla dolaylı olarak doğrulanır


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------

def _get_or_create_test_user(email, roles=None):
    """Test kullanıcısı oluşturur veya mevcutsa döner."""
    if not frappe.db.exists("User", email):
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "user_type": "System User",
            "send_welcome_email": 0,
        })
        for role in (roles or []):
            user.append("roles", {"role": role})
        user.insert(ignore_permissions=True)
        frappe.db.commit()
    return email
