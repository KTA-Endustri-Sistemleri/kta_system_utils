## [1.2.1](https://github.com/KTA-Endustri-Sistemleri/kta_system_utils/compare/v1.2.0...v1.2.1) (2026-10-27)

### ⚡ Performans İyileştirmeleri (Performance)

* **zebra:** optimize printer socket handling and poll interval ([1898b3c](https://github.com/KTA-Endustri-Sistemleri/kta_system_utils/commit/1898b3c017ea06f0371e41f3314f9fc285648d11))

### 🛠️ Refaktör ve Kod Düzenleme (Refactoring)

* **kta_system_utils_maintenance:** replace intrusive monkey-patching for maintenance mode with standard login hook and before_request logic ([46a1dce](https://github.com/KTA-Endustri-Sistemleri/kta_system_utils/commit/46a1dce8b0b5b2859116049e33e6a992718b743e))
* transition cache reload logic from sessionStorage to localStorage using daily keys to prevent repeated reloads ([f5a4bb5](https://github.com/KTA-Endustri-Sistemleri/kta_system_utils/commit/f5a4bb568729dc6b44f03adb6f42398323b8f87d))

## [1.2.0](https://github.com/KTA-Endustri-Sistemleri/kta_system_utils/compare/v1.1.0...v1.2.0) (2026-06-26)

### 🚀 Yeni Özellikler (Features)

* **ci:** configure semantic-release to generate and commit CHANGELOG.md files ([75e2221](https://github.com/KTA-Endustri-Sistemleri/kta_system_utils/commit/75e22212d69f157616ea1e8859d29169baee85d3))
