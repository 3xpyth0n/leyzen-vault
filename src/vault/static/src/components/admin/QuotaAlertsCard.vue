<template>
  <div class="quota-alerts-card glass glass-card">
    <div class="section-header">
      <h3>Quota Alerts</h3>
      <button @click="$emit('view-all')" class="btn-link">View All</button>
    </div>
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="alerts.length === 0" class="empty-state">
      <p>No quota alerts</p>
    </div>
    <div v-else class="alerts-list">
      <div
        v-for="alert in alerts"
        :key="alert.user_id"
        class="alert-item"
        :class="{
          'alert-critical': alert.usage_percent >= 95,
          'alert-warning':
            alert.usage_percent >= 80 && alert.usage_percent < 95,
        }"
      >
        <div class="alert-icon">
          <span
            :class="[
              'alert-indicator',
              alert.usage_percent >= 95 ? 'critical' : 'warning',
            ]"
          ></span>
        </div>
        <div class="alert-content">
          <div class="alert-email">{{ alert.email }}</div>
          <div class="alert-usage">
            {{ alert.used_gb }} GB / {{ alert.max_gb }} GB ({{
              alert.usage_percent
            }}%)
          </div>
          <div class="alert-progress">
            <div
              class="alert-progress-fill"
              :style="{ width: Math.min(alert.usage_percent, 100) + '%' }"
              :class="{
                critical: alert.usage_percent >= 95,
                warning: alert.usage_percent >= 80 && alert.usage_percent < 95,
              }"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "QuotaAlertsCard",
  props: {
    alerts: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["view-all"],
};
</script>

<style scoped>
.quota-alerts-card {
  padding: 1.5rem;
  border-radius: 1rem;
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
  color: #8b5cf6;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0;
  text-decoration: underline;
  transition: color 0.2s ease;
}

.btn-link:hover {
  color: #8b5cf6;
}

.loading,
.empty-state {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 0.5rem;
  border-left: 3px solid #fbbf24;
  transition: background 0.2s ease;
}

.alert-item:hover {
  background: rgba(30, 41, 59, 0.5);
}

.alert-item.alert-critical {
  border-left-color: #f87171;
}

.alert-item.alert-warning {
  border-left-color: #fbbf24;
}

.alert-icon {
  flex-shrink: 0;
  margin-top: 0.25rem;
}

.alert-indicator {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.alert-indicator.critical {
  background: #f87171;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}

.alert-indicator.warning {
  background: #fbbf24;
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
}

.alert-content {
  flex: 1;
  min-width: 0;
}

.alert-email {
  color: #e6eef6;
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.alert-usage {
  color: #94a3b8;
  font-size: 0.85rem;
  margin-bottom: 0.5rem;
}

.alert-progress {
  width: 100%;
  height: 6px;
  background: rgba(30, 41, 59, 0.6);
  border-radius: 3px;
  overflow: hidden;
}

.alert-progress-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.alert-progress-fill.warning {
  background: linear-gradient(90deg, #fbbf24, #f59e0b);
}

.alert-progress-fill.critical {
  background: linear-gradient(90deg, #f87171, #ef4444);
}
</style>
