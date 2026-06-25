import frappe

def boot_session(bootinfo):
    try:
        from frappe.utils import now
        # Fetch active scheduled notifications
        active_notifs = frappe.get_all(
            "KTA System Notification",
            filters={
                "docstatus": 1,
                "show_on_login": 1,
                "from_date": ("<=", now()),
                "to_date": (">=", now())
            },
            fields=["name", "subject", "message", "type", "audience_type", "action_label", "action_link"],
            ignore_permissions=True
        )

        user = frappe.session.user
        filtered_notifs = []
        
        if active_notifs and user and user != "Guest":
            user_roles = frappe.get_roles(user)
            user_dept = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "department")

            for n in active_notifs:
                allowed = False
                
                if n.audience_type == "Specific Roles":
                    roles = frappe.get_all("KTA Notification Target Role", filters={"parent": n.name}, pluck="role", ignore_permissions=True)
                    if any(r in user_roles for r in roles):
                        allowed = True
                elif n.audience_type == "Specific Departments":
                    departments = frappe.get_all("KTA Notification Target Dept", filters={"parent": n.name}, pluck="department", ignore_permissions=True)
                    if user_dept in departments:
                        allowed = True
                elif n.audience_type == "Specific Users":
                    users = frappe.get_all("KTA Notification Target User", filters={"parent": n.name}, pluck="user", ignore_permissions=True)
                    if user in users:
                        allowed = True
                else:
                    allowed = True

                if allowed:
                    # Prepare message with optional action button
                    final_message = n.message
                    if n.action_link and n.action_label:
                        btn_html = f'<div style="margin-top:10px;"><a href="{n.action_link}" class="btn btn-primary btn-xs" style="text-decoration:none;" target="_blank">{n.action_label}</a></div>'
                        final_message += btn_html
                        
                    filtered_notifs.append({
                        "name": n.name,
                        "subject": n.subject,
                        "message": final_message,
                        "type": n.type
                    })
                    
        bootinfo.kta_system_notifications = filtered_notifs
    except Exception as e:
        bootinfo.kta_system_notifications = []
        frappe.log_error(title="Failed to fetch KTA System Notifications on boot", message=str(e))
