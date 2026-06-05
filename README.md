# KTA System Utils

KTA system maintenance and utility tools for ERPNext / Frappe Framework.

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app kta_system_utils
```

---

## Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/kta_system_utils
pre-commit install
```

Pre-commit is configured to use the following tools:

- ruff
- eslint
- prettier
- pyupgrade

---

## Zebra Printer System

`kta_zebra_utils` modülü; Zebra marka termal yazıcıları ERPNext üzerinden yönetmek, etiket basmak ve yazıcı durumlarını gerçek zamanlı izlemek için tasarlanmış tam kapsamlı bir entegrasyon sistemidir.

### Mimari Genel Bakış

```
┌──────────────────────────────────────────────────────────────┐
│                     ERPNext / Frappe                         │
│                                                              │
│  ┌─────────────────┐     ┌──────────────────────────────┐   │
│  │  KTA Depo        │     │  kta_zebra_indicator.js      │   │
│  │  Etiketleri      │     │  (List/Form View Status UI)  │   │
│  │  (Label DocType) │     └──────────────┬───────────────┘   │
│  └────────┬─────────┘                    │ frappe.call()     │
│           │ print button                 │                   │
│           ▼                              ▼                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │               api.py (Whitelisted)                   │    │
│  │  get_printer_status()  /  get_all_printers_status()  │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│           ┌───────────────▼────────────────┐                │
│           │         ZebraPrinterManager    │                │
│           │  - get_printer_for_user()      │                │
│           │  - format_data()               │                │
│           │  - create_print_log()          │                │
│           └───────────────┬────────────────┘                │
│                           │                                  │
│           ┌───────────────▼────────────────┐                │
│           │           ZebraPrinter         │                │
│           │  - check_connection() [TCP]    │                │
│           │  - get_detailed_status() [~HS] │                │
│           │  - send() / send_batch()       │                │
│           └───────────────┬────────────────┘                │
└───────────────────────────┼──────────────────────────────────┘
                            │ TCP Socket (Port 9100)
                  ┌─────────▼──────────┐
                  │   Zebra Yazıcı     │
                  │  (Ağ üzerinden)    │
                  └────────────────────┘
```

---

### DocType'lar (Veri Modeli)

#### 1. `KTA Zebra Printers` — Yazıcı Tanımları

Ağdaki tüm fiziksel Zebra yazıcılarının kayıt defteri.

| Alan          | Tip  | Açıklama                                |
|---------------|------|-----------------------------------------|
| `printer_name`| Data | Yazıcının benzersiz adı (ör: `Ckprt 001`) — aynı zamanda `name` alanıdır |
| `ip`          | Data | Yazıcının yerel ağ IP adresi (ör: `192.168.1.50`) |
| `port`        | Int  | TCP portu. Zebra'nın standart varsayılanı `9100`'dür |

> **Not:** DocType `is_submittable: true` olarak tanımlıdır; yazıcı kayıtları gönderilip (Submit) kilitlenebildiğinden üretim ortamında yanlışlıkla düzenlenmesi önlenir.

---

#### 2. `KTA User Zebra Printers` — Kullanıcı Yazıcı Ataması

Her Frappe kullanıcısı için varsayılan ve yedek (fallback) yazıcı tanımı. `user` alanına göre adlandırılır; bir kullanıcı yalnızca bir aktif kayda sahip olabilir.

| Alan               | Tip   | Açıklama                                         |
|--------------------|-------|--------------------------------------------------|
| `user`             | Link  | Frappe kullanıcısı — benzersiz, birincil anahtar |
| `printer`          | Link  | Varsayılan yazıcı (`KTA Zebra Printers`)         |
| `fallback_printer` | Link  | Yedek yazıcı — birincil erişilemediğinde devreye girer |
| `disabled`         | Check | `1` olduğunda bu kullanıcı ataması devre dışı bırakılır |

---

#### 3. `KTA Printer Permission` — Rol Bazlı Erişim Kontrolü

Hangi Frappe rolünün hangi yazıcıyı kullanabileceğini tanımlar.

| Alan        | Tip   | Açıklama                              |
|-------------|-------|---------------------------------------|
| `printer`   | Link  | Hedef yazıcı (`KTA Zebra Printers`)  |
| `role`      | Link  | Frappe rolü                           |
| `can_print` | Check | Bu role yazdırma yetkisi ver/kaldır   |

> **Önemli Kural:** Bir yazıcı için `KTA Printer Permission` kaydı **yoksa**, sistem o yazıcıyı herkese açık kabul eder. Kısıtlama ancak en az bir kayıt girildiğinde devreye girer.

---

#### 4. `KTA Zebra Templates` — ZPL Şablonları

Farklı etiket türleri için ZPL (Zebra Programming Language) şablonlarını saklar. `doctype_name` alanına göre adlandırılır ve 1 saatlik Redis cache'e alınır.

| Alan            | Tip  | Açıklama                                          |
|-----------------|------|---------------------------------------------------|
| `doctype_name`  | Data | Eşleştiği ERPNext DocType adı (ör: `KTA Depo Etiketleri`) |
| `zebra_template`| Text | Python `str.format()` sözdiziminde ZPL kodu. Değişkenler `{data.field_name}` biçiminde tanımlanır |

**ZPL Şablonu Değişken Sözdizimi:**

```zpl
^FD{data.material_number}^FS
^FD{data.batch_no}^FS
^FD{data.qty}^FS
```

Şablon, `ZebraPrinterManager.format_data(doctype_name, data)` ile işlenir; `data` nesnesi bir Python sözlüğü/nesnesidir.

---

#### 5. `KTA Print Log` — Yazdırma Geçmişi

Her yazdırma girişiminin (başarılı veya başarısız) otomatik denetim kaydı. Format: `PRL-{YY}-{MM}-{#####}`.

| Alan            | Tip       | Açıklama                                        |
|-----------------|-----------|-------------------------------------------------|
| `label_doctype` | Data      | Etiketi oluşturan DocType (ör: `KTA Depo Etiketleri`) |
| `label_name`    | DynLink   | Belgenin `name` değeri                          |
| `printer`       | Link      | Hangi yazıcıya gönderildi                       |
| `user`          | Link      | İsteği başlatan kullanıcı                       |
| `status`        | Select    | `Pending` / `Success` / `Failed`                |
| `attempted_at`  | Datetime  | Deneme zamanı                                   |
| `error_message` | Small Text| Hata varsa detayı                               |
| `zpl_payload`   | Text      | Gönderilen ZPL'nin ilk 500 karakteri            |

---

#### 6. `KTA Depo Etiketleri` — Depo/GR Etiketi

Satın alma makbuzu (Purchase Receipt) bazlı etiket DocType'ı. Kullanıcı bu formu açar ve "Etiketi Bas" butonuna basar.

**Öne Çıkan Alanlar:**

| Alan                    | Açıklama                                        |
|-------------------------|-------------------------------------------------|
| `gr_number`             | İlgili Purchase Receipt                         |
| `batch`                 | Parti numarası                                  |
| `qty` / `uom`           | Miktar ve birim                                 |
| `do_not_split`          | İşaretlenirse etiket bölünmeden tek parça basılır |
| `table_gydm`            | `KTA Depo Etiketleri Bolme` child tablosu — parçalı bölme için satırlar |
| `print_count`           | Toplam kaç kez basıldığı (read-only)            |
| `last_printed_at/by`    | Son baskı zamanı ve kullanıcısı (read-only)     |

---

### Sistem Akışları

#### A. Etiket Yazdırma Akışı

```
Kullanıcı → "Etiketi Bas" butonu
      │
      ▼
ZebraPrinterManager.get_printer_for_user(user)
      │
      ├─► KTA User Zebra Printers tablosunu sorgula
      │
      ├─► Kullanıcının PRIMARY yazıcısını al
      │       └─► _user_can_print() ile yetki kontrol et
      │               └─► KTA Printer Permission tablosunu sorgula
      │                       (Kayıt yoksa → Herkese açık)
      │
      ├─► ZebraPrinter.check_connection() — TCP Soket testi (3 sn timeout)
      │       ├─► Başarılı → Yazıcıyı döndür
      │       └─► Başarısız → FALLBACK DEVREYe GiRER ▼
      │
      ├─► Fallback yazıcı var mı? → _user_can_print() kontrolü
      │       └─► Evet → Fallback yazıcıyı döndür + kullanıcıya bildirim (msgprint)
      │
      ▼
ZebraPrinterManager.format_data(doctype, data)
      └─► Redis cache'ten ZPL şablonunu al (cache yoksa DB'den çek, 1 saat cache'le)
      └─► Python str.format() ile değişkenleri yerleştir → ZPL string oluşur
      │
      ▼
ZebraPrinter.send(zpl) veya send_batch([zpl, ...])
      └─► TCP soket açılır → ZPL string yazıcıya gönderilir → soket kapatılır
      └─► KTA Print Log kaydı oluşturulur (Success veya Failed)
```

#### B. Yedek Yazıcı (Fallback) Karar Ağacı

```
PRIMARY yazıcıya yetkin var mı?
    │
    ├── HAYIR ──► FALLBACK yazıcıya yetkin var mı?
    │                 ├── EVET → Fallback yazıcıyı kullan
    │                 └── HAYIR → return None (yazdırma iptal)
    │
    └── EVET → PRIMARY yazıcıya bağlantı açılabiliyor mu?
                  ├── EVET → PRIMARY yazıcıyı kullan ✓
                  └── HAYIR → FALLBACK yazıcı tanımlı mı?
                                  ├── EVET → Fallback yazıcıya yetkin var mı?
                                  │             ├── EVET → Fallback'i kullan + kullanıcıya uyarı
                                  │             └── HAYIR → Yetki uyarısı, return None
                                  └── HAYIR → "Yedek yazıcı yok" uyarısı, PRIMARY döner
                                              (Hata logu oluşturulur; kim, neye gitmeye çalıştı bilinir)
```

> **Önemli Sınır:** Fallback sistemi **yalnızca ağ bağlantısına** (TCP soket) bakar. Yazıcı açık fakat kağıt bitmişse veya kapağı açıksa ağ yanıtlamaya devam ettiği için fallback **devreye girmez**. Donanımsal durum bazlı fallback için `get_detailed_status()` sonucuna göre genişletme yapılabilir.

---

#### C. Yazıcı Durum Sorgulama Akışı (`~HS` Protokolü)

Zebra yazıcılar, `~HS` (Host Status) ZPL komutu ile makine durumunu 3 ayrı satır (String) olarak döner.

```
Frappe → TCP Soket aç → "~HS" gönder → Yanıtı oku → Soket kapat
                                              │
                                              ▼
                               _parse_hs_response(response)
                                              │
                              Yanıt 3 satır: STX...ETX formatında
                                              │
                         ┌────────────────────┴──────────────────────┐
                         │  String 1 (lines[0])                      │
                         │  index[1] = Media Out (Kağıt Bitti)       │
                         │  index[2] = Pause Status (Duraklatıldı)   │
                         └────────────────────┬──────────────────────┘
                         ┌────────────────────┴──────────────────────┐
                         │  String 2 (lines[1])                      │
                         │  index[2] = Head Open (Kapak Açık)        │
                         │  index[3] = Ribbon Out (Ribon Bitti)      │
                         └────────────────────┬──────────────────────┘
                                              │
                              Öncelik sırası (ilk eşleşen döner):
                              1. Kapak Açık  → 🟠 orange  "Kapak Açık"
                              2. Kağıt Bitti → 🟠 orange  "Kağıt Bitti"
                              3. Ribon Bitti → 🟠 orange  "Ribon Bitti"
                              4. Duraklatıldı→ 🟡 yellow  "Duraklatıldı"
                              5. (Hiçbiri)   → 🟢 green   "Yazıcı Hazır"
                              Bağlanamıyorsa → 🔴 red     "Erişilemiyor (Offline)"
```

**Renk Referans Tablosu:**

| Durum             | `status`    | `color`  | `message`                   |
|-------------------|-------------|----------|-----------------------------|
| Yazıcı hazır      | `Ready`     | `green`  | Yazıcı Hazır                |
| Kağıt bitti       | `Media Out` | `orange` | Kağıt Bitti                 |
| Kapak açık        | `Head Open` | `orange` | Kapak Açık                  |
| Ribon bitti       | `Ribbon Out`| `orange` | Ribon Bitti                 |
| Duraklatıldı      | `Paused`    | `yellow` | Duraklatıldı                |
| Ağa bağlanamıyor  | `Offline`   | `red`    | Erişilemiyor (Offline)      |
| Genel hata        | `Error`     | `red`    | Sorgu Hatası: ...           |

---

### Toplu İşlem: Paralel Durum Sorgulama

Liste görünümünde tüm yazıcıların durumu `get_all_printers_status()` API'si ile **paralel** olarak sorgulanır.

```python
# api.py — Basitleştirilmiş gösterim
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(check, printers)
```

**Thread-Safety Notu:** Tüm veritabanı sorguları (`frappe.get_all`) ana thread'de çalıştırılır ve her thread'e yalnızca saf Python nesneleri geçilir. Bu sayede Frappe'nin DB context'i thread'ler arası sızıntıya karşı korunur.

---

### Frontend: Gerçek Zamanlı Durum Göstergesi

`kta_zebra_indicator.js` dosyası iki farklı davranış içerir:

#### Liste Görünümü (`frappe.listview_settings`)

```
Kullanıcı listeye girer (refresh tetiklenir)
      │
      ▼
fetch_and_update() çalışır
      │
      ├─► Sayfa hala liste görünümü mü? (frappe.get_route() kontrolü)
      │       └─► HAYIR → Döngü durur (setInterval yerine setTimeout — sunucu yük koruması)
      │
      ├─► get_all_printers_status() API çağrısı
      │
      ├─► Yanıt gelir → Sayfa hala liste mi? (ikinci kontrol — async race condition önlemi)
      │
      ├─► $('.list-row-container') DOM elemanları bulunur
      │       └─► Her satırdaki .list-row-checkbox[data-name] okunur
      │               └─► decodeURIComponent() ile URL-encode çözülür (Frappe v15 uyumu)
      │               └─► .indicator-pill className ve içeriği doğrudan güncellenir
      │
      └─► 5 saniye sonra tekrar çalıştır (setTimeout — önceki istek bitince başlar)
```

> **Neden `setInterval` değil `setTimeout`?** Bir Zebra yazıcı çevrimdışıysa bağlantı denemeleri 3 saniye `timeout` süresi boyunca bloke olur. `setInterval` kullanılırsa istekler üst üste binip Gunicorn worker'larını tüketerek tüm sistemi yavaşlatır. Ardışık `setTimeout` bu riski ortadan kaldırır.

> **Neden `onload` değil `refresh`?** Frappe SPA (Single Page Application) mimarisinde, kullanıcı form görünümünden listeye geri döndüğünde `onload` yeniden tetiklenmez. `refresh` hook'u her sayfa geçişinde çalışır, böylece timer her zaman temiz bir şekilde yeniden başlar.

#### Form Görünümü (`frappe.ui.form.on`)

Form açıldığında ve "Durumu Güncelle" butonuna basıldığında `get_printer_status()` API'si çağrılır; sonuç form başlığında gösterge (indicator) ve intro banner olarak gösterilir.

---

### Mock / Test Modu

`site_config.json` dosyasına aşağıdaki ayar eklenirse gerçek yazıcıya hiç bağlantı kurulmaz; ZPL çıktısı Frappe Error Log'a yazılır:

```json
{
  "use_mock_zebra_printer": 1
}
```

Otomatik testler (`frappe.flags.in_test`) sırasında da mock mod otomatik olarak aktif olur.

---

### Konfigürasyon Adımları (Sıfırdan Kurulum)

1. **Yazıcıları tanımla** — `KTA Zebra Printers` listesine her yazıcı için `printer_name`, `ip`, `port` (genellikle 9100) gir.

2. **Kullanıcılara yazıcı ata** — `KTA User Zebra Printers` listesine her kullanıcı için:
   - `user` → Frappe kullanıcısı
   - `printer` → Birincil yazıcı
   - `fallback_printer` → (Opsiyonel) Yedek yazıcı

3. **Erişim kısıtlaması koy** *(opsiyonel)* — `KTA Printer Permission` listesine yazıcı + rol çiftleri ekle. Bu adım yapılmazsa tüm yazıcılar herkese açık kalır.

4. **ZPL şablonu ekle** — `KTA Zebra Templates` listesine DocType bazında ZPL şablonu ekle. `doctype_name` değeri Python kodundaki `format_data()` çağrısıyla eşleşmelidir.

5. **Bağlantıyı doğrula** — `KTA Zebra Printers` liste görünümünü aç; tüm yazıcılar 5-10 saniye içinde gerçek durumlarıyla (Yazıcı Hazır / Kapak Açık vb.) listelenmelidir.

---

### Bilinen Sınırlamalar

| Sınırlama | Açıklama |
|-----------|----------|
| Fallback yalnızca ağ tabanlı | Kağıt bittiğinde ağ bağlantısı devam ettiğinden fallback tetiklenmez |
| ZPL şablon cache | Şablonda değişiklik yapıldıktan sonra Redis cache'i temizlemek gerekir: `bench --site <site> clear-cache` |
| Port 9100 varsayılanı | Zebra endüstri standardıdır; farklı bir port kullanılıyorsa her yazıcı kaydında açıkça belirtilmelidir |
| Timeout 3 saniye | `ZebraPrinter.__init__` içinde `self.timeout = 3` sabit kodludur; çok sayıda çevrimdışı yazıcı olduğunda bu süre durum sorgulamasını yavaşlatabilir |

---

## License

MIT
