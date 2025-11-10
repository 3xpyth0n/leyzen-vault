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
        placeholder="Filter by IP..."
        class="filter-input"
      />
      <select
        v-model="filters.success"
        @change="loadLogs"
        class="filter-select"
      >
        <option :value="null">All</option>
        <option :value="true">Success</option>
        <option :value="false">Failed</option>
      </select>
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
            <div v-if="log.file_id" class="log-detail">
              <strong>File ID:</strong> {{ log.file_id }}
            </div>
            <div class="log-detail"><strong>IP:</strong> {{ log.user_ip }}</div>
            <div v-if="log.details" class="log-detail">
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

export default {
  name: "AuditLogViewer",
  components: {
    AlertModal,
  },
  setup() {
    const logs = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const filters = ref({
      action: "",
      file_id: "",
      user_ip: "",
      success: null,
      limit: 100,
    });
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
        logs.value = result.logs || [];
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

    onMounted(() => {
      loadLogs();
    });

    return {
      logs,
      loading,
      error,
      filters,
      loadLogs,
      debouncedLoad,
      exportCSV,
      exportJSON,
      showAlertModal,
      alertModalConfig,
      handleAlertModalClose,
      formatDate,
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
}

.log-detail pre {
  margin: 0.5rem 0 0 0;
  padding: 0.5rem;
  background: rgba(15, 23, 42, 0.5);
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.85rem;
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
