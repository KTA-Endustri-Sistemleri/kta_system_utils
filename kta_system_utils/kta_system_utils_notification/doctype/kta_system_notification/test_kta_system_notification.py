# Copyright (c) 2026, KTA Endustri Sistemleri San. ve Tic. Ltd. Sti. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from kta_system_utils.kta_system_utils_notification.doctype.kta_system_notification.kta_system_notification import send_notifications_in_background
from kta_system_utils.kta_system_utils_notification.boot import boot_session

class TestKTASystemNotification(FrappeTestCase):
    def setUp(self):
        # Create test users
        self.create_user("unique_user_all1@example.com")
        self.create_user("unique_user_all2@example.com")
        self.create_user("unique_user_hr@example.com")
        self.create_user("unique_user_it@example.com")

        # Create basic role for testing
        if not frappe.db.exists("Role", "Test Basic Role"):
            frappe.get_doc({"doctype": "Role", "role_name": "Test Basic Role"}).insert()

        self.add_role("unique_user_all1@example.com", "Test Basic Role")
        self.add_role("unique_user_all2@example.com", "Test Basic Role")

        # Create Role
        if not frappe.db.exists("Role", "Test HR Role"):
            frappe.get_doc({"doctype": "Role", "role_name": "Test HR Role"}).insert()

        self.add_role("unique_user_hr@example.com", "Test HR Role")

        # Create Department
        if not frappe.db.exists("Department", {"department_name": "Test IT Dept"}):
            frappe.get_doc({"doctype": "Department", "department_name": "Test IT Dept"}).insert(ignore_if_duplicate=True)

        # Create Employee for department targeting
        dept_name = frappe.db.get_value("Department", {"department_name": "Test IT Dept"}, "name")
        existing_emp = frappe.db.get_value("Employee", {"user_id": "unique_user_it@example.com"}, "name")
        if existing_emp:
            emp = frappe.get_doc("Employee", existing_emp)
            emp.department = dept_name
            emp.save(ignore_permissions=True)
        elif not frappe.db.exists("Employee", "HR-TEST-EMP"):
            frappe.get_doc({
                "doctype": "Employee",
                "employee": "HR-TEST-EMP",
                "first_name": "Test",
                "status": "Active",
                "user_id": "unique_user_it@example.com",
                "department": dept_name,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": "2020-01-01"
            }).insert(ignore_permissions=True)

        # Clear existing logs for tests
        frappe.db.delete("Notification Log", {"document_type": "KTA System Notification"})
        frappe.db.delete("KTA System Notification")

    def tearDown(self):
        frappe.session.user = "Administrator"
        frappe.db.delete("Notification Log", {"document_type": "KTA System Notification"})
        frappe.db.delete("KTA System Notification")

    def create_user(self, email):
        if not frappe.db.exists("User", email):
            frappe.get_doc({
                "doctype": "User",
                "email": email,
                "first_name": "Test",
                "send_welcome_email": 0,
                "enabled": 1,
                "user_type": "System User"
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("User", email, "enabled", 1)

    def add_role(self, user, role):
        if not frappe.db.exists("Has Role", {"parent": user, "role": role}):
            doc = frappe.get_doc("User", user)
            doc.append("roles", {"role": role})
            doc.save(ignore_permissions=True)

    def test_broadcast_to_all_system_users(self):
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "Broadcast Test",
            "message": "This is a broadcast test",
            "type": "Info",
            "audience_type": "All System Users"
        }).insert(ignore_permissions=True)
        doc.submit()
        
        # Manually call the background worker for testing
        send_notifications_in_background(doc.name)
        
        logs = frappe.get_all("Notification Log", filters={"document_name": doc.name}, pluck="for_user")
        self.assertIn("unique_user_all1@example.com", logs)
        self.assertIn("unique_user_hr@example.com", logs)

    def test_cancel_notification_cleanup(self):
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "Cleanup Test",
            "message": "Cleanup",
            "type": "Info",
            "audience_type": "Specific Users",
            "target_users": [{"user": "unique_user_all1@example.com"}]
        }).insert(ignore_permissions=True)
        doc.submit()
        send_notifications_in_background(doc.name)
        
        self.assertTrue(frappe.db.exists("Notification Log", {"document_name": doc.name}))
        
        doc.cancel()
        
        self.assertFalse(frappe.db.exists("Notification Log", {"document_name": doc.name}))

    def test_targeted_notification_by_role(self):
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "Role Test",
            "message": "Role Test Message",
            "type": "Info",
            "audience_type": "Specific Roles",
            "target_roles": [{"role": "Test HR Role"}]
        }).insert(ignore_permissions=True)
        doc.submit()
        send_notifications_in_background(doc.name)
        
        logs = frappe.get_all("Notification Log", filters={"document_name": doc.name}, pluck="for_user")
        self.assertIn("unique_user_hr@example.com", logs)
        self.assertNotIn("unique_user_all1@example.com", logs)

    def test_targeted_notification_by_user(self):
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "User Test",
            "message": "User Test Message",
            "type": "Info",
            "audience_type": "Specific Users",
            "target_users": [{"user": "unique_user_all2@example.com"}]
        }).insert(ignore_permissions=True)
        doc.submit()
        send_notifications_in_background(doc.name)
        
        logs = frappe.get_all("Notification Log", filters={"document_name": doc.name}, pluck="for_user")
        self.assertEqual(len(logs), 1)
        self.assertIn("unique_user_all2@example.com", logs)
        
    def test_targeted_notification_by_department(self):
        dept_name = frappe.db.get_value("Department", {"department_name": "Test IT Dept"}, "name")
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "Dept Test",
            "message": "Dept Test Message",
            "type": "Info",
            "audience_type": "Specific Departments",
            "target_departments": [{"department": dept_name}]
        }).insert(ignore_permissions=True)
        doc.submit()
        send_notifications_in_background(doc.name)
        
        logs = frappe.get_all("Notification Log", filters={"document_name": doc.name}, pluck="for_user")
        self.assertEqual(len(logs), 1)
        self.assertIn("unique_user_it@example.com", logs)

    def test_action_link_injection(self):
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "Link Test",
            "message": "Link Test Message",
            "type": "Info",
            "audience_type": "Specific Users",
            "target_users": [{"user": "unique_user_all1@example.com"}],
            "action_label": "Click Here",
            "action_link": "/app/test"
        }).insert(ignore_permissions=True)
        doc.submit()
        send_notifications_in_background(doc.name)
        
        log = frappe.get_last_doc("Notification Log", filters={"document_name": doc.name})
        self.assertEqual(log.link, "/app/test")
        
    def test_boot_session_logic(self):
        from frappe.utils import add_days, now
        doc = frappe.get_doc({
            "doctype": "KTA System Notification",
            "subject": "Boot Test",
            "message": "Boot Test Message",
            "type": "Info",
            "show_on_login": 1,
            "from_date": add_days(now(), -1),
            "to_date": add_days(now(), 1),
            "audience_type": "Specific Roles",
            "target_roles": [{"role": "Test HR Role"}]
        }).insert(ignore_permissions=True)
        doc.submit()

        class DummyBootinfo:
            pass

        bootinfo = DummyBootinfo()
        
        # Test valid role
        frappe.session.user = "unique_user_hr@example.com"
        boot_session(bootinfo)
        self.assertTrue(hasattr(bootinfo, 'kta_system_notifications'))
        self.assertEqual(len(bootinfo.kta_system_notifications), 1)
        self.assertEqual(bootinfo.kta_system_notifications[0]["name"], doc.name)
        
        # Test invalid role
        frappe.session.user = "unique_user_all1@example.com"
        bootinfo = DummyBootinfo()
        boot_session(bootinfo)
        self.assertEqual(len(bootinfo.kta_system_notifications), 0)
