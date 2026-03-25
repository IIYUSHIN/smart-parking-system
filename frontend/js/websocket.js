/**
 * Smart Parking — WebSocket Client
 * Connects to Flask-SocketIO, receives real-time parking_update events.
 */

// ── GLOBALS ──
let socket = null;
const liveDot = document.getElementById('live-dot');
const connStatus = document.getElementById('connection-status');

function initWebSocket() {
    // Connect to same host as page was loaded from
    const url = window.location.origin;
    socket = io(url, {
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: Infinity
    });

    socket.on('connect', () => {
        if (liveDot) liveDot.classList.add('connected');
        if (connStatus) connStatus.textContent = 'Live';
        console.log('[WS] Connected');
    });

    socket.on('disconnect', () => {
        if (liveDot) liveDot.classList.remove('connected');
        if (connStatus) connStatus.textContent = 'Disconnected';
        console.log('[WS] Disconnected');
    });

    socket.on('connect_error', () => {
        if (connStatus) connStatus.textContent = 'Reconnecting...';
    });

    // ── MAIN EVENT ──
    socket.on('parking_update', (data) => {
        console.log('[WS] parking_update:', data);
        updateDashboard(data);
        addChartDataPoint(data);
    });
}
