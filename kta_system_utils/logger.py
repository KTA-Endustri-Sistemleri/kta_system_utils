import logging
import frappe


def get_logger(module: str = "kta_system_utils") -> logging.Logger:
    """Return a logger configured specifically for kta_system_utils.

    The logging level is controlled per-site via site_config.json:
      - To disable INFO/debug logging and mute module logs (sets level to ERROR):
          bench --site <site> set-config kta_system_utils_logging 0
          # or: "kta_system_utils_logging": false in site_config.json
      - To enable logging (default):
          bench --site <site> set-config kta_system_utils_logging 1
      - To specify an explicit level (DEBUG, INFO, WARNING, ERROR, CRITICAL):
          bench --site <site> set-config kta_system_utils_log_level INFO
    """
    logger = frappe.logger(module)

    # Check if logging is explicitly disabled via site_config
    is_enabled = frappe.conf.get("kta_system_utils_logging", True)
    if not is_enabled or is_enabled in (0, "0", "false", "False"):
        logger.setLevel(logging.ERROR)
        return logger

    # Resolve log level from site_config, defaulting to INFO
    level_name = str(frappe.conf.get("kta_system_utils_log_level") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    return logger
