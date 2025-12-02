<template>
  <div class="recent-activity-list glass glass-card">
    <div class="section-header">
      <h3>Recent Activity</h3>
      <button @click="$emit('view-all')" class="btn-link">View All</button>
    </div>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="logs.length === 0" class="empty-state">
      <p>No recent activity</p>
    </div>
    <div v-else class="logs-list">
      <div
        v-for="log in displayedLogs"
        :key="log.id || log.timestamp"
        class="log-item"
        :class="{ 'log-failed': !log.success }"
      >
        <div class="log-icon">
          <span
            :class="['status-indicator', log.success ? 'success' : 'failed']"
          ></span>
        </div>
        <div class="log-content">
          <div class="log-action">{{ log.action }}</div>
          <div class="log-meta">
            <span class="log-ip">{{ log.user_ip }}</span>
            <span class="log-time">{{ formatDate(log.timestamp) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "RecentActivityList",
  props: {
    logs: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["view-all"],
  computed: {
    displayedLogs() {
      return this.logs.slice(0, 3);
    },
  },
  methods: {
    formatDate(dateString) {
      if (!dateString) return "N/A";
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);

      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays < 7) return `${diffDays}d ago`;
      return date.toLocaleDateString();
    },
  },
};
</script>

<style scoped>
.recent-activity-list {
  padding: 1.5rem;
  border-radius: 1rem;
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

.mobile-mode .recent-activity-list {
  padding: 1rem;
  max-width: 100%;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h3 {
  margin: 0;
  color: #e6eef6;
  font-size: 1.1rem;
  font-weight: 600;
}

.btn-link {
  background: none;
  border: none;
  color: #60a5fa;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0;
  text-decoration: underline;
  transition: color 0.2s ease;
}

.btn-link:hover {
  color: #38bdf8;
}

.loading,
.empty-state {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
}

.logs-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.log-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 0.5rem;
  border-left: 3px solid #38bdf8;
  transition: background 0.2s ease;
}

.log-item:hover {
  background: rgba(30, 41, 59, 0.5);
}

.log-item.log-failed {
  border-left-color: #f87171;
}

.log-icon {
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.status-indicator {
  display: block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-indicator.success {
  background: #10b981;
}

.status-indicator.failed {
  background: #f87171;
}

.log-content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.mobile-mode .log-content {
  min-width: 0;
  max-width: 100%;
}

.log-action {
  color: #e6eef6;
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.25rem;
  text-transform: capitalize;
  word-break: break-word;
  overflow-wrap: break-word;
}

.mobile-mode .log-action {
  font-size: 0.85rem;
}

.log-meta {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.log-ip {
  color: #94a3b8;
  font-size: 0.8rem;
  font-family: monospace;
}

.log-time {
  color: #94a3b8;
  font-size: 0.8rem;
}
</style>
