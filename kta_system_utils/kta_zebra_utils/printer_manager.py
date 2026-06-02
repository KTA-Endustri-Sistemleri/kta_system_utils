import socket
import frappe

class ZebraPrinter:
    """
    Zebra Printer Entity - Bir yazıcıyı ve onun durumunu temsil eder.
    """
    def __init__(self, printer_name, ip, port=9100):
        self.printer_name = printer_name
        self.ip = ip
        self.port = int(port)
        self.timeout = 3

    def check_connection(self):
        """Sadece TCP bağlantısının açık olup olmadığını kontrol eder."""
        try:
            with socket.create_connection((self.ip, self.port), timeout=self.timeout):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False

    def get_detailed_status(self):
        """ZPL ~HS komutu ile yazıcıdan detaylı durum bilgisi çeker."""
        if not self.check_connection():
            return {
                "status": "Offline",
                "color": "red",
                "message": "Erişilemiyor (Offline)"
            }

        try:
            # ~HS (Host Status) komutunu gönder
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect((self.ip, self.port))
                s.sendall(b"~HS")
                
                # Yanıtı oku (3 parça bekliyoruz)
                data = s.recv(1024).decode('ascii', errors='ignore')
                
                return self._parse_hs_response(data)
        except Exception as e:
            return {
                "status": "Error",
                "color": "red",
                "message": f"Sorgu Hatası: {str(e)}"
            }

    def _create_print_log(self, label_doctype, label_name, status, zpl, error=None):
        ZebraPrinterManager.create_print_log(
            label_doctype=label_doctype,
            label_name=label_name,
            printer=self.printer_name,
            status=status,
            zpl=zpl,
            error=error,
            user=getattr(frappe.session, "user", None) or "Administrator"
        )

    def send(self, data, label_doctype=None, label_name=None):
        """ZPL verisini yazıcıya soket üzerinden gönderir."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect((self.ip, self.port))
                s.sendall(data.encode("utf-8"))
            self._create_print_log(label_doctype, label_name, "Success", data)
            return None
        except Exception as e:
            self._create_print_log(label_doctype, label_name, "Failed", data, str(e))
            frappe.log_error(title=f"ZPL Print Error {str(e)}", message="Printer Error")
            return {"status": "error", "message": f"Failed to send label {str(e)}"}

    def send_batch(self, data_list, label_doctype=None, label_names=None):
        """
        ZPL listesini tek TCP bağlantısında sırayla gönderir.
        data_list: [zpl_str, ...]
        label_names: [label_name, ...] (data_list ile aynı sırada olmalı)
        """
        errors = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect((self.ip, self.port))
                for i, zpl in enumerate(data_list):
                    lbl = label_names[i] if label_names and i < len(label_names) else None
                    try:
                        s.sendall(zpl.encode("utf-8"))
                        self._create_print_log(label_doctype, lbl, "Success", zpl)
                    except Exception as e:
                        errors.append({"label": lbl, "error": str(e)})
                        self._create_print_log(label_doctype, lbl, "Failed", zpl, str(e))
        except Exception as e:
            frappe.log_error(f"Batch TCP Error: {e}", "ZebraPrinter")
            # Eğer tüm batch için connection hatası aldıysak, henüz gönderilemeyenleri Failed logla
            for i, zpl in enumerate(data_list):
                lbl = label_names[i] if label_names and i < len(label_names) else None
                self._create_print_log(label_doctype, lbl, "Failed", zpl, str(e))
            errors.append({"error": str(e)})
        return errors

    def _parse_hs_response(self, response):
        """
        ~HS yanıtını parse eder.
        Genelde 3 satır döner, her biri <STX> ile başlar <ETX> ile biter.
        Örnek String 2: mmm,n,o,p,q,r,s,t,uuuuuuuu,v,w
        q = Media Out, r = Ribbon Out, s = Head Open, t = Pause Status
        """
        try:
            # Kontrol karakterlerini ve boşlukları temizle, satırlara böl
            lines = response.replace('\x02', '').replace('\x03', '').split('\r\n')
            lines = [l for l in lines if l.strip()]
            
            if len(lines) < 2:
                # Bazı durumlarda yanıt farklı formatta gelebilir
                return {"status": "Online", "color": "green", "message": "Çevrimiçi (Hazır)"}

            # String 2'yi analiz et
            s2_parts = lines[1].split(',')
            
            if len(s2_parts) < 8:
                return {"status": "Online", "color": "green", "message": "Çevrimiçi"}

            media_out = s2_parts[4].strip() == "1"
            ribbon_out = s2_parts[5].strip() == "1"
            head_open = s2_parts[6].strip() == "1"
            is_paused = s2_parts[7].strip() == "1"

            if head_open:
                return {"status": "Head Open", "color": "orange", "message": "Kapak Açık"}
            if media_out:
                return {"status": "Media Out", "color": "orange", "message": "Kağıt Bitti"}
            if ribbon_out:
                return {"status": "Ribbon Out", "color": "orange", "message": "Ribon Bitti"}
            if is_paused:
                return {"status": "Paused", "color": "yellow", "message": "Duraklatıldı"}

            return {"status": "Ready", "color": "green", "message": "Yazıcı Hazır"}
            
        except Exception:
            return {"status": "Online", "color": "green", "message": "Çevrimiçi (Detay Alınamadı)"}

class MockZebraPrinter(ZebraPrinter):
    """
    Test ve geliştirme ortamı için yazıcı simülasyonu.
    Gerçek TCP bağlantısı açmaz; ZPL çıktısını log'a yazar.
    """
    def __init__(self):
        super().__init__("MOCK_PRINTER", "127.0.0.1", 9100)

    def check_connection(self):
        return True

    def get_detailed_status(self):
        return {"status": "Ready", "color": "green", "message": "Yazıcı Hazır (MOCK)"}

    def send(self, data, label_doctype=None, label_name=None):
        self._create_print_log(label_doctype, label_name, "Success", data)
        frappe.log_error(
            title="[MOCK ZEBRA] ZPL Output",
            message=data[:1000]
        )
        return None

    def send_batch(self, data_list, label_doctype=None, label_names=None):
        for i, zpl in enumerate(data_list):
            lbl = label_names[i] if label_names and i < len(label_names) else None
            self.send(zpl, label_doctype=label_doctype, label_name=lbl)
        return []

class ZebraPrinterManager:
    """
    Yazıcı listesini yöneten ve toplu işlemler yapan Entity.
    """
    def __init__(self):
        self.printers = {}

    def get_printer_instance(self, printer_name):
        """Veritabanından yazıcı bilgilerini çekip nesne oluşturur."""
        doc = frappe.get_doc("KTA Zebra Printers", printer_name, ignore_permissions=True)
        if not doc:
            return None
        
        return ZebraPrinter(
            printer_name=doc.name,
            ip=doc.ip,
            port=doc.port or 9100
        )

    def check_printer_status(self, printer_name):
        """Tek bir yazıcının detaylı durumunu döner."""
        printer = self.get_printer_instance(printer_name)
        if not printer:
            return {"status": "Error", "color": "gray", "message": "Yazıcı bulunamadı"}
        
        return printer.get_detailed_status()

    @staticmethod
    def _user_can_print(user, printer_name):
        """Kullanıcının bu yazıcıya iş gönderme izni var mı?"""
        user_roles = frappe.get_roles(user)
        allowed_roles = frappe.get_all(
            "KTA Printer Permission",
            filters={"printer": printer_name, "can_print": 1},
            pluck="role"
        )
        if not allowed_roles:
            return True  # İzin tablosu boşsa herkese açık
        return bool(set(user_roles) & set(allowed_roles))

    @staticmethod
    def get_printer_for_user(user=None):
        """Kullanıcının varsayılan veya fallback yazıcısını döndürür."""
        if frappe.conf.get("use_mock_zebra_printer") or frappe.flags.in_test:
            return MockZebraPrinter()

        if not user:
            user = frappe.session.user

        user_printer = frappe.db.get_value(
            doctype="KTA User Zebra Printers",
            filters={"user": user, "disabled": 0},
            fieldname=["printer", "fallback_printer"],
            as_dict=True
        )

        if not user_printer:
            frappe.msgprint("No default printer found for the current user.")
            return None

        # Primary printer'ı dene
        primary_printer = None
        if user_printer.printer:
            if ZebraPrinterManager._user_can_print(user, user_printer.printer):
                doc = frappe.get_doc("KTA Zebra Printers", user_printer.printer, ignore_permissions=True)
                primary_printer = ZebraPrinter(doc.name, doc.ip, doc.port or 9100)
            else:
                frappe.msgprint(f"Varsayılan yazıcıya ({user_printer.printer}) erişim izniniz yok.", alert=True)

        if primary_printer:
            # Sadece bağlantı kontrolü yapıyoruz. Eğer ayakta ise döndür
            if primary_printer.check_connection():
                return primary_printer
            
            # Bağlanamıyorsak ve fallback varsa onu dene
            if user_printer.fallback_printer:
                if ZebraPrinterManager._user_can_print(user, user_printer.fallback_printer):
                    fallback_doc = frappe.get_doc("KTA Zebra Printers", user_printer.fallback_printer, ignore_permissions=True)
                    fallback_printer = ZebraPrinter(fallback_doc.name, fallback_doc.ip, fallback_doc.port or 9100)
                    frappe.msgprint(f"Varsayılan yazıcıya ({primary_printer.printer_name}) erişilemedi, yedek yazıcı ({fallback_printer.printer_name}) kullanılıyor.", alert=True)
                    return fallback_printer
                else:
                    frappe.msgprint(f"Yedek yazıcıya ({user_printer.fallback_printer}) erişim izniniz yok.", alert=True)
            else:
                # Fallback yoksa yine de primary'i dönelim (çünkü hata logu oluşturulurken hangi yazıcıya gitmeye çalıştığı loglanmalı)
                # Ancak kullanıcıya uyarı göster
                frappe.msgprint(f"Varsayılan yazıcıya ({primary_printer.printer_name}) erişilemiyor ve yedek yazıcı tanımlanmamış.", alert=True)
                return primary_printer
        elif user_printer.fallback_printer:
            # Primary printer'a izin yoksa direkt fallback'e bakabiliriz!
            if ZebraPrinterManager._user_can_print(user, user_printer.fallback_printer):
                fallback_doc = frappe.get_doc("KTA Zebra Printers", user_printer.fallback_printer, ignore_permissions=True)
                fallback_printer = ZebraPrinter(fallback_doc.name, fallback_doc.ip, fallback_doc.port or 9100)
                frappe.msgprint(f"Varsayılan yazıcıya izniniz yok, yedek yazıcı ({fallback_printer.printer_name}) kullanılıyor.", alert=True)
                return fallback_printer

        return None

    @staticmethod
    def format_data(doctype_name, data):
        """KTA Zebra Templates üzerinden ZPL şablonuna veriyi basar. Şablon cache'lenir."""
        cache_key = f"kta_zebra_template_{doctype_name}"
        template = frappe.cache().get_value(cache_key)

        if not template:
            doc = frappe.get_doc("KTA Zebra Templates", doctype_name, ignore_permissions=True)
            template = doc.get("zebra_template")
            if not template:
                frappe.throw(f"Zebra Template not found in KTA Zebra Templates for: {doctype_name}")
            # 1 saatlik cache
            frappe.cache().set_value(cache_key, template, expires_in_sec=3600)

        return template.format(data=data)

    @staticmethod
    def create_print_log(label_doctype, label_name, printer, status, zpl, error=None, user=None):
        if not label_doctype or not label_name:
            return
        try:
            frappe.get_doc({
                "doctype": "KTA Print Log",
                "label_doctype": label_doctype,
                "label_name": label_name,
                "printer": printer or None,
                "user": user or frappe.session.user or "Administrator",
                "status": status,
                "attempted_at": frappe.utils.now(),
                "error_message": error,
                "zpl_payload": zpl[:500] if zpl else None
            }).insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Print Log Creation Error: {str(e)}", "KTA Print Log")

    @staticmethod
    def format_qty(qty):
        """Sayıyı tr_TR lokaline uygun (küsüratsızsa tamsayı, değilse 2 hane) formatlar."""
        from babel.numbers import format_decimal
        if qty % 1 == 0:
            return format_decimal(f"{qty:g}", locale="tr_TR")
        else:
            return format_decimal(f"{qty:.2f}", locale="tr_TR")
