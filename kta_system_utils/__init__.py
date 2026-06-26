__version__ = "1.1.0"

# Maintenance mode bypass: Administrator ve System Manager kullanıcılarının
# maintenance mode sırasında sisteme erişimine izin verir.
# Patch, modül import edildiğinde (worker başlatıldığında) uygulanır.
from kta_system_utils.kta_system_utils_maintenance.maintenance_bypass import (
    apply_patch as _apply_maintenance_bypass,
)

_apply_maintenance_bypass()
