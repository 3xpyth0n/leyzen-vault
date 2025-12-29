import { BaseChart } from "./base-chart.js";

export class UptimeDistributionChart extends BaseChart {
  constructor(element, options = {}) {
    super(element, options);
    this._init();
  }

  _init() {
    if (!this.chart) return;
    this.setOption(
      {
        backgroundColor: "transparent",
        tooltip: {
          trigger: "item",
          position: function (point, params, dom, rect, size) {
            if (params.componentType === "legend") {
              return [point[0], point[1] - size.contentSize[1] - 10];
            }
            // Otherwise, display above the point
            return [point[0], point[1] - size.contentSize[1] - 10];
          },
          confine: true,
          formatter: (params) => {
            if (!params) return "";
            const value = Number(params.value || 0);
            return `${params.name}: ${Math.round(value)}s`;
          },
        },
        legend: {
          bottom: 8,
          itemGap: 16,
          textStyle: { color: "#cbd5f5", fontSize: 11 },
        },
        grid: {
          bottom: 80,
          left: 0,
          right: 0,
          top: 0,
        },
        series: [
          {
            name: "Uptime",
            type: "pie",
            radius: ["40%", "60%"],
            center: ["50%", "40%"],
            avoidLabelOverlap: true,
            itemStyle: {
              borderRadius: 8,
              borderColor: "rgba(255, 255, 255, 0.08)",
              borderWidth: 2,
            },
            label: {
              show: false,
            },
            emphasis: {
              label: {
                show: true,
                formatter: "{b}: {d}%",
                color: "#f8fafc",
              },
            },
            data: [],
          },
        ],
        color: [
          "#34d399",
          "#60a5fa",
          "#f472b6",
          "#f97316",
          "#22d3ee",
          "#facc15",
        ],
      },
      { notMerge: true },
    );
  }

  update(labels, data) {
    if (!this.chart) return;
    const seriesData = labels.map((label, index) => ({
      name: label,
      value: data[index] ?? 0,
    }));
    this.setOption(
      {
        series: [
          {
            name: "Uptime",
            data: seriesData,
          },
        ],
      },
      { notMerge: false },
    );
  }
}
