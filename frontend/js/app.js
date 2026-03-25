/**
 * Smart Parking — Main Application Logic
 * Loads initial data, connects WebSocket, manages dashboard updates.
 */

// ── DOM REFERENCES ──
const DOM = {
    occupancyCount:  document.getElementById('occupancy-count'),
    maxCapacity:     document.getElementById('max-capacity'),
    availableSlots:  document.getElementById('available-slots'),
    ringFill:        document.getElementById('occupancy-ring-fill'),
    statusBadge:     document.getElementById('status-badge'),
    lastEventType:   document.getElementById('last-event-type'),
    lastUpdated:     document.getElementById('last-updated'),
    predictionValue: document.getElementById('prediction-value'),
    peakHours:       document.getElementById('peak-hours'),
    utilizationValue:document.getElementById('utilization-value'),
    utilizationFill: document.getElementById('utilization-bar-fill'),
};

// Ring circumference for SVG (radius=65, C = 2*pi*r)
const RING_CIRCUMFERENCE = 2 * Math.PI * 65; // ~408.41

// ═══════════════════════════════════════════════════════════
// DASHBOARD UPDATE
// ═══════════════════════════════════════════════════════════

function updateDashboard(data) {
    if (!data) return;

    const count = data.current_count || 0;
    const maxCap = data.max_capacity || 4;
    const available = data.available_slots || (maxCap - count);
    const isFull = data.is_full || (count >= maxCap);
    const utilization = data.utilization_percent || 0;

    // Occupancy count
    if (DOM.occupancyCount) DOM.occupancyCount.textContent = count;
    if (DOM.maxCapacity) DOM.maxCapacity.textContent = maxCap;
    if (DOM.availableSlots) DOM.availableSlots.textContent = available;

    // Occupancy ring
    if (DOM.ringFill) {
        const progress = count / maxCap;
        const offset = RING_CIRCUMFERENCE * (1 - progress);
        DOM.ringFill.style.strokeDasharray = RING_CIRCUMFERENCE;
        DOM.ringFill.style.strokeDashoffset = offset;

        // Color based on fill level
        DOM.ringFill.classList.remove('full', 'warning');
        if (isFull) {
            DOM.ringFill.classList.add('full');
        } else if (count >= maxCap - 1) {
            DOM.ringFill.classList.add('warning');
        }
    }

    // Status badge
    if (DOM.statusBadge) {
        if (isFull) {
            DOM.statusBadge.className = 'badge badge-full';
            DOM.statusBadge.innerHTML = '<span>&#x1F6AB;</span> FULL';
        } else {
            DOM.statusBadge.className = 'badge badge-ok';
            DOM.statusBadge.innerHTML = '<span>&#x2705;</span> Available';
        }
    }

    // Last event
    if (DOM.lastEventType && data.last_event) {
        DOM.lastEventType.textContent = data.last_event;
    }

    // Last updated
    if (DOM.lastUpdated && data.last_updated) {
        const dt = new Date(data.last_updated);
        DOM.lastUpdated.textContent = dt.toLocaleTimeString();
    }
}

// ═══════════════════════════════════════════════════════════
// PREDICTION UPDATE
// ═══════════════════════════════════════════════════════════

function updatePrediction(pred) {
    if (!pred) return;

    if (DOM.predictionValue) {
        DOM.predictionValue.textContent = pred.predicted_count + '/4';
    }

    if (DOM.peakHours && pred.peak_hour_start && pred.peak_hour_end) {
        DOM.peakHours.textContent =
            pred.peak_hour_start + ' \u2013 ' + pred.peak_hour_end;
    }

    if (DOM.utilizationValue && pred.utilization_avg !== undefined) {
        DOM.utilizationValue.textContent = Math.round(pred.utilization_avg) + '%';
    }

    if (DOM.utilizationFill && pred.utilization_avg !== undefined) {
        DOM.utilizationFill.style.width = Math.min(pred.utilization_avg, 100) + '%';
    }
}

// ═══════════════════════════════════════════════════════════
// INITIAL DATA LOAD
// ═══════════════════════════════════════════════════════════

async function loadInitialData() {
    try {
        // Load status
        const statusRes = await fetch('/api/status');
        const statusJson = await statusRes.json();
        if (statusJson.data) {
            updateDashboard(statusJson.data);
        }
    } catch (err) {
        console.error('[App] Status load error:', err);
    }

    try {
        // Load prediction
        const predRes = await fetch('/api/predictions');
        const predJson = await predRes.json();
        if (predJson.data) {
            updatePrediction(predJson.data);
        }
    } catch (err) {
        console.error('[App] Prediction load error:', err);
    }
}

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // 1. Load initial data from API
    loadInitialData();

    // 2. Initialize charts
    initCharts();

    // 3. Connect WebSocket
    initWebSocket();

    // 4. Refresh predictions every 5 minutes
    setInterval(async () => {
        try {
            const res = await fetch('/api/predictions');
            const json = await res.json();
            if (json.data) updatePrediction(json.data);
        } catch (e) { /* silent */ }
    }, 5 * 60 * 1000);

    console.log('[App] Smart Parking Dashboard initialized');
});
