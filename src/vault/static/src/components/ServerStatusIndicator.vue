<template>
  <div
    class="server-status-indicator"
    :class="{ online: isOnline, offline: !isOnline }"
  >
    <div class="status-dot" :class="{ 'status-checking': isChecking }"></div>
    <span class="status-text">{{ isOnline ? "Online" : "Offline" }}</span>
  </div>
</template>

<script>
import { useHealthCheck } from "../composables/useHealthCheck";

export default {
  name: "ServerStatusIndicator",
  setup() {
    const { isOnline, isChecking } = useHealthCheck();

    return {
      isOnline,
      isChecking,
    };
  },
};
</script>

<style scoped>
.server-status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 0.875rem;
  transition: all 0.3s ease;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
  transition: all 0.3s ease;
  position: relative;
}

.status-dot.status-checking {
  animation: pulse 1.5s ease-in-out infinite;
}

.status-dot.status-checking::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid currentColor;
  opacity: 0.5;
  animation: ripple 1.5s ease-in-out infinite;
}

.server-status-indicator.offline .status-dot {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}

.status-text {
  color: #e6eef6;
  font-weight: 500;
  white-space: nowrap;
}

.server-status-indicator.offline .status-text {
  color: #fca5a5;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

@keyframes ripple {
  0% {
    transform: translate(-50%, -50%) scale(0.8);
    opacity: 0.5;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.5);
    opacity: 0;
  }
}
</style>
