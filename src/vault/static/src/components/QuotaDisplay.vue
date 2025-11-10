<template>
  <div class="quota-display glass glass-card" v-if="quotaInfo">
    <div class="quota-header">
      <h3>Storage Quota</h3>
    </div>
    <div class="quota-content">
      <div class="quota-bar-container">
        <div
          class="quota-bar"
          :class="{
            'quota-warning':
              quotaInfo.disk_percentage >= 80 && quotaInfo.disk_percentage < 95,
            'quota-danger': quotaInfo.disk_percentage >= 95,
          }"
          :style="{
            width: Math.min(quotaInfo.disk_percentage || 0, 100) + '%',
          }"
        ></div>
      </div>
      <div class="quota-stats">
        <span class="quota-used">{{ formatSize(quotaInfo.used) }}</span>
        <span class="quota-separator">/</span>
        <span class="quota-limit">{{
          quotaInfo.limit ? formatSize(quotaInfo.limit) : "N/A"
        }}</span>
        <span class="quota-percentage"
          >({{ Math.round(quotaInfo.disk_percentage || 0) }}%)</span
        >
      </div>
      <div class="quota-available">
        <span v-if="quotaInfo.available && quotaInfo.available > 0">
          {{ formatSize(quotaInfo.available) }} available
        </span>
        <span v-else class="quota-full">Disk full</span>
      </div>
      <div
        v-if="quotaInfo.disk_percentage >= 80"
        class="quota-alert"
        :class="{
          'quota-alert-warning':
            quotaInfo.disk_percentage >= 80 && quotaInfo.disk_percentage < 95,
          'quota-alert-danger': quotaInfo.disk_percentage >= 95,
        }"
      >
        <span v-if="quotaInfo.disk_percentage >= 95">
          ⚠️ Disk storage almost full! Please free up space.
        </span>
        <span v-else>
          ⚠️ Disk storage {{ Math.round(quotaInfo.disk_percentage) }}% full.
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from "vue";
import { quota } from "../services/api";

export default {
  name: "QuotaDisplay",
  props: {
    autoRefresh: {
      type: Boolean,
      default: true,
    },
    refreshInterval: {
      type: Number,
      default: 30000, // 30 seconds
    },
  },
  setup(props) {
    const quotaInfo = ref(null);
    const loading = ref(false);
    const error = ref(null);
    let refreshTimer = null;

    const loadQuota = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await quota.get();
        // Extract user quota info from response
        // The API returns quota information directly
        if (data.used !== undefined) {
          // Data is already the quota object
          quotaInfo.value = data;
        } else {
          // If structure is unexpected, try to extract what we can
          quotaInfo.value = {
            used: data.used || 0,
            limit: data.limit || null,
            available: data.available || 0,
            disk_percentage: data.disk_percentage || data.percentage || 0,
          };
        }
        // Ensure used is always a number
        if (
          quotaInfo.value.used === undefined ||
          quotaInfo.value.used === null ||
          isNaN(quotaInfo.value.used)
        ) {
          quotaInfo.value.used = 0;
        }
        // Convert to number if it's a string
        quotaInfo.value.used = Number(quotaInfo.value.used) || 0;
        quotaInfo.value.limit = quotaInfo.value.limit
          ? Number(quotaInfo.value.limit)
          : null;
        quotaInfo.value.available = Number(quotaInfo.value.available) || 0;
        quotaInfo.value.disk_percentage =
          Number(quotaInfo.value.disk_percentage) || 0;
      } catch (err) {
        error.value = err.message || "Failed to load quota";
      } finally {
        loading.value = false;
      }
    };

    const formatSize = (bytes) => {
      if (bytes === null || bytes === undefined || (bytes !== 0 && !bytes)) {
        return "0 B";
      }
      if (typeof bytes !== "number" || isNaN(bytes) || !isFinite(bytes)) {
        return "0 B";
      }
      if (bytes === 0) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    };

    onMounted(() => {
      loadQuota();
      if (props.autoRefresh) {
        refreshTimer = setInterval(loadQuota, props.refreshInterval);
      }
    });

    const stopRefresh = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
      }
    };

    return {
      quotaInfo,
      loading,
      error,
      loadQuota,
      formatSize,
      stopRefresh,
    };
  },
  beforeUnmount() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer);
    }
  },
};
</script>

<style scoped>
.quota-display {
  padding: 1rem 1.5rem;
  border-radius: var(--radius-md, 8px);
  margin-bottom: 1rem;
}

.quota-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.quota-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.quota-unlimited {
  color: var(--accent-green, #10b981);
  font-size: 0.9rem;
  font-weight: 600;
}

.quota-content {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.quota-bar-container {
  width: 100%;
  height: 8px;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.quota-bar {
  height: 100%;
  background: var(--accent-blue, #38bdf8);
  transition:
    width 0.3s ease,
    background-color 0.3s ease;
  border-radius: 4px;
}

.quota-bar.quota-warning {
  background: var(--accent-yellow, #fbbf24);
}

.quota-bar.quota-danger {
  background: var(--accent-red, #ef4444);
}

.quota-stats {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.quota-used {
  color: var(--text-primary, #f1f5f9);
  font-weight: 600;
}

.quota-separator {
  color: var(--text-secondary, #cbd5e1);
}

.quota-limit {
  color: var(--text-secondary, #cbd5e1);
}

.quota-percentage {
  color: var(--text-muted, #94a3b8);
  font-size: 0.85rem;
}

.quota-available {
  font-size: 0.85rem;
  color: var(--text-secondary, #cbd5e1);
}

.quota-full {
  color: var(--accent-red, #ef4444);
  font-weight: 600;
}

.quota-alert {
  padding: 0.75rem;
  border-radius: var(--radius-md, 8px);
  font-size: 0.9rem;
  margin-top: 0.5rem;
}

.quota-alert-warning {
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.3);
  color: var(--accent-yellow, #fbbf24);
}

.quota-alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--accent-red, #ef4444);
}
</style>
