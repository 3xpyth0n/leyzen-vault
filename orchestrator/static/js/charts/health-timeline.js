const STATUS_DEFS = [
  { key: "running", color: "#34d399" },
  { key: "starting", color: "#fbbf24" },
  { key: "unhealthy", color: "#f87171" },
  { key: "stopped", color: "#94a3b8" },
];

const STATUS_COLOR_MAP = STATUS_DEFS.reduce((acc, def) => {
  acc[def.key] = def.color;
  return acc;
}, {});

function formatTimestamp(ts) {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "";
  return date
    .toLocaleTimeString([], {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
    .replace(/^(\d{2}):(\d{2}):(\d{2})$/, "$1:$2:$3");
}

export class HealthTimelineChart {
  constructor(element, options = {}) {
    if (!element) {
      throw new Error("HealthTimelineChart requires a DOM element");
    }

    this.el = element;
    this.windowSize = Math.max(4, options.windowSize || 80);
    this.history = [];
    this._disposed = false;
    this._dpr = window.devicePixelRatio || 1;
    this._resizeObserver = null;

    this.canvas = document.createElement("canvas");
    this.canvas.className = "timeline-canvas";
    this.canvas.setAttribute("role", "img");
    this.canvas.setAttribute("aria-hidden", "true");
    this.el.innerHTML = "";
    this.el.appendChild(this.canvas);

    this.ctx = this.canvas.getContext("2d");

    this._handleResize = this._handleResize.bind(this);
    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver = new ResizeObserver(this._handleResize);
      this._resizeObserver.observe(this.el);
    } else {
      window.addEventListener("resize", this._handleResize);
    }

    this._handleResize();
  }

  _handleResize() {
    if (this._disposed) return;

    const rect = this.el.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const dpr = window.devicePixelRatio || 1;
    this._dpr = dpr;
    this.canvas.width = Math.round(width * dpr);
    this.canvas.height = Math.round(height * dpr);
    this.canvas.style.width = `${Math.round(width)}px`;
    this.canvas.style.height = `${Math.round(height)}px`;
    this._render();
  }

  addSample(timestamp, state, health) {
    if (this._disposed) return;

    const label = formatTimestamp(timestamp);
    const normalizedState = (state || "unknown").toString();
    const normalizedHealth = (health || "unknown").toString();
    const status = normalizeStatus(normalizedState, normalizedHealth);

    this.history.push({
      label,
      state: normalizedState,
      health: normalizedHealth,
      status,
    });

    if (this.history.length > this.windowSize) {
      this.history.splice(0, this.history.length - this.windowSize);
    }

    const tooltipLines = [
      `${label || "Timestamp"}`,
      `State: ${normalizedState}`,
      `Health: ${normalizedHealth}`,
    ];
    this.el.setAttribute("title", tooltipLines.join("\n"));

    this._render();
  }

  _render() {
    if (!this.ctx || this._disposed) return;

    const ctx = this.ctx;
    const { width, height } = this.canvas;
    if (width === 0 || height === 0) return;

    ctx.save();
    ctx.clearRect(0, 0, width, height);

    const count = this.history.length;
    if (!count) {
      ctx.restore();
      return;
    }

    const dpr = this._dpr;
    ctx.scale(dpr, dpr);

    const logicalWidth = width / dpr;
    const logicalHeight = height / dpr;
    const maxBars = this.windowSize;
    const columnWidth = logicalWidth / maxBars;
    const startIndex = Math.max(0, count - maxBars);
    const visibleItems = this.history.slice(startIndex);
    let x = logicalWidth - columnWidth * visibleItems.length;

    for (let i = 0; i < visibleItems.length; i += 1) {
      const item = visibleItems[i];
      const color = STATUS_COLOR_MAP[item.status] || "#334155";
      const nextX = x + columnWidth;
      ctx.fillStyle = color;
      ctx.fillRect(Math.floor(x), 0, Math.ceil(nextX - x) + 1, logicalHeight);

      // divider line for readability
      ctx.fillStyle = "rgba(15, 23, 42, 0.45)";
      ctx.fillRect(Math.floor(nextX) - 1, 0, 1, logicalHeight);

      x = nextX;
    }

    const latest = visibleItems[visibleItems.length - 1];
    if (latest) {
      ctx.fillStyle = "rgba(15, 23, 42, 0.2)";
      ctx.fillRect(logicalWidth - columnWidth, 0, columnWidth, logicalHeight);
    }

    ctx.restore();
  }

  dispose() {
    if (this._disposed) return;
    this._disposed = true;
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    } else {
      window.removeEventListener("resize", this._handleResize);
    }
    if (this.canvas && this.canvas.parentNode === this.el) {
      this.el.removeChild(this.canvas);
    }
    this.ctx = null;
  }
}

function normalizeStatus(state, health) {
  const stateLower = state.toLowerCase();
  const healthLower = health.toLowerCase();

  if (stateLower === "running") {
    if (healthLower.includes("healthy")) {
      return "running";
    }
    if (healthLower.includes("starting")) {
      return "starting";
    }
    if (healthLower.includes("unhealthy")) {
      return "unhealthy";
    }
    return "running";
  }

  if (stateLower === "starting" || healthLower.includes("starting")) {
    return "starting";
  }

  if (healthLower.includes("unhealthy")) {
    return "unhealthy";
  }

  return "stopped";
}
