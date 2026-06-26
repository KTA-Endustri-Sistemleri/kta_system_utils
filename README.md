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

> **Cache Otomatik Geçersizleştirme:** `KTA Zebra Templates` kaydı kaydedildiğinde (`on_update` hook) ilgili cache anahtarı otomatik olarak silinir. Manuel cache temizlemeye gerek yoktur.

---

#### 5. `KTA Print Log` — Yazdırma Geçmişi

Her yazdırma girişiminin (başarılı veya başarısız) otomatik denetim kaydı. Format: `PRL-{YY}-{MM}-{#####}`.

| Alan            | Tip       | Açıklama                                        |
|-----------------|-----------|-------------------------------------------------|
| `label_doctype` | Data      | Etiketi oluşturan DocType (ör: `KTA Depo Etiketleri`) |
| `label_name`    | DynLink   | Belgenin `name` değeri                          |
| `printer`       | Link      | Hangi yazıcıya gönderildi                       |
| `user`          | Link      | İsteği başlatan kullanıcı                       |
| `status`        | Select    | `Pending` / `Success` / `Failed` / `Retried`    |
| `attempted_at`  | Datetime  | Deneme zamanı                                   |
| `error_message` | Small Text| Hata varsa detayı                               |
| `zpl_payload`   | Text      | Gönderilen ZPL'nin ilk 500 karakteri            |

**Durum Anlamları:**

| Durum     | Açıklama |
|-----------|----------|
| `Pending` | Kuyrukta bekliyor, worker henüz işlemedi |
| `Success` | Yazıcıya başarıyla gönderildi |
| `Failed`  | Gönderim başarısız (hata detayı `error_message` alanında) |
| `Retried` | Print Queue sayfasından manuel yeniden deneme yapıldı; yeni bir `Success`/`Failed` logu üretilir |

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
      ├─► send()       → Tek ZPL, tek TCP bağlantısı
      └─► send_batch() → Liste, BATCH_CHUNK_SIZE (10) adetlik gruplara bölünür
              └─► Her grup için _send_single_chunk() — ayrı TCP bağlantısı
              └─► Her etiket için KTA Print Log kaydı (Success veya Failed)
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

#### D. Uygulama ve Entegrasyon Sınırları (`kta_system_utils` vs `erpnextkta`)

**ÖNEMLİ MİMARİ NOT:** `kta_system_utils` uygulaması; Purchase Receipt (Satınalma Kabul), Stock Entry (Repack/Üretim) gibi ERPNext modüllerinin iş kurallarından tamamen bağımsızdır. `kta_system_utils` sadece bir **donanım sürücüsü, yazdırma kuyruğu ve ZPL derleyicisi** olarak görev yapar.

Akıllı etiketleme ve parti bölme (Batch Split) kurgularının sistemdeki yerleşimi şu şekildedir:

1. **`kta_system_utils` (Bu Uygulama) Neler Yapar?**
   - TCP Soket yönetimi ve yazıcı durumlarının (Hazır, Kapak Açık) izlenmesi.
   - `ZebraPrinterManager` sınıfı üzerinden gelen rastgele JSON/Dict verilerini ZPL şablonlarıyla harmanlayıp yazıcıya yollamak.
   - Print Log ve yetkilendirme (Rol/Kullanıcı) denetimlerini sağlamak.
   - Herhangi bir ERPNext belgesi (Invoice, Delivery Note vb.) bu modülü çağırarak kendi özel etiketini bastırabilir.

2. **`erpnextkta` / `kta_stock` Modülü Neler Yapar? (İş Kuralları)**
   - **`KTA Stock Label`** (`KTA Depo Etiketleri`) DocType'ını barındırır.
   - **Batch Split (Akıllı Parti Bölme):** Purchase Receipt onaylandığında `custom_split_qty` değerine göre veya Stock Entry (Repack/Manufacture) işlemlerinde *Item Customer Detail* tablosundaki `musteri_paketleme_miktari` değerine göre alt partileri oluşturmak.
   - **Kalite Kontrol (Quality Inspection):** Ürün Kalite Kontrol'e tabiyse etiket basımını bekletmek ve ancak QI belgesi onaylandıktan sonra etiket sürecini tetiklemek.
   - **Veri Fallback (Geri Dönüş):** Taslak (Draft) halindeki belgelerde eksik olan parti numaralarını kaynak (Source) satırlardan bularak etiket veri sözlüğünü (dictionary) hazırlamak.

Kısacası; `kta_stock` modülü "Hangi etiketin ne zaman ve nasıl (kaç parçaya bölünerek) basılacağına" karar veren beyindir, `kta_system_utils` ise sadece kendisine verilen emri kağıda döken kas gücüdür.

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

### Toplu Gönderim: `send_batch` ve Chunk Mimarisi

Çok sayıda etiketin tek seferde basılması gerektiğinde `ZebraPrinter.send_batch()` kullanılır. Zebra yazıcıların TCP alım tamponu (~32 KB) sınırlı olduğundan büyük listelerde sessiz veri kaybı yaşanabilir. Bu riski önlemek için gönderim `BATCH_CHUNK_SIZE = 10` adetlik parçalara bölünür:

```
send_batch([zpl_1, zpl_2, ..., zpl_35])
      │
      ├─► Chunk 1: [zpl_1  … zpl_10]  → _send_single_chunk() → TCP bağlantısı 1
      ├─► Chunk 2: [zpl_11 … zpl_20]  → _send_single_chunk() → TCP bağlantısı 2
      ├─► Chunk 3: [zpl_21 … zpl_30]  → _send_single_chunk() → TCP bağlantısı 3
      └─► Chunk 4: [zpl_31 … zpl_35]  → _send_single_chunk() → TCP bağlantısı 4
```

- Bir chunk'ta bağlantı hatası oluşursa **yalnızca o chunk** Failed loglanır; diğer chunk'lar etkilenmez.
- `BATCH_CHUNK_SIZE` sınıf seviyesinde sabittir; ihtiyaca göre değiştirilebilir.

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

### KTA Print Queue Sayfası

`/app/kta-print-queue` adresinden erişilen bu Frappe Page, yazıcı sisteminin merkezi izleme ve müdahale ekranıdır.

#### Sayfa Bölümleri

**1. İstatistik Kartları (üst şerit)**

`get_queue_stats()` API'si ile her 60 saniyede bir yenilenir:

| Kart | Açıklama |
|------|----------|
| Bugün Başarılı | Günlük `Success` log sayısı |
| Bugün Başarısız | Günlük `Failed` log sayısı |
| Bekleyen | Günlük `Pending` log sayısı |
| Yeniden Denenen | Günlük `Retried` log sayısı |

**2. Yazıcı Durum Şeridi**

Paralel `~HS` sorgusu ile tüm yazıcıların anlık durumu renk kodlu badge olarak gösterilir. 60 saniyede bir otomatik güncellenir.

**3. Bekleyen İşler Tablosu**

`status = Pending` kayıtları listelenir. Her satırda **İptal Et** butonu bulunur; butona basıldığında log `Failed` durumuna geçer.

**4. Son Başarısız İşler Tablosu**

`status = Failed` veya `Retried` kayıtları listelenir. Her satırda **Yeniden Dene** butonu bulunur:
- `KTA Depo Etiketleri` tipi → `reprint_depo_label()` kuyruğa alınır
- `Stock Entry` tipi → `print_kta_wo_labels_of_stock_entry()` kuyruğa alınır
- Eski log `Retried` durumuna geçer; başarı/hata yeni bir log kaydıyla izlenir

#### Yenileme Döngüleri

| Bileşen | Interval | Yöntem |
|---------|----------|--------|
| Bekleyen/Başarısız tablolar | 15 saniye | `setInterval` |
| İstatistik kartları + yazıcı durumu | 60 saniye | `setInterval` |

Sayfa görünümden ayrıldığında (`destroyed`) her iki interval da temizlenir.

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
| ZPL şablon cache | Şablon kaydedildiğinde cache **otomatik** temizlenir (`on_update` hook). Manuel müdahale gerekmez. |
| Port 9100 varsayılanı | Zebra endüstri standardıdır; farklı bir port kullanılıyorsa her yazıcı kaydında açıkça belirtilmelidir |
| Timeout 3 saniye | `ZebraPrinter.__init__` içinde `self.timeout = 3` sabit kodludur; çok sayıda çevrimdışı yazıcı olduğunda bu süre durum sorgulamasını yavaşlatabilir |
| Batch chunk boyutu | `BATCH_CHUNK_SIZE = 10` sınıf sabitidir. Yazıcı modeline göre optimal değer değişebilir; gerekirse kod içinde ayarlanabilir |

---

## System Notification System

`kta_system_utils_notification` modülü; ERPNext içerisinde kullanıcılara, rollere veya departmanlara özel hedeflenmiş duyuru ve bildirimlerin merkezi olarak yönetilmesini sağlayan bir altyapıdır. Asenkron çalışma prensibi (Redis Queue) ve oturum başlatma (Boot Session) entegrasyonu ile sistemi yormadan çalışır.

### Mimari Genel Bakış

```text
┌──────────────────────────────────────────────────────────────┐
│                     ERPNext / Frappe                         │
│                                                              │
│  ┌─────────────────┐     ┌──────────────────────────────┐   │
│  │  KTA System      │     │  kta_system_notification_    │   │
│  │  Notification    │     │  popup.js (Client Script)    │   │
│  │  (DocType)       │     └──────────────▲───────────────┘   │
│  └────────┬─────────┘                    │ bootinfo (JSON)   │
│           │ submit                       │                   │
│           ▼                              │                   │
│  ┌───────────────────────────────────────┴─────────────┐    │
│  │               Redis Background Worker               │    │
│  │  send_notifications_in_background()                 │    │
│  │  - Hedef Kitle (Role/Dept/User) Çözümleme           │    │
│  │  - Action Link Enjeksiyonu                          │    │
│  │  - Notification Log Oluşturma                       │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│           ┌───────────────▼────────────────┐                │
│           │            boot.py             │                │
│           │  - boot_session() hook         │                │
│           │  - Geçerli bildirimleri filtrele│                │
│           └────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────┘
```

### DocType'lar (Veri Modeli)

#### 1. `KTA System Notification` — Ana Bildirim Formu

Sistem yöneticilerinin yeni bildirim oluşturduğu ana DocType'tır. `is_submittable: true` olarak yapılandırılmıştır; bildirimler yalnızca "Submit" edildiğinde işleme alınır.

| Alan            | Tip      | Açıklama                                      |
|-----------------|----------|-----------------------------------------------|
| `subject`       | Data     | Bildirim Başlığı                              |
| `message`       | Text Editor| Zengin metin destekli mesaj içeriği           |
| `type`          | Select   | Info, Success, Warning, Error (Renk kodlaması)|
| `audience_type` | Select   | All System Users, Specific Roles, Specific Departments, Specific Users |
| `action_label`  | Data     | (Opsiyonel) Yönlendirme butonu etiketi        |
| `action_link`   | Data     | (Opsiyonel) Yönlendirme butonu URL'si         |
| `show_on_login` | Check    | İşaretlenirse kullanıcı her giriş yaptığında gösterilir |
| `from_date` / `to_date` | Date | `show_on_login` için geçerlilik tarih aralığı |

#### 2. Hedefleme Tabloları (Child DocTypes)
- `KTA Notification Target Role`: Role göre hedefleme.
- `KTA Notification Target Dept`: Departmana göre hedefleme (ERPNext `Employee` kayıtları üzerinden departman - kullanıcı eşleştirmesi yapılır).
- `KTA Notification Target User`: Spesifik kullanıcılara göre hedefleme.

---

### Sistem Akışları

#### A. Arkaplan Gönderim Akışı (Background Processing)

Kullanıcı arayüzünü (UI) bloklamamak adına, bildirimler "Submit" edildiğinde doğrudan işlenmez; `frappe.enqueue` aracılığıyla Redis işçi kuyruğuna (Worker Queue) gönderilir.

1. **Hedef Kitle Çözümleme:** Sistem seçilen hedefleme tipine göre (`All System Users`, `Specific Roles`, `Specific Departments`, `Specific Users`) sistemdeki tüm aktif kullanıcıları tarar ve bir havuz oluşturur. (Yalnızca `enabled: 1` ve `user_type: "System User"` olanlar).
2. **Mesaj Hazırlama:** Eğer `action_link` tanımlanmışsa, mesajın sonuna HTML formatında tıklanabilir bir Call-to-Action butonu enjekte edilir.
3. **Dağıtım:** Hedeflenen her bir kullanıcı için Frappe'nin yerleşik `Notification Log` tablosuna kayıt atılır. Bu sayede kullanıcılar standart "Çan" (Bell) ikonunda bu bildirimleri görebilir.

#### B. Oturum Başlatma (Boot Session) Enjeksiyonu

Belirli bir tarih aralığı boyunca kullanıcıya her girişinde zorunlu olarak gösterilmesi istenen bildirimler için `show_on_login` özelliği kullanılır.

1. `kta_system_utils/hooks.py` içerisindeki `extend_boot_session` listesi üzerinden `boot.py` tetiklenir.
2. Oturum açan kullanıcının rolleri kontrol edilir ve aktif tarih aralığındaki (`from_date` - `to_date`) onaylanmış bildirimler sorgulanır.
3. Kullanıcının görmeye yetkili olduğu bildirimler JSON formatında Frappe `bootinfo` nesnesine eklenir.

#### C. Popup Gösterimi (Frontend)

`kta_system_notification_popup.js` istemci betiği, sayfa yüklendiğinde `frappe.boot.kta_system_notifications` objesini okur.
Birden fazla bildirim olması durumunda, UI'ın üst üste binmesini engellemek amacıyla bildirimler 2'şer saniyelik gecikmelerle (staggered delay) ekranda `frappe.msgprint` alertleri olarak gösterilir.

#### D. Temizlik (Cleanup) Akışı

Eğer yayınlanmış bir bildirim iptal (Cancel) edilirse, `on_cancel` olay dinleyicisi tetiklenir. Sistem, bu bildirime ait oluşturulmuş tüm `Notification Log` kayıtlarını veritabanından siler ve kullanıcıların okunmamış bildirim (çan) sayaçları otomatik olarak temizlenir.

---

## System Maintenance

`kta_system_utils_maintenance` modülü; gece bakım görevleri (cache temizleme, oturum sonlandırma) ve maintenance mode sırasında yetkili kullanıcılara erişim izni sağlayan altyapıyı içerir.

### Mimari Genel Bakış

```text
┌──────────────────────────────────────────────────────────────┐
│                     ERPNext / Frappe                         │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         __init__.py (app import sırasında)          │    │
│  │    apply_patch() → frappe.app.init_request wrap     │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────┐    │
│  │         maintenance_bypass.py (Monkey-Patch)        │    │
│  │  - SessionStopped yakalama                          │    │
│  │  - Session kurulumu sonrası rol kontrolü            │    │
│  │  - Admin/System Manager bypass izni                 │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────┐    │
│  │                   tasks.py (Scheduler)              │    │
│  │  nightly_cache_clear() — Her gece 01:00             │    │
│  │  - Force logout all users                           │    │
│  │  - Redis cache temizleme                            │    │
│  │  - __pycache__ / .pyc silme                         │    │
│  │  - Hard-reload flag (Redis, 4 saat TTL)             │    │
│  └────────────────────────┬────────────────────────────┘    │
│                           │                                  │
│  ┌────────────────────────▼────────────────────────────┐    │
│  │                   boot.py (Boot Session)            │    │
│  │  - Hard-reload sinyalini bootinfo'ya ekle           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         cache_reload_handler.js (Frontend)          │    │
│  │  - bootinfo'daki flag'i oku                         │    │
│  │  - Gerekiyorsa tarayıcıyı hard-reload et           │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

---

### 1. Gece Bakım Görevi (Nightly Cache Clear)

Her gece 01:00'de scheduler tarafından `nightly_cache_clear()` fonksiyonu çalıştırılır ve aşağıdaki işlemleri sırasıyla yapar:

| Adım | İşlem | Açıklama |
|------|-------|----------|
| 1 | `_force_logout_all()` | Tüm aktif kullanıcı oturumlarını sonlandırır |
| 2 | `_clear_redis_cache()` | Frappe Redis önbelleğini temizler |
| 3 | `_clear_pycache()` | `apps/` altındaki `__pycache__` ve `.pyc` dosyalarını siler |
| 4 | `_set_hard_reload_flag()` | Redis'e hard-reload sinyali yazar (4 saat TTL) |

**Hard-Reload Akışı:**

```
Gece 01:00 → nightly_cache_clear()
      │
      ├─► Redis'e flag yaz: kta_system_utils_hard_reload_required = 1 (TTL: 4 saat)
      │
      ▼
Sabah kullanıcı giriş yapar
      │
      ├─► boot.py → bootinfo'ya flag eklenir
      │
      ├─► cache_reload_handler.js → flag'i okur
      │       └─► Flag = 1 → location.reload(true) ile hard-reload
      │
      └─► Kullanıcı güncel asset'lerle çalışmaya başlar
```

---

### 2. Maintenance Mode Bypass (Yetkili Kullanıcı Erişimi)

#### Problem

Frappe'de `maintenance_mode=1` olduğunda `init_request()` fonksiyonunda `SessionStopped` exception'ı fırlatılır. Bu kontrol, kullanıcı session'ı kurulmadan **önce** yapıldığı için kullanıcının kim olduğu bilinmez ve **tüm kullanıcılar** engellenir — Administrator dahil.

Bunun yanı sıra, Frappe varsayılanında bakım modu açıldığında eski oturumlar aktif kalır.

#### Çözüm: Anında Logout & Monkey-Patch

`kta_system_utils` modülü import edildiğinde (her worker başlatıldığında) `frappe.app.init_request` fonksiyonu monkey-patch ile wrap edilir.

**Otomatik Temizlik (Forced Logout & Cache Clear):** Modun açıldığı (0'dan 1'e geçtiği) an tespit edilerek `_force_logout_all()` tetiklenir. Administrator dahil sistemdeki tüm kullanıcıların oturumları silinir ve kullanıcılar anında `/login` sayfasına yönlendirilir.

**Tarayıcı Temizliği (Frontend):** Kullanıcılar login sayfasına düştüklerinde `kta_login_cleanup.js` scripti çalışır ve Frappe'nin tarayıcıda tuttuğu `localStorage` ve `sessionStorage` kalıntılarını sıfırlar.

```
Request → patched init_request → SessionStopped yakalanır
→ Session kurulur → Rol kontrolü
    ├─► Admin veya System Manager ise → ✅ Erişim verilir
    └─► Değilse → ❌ SessionStopped yeniden fırlatılır
```

#### Detaylı Akış

```
Request gelir
      │
      ▼
_patched_init_request(request)
      │
      ├─► Orijinal init_request() çalıştırılır
      │       ├─► maintenance_mode kapalı → Normal akış, patch devreye girmez
      │       └─► maintenance_mode açık → SessionStopped fırlatılır
      │
      ▼
SessionStopped yakalanır (except bloğu)
      │
      ├─► _complete_init_after_maintenance_bypass(request)
      │       ├─► max_content_length ayarla
      │       ├─► make_form_dict(request)
      │       ├─► HTTPRequest() → Session + Cookie + Auth kurulur
      │       └─► before_request hooks çalıştırılır
      │
      ▼
_is_maintenance_bypass_allowed()
      │
      ├─► frappe.session.user == "Administrator" → ✅ Her zaman bypass
      │
      ├─► site_config.maintenance_bypass_roles kontrol edilir
      │       (varsayılan: ["System Manager"])
      │       └─► Kullanıcının rolleri ile kesişim var mı?
      │               ├─► EVET → ✅ Bypass izni verilir
      │               └─► HAYIR → ❌ SessionStopped yeniden fırlatılır
      │
      ▼
Erişim modu belirlenir:
      ├─► maintenance_bypass_full_access = true → Full access (yazma dahil)
      └─► maintenance_bypass_full_access = false → Read-only mode (varsayılan)
```

#### Bypass Kuralları

| Kullanıcı | Bypass İzni | Açıklama |
|-----------|-------------|----------|
| `Administrator` | ✅ Her zaman | Sabit kodlu, konfigürasyona bağlı değil |
| System Manager rolü | ✅ Varsayılan | `maintenance_bypass_roles` ile konfigüre edilebilir |
| Diğer roller | ❌ Engellenir | `maintenance_bypass_roles`'a eklenmediği sürece |
| Guest | ❌ Her zaman | Session kurulsa bile bypass yapılamaz |

---

### Konfigürasyon

#### Otomatik Kurulum

App yüklendiğinde (`bench install-app kta_system_utils`) `after_install` hook'u çalışır ve aşağıdaki ayarlar `site_config.json`'a **otomatik eklenir**. Mevcut değerler varsa üzerine yazılmaz.

#### site_config.json Ayarları

```json
{
  "maintenance_bypass_roles": ["System Manager"],
  "maintenance_bypass_full_access": false
}
```

| Ayar | Tip | Varsayılan | Açıklama |
|------|-----|------------|----------|
| `maintenance_bypass_roles` | list veya string | `["System Manager"]` | Maintenance mode'da bypass izni olan Frappe rolleri |
| `maintenance_bypass_full_access` | boolean | `false` | `true` ise bypass eden kullanıcılar yazma dahil tam erişime sahip olur. `false` ise read-only mode'da çalışır |

**Örnekler:**

```json
// Sadece System Manager (varsayılan):
{
  "maintenance_bypass_roles": ["System Manager"]
}

// Birden fazla rol:
{
  "maintenance_bypass_roles": ["System Manager", "IT Support"]
}

// String olarak tek rol:
{
  "maintenance_bypass_roles": "System Manager"
}

// Full access (yazma dahil):
{
  "maintenance_bypass_roles": ["System Manager"],
  "maintenance_bypass_full_access": true
}
```

---

### Loglama

Maintenance mode bypass işlemleri Python logger üzerinden loglanır (`kta_system_utils` logger):

| Durum | Log Seviyesi | Mesaj Formatı |
|-------|-------------|---------------|
| Bypass — Read-Only | INFO | `Maintenance bypass: READ-ONLY — user=X, ip=Y` |
| Bypass — Full Access | INFO | `Maintenance bypass: FULL ACCESS — user=X, ip=Y` |
| Erişim Reddedildi | INFO | `Maintenance mode: erişim reddedildi — user=X, ip=Y` |
| Patch Uygulandı | INFO | `kta_system_utils: maintenance_bypass patch uygulandı` |

---

### Dosya Yapısı

```
kta_system_utils/
├── __init__.py                              # Patch import ve uygulama
├── install.py                               # after_install: site_config ayarları
├── hooks.py                                 # Scheduler, boot, install hooks
└── kta_system_utils_maintenance/
    ├── __init__.py
    ├── boot.py                              # Hard-reload flag → bootinfo
    ├── maintenance_bypass.py                # Monkey-patch: init_request wrap
    ├── tasks.py                             # Gece bakım görevleri
    └── tests/
        ├── test_maintenance.py              # Gece bakım testleri
        └── test_maintenance_bypass.py       # Bypass mekanizması testleri
```

---

### Manuel Test

```bash
# Maintenance mode aç
bench --site [site_name] set-maintenance-mode on

# Test:
# 1. Normal kullanıcı ile giriş → "Session Stopped" sayfası görmeli
# 2. Administrator ile giriş → Sisteme erişebilmeli
# 3. System Manager rolündeki kullanıcı ile giriş → Sisteme erişebilmeli

# Maintenance mode kapat
bench --site [site_name] set-maintenance-mode off
# Tüm kullanıcılar normal erişebilmeli
```

---

### Bilinen Sınırlamalar

| Sınırlama | Açıklama |
|-----------|----------|
| Monkey-patch yaklaşımı | Frappe core'u güncellenmesi durumunda `init_request` imzası değişirse patch uyumluluğu kontrol edilmelidir |
| Bypass kullanıcıları varsayılanda read-only | `maintenance_bypass_full_access` açılmadıkça bypass eden kullanıcılar DB'ye yazma yapamaz |
| Session kurulum maliyeti | Bypass kontrolü için her request'te session kurulumu yapılır; bu maintenance mode'daki performansı çok az etkileyebilir |

---

## License

MIT
