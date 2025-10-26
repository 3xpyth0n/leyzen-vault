/* CONFIG */

let orchestratorRunning = true;
const MAX_FAILS = 5; // after N fails consider API offline

function readNumberMeta(name) {
  const meta = document.querySelector(`meta[name="${name}"]`);
  if (!meta) return null;
  const value = Number(meta.content);
  return Number.isFinite(value) ? value : null;
}

const rotationIntervalMeta = readNumberMeta("dashboard-rotation-interval") || 0;
const ROTATION_INTERVAL_SECONDS = Math.max(0, rotationIntervalMeta);

/* ==== CONTROL BUTTONS ==== */
function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
}

function getCsrfToken() {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
  return getCookie("csrf_token");
}

async function sendControl(action) {
  const statusEl = document.getElementById("control-status");
  if (!statusEl) return;

  if (action === "start" && orchestratorRunning) {
    showStatus("Already running.");
    return;
  }
  if (action === "stop" && !orchestratorRunning) {
    showStatus("Already stopped.");
    return;
  }
  if (action === "kill" && orchestratorRunning) {
    showStatus("Stop orchestrator before kill.");
    return;
  }

  showStatus(`<span class="loader"></span> Processing ${action}...`);

  try {
    const csrfToken = getCsrfToken();
    if (!csrfToken) {
      console.warn("CSRF token not found; request may be rejected.");
    }
    const res = await fetch("/orchestrator/api/control", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      },
      credentials: "same-origin",
      body: JSON.stringify({ action }),
    });

    const json = await res.json();
    showStatus(json.message || "Action sent.");

    if (res.ok) {
      if (typeof json.rotation_active === "boolean") {
        orchestratorRunning = json.rotation_active;
      }
      updateControlButtons();
      if (!orchestratorRunning) {
        stopCountdown("Next in: paused");
      }
    }
  } catch (err) {
    console.error("Control action failed:", err);
    showStatus("Request failed.");
  }
}

function showStatus(message) {
  const el = document.getElementById("control-status");
  if (!el) return;
  el.innerHTML = message;
  el.classList.add("active");
  autoFadeStatus();
}

function autoFadeStatus() {
  const el = document.getElementById("control-status");
  if (!el) return;
  clearTimeout(el._fadeTimer);
  el._fadeTimer = setTimeout(() => {
    el.classList.remove("active");
    setTimeout(() => (el.innerHTML = ""), 500);
  }, 5000);
}

document.getElementById("btn-start").onclick = () => sendControl("start");
document.getElementById("btn-stop").onclick = () => sendControl("stop");
document.getElementById("btn-kill").onclick = () => {
  if (confirm("⚠️ Are you sure you want to stop all Paperless containers?")) {
    sendControl("kill");
  }
};

function updateControlButtons() {
  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");
  const btnKill = document.getElementById("btn-kill");

  if (orchestratorRunning) {
    btnStart.disabled = true;
    btnStart.style.opacity = "0.5";
    btnStop.disabled = false;
    btnStop.style.opacity = "1";
    btnKill.disabled = true;
    btnKill.style.opacity = "0.5";
  } else {
    btnStart.disabled = false;
    btnStart.style.opacity = "1";
    btnStop.disabled = true;
    btnStop.style.opacity = "0.5";
    btnKill.disabled = false;
    btnKill.style.opacity = "1";
  }
}
updateControlButtons();

/* UTIL */
function fmtHMS(s) {
  if (s === null || s === undefined) return "-";
  s = Math.max(0, Math.floor(s));
  const h = Math.floor(s / 3600),
    m = Math.floor((s % 3600) / 60),
    sec = s % 60;
  if (h > 0)
    return `${h}h ${String(m).padStart(2, "0")}m ${String(sec).padStart(2, "0")}s`;
  if (m > 0) return `${m}m ${String(sec).padStart(2, "0")}s`;
  return `${sec}s`;
}
function humanTime(ts) {
  return ts || "N/A";
}

/* SAFE DOM HELPERS */
function safeSetText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
function safeSetHTML(id, html) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = html;
}

/* CHART (single init + update) */
let uptimeChart = null;
function createChart(labels = [], data = []) {
  const ctx = document.getElementById("uptimeChart").getContext("2d");
  uptimeChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data,
          backgroundColor: ["#34d399", "#60a5fa", "#f472b6", "#f97316"],
          borderWidth: 0,
        },
      ],
    },
    options: {
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#cbd5e1" },
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              const value = context.parsed || 0;
              const seconds = Math.round(value);
              return `${context.label}: ${seconds}s`;
            },
          },
        },
      },
      maintainAspectRatio: false,
      cutout: "60%",
      animation: { duration: 250, animateRotate: false, animateScale: false },
      responsive: true,
      hover: { mode: null },
    },
  });
}
function updateChartData(labels, data) {
  if (!uptimeChart) {
    createChart(labels, data);
    return;
  }
  uptimeChart.data.labels = labels;
  uptimeChart.data.datasets[0].data = data;
  uptimeChart.update({ duration: 150, easing: "linear" });
}

/* STATE */
let lastSuccessfulFetch = null;
let failCount = 0;
let lastKnownData = null;
let nextRotationDiff = 0;
let countdownTimer = null;
let lastRotationTs = null;

function startCountdown(seconds) {
  nextRotationDiff = Math.max(0, Math.floor(Number(seconds) || 0));
  const nextEl = document.getElementById("next-rotation");
  if (!nextEl) return;
  if (countdownTimer) clearInterval(countdownTimer);
  nextEl.textContent = `Next in: ${fmtHMS(nextRotationDiff)}`;
  countdownTimer = setInterval(() => {
    nextRotationDiff = Math.max(0, nextRotationDiff - 1);
    nextEl.textContent = `Next in: ${fmtHMS(nextRotationDiff)}`;
    if (nextRotationDiff <= 0) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }, 1000);
}

function stopCountdown(message = "Next in: paused") {
  const nextEl = document.getElementById("next-rotation");
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  nextRotationDiff = 0;
  lastRotationTs = null;
  if (nextEl) {
    nextEl.textContent = message;
  }
}

/* UPDATE DASHBOARD */
function updateDashboardFromData(json) {
  try {
    const wasRunning = orchestratorRunning;
    failCount = 0;
    lastSuccessfulFetch = Date.now();
    lastKnownData = json;

    if (typeof json.rotation_active === "boolean") {
      orchestratorRunning = json.rotation_active;
      updateControlButtons();
    }

    safeSetHTML(
      "api-status",
      `Last API update: <span class="api-online">${new Date(
        lastSuccessfulFetch,
      ).toLocaleTimeString()}</span>`,
    );

    const containers = json.containers || {};
    let total = Object.values(containers).reduce(
      (s, c) => s + (c.uptime || 0),
      0,
    );
    const rowsEl = document.getElementById("rows");
    if (!rowsEl) return;

    const labels = [],
      data = [];

    for (const [name, info] of Object.entries(containers)) {
      const uptime = info.uptime || 0;
      const percent = total > 0 ? Math.round((uptime / total) * 100) : 0;

      let rowEl = rowsEl.querySelector(`[data-row="${CSS.escape(name)}"]`);

      if (!rowEl) {
        const tpl = document.getElementById("row-template");
        if (!tpl) continue;
        const clone = tpl.content.cloneNode(true);
        rowsEl.appendChild(clone);
        rowEl = rowsEl.lastElementChild;
        if (!rowEl) continue;
        rowEl.setAttribute("data-row", name);
      }

      const dot = rowEl.querySelector("[data-dot]");
      const nm = rowEl.querySelector("[data-name]");
      const sub = rowEl.querySelector("[data-sub]");
      const upEl = rowEl.querySelector("[data-uptime]");
      const percentEl = rowEl.querySelector("[data-percent]");

      if (nm) nm.textContent = name;

      const state = (info.state || "").toString();
      const health = (info.health || "").toString();

      let badgeLabel = "";
      let badgeClass = "status-not-found";
      if (state !== "running") {
        badgeLabel = "stopped";
        badgeClass = "status-not-found";
      } else {
        if (health.toLowerCase().includes("healthy")) {
          badgeLabel = "running";
          badgeClass = "status-running";
        } else if (health.toLowerCase().includes("starting")) {
          badgeLabel = "starting";
          badgeClass = "status-starting";
        } else if (health.toLowerCase().includes("unhealthy")) {
          badgeLabel = "unhealthy";
          badgeClass = "status-unhealthy";
        } else {
          badgeLabel = "running";
          badgeClass = "status-running";
        }
      }

      if (sub) {
        sub.innerHTML = `<span class="badge ${badgeClass}">${badgeLabel}</span>&nbsp;<span class="text-xs text-slate-400">state: ${state}${
          health ? " • health: " + health : ""
        }</span>`;
      }

      if (upEl) upEl.textContent = fmtHMS(uptime);
      if (percentEl) percentEl.textContent = percent + "%";

      if (percentEl) {
        if (badgeClass === "status-running") {
          percentEl.style.background = "#052e14";
          percentEl.style.color = "#34d399";
        } else if (badgeClass === "status-starting") {
          percentEl.style.background = "#2b1b05";
          percentEl.style.color = "#f59e0b";
        } else if (badgeClass === "status-unhealthy") {
          percentEl.style.background = "#2b0f0f";
          percentEl.style.color = "#ef4444";
        } else {
          percentEl.style.background = "#1f2937";
          percentEl.style.color = "#94a3b8";
        }
      }

      if (dot) {
        dot.classList.remove("pulse");
        dot.style.backgroundColor = "";
        dot.style.boxShadow = "";

        if (badgeClass === "status-running") {
          dot.style.backgroundColor = "#34d399";
          dot.classList.add("pulse");
          dot.style.boxShadow = "0 0 8px rgba(52,211,153,0.12)";
        } else if (badgeClass === "status-starting") {
          dot.style.backgroundColor = "#f59e0b";
          dot.classList.add("pulse");
          dot.style.boxShadow = "0 0 8px rgba(245,158,11,0.12)";
        } else if (badgeClass === "status-unhealthy") {
          dot.style.backgroundColor = "#ef4444";
        } else {
          dot.style.backgroundColor = "#94a3b8";
        }
      }

      labels.push(name);
      data.push(uptime);
    }

    const existingRows = Array.from(rowsEl.querySelectorAll("[data-row]"));
    const namesSet = new Set(Object.keys(containers));
    for (const r of existingRows) {
      const rn = r.getAttribute("data-row");
      if (!namesSet.has(rn)) r.remove();
    }

    updateChartData(labels, data);

    safeSetText("rotation-count", json.rotation_count ?? 0);
    safeSetText("rot-count-small", json.rotation_count ?? 0);
    safeSetText(
      "total-uptime",
      fmtHMS(
        Object.values(containers).reduce((s, c) => s + (c.uptime || 0), 0),
      ),
    );

    const nextEl = document.getElementById("next-rotation");
    if (nextEl) {
      if (!orchestratorRunning) {
        stopCountdown("Next in: paused");
      } else if (json.last_rotation) {
        const newLastTs = new Date(json.last_rotation.replace(" ", "T"));
        const now = new Date();
        if (
          !lastRotationTs ||
          newLastTs.getTime() !== lastRotationTs.getTime() ||
          !wasRunning
        ) {
          lastRotationTs = newLastTs;
          const nextTs = new Date(
            lastRotationTs.getTime() + ROTATION_INTERVAL_SECONDS * 1000,
          );
          let diff = Math.max(0, Math.floor((nextTs - now) / 1000));
          if (diff <= 0) diff = ROTATION_INTERVAL_SECONDS;
          startCountdown(diff);
        }
      } else {
        stopCountdown("Next in: —");
      }
    }
  } catch (err) {
    failCount++;
    if (failCount >= MAX_FAILS) {
      safeSetHTML(
        "api-status",
        `<span class="api-offline">API offline (last: ${
          lastSuccessfulFetch
            ? new Date(lastSuccessfulFetch).toLocaleTimeString()
            : "never"
        })</span>`,
      );
    } else {
      safeSetText(
        "api-status",
        `Last API attempt failed (${failCount}/${MAX_FAILS})`,
      );
    }
    console.warn("updateDashboard() failed:", err);
  }
}

/* ==== SSE CONNECTION ==== */
let evtSource = null;
let reconnectTimer = null;
let hasReceivedData = false;

function connectSSE() {
  if (evtSource) {
    try {
      evtSource.close();
    } catch {}
    evtSource = null;
  }

  hasReceivedData = false;
  safeSetHTML(
    "api-status",
    `<span class="api-offline">Reconnecting to stream…</span>`,
  );

  try {
    evtSource = new EventSource("/orchestrator/api/stream");
  } catch (e) {
    console.error("SSE init error:", e);
    scheduleReconnect();
    return;
  }

  // Called only when HTTP handshake (200 OK) succeeds
  evtSource.onopen = () => {
    console.log("SSE connection established (HTTP 200)");
    safeSetHTML(
      "api-status",
      `<span class="api-online">Connected to live stream</span>`,
    );
  };

  evtSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      hasReceivedData = true;
      updateDashboardFromData(payload);
    } catch (e) {
      console.error("Invalid SSE data:", e);
    }
  };

  evtSource.onerror = (err) => {
    console.warn("SSE connection lost:", err);

    // Only show reconnecting if connection was previously open
    if (hasReceivedData || evtSource.readyState === EventSource.CLOSED) {
      safeSetHTML(
        "api-status",
        `<span class="api-offline">Reconnecting to stream…</span>`,
      );
    }

    try {
      evtSource.close();
    } catch {}
    evtSource = null;
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      console.log("Attempting to reconnect SSE…");
      connectSSE();
    }, 5000);
  }
}

// start initial connection
connectSSE();
