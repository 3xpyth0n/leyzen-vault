<template>
  <div
    v-if="visible"
    :class="['progress-container', { 'progress-sticky': sticky }]"
  >
    <div class="progress-content">
      <div class="progress-header">
        <div v-if="fileName" class="progress-file-name">
          <Icon
            v-if="status"
            :name="status === 'Uploading...' ? 'upload' : 'download'"
            :size="16"
            class="progress-status-icon"
          />
          <span class="progress-file-name-text">{{ fileName }}</span>
        </div>
        <button
          v-if="onCancel"
          @click="handleCancel"
          class="progress-cancel-btn"
          type="button"
          title="Cancel"
        >
          <Icon name="x" :size="16" />
        </button>
      </div>
      <div class="progress-bar-wrapper">
        <div
          class="progress-bar"
          :style="{ width: `${Math.min(100, Math.max(0, progress))}%` }"
        ></div>
      </div>
      <div class="progress-info">
        <span class="progress-percent">{{ Math.round(progress) }}%</span>
        <span v-if="speed > 0" class="progress-speed">
          {{ formatSpeed(speed) }}
        </span>
        <span
          v-if="timeRemaining !== null && timeRemaining > 0"
          class="progress-time"
        >
          {{ formatTimeRemaining(timeRemaining) }}
        </span>
        <span v-if="status" class="progress-status">{{ status }}</span>
      </div>
    </div>
  </div>
</template>

<script>
import Icon from "./Icon.vue";

export default {
  name: "ProgressBar",
  components: {
    Icon,
  },
  props: {
    progress: {
      type: Number,
      default: 0,
      validator: (value) => value >= 0 && value <= 100,
    },
    speed: {
      type: Number,
      default: 0,
    },
    timeRemaining: {
      type: Number,
      default: null,
    },
    fileName: {
      type: String,
      default: "",
    },
    status: {
      type: String,
      default: "",
    },
    visible: {
      type: Boolean,
      default: true,
    },
    sticky: {
      type: Boolean,
      default: false,
    },
    onCancel: {
      type: Function,
      default: null,
    },
  },
  methods: {
    formatSpeed(bytesPerSecond) {
      if (bytesPerSecond < 1024) {
        return `${Math.round(bytesPerSecond)} B/s`;
      }
      if (bytesPerSecond < 1024 * 1024) {
        return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
      }
      return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
    },
    formatTimeRemaining(seconds) {
      if (!seconds || !isFinite(seconds)) {
        return "";
      }
      if (seconds < 60) {
        return `${Math.round(seconds)}s remaining`;
      }
      if (seconds < 3600) {
        const minutes = Math.round(seconds / 60);
        return `${minutes}m remaining`;
      }
      const hours = Math.round(seconds / 3600);
      return `${hours}h remaining`;
    },
    handleCancel() {
      if (this.onCancel) {
        this.onCancel();
      }
    },
  },
};
</script>

<style scoped>
.progress-container {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border-radius: var(--radius-md, 0.5rem);
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.progress-container.progress-sticky {
  position: fixed;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  width: 90%;
  max-width: 600px;
  margin: 0;
  padding: 1.25rem 1.5rem;
  z-index: 10002;
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.98),
    rgba(15, 23, 42, 0.95)
  );
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 2rem;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(255, 255, 255, 0.05) inset;
  animation: slideUp 0.3s ease-out;
}

@media (max-width: 768px) {
  .progress-container.progress-sticky {
    width: calc(100% - 2rem);
    bottom: 1rem;
    left: 1rem;
    right: 1rem;
    transform: none;
  }
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(100%);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

@media (max-width: 768px) {
  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(100%);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
}

.progress-content {
  width: 100%;
}

.progress-header {
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.progress-file-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary, #f1f5f9);
  word-break: break-word;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.progress-file-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-status-icon {
  flex-shrink: 0;
  color: var(--text-secondary, #cbd5e1);
}

.progress-cancel-btn {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  padding: 0.375rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  color: #ef4444;
  flex-shrink: 0;
}

.progress-cancel-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
  transform: scale(1.1);
}

.progress-cancel-btn:active {
  transform: scale(0.95);
}

.progress-bar-wrapper {
  width: 100%;
  height: 8px;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.75rem;
}

.progress-bar {
  height: 100%;
  background: var(
    --accent-gradient,
    linear-gradient(90deg, #38bdf8 0%, #3b82f6 100%)
  );
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.875rem;
  color: var(--text-secondary, #cbd5e1);
  gap: 1rem;
  flex-wrap: wrap;
}

.progress-percent {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.progress-speed,
.progress-time,
.progress-status {
  white-space: nowrap;
}

.progress-status {
  font-style: italic;
}
</style>
