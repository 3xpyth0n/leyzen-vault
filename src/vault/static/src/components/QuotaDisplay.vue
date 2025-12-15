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
            'quota-warning': quotaPercentage >= 80 && quotaPercentage < 100,
            'quota-danger': quotaPercentage >= 100,
          }"
          :style="{
            width: Math.min(quotaPercentage || 0, 100) + '%',
          }"
        ></div>
      </div>
      <div class="quota-stats">
        <span class="quota-used">{{ formatSize(quotaInfo.used) }}</span>
        <span class="quota-separator">/</span>
        <span class="quota-limit">{{
          quotaInfo.limit ? formatQuotaLimit(quotaInfo.limit) : "N/A"
        }}</span>
        <span class="quota-percentage"
          >({{ Math.round(quotaPercentage || 0) }}%)</span
        >
      </div>
      <div class="quota-available">
        <span v-if="quotaInfo.available && quotaInfo.available > 0">
          {{ formatSize(quotaInfo.available) }} available
        </span>
        <span v-else-if="quotaPercentage >= 100" class="quota-full"
          >Quota limit reached</span
        >
        <span v-else class="quota-full">No space available</span>
      </div>
      <div
        v-if="quotaPercentage >= 80"
        class="quota-alert"
        :class="{
          'quota-alert-warning': quotaPercentage >= 80 && quotaPercentage < 100,
          'quota-alert-danger': quotaPercentage >= 100,
        }"
      >
        <span v-if="quotaPercentage >= 100">
          ⚠️ Maximum quota reached! You have used 100% of your storage quota.
          Please free up space.
        </span>
        <span v-else>
          ⚠️ Warning: You have used {{ Math.round(quotaPercentage) }}% of your
          storage quota.
        </span>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue";
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

    const isAuthenticated = () => {
      return localStorage.getItem("jwt_token") !== null;
    };

    // Computed property to get the correct percentage (priority: percentage > disk_percentage)
    const quotaPercentage = computed(() => {
      if (!quotaInfo.value) return 0;
      // Use percentage field (works for both user-specific quota and disk total)
      return (
        Number(quotaInfo.value.percentage) ||
        Number(quotaInfo.value.disk_percentage) ||
        0
      );
    });

    const loadQuota = async () => {
      if (!isAuthenticated()) {
        stopRefresh();
        return;
      }

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
            percentage: data.percentage || data.disk_percentage || 0,
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
        quotaInfo.value.percentage =
          Number(quotaInfo.value.percentage) ||
          Number(quotaInfo.value.disk_percentage) ||
          0;
        quotaInfo.value.disk_percentage =
          Number(quotaInfo.value.disk_percentage) ||
          Number(quotaInfo.value.percentage) ||
          0;
      } catch (err) {
        error.value = err.message || "Failed to load quota";
        if (err.message && err.message.includes("401")) {
          stopRefresh();
        }
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

    // Helper function to format quota limit using decimal conversion (base 1000)
    // This ensures 0.1 GB displays as 100 MB (0.1 * 1000 = 100)
    const formatQuotaLimit = (bytes) => {
      if (!bytes || bytes <= 0) return "0 MB";

      // Convert bytes to GB using binary (1024 base) as stored
      const gb = bytes / (1024 * 1024 * 1024);

      // Convert to MB using decimal base (1000) for display
      // This way 0.1 GB = 100 MB, 0.12 GB = 120 MB, etc.
      const mb = Math.round(gb * 1000);

      // If less than 1 MB, show in KB
      if (mb < 1) {
        const kb = Math.round(((bytes / 1024) * 1000) / 1024);
        return kb + " KB";
      }

      // If less than 1000 MB, show in MB
      if (mb < 1000) {
        return mb + " MB";
      }

      // If 1000 MB or more, show in GB with decimals
      const gbDisplay = mb / 1000;
      // Round to 2 decimal places max, removing trailing zeros
      const gbRounded = Math.round(gbDisplay * 100) / 100;
      return gbRounded + " GB";
    };

    const stopRefresh = () => {
      if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
      }
    };

    const startRefresh = () => {
      if (!isAuthenticated()) {
        return;
      }
      if (props.autoRefresh && !refreshTimer) {
        refreshTimer = setInterval(loadQuota, props.refreshInterval);
      }
    };

    onMounted(() => {
      if (isAuthenticated()) {
        loadQuota();
        startRefresh();
      }
    });

    onBeforeUnmount(() => {
      stopRefresh();
    });

    watch(
      () => localStorage.getItem("jwt_token"),
      (newToken, oldToken) => {
        if (!newToken && oldToken) {
          stopRefresh();
          quotaInfo.value = null;
        } else if (newToken && !oldToken) {
          loadQuota();
          startRefresh();
        }
      },
    );

    return {
      quotaInfo,
      quotaPercentage,
      loading,
      error,
      loadQuota,
      formatSize,
      formatQuotaLimit,
      stopRefresh,
    };
  },
};
</script>

<style scoped>
.quota-display {
  padding: 1rem 1.5rem;
  border-radius: var(--radius-md, 8px);
  margin-bottom: 1rem;
}

.mobile-mode .quota-display {
  padding: 0.75rem 1rem;
  margin-bottom: 0.75rem;
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
  background: var(--accent-blue, #8b5cf6);
  transition:
    width 0.3s ease,
    background-color 0.3s ease;
  border-radius: 4px;
}

.quota-bar.quota-warning {
  background: var(--accent-orange, #f97316);
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
  background: rgba(249, 115, 22, 0.1);
  border: 1px solid rgba(249, 115, 22, 0.3);
  color: var(--accent-orange, #f97316);
}

.quota-alert-danger {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: var(--accent-red, #ef4444);
}
</style>
