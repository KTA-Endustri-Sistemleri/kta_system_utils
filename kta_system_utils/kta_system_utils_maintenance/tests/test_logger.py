# Copyright (c) 2026, KTA Endustri Sistemleri San. ve Tic. Ltd. Sti. and Contributors
# See license.txt

import logging
import unittest
import frappe
from kta_system_utils.logger import get_logger


class TestKTALogger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not getattr(frappe.local, 'site', None):
            try:
                frappe.init(site='erpnext.kta-endustri.com.tr')
            except Exception:
                frappe.local.conf = frappe._dict()

    def setUp(self):
        super().setUp()
        self.orig_logging = frappe.conf.get('kta_system_utils_logging')
        self.orig_level = frappe.conf.get('kta_system_utils_log_level')

    def tearDown(self):
        super().tearDown()
        if self.orig_logging is not None:
            frappe.conf['kta_system_utils_logging'] = self.orig_logging
        elif 'kta_system_utils_logging' in frappe.conf:
            del frappe.conf['kta_system_utils_logging']

        if self.orig_level is not None:
            frappe.conf['kta_system_utils_log_level'] = self.orig_level
        elif 'kta_system_utils_log_level' in frappe.conf:
            del frappe.conf['kta_system_utils_log_level']

    def test_default_logger_level_is_info(self):
        frappe.conf.pop('kta_system_utils_logging', None)
        frappe.conf.pop('kta_system_utils_log_level', None)
        logger = get_logger()
        self.assertEqual(logger.level, logging.INFO)

    def test_logger_disabled_via_boolean_false(self):
        frappe.conf['kta_system_utils_logging'] = False
        logger = get_logger()
        self.assertEqual(logger.level, logging.ERROR)

    def test_logger_disabled_via_int_zero(self):
        frappe.conf['kta_system_utils_logging'] = 0
        logger = get_logger()
        self.assertEqual(logger.level, logging.ERROR)

    def test_logger_disabled_via_string_false(self):
        frappe.conf['kta_system_utils_logging'] = 'false'
        logger = get_logger()
        self.assertEqual(logger.level, logging.ERROR)

    def test_logger_custom_level_debug(self):
        frappe.conf['kta_system_utils_logging'] = 1
        frappe.conf['kta_system_utils_log_level'] = 'DEBUG'
        logger = get_logger()
        self.assertEqual(logger.level, logging.DEBUG)

    def test_logger_custom_level_warning(self):
        frappe.conf['kta_system_utils_logging'] = 1
        frappe.conf['kta_system_utils_log_level'] = 'WARNING'
        logger = get_logger()
        self.assertEqual(logger.level, logging.WARNING)
