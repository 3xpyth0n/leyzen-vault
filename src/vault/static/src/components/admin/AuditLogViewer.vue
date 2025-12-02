<template>
  <div class="audit-log-viewer">
    <div class="section-header">
      <h2>Audit Logs</h2>
      <div class="header-actions">
        <button @click="exportCSV" class="btn btn-secondary">Export CSV</button>
        <button @click="exportJSON" class="btn btn-secondary">
          Export JSON
        </button>
      </div>
    </div>

    <div class="filters">
      <CustomSelect
        v-model="filters.action_type"
        :options="actionTypeFilterOptions"
        @change="loadLogs"
        placeholder="All Actions"
      />
      <input
        v-model="filters.action"
        @input="debouncedLoad"
        type="text"
        placeholder="Filter by action..."
        class="filter-input"
      />
      <input
        v-model="filters.file_id"
        @input="debouncedLoad"
        type="text"
        placeholder="Filter by file ID..."
        class="filter-input"
      />
      <input
        v-model="filters.user_ip"
        @input="debouncedLoad"
        type="text"
        placeholder="Filter by IP or location..."
        class="filter-input"
      />
      <CustomSelect
        v-model="filters.success"
        :options="successFilterOptions"
        @change="loadLogs"
        placeholder="All"
      />
      <input
        v-model.number="filters.limit"
        @change="loadLogs"
        type="number"
        placeholder="Limit"
        class="filter-input filter-limit"
        min="1"
        max="10000"
      />
    </div>

    <div v-if="loading" class="loading">Loading audit logs...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="logs-count">
        Showing {{ logs.length }} log{{ logs.length !== 1 ? "s" : "" }}
      </div>
      <div class="logs-container">
        <div
          v-for="log in logs"
          :key="log.id || log.timestamp"
          class="log-entry"
          :class="{
            'security-event': isSecurityEvent(log.action),
          }"
        >
          <div class="log-header">
            <span
              class="log-action"
              :class="{
                'log-success': log.success,
                'log-failed': !log.success,
              }"
            >
              {{ log.action }}
            </span>
            <span class="log-timestamp">{{ formatDate(log.timestamp) }}</span>
          </div>
          <div class="log-details">
            <div v-if="log.user_id" class="log-detail">
              <strong>User ID:</strong> {{ log.user_id }}
            </div>
            <div v-if="log.file_id" class="log-detail">
              <strong>File ID:</strong> {{ log.file_id }}
            </div>
            <div class="log-detail"><strong>IP:</strong> {{ log.user_ip }}</div>
            <div class="log-detail">
              <strong>IPv4:</strong>
              <span v-if="log.ipv4" class="ip-display"> {{ log.ipv4 }}</span>
              <span v-else class="ip-not-found"> not found</span>
            </div>
            <div class="log-detail">
              <strong>Location:</strong>
              <span v-if="log.ip_location" class="ip-location">
                <template v-if="log.ip_location.country_code">
                  <span class="location-flag">
                    {{ getCountryFlag(log.ip_location.country_code) }}
                  </span>
                </template>
                <span v-if="log.ip_location.country" class="location-text">
                  {{ log.ip_location.country }}
                  <span v-if="log.ip_location.city"
                    >, {{ log.ip_location.city }}</span
                  >
                </span>
                <span
                  v-else-if="log.ip_location.country_code"
                  class="location-text"
                >
                  {{ log.ip_location.country_code }}
                </span>
                <span v-else class="location-text">Unknown</span>
              </span>
              <span v-else class="location-not-found"> not found</span>
            </div>
            <div
              v-if="log.details && Object.keys(log.details).length > 0"
              class="log-detail"
            >
              <strong>Details:</strong>
              <pre>{{ JSON.stringify(log.details, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Alert Modal -->
    <AlertModal
      :show="showAlertModal"
      :type="alertModalConfig.type"
      :title="alertModalConfig.title"
      :message="alertModalConfig.message"
      @close="handleAlertModalClose"
      @ok="handleAlertModalClose"
    />
  </div>
</template>

<script>
import { ref, onMounted } from "vue";
import { admin } from "../../services/api";
import AlertModal from "../AlertModal.vue";
import CustomSelect from "../CustomSelect.vue";

export default {
  name: "AuditLogViewer",
  components: {
    AlertModal,
    CustomSelect,
  },
  setup() {
    const logs = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const filters = ref({
      action_type: null,
      action: "",
      file_id: "",
      user_ip: "",
      success: null,
      limit: 100,
    });

    const actionTypeFilterOptions = [
      { value: null, label: "All Actions" },
      { value: "auth", label: "Authentication" },
      { value: "rate_limit", label: "Rate Limiting" },
      { value: "file", label: "File Operations" },
      { value: "share", label: "Sharing" },
    ];

    const successFilterOptions = [
      { value: null, label: "All" },
      { value: true, label: "Success" },
      { value: false, label: "Failed" },
    ];
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "error",
      title: "Error",
      message: "",
    });

    let loadTimeout = null;

    const loadLogs = async () => {
      loading.value = true;
      error.value = null;
      try {
        const options = {
          limit: filters.value.limit,
        };
        if (filters.value.action) options.action = filters.value.action;
        if (filters.value.file_id) options.file_id = filters.value.file_id;
        if (filters.value.user_ip) options.user_ip = filters.value.user_ip;
        if (filters.value.success !== null)
          options.success = filters.value.success;

        const result = await admin.getAuditLogs(options);
        let filteredLogs = result.logs || [];

        // Filter by action type if selected
        if (filters.value.action_type) {
          const actionType = filters.value.action_type;
          filteredLogs = filteredLogs.filter((log) => {
            const action = log.action || "";
            if (actionType === "auth") {
              return action.startsWith("auth_");
            } else if (actionType === "rate_limit") {
              return action.includes("rate_limit");
            } else if (actionType === "file") {
              return [
                "upload",
                "download",
                "delete",
                "rename",
                "move",
              ].includes(action);
            } else if (actionType === "share") {
              return action.includes("share");
            }
            return true;
          });
        }

        logs.value = filteredLogs;
      } catch (err) {
        error.value = err.message || "Failed to load audit logs";
      } finally {
        loading.value = false;
      }
    };

    const debouncedLoad = () => {
      if (loadTimeout) clearTimeout(loadTimeout);
      loadTimeout = setTimeout(loadLogs, 300);
    };

    const exportCSV = async () => {
      try {
        const blob = await admin.exportAuditLogsCSV(filters.value.limit);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_logs_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Failed to export CSV: " + err.message,
        });
      }
    };

    const exportJSON = async () => {
      try {
        const blob = await admin.exportAuditLogsJSON(filters.value.limit);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `audit_logs_${new Date().toISOString().split("T")[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Failed to export JSON: " + err.message,
        });
      }
    };

    const showAlert = (config) => {
      alertModalConfig.value = {
        type: config.type || "error",
        title: config.title || "Alert",
        message: config.message || "",
      };
      showAlertModal.value = true;
    };

    const handleAlertModalClose = () => {
      showAlertModal.value = false;
    };

    const formatDate = (dateString) => {
      if (!dateString) return "N/A";
      return new Date(dateString).toLocaleString();
    };

    const getCountryFlag = (countryCode) => {
      if (!countryCode || countryCode.length !== 2) return "";
      try {
        // Convert country code to flag emoji
        // Each letter of the country code (e.g., "FR") is converted to a regional indicator symbol
        // Regional Indicator Symbol Letter A = U+1F1E6 (127462)
        const codePoints = countryCode
          .toUpperCase()
          .split("")
          .map((char) => 127462 + (char.charCodeAt(0) - 65));
        const flag = String.fromCodePoint(...codePoints);
        return flag + " "; // Add space after flag
      } catch (e) {
        // Fallback if code point conversion fails
        console.warn("Failed to generate flag emoji for", countryCode, e);
        return "";
      }
    };

    const isSecurityEvent = (action) => {
      if (!action) return false;
      return (
        action.startsWith("auth_") ||
        action.includes("rate_limit") ||
        action === "access_denied"
      );
    };

    onMounted(() => {
      loadLogs();
    });

    return {
      logs,
      loading,
      error,
      filters,
      actionTypeFilterOptions,
      successFilterOptions,
      loadLogs,
      debouncedLoad,
      exportCSV,
      exportJSON,
      showAlertModal,
      alertModalConfig,
      handleAlertModalClose,
      formatDate,
      getCountryFlag,
      isSecurityEvent,
    };
  },
};
</script>

<style scoped>
.audit-log-viewer {
  padding: 0;
  width: 100%;
  box-sizing: border-box;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.section-header h2 {
  margin: 0;
  color: #e6eef6;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.filters {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.filter-input,
.filter-select {
  padding: 0.5rem 1rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
  background: rgba(30, 41, 59, 0.5);
  color: #e6eef6;
  font-size: 0.9rem;
}

.filter-input {
  flex: 1;
  min-width: 150px;
}

.filter-limit {
  max-width: 100px;
}

.logs-count {
  color: #cbd5e1;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.logs-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 600px;
  overflow-y: auto;
}

.log-entry {
  background: rgba(30, 41, 59, 0.4);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 8px;
  padding: 1rem;
  overflow-x: visible;
  max-width: 100%;
  box-sizing: border-box;
}

.log-entry.security-event {
  border-left: 3px solid #f59e0b;
}

.log-entry.security-event.log-failed {
  border-left-color: #ef4444;
}

.log-entry.security-event.log-success {
  border-left-color: #10b981;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.log-action {
  font-weight: 600;
  font-size: 0.95rem;
}

.log-action.log-success {
  color: #10b981;
}

.log-action.log-failed {
  color: #f87171;
}

.log-timestamp {
  color: #94a3b8;
  font-size: 0.85rem;
}

.log-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.log-detail {
  color: #cbd5e1;
  font-size: 0.9rem;
  overflow-x: visible;
  max-width: 100%;
}

.log-detail pre {
  margin: 0.5rem 0 0 0;
  padding: 0.5rem;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 4px;
  overflow-x: auto;
  overflow-y: visible;
  max-width: 100%;
  width: 100%;
  box-sizing: border-box;
  white-space: pre;
  word-break: normal;
  font-size: 0.85rem;
  -webkit-overflow-scrolling: touch;
}

.ip-display {
  font-weight: 500;
}

.ip-original {
  color: #94a3b8;
  font-size: 0.85em;
  margin-left: 0.25rem;
}

.ip-location {
  margin-left: 0.5rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.location-flag {
  font-size: 1.1em;
}

.location-text {
  color: #cbd5e1;
  font-size: 0.9em;
}

.ip-not-found,
.location-not-found {
  color: #94a3b8;
  font-style: italic;
  font-size: 0.9em;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.btn-secondary {
  background: rgba(148, 163, 184, 0.2);
  color: #e6eef6;
}

.btn-secondary:hover {
  background: rgba(148, 163, 184, 0.3);
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
}
</style>
