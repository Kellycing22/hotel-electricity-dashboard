// Chart.js default configuration
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Poppins', sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 15;

const commonOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: { legend: { display: true, position: 'bottom' } }
};

function destroyChart(chartId) {
    if (charts[chartId]) {
        charts[chartId].destroy();
        delete charts[chartId];
    }
}

// ACTIVE AREAS bar chart
function renderAreasChart(data) {
    destroyChart('areasChart');
    const ctx = document.getElementById('areasChart');
    if (!ctx) return;
    charts['areasChart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Building', 'Area A', 'Area B', 'Area C'],
            datasets: [{
                label: 'Electricity Used (kWh)',
                data: [data.total_usage||0, data.area_a||0, data.area_b||0, data.area_c||0],
                backgroundColor: ['rgba(99,102,241,0.8)','rgba(59,130,246,0.8)','rgba(168,85,247,0.8)','rgba(34,197,94,0.8)'],
                borderColor:     ['rgb(99,102,241)',      'rgb(59,130,246)',     'rgb(168,85,247)',     'rgb(34,197,94)'],
                borderWidth: 2,
                borderRadius: 8
            }]
        },
        options: {
            ...commonOptions,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(148,163,184,0.1)' },
                    ticks: { callback: v => formatNumber(v, 2) + ' kWh' }
                },
                x: { grid: { display: false } }
            },
            plugins: {
                ...commonOptions.plugins,
                tooltip: { callbacks: { label: c => formatNumber(c.parsed.y, 2) + ' kWh' } }
            }
        }
    });
}

// COST PIE doughnut
function renderCostPieChart(data) {
    destroyChart('costPieChart');
    const ctx = document.getElementById('costPieChart');
    if (!ctx) return;
    charts['costPieChart'] = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Building LWBP','Building WBP','Restaurant A','Restaurant B','Restaurant C'],
            datasets: [{
                data: [data.lwbp_cost||0, data.wbp_cost||0, data.area_a_cost||0, data.area_b_cost||0, data.area_c_cost||0],
                backgroundColor: ['rgba(6,182,212,0.8)','rgba(251,191,36,0.8)','rgba(59,130,246,0.8)','rgba(168,85,247,0.8)','rgba(34,197,94,0.8)'],
                borderColor:     ['rgb(6,182,212)',       'rgb(251,191,36)',     'rgb(59,130,246)',     'rgb(168,85,247)',     'rgb(34,197,94)'],
                borderWidth: 2
            }]
        },
        options: {
            ...commonOptions,
            cutout: '60%',
            plugins: {
                ...commonOptions.plugins,
                legend: { position: 'right' },
                tooltip: {
                    callbacks: {
                        label: function(c) {
                            const total = c.dataset.data.reduce((a,b) => a+b, 0);
                            const pct   = ((c.parsed / total) * 100).toFixed(1);
                            return `${c.label}: ${formatCurrency(c.parsed)} (${pct}%)`;
                        }
                    }
                }
            }
        }
    });
}

// CHANGE IN COST bar (rata-rata historis vs hari ini)
function renderChangeInCostChart(data, yesterdayCost, todayCost) {
    destroyChart('changeInCostChart');
    const ctx = document.getElementById('changeInCostChart');
    if (!ctx) return;
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    charts['changeInCostChart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [
                yesterday.toLocaleDateString('id-ID', { month: 'short', day: 'numeric' }),
                today.toLocaleDateString('id-ID',     { month: 'short', day: 'numeric' })
            ],
            datasets: [{
                data: [yesterdayCost, todayCost],
                backgroundColor: ['rgba(20,184,166,0.8)', 'rgba(20,184,166,0.8)'],
                borderColor:     ['rgb(20,184,166)',       'rgb(20,184,166)'],
                borderWidth: 0,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => formatCurrency(c.parsed.y) } }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    grid: { color: 'rgba(148,163,184,0.1)', borderDash: [5,5] },
                    ticks: { callback: v => 'Rp ' + (v/1000000).toFixed(1) + 'M' }
                },
                x: { grid: { display: false } }
            }
        }
    });
}


function renderUsageEstimateChart(actual, prediction) {
    destroyChart('usageEstimateChart');
    const ctx = document.getElementById('usageEstimateChart');
    if (!ctx) return;
    const actualKwh    = actual.total_usage         || 0;
    const predictedKwh = prediction.predicted_usage ?? actualKwh;
    charts['usageEstimateChart'] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Start','Week 1','Week 2','Now','Week 3','Week 4','End'],
            datasets: [
                {
                    label: 'Actual',
                    data: [0, null, null, actualKwh, null, null, null],
                    borderColor: 'rgb(239,68,68)', backgroundColor: 'rgba(239,68,68,0.3)',
                    borderWidth: 3, fill: true, tension: 0.4,
                    pointRadius: [0,0,0,6,0,0,0],
                    pointBackgroundColor: 'rgb(239,68,68)',
                    pointBorderColor: 'white', pointBorderWidth: 2
                },
                {
                    label: 'Predicted',
                    data: [null, null, null, actualKwh, null, null, predictedKwh],
                    borderColor: 'rgb(99,102,241)', backgroundColor: 'rgba(99,102,241,0.3)',
                    borderWidth: 3, fill: true, tension: 0.4, borderDash: [5,5],
                    pointRadius: [0,0,0,0,6,6,6],
                    pointBackgroundColor: 'rgb(239,68,68)',
                    pointBorderColor: 'white', pointBorderWidth: 2
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: c => c.parsed.y !== null ? formatNumber(c.parsed.y, 2) + ' kWh' : '' } }
            },
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { callback: v => formatNumber(v,1)+' kWh' } },
                x: { grid: { color: 'rgba(148,163,184,0.1)' } }
            }
        }
    });
}

// MONTH LINE chart
function renderMonthChart(dailyData) {
    destroyChart('monthChart');
    const ctx = document.getElementById('monthChart');
    if (!ctx) return;
    charts['monthChart'] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyData.map(d => new Date(d.date).getDate()),
            datasets: [
                { label: 'Actual',    data: dailyData.map(d => d.actual),    borderColor: 'rgb(59,130,246)',  backgroundColor: 'rgba(59,130,246,0.1)',  borderWidth:3, tension:0.4, fill:true, pointRadius:4 },
                { label: 'Predicted', data: dailyData.map(d => d.predicted), borderColor: 'rgb(168,85,247)', backgroundColor: 'rgba(168,85,247,0.1)', borderWidth:3, tension:0.4, fill:true, pointRadius:4, borderDash:[5,5] }
            ]
        },
        options: {
            ...commonOptions,
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(148,163,184,0.1)' }, ticks: { callback: v => formatNumber(v,2)+' kWh' } },
                x: { grid: { color: 'rgba(148,163,184,0.1)' } }
            },
            plugins: { ...commonOptions.plugins, tooltip: { callbacks: { label: c => c.parsed.y !== null ? `${c.dataset.label}: ${formatNumber(c.parsed.y,2)} kWh` : '' } } }
        }
    });
}

// YEAR BAR+LINE chart
function renderYearChart(monthlyData) {
    destroyChart('yearChart');
    const ctx = document.getElementById('yearChart');
    if (!ctx) return;
    const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const types = monthlyData.map(d => d.type);
    const bgColors = types.map(t => t==='actual' ? 'rgba(34,197,94,0.8)' : t==='predicted' ? 'rgba(59,130,246,0.8)' : 'rgba(148,163,184,0.5)');
    charts['yearChart'] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: monthlyData.map(d => monthNames[d.month-1]),
            datasets: [
                { label: 'Cost (IDR)', data: monthlyData.map(d=>d.cost), backgroundColor: bgColors, borderRadius:8, borderWidth:2, yAxisID:'y' },
                { label: 'Usage (kWh)', data: monthlyData.map(d=>d.usage), type:'line', borderColor:'rgb(251,191,36)', backgroundColor:'rgba(251,191,36,0.1)', borderWidth:3, tension:0.4, fill:false, yAxisID:'y1', pointRadius:5 }
            ]
        },
        options: {
            ...commonOptions,
            scales: {
                y:  { type:'linear', display:true, position:'left',  beginAtZero:true, grid:{ color:'rgba(148,163,184,0.1)' }, ticks:{ callback: v => 'Rp '+(v/1000000).toFixed(1)+'M' } },
                y1: { type:'linear', display:true, position:'right', beginAtZero:true, grid:{ drawOnChartArea:false }, ticks:{ callback: v => formatNumber(v,1)+' kWh' } },
                x:  { grid:{ display:false } }
            },
            plugins: {
                ...commonOptions.plugins,
                tooltip: { callbacks: { label: c => c.datasetIndex===0 ? formatCurrency(c.parsed.y) : formatNumber(c.parsed.y,2)+' kWh', afterLabel: c => types[c.dataIndex] ? `(${types[c.dataIndex]})` : '' } }
            }
        }
    });
}