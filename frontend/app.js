/**
 * SmartPark v2.0 — Frontend Application
 * SPA Router + API Client + Charts + WebSocket + Auth
 */

// ═══════════════════════════════════════
// STATE
// ═══════════════════════════════════════
const state = {
    currentPage: 'landing',
    user: null,
    token: null,
    locations: [],
    selectedZone: null,
    socket: null,
    charts: {},
};

// ═══════════════════════════════════════
// API CLIENT
// ═══════════════════════════════════════
const API = {
    async get(url) {
        const headers = {};
        if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
        const res = await fetch(url, { headers });
        return res.json();
    },
    async post(url, body) {
        const headers = { 'Content-Type': 'application/json' };
        if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
        const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
        return res.json();
    }
};

// ═══════════════════════════════════════
// SPA ROUTER
// ═══════════════════════════════════════
function navigate(page) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    // Show target
    const target = document.getElementById(`page-${page}`);
    if (target) target.classList.add('active');

    // Update nav active state
    document.querySelectorAll('.navbar-links a').forEach(a => {
        a.classList.toggle('active', a.dataset.page === page);
    });

    state.currentPage = page;
    window.scrollTo(0, 0);

    // Load page data
    if (page === 'locations') loadLocations();
    if (page === 'dashboard') loadDashboard();
    if (page === 'profile') loadProfile();
}

// Nav link clicks
document.querySelectorAll('.navbar-links a').forEach(a => {
    a.addEventListener('click', e => {
        e.preventDefault();
        navigate(a.dataset.page);
    });
});

// Navbar scroll effect
window.addEventListener('scroll', () => {
    document.getElementById('navbar').classList.toggle('scrolled', window.scrollY > 20);
});

// Intersection observer for fade-in animations
const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
        if (e.isIntersecting) e.target.classList.add('visible');
    });
}, { threshold: 0.1 });
document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

// Mobile nav toggle
function toggleMobileNav() {
    const links = document.getElementById('navLinks');
    links.style.display = links.style.display === 'flex' ? 'none' : 'flex';
}

// ═══════════════════════════════════════
// AUTH
// ═══════════════════════════════════════
function switchAuthTab(tab) {
    document.getElementById('loginForm').classList.toggle('hidden', tab !== 'login');
    document.getElementById('registerForm').classList.toggle('hidden', tab !== 'register');
    document.getElementById('tabLogin').classList.toggle('active', tab === 'login');
    document.getElementById('tabRegister').classList.toggle('active', tab === 'register');
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const errEl = document.getElementById('loginError');
    errEl.textContent = '';

    const res = await API.post('/api/auth/login', { email, password });
    if (res.status === 'ok') {
        state.user = res.data.user;
        state.token = res.data.token;
        localStorage.setItem('sp_token', state.token);
        localStorage.setItem('sp_user', JSON.stringify(state.user));
        updateAuthUI();
        navigate('landing');
    } else {
        errEl.textContent = res.message || 'Login failed';
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const errEl = document.getElementById('registerError');
    errEl.textContent = '';

    const body = {
        name: document.getElementById('regName').value,
        email: document.getElementById('regEmail').value,
        password: document.getElementById('regPassword').value,
        phone: document.getElementById('regPhone').value || undefined,
        vehicle_plate: document.getElementById('regVehicle').value || undefined
    };

    const res = await API.post('/api/auth/register', body);
    if (res.status === 'ok') {
        state.user = res.data.user;
        state.token = res.data.token;
        localStorage.setItem('sp_token', state.token);
        localStorage.setItem('sp_user', JSON.stringify(state.user));
        updateAuthUI();
        navigate('landing');
    } else {
        errEl.textContent = res.message || 'Registration failed';
    }
}

function logout() {
    state.user = null;
    state.token = null;
    localStorage.removeItem('sp_token');
    localStorage.removeItem('sp_user');
    updateAuthUI();
    navigate('landing');
}

function updateAuthUI() {
    const loggedIn = !!state.user;
    document.getElementById('btnLogin').classList.toggle('hidden', loggedIn);
    document.getElementById('btnSignup').classList.toggle('hidden', loggedIn);
    document.getElementById('btnProfile').classList.toggle('hidden', !loggedIn);
    document.getElementById('btnLogout').classList.toggle('hidden', !loggedIn);
}

// Restore session
function restoreSession() {
    const token = localStorage.getItem('sp_token');
    const user = localStorage.getItem('sp_user');
    if (token && user) {
        state.token = token;
        state.user = JSON.parse(user);
        updateAuthUI();
    }
}

// ═══════════════════════════════════════
// LOCATIONS PAGE
// ═══════════════════════════════════════
const LOC_ICONS = {
    MALL: '🏬', AIRPORT: '✈️', CORPORATE: '🏢',
    UNIVERSITY: '🎓', HOSPITAL: '🏥'
};
const LOC_COLORS = {
    MALL: '#ff6b6b', AIRPORT: '#4ecdc4', CORPORATE: '#45b7d1',
    UNIVERSITY: '#96ceb4', HOSPITAL: '#ff8a65'
};

async function loadLocations() {
    const grid = document.getElementById('locationsGrid');
    grid.innerHTML = '<div class="spinner"></div>';

    const res = await API.get('/api/locations');
    if (res.status !== 'ok') {
        grid.innerHTML = '<p class="text-muted">Failed to load locations</p>';
        return;
    }

    state.locations = res.data;
    let totalAvail = 0;

    grid.innerHTML = res.data.map(loc => {
        const util = loc.utilization_percent || 0;
        const avail = loc.total_available || 0;
        totalAvail += avail;
        const icon = LOC_ICONS[loc.location_type] || '🅿️';
        const statusBadge = util < 60 ? 'badge-success' :
                           (util < 85 ? 'badge-warning' : 'badge-danger');
        const statusText = util < 60 ? 'Available' :
                          (util < 85 ? 'Filling Up' : 'Almost Full');

        return `
        <div class="card location-card">
            <div class="location-card-img" style="background: linear-gradient(135deg, ${LOC_COLORS[loc.location_type]}22, ${LOC_COLORS[loc.location_type]}08);">
                <span>${icon}</span>
                <span class="badge ${statusBadge} type-badge">${statusText}</span>
            </div>
            <div class="location-card-body">
                <h3>${loc.name}</h3>
                <p class="address">${loc.location_type} • ${loc.zone_count || '--'} zones</p>
                <div class="location-stats">
                    <div class="location-stat-item">
                        <strong>${avail}</strong>
                        Available Spots
                    </div>
                    <div class="location-stat-item">
                        <strong>${loc.total_capacity || '--'}</strong>
                        Total Capacity
                    </div>
                    <div class="location-stat-item">
                        <strong>${util}%</strong>
                        Utilization
                    </div>
                    <div class="location-stat-item">
                        <strong>₹${loc.rate_per_hour || '--'}</strong>
                        Per Hour
                    </div>
                </div>
                <div class="location-card-actions">
                    <button class="btn btn-primary btn-sm" onclick="viewLocationDashboard('${loc.location_id}')">
                        Dashboard
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="bookLocation('${loc.location_id}')">
                        Book Now
                    </button>
                </div>
            </div>
        </div>`;
    }).join('');

    // Update hero stats
    document.getElementById('heroAvailable').textContent = totalAvail;
}

function viewLocationDashboard(locationId) {
    navigate('dashboard');
    // Find first zone of this location and select it
    const loc = state.locations.find(l => l.location_id === locationId);
    if (loc && loc.zones && loc.zones.length > 0) {
        const selector = document.getElementById('zoneSelector');
        selector.value = loc.zones[0].zone_id;
        loadZoneData(loc.zones[0].zone_id);
    }
}

function bookLocation(locationId) {
    if (!state.user) {
        navigate('auth');
        return;
    }
    // Navigate to chat and suggest booking
    navigate('assistant');
    const locName = state.locations.find(l => l.location_id === locationId)?.name || locationId;
    sendChat(`Book a spot at ${locName}`);
}

// ═══════════════════════════════════════
// DASHBOARD PAGE
// ═══════════════════════════════════════
async function loadDashboard() {
    // Populate zone selector
    const selector = document.getElementById('zoneSelector');
    const res = await API.get('/api/locations');
    if (res.status !== 'ok') return;

    let options = '<option value="">— Select Zone —</option>';
    res.data.forEach(loc => {
        const icon = LOC_ICONS[loc.location_type] || '🅿️';
        if (loc.zones) {
            loc.zones.forEach(z => {
                options += `<option value="${z.zone_id}">${icon} ${loc.name} — ${z.zone_name}</option>`;
            });
        }
    });
    selector.innerHTML = options;

    // If a zone was previously selected, reload it
    if (state.selectedZone) {
        selector.value = state.selectedZone;
        loadZoneData(state.selectedZone);
    }
}

async function loadZoneData(zoneId) {
    if (!zoneId) return;
    state.selectedZone = zoneId;

    // Parallel API calls for performance
    const [statusRes, hourlyRes, dailyRes, historyRes, predRes, recRes] = await Promise.all([
        API.get(`/api/dashboard/${zoneId}/status`),
        API.get(`/api/dashboard/${zoneId}/hourly`),
        API.get(`/api/dashboard/${zoneId}/daily`),
        API.get(`/api/dashboard/${zoneId}/history?hours=6`),
        API.get(`/api/dashboard/${zoneId}/predictions`),
        API.get(`/api/dashboard/${zoneId}/recommendation`)
    ]);

    // Update summary cards
    if (statusRes.status === 'ok' && statusRes.data) {
        const s = statusRes.data;
        document.getElementById('dashOccupancy').textContent = s.current_count || 0;
        document.getElementById('dashCapacity').textContent = `/ ${s.max_capacity || '--'}`;
        document.getElementById('dashAvailable').textContent = s.available_slots || 0;
        const util = s.utilization_percent || 0;
        document.getElementById('dashUtilization').textContent = `${util}%`;
        document.getElementById('dashUtilization').style.color =
            util < 60 ? 'var(--success)' : (util < 85 ? 'var(--warning)' : 'var(--danger)');
        document.getElementById('dashStatus').textContent =
            util < 60 ? 'Normal' : (util < 85 ? 'Busy' : 'Critical');
        document.getElementById('dashboardSubtitle').textContent =
            `Viewing: ${s.zone_name || zoneId} • Last updated: ${(s.last_updated || '--').substring(0, 16)}`;
    }

    // Prediction card
    if (predRes.status === 'ok' && predRes.data) {
        document.getElementById('dashPrediction').textContent = predRes.data.predicted_count || '--';
        document.getElementById('dashPredModel').textContent = predRes.data.model_type || 'ML';
    }

    // Recommendation banner
    const banner = document.getElementById('recBanner');
    if (recRes.status === 'ok' && recRes.data) {
        banner.classList.remove('hidden');
        document.getElementById('recMessage').textContent = recRes.data.message || '';
        banner.className = 'recommendation-banner';
        if (recRes.data.category === 'URGENT') banner.classList.add('urgent');
        if (recRes.data.category === 'CRITICAL' || recRes.data.category === 'FULL_REDIRECT')
            banner.classList.add('critical');
    } else {
        banner.classList.add('hidden');
    }

    // Hourly chart
    if (hourlyRes.status === 'ok' && hourlyRes.data) {
        renderHourlyChart(hourlyRes.data);
    }

    // Daily chart
    if (dailyRes.status === 'ok' && dailyRes.data) {
        renderDailyChart(dailyRes.data);
    }

    // Recent events
    if (historyRes.status === 'ok' && historyRes.data) {
        renderEventsList(historyRes.data);
    }

    // AI analysis section
    renderAIAnalysis(predRes.data);
}

// ═══════════════════════════════════════
// CHARTS (Chart.js)
// ═══════════════════════════════════════
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
        tooltip: {
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            borderColor: 'rgba(0, 229, 255, 0.3)',
            borderWidth: 1,
            titleColor: '#f1f5f9',
            bodyColor: '#94a3b8',
            cornerRadius: 8,
            padding: 12,
        }
    },
    scales: {
        x: {
            grid: { color: 'rgba(148,163,184,0.06)' },
            ticks: { color: '#475569', font: { size: 11 } }
        },
        y: {
            grid: { color: 'rgba(148,163,184,0.06)' },
            ticks: { color: '#475569', font: { size: 11 } },
            beginAtZero: true
        }
    }
};

function renderHourlyChart(data) {
    const ctx = document.getElementById('chartHourly');
    if (state.charts.hourly) state.charts.hourly.destroy();

    const labels = data.map(d => `${d.hour}:00`);
    const values = data.map(d => Math.round(d.avg_occupancy));

    state.charts.hourly = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Avg Occupancy',
                data: values,
                borderColor: '#00e5ff',
                backgroundColor: 'rgba(0, 229, 255, 0.1)',
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointBackgroundColor: '#00e5ff',
                borderWidth: 2
            }]
        },
        options: { ...chartDefaults }
    });
}

function renderDailyChart(data) {
    const ctx = document.getElementById('chartDaily');
    if (state.charts.daily) state.charts.daily.destroy();

    const labels = data.map(d => d.date ? d.date.substring(5) : '--');
    const maxes = data.map(d => d.peak_count || 0);
    const avgs = data.map(d => Math.round(d.avg_utilization || 0));

    state.charts.daily = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Peak',
                    data: maxes,
                    backgroundColor: 'rgba(255, 171, 0, 0.6)',
                    borderRadius: 4,
                    barPercentage: 0.6
                },
                {
                    label: 'Average',
                    data: avgs,
                    backgroundColor: 'rgba(0, 229, 255, 0.6)',
                    borderRadius: 4,
                    barPercentage: 0.6
                }
            ]
        },
        options: {
            ...chartDefaults,
            plugins: {
                ...chartDefaults.plugins,
                legend: { display: true, position: 'top',
                    labels: { color: '#94a3b8', boxWidth: 12, padding: 16 } }
            }
        }
    });
}

function renderEventsList(events) {
    const el = document.getElementById('eventsList');
    document.getElementById('eventCount').textContent = `${events.length} events`;

    if (events.length === 0) {
        el.innerHTML = '<p class="text-muted" style="padding: 16px;">No recent events</p>';
        return;
    }

    el.innerHTML = events.slice(0, 50).map(e => {
        const icon = e.event_type === 'ENTRY' ? '🟢' : '🔴';
        const time = (e.event_time || '').substring(11, 19);
        return `<div style="display: flex; align-items: center; gap: 12px;
                    padding: 8px 12px; border-bottom: 1px solid var(--border);
                    font-size: 0.8125rem;">
            <span>${icon}</span>
            <span style="flex: 1; color: var(--text-secondary);">${e.event_type}</span>
            <span style="font-family: monospace; color: var(--text-muted);">${time}</span>
            <span style="font-weight: 600;">${e.occupancy_after || '--'}</span>
        </div>`;
    }).join('');
}

function renderAIAnalysis(prediction) {
    const el = document.getElementById('aiAnalysis');
    if (!prediction) {
        el.innerHTML = '<p class="text-muted">No AI data available for this zone</p>';
        return;
    }

    el.innerHTML = `
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">PREDICTED NEXT HOUR</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: var(--accent);">${prediction.predicted_count || '--'}</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">MODEL TYPE</div>
                <div style="font-size: 1rem; font-weight: 600;">${prediction.model_type || '--'}</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">PEAK HOURS</div>
                <div style="font-size: 1rem; font-weight: 600;">${prediction.peak_hour_start || '--'} - ${prediction.peak_hour_end || '--'}</div>
            </div>
            <div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px;">AVG UTILIZATION</div>
                <div style="font-size: 1rem; font-weight: 600;">${prediction.utilization_avg || '--'}%</div>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════
// CHATBOT
// ═══════════════════════════════════════
async function sendChat(text) {
    const input = document.getElementById('chatInput');
    const query = text || input.value.trim();
    if (!query) return;
    input.value = '';

    // Add user bubble
    const messages = document.getElementById('chatMessages');
    messages.innerHTML += `<div class="chat-bubble user">${escapeHtml(query)}</div>`;
    messages.scrollTop = messages.scrollHeight;

    // Show typing indicator
    const typingId = 'typing-' + Date.now();
    messages.innerHTML += `<div class="chat-bubble bot" id="${typingId}" style="opacity: 0.5;">Thinking...</div>`;
    messages.scrollTop = messages.scrollHeight;

    // Call API
    const res = await API.post('/api/chatbot/query', { query });

    // Remove typing indicator
    const typingEl = document.getElementById(typingId);
    if (typingEl) typingEl.remove();

    // Add bot response
    const response = res.status === 'ok' ? res.data.response : 'Sorry, something went wrong.';
    messages.innerHTML += `<div class="chat-bubble bot">${formatBotResponse(response)}</div>`;
    messages.scrollTop = messages.scrollHeight;
}

function formatBotResponse(text) {
    // Convert markdown-like formatting to HTML
    return escapeHtml(text)
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ═══════════════════════════════════════
// PROFILE PAGE
// ═══════════════════════════════════════
async function loadProfile() {
    if (!state.user) {
        navigate('auth');
        return;
    }

    document.getElementById('profileName').textContent = state.user.name || 'User';
    document.getElementById('profileEmail').textContent = state.user.email || '';
    document.getElementById('profileAvatar').textContent =
        (state.user.name || 'U').charAt(0).toUpperCase();

    // Load bookings
    const bookingsRes = await API.get('/api/bookings/my');
    const bookingsEl = document.getElementById('profileBookings');

    if (bookingsRes.status === 'ok' && bookingsRes.data && bookingsRes.data.length > 0) {
        bookingsEl.innerHTML = bookingsRes.data.map(b => {
            const statusClass = b.status === 'CONFIRMED' ? 'badge-success' :
                               (b.status === 'CANCELLED' ? 'badge-danger' : 'badge-info');
            return `
            <div class="card" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: 600;">${b.zone_name || b.zone_id}</div>
                    <div style="font-size: 0.8125rem; color: var(--text-secondary);">
                        ${(b.booking_time || '').substring(0, 16)}
                    </div>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span class="badge ${statusClass}">${b.status}</span>
                    ${b.status === 'CONFIRMED' ?
                        `<button class="btn btn-sm btn-secondary" onclick="cancelBooking(${b.booking_id})">Cancel</button>` : ''}
                </div>
            </div>`;
        }).join('');
    } else {
        bookingsEl.innerHTML = '<p class="text-muted">No bookings yet. Visit Locations to book your first spot!</p>';
    }

    // Load payments
    const paymentsRes = await API.get('/api/payments/history');
    const paymentsEl = document.getElementById('profilePayments');

    if (paymentsRes.status === 'ok' && paymentsRes.data && paymentsRes.data.length > 0) {
        paymentsEl.innerHTML = paymentsRes.data.map(p => `
            <div class="card" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="font-weight: 600;">₹${p.amount}</div>
                    <div style="font-size: 0.8125rem; color: var(--text-secondary);">
                        ${p.transaction_id} • ${(p.payment_time || '').substring(0, 16)}
                    </div>
                </div>
                <span class="badge ${p.status === 'COMPLETED' ? 'badge-success' : 'badge-warning'}">${p.status}</span>
            </div>
        `).join('');
    } else {
        paymentsEl.innerHTML = '<p class="text-muted">No payment history.</p>';
    }
}

async function cancelBooking(bookingId) {
    const res = await API.post(`/api/bookings/${bookingId}/cancel`);
    if (res.status === 'ok') {
        loadProfile(); // Refresh
    }
}

function switchProfileTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('profileBookings').classList.toggle('hidden', tab !== 'bookings');
    document.getElementById('profilePayments').classList.toggle('hidden', tab !== 'payments');
}

// ═══════════════════════════════════════
// WEBSOCKET
// ═══════════════════════════════════════
function initWebSocket() {
    try {
        state.socket = io();
        state.socket.on('all_statuses', data => {
            // Update hero available count
            if (data.data) {
                const totalAvail = data.data.reduce((sum, s) => sum + (s.available_slots || 0), 0);
                const el = document.getElementById('heroAvailable');
                if (el) el.textContent = totalAvail;
            }
        });
        state.socket.on('zone_update', data => {
            // If we're on dashboard viewing this zone, refresh
            if (state.currentPage === 'dashboard' && state.selectedZone &&
                data.data && data.data.zone_id === state.selectedZone) {
                loadZoneData(state.selectedZone);
            }
        });
    } catch (e) {
        console.log('WebSocket not available, using REST polling');
    }
}

// ═══════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    restoreSession();
    initWebSocket();

    // Load hero available spots
    API.get('/api/statuses').then(res => {
        if (res.status === 'ok' && res.data) {
            const totalAvail = res.data.reduce((sum, s) => sum + (s.available_slots || 0), 0);
            document.getElementById('heroAvailable').textContent = totalAvail;
        }
    }).catch(() => {});
});
