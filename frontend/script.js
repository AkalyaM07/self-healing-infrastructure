// Global State & Chart Instance
let resourceChart = null;
let refreshCountdown = 5;
let countdownInterval = null;
let currentRecoveryLogs = {};

document.addEventListener("DOMContentLoaded", () => {
    initChart();
    fetchDashboardData(true);
    startCountdown();
});

// Initialize Chart.js
function initChart() {
    const ctx = document.getElementById("resourceChart").getContext("2d");

    const cpuGradient = ctx.createLinearGradient(0, 0, 0, 250);
    cpuGradient.addColorStop(0, "rgba(56, 189, 248, 0.4)");
    cpuGradient.addColorStop(1, "rgba(56, 189, 248, 0.0)");

    const memGradient = ctx.createLinearGradient(0, 0, 0, 250);
    memGradient.addColorStop(0, "rgba(129, 140, 248, 0.4)");
    memGradient.addColorStop(1, "rgba(129, 140, 248, 0.0)");

    resourceChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [
                {
                    label: "CPU Usage (%)",
                    data: [],
                    borderColor: "#38bdf8",
                    backgroundColor: cpuGradient,
                    borderWidth: 2,
                    tension: 0.35,
                    fill: true,
                    pointRadius: 2,
                    pointHoverRadius: 5
                },
                {
                    label: "Memory Usage (%)",
                    data: [],
                    borderColor: "#818cf8",
                    backgroundColor: memGradient,
                    borderWidth: 2,
                    tension: 0.35,
                    fill: true,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 400 },
            scales: {
                x: {
                    grid: { color: "rgba(51, 65, 85, 0.3)" },
                    ticks: { color: "#64748b", font: { size: 10 } }
                },
                y: {
                    min: 0,
                    max: 100,
                    grid: { color: "rgba(51, 65, 85, 0.3)" },
                    ticks: {
                        color: "#64748b",
                        callback: val => val + "%"
                    }
                }
            },
            plugins: {
                legend: {
                    labels: { color: "#94a3b8", font: { size: 11 } }
                },
                tooltip: {
                    backgroundColor: "#0f172a",
                    titleColor: "#f8fafc",
                    bodyColor: "#94a3b8",
                    borderColor: "#334155",
                    borderWidth: 1
                }
            }
        }
    });
}

// 5-second Auto Refresh Timer
function startCountdown() {
    if (countdownInterval) clearInterval(countdownInterval);
    refreshCountdown = 5;
    countdownInterval = setInterval(() => {
        refreshCountdown--;
        const timerElem = document.getElementById("refresh-timer");
        if (timerElem) timerElem.innerText = `Auto-refresh: ${refreshCountdown}s`;
        if (refreshCountdown <= 0) {
            refreshCountdown = 5;
            fetchDashboardData(false);
        }
    }, 1000);
}

// Main Data Fetcher
async function fetchDashboardData(showSpinner = false) {
    const spinner = document.getElementById("refresh-spinner");
    if (showSpinner && spinner) spinner.style.borderTopColor = "#38bdf8";

    try {
        const [statusRes, metricsRes, alertsRes, recoveryRes, activityRes] = await Promise.all([
            fetch("/api/server-status").then(r => r.json()),
            fetch("/api/metrics").then(r => r.json()),
            fetch("/api/alerts").then(r => r.json()),
            fetch("/api/recovery-history").then(r => r.json()),
            fetch("/api/activity").then(r => r.json())
        ]);

        updateServerStatus(statusRes);
        updateMetricsChart(metricsRes);
        updateAlerts(alertsRes);
        updateRecoveryHistory(recoveryRes);
        updateActivityTimeline(activityRes);
    } catch (err) {
        console.error("Dashboard poll error:", err);
    }
}

// Update Overview Cards & Service Health
function updateServerStatus(data) {
    const infraPill = document.getElementById("infra-overall-pill");
    const infraText = document.getElementById("infra-status-text");
    const incidentBanner = document.getElementById("live-incident-banner");

    if (data.infrastructure_status === "HEALTHY") {
        infraPill.className = "status-pill status-healthy";
        infraText.innerText = "SYSTEM HEALTHY";
        incidentBanner.classList.add("hidden");
    } else {
        infraPill.className = "status-pill status-degraded";
        infraText.innerText = "INCIDENT IN PROGRESS";
        incidentBanner.classList.remove("hidden");
        document.getElementById("incident-title").innerText = "SERVICE OUTAGE DETECTED";
        document.getElementById("incident-details").innerText = "NGINX health probe failed. Self-healing automation has been triggered via Alertmanager and Ansible.";
    }

    // Overview Cards
    document.getElementById("card-server-status").innerText = data.server_status;
    
    const nginxStatusCard = document.getElementById("card-nginx-status");
    nginxStatusCard.innerText = data.nginx_status;
    nginxStatusCard.className = `metric-highlight ${data.nginx_status === "RUNNING" ? "text-green" : "text-red"}`;
    document.getElementById("card-nginx-source").innerText = data.nginx_health_source || (data.website_available ? "HTTP 200 OK" : "Unreachable");

    document.getElementById("card-cpu-val").innerText = `${data.cpu_percent.toFixed(1)}%`;
    document.getElementById("bar-cpu").style.width = `${Math.min(100, data.cpu_percent)}%`;

    document.getElementById("card-mem-val").innerText = `${data.memory_percent.toFixed(1)}%`;
    document.getElementById("bar-mem").style.width = `${Math.min(100, data.memory_percent)}%`;

    document.getElementById("card-disk-val").innerText = `${data.disk_percent.toFixed(1)}%`;
    document.getElementById("bar-disk").style.width = `${Math.min(100, data.disk_percent)}%`;

    const availCard = document.getElementById("card-web-avail");
    availCard.innerText = data.website_available ? "100% UP" : "0% DOWN";
    availCard.className = `metric-highlight ${data.website_available ? "text-green" : "text-red"}`;

    document.getElementById("card-total-alerts").innerText = data.total_alerts;
    document.getElementById("card-success-rec").innerText = data.successful_recoveries;
    document.getElementById("card-failed-rec").innerText = data.failed_recoveries;

    // Section C: Service Health Details
    const serviceBadge = document.getElementById("service-status-badge");
    const nginxBadge = document.getElementById("health-nginx-badge");
    const blackboxBadge = document.getElementById("health-blackbox-badge");

    if (data.website_available) {
        serviceBadge.className = "badge badge-green";
        serviceBadge.innerText = "HEALTHY";
        nginxBadge.className = "tag tag-success";
        nginxBadge.innerText = "HTTP 200 OK";
        blackboxBadge.className = "tag tag-success";
        blackboxBadge.innerText = "PROBE SUCCESS";
    } else {
        serviceBadge.className = "badge badge-pulse text-red";
        serviceBadge.innerText = "DEGRADED";
        nginxBadge.className = "tag tag-danger";
        nginxBadge.innerText = "DOWN (REFUSED)";
        blackboxBadge.className = "tag tag-danger";
        blackboxBadge.innerText = "PROBE FAILED";
    }

    if (data.last_health_check) {
        const d = new Date(data.last_health_check);
        document.getElementById("health-last-probe").innerText = d.toLocaleTimeString();
    }
    if (data.last_failure_time) {
        const d = new Date(data.last_failure_time);
        document.getElementById("health-last-failure").innerText = d.toLocaleTimeString();
        document.getElementById("health-last-failure").className = "health-val font-mono text-red";
    }
}

// Update Real-Time Chart
function updateMetricsChart(metrics) {
    if (!resourceChart) return;

    if (metrics.history_timestamps && metrics.history_timestamps.length > 0) {
        resourceChart.data.labels = metrics.history_timestamps;
        resourceChart.data.datasets[0].data = metrics.history_cpu;
        resourceChart.data.datasets[1].data = metrics.history_memory;
        resourceChart.update();
    }

    document.getElementById("net-rx").innerText = `${metrics.network_rx_mb || 0} MB`;
    document.getElementById("net-tx").innerText = `${metrics.network_tx_mb || 0} MB`;
}

// Update Alerts Section
function updateAlerts(alertsData) {
    const tbody = document.getElementById("alerts-table-body");
    const badge = document.getElementById("active-alerts-count");

    const liveAlerts = alertsData.live_alerts || [];
    const historyAlerts = alertsData.history_alerts || [];

    // Prioritize firing alerts
    const firingAlerts = liveAlerts.filter(a => a.status === "ACTIVE" || a.status === "FIRING");
    badge.innerText = `${firingAlerts.length} ACTIVE`;
    badge.className = `badge ${firingAlerts.length > 0 ? "badge-pulse text-red" : "badge-blue"}`;

    const displayList = firingAlerts.length > 0 ? firingAlerts : historyAlerts.slice(0, 5);

    if (displayList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No active or recent alerts. Infrastructure is nominal.</td></tr>`;
        return;
    }

    tbody.innerHTML = displayList.map(a => {
        const isCritical = (a.severity || "").toLowerCase() === "critical";
        const isResolved = (a.status || "").toLowerCase() === "resolved";
        const statusClass = isResolved ? "tag tag-success" : isCritical ? "tag tag-danger" : "tag tag-warning";
        const routingText = (a.service === "nginx" || a.alertname === "NGINXDown") 
            ? '<span class="tag tag-cyan">Ansible Webhook</span>' 
            : '<span class="tag tag-blue">Notification Only</span>';
        
        let startFormatted = a.starts_at || a.created_at || "Just now";
        try {
            startFormatted = new Date(startFormatted).toLocaleTimeString();
        } catch(e) {}

        return `
            <tr>
                <td class="font-mono font-bold">${a.alertname}</td>
                <td><span class="${isCritical ? 'tag tag-danger' : 'tag tag-warning'}">${(a.severity || 'info').toUpperCase()}</span></td>
                <td><span class="tag tag-blue">${a.service || 'system'}</span></td>
                <td>
                    <div style="font-weight: 600;">${a.summary || a.alertname}</div>
                    <div style="font-size: 0.75rem; color: #94a3b8;">${a.description || ''}</div>
                </td>
                <td class="font-mono">${startFormatted}</td>
                <td><span class="${statusClass}">${(a.status || 'ACTIVE').toUpperCase()}</span></td>
                <td>${routingText}</td>
            </tr>
        `;
    }).join("");
}

// Update Recovery History Table
function updateRecoveryHistory(historyList) {
    const tbody = document.getElementById("recovery-table-body");
    currentRecoveryLogs = {};

    if (!historyList || historyList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No automated recovery events recorded yet.</td></tr>`;
        return;
    }

    tbody.innerHTML = historyList.map(item => {
        currentRecoveryLogs[item.event_id] = item.execution_output || "No log output recorded.";
        
        let resultTag = "tag tag-blue";
        if (item.recovery_result === "RECOVERED") resultTag = "tag tag-success";
        else if (item.recovery_result === "RECOVERY FAILED") resultTag = "tag tag-danger";

        let detTime = item.detection_time;
        let compTime = item.recovery_completion_time || "--";
        try { detTime = new Date(detTime).toLocaleTimeString(); } catch(e){}
        try { if (compTime !== "--") compTime = new Date(compTime).toLocaleTimeString(); } catch(e){}

        return `
            <tr>
                <td class="font-mono font-bold" style="color: #38bdf8;">${item.event_id}</td>
                <td><span class="tag tag-blue">${item.service_name}</span></td>
                <td>${item.failure_reason}</td>
                <td class="font-mono">${detTime}</td>
                <td><code>${item.recovery_action}</code></td>
                <td><span class="${resultTag}">${item.recovery_result}</span></td>
                <td class="font-mono">${compTime}</td>
                <td>
                    <button class="btn btn-outline" style="padding: 4px 10px; font-size: 0.75rem;" onclick="openLogModal('${item.event_id}')">
                        View Logs
                    </button>
                </td>
            </tr>
        `;
    }).join("");
}

// Update Activity Timeline
function updateActivityTimeline(activityList) {
    const container = document.getElementById("activity-timeline");
    if (!activityList || activityList.length === 0) {
        container.innerHTML = `<div class="text-muted" style="padding-left: 10px;">Waiting for system activity...</div>`;
        return;
    }

    container.innerHTML = activityList.slice(0, 10).map(item => {
        let dotColor = "dot-blue";
        if (item.badge_color === "red") dotColor = "dot-red";
        else if (item.badge_color === "green") dotColor = "dot-green";
        else if (item.badge_color === "orange") dotColor = "dot-orange";

        let timeFormatted = item.timestamp;
        try { timeFormatted = new Date(item.timestamp).toLocaleTimeString(); } catch(e){}

        return `
            <div class="timeline-item">
                <div class="timeline-dot ${dotColor}"></div>
                <div class="timeline-header">
                    <span class="timeline-title">${item.title}</span>
                    <span class="timeline-time">${timeFormatted}</span>
                </div>
                <p class="timeline-desc">${item.description}</p>
            </div>
        `;
    }).join("");
}

// Interactive Simulation Handlers
async function simulateStopNginx() {
    const btn = document.getElementById("btn-stop-nginx");
    btn.disabled = true;
    btn.innerText = "Stopping NGINX...";

    try {
        const res = await fetch("/api/simulate/stop-nginx", { method: "POST" });
        const json = await res.json();
        alert(`Incident Initiated:\n${json.message || "NGINX stopped."}\n\nPrometheus and Blackbox Exporter will detect the failure, trigger the alert, and Ansible will automatically restart NGINX!`);
        fetchDashboardData(true);
    } catch (err) {
        alert("Failed to stop NGINX container. Make sure Docker is running.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-icon">⚡</span> Kill / Stop NGINX`;
    }
}

async function simulateCpuStress() {
    const btn = document.getElementById("btn-cpu-stress");
    btn.disabled = true;
    btn.innerText = "Stressing CPU...";

    try {
        const res = await fetch("/api/simulate/cpu-load?duration=15", { method: "POST" });
        const json = await res.json();
        alert(`CPU Load Triggered:\n${json.message}\nWatch the CPU chart spike!`);
        fetchDashboardData(true);
    } catch (err) {
        alert("Failed to initiate CPU load test.");
    } finally {
        setTimeout(() => {
            btn.disabled = false;
            btn.innerHTML = `<span class="btn-icon">🔥</span> Simulate High CPU (>90%)`;
        }, 3000);
    }
}

async function triggerAnsibleManual() {
    const btn = document.getElementById("btn-run-ansible");
    btn.disabled = true;
    btn.innerText = "Running Playbook...";

    try {
        const res = await fetch("/api/simulate/trigger-recovery", { method: "POST" });
        const json = await res.json();
        openLogModalDirect("MANUAL-EXECUTION", json.output || JSON.stringify(json, null, 2));
        fetchDashboardData(true);
    } catch (err) {
        alert("Failed to trigger playbook execution.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-icon">🔧</span> Trigger Ansible Playbook`;
    }
}

// Log Modal Functions
function openLogModal(eventId) {
    const log = currentRecoveryLogs[eventId] || "No execution log recorded for this event.";
    openLogModalDirect(eventId, log);
}

function openLogModalDirect(title, content) {
    document.getElementById("modal-subtitle").innerText = `Target / Event ID: ${title}`;
    document.getElementById("modal-log-text").innerText = content;
    document.getElementById("log-modal").classList.remove("hidden");
}

function closeLogModal(event) {
    document.getElementById("log-modal").classList.add("hidden");
}
