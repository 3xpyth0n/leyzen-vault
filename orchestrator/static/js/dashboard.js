import { SSEClient } from "./core/sse-client.js";
import {
  CpuTimeSeriesChart,
  MemoryTimeSeriesChart,
  NetIoTimeSeriesChart,
} from "./charts/time-series.js";
import { HealthTimelineChart } from "./charts/health-timeline.js";
import { UptimeDistributionChart } from "./charts/uptime-distribution.js";

/* CONFIG */

let orchestratorRunning = true;
const MAX_FAILS = 5; // after N fails consider API offline

let pendingAnimationFrame = null;
let pendingSnapshot = null;

function flushDashboardQueue() {
  if (!pendingSnapshot) {
    pendingAnimationFrame = null;
    return;
  }
  const snapshot = pendingSnapshot;
  pendingSnapshot = null;
  pendingAnimationFrame = null;
  updateDashboardFromData(snapshot);
}

function scheduleDashboardUpdate(data, options = {}) {
  if (!data) return;
  const { immediate = false } = options;
  pendingSnapshot = data;
  if (immediate) {
    if (pendingAnimationFrame) {
      cancelAnimationFrame(pendingAnimationFrame);
      pendingAnimationFrame = null;
    }
    flushDashboardQueue();
    return;
  }
  if (pendingAnimationFrame) return;
  pendingAnimationFrame = requestAnimationFrame(flushDashboardQueue);
}

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
  if (action === "rotate" && !orchestratorRunning) {
    showStatus("Resume rotation before rotating.");
    return;
  }

  showStatus(`<span class="loader"></span> Processing ${action}...`, {
    allowHtml: true,
  });

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
      if (json.snapshot) {
        scheduleDashboardUpdate(json.snapshot, { immediate: true });
      } else if (action === "rotate" && orchestratorRunning) {
        startCountdown(ROTATION_INTERVAL_SECONDS);
      }
      if (!orchestratorRunning) {
        stopCountdown("Next in: paused");
      }
    }
  } catch (err) {
    console.error("Control action failed:", err);
    showStatus("Request failed.");
  }
}

function showStatus(message, options = {}) {
  const { allowHtml = false } = options;
  const el = document.getElementById("control-status");
  if (!el) return;
  if (allowHtml) {
    el.innerHTML = message;
  } else {
    el.textContent = message;
  }
  el.classList.add("active");
  autoFadeStatus();
}

function autoFadeStatus() {
  const el = document.getElementById("control-status");
  if (!el) return;
  clearTimeout(el._fadeTimer);
  el._fadeTimer = setTimeout(() => {
    el.classList.remove("active");
    setTimeout(() => (el.textContent = ""), 500);
  }, 5000);
}

document.getElementById("btn-start").onclick = () => sendControl("start");
document.getElementById("btn-stop").onclick = () => sendControl("stop");
document.getElementById("btn-rotate").onclick = () => sendControl("rotate");
document.getElementById("btn-kill").onclick = () => {
  if (confirm("⚠️  Are you sure you want to stop all the containers?")) {
    sendControl("kill");
  }
};

function refreshRotationState() {
  const stateEl = document.getElementById("rotation-state");
  if (stateEl) {
    stateEl.textContent = orchestratorRunning ? "Active" : "Paused";
  }
  const dotEl = document.getElementById("rotation-state-dot");
  if (dotEl) {
    dotEl.classList.toggle("state-paused", !orchestratorRunning);
  }
}

function updateControlButtons() {
  const btnStart = document.getElementById("btn-start");
  const btnStop = document.getElementById("btn-stop");
  const btnKill = document.getElementById("btn-kill");
  const btnRotate = document.getElementById("btn-rotate");

  if (orchestratorRunning) {
    btnStart.disabled = true;
    btnStart.style.opacity = "0.5";
    btnStop.disabled = false;
    btnStop.style.opacity = "1";
    if (btnRotate) {
      btnRotate.disabled = false;
      btnRotate.style.opacity = "1";
    }
    btnKill.disabled = true;
    btnKill.style.opacity = "0.5";
  } else {
    btnStart.disabled = false;
    btnStart.style.opacity = "1";
    btnStop.disabled = true;
    btnStop.style.opacity = "0.5";
    if (btnRotate) {
      btnRotate.disabled = true;
      btnRotate.style.opacity = "0.5";
    }
    btnKill.disabled = false;
    btnKill.style.opacity = "1";
  }
  refreshRotationState();
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

function timeAgo(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return "—";
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 0) return "just now";
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) return "0 B";
  const absolute = Math.abs(value);
  const units = ["B", "KB", "MB", "GB", "TB"];
  let idx = 0;
  let scaled = absolute;
  while (scaled >= 1024 && idx < units.length - 1) {
    scaled /= 1024;
    idx += 1;
  }
  const rounded = idx === 0 ? Math.round(scaled) : scaled.toFixed(1);
  const prefix = value < 0 ? "-" : "";
  return `${prefix}${rounded} ${units[idx]}`;
}

function formatPercent(value, options = {}) {
  if (!Number.isFinite(value)) return "—";
  const precision = options.precision ?? 1;
  return `${value.toFixed(precision)}%`;
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

function setMetricValue(key, value) {
  const nodes = document.querySelectorAll(
    `[data-metric-value="${CSS.escape(key)}"]`,
  );
  nodes.forEach((node) => {
    node.textContent = value;
  });
}

/* CHARTS */
let uptimeChart = null;
let cpuChart = null;
let memoryChart = null;
let netChart = null;
const containerTimelineCharts = new Map();
const containerRowState = new Map();

function getPercentStyle(badgeClass) {
  switch (badgeClass) {
    case "status-running":
      return {
        background: "rgba(34,197,94,0.12)",
        color: "#34d399",
        boxShadow: "0 0 10px rgba(34,197,94,0.12)",
      };
    case "status-starting":
      return {
        background: "rgba(245,158,11,0.12)",
        color: "#f59e0b",
        boxShadow: "0 0 10px rgba(245,158,11,0.12)",
      };
    case "status-unhealthy":
      return {
        background: "rgba(248,113,113,0.12)",
        color: "#ef4444",
        boxShadow: "0 0 10px rgba(248,113,113,0.12)",
      };
    default:
      return {
        background: "rgba(148,163,184,0.1)",
        color: "#94a3b8",
        boxShadow: "none",
      };
  }
}

function getDotStyle(badgeClass) {
  switch (badgeClass) {
    case "status-running":
      return {
        backgroundColor: "#34d399",
        boxShadow: "0 0 8px rgba(52,211,153,0.12)",
        pulse: true,
      };
    case "status-starting":
      return {
        backgroundColor: "#f59e0b",
        boxShadow: "0 0 8px rgba(245,158,11,0.12)",
        pulse: true,
      };
    case "status-unhealthy":
      return {
        backgroundColor: "#ef4444",
        boxShadow: "",
        pulse: false,
      };
    default:
      return {
        backgroundColor: "#94a3b8",
        boxShadow: "",
        pulse: false,
      };
  }
}
const detachSparklineHandlers = [];

function initCharts() {
  const uptimeEl = document.getElementById("uptimeChart");
  if (uptimeEl) {
    uptimeChart = new UptimeDistributionChart(uptimeEl);
  }

  const cpuEl = document.querySelector('[data-timeseries="cpu"]');
  if (cpuEl) {
    cpuChart = new CpuTimeSeriesChart(cpuEl, {
      windowSize: 180,
    });
  }

  const memoryEl = document.querySelector('[data-timeseries="memory"]');
  if (memoryEl) {
    memoryChart = new MemoryTimeSeriesChart(memoryEl, {
      windowSize: 180,
    });
  }

  const netEl = document.querySelector('[data-timeseries="net"]');
  if (netEl) {
    netChart = new NetIoTimeSeriesChart(netEl, {
      windowSize: 180,
      yAxisFormatter: (value) => formatBytes(value) + "/s",
    });
  }

  const sparklineSelectors = [
    { selector: '[data-timeseries-sparkline="cpu"]', chart: () => cpuChart },
    {
      selector: '[data-timeseries-sparkline="memory"]',
      chart: () => memoryChart,
    },
    {
      selector: '[data-timeseries-sparkline="net-ingress"]',
      chart: () => netChart,
      options: { seriesIndex: 0 },
    },
    {
      selector: '[data-timeseries-sparkline="net-egress"]',
      chart: () => netChart,
      options: { seriesIndex: 1 },
    },
  ];

  for (const entry of sparklineSelectors) {
    const nodes = document.querySelectorAll(entry.selector);
    nodes.forEach((node) => {
      const chart = entry.chart();
      if (chart && typeof chart.attachSparkline === "function") {
        const detach = chart.attachSparkline(node, entry.options);
        detachSparklineHandlers.push(detach);
      }
    });
  }
}

function updateUptimeChart(labels, data) {
  if (uptimeChart) {
    uptimeChart.update(labels, data);
  }
}

function updateMetricCharts(metrics) {
  if (!metrics) return;
  const timestamp = metrics.timestamp || Date.now();

  if (cpuChart && metrics.cpu) {
    const usage = Number(metrics.cpu.usage);
    if (Number.isFinite(usage)) {
      cpuChart.pushSample(timestamp, { usage });
      setMetricValue("cpu", formatPercent(usage));
    }
  }

  if (memoryChart && metrics.memory) {
    const used = Number(metrics.memory.used);
    const total = Number(metrics.memory.total);
    if (Number.isFinite(used) && Number.isFinite(total) && total > 0) {
      const percent = (used / total) * 100;
      memoryChart.pushSample(timestamp, { percent });
      setMetricValue(
        "memory",
        `${formatBytes(used)} / ${formatBytes(total)} (${formatPercent(percent)})`,
      );
    }
  }

  if (netChart && metrics.net_io) {
    const rx = Number(metrics.net_io.rx_rate ?? metrics.net_io.rx);
    const tx = Number(metrics.net_io.tx_rate ?? metrics.net_io.tx);
    const sample = {};
    if (Number.isFinite(rx)) sample.rx = rx;
    if (Number.isFinite(tx)) sample.tx = tx;
    if (Object.keys(sample).length > 0) {
      netChart.pushSample(timestamp, sample);
      if (Number.isFinite(rx)) {
        setMetricValue("net-ingress", `${formatBytes(rx)}/s ↓`);
      }
      if (Number.isFinite(tx)) {
        setMetricValue("net-egress", `${formatBytes(tx)}/s ↑`);
      }
      if (Number.isFinite(rx) || Number.isFinite(tx)) {
        const rxLabel = Number.isFinite(rx) ? `${formatBytes(rx)}/s ↓` : "—";
        const txLabel = Number.isFinite(tx) ? `${formatBytes(tx)}/s ↑` : "—";
        setMetricValue("net", `${rxLabel} • ${txLabel}`);
      }
    }
  }
}

/* STATE */
let lastSuccessfulFetch = null;
let failCount = 0;
let lastKnownData = null;
let nextRotationDiff = 0;
let countdownTimer = null;
let lastRotationTs = null;

function startCountdown(seconds) {
  const desired = Math.max(0, Math.floor(Number(seconds) || 0));
  if (
    countdownTimer &&
    Math.abs(desired - nextRotationDiff) <= 1 &&
    desired !== 0 &&
    nextRotationDiff !== 0
  ) {
    return;
  }

  nextRotationDiff = desired;
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
    const updateTimestamp = Date.now();
    lastSuccessfulFetch = updateTimestamp;
    lastKnownData = json;

    if (typeof json.rotation_active === "boolean") {
      orchestratorRunning = json.rotation_active;
      updateControlButtons();
    }
    refreshRotationState();

    safeSetHTML(
      "api-status",
      `Last API update: <span class="api-online">${new Date(
        lastSuccessfulFetch,
      ).toLocaleTimeString()}</span>`,
    );

    const containers = json.containers || {};
    updateMetricCharts(json.metrics || null);
    const total = Object.values(containers).reduce(
      (s, c) => s + (c.uptime || 0),
      0,
    );
    const totalCount = Object.keys(containers).length;
    let healthyCount = 0;
    let runningCount = 0;

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
        rowEl._refs = {
          dot: rowEl.querySelector("[data-dot]"),
          name: rowEl.querySelector("[data-name]"),
          sub: rowEl.querySelector("[data-sub]"),
          uptime: rowEl.querySelector("[data-uptime]"),
          percent: rowEl.querySelector("[data-percent]"),
          timeline: rowEl.querySelector("[data-health-timeline]"),
        };
      }

      const refs = rowEl._refs || {
        dot: rowEl.querySelector("[data-dot]"),
        name: rowEl.querySelector("[data-name]"),
        sub: rowEl.querySelector("[data-sub]"),
        uptime: rowEl.querySelector("[data-uptime]"),
        percent: rowEl.querySelector("[data-percent]"),
        timeline: rowEl.querySelector("[data-health-timeline]"),
      };

      rowEl._refs = refs;

      const prevState = containerRowState.get(name) || {};

      if (refs.name && prevState.name !== name) {
        refs.name.textContent = name;
      }

      const state = (info.state || "").toString();
      let health = (info.health || "").toString();

      if (state.toLowerCase() === "exited") {
        health = "stopped";
      }

      let badgeLabel = "";
      let badgeClass = "status-not-found";
      if (state !== "running") {
        badgeLabel = "stopped";
        badgeClass = "status-not-found";
      } else {
        runningCount += 1;
        if (health.toLowerCase().includes("healthy")) {
          badgeLabel = "running";
          badgeClass = "status-running";
          healthyCount += 1;
        } else if (health.toLowerCase().includes("starting")) {
          badgeLabel = "starting";
          badgeClass = "status-starting";
        } else if (health.toLowerCase().includes("unhealthy")) {
          badgeLabel = "unhealthy";
          badgeClass = "status-unhealthy";
        } else {
          badgeLabel = "running";
          badgeClass = "status-running";
          healthyCount += 1;
        }
      }

      const statusHtml = `<span class="badge ${badgeClass}">${badgeLabel}</span>&nbsp;<span class="text-xs text-slate-400">state: ${state}${
        health ? " • health: " + health : ""
      }</span>`;

      if (refs.sub && prevState.statusHtml !== statusHtml) {
        refs.sub.innerHTML = statusHtml;
      }

      const uptimeText = fmtHMS(uptime);
      if (refs.uptime && prevState.uptimeText !== uptimeText) {
        refs.uptime.textContent = uptimeText;
      }

      const percentText = percent + "%";
      if (refs.percent && prevState.percentText !== percentText) {
        refs.percent.textContent = percentText;
      }

      const percentStyle = getPercentStyle(badgeClass);
      if (
        refs.percent &&
        (prevState.percentBg !== percentStyle.background ||
          prevState.percentColor !== percentStyle.color ||
          prevState.percentShadow !== percentStyle.boxShadow)
      ) {
        refs.percent.style.background = percentStyle.background;
        refs.percent.style.color = percentStyle.color;
        refs.percent.style.boxShadow = percentStyle.boxShadow;
      }

      const dotStyle = getDotStyle(badgeClass);
      if (
        refs.dot &&
        (prevState.dotColor !== dotStyle.backgroundColor ||
          prevState.dotShadow !== dotStyle.boxShadow ||
          prevState.dotPulse !== dotStyle.pulse)
      ) {
        refs.dot.style.backgroundColor = dotStyle.backgroundColor;
        refs.dot.style.boxShadow = dotStyle.boxShadow;
        refs.dot.classList.toggle("pulse", dotStyle.pulse);
      }

      let timelineChart = containerTimelineCharts.get(name);
      if (!timelineChart) {
        const timelineEl = refs.timeline;
        if (timelineEl) {
          timelineChart = new HealthTimelineChart(timelineEl, {
            windowSize: 120,
          });
          containerTimelineCharts.set(name, timelineChart);
        }
      }
      const normalizedHealth = health || "unknown";
      const timelineNeedsUpdate =
        prevState.state !== state ||
        prevState.health !== normalizedHealth ||
        !prevState.timelineTs ||
        updateTimestamp - prevState.timelineTs >= 5000;

      if (timelineChart && timelineNeedsUpdate) {
        timelineChart.addSample(updateTimestamp, state, normalizedHealth);
      }

      labels.push(name);
      data.push(uptime);

      containerRowState.set(name, {
        name,
        uptimeText,
        percentText,
        statusHtml,
        percentBg: percentStyle.background,
        percentColor: percentStyle.color,
        percentShadow: percentStyle.boxShadow,
        dotColor: dotStyle.backgroundColor,
        dotShadow: dotStyle.boxShadow,
        dotPulse: dotStyle.pulse,
        state,
        health: normalizedHealth,
        timelineTs: timelineNeedsUpdate
          ? updateTimestamp
          : prevState.timelineTs || updateTimestamp,
      });
    }

    const existingRows = Array.from(rowsEl.querySelectorAll("[data-row]"));
    const namesSet = new Set(Object.keys(containers));
    for (const r of existingRows) {
      const rn = r.getAttribute("data-row");
      if (!namesSet.has(rn)) {
        r.remove();
        const timelineChart = containerTimelineCharts.get(rn);
        if (timelineChart) {
          timelineChart.dispose();
          containerTimelineCharts.delete(rn);
        }
        containerRowState.delete(rn);
      }
    }

    updateUptimeChart(labels, data);

    safeSetText("rotation-count", json.rotation_count ?? 0);
    safeSetText("rot-count-small", json.rotation_count ?? 0);
    safeSetText("total-uptime", fmtHMS(total));
    safeSetText("avg-uptime", fmtHMS(totalCount > 0 ? total / totalCount : 0));
    safeSetText("healthy-count", healthyCount);
    safeSetText("container-count", totalCount);
    safeSetText("degraded-count", Math.max(totalCount - healthyCount, 0));
    safeSetText("running-count", runningCount);
    safeSetText("running-count-chart", runningCount);

    const lastRotationRaw = json.last_rotation;
    let lastRotationDate = null;
    if (lastRotationRaw) {
      const parsed = new Date(lastRotationRaw.replace(" ", "T"));
      if (!Number.isNaN(parsed.getTime())) {
        lastRotationDate = parsed;
      }
    }

    if (lastRotationDate) {
      safeSetText("last-rotation", lastRotationDate.toLocaleString());
      safeSetText("last-rotation-ago", timeAgo(lastRotationDate));
    } else {
      safeSetText("last-rotation", "—");
      safeSetText("last-rotation-ago", "Awaiting data");
    }

    const nextEl = document.getElementById("next-rotation");
    if (nextEl) {
      const eta = Number(json.next_rotation_eta);
      const hasEta = Number.isFinite(eta) && eta >= 0;

      if (!orchestratorRunning) {
        stopCountdown("Next in: paused");
      } else if (hasEta) {
        startCountdown(Math.floor(eta));
      } else if (lastRotationDate) {
        const newLastTs = lastRotationDate;
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
let sseClient = null;
let hasReceivedData = false;

function setupSse() {
  if (sseClient) {
    sseClient.stop();
  }

  hasReceivedData = false;
  safeSetHTML(
    "api-status",
    `<span class="api-offline">Connecting to stream…</span>`,
  );

  sseClient = new SSEClient(
    [
      {
        name: "dashboard",
        url: "/orchestrator/api/stream",
        event: "snapshot",
      },
    ],
    { throttleMs: 500, retryDelay: 5000 },
  );

  sseClient.subscribe("connection-open", () => {
    safeSetHTML(
      "api-status",
      `<span class="api-online">Connected to live stream</span>`,
    );
  });

  sseClient.subscribe("connection-reconnecting", () => {
    const message = hasReceivedData
      ? "Reconnecting to stream…"
      : "Connecting to stream…";
    safeSetHTML("api-status", `<span class="api-offline">${message}</span>`);
  });

  sseClient.subscribe("connection-error", (event) => {
    console.warn(
      "SSE connection error",
      event.detail?.error || "unknown error",
    );
    hasReceivedData = false;
    safeSetHTML(
      "api-status",
      `<span class="api-offline">Connection lost, retrying…</span>`,
    );
  });

  sseClient.subscribe("snapshot", (event) => {
    hasReceivedData = true;
    if (!event?.detail?.data) return;
    scheduleDashboardUpdate(event.detail.data);
  });

  sseClient.start();
}

function initMetricTabs() {
  const tablist = document.querySelector("[data-metric-tabs]");
  if (!tablist) return;

  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  if (!tabs.length) return;

  const mediaQuery = window.matchMedia("(min-width: 1024px)");
  const tabToPanel = new Map();

  for (const tab of tabs) {
    const key = tab.getAttribute("data-metric-tab");
    if (!key) continue;
    const panel = document.querySelector(`[data-metric-panel="${key}"]`);
    if (panel) {
      tabToPanel.set(tab, panel);
    }
  }

  if (!tabToPanel.size) return;

  let activeTab = tabs.find(
    (tab) => tab.getAttribute("aria-selected") === "true",
  );
  if (!activeTab) {
    activeTab = tabs[0];
  }

  function applyPanelState(tab, isActive) {
    const panel = tabToPanel.get(tab);
    if (!panel) return;
    if (mediaQuery.matches) {
      panel.setAttribute("aria-hidden", "false");
      panel.setAttribute("tabindex", "0");
      panel.classList.add("is-active");
    } else {
      panel.setAttribute("aria-hidden", isActive ? "false" : "true");
      panel.setAttribute("tabindex", isActive ? "0" : "-1");
      panel.classList.toggle("is-active", isActive);
    }
  }

  function activateTab(nextTab, { focus = true } = {}) {
    if (!nextTab) return;
    if (activeTab === nextTab && !mediaQuery.matches) {
      if (focus) nextTab.focus();
      return;
    }

    for (const tab of tabs) {
      const isSelected = tab === nextTab;
      tab.setAttribute("aria-selected", isSelected ? "true" : "false");
      tab.classList.toggle("is-active", isSelected);
      applyPanelState(tab, isSelected);
    }

    activeTab = nextTab;
    if (focus) {
      nextTab.focus();
    }
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab, { focus: false }));
  });

  tablist.addEventListener("keydown", (event) => {
    const { key } = event;
    const currentIndex = tabs.indexOf(document.activeElement);
    if (key === "ArrowRight" || key === "ArrowDown") {
      event.preventDefault();
      const next = tabs[(currentIndex + 1) % tabs.length];
      activateTab(next, { focus: false });
      next.focus();
    } else if (key === "ArrowLeft" || key === "ArrowUp") {
      event.preventDefault();
      const next = tabs[(currentIndex - 1 + tabs.length) % tabs.length];
      activateTab(next, { focus: false });
      next.focus();
    } else if (key === "Home") {
      event.preventDefault();
      activateTab(tabs[0], { focus: false });
      tabs[0].focus();
    } else if (key === "End") {
      event.preventDefault();
      const last = tabs[tabs.length - 1];
      activateTab(last, { focus: false });
      last.focus();
    } else if (key === " " || key === "Enter") {
      event.preventDefault();
      const target = document.activeElement;
      if (tabs.includes(target)) {
        activateTab(target, { focus: false });
      }
    }
  });

  function syncPanels(e) {
    if (e.matches) {
      for (const tab of tabs) {
        applyPanelState(tab, tab === activeTab);
      }
    } else {
      activateTab(activeTab, { focus: false });
    }
  }

  if (typeof mediaQuery.addEventListener === "function") {
    mediaQuery.addEventListener("change", syncPanels);
  } else if (typeof mediaQuery.addListener === "function") {
    mediaQuery.addListener(syncPanels);
  }
  syncPanels(mediaQuery);
  activateTab(activeTab, { focus: false });
}

initMetricTabs();
initCharts();
setupSse();

window.addEventListener("beforeunload", () => {
  detachSparklineHandlers.forEach((fn) => {
    try {
      fn();
    } catch (err) {
      console.warn("Failed to detach sparkline", err);
    }
  });
  detachSparklineHandlers.length = 0;
  if (sseClient) {
    sseClient.stop();
  }
  if (pendingAnimationFrame) {
    cancelAnimationFrame(pendingAnimationFrame);
  }
});
