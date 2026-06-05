/**
 * KTA System Utils — Cache Reload Handler
 * Modül: kta_system_utils_maintenance
 *
 * Gece 01:00 bakım görevi çalıştıktan sonra sabah sisteme giriş yapan
 * kullanıcıların tarayıcı cache'ini hard-reload ile temizler.
 *
 * Frappe boot payload'ında kta_system_utils_hard_reload_required = 1
 * set edilmişse çalışır (boot.py tarafından enjekte edilir).
 *
 * Tarayıcı cache bypass: ?_cb=<timestamp> parametresi ile yeni URL
 * oluşturulur — Ctrl+Shift+R / hard-reload eşdeğeridir.
 */

frappe.provide("kta_system_utils.maintenance");

kta_system_utils.maintenance.check_hard_reload = function () {
    if (
        !frappe.boot ||
        !frappe.boot.kta_system_utils_hard_reload_required
    ) {
        return;
    }

    /**
     * sessionStorage kullanımı: localStorage'dan farklı olarak
     * tab/pencere kapatıldığında sıfırlanır.
     * Bu sayesinde:
     *   - Aynı oturumda (tab açık) sonsuz döngü olmaz
     *   - Yeni sekme / yeni oturumda tekrar tetiklenir (kasıtlı)
     */
    var RELOAD_KEY = "kta_system_utils_reload_done";
    if (sessionStorage.getItem(RELOAD_KEY)) {
        return;
    }

    // Önce işareti koy, sonra reload — çökme/hata durumunda döngüye girme
    sessionStorage.setItem(RELOAD_KEY, "1");

    frappe.show_alert({
        message: __("Sistem önbelleği güncellendi. Sayfa yeniden yükleniyor..."),
        indicator: "blue"
    }, 3);

    // 2 saniye bekle, ardından cache-busting URL ile hard reload
    setTimeout(function () {
        window.location.replace(
            window.location.pathname + "?_cb=" + Date.now()
        );
    }, 2000);
};

// Frappe Desk hazır olduğunda bir kez çalıştır
frappe.after_ajax(function () {
    if (frappe._kta_system_utils_reload_checked) return;
    frappe._kta_system_utils_reload_checked = true;
    kta_system_utils.maintenance.check_hard_reload();
});
