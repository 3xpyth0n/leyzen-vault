import { BaseChart } from "./base-chart.js";

const STATUS_DEFS = [
  { key: "running", color: "#34d399" },
  { key: "starting", color: "#fbbf24" },
  { key: "unhealthy", color: "#f87171" },
  { key: "stopped", color: "#94a3b8" },
];

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

export class HealthTimelineChart extends BaseChart {
  constructor(element, options = {}) {
    super(element, options);
    this.windowSize = options.windowSize || 80;
    this.history = [];
    this._initChart();
  }

  _initChart() {
    if (!this.chart) return;

    this.setOption(
      {
        grid: { left: 2, right: 6, top: 6, bottom: 2, containLabel: false },
        tooltip: {
          trigger: "axis",
          formatter: (params) => {
            if (!params || !params.length) return "";
            const entry = this.history[params[0].dataIndex];
            if (!entry) return "";
            const lines = [
              `<strong>${entry.label}</strong>`,
              `State: ${entry.state}`,
              `Health: ${entry.health}`,
            ];
            return lines.join("<br>");
          },
        },
        xAxis: {
          type: "category",
          data: [],
          boundaryGap: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
        },
        yAxis: {
          type: "value",
          min: 0,
          max: STATUS_DEFS.length,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        series: [
          ...STATUS_DEFS.map((status) => ({
            name: status.key,
            type: "bar",
            stack: "status",
            barWidth: "90%",
            emphasis: { focus: "series" },
            itemStyle: { color: status.color },
            data: [],
            animationDuration: 200,
          })),
          {
            name: "markers",
            type: "line",
            data: [],
            smooth: true,
            showSymbol: true,
            symbol: "circle",
            symbolSize: (value, params) => {
              const item = this.history[params.dataIndex];
              return item && item.status === "stopped" ? 8 : 4;
            },
            lineStyle: { color: "rgba(148, 163, 184, 0.45)", width: 1.2 },
            itemStyle: {
              color: (params) => {
                const item = this.history[params.dataIndex];
                if (!item) return "#e2e8f0";
                switch (item.status) {
                  case "running":
                    return "#34d399";
                  case "starting":
                    return "#fbbf24";
                  case "unhealthy":
                    return "#f87171";
                  default:
                    return "#94a3b8";
                }
              },
            },
            animationDuration: 200,
          },
        ],
      },
      { notMerge: true },
    );
  }

  addSample(timestamp, state, health) {
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
      this.history.shift();
    }

    this._render();
  }

  _render() {
    if (!this.chart) return;

    const categories = this.history.map((item) => item.label);
    const stackedSeries = STATUS_DEFS.map((definition) =>
      this.history.map((item) => (item.status === definition.key ? 1 : 0)),
    );

    const markers = this.history.map(
      (item) => STATUS_DEFS.findIndex((def) => def.key === item.status) + 0.5,
    );

    this.setOption(
      {
        xAxis: { data: categories },
        series: [
          ...STATUS_DEFS.map((definition, index) => ({
            name: definition.key,
            data: stackedSeries[index],
          })),
          {
            name: "markers",
            data: markers,
          },
        ],
      },
      { notMerge: false },
    );
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
