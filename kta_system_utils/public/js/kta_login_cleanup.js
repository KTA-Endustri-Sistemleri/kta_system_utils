// kta_system_utils/public/js/kta_login_cleanup.js

/* 
 * Maintenance Mode - Browser Cleanup
 * 
 * Bu script, Frappe'nin login sayfasında (/login) çalışır.
 * Eğer sistem maintenance mode'a geçerse, arka uçtaki _force_logout_all()
 * tüm kullanıcıları sistemden atar ve login sayfasına düşürür.
 * 
 * Kullanıcı login sayfasına düştüğünde, browser'da kalan tüm
 * localStorage ve sessionStorage verilerinin temizlenmesini sağlar.
 */

if (window.location.pathname === '/login') {
    try {
        // Frappe cache'ini ve genel storage'ı temizle
        localStorage.clear();
        sessionStorage.clear();
        
        // Log to console (optional, for debugging)
        console.log("KTA System Utils: Browser storage cleared due to login page redirect (potential maintenance mode).");
    } catch (e) {
        console.error("KTA System Utils: Failed to clear browser storage.", e);
    }
}
