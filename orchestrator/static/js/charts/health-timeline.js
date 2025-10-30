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

function hexToRgb(hex) {
  if (typeof hex !== "string") {
    return { r: 51, g: 65, b: 85 };
  }

  const normalized = hex.replace("#", "").trim();
  if (!/^[0-9a-f]{3}([0-9a-f]{3})?$/i.test(normalized)) {
    return { r: 51, g: 65, b: 85 };
  }

  const value =
    normalized.length === 3
      ? normalized
          .split("")
          .map((char) => `${char}${char}`)
          .join("")
      : normalized;

  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return { r, g, b };
}

function withAlpha(hex, alpha) {
  const { r, g, b } = hexToRgb(hex);
  const clampedAlpha = Math.min(1, Math.max(0, Number(alpha) || 0));
  return `rgba(${r}, ${g}, ${b}, ${clampedAlpha})`;
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  const w = Math.max(0, width);
  const h = Math.max(0, height);
  const r = Math.max(0, Math.min(radius, Math.min(w, h) / 2));

  ctx.beginPath();
  if (typeof ctx.roundRect === "function") {
    ctx.roundRect(x, y, w, h, r);
    ctx.closePath();
    return;
  }

  const right = x + w;
  const bottom = y + h;
  ctx.moveTo(x + r, y);
  ctx.lineTo(right - r, y);
  ctx.quadraticCurveTo(right, y, right, y + r);
  ctx.lineTo(right, bottom - r);
  ctx.quadraticCurveTo(right, bottom, right - r, bottom);
  ctx.lineTo(x + r, bottom);
  ctx.quadraticCurveTo(x, bottom, x, bottom - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

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
    const gap = Math.min(4, columnWidth * 0.35);
    const barWidth = Math.max(2, columnWidth - gap);
    const verticalPadding = Math.min(8, logicalHeight * 0.25);
    const barHeight = Math.max(2, logicalHeight - verticalPadding * 2);
    const radius = Math.min(6, barWidth / 2, barHeight / 2);
    const startIndex = Math.max(0, count - maxBars);
    const visibleItems = this.history.slice(startIndex);
    let x = logicalWidth - columnWidth * visibleItems.length;

    const background = ctx.createLinearGradient(0, 0, 0, logicalHeight);
    background.addColorStop(0, "rgba(15, 23, 42, 0.35)");
    background.addColorStop(1, "rgba(15, 23, 42, 0.6)");
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, logicalWidth, logicalHeight);

    visibleItems.forEach((item, index) => {
      const color = STATUS_COLOR_MAP[item.status] || "#334155";
      const rectX = x + gap / 2;
      const rectY = (logicalHeight - barHeight) / 2;

      ctx.save();
      drawRoundedRect(ctx, rectX, rectY, barWidth, barHeight, radius);
      ctx.fillStyle = withAlpha(color, 0.95);
      ctx.fill();

      const gloss = ctx.createLinearGradient(
        rectX,
        rectY,
        rectX,
        rectY + barHeight,
      );
      gloss.addColorStop(0, withAlpha("#ffffff", 0.14));
      gloss.addColorStop(0.5, withAlpha(color, 0.08));
      gloss.addColorStop(1, withAlpha("#000000", 0.22));
      ctx.fillStyle = gloss;
      ctx.fill();
      ctx.restore();

      ctx.save();
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(15, 23, 42, 0.5)";
      drawRoundedRect(ctx, rectX, rectY, barWidth, barHeight, radius);
      ctx.stroke();
      ctx.restore();

      if (index === visibleItems.length - 1) {
        const { r, g, b } = hexToRgb(color);

        ctx.save();
        ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.35)`;
        ctx.shadowBlur = 10;
        ctx.lineWidth = 1.6;
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.85)`;
        drawRoundedRect(ctx, rectX, rectY, barWidth, barHeight, radius);
        ctx.stroke();
        ctx.restore();

        ctx.save();
        const pulse = ctx.createLinearGradient(
          rectX,
          rectY,
          rectX,
          rectY + barHeight,
        );
        pulse.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.25)`);
        pulse.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        ctx.fillStyle = pulse;
        drawRoundedRect(ctx, rectX, rectY, barWidth, barHeight, radius);
        ctx.fill();
        ctx.restore();
      }

      x += columnWidth;
    });

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
