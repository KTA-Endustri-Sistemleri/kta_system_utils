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

class ZebraPrinterManager:
    """
    Yazıcı listesini yöneten ve toplu işlemler yapan Entity.
    """
    def __init__(self):
        self.printers = {}

    def get_printer_instance(self, printer_name):
        """Veritabanından yazıcı bilgilerini çekip nesne oluşturur."""
        doc = frappe.get_doc("KTA Zebra Printers", printer_name)
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
