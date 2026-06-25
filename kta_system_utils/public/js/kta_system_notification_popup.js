// Helper: show a custom KTA notification modal (no frappe.ui.Dialog dependency)
function kta_show_notification_dialog(title, message) {
    var existing = document.getElementById("kta-notif-modal-overlay");
    if (existing) existing.remove();

    var isMobile = window.innerWidth < 600;

    var overlay = document.createElement("div");
    overlay.id = "kta-notif-modal-overlay";
    overlay.style.cssText = [
        "position:fixed", "top:0", "left:0", "width:100%", "height:100%",
        "background:rgba(0,0,0,0.45)", "z-index:9999", "display:flex",
        "align-items:" + (isMobile ? "flex-end" : "center"),
        "justify-content:center"
    ].join(";");

    var modal = document.createElement("div");
    modal.style.cssText = [
        "background:#fff",
        "border-radius:" + (isMobile ? "12px 12px 0 0" : "8px"),
        "box-shadow:0 8px 32px rgba(0,0,0,0.22)",
        "width:" + (isMobile ? "100%" : "min(540px, 92vw)"),
        "max-height:" + (isMobile ? "85vh" : "80vh"),
        "overflow:hidden", "display:flex", "flex-direction:column",
        "font-family:inherit"
    ].join(";");

    // Header — title only, no X button
    var header = document.createElement("div");
    header.style.cssText = "padding:16px 20px 12px;border-bottom:1px solid #f0f0f0;flex-shrink:0;";

    var titleEl = document.createElement("div");
    titleEl.textContent = title;
    titleEl.style.cssText = "font-weight:600;font-size:15px;color:#1c1c1c;line-height:1.4;";
    header.appendChild(titleEl);

    // Body — scrollable
    var body = document.createElement("div");
    body.style.cssText = "padding:14px 20px;color:#444;line-height:1.6;overflow-y:auto;flex:1;";
    body.innerHTML = message;

    // Scoped CSS for content inside the modal
    var style = document.createElement("style");
    style.textContent = [
        "#kta-notif-modal-overlay .btn.btn-primary.btn-xs {",
        "  display:inline-block;background:#4f46e5 !important;color:#fff !important;",
        "  border:none !important;border-radius:5px !important;",
        "  padding:5px 14px !important;font-size:12px !important;",
        "  text-decoration:none !important;cursor:pointer;font-weight:500;",
        "}",
        "#kta-notif-modal-overlay hr {",
        "  border:none;border-top:1px solid #efefef;margin:12px 0;",
        "}",
        "#kta-notif-modal-overlay h5 {",
        "  margin:0 0 3px 0;font-size:14px;font-weight:600;color:#111;",
        "}",
        "#kta-notif-modal-overlay .ql-editor.read-mode,",
        "#kta-notif-modal-overlay .ql-editor {",
        "  padding:0 !important;font-size:13px;color:#555;",
        "}",
        "#kta-notif-modal-overlay p { margin:0 0 4px 0; }",
    ].join("\n");
    document.head.appendChild(style);

    // Footer — single Kapat button
    var footer = document.createElement("div");
    footer.style.cssText = "padding:10px 20px;border-top:1px solid #f0f0f0;text-align:right;flex-shrink:0;";

    var okBtn = document.createElement("button");
    okBtn.textContent = "Kapat";
    okBtn.style.cssText = [
        "background:#1a1a1a", "color:#fff", "border:none", "border-radius:5px",
        "padding:7px 20px", "cursor:pointer", "font-size:13px", "font-weight:500"
    ].join(";");
    okBtn.onclick = function() { overlay.remove(); };

    footer.appendChild(okBtn);
    modal.appendChild(header);
    modal.appendChild(body);
    modal.appendChild(footer);
    overlay.appendChild(modal);

    // Close on overlay click
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    document.body.appendChild(overlay);
}

// Listen for real-time KTA notifications (when user is already logged in).
// Wrapped in $(document).ready to ensure frappe.realtime is fully initialized.
$(document).ready(function() {
    try {
        frappe.realtime.on("kta_system_notification", function(data) {
            if (frappe.boot && frappe.boot.developer_mode) {
                console.log("KTA realtime notification received:", data);
            }
            kta_show_notification_dialog(data.title, data.message);
        });
    } catch(e) {
        console.error("KTA: Could not register realtime listener:", e);
    }
});

// Show login-time notifications.
// Guard: frappe.after_ajax fires after every AJAX call, only run once per page load.
frappe._kta_notif_popup_shown = false;

frappe.after_ajax(function() {
    if (frappe._kta_notif_popup_shown) return;
    if (typeof frappe === "undefined" || !frappe.boot) return;

    var notifs = frappe.boot.kta_system_notifications;
    if (!notifs) return;

    if (!Array.isArray(notifs)) {
        notifs = [notifs];
    }

    if (notifs.length === 0) return;

    frappe._kta_notif_popup_shown = true;

    if (frappe.boot.developer_mode) {
        console.log("KTA System Notification Popup is running!", notifs);
    }

    var session_id = frappe.csrf_token || frappe.get_cookie("sid") || "unknown_session";

    // Clean up stale localStorage keys from previous sessions
    Object.keys(localStorage).forEach(function(key) {
        if (key.startsWith("kta_notif_seen_") && !key.endsWith("_" + session_id)) {
            localStorage.removeItem(key);
        }
    });

    // Filter only unseen notifications for this session
    var unseen_notifs = notifs.filter(function(notif) {
        return !localStorage.getItem("kta_notif_seen_" + notif.name + "_" + session_id);
    });

    if (unseen_notifs.length === 0) return;

    var combined_message = "";
    var combined_title = unseen_notifs.length > 1 ? "Sistem Bildirimleri" : unseen_notifs[0].subject;

    unseen_notifs.forEach(function(notif, index) {
        if (unseen_notifs.length > 1) {
            combined_message += '<h5>' + notif.subject + '</h5>';
        }
        combined_message += '<div>' + notif.message + '</div>';
        if (index < unseen_notifs.length - 1) {
            combined_message += '<hr>';
        }
        localStorage.setItem("kta_notif_seen_" + notif.name + "_" + session_id, "1");
    });

    setTimeout(function() {
        kta_show_notification_dialog(combined_title, combined_message);
    }, 1000);
});
