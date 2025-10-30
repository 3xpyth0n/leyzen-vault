const STATUS_DEFS = [
  { key: "running", color: "#34d399" },
  { key: "starting", color: "#fbbf24" },
  { key: "unhealthy", color: "#f87171" },
  { key: "stopped", color: "#94a3b8" },
];

const STATUS_ICONS = {
  running: "▶",
  starting: "⏳",
  unhealthy: "⚠",
  stopped: "■",
};

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

function mixColor(hex, ratio, targetHex = "#ffffff") {
  const base = hexToRgb(hex);
  const target = hexToRgb(targetHex);
  const clamp = (value) => Math.max(0, Math.min(255, Math.round(value)));
  const mix = (baseValue, targetValue) =>
    clamp(baseValue * (1 - ratio) + targetValue * ratio);
  const toHex = (value) => value.toString(16).padStart(2, "0");
  const r = mix(base.r, target.r);
  const g = mix(base.g, target.g);
  const b = mix(base.b, target.b);
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

const STATUS_TEXTURE_CACHE = new Map();

function getStatusTexture(ctx, status) {
  const dpr = window.devicePixelRatio || 1;
  const key = `${status}-${dpr}`;
  if (STATUS_TEXTURE_CACHE.has(key)) {
    return STATUS_TEXTURE_CACHE.get(key);
  }

  const baseColor = STATUS_COLOR_MAP[status] || "#334155";
  let pattern = null;

  if (status === "starting") {
    pattern = createDiagonalPattern(ctx, baseColor, dpr);
  } else if (status === "stopped") {
    pattern = createDotPattern(ctx, baseColor, dpr);
  }

  STATUS_TEXTURE_CACHE.set(key, pattern);
  return pattern;
}

function createDiagonalPattern(ctx, baseColor, dpr) {
  const size = Math.max(12, Math.round(14 * dpr));
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const patternCtx = canvas.getContext("2d");
  if (!patternCtx) return null;

  patternCtx.fillStyle = withAlpha(baseColor, 0.18);
  patternCtx.fillRect(0, 0, size, size);

  patternCtx.strokeStyle = withAlpha("#ffffff", 0.25);
  patternCtx.lineWidth = Math.max(1, Math.round(1.25 * dpr));
  patternCtx.beginPath();
  patternCtx.moveTo(0, size);
  patternCtx.lineTo(size, 0);
  patternCtx.stroke();

  patternCtx.strokeStyle = withAlpha(baseColor, 0.45);
  patternCtx.beginPath();
  patternCtx.moveTo(-size * 0.25, size);
  patternCtx.lineTo(size, -size * 0.25);
  patternCtx.stroke();

  return ctx.createPattern(canvas, "repeat");
}

function createDotPattern(ctx, baseColor, dpr) {
  const size = Math.max(10, Math.round(12 * dpr));
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const patternCtx = canvas.getContext("2d");
  if (!patternCtx) return null;

  patternCtx.fillStyle = withAlpha(baseColor, 0.14);
  patternCtx.fillRect(0, 0, size, size);

  const radius = Math.max(1.5, 2.5 * dpr);
  patternCtx.fillStyle = withAlpha(baseColor, 0.55);
  patternCtx.beginPath();
  patternCtx.arc(size * 0.3, size * 0.3, radius, 0, Math.PI * 2);
  patternCtx.fill();

  patternCtx.fillStyle = withAlpha("#ffffff", 0.25);
  patternCtx.beginPath();
  patternCtx.arc(size * 0.75, size * 0.75, radius * 0.65, 0, Math.PI * 2);
  patternCtx.fill();

  return ctx.createPattern(canvas, "repeat");
}

function createStatusFill(ctx, status, x, y, width, height) {
  const color = STATUS_COLOR_MAP[status] || "#334155";
  const light = mixColor(color, 0.3, "#ffffff");
  const deep = mixColor(color, 0.45, "#0f172a");
  let gradient;

  switch (status) {
    case "running": {
      gradient = ctx.createLinearGradient(x, y, x + width, y);
      gradient.addColorStop(0, withAlpha(light, 0.85));
      gradient.addColorStop(0.5, withAlpha(color, 0.95));
      gradient.addColorStop(1, withAlpha(deep, 0.85));
      break;
    }
    case "unhealthy": {
      gradient = ctx.createLinearGradient(x, y, x, y + height);
      gradient.addColorStop(0, withAlpha(light, 0.9));
      gradient.addColorStop(0.6, withAlpha(color, 0.95));
      gradient.addColorStop(1, withAlpha(deep, 0.85));
      break;
    }
    case "starting": {
      gradient = ctx.createLinearGradient(x, y, x, y + height);
      gradient.addColorStop(0, withAlpha(light, 0.9));
      gradient.addColorStop(0.35, withAlpha(color, 0.85));
      gradient.addColorStop(1, withAlpha(deep, 0.8));
      break;
    }
    case "stopped":
    default: {
      gradient = ctx.createLinearGradient(x, y, x + width, y);
      gradient.addColorStop(0, withAlpha(light, 0.75));
      gradient.addColorStop(0.5, withAlpha(color, 0.9));
      gradient.addColorStop(1, withAlpha(deep, 0.9));
      break;
    }
  }

  return gradient;
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
    const verticalPadding = Math.min(10, logicalHeight * 0.25);
    const ribbonHeight = Math.max(2, logicalHeight - verticalPadding * 2);
    const radius = Math.min(12, ribbonHeight / 2);
    const startIndex = Math.max(0, count - maxBars);
    const visibleItems = this.history.slice(startIndex);
    const baseX = logicalWidth - columnWidth * visibleItems.length;

    const segments = [];
    let currentSegment = null;

    visibleItems.forEach((item, index) => {
      const startX = baseX + columnWidth * index;
      const endX = startX + columnWidth;
      if (!currentSegment || currentSegment.status !== item.status) {
        if (currentSegment) {
          segments.push(currentSegment);
        }
        currentSegment = {
          status: item.status,
          start: startX,
          end: endX,
          length: 1,
          last: item,
        };
      } else {
        currentSegment.end = endX;
        currentSegment.length += 1;
        currentSegment.last = item;
      }
    });

    if (currentSegment) {
      segments.push(currentSegment);
    }

    const background = ctx.createLinearGradient(0, 0, 0, logicalHeight);
    background.addColorStop(0, "rgba(15, 23, 42, 0.35)");
    background.addColorStop(1, "rgba(15, 23, 42, 0.6)");
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, logicalWidth, logicalHeight);

    ctx.save();
    ctx.strokeStyle = "rgba(148, 163, 184, 0.08)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 1; i < visibleItems.length; i += 1) {
      const lineX = baseX + columnWidth * i;
      ctx.moveTo(lineX, verticalPadding * 0.5);
      ctx.lineTo(lineX, logicalHeight - verticalPadding * 0.5);
    }
    ctx.stroke();
    ctx.restore();

    const ribbonY = (logicalHeight - ribbonHeight) / 2;
    const ribbonEndX = baseX + columnWidth * visibleItems.length;

    ctx.save();
    ctx.strokeStyle = "rgba(15, 23, 42, 0.45)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(baseX, ribbonY);
    ctx.lineTo(ribbonEndX, ribbonY);
    ctx.moveTo(baseX, ribbonY + ribbonHeight);
    ctx.lineTo(ribbonEndX, ribbonY + ribbonHeight);
    ctx.stroke();
    ctx.restore();

    segments.forEach((segment, index) => {
      const rectX = segment.start;
      const rectWidth = Math.max(1, segment.end - segment.start);
      const color = STATUS_COLOR_MAP[segment.status] || "#334155";

      ctx.save();
      drawRoundedRect(ctx, rectX, ribbonY, rectWidth, ribbonHeight, radius);
      ctx.fillStyle = createStatusFill(
        ctx,
        segment.status,
        rectX,
        ribbonY,
        rectWidth,
        ribbonHeight,
      );
      ctx.fill();

      const texture = getStatusTexture(ctx, segment.status);
      if (texture) {
        ctx.globalAlpha = segment.status === "starting" ? 0.45 : 0.35;
        ctx.fillStyle = texture;
        drawRoundedRect(ctx, rectX, ribbonY, rectWidth, ribbonHeight, radius);
        ctx.fill();
        ctx.globalAlpha = 1;
      }

      const gloss = ctx.createLinearGradient(
        rectX,
        ribbonY,
        rectX,
        ribbonY + ribbonHeight,
      );
      gloss.addColorStop(0, withAlpha("#ffffff", 0.12));
      gloss.addColorStop(0.5, withAlpha(color, 0.08));
      gloss.addColorStop(1, withAlpha("#000000", 0.16));
      ctx.fillStyle = gloss;
      drawRoundedRect(ctx, rectX, ribbonY, rectWidth, ribbonHeight, radius);
      ctx.fill();
      ctx.restore();

      ctx.save();
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(15, 23, 42, 0.55)";
      drawRoundedRect(ctx, rectX, ribbonY, rectWidth, ribbonHeight, radius);
      ctx.stroke();
      ctx.restore();

      if (index > 0) {
        const boundaryX = rectX;
        ctx.save();
        ctx.strokeStyle = "rgba(15, 23, 42, 0.75)";
        ctx.lineWidth = 1.15;
        ctx.beginPath();
        ctx.moveTo(boundaryX, ribbonY + 2);
        ctx.lineTo(boundaryX, ribbonY + ribbonHeight - 2);
        ctx.stroke();
        ctx.restore();
      }

      const icon = STATUS_ICONS[segment.status];
      const markerRadius = Math.min(ribbonHeight * 0.45, 14);
      const hasSpace = rectWidth >= markerRadius * 2 + 8;
      if (icon && hasSpace) {
        const idealX = rectX + rectWidth / 2;
        const finalX = Math.min(
          rectX + rectWidth - markerRadius - 4,
          Math.max(rectX + markerRadius + 4, idealX),
        );
        const finalY = ribbonY + ribbonHeight / 2;

        ctx.save();
        ctx.fillStyle = withAlpha("#0f172a", 0.55);
        ctx.beginPath();
        ctx.arc(finalX, finalY, markerRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.lineWidth = 1;
        ctx.strokeStyle = withAlpha("#ffffff", 0.2);
        ctx.stroke();

        ctx.font = `600 ${Math.min(16, markerRadius * 1.3)}px "Inter", "Segoe UI", sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = withAlpha("#e2e8f0", 0.95);
        ctx.fillText(icon, finalX, finalY + (icon === "⏳" ? 1 : 0));
        ctx.restore();
      } else if (icon) {
        const centerX = rectX + rectWidth / 2;
        const baseY = ribbonY + ribbonHeight / 2;
        ctx.save();
        ctx.strokeStyle = withAlpha(color, 0.9);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(centerX, baseY - markerRadius * 0.6);
        ctx.lineTo(centerX, baseY + markerRadius * 0.6);
        ctx.stroke();
        ctx.fillStyle = withAlpha("#0f172a", 0.65);
        ctx.font = `600 ${Math.min(12, markerRadius * 1.1)}px "Inter", "Segoe UI", sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "bottom";
        ctx.fillText(icon, centerX, baseY - markerRadius * 0.7);
        ctx.restore();
      }
    });

    const lastSegment = segments[segments.length - 1];
    if (lastSegment) {
      const lastColor = STATUS_COLOR_MAP[lastSegment.status] || "#22d3ee";
      const { r, g, b } = hexToRgb(lastColor);
      const rectX = lastSegment.start;
      const rectWidth = Math.max(1, lastSegment.end - lastSegment.start);

      ctx.save();
      ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.35)`;
      ctx.shadowBlur = 12;
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.85)`;
      drawRoundedRect(ctx, rectX, ribbonY, rectWidth, ribbonHeight, radius);
      ctx.stroke();
      ctx.restore();

      ctx.save();
      const pulse = ctx.createLinearGradient(
        rectX,
        ribbonY,
        rectX,
        ribbonY + ribbonHeight,
      );
      pulse.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.25)`);
      pulse.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
      ctx.fillStyle = pulse;
      drawRoundedRect(ctx, rectX, ribbonY, rectWidth, ribbonHeight, radius);
      ctx.fill();
      ctx.restore();
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
