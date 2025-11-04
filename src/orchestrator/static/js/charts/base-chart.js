let missingWarningShown = false;

function resolveEcharts() {
  if (typeof window === "undefined") return null;
  return window.echarts || null;
}

export class BaseChart {
  constructor(element, options = {}) {
    if (!element) {
      throw new Error("BaseChart requires a DOM element");
    }

    this.el = element;
    this._options = options;
    this._disposed = false;
    this._resizeObserver = null;

    const echarts = resolveEcharts();
    if (!echarts) {
      if (!missingWarningShown) {
        missingWarningShown = true;
        console.warn(
          "ECharts library was not found on window. Chart rendering is disabled.",
        );
      }
      this.chart = null;
      return;
    }

    const theme = options.theme || "dark";
    this.chart = echarts.init(this.el, theme, {
      renderer: options.renderer || "canvas",
    });

    this._handleResize = () => {
      if (this.chart && !this._disposed) {
        this.chart.resize();
      }
    };

    if (typeof ResizeObserver !== "undefined") {
      this._resizeObserver = new ResizeObserver(() => this._handleResize());
      this._resizeObserver.observe(this.el);
    } else {
      window.addEventListener("resize", this._handleResize);
    }
  }

  setOption(option, opts) {
    if (!this.chart || this._disposed) return;
    this.chart.setOption(option, opts);
  }

  resize() {
    if (this.chart && !this._disposed) {
      this.chart.resize();
    }
  }

  dispose() {
    if (this._disposed) return;
    this._disposed = true;
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    } else if (this._handleResize) {
      window.removeEventListener("resize", this._handleResize);
    }
    if (this.chart) {
      this.chart.dispose();
    }
    this.chart = null;
  }
}

export function initCharts(selector, ChartClass, optionsFactory) {
  const nodes = document.querySelectorAll(selector);
  return Array.from(nodes).map(
    (node) => new ChartClass(node, optionsFactory ? optionsFactory(node) : {}),
  );
}
