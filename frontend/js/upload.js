// Check authentication
if (!requireAuth()) {
    throw new Error('Not authenticated');
}

// Global variables
let selectedFile = null;

// MAPE desimal per zona (dari NB2 — identik dengan Tabel 4.2 skripsi)
const MAPE_ZONA = {
    utama: 0.0923,
    a:     0.1112,
    b:     0.1030,
    c:     0.1069,
};

// ─────────────────────────────────────────────────────────
// INITIALIZE
// ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadUserInfo();
    setupDragDrop();
    setupFileInput();
    setupUploadBtn();
    loadUploadHistory();
});

function loadUserInfo() {
    const user = getUser();
    if (user) {
        const el = document.getElementById('userName');
        if (el) el.textContent = user.username;
    }
}

// ─────────────────────────────────────────────────────────
// DRAG & DROP
// ─────────────────────────────────────────────────────────
function setupDragDrop() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    if (!dropZone || !fileInput) return;

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#6956F6';
        dropZone.style.background  = 'rgba(105,86,246,0.10)';
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = 'rgba(105,86,246,0.30)';
        dropZone.style.background  = 'var(--purple-bg, #ECECFC)';
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'rgba(105,86,246,0.30)';
        dropZone.style.background  = 'var(--purple-bg, #ECECFC)';
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });
}

function setupFileInput() {
    const fileInput = document.getElementById('fileInput');
    if (!fileInput) return;
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
    });
}

// ─────────────────────────────────────────────────────────
// UPLOAD BUTTON
// ─────────────────────────────────────────────────────────
function setupUploadBtn() {
    const uploadBtn = document.getElementById('uploadBtn');
    if (!uploadBtn) return;

    uploadBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        const uploadBtnText = document.getElementById('uploadBtnText');
        const successDiv    = document.getElementById('successMessage');
        const errorDiv      = document.getElementById('errorMessage');

        successDiv.classList.add('hidden');
        errorDiv.classList.add('hidden');
        hidePredictionResult();

        uploadBtn.disabled = true;
        if (uploadBtnText) uploadBtnText.textContent = 'Memproses...';

        try {
            const formData = new FormData();
            formData.append('file', selectedFile, selectedFile.name);

            const token = getToken();

            const response = await fetch('http://localhost:5001/api/predict/upload', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
                body: formData
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Upload gagal');
            }

            const data = await response.json();

            if (data.success) {
                const detailEl = document.getElementById('successDetails');
                if (detailEl) detailEl.textContent =
                    `Berhasil memproses ${data.total_rows} baris data. Prediksi selesai.`;
                successDiv.classList.remove('hidden');

                renderPredictionResult(data);
                localStorage.setItem('lastPredictionResult', JSON.stringify(data));

                if (uploadBtnText) uploadBtnText.textContent = '✓ Selesai';

                setTimeout(() => loadUploadHistory(), 1500);
            } else {
                throw new Error(data.error || 'Prediksi gagal');
            }

        } catch (error) {
            console.error('Upload error:', error);
            showUploadError(error.message || 'Upload gagal. Silakan coba lagi.');
            uploadBtn.disabled = false;
            if (uploadBtnText) uploadBtnText.textContent = 'Upload & Prediksi';
        }
    });
}

// ─────────────────────────────────────────────────────────
// FILE SELECTION
// ─────────────────────────────────────────────────────────
function handleFileSelect(file) {
    if (!file.name.match(/\.(csv|xlsx|xls)$/i)) {
        showUploadError('Hanya file CSV, XLSX, atau XLS yang diterima.');
        return;
    }
    if (file.size > 16 * 1024 * 1024) {
        showUploadError('File terlalu besar. Maksimal 16MB.');
        return;
    }

    selectedFile = file;
    const fnEl = document.getElementById('fileName');
    const fsEl = document.getElementById('fileSize');
    const fiEl = document.getElementById('fileInfo');
    const ubEl = document.getElementById('uploadBtn');

    if (fnEl) fnEl.textContent = file.name;
    if (fsEl) fsEl.textContent = formatFileSize(file.size);
    if (fiEl) fiEl.classList.remove('hidden');
    if (ubEl) ubEl.disabled = false;

    const sucEl = document.getElementById('successMessage');
    const errEl = document.getElementById('errorMessage');
    if (sucEl) sucEl.classList.add('hidden');
    if (errEl) errEl.classList.add('hidden');
    hidePredictionResult();
}

function clearFile() {
    selectedFile = null;
    const fiEl = document.getElementById('fileInput');
    const fEl  = document.getElementById('fileInfo');
    const ubEl = document.getElementById('uploadBtn');
    if (fiEl) fiEl.value = '';
    if (fEl)  fEl.classList.add('hidden');
    if (ubEl) ubEl.disabled = true;

    const sucEl = document.getElementById('successMessage');
    const errEl = document.getElementById('errorMessage');
    if (sucEl) sucEl.classList.add('hidden');
    if (errEl) errEl.classList.add('hidden');
    hidePredictionResult();
}

// ─────────────────────────────────────────────────────────
// RENDER HASIL PREDIKSI (PER ZONA + MAPE DESIMAL)
// ─────────────────────────────────────────────────────────
function renderPredictionResult(data) {
    const container = document.getElementById('predictionResult');
    if (!container) return;

    const summary   = data.summary        || {};
    const rec       = data.recommendation || {};
    const nextDay   = data.next_day        ?? '-';
    const zonePred  = data.zone_predictions || {};

    // Ambil prediksi per zona
    const predUtama = typeof nextDay === 'number' ? Math.round(nextDay) : nextDay;
    const predA     = Math.round(zonePred.zona_A || summary.zone_a_avg || 532);
    const predB     = Math.round(zonePred.zona_B || summary.zone_b_avg || 161);
    const predC     = Math.round(zonePred.zona_C || summary.zone_c_avg || 113);

    // Status badge
    const statusStyle = {
        high:    'color:#dc2626;background:rgba(239,68,68,0.10);border:1px solid rgba(239,68,68,0.25);',
        low:     'color:#059669;background:rgba(16,185,129,0.10);border:1px solid rgba(16,185,129,0.25);',
        normal:  'color:#6956F6;background:rgba(105,86,246,0.10);border:1px solid rgba(105,86,246,0.25);',
        unknown: 'color:#A3A1AF;background:rgba(163,161,175,0.10);border:1px solid rgba(163,161,175,0.25);',
    }[rec.status] || 'color:#A3A1AF;background:rgba(163,161,175,0.10);';

    // Zona config
    const zonas = [
        { label: 'Gedung Utama', pred: predUtama, mape: MAPE_ZONA.utama, color: '#6956F6', bg: 'rgba(105,86,246,0.06)', border: 'rgba(105,86,246,0.18)' },
        { label: 'Zona A (Resto A)', pred: predA, mape: MAPE_ZONA.a, color: '#8C4AF2', bg: 'rgba(140,74,242,0.06)', border: 'rgba(140,74,242,0.18)' },
        { label: 'Zona B (Resto B)', pred: predB, mape: MAPE_ZONA.b, color: '#AA9ADB', bg: 'rgba(170,154,219,0.06)', border: 'rgba(170,154,219,0.18)' },
        { label: 'Zona C (Resto C)', pred: predC, mape: MAPE_ZONA.c, color: '#ec4899', bg: 'rgba(236,72,153,0.06)', border: 'rgba(236,72,153,0.18)' },
    ];

    container.classList.remove('hidden');
    container.innerHTML = `
        <div style="background:#fff;border:1px solid rgba(105,86,246,0.12);box-shadow:0 2px 12px rgba(105,86,246,0.08);border-radius:20px;padding:24px;margin-top:24px;">
            <h3 style="color:#1e1b4b;font-weight:600;font-size:15px;margin-bottom:16px;">📊 Hasil Prediksi CNN-GSO</h3>

            <!-- Status -->
            <div style="background:#ECECFC;border-radius:14px;padding:14px 16px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;">
                <p style="color:#374151;font-size:13px;">Status Konsumsi Besok</p>
                <span style="${statusStyle}padding:4px 14px;border-radius:999px;font-size:12px;font-weight:600;">
                    ${rec.status?.toUpperCase() || 'NORMAL'}
                </span>
            </div>

            <!-- Rekomendasi -->
            <div style="background:rgba(105,86,246,0.06);border:1px solid rgba(105,86,246,0.18);border-radius:10px;padding:12px;margin-bottom:20px;font-size:13px;color:#374151;">
                💡 ${rec.message || 'Prediksi konsumsi dalam rentang normal.'}
            </div>

            <!-- Prediksi per zona -->
            <p style="color:#374151;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;">Prediksi Konsumsi Hari Berikutnya</p>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:20px;">
                ${zonas.map(z => `
                <div style="background:${z.bg};border:1px solid ${z.border};border-radius:14px;padding:16px;">
                    <p style="color:#374151;font-size:11px;font-weight:500;margin-bottom:6px;">${z.label}</p>
                    <p style="color:${z.color};font-size:22px;font-weight:700;margin-bottom:2px;">
                        ${typeof z.pred === 'number' ? z.pred.toLocaleString('id-ID') : z.pred}
                        <span style="font-size:12px;font-weight:400;color:#374151;">kWh</span>
                    </p>
                    <p style="color:#374151;font-size:11px;">MAPE: <span style="color:${z.color};font-weight:600;">${z.mape.toFixed(4).replace('.',',')}</span></p>
                </div>`).join('')}
            </div>

            <!-- Tombol aksi -->
            <div style="display:flex;gap:12px;justify-content:flex-end;">
                <a href="prediksi.html"
                    style="padding:9px 20px;background:#ECECFC;color:#6956F6;border:1px solid rgba(105,86,246,0.20);border-radius:10px;font-size:13px;font-weight:500;text-decoration:none;"
                    onmouseover="this.style.opacity='.8'" onmouseout="this.style.opacity='1'">
                    Lihat Optimasi GSO →
                </a>
                <a href="dashboard.html"
                    style="padding:9px 20px;background:#6956F6;color:#fff;border-radius:10px;font-size:13px;font-weight:500;text-decoration:none;box-shadow:0 4px 12px rgba(105,86,246,0.30);"
                    onmouseover="this.style.opacity='.85'" onmouseout="this.style.opacity='1'">
                    Lihat Dashboard →
                </a>
            </div>
        </div>`;
}

function hidePredictionResult() {
    const el = document.getElementById('predictionResult');
    if (el) el.classList.add('hidden');
}

// ─────────────────────────────────────────────────────────
// RIWAYAT UPLOAD
// ─────────────────────────────────────────────────────────
async function loadUploadHistory() {
    const historyDiv = document.getElementById('uploadHistory');
    if (!historyDiv) return;

    historyDiv.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;padding:32px;color:#A3A1AF;font-size:13px;">
            <div style="width:20px;height:20px;border-radius:50%;border:2px solid #6956F6;border-top-color:transparent;animation:spin 0.8s linear infinite;margin-right:8px;"></div>
            Memuat riwayat...
        </div>
        <style>@keyframes spin{to{transform:rotate(360deg)}}</style>`;

    try {
        const token = getToken();
        const res   = await fetch('http://localhost:5001/api/predict/history?limit=5', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) { historyDiv.innerHTML = emptyHistory(); return; }

        const data = await res.json();

        if (data.success && data.history && data.history.length > 0) {
            historyDiv.innerHTML = data.history.map(h => {
                const dt   = new Date(h.created_at);
                const tgl  = dt.toLocaleDateString('id-ID', {day:'2-digit',month:'short',year:'numeric'});
                const jam  = dt.toLocaleTimeString('id-ID', {hour:'2-digit',minute:'2-digit'});
                const kwh  = h.next_day_kwh ? Math.round(h.next_day_kwh).toLocaleString('id-ID') : '-';
                // MAPE ditampilkan dalam desimal
                const mapeDecimal = h.mape ? (h.mape / 100).toFixed(4).replace('.', ',') : '-';

                return `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:14px;background:#ECECFC;border-radius:12px;margin-bottom:8px;transition:background .2s;"
                    onmouseover="this.style.background='rgba(105,86,246,0.12)'" onmouseout="this.style.background='#ECECFC'">
                    <div style="display:flex;align-items:center;gap:12px;">
                        <div style="width:36px;height:36px;background:rgba(105,86,246,0.12);border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                            <svg width="16" height="16" fill="none" stroke="#6956F6" stroke-width="2" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                            </svg>
                        </div>
                        <div>
                            <p style="color:#1e1b4b;font-weight:500;font-size:13px;">${h.dataset_filename || 'Dataset'}</p>
                            <p style="color:#A3A1AF;font-size:11px;margin-top:2px;">
                                ${h.total_rows} baris &nbsp;·&nbsp;
                                Prediksi: <span style="color:#6956F6;font-weight:500;">${kwh} kWh</span> &nbsp;·&nbsp;
                                MAPE: <span style="color:#059669;font-weight:500;">${mapeDecimal}</span> &nbsp;·&nbsp;
                                ${tgl} ${jam}
                            </p>
                        </div>
                    </div>
                    <a href="prediksi.html" style="color:#6956F6;font-size:12px;font-weight:500;text-decoration:none;flex-shrink:0;margin-left:16px;"
                        onmouseover="this.style.opacity='.7'" onmouseout="this.style.opacity='1'">
                        Lihat →
                    </a>
                </div>`;
            }).join('');
        } else {
            historyDiv.innerHTML = emptyHistory();
        }
    } catch (e) {
        console.error('History error:', e);
        historyDiv.innerHTML = emptyHistory();
    }
}

function emptyHistory() {
    return `
        <div style="text-align:center;padding:32px;">
            <div style="width:40px;height:40px;background:rgba(105,86,246,0.08);border-radius:12px;display:flex;align-items:center;justify-content:center;margin:0 auto 10px;">
                <svg width="20" height="20" fill="none" stroke="#A3A1AF" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
            </div>
            <p style="color:#A3A1AF;font-size:13px;">Belum ada riwayat prediksi</p>
            <p style="color:#A3A1AF;font-size:11px;margin-top:4px;">Upload data untuk memulai prediksi</p>
        </div>`;
}

// ─────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────
function showUploadError(message) {
    const el  = document.getElementById('errorDetails');
    const div = document.getElementById('errorMessage');
    if (el)  el.textContent = message;
    if (div) div.classList.remove('hidden');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}