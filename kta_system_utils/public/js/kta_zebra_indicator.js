let bulk_printer_statuses = {};
let bulk_loading = false;

frappe.ui.form.on('KTA Zebra Printers', {
    refresh: function(frm) {
        // Form görünümünde göstergeyi ekle
        update_printer_status(frm);
        
        // Yenile butonu ekle
        frm.add_custom_button(__('Durumu Güncelle'), function() {
            update_printer_status(frm);
        });
    }
});

let printer_status_timer;

// Liste görünümü için
frappe.listview_settings['KTA Zebra Printers'] = {
    refresh: function(listview) {
        // Kullanıcı sayfaya her geri döndüğünde veya sayfayı yenilediğinde eski döngüyü temizle
        if (printer_status_timer) {
            clearTimeout(printer_status_timer);
        }
        
        let fetch_and_update = function() {
            // Eğer kullanıcı listeyi terk ettiyse döngüyü durdur
            let route = frappe.get_route();
            if (!route || route[0] !== 'List' || route[1] !== 'KTA Zebra Printers') {
                return;
            }

            frappe.call({
                method: 'kta_system_utils.kta_zebra_utils.api.get_all_printers_status',
                callback: function(r) {
                    // API yanıt verene kadar kullanıcı sayfadan çıkmış olabilir, tekrar kontrol et
                    route = frappe.get_route();
                    if (!route || route[0] !== 'List' || route[1] !== 'KTA Zebra Printers') {
                        return;
                    }

                    if (r.message) {
                        let statuses = r.message;
                        // DOM üzerinde satırları bulup doğrudan güncelle
                        $('.list-row-container').each(function() {
                            let raw_name = $(this).find('.list-row-checkbox').attr('data-name');
                            if (!raw_name) return;
                            
                            // Checkbox'taki isim encode (URL-encoded) edilmiş olabilir
                            let docname = decodeURIComponent(raw_name);
                            
                            if (docname && statuses[docname]) {
                                let status = statuses[docname];
                                let $ind = $(this).find('.indicator-pill');
                                if ($ind.length) {
                                    $ind.removeClass().addClass('indicator-pill whitespace-nowrap ' + status.color);
                                    $ind.html(`<span>${__(status.message)}</span>`);
                                }
                            }
                        });
                    }
                    
                    // İstek tamamen bittikten SONRA 5 saniye bekle ve tekrarla
                    printer_status_timer = setTimeout(fetch_and_update, 5000);
                }
            });
        };

        // Liste her ekrana geldiğinde (refresh) döngüyü yeniden başlat
        fetch_and_update();
    },
    get_indicator: function(doc) {
        return [__("Sorgulanıyor..."), "gray", "printer_name,=," + doc.name];
    }
};

function update_printer_status(frm) {
    if (frm.is_new()) return;

    frappe.call({
        method: 'kta_system_utils.kta_zebra_utils.api.get_printer_status',
        args: {
            printer_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                let status = r.message;
                
                // Önceki intro/headline'ları temizle
                frm.set_intro('');
                if (frm.dashboard) {
                    frm.dashboard.clear_headline();
                }
                
                // Form header indicator
                frm.page.set_indicator(status.message, status.color);
                
                // Form intro banner
                frm.set_intro(status.message, status.color);
            }
        }
    });
}
