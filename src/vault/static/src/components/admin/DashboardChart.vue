<template>
  <div class="dashboard-chart">
    <div class="chart-header">
      <h3>{{ title }}</h3>
      <div class="chart-legend" v-if="legend">
        <span v-for="(item, index) in legend" :key="index" class="legend-item">
          <span
            class="legend-color"
            :style="{ backgroundColor: item.color }"
          ></span>
          <span class="legend-label">{{ item.label }}</span>
        </span>
      </div>
    </div>
    <div class="chart-container">
      <canvas ref="chartCanvas" :width="width" :height="height"></canvas>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch, nextTick } from "vue";

export default {
  name: "DashboardChart",
  props: {
    title: {
      type: String,
      required: true,
    },
    data: {
      type: Array,
      required: true,
    },
    dataKey: {
      type: String,
      default: "count",
    },
    width: {
      type: Number,
      default: 800,
    },
    height: {
      type: Number,
      default: 200,
    },
    color: {
      type: String,
      default: "#004225",
    },
    legend: {
      type: Array,
      default: null,
    },
  },
  setup(props) {
    const chartCanvas = ref(null);

    const drawChart = () => {
      if (!chartCanvas.value || !props.data || props.data.length === 0) {
        return;
      }

      const canvas = chartCanvas.value;
      const ctx = canvas.getContext("2d");
      const padding = { top: 20, right: 20, bottom: 30, left: 50 };
      const chartWidth = props.width - padding.left - padding.right;
      const chartHeight = props.height - padding.top - padding.bottom;

      // Clear canvas
      ctx.clearRect(0, 0, props.width, props.height);

      // Find min/max values
      const values = props.data.map((d) => d[props.dataKey] || 0);
      const maxValue = Math.max(...values, 1);
      const minValue = Math.min(...values, 0);

      // Draw grid
      ctx.strokeStyle = "#004225";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 5; i++) {
        const y = padding.top + (chartHeight / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(padding.left + chartWidth, y);
        ctx.stroke();
      }

      // Draw axes
      ctx.strokeStyle = "#004225";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padding.left, padding.top);
      ctx.lineTo(padding.left, padding.top + chartHeight);
      ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight);
      ctx.stroke();

      // Draw line
      ctx.strokeStyle = props.color;
      ctx.lineWidth = 2;
      ctx.beginPath();

      props.data.forEach((point, index) => {
        const x =
          padding.left + (chartWidth / (props.data.length - 1 || 1)) * index;
        const value = point[props.dataKey] || 0;
        const y =
          padding.top +
          chartHeight -
          ((value - minValue) / (maxValue - minValue || 1)) * chartHeight;

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();

      // Draw points
      ctx.fillStyle = props.color;
      props.data.forEach((point, index) => {
        const x =
          padding.left + (chartWidth / (props.data.length - 1 || 1)) * index;
        const value = point[props.dataKey] || 0;
        const y =
          padding.top +
          chartHeight -
          ((value - minValue) / (maxValue - minValue || 1)) * chartHeight;

        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fill();
      });

      // Draw labels
      ctx.fillStyle = "#A9B7AA";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "center";

      // X-axis labels (show every 5th date)
      props.data.forEach((point, index) => {
        if (index % 5 === 0 || index === props.data.length - 1) {
          const x =
            padding.left + (chartWidth / (props.data.length - 1 || 1)) * index;
          const date = point.date || "";
          const dateLabel = date.split("-").slice(1).join("/");
          ctx.fillText(dateLabel, x, padding.top + chartHeight + 20);
        }
      });

      // Y-axis labels
      ctx.textAlign = "right";
      for (let i = 0; i <= 5; i++) {
        const y = padding.top + (chartHeight / 5) * i;
        const value = maxValue - (maxValue / 5) * i;
        ctx.fillText(Math.round(value).toString(), padding.left - 10, y + 4);
      }
    };

    onMounted(() => {
      nextTick(() => {
        drawChart();
      });
    });

    watch(
      () => [props.data, props.dataKey],
      () => {
        nextTick(() => {
          drawChart();
        });
      },
      { deep: true },
    );

    return {
      chartCanvas,
    };
  },
};
</script>

<style scoped>
.dashboard-chart {
  padding: 1.5rem;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.chart-header h3 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.1rem;
  font-weight: 600;
}

.chart-legend {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.legend-color {
  width: 12px;
  height: 12px;
}

.legend-label {
  color: #a9b7aa;
  font-size: 0.85rem;
}

.chart-container {
  width: 100%;
  overflow-x: auto;
}

canvas {
  display: block;
  max-width: 100%;
}
</style>
