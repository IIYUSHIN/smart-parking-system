/**
 * Smart Parking — Chart.js Charts
 * 1. Occupancy Timeline (line chart, last 24h)
 * 2. Daily Utilization (bar chart, 7 days)
 */

let timelineChart = null;
let dailyChart = null;

// ── CHART 1: OCCUPANCY TIMELINE ──
async function initTimelineChart() {
    try {
        const res = await fetch('/api/history?hours=24');
        const json = await res.json();
        const data = (json.data || []).reverse(); // oldest first

        const ctx = document.getElementById('chart-timeline');
        if (!ctx) return;

        timelineChart = new Chart(ctx.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.map(e => {
                    const t = e.event_time || '';
                    return t.substring(11, 16); // HH:MM
                }),
                datasets: [{
                    label: 'Occupancy',
                    data: data.map(e => e.occupancy_after),
                    borderColor: '#00e5ff',
                    backgroundColor: 'rgba(0, 229, 255, 0.08)',
                    fill: true,
                    tension: 0.35,
                    pointRadius: 1.5,
                    pointHoverRadius: 5,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: {
                        min: 0, max: 4,
                        ticks: { stepSize: 1, color: '#9e9e9e', font: { size: 11 } },
                        grid: { color: 'rgba(255,255,255,0.04)' }
                    },
                    x: {
                        ticks: { maxTicksLimit: 12, color: '#9e9e9e', font: { size: 10 } },
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a2332',
                        titleColor: '#e0e0e0',
                        bodyColor: '#00e5ff',
                        borderColor: 'rgba(0,229,255,0.2)',
                        borderWidth: 1
                    }
                }
            }
        });
    } catch (err) {
        console.error('[Charts] Timeline init error:', err);
    }
}

// ── CHART 2: DAILY UTILIZATION ──
async function initDailyChart() {
    try {
        const res = await fetch('/api/analytics/daily?days=7');
        const json = await res.json();
        const data = (json.data || []).reverse(); // oldest first

        const ctx = document.getElementById('chart-daily');
        if (!ctx) return;

        dailyChart = new Chart(ctx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: data.map(d => {
                    const parts = (d.date || '').split('-');
                    return parts.length === 3 ? `${parts[1]}/${parts[2]}` : d.date;
                }),
                datasets: [{
                    label: 'Utilization %',
                    data: data.map(d => d.avg_utilization || 0),
                    backgroundColor: 'rgba(0, 191, 165, 0.6)',
                    borderColor: '#00bfa5',
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        min: 0, max: 100,
                        ticks: { callback: v => v + '%', color: '#9e9e9e', font: { size: 11 } },
                        grid: { color: 'rgba(255,255,255,0.04)' }
                    },
                    x: {
                        ticks: { color: '#9e9e9e', font: { size: 10 } },
                        grid: { display: false }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#1a2332',
                        titleColor: '#e0e0e0',
                        bodyColor: '#00bfa5',
                        callbacks: {
                            label: ctx => `${ctx.parsed.y.toFixed(1)}% utilization`
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('[Charts] Daily init error:', err);
    }
}

// ── LIVE UPDATE POINT ──
function addChartDataPoint(data) {
    if (!timelineChart) return;

    const now = new Date();
    const label = now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

    timelineChart.data.labels.push(label);
    timelineChart.data.datasets[0].data.push(data.current_count);

    // Keep max 80 data points
    if (timelineChart.data.labels.length > 80) {
        timelineChart.data.labels.shift();
        timelineChart.data.datasets[0].data.shift();
    }

    timelineChart.update('none'); // skip animation for performance
}

// ── INIT ──
function initCharts() {
    initTimelineChart();
    initDailyChart();
}
