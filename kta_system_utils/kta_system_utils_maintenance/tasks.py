# kta_system_utils/kta_system_utils_maintenance/tasks.py
#
# Gece bakım görevleri:
#   - Tüm kullanıcı oturumlarını kapatır (force logout)
#   - Redis önbelleğini temizler
#   - __pycache__ / .pyc dosyalarını siler
#   - Browser hard-reload sinyali bırakır

from __future__ import unicode_literals
import os
import subprocess
import frappe

_LOGGER = "kta_system_utils"
_RELOAD_FLAG_KEY = "kta_system_utils_hard_reload_required"
_RELOAD_FLAG_TTL = 24 * 3600  # 24 saat (Tüm gün giriş yapanları kapsar)


def nightly_cache_clear():
    """
    Her gece 01:00'de scheduler tarafından çalıştırılır.

    Sırasıyla:
    1. Tüm aktif kullanıcı oturumlarını sonlandırır (force logout)
    2. Frappe Redis önbelleğini temizler
    3. apps/ altındaki __pycache__ ve .pyc dosyalarını siler
    4. Kullanıcılar sabah giriş yapınca tarayıcıyı hard-reload'a zorlar
    """
    frappe.logger(_LOGGER).info("nightly_cache_clear: Başlatıldı")

    _force_logout_all()
    _clear_redis_cache()
    _clear_pycache()
    _set_hard_reload_flag()

    frappe.logger(_LOGGER).info("nightly_cache_clear: Tamamlandı")


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------

def _force_logout_all():
    """Tüm aktif kullanıcı oturumlarını sonlandırır."""
    try:
        from frappe.sessions import clear_all_sessions
        # clear_all_sessions içinde frappe.only_for("Administrator") kontrolü var
        frappe.set_user("Administrator")
        clear_all_sessions(reason="KTA gece bakım: önbellek temizleme")
        frappe.db.commit()
        frappe.logger(_LOGGER).info("nightly_cache_clear: → Tüm oturumlar kapatıldı")
    except Exception:
        frappe.log_error(
            title="kta_system_utils_maintenance: force_logout hatası",
            message=frappe.get_traceback(),
        )


def _clear_redis_cache():
    """Frappe Redis önbelleğini temizler."""
    try:
        frappe.clear_cache()
        frappe.logger(_LOGGER).info("nightly_cache_clear: → Redis cache temizlendi")
    except Exception:
        frappe.log_error(
            title="kta_system_utils_maintenance: redis_clear hatası",
            message=frappe.get_traceback(),
        )


def _clear_pycache():
    """
    Bench apps/ dizinindeki tüm __pycache__ klasörlerini
    ve .pyc dosyalarını temizler.

    Güvenlik: yalnızca frappe.utils.get_bench_path()/apps/ altı hedeflenir.
    """
    try:
        bench_path = frappe.utils.get_bench_path()
        apps_path = os.path.join(bench_path, "apps")

        if not os.path.isdir(apps_path):
            frappe.logger(_LOGGER).warning(
                f"nightly_cache_clear: apps_path bulunamadı → {apps_path}"
            )
            return

        # __pycache__ klasörlerini sil
        subprocess.run(
            [
                "find", apps_path,
                "-type", "d", "-name", "__pycache__",
                "-exec", "rm", "-rf", "{}", "+",
            ],
            capture_output=True, text=True, timeout=120, check=False,
        )

        # Kalan .pyc dosyalarını sil
        subprocess.run(
            ["find", apps_path, "-name", "*.pyc", "-delete"],
            capture_output=True, text=True, timeout=120, check=False,
        )

        frappe.logger(_LOGGER).info(
            "nightly_cache_clear: → __pycache__ ve .pyc silindi"
        )
    except Exception:
        frappe.log_error(
            title="kta_system_utils_maintenance: pycache_clear hatası",
            message=frappe.get_traceback(),
        )


def _set_hard_reload_flag():
    """
    Redis'e hard-reload sinyali yazar (TTL: 4 saat).
    boot.py bu değeri okur, JS handler tarayıcıyı yeniler.
    """
    try:
        frappe.cache.set_value(
            _RELOAD_FLAG_KEY,
            1,
            expires_in_sec=_RELOAD_FLAG_TTL,
        )
        frappe.logger(_LOGGER).info(
            f"nightly_cache_clear: → {_RELOAD_FLAG_KEY} flag set edildi "
            f"({_RELOAD_FLAG_TTL // 3600} saat)"
        )
    except Exception:
        frappe.log_error(
            title="kta_system_utils_maintenance: flag_set hatası",
            message=frappe.get_traceback(),
        )
