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
            'security-event': isSecurityEvent(log.action, log.success),
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
            <div v-if="log.user_email" class="log-detail">
              <strong>User Email:</strong> {{ log.user_email }}
            </div>
            <div v-if="log.file_id" class="log-detail">
              <strong>File ID:</strong> {{ log.file_id }}
            </div>
            <div class="log-detail"><strong>IP:</strong> {{ log.user_ip }}</div>
            <div class="log-detail">
              <strong>IPv4:</strong>
              <span v-if="log.ipv4">{{ log.ipv4 }}</span>
              <span v-else class="ip-not-found"> not found</span>
            </div>
            <div class="log-detail">
              <strong>Location:</strong>
              <span v-if="log.ip_location" class="ip-location">
                <template v-if="log.ip_location?.country_code">
                  <span class="location-flag">
                    {{ getCountryFlag(log.ip_location.country_code) }}
                  </span>
                </template>
              </span>
            </div>
            <div
              v-if="log.details && Object.keys(log.details).length"
              class="log-detail log-details-json"
            >
              <strong>Details:</strong>
              <pre class="details-code">{{
                stringifyDetails(log.details)
              }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { admin } from "../../services/api";
import CustomSelect from "../CustomSelect.vue";

const logs = ref([]);
const loading = ref(false);
const error = ref(null);
const debounceTimer = ref(null);

const filters = ref({
  action: "",
  file_id: "",
  user_ip: "",
  success: null,
  limit: 100,
});

const successFilterOptions = [
  { value: null, label: "All" },
  { value: true, label: "Success" },
  { value: false, label: "Failed" },
];

const formatDate = (value) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
};

const getCountryFlag = (countryCode) => {
  if (!countryCode || countryCode.length !== 2) return "";
  const base = 127397;
  return countryCode
    .toUpperCase()
    .split("")
    .map((char) => String.fromCodePoint(base + char.charCodeAt(0)))
    .join("");
};

const isSecurityEvent = (action, success) => {
  if (!action) return false;
  const normalized = action.toLowerCase();
  return (
    normalized.includes("denied") ||
    normalized.includes("failed") ||
    normalized.includes("unauthorized") ||
    success === false
  );
};

const stringifyDetails = (details) => {
  try {
    return JSON.stringify(details, null, 2);
  } catch (e) {
    return "";
  }
};

const buildParams = () => {
  const params = {};
  if (filters.value.action) params.action = filters.value.action;
  if (filters.value.file_id) params.file_id = filters.value.file_id;
  if (filters.value.user_ip) params.user_ip = filters.value.user_ip;
  if (filters.value.success !== null) params.success = filters.value.success;
  params.limit = filters.value.limit || 100;
  return params;
};

const loadLogs = async () => {
  loading.value = true;
  error.value = null;
  try {
    const data = await admin.getAuditLogs(buildParams());
    logs.value = data.logs || [];
  } catch (err) {
    error.value = err?.message || "Failed to load audit logs";
    logs.value = [];
  } finally {
    loading.value = false;
  }
};

const debouncedLoad = () => {
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value);
  }
  debounceTimer.value = setTimeout(() => {
    loadLogs();
  }, 300);
};

const exportCSV = async () => {
  error.value = null;
  try {
    const blob = await admin.exportAuditLogsCSV(filters.value.limit || 1000);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-logs-${Date.now()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    error.value = err?.message || "Failed to export CSV";
  }
};

const exportJSON = async () => {
  error.value = null;
  try {
    const blob = await admin.exportAuditLogsJSON(filters.value.limit || 1000);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-logs-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    error.value = err?.message || "Failed to export JSON";
  }
};

onMounted(() => {
  loadLogs();
});

onBeforeUnmount(() => {
  if (debounceTimer.value) {
    clearTimeout(debounceTimer.value);
  }
});
</script>

<style scoped>
.audit-log-viewer {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.5rem;
  width: 100%;
  box-sizing: border-box;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h2 {
  margin: 0;
  color: var(--text-primary, #e6eef6);
  font-size: 1.75rem;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.btn {
  padding: 0.625rem 1.25rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.4);
  color: var(--text-primary, #e6eef6);
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn:hover {
  background: rgba(30, 41, 59, 0.6);
  border-color: rgba(56, 189, 248, 0.5);
}

.btn-secondary {
  background: rgba(30, 41, 59, 0.4);
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 1rem;
  background: rgba(30, 41, 59, 0.3);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
}

.filter-input {
  padding: 0.625rem 1rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  background: rgba(15, 23, 42, 0.4);
  color: var(--text-primary, #e6eef6);
  font-size: 0.9rem;
  transition: all 0.2s ease;
  min-width: 150px;
}

.filter-input:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.5);
  background: rgba(15, 23, 42, 0.6);
}

.filter-input::placeholder {
  color: rgba(148, 163, 184, 0.6);
}

.filter-limit {
  min-width: 80px;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.3);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.loading {
  color: var(--text-secondary, #94a3b8);
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
}

.logs-count {
  color: var(--text-secondary, #94a3b8);
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.logs-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.log-entry {
  padding: 1.25rem;
  background: rgba(15, 23, 42, 0.3);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  transition: all 0.2s ease;
  width: 100%;
  box-sizing: border-box;
}

.log-entry:hover {
  background: rgba(15, 23, 42, 0.5);
  border-color: rgba(148, 163, 184, 0.3);
}

.log-entry.security-event {
  background: rgba(239, 68, 68, 0.05);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.log-action {
  font-weight: 600;
  font-size: 1.1rem;
  color: var(--text-primary, #e6eef6);
  text-transform: capitalize;
}

.log-action.log-success {
  color: #86efac;
}

.log-action.log-failed {
  color: #f87171;
}

.log-timestamp {
  color: var(--text-secondary, #94a3b8);
  font-size: 0.9rem;
}

.log-details {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.log-detail {
  display: flex;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-secondary, #94a3b8);
  line-height: 1.5;
}

.log-detail strong {
  color: var(--text-primary, #e6eef6);
  font-weight: 600;
  min-width: 100px;
}

.ip-not-found {
  color: rgba(148, 163, 184, 0.5);
  font-style: italic;
}

.location-flag {
  font-size: 1.2rem;
}

.log-details-json {
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}

.details-code {
  margin: 0.5rem 0 0 0;
  padding: 0.75rem 1rem;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  font-family: "Courier New", Courier, monospace;
  font-size: 0.85rem;
  color: var(--text-primary, #e6eef6);
  overflow-x: auto;
  white-space: pre;
  line-height: 1.5;
  min-width: 0;
  max-width: 100%;
  width: --webkit-fill-available;
  box-sizing: border-box;
}

.log-detail {
  overflow-wrap: break-word;
  word-break: break-word;
}

.log-detail strong {
  flex-shrink: 0;
}

.log-action {
  overflow-wrap: break-word;
  word-break: break-word;
}

@media (max-width: 768px) {
  .audit-log-viewer {
    padding: 1rem;
    gap: 1rem;
  }

  .section-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;
  }

  .section-header h2 {
    font-size: 1.5rem;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .btn {
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    flex: 1;
    min-width: 120px;
  }

  .filters {
    flex-direction: column;
  }

  .filter-input {
    width: 100%;
    min-width: unset;
  }

  .log-entry {
    padding: 1rem;
  }

  .log-header {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .log-action {
    font-size: 1rem;
  }

  .log-timestamp {
    font-size: 0.85rem;
  }

  .log-detail strong {
    min-width: 80px;
  }
}

@media (max-width: 640px) {
  .audit-log-viewer {
    padding: 0.75rem;
    gap: 0.75rem;
  }

  .section-header h2 {
    font-size: 1.25rem;
  }

  .header-actions {
    flex-direction: column;
    width: 100%;
  }

  .btn {
    width: 100%;
    padding: 0.625rem 1rem;
  }

  .filters {
    padding: 0.75rem;
    gap: 0.5rem;
  }

  .filter-input {
    font-size: 0.85rem;
    padding: 0.5rem 0.75rem;
  }

  .logs-count {
    font-size: 0.85rem;
  }

  .log-entry {
    padding: 0.75rem;
  }

  .log-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .log-action {
    font-size: 0.95rem;
    width: 100%;
  }

  .log-timestamp {
    font-size: 0.8rem;
  }

  .log-details {
    gap: 0.5rem;
  }

  .log-detail {
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.85rem;
  }

  .log-detail strong {
    min-width: unset;
    display: block;
  }

  .details-code {
    font-size: 0.75rem;
    padding: 0.5rem 0.75rem;
    white-space: pre;
    overflow-x: auto;
  }
}
</style>
