<template>
  <div class="quota-management">
    <div class="section-header glass glass-card">
      <h2>Quota Management</h2>
      <button @click="showCreateModal = true" class="btn btn-primary">
        Set Quota
      </button>
    </div>

    <!-- Statistics Summary -->
    <div
      v-if="!loading && quotas.length > 0"
      class="stats-summary glass glass-card"
    >
      <div class="stat-item">
        <span class="stat-label">Total Users:</span>
        <span class="stat-value">{{ quotas.length }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Users with Quotas:</span>
        <span class="stat-value">{{ usersWithQuotas }}</span>
      </div>
      <div class="stat-item">
        <span class="stat-label">Total Storage Used:</span>
        <span class="stat-value">{{ formatSize(totalStorageUsed) }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading glass glass-card">
      <span v-html="getIcon('clock', 24)"></span>
      Loading quotas...
    </div>
    <div v-else-if="error" class="error glass glass-card">{{ error }}</div>
    <div v-else-if="quotas.length === 0" class="empty-state glass glass-card">
      <span v-html="getIcon('info', 48)"></span>
      <p>No users found</p>
    </div>
    <div v-else class="table-container glass glass-card">
      <table class="quotas-table">
        <thead>
          <tr>
            <th>User Email</th>
            <th>Max Storage</th>
            <th>Used Storage</th>
            <th>Usage %</th>
            <th>Max Files</th>
            <th>Used Files</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="quota in quotas" :key="quota.id || quota.user_id">
            <td>
              <span v-if="quota.user_email">{{ quota.user_email }}</span>
              <span v-else-if="quota.user_id" class="text-muted"
                >User ID: {{ quota.user_id.substring(0, 8) }}...</span
              >
              <span v-else class="text-muted">N/A</span>
            </td>
            <td>
              <span
                v-if="quota.max_storage_bytes && quota.max_storage_bytes > 0"
              >
                {{ formatQuotaSize(quota.max_storage_bytes) }}
              </span>
              <span v-else class="text-unlimited">Unlimited</span>
            </td>
            <td>{{ formatSize(quota.used_storage_bytes || 0) }}</td>
            <td>
              <span
                v-if="quota.max_storage_bytes && quota.max_storage_bytes > 0"
                :class="{
                  'usage-high': getUsagePercent(quota) >= 90,
                  'usage-medium':
                    getUsagePercent(quota) >= 70 && getUsagePercent(quota) < 90,
                  'usage-low': getUsagePercent(quota) < 70,
                }"
                class="usage-badge"
              >
                {{ getUsagePercent(quota).toFixed(1) }}%
              </span>
              <span v-else class="text-muted">-</span>
            </td>
            <td>
              <span v-if="quota.max_files">{{ quota.max_files }}</span>
              <span v-else class="text-unlimited">Unlimited</span>
            </td>
            <td>{{ quota.used_files || 0 }}</td>
            <td>
              <button
                @click="editQuota(quota)"
                class="btn btn-sm btn-secondary"
                title="Edit Quota"
              >
                <span v-html="getIcon('edit', 16)"></span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create/Edit Quota Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal glass glass-card modal-wide" @click.stop>
        <div class="modal-header">
          <h3>{{ editingQuota ? "Edit Quota" : "Set Quota" }}</h3>
          <button
            @click="closeModal"
            class="modal-close-btn"
            aria-label="Close"
            type="button"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="saveQuota" class="modal-form">
            <div class="form-group">
              <label>User:</label>
              <CustomSelect
                v-model="quotaForm.user_id"
                :options="userOptions"
                :disabled="editingQuota"
                placeholder="Select a user..."
                required
              />
            </div>
            <div class="form-group">
              <label>Max Storage (GB):</label>
              <input
                :value="quotaForm.max_storage_gb"
                type="text"
                min="0"
                step="0.1"
                placeholder="Leave empty for unlimited"
                @input="normalizeQuotaInput"
                class="form-input"
              />
              <small class="form-help">
                Current usage: {{ getCurrentUsage(quotaForm.user_id) }}
              </small>
            </div>
            <div class="form-group">
              <label>Max Files:</label>
              <input
                v-model.number="quotaForm.max_files"
                type="number"
                min="0"
                placeholder="Leave empty for unlimited"
                class="form-input"
              />
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary">Save</button>
              <button
                type="button"
                @click="closeModal"
                class="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                v-if="editingQuota"
                type="button"
                @click="removeQuota"
                class="btn btn-danger"
              >
                Remove Quota
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from "vue";
import { admin } from "../../services/api";
import CustomSelect from "../CustomSelect.vue";

export default {
  name: "QuotaManagement",
  components: {
    CustomSelect,
  },
  setup() {
    const quotas = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const showCreateModal = ref(false);
    const editingQuota = ref(null);
    const quotaForm = ref({
      user_id: "",
      max_storage_gb: null,
      max_files: null,
    });

    const usersWithQuotas = computed(() => {
      return quotas.value.filter(
        (q) => q.max_storage_bytes !== null && q.max_storage_bytes !== 0,
      ).length;
    });

    const totalStorageUsed = computed(() => {
      return quotas.value.reduce(
        (sum, q) => sum + (q.used_storage_bytes || 0),
        0,
      );
    });

    const userOptions = computed(() => {
      return quotas.value.map((quota) => ({
        value: quota.user_id,
        label: quota.user_email || quota.user_id || "Unknown",
      }));
    });

    const getIcon = (iconName, size = 24) => {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    };

    const loadQuotas = async () => {
      loading.value = true;
      error.value = null;
      try {
        const quotasData = await admin.listQuotas();
        // Enrich quotas with user emails if available
        if (Array.isArray(quotasData)) {
          quotas.value = await Promise.all(
            quotasData.map(async (quota) => {
              if (quota.user_id && !quota.user_email) {
                try {
                  const userDetails = await admin.getUserDetails(quota.user_id);
                  if (userDetails && userDetails.user) {
                    quota.user_email = userDetails.user.email;
                  }
                } catch (err) {
                  console.warn("Failed to load user email for quota:", err);
                }
              }
              return quota;
            }),
          );
        } else {
          quotas.value = [];
        }
      } catch (err) {
        console.error("Error loading quotas:", err);
        error.value = err.message || "Failed to load quotas";
        quotas.value = [];
      } finally {
        loading.value = false;
      }
    };

    const formatSize = (bytes) => {
      if (bytes === null || bytes === undefined || (bytes !== 0 && !bytes)) {
        return "0 B";
      }
      try {
        const numBytes = Number(bytes);
        if (isNaN(numBytes) || numBytes < 0) {
          return "0 B";
        }
        if (numBytes === 0) {
          return "0 B";
        }
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(numBytes) / Math.log(k));
        return (
          Math.round((numBytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i]
        );
      } catch (err) {
        console.error("Error formatting size:", err, bytes);
        return "0 B";
      }
    };

    const getUsagePercent = (quota) => {
      if (!quota.max_storage_bytes) return 0;
      const used = quota.used_storage_bytes || 0;
      const max = quota.max_storage_bytes;
      if (max === 0) return 0;
      return (used / max) * 100;
    };

    const getCurrentUsage = (userId) => {
      const quota = quotas.value.find((q) => q.user_id === userId);
      return quota ? formatSize(quota.used_storage_bytes || 0) : "0 B";
    };

    // Helper function to convert GB to bytes with proper rounding
    const gbToBytes = (gb) => {
      if (!gb || gb <= 0) return null;
      // Convert to bytes and round to nearest integer to avoid floating point errors
      return Math.round(gb * 1024 * 1024 * 1024);
    };

    // Helper function to convert bytes to GB with proper precision
    const bytesToGb = (bytes) => {
      if (!bytes || bytes <= 0) return null;
      // Round to 6 decimal places to preserve precision and avoid floating point display errors
      // This ensures that values like 0.1 GB are displayed accurately when converted back
      return Math.round((bytes / (1024 * 1024 * 1024)) * 1000000) / 1000000;
    };

    // Helper function to format quota size using decimal conversion (base 1000)
    // This ensures 0.1 GB displays as 100 MB (0.1 * 1000 = 100)
    const formatQuotaSize = (bytes) => {
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

    // Normalize input: convert comma to dot and ensure valid number
    const normalizeQuotaInput = (event) => {
      let value = event.target.value.trim();

      // If empty, set to null
      if (value === "") {
        quotaForm.value.max_storage_gb = null;
        event.target.value = "";
        return;
      }

      // Replace comma with dot for decimal separator (French/European format)
      value = value.replace(/,/g, ".");

      // Remove any non-numeric characters except dot and minus
      value = value.replace(/[^\d.-]/g, "");

      // Ensure only one dot
      const parts = value.split(".");
      if (parts.length > 2) {
        value = parts[0] + "." + parts.slice(1).join("");
      }

      // Ensure only one minus at the start
      if (value.indexOf("-") > 0) {
        value = value.replace(/-/g, "");
      }
      if (value.startsWith("-")) {
        value = "-" + value.replace(/-/g, "");
      }

      // Convert to number or null
      const numValue =
        value === "" || value === "." || value === "-"
          ? null
          : parseFloat(value);

      // Update the form value
      quotaForm.value.max_storage_gb =
        isNaN(numValue) || numValue < 0 ? null : numValue;

      // Update the input display value to show the normalized version
      if (quotaForm.value.max_storage_gb !== null) {
        event.target.value = quotaForm.value.max_storage_gb.toString();
      } else {
        event.target.value = "";
      }
    };

    const editQuota = (quota) => {
      editingQuota.value = quota;
      quotaForm.value = {
        user_id: quota.user_id,
        max_storage_gb: bytesToGb(quota.max_storage_bytes),
        max_files: quota.max_files || null,
      };
      showCreateModal.value = true;
    };

    const saveQuota = async () => {
      try {
        const max_storage_bytes = gbToBytes(quotaForm.value.max_storage_gb);

        // Normalize max_files: convert empty/NaN/undefined to null, preserve valid numbers
        let max_files = quotaForm.value.max_files;
        if (
          max_files === null ||
          max_files === undefined ||
          max_files === "" ||
          (typeof max_files === "number" && isNaN(max_files))
        ) {
          max_files = null;
        }

        await admin.createOrUpdateQuota({
          user_id: quotaForm.value.user_id,
          max_storage_bytes: max_storage_bytes,
          max_files: max_files,
        });

        await loadQuotas();
        closeModal();
      } catch (err) {
        console.error("Error saving quota:", err);
        error.value = err.message || "Failed to save quota";
      }
    };

    const removeQuota = async () => {
      try {
        // Remove quota by setting max_storage_bytes to 0 (unlimited)
        await admin.createOrUpdateQuota({
          user_id: editingQuota.value.user_id,
          max_storage_bytes: 0,
          max_files: null,
        });

        await loadQuotas();
        closeModal();
      } catch (err) {
        console.error("Error removing quota:", err);
        error.value = err.message || "Failed to remove quota";
      }
    };

    const closeModal = () => {
      showCreateModal.value = false;
      editingQuota.value = null;
      quotaForm.value = {
        user_id: "",
        max_storage_gb: null,
        max_files: null,
      };
    };

    onMounted(() => {
      loadQuotas();
    });

    return {
      quotas,
      loading,
      error,
      showCreateModal,
      editingQuota,
      quotaForm,
      usersWithQuotas,
      totalStorageUsed,
      userOptions,
      getIcon,
      loadQuotas,
      formatSize,
      formatQuotaSize,
      getUsagePercent,
      getCurrentUsage,
      editQuota,
      saveQuota,
      removeQuota,
      closeModal,
      normalizeQuotaInput,
    };
  },
};
</script>

<style scoped>
.quota-management {
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  border-radius: 1rem;
}

.section-header h2 {
  margin: 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
}

.table-container {
  padding: 1.5rem;
  border-radius: 1rem;
  overflow: hidden;
}

.mobile-mode .table-container {
  padding: 0.75rem;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  overflow-y: visible;
  scrollbar-width: thin;
  -ms-overflow-style: -ms-autohiding-scrollbar;
}

.mobile-mode .table-container::-webkit-scrollbar {
  height: 8px;
}

.mobile-mode .table-container::-webkit-scrollbar-track {
  background: rgba(30, 41, 59, 0.3);
  border-radius: 4px;
}

.mobile-mode .table-container::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 4px;
}

.mobile-mode .table-container::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.5);
}

.quotas-table {
  width: 100%;
  border-collapse: collapse;
}

.mobile-mode .quotas-table {
  min-width: 700px;
  width: 100%;
}

.quotas-table th {
  background: rgba(30, 41, 59, 0.4);
  padding: 1rem;
  text-align: left;
  color: #cbd5e1;
  font-weight: 600;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid rgba(148, 163, 184, 0.2);
}

.quotas-table td {
  padding: 1rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  color: #e6eef6;
}

.quotas-table tr:hover {
  background: rgba(30, 41, 59, 0.3);
}

.text-muted {
  color: #94a3b8;
  font-style: italic;
}

.text-unlimited {
  color: #38bdf8;
  font-weight: 500;
}

.usage-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  display: inline-block;
}

.usage-low {
  color: #10b981;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.usage-medium {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.15);
  border: 1px solid rgba(251, 191, 36, 0.3);
}

.usage-high {
  color: #f87171;
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.loading,
.error,
.empty-state {
  padding: 2rem;
  text-align: center;
  border-radius: 1rem;
}

.loading {
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
}

.loading :deep(svg) {
  color: #38bdf8;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.empty-state {
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.empty-state :deep(svg) {
  color: #94a3b8;
  opacity: 0.5;
}

.empty-state p {
  margin: 0;
  font-size: 1.1rem;
}

.stats-summary {
  display: flex;
  gap: 2rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  border-radius: 1rem;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat-label {
  color: #94a3b8;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  color: #e6eef6;
  font-size: 1.25rem;
  font-weight: 600;
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.75rem;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn-primary {
  background: linear-gradient(
    135deg,
    rgba(56, 189, 248, 0.2) 0%,
    rgba(129, 140, 248, 0.2) 100%
  );
  color: #38bdf8;
  border: 1px solid rgba(56, 189, 248, 0.3);
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(56, 189, 248, 0.3) 0%,
    rgba(129, 140, 248, 0.3) 100%
  );
  border-color: rgba(56, 189, 248, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2);
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.1);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.2);
  border-color: rgba(148, 163, 184, 0.3);
}

.btn-danger {
  background: linear-gradient(
    135deg,
    rgba(239, 68, 68, 0.2) 0%,
    rgba(220, 38, 38, 0.2) 100%
  );
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-danger:hover:not(:disabled) {
  background: linear-gradient(
    135deg,
    rgba(239, 68, 68, 0.3) 0%,
    rgba(220, 38, 38, 0.3) 100%
  );
  border-color: rgba(239, 68, 68, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(7, 14, 28, 0.6);
  backdrop-filter: var(--blur);
  -webkit-backdrop-filter: var(--blur);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
  padding-left: calc(2rem + 250px); /* Default: sidebar expanded (250px) */
  overflow-y: auto;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(2rem + 70px); /* Sidebar collapsed (70px) */
}

/* Remove sidebar padding in mobile mode */
.mobile-mode .modal-overlay {
  padding-left: 2rem !important;
  padding-right: 2rem !important;
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 2rem;
  border-radius: 2rem;
  min-width: 400px;
  max-width: 90vw;
  max-height: 90vh;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  margin: auto;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  overflow-y: auto;
}

.modal-wide {
  width: 90%;
  max-width: 600px;
  min-width: 500px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0;
  padding: 1.5rem 2rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  flex-shrink: 0;
  position: relative;
  z-index: 10;
  width: 100%;
  box-sizing: border-box;
}

.modal-header h3 {
  margin: 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modal-close-btn {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #94a3b8;
  cursor: pointer;
  padding: 0.5rem;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.modal-close-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 2rem;
  padding-top: 1.5rem;
  width: 100%;
  box-sizing: border-box;
}

.modal-form {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.form-group {
  margin-bottom: 1.25rem;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-size: 0.9rem;
  font-weight: 500;
  width: 100%;
}

.form-input,
.form-select {
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.4);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.5);
  background: rgba(30, 41, 59, 0.6);
}

.form-input:disabled,
.form-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-help {
  color: #94a3b8;
  font-size: 0.85rem;
  margin-top: 0.5rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
  width: 100%;
  box-sizing: border-box;
  flex-shrink: 0;
}
/* Mobile Mode Styles */
.mobile-mode .quota-card {
  width: 100%;
  padding: 1rem;
}

.mobile-mode .quota-form {
  width: 100%;
}

.mobile-mode .form-actions {
  flex-direction: column;
  gap: 0.5rem;
}

.mobile-mode .form-actions button {
  width: 100%;
}
</style>
