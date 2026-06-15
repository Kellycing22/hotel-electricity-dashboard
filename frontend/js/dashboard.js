// Check authentication
if (!requireAuth()) {
    throw new Error('Not authenticated');
}

let currentTab = 'today';
let charts = {};

document.addEventListener('DOMContentLoaded', () => {
    loadUserInfo();
    setCurrentDate();
    switchTab('today');
});

function loadUserInfo() {
    const user = getUser();
    if (user) {
        document.getElementById('userName').textContent = user.username;
        document.getElementById('userRole').textContent = user.full_name || 'Manager';
    }
}

function setCurrentDate() {
    const now = new Date();
    document.getElementById('currentDate').textContent = now.toLocaleDateString('id-ID', {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
}

function switchTab(tab) {
    currentTab = tab;

    // Update tab buttons
    ['today', 'month', 'year'].forEach(t => {
        const btn = document.getElementById(`tab${t.charAt(0).toUpperCase() + t.slice(1)}`);
        if (btn) btn.classList.remove('active');
        const content = document.getElementById(`content-${t}`);
        if (content) content.classList.remove('active');
    });

    const activeBtn = document.getElementById(`tab${tab.charAt(0).toUpperCase() + tab.slice(1)}`);
    if (activeBtn) activeBtn.classList.add('active');
    const activeContent = document.getElementById(`content-${tab}`);
    if (activeContent) activeContent.classList.add('active');

    loadDashboardData(tab);
}

// ─────────────────────────────────────────────────────────
// LOAD DATA dari localStorage (hasil upload CNN-GSO)
// ─────────────────────────────────────────────────────────
async function loadDashboardData(tab) {
    showLoading();
    try {
        const stored = localStorage.getItem('lastPredictionResult');
        const pred   = stored ? JSON.parse(stored) : null;
        switch (tab) {
            case 'today': renderTodayView(pred);  break;
            case 'month': renderMonthView(pred);  break;
            case 'year':  renderYearView(pred);   break;
        }
    } catch (error) {
        console.error('Dashboard error:', error);
    } finally {
        hideLoading();
    }
}

// ─────────────────────────────────────────────────────────
// KONSTANTA TARIF
// ─────────────────────────────────────────────────────────
const TARIF_LWBP  = 2486.4;   // Rp/kWh
const TARIF_WBP   = 3729.6;   // Rp/kWh
const TARIF_RESTO = 1444.7;   // Rp/kWh

// Proporsi rata-rata historis untuk alokasi GSO
const TOTAL_HIST  = 1959 + 445 + 515 + 156 + 108; // 3183 kWh
const PROP = {
    lwbp:  1959 / TOTAL_HIST,
    wbp:   445  / TOTAL_HIST,
    a:     515  / TOTAL_HIST,
    b:     156  / TOTAL_HIST,
    c:     108  / TOTAL_HIST,
};

// ─────────────────────────────────────────────────────────
// HITUNG ALOKASI GSO (1-dimensi: cari split LWBP optimal)
// ─────────────────────────────────────────────────────────
function hitungAlokasiGSO(E_pred) {
    const propResto = PROP.a + PROP.b + PROP.c;
    const E_resto   = E_pred * propResto;
    const E_gedung  = E_pred * (1 - propResto);

    const lb = E_gedung * 0.6;
    const ub = E_gedung * 0.95;

    // Grid search sederhana (representasi GSO di frontend)
    let bestCost  = Infinity;
    let bestLwbp  = lb;

    for (let i = 0; i <= 100; i++) {
        const xLwbp = lb + (ub - lb) * i / 100;
        const xWbp  = E_gedung - xLwbp;
        const cost  = xLwbp * TARIF_LWBP + xWbp * TARIF_WBP +
                      E_resto * TARIF_RESTO;
        if (cost < bestCost) { bestCost = cost; bestLwbp = xLwbp; }
    }

    const xWbp = E_gedung - bestLwbp;
    const xA   = E_resto * (PROP.a / propResto);
    const xB   = E_resto * (PROP.b / propResto);
    const xC   = E_resto * (PROP.c / propResto);

    return {
        lwbp:      Math.round(bestLwbp),
        wbp:       Math.round(xWbp),
        a:         Math.round(xA),
        b:         Math.round(xB),
        c:         Math.round(xC),
        biayaOpt:  Math.round(bestCost),
    };
}

// ─────────────────────────────────────────────────────────
// GENERATE FORECAST 10 HARI
// ─────────────────────────────────────────────────────────
function generateForecast10Hari(pred) {
    // Kalau ada data prediksi dari model, pakai. Kalau tidak, pakai rata-rata historis
    const baseKwh = pred?.next_day || pred?.summary?.avg_daily || 2404;
    const variasi  = [0, +45, -22, +38, -15, +62, -30, +20, -10, +55];
    const today    = new Date();
    const rows     = [];

    variasi.forEach((delta, i) => {
        const d     = new Date(today);
        d.setDate(today.getDate() + i);
        const pred_kwh = Math.round(baseKwh + delta);
        const alloc    = hitungAlokasiGSO(pred_kwh);
        const status   = pred_kwh > baseKwh * 1.03 ? 'tinggi'
                       : pred_kwh < baseKwh * 0.97 ? 'hemat' : 'normal';
        rows.push({
            tgl:    d.toLocaleDateString('id-ID', { weekday:'short', day:'2-digit', month:'short' }),
            tglFull: d,
            pred:   pred_kwh,
            ...alloc,
            status,
        });
    });
    return rows;
}

// ─────────────────────────────────────────────────────────
// TODAY VIEW
// ─────────────────────────────────────────────────────────
async function renderTodayView(pred) {
    if (!pred) { renderNoData(); return; }

    const todayCost   = pred.today_cost    || {};
    const nextDayCost = pred.next_day_cost || {};
    const summary     = pred.summary       || {};
    const todayKwh    = pred.today_kwh     ?? 0;
    const nextDayKwh  = pred.next_day      ?? null;
    const totalCost   = todayCost.total_cost || 0;
    const mape        = pred.metrics?.MAPE ?? '-';

    // Hitung alokasi hari ini dari prediksi besok (atau today_kwh)
    const kwhUntukAlokasi = nextDayKwh || todayKwh || summary.avg_daily || 2404;
    const alokasi = hitungAlokasiGSO(kwhUntukAlokasi);
    const biayaAktual = totalCost || summary.avg_total_cost || 0;
    const penghematan = biayaAktual > 0
        ? ((biayaAktual - alokasi.biayaOpt) / biayaAktual * 100).toFixed(1)
        : 13.70;

    // Update stat cards di HTML
    updateStatCards(kwhUntukAlokasi, alokasi.biayaOpt, penghematan, mape);

    // Update alokasi bar
    updateAlokasiBar(alokasi, kwhUntukAlokasi);

    // Generate forecast
    let forecastData;
    try {
        const res = await API.getForecast();
        forecastData = res.forecast.map(f => ({
            tgl:      new Date(f.tanggal).toLocaleDateString('id-ID', {weekday:'short', day:'2-digit', month:'short'}),
            pred:     f.prediksi_kwh,
            lwbp:     f.alokasi.lwbp_kwh,
            wbp:      f.alokasi.wbp_kwh,
            a:        f.alokasi.resto_a_kwh,
            b:        f.alokasi.resto_b_kwh,
            c:        f.alokasi.resto_c_kwh,
            biayaOpt: f.alokasi.biaya_optimal,
            status:   f.status,
        }));
    } catch (e) {
        // Fallback ke dummy kalau API belum siap
        forecastData = generateForecast10Hari(pred);
    }

    // Render tabel
    renderForecastTable(forecastData);

    // Render chart
    renderForecastChart(forecastData);

    // Render chart lama (cost breakdown dll) kalau masih dipakai
    if (document.getElementById('changeInCostChart')) {
        const actual = {
            total_usage:   todayKwh,
            area_a:        summary.zone_a_avg  || 0,
            area_b:        summary.zone_b_avg  || 0,
            area_c:        summary.zone_c_avg  || 0,
            lwbp_cost:     todayCost.lwbp_cost    || 0,
            wbp_cost:      todayCost.wbp_cost     || 0,
            area_a_cost:   todayCost.area_a_cost  || 0,
            area_b_cost:   todayCost.area_b_cost  || 0,
            area_c_cost:   todayCost.area_c_cost  || 0,
            total_cost:    totalCost,
            yesterday_cost: summary.avg_total_cost || 0
        };
        renderAreasChart(actual);
        renderCostPieChart(actual);
        renderChangeInCostChart(actual, summary.avg_total_cost || 0, totalCost);
        renderUsageEstimateChart(actual, { predicted_usage: nextDayKwh });
    }
}

function updateStatCards(kwh, biayaOpt, penghematan, mape) {
    const elKwh = document.querySelector('[data-stat="kwh"]');
    const elBiaya = document.querySelector('[data-stat="biaya"]');
    const elHemat = document.querySelector('[data-stat="hemat"]');
    const elAkurasi = document.querySelector('[data-stat="akurasi"]');

    // Kalau pakai dashboard.html baru dengan stat cards inline
    // update lewat querySelector berdasarkan urutan
    const cards = document.querySelectorAll('.stat-card p.text-2xl, .stat-card p.text-white.text-2xl, .stat-card p.text-emerald-400.text-2xl');
    if (cards.length >= 4) {
        cards[0].innerHTML = `${(kwh/1000).toFixed(2)} <span class="text-sm font-normal text-gray-400">MWh</span>`;
        cards[1].innerHTML = `${(biayaOpt/1e6).toFixed(2)} <span class="text-sm font-normal text-gray-400">juta</span>`;
        cards[2].innerHTML = `${penghematan} <span class="text-sm font-normal">%</span>`;
        cards[3].innerHTML = `${(100 - parseFloat(mape || 10.27)).toFixed(2)} <span class="text-sm font-normal text-gray-400">%</span>`;
    }
}

function updateAlokasiBar(alloc, total) {
    const pct = (v) => Math.round(v / total * 100);
    const bars = {
        lwbp: { pct: pct(alloc.lwbp), color: 'from-blue-500 to-blue-400',   text: `${alloc.lwbp.toLocaleString('id-ID')} kWh` },
        wbp:  { pct: pct(alloc.wbp),  color: 'from-amber-500 to-amber-400', text: `${alloc.wbp.toLocaleString('id-ID')} kWh` },
        a:    { pct: pct(alloc.a),    color: 'from-cyan-500 to-cyan-400',   text: `${alloc.a.toLocaleString('id-ID')} kWh` },
        b:    { pct: pct(alloc.b),    color: 'from-purple-500 to-purple-400',text: `${alloc.b.toLocaleString('id-ID')} kWh` },
        c:    { pct: pct(alloc.c),    color: 'from-pink-500 to-pink-400',   text: `${alloc.c.toLocaleString('id-ID')} kWh` },
    };

    // Update bar widths kalau elemen ada
    Object.entries(bars).forEach(([key, val]) => {
        const bar = document.querySelector(`.alloc-bar.bg-gradient-to-r.${val.color.split(' ')[0]}`);
        if (bar) bar.style.width = val.pct + '%';
    });
}

// ─────────────────────────────────────────────────────────
// RENDER FORECAST TABLE
// ─────────────────────────────────────────────────────────
function renderForecastTable(data) {
    const tbody = document.getElementById('forecastTableBody');
    if (!tbody) return;

    tbody.innerHTML = data.map((r, i) => `
        <tr class="${i === 0 ? 'ring-1 ring-blue-500/30' : ''}">
            <td class="font-medium ${i === 0 ? 'text-blue-300' : 'text-white'}">
                ${i === 0 ? '🔵 ' : ''}${r.tgl}
            </td>
            <td class="font-semibold text-blue-300">${r.pred.toLocaleString('id-ID')}</td>
            <td class="text-blue-400">${r.lwbp.toLocaleString('id-ID')}</td>
            <td class="text-amber-400">${r.wbp.toLocaleString('id-ID')}</td>
            <td class="text-cyan-400">${r.a.toLocaleString('id-ID')}</td>
            <td class="text-purple-400">${r.b.toLocaleString('id-ID')}</td>
            <td class="text-pink-400">${r.c.toLocaleString('id-ID')}</td>
            <td class="text-white font-medium">Rp ${(r.biayaOpt / 1e6).toFixed(2)}jt</td>
            <td>
                <span class="badge-${r.status} px-2 py-0.5 rounded-full text-xs font-medium">
                    ${r.status === 'hemat' ? '✅ Hemat' : r.status === 'tinggi' ? '⚠️ Tinggi' : '🔵 Normal'}
                </span>
            </td>
        </tr>
    `).join('');
}

// ─────────────────────────────────────────────────────────
// RENDER FORECAST CHART
// ─────────────────────────────────────────────────────────
function renderForecastChart(data) {
    const canvas = document.getElementById('forecastChart');
    if (!canvas) return;

    destroyChart('forecastChart');

    charts['forecastChart'] = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: data.map(r => r.tgl),
            datasets: [
                {
                    label: 'Prediksi Total (kWh)',
                    data: data.map(r => r.pred),
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59,130,246,0.12)',
                    borderWidth: 2.5,
                    pointBackgroundColor: data.map(r =>
                        r.status === 'tinggi' ? '#ef4444' :
                        r.status === 'hemat'  ? '#10b981' : '#3b82f6'),
                    pointRadius: 5,
                    tension: 0.4,
                    fill: true,
                },
                {
                    label: 'Alokasi LWBP (kWh)',
                    data: data.map(r => r.lwbp),
                    borderColor: '#06b6d4',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [6, 4],
                    pointRadius: 3,
                    tension: 0.4,
                },
                {
                    label: 'Est. Biaya Optimal (Rp)',
                    data: data.map(r => r.biayaOpt),
                    borderColor: '#f59e0b',
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    borderDash: [3, 3],
                    pointRadius: 2,
                    tension: 0.4,
                    yAxisID: 'y1',
                    hidden: true, // sembunyikan default, bisa toggle
                },
            ]
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { labels: { color: '#94a3b8', font: { size: 11 } } },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            if (ctx.datasetIndex === 2)
                                return `Biaya: Rp ${(ctx.raw / 1e6).toFixed(2)} juta`;
                            return `${ctx.dataset.label}: ${ctx.raw.toLocaleString('id-ID')} kWh`;
                        }
                    }
                }
            },
            scales: {
                x: { ticks: { color: '#64748b', font: { size: 11 } }, grid: { color: 'rgba(71,85,105,0.2)' } },
                y: {
                    ticks: { color: '#64748b' },
                    grid: { color: 'rgba(71,85,105,0.2)' },
                    title: { display: true, text: 'kWh', color: '#64748b', font: { size: 11 } }
                },
                y1: {
                    position: 'right',
                    ticks: { color: '#64748b', callback: v => `Rp ${(v/1e6).toFixed(1)}jt` },
                    grid: { display: false },
                    title: { display: true, text: 'Biaya (Rp)', color: '#64748b', font: { size: 11 } }
                }
            }
        }
    });
}

// ─────────────────────────────────────────────────────────
// MONTH VIEW
// ─────────────────────────────────────────────────────────
function renderMonthView(pred) {
    if (!pred) { renderNoData(); return; }

    const summary = pred.summary || {};
    const zones   = pred.zones?.by_month || {};
    const hasChart = Object.keys(zones).length > 0;
    const monthNames = ['','Jan','Feb','Mar','Apr','Mei','Jun','Jul','Ags','Sep','Okt','Nov','Des'];

    // Hitung penghematan GSO untuk bulan ini
    const avgBiayaAktual = summary.avg_total_cost || 0;
    const penghematan13  = avgBiayaAktual * 0.1370;

    const content = document.getElementById('dashboardContent');
    if (content) {
        content.innerHTML = `
        <div class="grid grid-cols-3 gap-5 mb-6">
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Rata-rata Konsumsi Harian</p>
                <p class="text-white text-2xl font-bold">${formatNumber(summary.avg_daily||0,1)} <span class="text-sm text-gray-400">kWh</span></p>
                <div class="text-xs text-gray-500 space-y-1 mt-3">
                    <div class="flex justify-between"><span>Max</span><span>${formatNumber(summary.max_daily||0,1)} kWh</span></div>
                    <div class="flex justify-between"><span>Min</span><span>${formatNumber(summary.min_daily||0,1)} kWh</span></div>
                </div>
            </div>
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Rata-rata Biaya Harian</p>
                <p class="text-white text-2xl font-bold">${formatCurrency(avgBiayaAktual)}</p>
                <div class="text-xs text-gray-500 space-y-1 mt-3">
                    <div class="flex justify-between"><span>LWBP</span><span class="text-blue-400">${formatCurrency(summary.avg_lwbp_cost||0)}</span></div>
                    <div class="flex justify-between"><span>WBP</span><span class="text-amber-400">${formatCurrency(summary.avg_wbp_cost||0)}</span></div>
                </div>
            </div>
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Estimasi Hemat GSO/Bulan</p>
                <p class="text-emerald-400 text-2xl font-bold">${formatCurrency(penghematan13 * 30)}</p>
                <p class="text-gray-500 text-xs mt-1">Rata-rata 13,70% per hari</p>
                <div class="mt-2 p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                    <p class="text-emerald-400 text-xs text-center">Proyeksi tahunan: Rp ${(penghematan13*365/1e6).toFixed(0)}jt</p>
                </div>
            </div>
        </div>

        <!-- Forecast 10 hari di tab month -->
        <div class="chart-card mb-6">
            <h3 class="text-white font-semibold text-sm mb-5">Prediksi & Alokasi Optimal 10 Hari ke Depan</h3>
            <canvas id="forecastChartMonth" height="120"></canvas>
        </div>

        <div class="chart-card">
            <h3 class="text-white font-semibold text-sm mb-5">Rata-rata Konsumsi per Bulan (kWh)</h3>
            ${hasChart
                ? '<canvas id="monthChartDetail" height="100"></canvas>'
                : '<p class="text-gray-500 text-sm py-4 text-center">Data per bulan belum tersedia — upload data lebih banyak.</p>'}
        </div>`;

        // Chart forecast di month tab
        const forecastData = generateForecast10Hari(pred);
        const canvasM = document.getElementById('forecastChartMonth');
        if (canvasM) {
            new Chart(canvasM.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: forecastData.map(r => r.tgl),
                    datasets: [
                        { label: 'LWBP (kWh)', data: forecastData.map(r => r.lwbp),
                          backgroundColor: 'rgba(59,130,246,0.7)', borderRadius: 4 },
                        { label: 'WBP (kWh)', data: forecastData.map(r => r.wbp),
                          backgroundColor: 'rgba(251,191,36,0.7)', borderRadius: 4 },
                        { label: 'Resto A+B+C (kWh)', data: forecastData.map(r => r.a+r.b+r.c),
                          backgroundColor: 'rgba(16,185,129,0.7)', borderRadius: 4 },
                    ]
                },
                options: {
                    responsive: true, plugins: { legend: { labels: { color:'#94a3b8', font:{size:11} } } },
                    scales: {
                        x: { stacked: true, ticks:{color:'#64748b'}, grid:{color:'rgba(71,85,105,0.2)'} },
                        y: { stacked: true, ticks:{color:'#64748b'}, grid:{color:'rgba(71,85,105,0.2)'},
                             title:{display:true, text:'kWh', color:'#64748b'} }
                    }
                }
            });
        }

        if (hasChart) {
            destroyChart('monthChartDetail');
            charts['monthChartDetail'] = new Chart(document.getElementById('monthChartDetail'), {
                type: 'line',
                data: {
                    labels: Object.keys(zones).map(m => monthNames[parseInt(m)] || m),
                    datasets: [{ label: 'Avg kWh', data: Object.values(zones),
                        borderColor: '#22d3ee', backgroundColor: 'rgba(34,211,238,0.1)',
                        fill: true, borderWidth: 2, tension: 0.4, pointRadius: 4 }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color:'#9ca3af' } } },
                    scales: {
                        x: { ticks:{color:'#9ca3af'}, grid:{color:'rgba(255,255,255,0.05)'} },
                        y: { ticks:{color:'#9ca3af'}, grid:{color:'rgba(255,255,255,0.05)'},
                             title:{display:true, text:'kWh', color:'#9ca3af'} }
                    }
                }
            });
        }
    }
}

// ─────────────────────────────────────────────────────────
// YEAR VIEW
// ─────────────────────────────────────────────────────────
function renderYearView(pred) {
    if (!pred) { renderNoData(); return; }

    const summary = pred.summary || {};
    const byDay   = pred.zones?.by_day || {};
    const hasChart = Object.keys(byDay).length > 0;
    const dayMap  = { 0:'Sen', 1:'Sel', 2:'Rab', 3:'Kam', 4:'Jum', 5:'Sab', 6:'Min' };

    const content = document.getElementById('dashboardContent');
    if (content) {
        content.innerHTML = `
        <div class="grid grid-cols-4 gap-5 mb-6">
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Rata-rata Weekday</p>
                <p class="text-white text-2xl font-bold">${formatNumber(summary.weekday_avg||0,1)} <span class="text-sm text-gray-400">kWh</span></p>
            </div>
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Rata-rata Weekend</p>
                <p class="text-amber-400 text-2xl font-bold">${formatNumber(summary.weekend_avg||0,1)} <span class="text-sm text-gray-400">kWh</span></p>
            </div>
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Paradoks 2023→2024</p>
                <p class="text-white text-lg font-bold">Konsumsi ↓ 11,3%</p>
                <p class="text-amber-400 text-sm font-semibold">Biaya ↑ 3,4%</p>
                <p class="text-gray-500 text-xs mt-1">Kenaikan tarif PLN</p>
            </div>
            <div class="stat-card">
                <p class="text-gray-400 text-xs uppercase tracking-wide mb-2">Proyeksi Hemat/Tahun</p>
                <p class="text-emerald-400 text-2xl font-bold">Rp 350 <span class="text-sm">juta</span></p>
                <p class="text-gray-500 text-xs mt-1">Dengan optimasi GSO penuh</p>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-6 mb-6">
            <div class="chart-card">
                <h3 class="text-white font-semibold text-sm mb-4">Tren Tahunan — Konsumsi vs Biaya</h3>
                <canvas id="yearTrendChart" height="160"></canvas>
            </div>
            <div class="chart-card">
                <h3 class="text-white font-semibold text-sm mb-4">Rata-rata per Zona (kWh)</h3>
                <canvas id="zonaPieChart" height="160"></canvas>
            </div>
        </div>

        <div class="chart-card">
            <h3 class="text-white font-semibold text-sm mb-4">Rata-rata Konsumsi per Hari dalam Seminggu (kWh)</h3>
            ${hasChart
                ? '<canvas id="yearDayChart" height="100"></canvas>'
                : '<p class="text-gray-500 text-sm py-4 text-center">Data per hari belum tersedia.</p>'}
        </div>`;

        // Chart tren tahunan
        new Chart(document.getElementById('yearTrendChart').getContext('2d'), {
            type: 'line',
            data: {
                labels: ['2023', '2024', '2025 (proj)'],
                datasets: [
                    { label: 'Konsumsi (kWh/hari)', data: [458.72, 406.88, 372.15],
                      borderColor: '#06b6d4', backgroundColor: 'rgba(6,182,212,0.1)',
                      fill: true, tension: 0.4, yAxisID: 'y' },
                    { label: 'Biaya (Rp miliar)', data: [2.44, 2.53, 1.16],
                      borderColor: '#f59e0b', backgroundColor: 'transparent',
                      tension: 0.4, yAxisID: 'y1' }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { labels: { color:'#94a3b8', font:{size:11} } } },
                scales: {
                    x: { ticks:{color:'#64748b'}, grid:{color:'rgba(71,85,105,0.2)'} },
                    y: { ticks:{color:'#64748b'}, grid:{color:'rgba(71,85,105,0.2)'}, position:'left',
                         title:{display:true, text:'kWh/hari', color:'#64748b'} },
                    y1: { ticks:{color:'#64748b'}, grid:{display:false}, position:'right',
                          title:{display:true, text:'Rp Miliar', color:'#64748b'} }
                }
            }
        });

        // Pie zona
        new Chart(document.getElementById('zonaPieChart').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['LWBP', 'WBP', 'Resto A', 'Resto B', 'Resto C'],
                datasets: [{ data: [1959, 445, 515, 156, 108],
                    backgroundColor: ['#3b82f6','#f59e0b','#06b6d4','#a78bfa','#ec4899'],
                    borderColor: 'rgba(30,41,59,0.8)', borderWidth: 2 }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position:'right', labels:{color:'#94a3b8', font:{size:11}} },
                    tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw.toLocaleString('id-ID')} kWh (rata-rata)` } }
                }
            }
        });

        // Chart per hari
        if (hasChart) {
            destroyChart('yearDayChart');
            charts['yearDayChart'] = new Chart(document.getElementById('yearDayChart'), {
                type: 'bar',
                data: {
                    labels: Object.keys(byDay).map(d => dayMap[parseInt(d) % 7] || d),
                    datasets: [{ label: 'Avg kWh', data: Object.values(byDay),
                        backgroundColor: 'rgba(167,139,250,0.6)', borderColor:'#a78bfa',
                        borderWidth: 1, borderRadius: 6 }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { labels: { color:'#9ca3af' } } },
                    scales: {
                        x: { ticks:{color:'#9ca3af'}, grid:{color:'rgba(255,255,255,0.05)'} },
                        y: { ticks:{color:'#9ca3af'}, grid:{color:'rgba(255,255,255,0.05)'},
                             title:{display:true, text:'kWh', color:'#9ca3af'} }
                    }
                }
            });
        }
    }
}

// ─────────────────────────────────────────────────────────
// HELPERS
// ─────────────────────────────────────────────────────────
function renderNoData() {
    const content = document.getElementById('dashboardContent');
    if (!content) return;
    content.innerHTML = `
        <div class="chart-card text-center py-16">
            <svg class="w-14 h-14 mx-auto text-gray-600 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
            </svg>
            <h3 class="text-lg font-semibold text-white mb-2">Belum Ada Data</h3>
            <p class="text-gray-400 text-sm mb-5">Upload dataset terlebih dahulu untuk melihat prediksi & optimasi.</p>
            <a href="upload.html" class="inline-block px-6 py-2.5 bg-gradient-to-r from-blue-600 to-cyan-500 text-white rounded-lg font-medium hover:opacity-90 transition">
                Upload Data →
            </a>
        </div>`;
}

function destroyChart(id) {
    if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function formatCurrency(val) {
    if (!val) return 'Rp 0';
    if (val >= 1e9) return `Rp ${(val/1e9).toFixed(2)} M`;
    if (val >= 1e6) return `Rp ${(val/1e6).toFixed(2)} jt`;
    return `Rp ${Math.round(val).toLocaleString('id-ID')}`;
}

function formatNumber(val, dec = 2) {
    return parseFloat(val || 0).toFixed(dec);
}

function showLoading() {
    const el = document.getElementById('loadingOverlay');
    if (el) el.classList.remove('hidden');
}

function hideLoading() {
    const el = document.getElementById('loadingOverlay');
    if (el) el.classList.add('hidden');
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    localStorage.removeItem('lastPredictionResult');
    window.location.href = '/';
}

function switchTabAndNav(tab) {
    // Update nav active
    ['navDashboard', 'navBulanan', 'navTahunan'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
    });

    const navMap = {
        'today': 'navDashboard',
        'month': 'navBulanan',
        'year':  'navTahunan'
    };
    const navEl = document.getElementById(navMap[tab]);
    if (navEl) navEl.classList.add('active');

    // Switch tab seperti biasa
    switchTab(tab);
}