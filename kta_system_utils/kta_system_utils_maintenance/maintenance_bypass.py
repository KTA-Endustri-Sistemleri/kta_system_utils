# kta_system_utils/kta_system_utils_maintenance/maintenance_bypass.py
#
# Monkey-patch: Maintenance mode sırasında Administrator ve
# System Manager rolüne sahip kullanıcıların sisteme erişimine izin verir.
#
# Frappe'de maintenance_mode kontrolü, kullanıcı session'ı kurulmadan
# ÖNCE yapılır (app.py → init_request). Bu yüzden hook sistemi ile
# bu davranışı değiştirmek mümkün değildir. Monkey-patch ile
# init_request fonksiyonunu wrap ediyoruz.

import functools
import logging

import frappe
import frappe.app

logger = logging.getLogger("kta_system_utils")

_PATCH_APPLIED = False

# Maintenance mode'da login ve logout yapabilmek için izin verilen path'ler.
# Login sayfası yüklenmeden giriş yapılamaz; logout yapılamazsa yetkisiz
# kullanıcılar içeride mahsur kalır.
_AUTH_WHITELIST_PATHS = frozenset((
    "/login",
    "/api/method/login",
    "/api/method/logout",
))

# Login akışı sırasında gereken ek path prefix'leri
# (assets, translations vb.)
_AUTH_WHITELIST_PREFIXES = (
    "/api/method/frappe.client.get_list",        # login sayfası render bağımlılıkları
    "/api/method/frappe.client.get_count",
    "/api/method/frappe.website.",                # website route handler
    "/api/method/frappe.www.",                    # www handler
    "/assets/",                                   # statik dosyalar (CSS/JS)
)


def apply_patch():
    """
    frappe.app.init_request fonksiyonunu monkey-patch ile wrap eder.

    Bu fonksiyon idempotent'tir — birden fazla çağrılsa bile
    patch yalnızca bir kez uygulanır.
    """
    global _PATCH_APPLIED

    if _PATCH_APPLIED:
        return

    _original_init_request = frappe.app.init_request

    @functools.wraps(_original_init_request)
    def _patched_init_request(request):
        """
        Orijinal init_request'i çalıştırır. Eğer maintenance_mode
        aktifse ve SessionStopped fırlatılırsa:

        1. Auth (login/logout) sayfası/API ise → giriş/çıkış için izin verilir
        2. DB bağlantısı zaten kurulmuş (frappe.connect çağrıldıktan sonra)
        3. Maintenance kontrolünü atlayarak kalan init_request adımlarını
           manuel olarak çalıştırır (form_dict, HTTPRequest, before_request hooks)
        4. Kullanıcı session'ı kurulduktan sonra rol kontrolü yapar
        5. Administrator veya System Manager değilse → SessionStopped fırlatır
        """
        try:
            _original_init_request(request)
            # Eğer hata yoksa (maintenance mode kapalı veya API allow_reads vs ise)
            if frappe.db:
                _check_maintenance_mode_status()
        except frappe.SessionStopped:
            # Maintenance mode aktif ve SessionStopped fırlatıldı.
            # Bu noktada frappe.connect() zaten çalıştı, DB bağlantısı var.
            if frappe.db:
                _check_maintenance_mode_status()

            # Ama form_dict, HTTPRequest ve before_request hooks çalışmadı.

            # init_request'in kalan adımlarını manuel çalıştır
            _complete_init_after_maintenance_bypass(request)

            # Login/Logout sayfası veya API'si ise → izin ver
            # Böylece kullanıcılar giriş yapabilir veya mahsur kalanlar çıkış yapabilir
            if _is_auth_request(request):
                logger.info(
                    "Maintenance mode: auth (login/logout) erişimine izin verildi — path=%s, ip=%s",
                    request.path,
                    getattr(frappe.local, "request_ip", "unknown"),
                )
                return

            # Şimdi session kuruldu, kullanıcıyı kontrol et
            if _is_maintenance_bypass_allowed():
                # Yetkili kullanıcı — read-only mode kur (güvenlik için)
                # ama full access istiyorlarsa site_config'den ayarlanabilir
                if frappe.local.conf.get("maintenance_bypass_full_access"):
                    # Full access — yazma işlemleri de yapılabilir
                    logger.info(
                        "Maintenance bypass: FULL ACCESS — user=%s, ip=%s",
                        frappe.session.user,
                        getattr(frappe.local, "request_ip", "unknown"),
                    )
                else:
                    # Varsayılan: read-only mode
                    frappe.app.setup_read_only_mode()
                    logger.info(
                        "Maintenance bypass: READ-ONLY — user=%s, ip=%s",
                        frappe.session.user,
                        getattr(frappe.local, "request_ip", "unknown"),
                    )
            else:
                # Yetkisiz kullanıcı — orijinal davranışı koru
                logger.info(
                    "Maintenance mode: erişim reddedildi — user=%s, ip=%s",
                    getattr(frappe.session, "user", "Guest"),
                    getattr(frappe.local, "request_ip", "unknown"),
                )
                raise frappe.SessionStopped("Session Stopped")

    frappe.app.init_request = _patched_init_request

    # application fonksiyonundaki referansı da güncelle
    # (init_request, application() içinde doğrudan çağrılır)
    _PATCH_APPLIED = True
    logger.info("kta_system_utils: maintenance_bypass patch uygulandı")


def _is_auth_request(request):
    """
    İsteğin login/logout sayfası veya auth API'si olup olmadığını kontrol eder.

    Yetkisiz kullanıcılar maintenance mode açıldığında içeride mahsur kalmamak
    için logout olabilmelidir. Aynı şekilde login formu da yüklenebilmelidir.
    """
    path = request.path

    # Tam eşleşme
    if path in _AUTH_WHITELIST_PATHS:
        return True

    # cmd kontrolü (eski Frappe uyumluluğu)
    # form_dict bu noktada kurulmuş durumda
    cmd = getattr(frappe.local, "form_dict", {}).get("cmd")
    if cmd in ("login", "logout"):
        return True

    # Prefix eşleşme: login sayfasının ihtiyaç duyduğu kaynaklar
    for prefix in _AUTH_WHITELIST_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


def _complete_init_after_maintenance_bypass(request):
    """
    init_request'in maintenance_mode kontrolünden sonraki
    adımlarını manuel olarak çalıştırır.

    Orijinal init_request'teki sıralama (app.py L177-209):
      1. frappe.local.request = request          ✅ zaten yapıldı
      2. frappe.local.is_ajax                    ✅ zaten yapıldı
      3. frappe.init(site=...)                   ✅ zaten yapıldı
      4. frappe.connect()                        ✅ zaten yapıldı
      5. maintenance_mode kontrolü               ← BURADA SessionStopped yakalandı
      6. max_content_length                      ← bundan sonrası eksik
      7. make_form_dict(request)
      8. HTTPRequest()  (session kurulumu)
      9. before_request hooks
    """
    from frappe.auth import HTTPRequest
    from frappe.utils import cint

    # max_content_length
    if request.path.startswith("/api/method/upload_file"):
        from frappe.core.api.file import get_max_file_size

        request.max_content_length = get_max_file_size()
    else:
        request.max_content_length = (
            cint(frappe.local.conf.get("max_file_size")) or 25 * 1024 * 1024
        )

    # form_dict oluştur
    frappe.app.make_form_dict(request)

    # HTTPRequest: cookie, session, lang, csrf
    if request.method != "OPTIONS":
        frappe.local.http_request = HTTPRequest()

    # before_request hooks
    for before_request_task in frappe.get_hooks("before_request"):
        frappe.call(before_request_task)


def _is_maintenance_bypass_allowed():
    """
    Mevcut kullanıcının maintenance mode'da sisteme erişip
    erişemeyeceğini kontrol eder.

    Bypass kuralları (sırasıyla):
    1. "Administrator" kullanıcısı → her zaman bypass
    2. site_config.maintenance_bypass_roles listesindeki rollere
       sahip kullanıcılar → bypass (varsayılan: ["System Manager"])

    Returns:
        bool: True ise bypass'a izin verilir
    """
    user = getattr(frappe.session, "user", None)

    if not user or user == "Guest":
        return False

    # Administrator her zaman bypass edebilir
    if user == "Administrator":
        return True

    # site_config'den konfigüre edilebilir roller
    # Varsayılan: ["System Manager"]
    bypass_roles = frappe.local.conf.get(
        "maintenance_bypass_roles", ["System Manager"]
    )

    if isinstance(bypass_roles, str):
        bypass_roles = [bypass_roles]

    # Kullanıcının rollerini kontrol et
    user_roles = frappe.get_roles(user)
    return bool(set(bypass_roles) & set(user_roles))


def _check_maintenance_mode_status():
    """
    Sistemin maintenance mode durumunu kontrol eder.
    Eğer mod 'kapalı'dan 'açık' durumuna geçmişse:
    - Veritabanı ve Redis'teki tüm session'ları öldürür.
    Böylece Administrator dahil herkes sistemden atılır ve sadece
    bypass yetkisi olanlar tekrar şifreleriyle girebilir.
    """
    current_mode = int(frappe.local.conf.maintenance_mode or 0)

    # Redis'ten son durumu oku
    last_mode = frappe.cache().get_value("kta_maintenance_mode_status")

    if last_mode is None:
        frappe.cache().set_value("kta_maintenance_mode_status", current_mode)
        return

    last_mode = int(last_mode)

    if current_mode == 1 and last_mode == 0:
        # Maintenance mode yeni AÇILDI!
        frappe.cache().set_value("kta_maintenance_mode_status", 1)

        try:
            from kta_system_utils.kta_system_utils_maintenance.tasks import _force_logout_all
            _force_logout_all()
            logger.info("Maintenance mode activated: All users logged out automatically.")
        except Exception as e:
            logger.error(f"Maintenance mode activation logout failed: {e}")

    elif current_mode == 0 and last_mode == 1:
        # Maintenance mode KAPANDI.
        frappe.cache().set_value("kta_maintenance_mode_status", 0)
        logger.info("Maintenance mode deactivated.")


def prevent_login_if_maintenance(*args, **kwargs):
    """
    on_session_creation hook'una bağlıdır. 
    Kullanıcı şifresini girdiğinde, session oluşturulduktan HEMEN SONRA çalışır.
    Eğer sistem bakım modundaysa ve kullanıcının bypass yetkisi yoksa,
    login işlemini iptal eder ve kullanıcıyı login sayfasında hata mesajıyla bırakır.
    """
    if int(frappe.local.conf.maintenance_mode or 0) == 1:
        if not _is_maintenance_bypass_allowed():
            user = getattr(frappe.session, "user", "Unknown")
            logger.info("Maintenance mode: %s için login reddedildi.", user)

            # Oluşmakta olan session'ı yok et
            if hasattr(frappe.local, "login_manager"):
                frappe.local.login_manager.logout()
            else:
                from frappe.auth import clear_sessions
                clear_sessions(user, keep_current=False)

            frappe.throw(
                "Sistem şu an bakım modundadır. Sadece yetkili kullanıcılar giriş yapabilir.",
                exc=frappe.AuthenticationError
            )
