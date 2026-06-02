frappe.pages['kta_print_queue'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('KTA Yazıcı İş Kuyruğu'),
		single_column: true
	});

	// CSS Ekle
	$(`<style>
		.print-queue-container {
			padding: 15px;
		}
		.queue-card {
			background: #fff;
			border: 1px solid #f0f0f0;
			border-radius: 8px;
			padding: 20px;
			margin-bottom: 25px;
			box-shadow: 0 2px 8px rgba(0,0,0,0.02);
		}
		.queue-title {
			font-size: 1.2rem;
			font-weight: 600;
			margin-bottom: 15px;
			color: #333;
			border-bottom: 2px solid #f7f7f7;
			padding-bottom: 10px;
			display: flex;
			justify-content: space-between;
			align-items: center;
		}
		.queue-table th {
			font-weight: 500;
			color: #666;
			background-color: #fafafa !important;
		}
		.status-badge {
			padding: 4px 8px;
			border-radius: 4px;
			font-size: 0.85rem;
			font-weight: 500;
		}
		.status-pending {
			background-color: #fff8e1;
			color: #b78103;
		}
		.status-failed {
			background-color: #ffebee;
			color: #c62828;
		}
	</style>`).appendTo(wrapper);

	// Container ekle
	let container = $('<div class="print-queue-container"></div>').appendTo(page.body);

	// Yenile butonu
	page.add_inner_button(__('Yenile'), () => refresh_queue(), 'fa fa-refresh');

	// Toplu Yeniden Dene butonu
	let btn_retry_all = page.add_custom_button(__('Başarısızları Yeniden Dene'), () => {
		frappe.confirm(__('Son 2 saatteki tüm başarısız etiket basımlarını yeniden denemek istediğinize emin misiniz?'), () => {
			frappe.call({
				method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.retry_all_failed',
				freeze: true,
				callback: function(r) {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({message: r.message.message, indicator: 'green'});
						refresh_queue();
					}
				}
			});
		});
	});
	btn_retry_all.addClass('btn-primary');

	// Kuyruk Durumunu getirme ve listeleme fonksiyonu
	function refresh_queue() {
		frappe.call({
			method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.get_queue_status',
			callback: function(r) {
				if (r.message) {
					render_queue(r.message);
				}
			}
		});
	}

	function render_queue(data) {
		container.empty();

		// --- BEKLEYEN İŞLER ---
		let pending_section = $(`
			<div class="queue-card">
				<div class="queue-title">
					<span><i class="fa fa-clock-o text-warning"></i> Bekleyen Etiket İşleri (${data.pending.length})</span>
				</div>
				<div class="table-responsive">
					<table class="table queue-table table-hover">
						<thead>
							<tr>
								<th>ID</th>
								<th>Etiket Tipi</th>
								<th>Etiket Adı</th>
								<th>Hedef Yazıcı</th>
								<th>Kullanıcı</th>
								<th>Zaman</th>
								<th style="width: 120px;">İşlemler</th>
							</tr>
						</thead>
						<tbody class="pending-list"></tbody>
					</table>
				</div>
			</div>
		`).appendTo(container);

		if (data.pending.length === 0) {
			pending_section.find('.pending-list').append(`
				<tr>
					<td colspan="7" class="text-center text-muted py-4">${__('Bekleyen etiket işi bulunmuyor.')}</td>
				</tr>
			`);
		} else {
			data.pending.forEach(item => {
				let row = $(`
					<tr>
						<td><a href="/app/kta-print-log/${item.name}"><b>${item.name}</b></a></td>
						<td>${item.label_doctype}</td>
						<td><a href="/app/kta-depo-etiketleri/${item.label_name}">${item.label_name}</a></td>
						<td>${item.printer || '<span class="text-muted">Bulunamadı</span>'}</td>
						<td>${item.user}</td>
						<td>${comment_when(item.attempted_at)}</td>
						<td>
							<button class="btn btn-xs btn-danger btn-cancel-job" data-id="${item.name}">${__('İptal Et')}</button>
						</td>
					</tr>
				`);
				pending_section.find('.pending-list').append(row);
			});
		}

		// --- BAŞARISIZ İŞLER ---
		let failed_section = $(`
			<div class="queue-card">
				<div class="queue-title">
					<span><i class="fa fa-exclamation-triangle text-danger"></i> Son Başarısız İşler (${data.failed.length})</span>
				</div>
				<div class="table-responsive">
					<table class="table queue-table table-hover">
						<thead>
							<tr>
								<th>ID</th>
								<th>Etiket Tipi</th>
								<th>Etiket Adı</th>
								<th>Yazıcı</th>
								<th>Hata Mesajı</th>
								<th>Kullanıcı</th>
								<th>Zaman</th>
								<th style="width: 120px;">İşlemler</th>
							</tr>
						</thead>
						<tbody class="failed-list"></tbody>
					</table>
				</div>
			</div>
		`).appendTo(container);

		if (data.failed.length === 0) {
			failed_section.find('.failed-list').append(`
				<tr>
					<td colspan="8" class="text-center text-muted py-4">${__('Başarısız etiket işi bulunmuyor.')}</td>
				</tr>
			`);
		} else {
			data.failed.forEach(item => {
				let row = $(`
					<tr>
						<td><a href="/app/kta-print-log/${item.name}"><b>${item.name}</b></a></td>
						<td>${item.label_doctype}</td>
						<td><a href="/app/kta-depo-etiketleri/${item.label_name}">${item.label_name}</a></td>
						<td>${item.printer || '<span class="text-muted">Bulunamadı</span>'}</td>
						<td class="text-danger small" style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.error_message}">${item.error_message || ''}</td>
						<td>${item.user}</td>
						<td>${comment_when(item.attempted_at)}</td>
						<td>
							<button class="btn btn-xs btn-default btn-retry-job" data-id="${item.name}"><i class="fa fa-refresh"></i> ${__('Yeniden Dene')}</button>
						</td>
					</tr>
				`);
				failed_section.find('.failed-list').append(row);
			});
		}

		// Event listener'ları bağla
		container.find('.btn-cancel-job').click(function() {
			let id = $(this).attr('data-id');
			frappe.call({
				method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.cancel_job',
				args: { log_name: id },
				callback: function(r) {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({message: r.message.message, indicator: 'green'});
						refresh_queue();
					}
				}
			});
		});

		container.find('.btn-retry-job').click(function() {
			let id = $(this).attr('data-id');
			frappe.call({
				method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.retry_job',
				args: { log_name: id },
				callback: function(r) {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({message: r.message.message, indicator: 'green'});
						refresh_queue();
					} else if (r.message) {
						frappe.msgprint(r.message.message);
					}
				}
			});
		});
	}

	// İlk yükleme
	refresh_queue();

	// Her 10 saniyede bir otomatik yenile
	let autorefresh = setInterval(() => {
		if (wrapper.offsetParent !== null) { // Sayfa aktifse yenile
			refresh_queue();
		}
	}, 10000);

	// Sayfadan çıkıldığında interval'ı temizle
	$(wrapper).on('destroyed', () => {
		clearInterval(autorefresh);
	});
};
