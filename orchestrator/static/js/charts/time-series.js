import { BaseChart } from "./base-chart.js";

function getEcharts() {
  if (typeof window === "undefined") return null;
  return window.echarts || null;
}

const DEFAULT_WINDOW = 120;
let sparklineIdCounter = 0;

function defaultFormatTimestamp(ts) {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
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

export class TimeSeriesChart extends BaseChart {
  constructor(element, options = {}) {
    super(element, options);

    this.windowSize = options.windowSize || DEFAULT_WINDOW;
    this.seriesDefinitions = (options.series || []).map((definition, index) => {
      const id = definition.id || definition.key || `series-${index}`;
      return { ...definition, id };
    });
    this.timestamps = [];
    this.seriesData = this.seriesDefinitions.map(() => []);
    this.sparklineCharts = [];
    this.lastSample = null;
    this.lastTimestamp = null;
    this.yAxisFormatter = options.yAxisFormatter || ((value) => value);
    this.yAxisRange = {
      min: options.yAxisMin ?? null,
      max: options.yAxisMax ?? null,
    };
    this.timestampFormatter =
      options.timestampFormatter || ((value) => defaultFormatTimestamp(value));
    this.isActive = options.initiallyActive ?? true;
    this.needsRender = false;

    this._initChart();
  }

  _initChart() {
    if (!this.chart) return;

    this.setOption(
      {
        grid: {
          left: 36,
          right: 18,
          top: 28,
          bottom: 24,
        },
        tooltip: {
          trigger: "axis",
          formatter: (params) => {
            if (!params || !params.length) return "";
            const lines = [params[0].axisValue];
            for (const item of params) {
              const definition = this.seriesDefinitions[item.seriesIndex] || {};
              const formattedValue = definition.tooltipFormatter
                ? definition.tooltipFormatter(item.data, item, this)
                : item.data;
              lines.push(
                `${item.marker} ${item.seriesName}: ${formattedValue ?? "—"}`,
              );
            }
            return lines.join("<br>");
          },
        },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: [],
          axisLine: { lineStyle: { color: "#334155" } },
          axisLabel: { color: "#cbd5f5", fontSize: 10 },
          axisTick: { show: false },
        },
        yAxis: {
          type: "value",
          scale: true,
          min: this.yAxisRange.min,
          max: this.yAxisRange.max,
          splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.1)" } },
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: "#cbd5f5",
            fontSize: 10,
            formatter: (value) => this.yAxisFormatter(value),
          },
        },
        animationDurationUpdate: 260,
        series: this.seriesDefinitions.map((definition) => ({
          id: definition.id,
          name: definition.name,
          type: "line",
          smooth: true,
          showSymbol: false,
          animationDuration: 260,
          lineStyle: {
            color: definition.color,
            width: 2,
          },
          areaStyle:
            definition.fill === false
              ? undefined
              : {
                  color: definition.areaColor || definition.color,
                  opacity: definition.areaOpacity ?? 0.15,
                },
          data: [],
        })),
      },
      { notMerge: true },
    );
  }

  attachSparkline(element, options = {}) {
    const echarts = getEcharts();
    if (!echarts || !element) return () => {};

    const seriesIndex = options.seriesIndex ?? 0;
    const chart = echarts.init(element, null, {
      renderer: "canvas",
    });

    const seriesId =
      options.seriesId || `spark-${seriesIndex}-${sparklineIdCounter++}`;

    chart.setOption(
      {
        grid: { left: 4, right: 4, top: 4, bottom: 4 },
        xAxis: {
          type: "category",
          data: [],
          boundaryGap: false,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
        },
        yAxis: {
          type: "value",
          scale: true,
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: { show: false },
          splitLine: { show: false },
        },
        series: [
          {
            id: seriesId,
            type: "line",
            data: [],
            smooth: true,
            showSymbol: false,
            animationDuration: 180,
            lineStyle: {
              width: 1.5,
              color:
                options.color ||
                this.seriesDefinitions[seriesIndex]?.color ||
                "#38bdf8",
            },
            areaStyle:
              options.fill === false
                ? undefined
                : {
                    color:
                      options.areaColor ||
                      this.seriesDefinitions[seriesIndex]?.color ||
                      "#38bdf8",
                    opacity: options.areaOpacity ?? 0.2,
                  },
          },
        ],
      },
      { notMerge: true },
    );

    const config = { chart, element, seriesIndex, seriesId };
    this.sparklineCharts.push(config);
    this._updateSparklines();

    return () => {
      chart.dispose();
      this.sparklineCharts = this.sparklineCharts.filter(
        (item) => item !== config,
      );
    };
  }

  pushSample(timestamp, sample = {}) {
    const tsValue =
      typeof timestamp === "number" ? timestamp : Date.parse(timestamp);
    const resolvedTs = Number.isFinite(tsValue) ? tsValue : Date.now();
    const label = this.timestampFormatter(resolvedTs);

    this.timestamps.push(label);
    if (this.timestamps.length > this.windowSize) {
      this.timestamps.shift();
    }

    this.seriesDefinitions.forEach((definition, index) => {
      let value = sample[definition.key];
      if (
        typeof value === "number" &&
        Number.isFinite(value) &&
        typeof definition.formatValue === "function"
      ) {
        try {
          value = definition.formatValue(value, sample);
        } catch (err) {
          console.warn("Failed to format chart value", err);
        }
      }
      const arr = this.seriesData[index];
      if (typeof value === "number" && Number.isFinite(value)) {
        arr.push(value);
      } else {
        arr.push(null);
      }
      if (arr.length > this.windowSize) {
        arr.shift();
      }
    });

    this.lastSample = sample;
    this.lastTimestamp = resolvedTs;
    this.needsRender = true;
    this._render();
  }

  _render() {
    if (!this.chart) return;

    const xData = this.timestamps.slice(-this.windowSize);
    const updateSeries = this.seriesDefinitions.map((definition, index) => ({
      id: definition.id,
      data: this.seriesData[index].slice(-this.windowSize),
      animationDuration: 0,
      animationDurationUpdate: 160,
    }));

    if (!this.isActive) {
      this.needsRender = true;
      this._updateSparklines(xData);
      return;
    }

    this.needsRender = false;
    this.setOption(
      {
        animationDuration: 0,
        animationDurationUpdate: 220,
        xAxis: { data: xData },
        series: updateSeries,
      },
      { notMerge: false, lazyUpdate: true },
    );

    this._updateSparklines(xData);
  }

  _updateSparklines(xAxisValues) {
    if (!this.sparklineCharts.length) return;
    const xData = xAxisValues || this.timestamps.slice(-this.windowSize);
    this.sparklineCharts.forEach((config) => {
      const data =
        this.seriesData[config.seriesIndex]?.slice(-this.windowSize) || [];
      config.chart.setOption(
        {
          animationDuration: 0,
          animationDurationUpdate: 160,
          xAxis: { data: xData },
          series: [
            {
              id: config.seriesId,
              data,
              animationDuration: 0,
              animationDurationUpdate: 160,
            },
          ],
        },
        { notMerge: false, lazyUpdate: true },
      );
    });
  }

  getLatestValue(key) {
    if (!this.lastSample) return null;
    const value = this.lastSample[key];
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  setActive(isActive) {
    const nextState = Boolean(isActive);
    if (this.isActive === nextState) {
      if (nextState && this.needsRender) {
        this._render();
      }
      return;
    }

    this.isActive = nextState;
    if (this.isActive) {
      this.resize();
      this._render();
    }
  }
}

export class CpuTimeSeriesChart extends TimeSeriesChart {
  constructor(element, options = {}) {
    super(
      element,
      Object.assign(
        {
          series: [
            {
              key: "usage",
              name: "CPU %",
              color: "#34d399",
              areaOpacity: 0.25,
              formatValue: (value) => Number(value.toFixed(2)),
              tooltipFormatter: (value) =>
                Number.isFinite(value) ? `${value.toFixed(1)}%` : "—",
            },
          ],
          yAxisMin: 0,
          yAxisMax: 100,
          yAxisFormatter: (value) => `${Math.round(value)}%`,
        },
        options,
      ),
    );
  }
}

export class MemoryTimeSeriesChart extends TimeSeriesChart {
  constructor(element, options = {}) {
    super(
      element,
      Object.assign(
        {
          series: [
            {
              key: "percent",
              name: "Memory %",
              color: "#60a5fa",
              areaOpacity: 0.25,
              formatValue: (value) => Number(value.toFixed(2)),
              tooltipFormatter: (value) =>
                Number.isFinite(value) ? `${value.toFixed(1)}%` : "—",
            },
          ],
          yAxisMin: 0,
          yAxisMax: 100,
          yAxisFormatter: (value) => `${Math.round(value)}%`,
        },
        options,
      ),
    );
  }
}

export class NetIoTimeSeriesChart extends TimeSeriesChart {
  constructor(element, options = {}) {
    super(
      element,
      Object.assign(
        {
          series: [
            {
              key: "rx",
              name: "Ingress",
              color: "#f97316",
              areaOpacity: 0.2,
              formatValue: (value) => Number(value.toFixed(2)),
              tooltipFormatter: (value) =>
                Number.isFinite(value) ? `${formatBytes(value)}/s` : "—",
            },
            {
              key: "tx",
              name: "Egress",
              color: "#a855f7",
              areaOpacity: 0.2,
              formatValue: (value) => Number(value.toFixed(2)),
              tooltipFormatter: (value) =>
                Number.isFinite(value) ? `${formatBytes(value)}/s` : "—",
            },
          ],
          yAxisFormatter: (value) => value,
        },
        options,
      ),
    );
  }
}
