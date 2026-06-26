# Copyright (c) 2026, KTA Endustri Sistemleri San. ve Tic. Ltd. Sti. and Contributors
# See license.txt

import frappe
from unittest.mock import patch
from frappe.tests.utils import FrappeTestCase
from kta_system_utils.kta_system_utils_maintenance.tasks import (
    nightly_cache_clear,
    _RELOAD_FLAG_KEY,
)
from kta_system_utils.kta_system_utils_maintenance.boot import boot_session


class TestKTASystemUtilsMaintenance(FrappeTestCase):
    def setUp(self):
        # Clear cache flag before running tests
        frappe.cache.delete_value(_RELOAD_FLAG_KEY)

    def tearDown(self):
        # Clean up cache flag after tests
        frappe.cache.delete_value(_RELOAD_FLAG_KEY)

    @patch("kta_system_utils.kta_system_utils_maintenance.tasks.subprocess.run")
    @patch("kta_system_utils.kta_system_utils_maintenance.tasks._force_logout_all")
    @patch("kta_system_utils.kta_system_utils_maintenance.tasks._clear_redis_cache")
    def test_nightly_cache_clear_flow(self, mock_clear_redis, mock_force_logout, mock_run):
        # Run nightly cache clear
        nightly_cache_clear()

        # Check that helper functions were invoked
        mock_force_logout.assert_called_once()
        mock_clear_redis.assert_called_once()
        
        # Check that the hard reload flag is set in Redis cache
        flag_val = frappe.cache.get_value(_RELOAD_FLAG_KEY)
        self.assertEqual(flag_val, 1)

    @patch("frappe.sessions.clear_all_sessions")
    def test_force_logout_all(self, mock_clear_all_sessions):
        from kta_system_utils.kta_system_utils_maintenance.tasks import _force_logout_all
        # Cache original user to restore it
        original_user = frappe.session.user
        try:
            _force_logout_all()
            mock_clear_all_sessions.assert_called_once_with(reason="KTA gece bakım: önbellek temizleme")
            self.assertEqual(frappe.session.user, "Administrator")
        finally:
            frappe.session.user = original_user

    @patch("kta_system_utils.kta_system_utils_maintenance.tasks.frappe.clear_cache")
    def test_clear_redis_cache(self, mock_clear_cache):
        from kta_system_utils.kta_system_utils_maintenance.tasks import _clear_redis_cache
        _clear_redis_cache()
        mock_clear_cache.assert_called_once()

    @patch("kta_system_utils.kta_system_utils_maintenance.tasks.subprocess.run")
    @patch("kta_system_utils.kta_system_utils_maintenance.tasks.frappe.utils.get_bench_path")
    def test_clear_pycache(self, mock_get_bench_path, mock_run):
        from kta_system_utils.kta_system_utils_maintenance.tasks import _clear_pycache
        mock_get_bench_path.return_value = "/mock/bench/path"

        with patch("os.path.isdir") as mock_isdir:
            mock_isdir.return_value = True
            _clear_pycache()

            # Should call subprocess.run to delete __pycache__ and *.pyc files
            self.assertEqual(mock_run.call_count, 2)
            
            # Verify find command parameters
            call1_args = mock_run.call_args_list[0][0][0]
            self.assertIn("find", call1_args)
            self.assertIn("__pycache__", call1_args)

            call2_args = mock_run.call_args_list[1][0][0]
            self.assertIn("find", call2_args)
            self.assertIn("*.pyc", call2_args)

    @patch("kta_system_utils.kta_system_utils_maintenance.boot.frappe.cache")
    def test_boot_session_extension(self, mock_cache):
        # Case 1: Flag is NOT set in cache
        mock_cache.get_value.return_value = None
        bootinfo = frappe._dict()
        boot_session(bootinfo)
        self.assertEqual(bootinfo.kta_system_utils_hard_reload_required, 0)

        # Case 2: Flag IS set in cache
        mock_cache.get_value.return_value = 1
        bootinfo = frappe._dict()
        boot_session(bootinfo)
        self.assertEqual(bootinfo.kta_system_utils_hard_reload_required, 1)
