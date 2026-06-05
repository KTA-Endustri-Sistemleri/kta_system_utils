frappe.pages['kta_print_queue'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('KTA Yazıcı İş Kuyruğu'),
		single_column: true
	});

	// CSS
	$(`<style>
		.print-queue-container {
			padding: 15px;
		}
		/* --- İstatistik kartları --- */
		.pq-stats-row {
			display: flex;
			gap: 12px;
			margin-bottom: 20px;
			flex-wrap: wrap;
		}
		.pq-stat-card {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 8px;
			padding: 14px 20px;
			min-width: 130px;
			box-shadow: var(--card-shadow);
			display: flex;
			flex-direction: column;
			gap: 4px;
		}
		.pq-stat-card .stat-label {
			font-size: 0.78rem;
			color: var(--text-muted);
			text-transform: uppercase;
			letter-spacing: 0.04em;
		}
		.pq-stat-card .stat-value {
			font-size: 1.6rem;
			font-weight: 700;
			line-height: 1;
		}
		.pq-stat-card.success .stat-value { color: var(--green-500, #28a745); }
		.pq-stat-card.failed  .stat-value { color: var(--red-500,   #dc3545); }
		.pq-stat-card.pending .stat-value { color: var(--yellow-500, #ffc107); }
		.pq-stat-card.retried .stat-value { color: var(--blue-500,   #17a2b8); }
		/* --- Yazıcı durum şeridi --- */
		.pq-printer-row {
			display: flex;
			gap: 10px;
			flex-wrap: wrap;
			margin-bottom: 20px;
		}
		.pq-printer-badge {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 20px;
			padding: 5px 14px;
			font-size: 0.85rem;
			display: flex;
			align-items: center;
			gap: 6px;
			box-shadow: var(--card-shadow);
		}
		.pq-printer-badge .pq-dot {
			width: 8px;
			height: 8px;
			border-radius: 50%;
			flex-shrink: 0;
		}
		.pq-dot.green  { background: #28a745; }
		.pq-dot.red    { background: #dc3545; }
		.pq-dot.orange { background: #fd7e14; }
		.pq-dot.yellow { background: #ffc107; }
		.pq-dot.gray   { background: #adb5bd; }
		/* --- Tablo kartları --- */
		.queue-card {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: 8px;
			padding: 20px;
			margin-bottom: 25px;
			box-shadow: var(--card-shadow);
		}
		.queue-title {
			font-size: 1.1rem;
			font-weight: 600;
			margin-bottom: 15px;
			color: var(--text-color);
			border-bottom: 2px solid var(--border-color);
			padding-bottom: 10px;
			display: flex;
			justify-content: space-between;
			align-items: center;
		}
		.queue-table th {
			font-weight: 500;
			color: var(--text-muted);
			background-color: var(--bg-light-gray) !important;
			border-bottom: 1px solid var(--border-color) !important;
		}
		.queue-table td {
			border-color: var(--border-color) !important;
			vertical-align: middle;
		}
	</style>`).appendTo(wrapper);

	let container = $('<div class="print-queue-container"></div>').appendTo(page.body);

	// Yenile butonu
	page.add_action_icon('es-line-reload', () => refresh_all(), '', __('Yenile'));

	// ─── İstatistik + yazıcı durumu yükleme ───────────────────────────────────
	function load_stats() {
		frappe.call({
			method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.get_queue_stats',
			callback: function(r) {
				if (!r.message) return;
				render_stats_bar(r.message);
			}
		});
	}

	function render_stats_bar(data) {
		container.find('.pq-stats-area').remove();

		const t = data.total_today || {};
		const ps = data.printer_statuses || {};

		let area = $('<div class="pq-stats-area"></div>').prependTo(container);

		// Toplam istatistik kartları
		let statsRow = $('<div class="pq-stats-row"></div>').appendTo(area);
		[
			{ cls: 'success', label: __('Bugün Başarılı'), val: t.success || 0 },
			{ cls: 'failed',  label: __('Bugün Başarısız'), val: t.failed || 0 },
			{ cls: 'pending', label: __('Bekleyen'),        val: t.pending || 0 },
			{ cls: 'retried', label: __('Yeniden Denenen'), val: t.retried || 0 },
		].forEach(s => {
			statsRow.append(`
				<div class="pq-stat-card ${s.cls}">
					<span class="stat-label">${s.label}</span>
					<span class="stat-value">${s.val}</span>
				</div>
			`);
		});

		// Yazıcı durum şeridi
		if (Object.keys(ps).length > 0) {
			let printerRow = $('<div class="pq-printer-row"></div>').appendTo(area);
			Object.entries(ps).forEach(([name, status]) => {
				printerRow.append(`
					<div class="pq-printer-badge" title="${status.message}">
						<span class="pq-dot ${status.color}"></span>
						<strong>${name}</strong>
						<span class="text-muted">— ${__(status.message)}</span>
					</div>
				`);
			});
		}
	}

	// ─── Kuyruk listesi ───────────────────────────────────────────────────────
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

	function refresh_all() {
		load_stats();
		refresh_queue();
	}

	function label_link(doctype, name) {
		const route = frappe.router.slug(doctype);
		return `<a href="/app/${route}/${name}">${name}</a>`;
	}

	function render_queue(data) {
		container.find('.queue-card').remove();

		// ── Bekleyen İşler ─────────────────────────────────────────────────────
		let pending_section = $(`
			<div class="queue-card">
				<div class="queue-title">
					<span><i class="fa fa-clock-o text-warning"></i> ${__('Bekleyen Etiket İşleri')} (${data.pending.length})</span>
				</div>
				<div class="table-responsive">
					<table class="table queue-table table-hover">
						<thead>
							<tr>
								<th>${__('Log ID')}</th>
								<th>${__('Etiket Tipi')}</th>
								<th>${__('Etiket Adı')}</th>
								<th>${__('Hedef Yazıcı')}</th>
								<th>${__('Kullanıcı')}</th>
								<th>${__('Zaman')}</th>
								<th style="width: 120px;">${__('İşlemler')}</th>
							</tr>
						</thead>
						<tbody class="pending-list"></tbody>
					</table>
				</div>
			</div>
		`).appendTo(container);

		if (data.pending.length === 0) {
			pending_section.find('.pending-list').append(`
				<tr><td colspan="7" class="text-center text-muted py-4">${__('Bekleyen etiket işi bulunmuyor.')}</td></tr>
			`);
		} else {
			data.pending.forEach(item => {
				pending_section.find('.pending-list').append(`
					<tr>
						<td><a href="/app/kta-print-log/${item.name}"><b>${item.name}</b></a></td>
						<td>${item.label_doctype}</td>
						<td>${label_link(item.label_doctype, item.label_name)}</td>
						<td>${item.printer || '<span class="text-muted">Bulunamadı</span>'}</td>
						<td>${item.user}</td>
						<td>${comment_when(item.attempted_at)}</td>
						<td>
							<button class="btn btn-xs btn-danger btn-cancel-job" data-id="${item.name}">${__('İptal Et')}</button>
						</td>
					</tr>
				`);
			});
		}

		// ── Başarısız İşler ────────────────────────────────────────────────────
		let failed_section = $(`
			<div class="queue-card">
				<div class="queue-title">
					<span><i class="fa fa-exclamation-triangle text-danger"></i> ${__('Son Başarısız İşler')} (${data.failed.length})</span>
				</div>
				<div class="table-responsive">
					<table class="table queue-table table-hover">
						<thead>
							<tr>
								<th>${__('Log ID')}</th>
								<th>${__('Etiket Tipi')}</th>
								<th>${__('Etiket Adı')}</th>
								<th>${__('Yazıcı')}</th>
								<th>${__('Hata Mesajı')}</th>
								<th>${__('Kullanıcı')}</th>
								<th>${__('Zaman')}</th>
								<th style="width: 140px;">${__('İşlemler')}</th>
							</tr>
						</thead>
						<tbody class="failed-list"></tbody>
					</table>
				</div>
			</div>
		`).appendTo(container);

		if (data.failed.length === 0) {
			failed_section.find('.failed-list').append(`
				<tr><td colspan="8" class="text-center text-muted py-4">${__('Başarısız etiket işi bulunmuyor.')}</td></tr>
			`);
		} else {
			data.failed.forEach(item => {
				failed_section.find('.failed-list').append(`
					<tr>
						<td><a href="/app/kta-print-log/${item.name}"><b>${item.name}</b></a></td>
						<td>${item.label_doctype}</td>
						<td>${label_link(item.label_doctype, item.label_name)}</td>
						<td>${item.printer || '<span class="text-muted">Bulunamadı</span>'}</td>
						<td class="text-danger small" style="max-width:230px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${item.error_message || ''}">${item.error_message || ''}</td>
						<td>${item.user}</td>
						<td>${comment_when(item.attempted_at)}</td>
						<td>
							<button class="btn btn-xs btn-default btn-retry-job" data-id="${item.name}">
								<i class="fa fa-refresh"></i> ${__('Yeniden Dene')}
							</button>
						</td>
					</tr>
				`);
			});
		}

		// ── Event Listener'lar ─────────────────────────────────────────────────
		container.find('.btn-cancel-job').click(function() {
			let id = $(this).attr('data-id');
			frappe.call({
				method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.cancel_job',
				args: { log_name: id },
				callback: function(r) {
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({ message: r.message.message, indicator: 'green' });
						refresh_all();
					}
				}
			});
		});

		container.find('.btn-retry-job').click(function() {
			let id = $(this).attr('data-id');
			let $btn = $(this).prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');
			frappe.call({
				method: 'kta_system_utils.kta_zebra_utils.page.kta_print_queue.kta_print_queue.retry_job',
				args: { log_name: id },
				callback: function(r) {
					$btn.prop('disabled', false).html(`<i class="fa fa-refresh"></i> ${__('Yeniden Dene')}`);
					if (r.message && r.message.status === 'success') {
						frappe.show_alert({ message: r.message.message, indicator: 'green' });
						refresh_all();
					} else if (r.message) {
						frappe.msgprint(r.message.message);
					}
				}
			});
		});
	}

	// ─── İlk yükleme ──────────────────────────────────────────────────────────
	refresh_all();

	// Her 15 saniyede kuyruk + 60 saniyede yazıcı durumu yenile
	let queueTimer = setInterval(() => {
		if (wrapper.offsetParent !== null) refresh_queue();
	}, 15000);

	let statsTimer = setInterval(() => {
		if (wrapper.offsetParent !== null) load_stats();
	}, 60000);

	$(wrapper).on('destroyed', () => {
		clearInterval(queueTimer);
		clearInterval(statsTimer);
	});
};
