# Copyright (c) 2026, KTA Endustri Sistemleri San. ve Tic. Ltd. Sti. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class KTASystemNotification(Document):
    def on_submit(self):
        from frappe.utils import now
        
        # If scheduled for the future, don't broadcast immediately.
        if self.show_on_login and self.from_date and self.from_date > now():
            frappe.msgprint(frappe._("Notification is scheduled for a future date. It will be shown on login starting from {0}.").format(self.from_date))
            return

        frappe.enqueue(
            "kta_system_utils.kta_system_utils_notification.doctype.kta_system_notification.kta_system_notification.send_notifications_in_background",
            queue="long",
            timeout=1500,
            notification_id=self.name
        )
        frappe.msgprint(frappe._("Notification broadcast has been queued in the background."))

    def on_cancel(self):
        # Delete generated Notification Log records to clean up user bell icons
        frappe.db.delete(
            "Notification Log",
            filters={
                "document_type": "KTA System Notification",
                "document_name": self.name
            }
        )

def send_notifications_in_background(notification_id):
    try:
        doc = frappe.get_doc("KTA System Notification", notification_id)
    except frappe.DoesNotExistError:
        return

    # Fetch targeted users based on audience_type
    users = []
    if doc.audience_type == "Specific Roles":
        roles = [d.role for d in doc.target_roles if d.role]
        if roles:
            users = frappe.get_all("Has Role", filters={"role": ("in", roles), "parenttype": "User"}, pluck="parent")
    elif doc.audience_type == "Specific Departments":
        departments = [d.department for d in doc.target_departments if d.department]
        if departments:
            employees = frappe.get_all("Employee", filters={"department": ("in", departments), "status": "Active"}, pluck="user_id")
            users = [u for u in employees if u]
    elif doc.audience_type == "Specific Users":
        users = [d.user for d in doc.target_users if d.user]
    elif doc.audience_type == "All System Users":
        users = frappe.get_all(
            "User",
            filters={"enabled": 1, "user_type": "System User", "name": ("!=", "Administrator")},
            pluck="name"
        )
    else:
        users = []

    # Clean up user list (remove duplicates and ensure they are active system users)
    if users:
        users = list(set(users))
        users = frappe.get_all("User", filters={"name": ("in", users), "enabled": 1, "user_type": "System User"}, pluck="name")
        
    if not users:
        return
        
    # Prepare message with optional action button
    final_message = doc.message
    if doc.action_link and doc.action_label:
        btn_html = f'<div style="margin-top:10px;"><a href="{doc.action_link}" class="btn btn-primary btn-xs" style="text-decoration:none;" target="_blank">{doc.action_label}</a></div>'
        final_message += btn_html
    
    # Publish realtime message to all online users
    indicator_map = {
        "Info": "blue",
        "Success": "green",
        "Warning": "orange",
        "Error": "red"
    }
    indicator = indicator_map.get(doc.type, "blue")
    
    # Create Notification Log for each user
    # Instead of creating them one by one individually in the DB transaction,
    # we can use frappe.db.bulk_insert if we want, but inserting one by one 
    # inside a background job is perfectly fine and safe.
    for user in users:
        frappe.publish_realtime(
            "kta_system_notification",
            {
                "title": doc.subject,
                "message": final_message,
                "indicator": indicator
            },
            user=user
        )
        
        log_doc = frappe.get_doc({
            "doctype": "Notification Log",
            "subject": doc.subject,
            "email_content": frappe.utils.strip_html(doc.message)[:140], # Preview text
            "for_user": user,
            "type": "Alert",
            "document_type": "KTA System Notification",
            "document_name": doc.name
        })
        if doc.action_link:
            log_doc.link = doc.action_link
            
        log_doc.insert(ignore_permissions=True)
        
    # Send Email if requested
    if doc.send_email:
        emails = frappe.get_all(
            "User",
            filters={"enabled": 1, "user_type": "System User", "name": ("in", users)},
            pluck="email"
        )
        valid_emails = [e for e in emails if e]
        if valid_emails:
            frappe.sendmail(
                recipients=valid_emails,
                subject=doc.subject,
                message=doc.message,
                delayed=True
            )
