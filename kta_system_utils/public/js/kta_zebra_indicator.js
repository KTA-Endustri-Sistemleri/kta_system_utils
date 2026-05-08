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

// Liste görünümü için
frappe.listview_settings['KTA Zebra Printers'] = {
    onload: function(listview) {
        // Liste yüklendiğinde her satıra indicator eklemek için bir metod gerekebilir
        // Ancak basitlik için liste görünümünde standart indicator alanlarını kullanmak daha iyidir
    },
    refresh: function(listview) {
        // Liste yenilendiğinde durumları çekebiliriz
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
                
                // Standart Frappe bildirim gösterimi (Sağ altta çıkan veya üstte)
                // Kalıcı olması için set_intro kullanalım ama temizleyerek
                frm.set_intro(status.message, status.color);
            }
        }
    });
}
