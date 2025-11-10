<template>
  <div class="api-key-management">
    <div class="section-header glass glass-card">
      <h2>API Key Management</h2>
      <button @click="showCreateModal = true" class="btn btn-primary">
        <span v-html="getIcon('plus', 16)"></span>
        Generate API Key
      </button>
    </div>

    <div class="filters glass glass-card">
      <select
        v-model="filterUserId"
        @change="loadApiKeys"
        class="filter-select"
      >
        <option value="">All Users</option>
        <option v-for="user in users" :key="user.id" :value="user.id">
          {{ user.email }}
        </option>
      </select>
    </div>

    <div v-if="loading" class="loading glass glass-card">
      <span v-html="getIcon('clock', 24)"></span>
      Loading API keys...
    </div>
    <div v-else-if="error" class="error glass glass-card">{{ error }}</div>
    <div v-else class="table-container glass glass-card">
      <table class="api-keys-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>User</th>
            <th>Prefix</th>
            <th>Created</th>
            <th>Last Used</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="apiKey in apiKeys" :key="apiKey?.id || Math.random()">
            <td>{{ apiKey?.name || "N/A" }}</td>
            <td>{{ getUserEmail(apiKey?.user_id) || "N/A" }}</td>
            <td>
              <code class="key-prefix">{{ apiKey?.key_prefix || "N/A" }}</code>
            </td>
            <td>{{ formatDate(apiKey?.created_at) }}</td>
            <td>{{ formatDate(apiKey?.last_used_at) }}</td>
            <td class="actions">
              <button
                @click="revokeApiKey(apiKey?.id)"
                class="btn-icon btn-danger-icon"
                title="Revoke"
                :disabled="!apiKey?.id"
                v-html="getIcon('delete', 18)"
              ></button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Generate API Key Modal -->
    <div v-if="showCreateModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal glass glass-card modal-wide" @click.stop>
        <div class="modal-header">
          <h3>Generate API Key</h3>
          <button
            @click="closeModal"
            class="modal-close-btn"
            aria-label="Close"
            type="button"
          >
            ×
          </button>
        </div>
        <form @submit.prevent="generateApiKey" class="modal-form">
          <div class="form-group">
            <label>User:</label>
            <select v-model="apiKeyForm.userId" required class="form-select">
              <option value="">Select a user</option>
              <option v-for="user in users" :key="user.id" :value="user.id">
                {{ user.email }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Name:</label>
            <input
              v-model="apiKeyForm.name"
              type="text"
              required
              placeholder="e.g., n8n automation"
              class="form-input"
            />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Generate</button>
            <button type="button" @click="closeModal" class="btn btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Show Generated Key Modal -->
    <div
      v-if="showKeyModal && generatedKey"
      class="modal-overlay"
      @click.self="closeKeyModal"
    >
      <div class="modal glass glass-card modal-wide" @click.stop>
        <div class="modal-header">
          <h3>
            <span v-html="getIcon('key', 20)"></span>
            API Key Generated
          </h3>
          <button
            @click="closeKeyModal"
            class="modal-close-btn"
            aria-label="Close"
            type="button"
          >
            ×
          </button>
        </div>
        <div class="modal-body">
          <div class="warning-message glass">
            <span v-html="getIcon('warning', 16)"></span>
            This is the only time you will see this API key. Make sure to copy
            it now and store it securely.
          </div>
          <div class="form-group">
            <label>API Key:</label>
            <div class="key-display">
              <code class="api-key-value">{{ generatedKey }}</code>
              <button
                @click="copyToClipboard"
                class="btn btn-secondary btn-copy"
                :class="{ copied: copied }"
              >
                <span v-if="!copied" v-html="getIcon('copy', 16)"></span>
                <span v-else>Copied!</span>
              </button>
            </div>
          </div>
          <div class="form-actions">
            <button @click="closeKeyModal" class="btn btn-primary">
              I've copied the key
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirmation Modal -->
    <ConfirmationModal
      :show="showConfirmModal"
      :title="confirmModalConfig.title"
      :message="confirmModalConfig.message"
      :confirmText="confirmModalConfig.confirmText"
      :dangerous="confirmModalConfig.dangerous"
      @confirm="handleConfirmModalConfirm"
      @cancel="handleConfirmModalCancel"
      @close="handleConfirmModalCancel"
    />

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
import ConfirmationModal from "../ConfirmationModal.vue";
import AlertModal from "../AlertModal.vue";

export default {
  name: "ApiKeyManagement",
  components: {
    ConfirmationModal,
    AlertModal,
  },
  setup() {
    const apiKeys = ref([]);
    const users = ref([]);
    const loading = ref(false);
    const error = ref(null);
    const filterUserId = ref("");
    const showCreateModal = ref(false);
    const showKeyModal = ref(false);
    const generatedKey = ref(null);
    const copied = ref(false);
    const apiKeyForm = ref({
      userId: "",
      name: "",
    });
    const showConfirmModal = ref(false);
    const confirmModalConfig = ref({
      title: "",
      message: "",
      confirmText: "Confirm",
      dangerous: false,
      onConfirm: null,
    });
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "error",
      title: "Error",
      message: "",
    });

    const getIcon = (iconName, size = 24) => {
      try {
        if (!window || !window.Icons) {
          return "";
        }
        if (!window.Icons[iconName]) {
          return "";
        }
        const iconFn = window.Icons[iconName];
        if (typeof iconFn !== "function") {
          return "";
        }
        return iconFn.call(window.Icons, size, "currentColor");
      } catch (err) {
        console.warn("Error getting icon:", iconName, err);
        return "";
      }
    };

    const loadUsers = async () => {
      try {
        const result = await admin.listUsers({ per_page: 1000 });
        users.value = result.users || [];
      } catch (err) {
        console.error("Failed to load users:", err);
      }
    };

    const loadApiKeys = async () => {
      loading.value = true;
      error.value = null;
      try {
        let keys = await admin.listApiKeys();

        // Filter by user if selected
        if (filterUserId.value) {
          keys = keys.filter((key) => key.user_id === filterUserId.value);
        }

        apiKeys.value = keys;
      } catch (err) {
        console.error("Error in loadApiKeys:", err);
        error.value = err.message || "Failed to load API keys";
        apiKeys.value = [];
      } finally {
        loading.value = false;
      }
    };

    const getUserEmail = (userId) => {
      const user = users.value.find((u) => u.id === userId);
      return user ? user.email : null;
    };

    const generateApiKey = async () => {
      if (!apiKeyForm.value.userId || !apiKeyForm.value.name.trim()) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Please fill in all fields",
        });
        return;
      }

      try {
        const result = await admin.generateApiKey(
          apiKeyForm.value.userId,
          apiKeyForm.value.name.trim(),
        );
        generatedKey.value = result.key;
        showCreateModal.value = false;
        showKeyModal.value = true;
        copied.value = false;
        // Reset form
        apiKeyForm.value = {
          userId: "",
          name: "",
        };
        // Reload API keys
        await loadApiKeys();
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message:
            "Failed to generate API key: " + (err.message || "Unknown error"),
        });
      }
    };

    const revokeApiKey = (keyId) => {
      if (!keyId) {
        return;
      }

      showConfirm({
        title: "Revoke API Key",
        message:
          "Are you sure you want to revoke this API key? This action cannot be undone.",
        confirmText: "Revoke",
        dangerous: true,
        onConfirm: async () => {
          try {
            await admin.revokeApiKey(keyId);
            await loadApiKeys();
            showAlert({
              type: "success",
              title: "Success",
              message: "API key revoked successfully",
            });
          } catch (err) {
            showAlert({
              type: "error",
              title: "Error",
              message:
                "Failed to revoke API key: " + (err.message || "Unknown error"),
            });
          }
        },
      });
    };

    const copyToClipboard = async () => {
      if (!generatedKey.value) {
        return;
      }

      try {
        await navigator.clipboard.writeText(generatedKey.value);
        copied.value = true;
        setTimeout(() => {
          copied.value = false;
        }, 2000);
      } catch (err) {
        showAlert({
          type: "error",
          title: "Error",
          message: "Failed to copy to clipboard",
        });
      }
    };

    const closeModal = () => {
      showCreateModal.value = false;
      apiKeyForm.value = {
        userId: "",
        name: "",
      };
    };

    const closeKeyModal = () => {
      showKeyModal.value = false;
      generatedKey.value = null;
      copied.value = false;
    };

    const showAlert = (config) => {
      alertModalConfig.value = {
        type: config.type || "error",
        title: config.title || "Alert",
        message: config.message || "",
      };
      showAlertModal.value = true;
    };

    const showConfirm = (config) => {
      confirmModalConfig.value = {
        title: config.title || "Confirm Action",
        message: config.message || "Are you sure you want to proceed?",
        confirmText: config.confirmText || "Confirm",
        dangerous: config.dangerous || false,
        onConfirm: config.onConfirm || (() => {}),
      };
      showConfirmModal.value = true;
    };

    const handleConfirmModalConfirm = () => {
      if (confirmModalConfig.value.onConfirm) {
        confirmModalConfig.value.onConfirm();
      }
      showConfirmModal.value = false;
    };

    const handleConfirmModalCancel = () => {
      showConfirmModal.value = false;
    };

    const handleAlertModalClose = () => {
      showAlertModal.value = false;
    };

    const formatDate = (dateString) => {
      if (!dateString || dateString === null || dateString === undefined) {
        return "Never";
      }
      try {
        const date = new Date(dateString);
        if (isNaN(date.getTime())) {
          return "Invalid Date";
        }
        return date.toLocaleString();
      } catch (err) {
        console.error("Error formatting date:", err, dateString);
        return "Invalid Date";
      }
    };

    onMounted(async () => {
      await loadUsers();
      await loadApiKeys();
    });

    return {
      apiKeys,
      users,
      loading,
      error,
      filterUserId,
      showCreateModal,
      showKeyModal,
      generatedKey,
      copied,
      apiKeyForm,
      showConfirmModal,
      confirmModalConfig,
      showAlertModal,
      alertModalConfig,
      getIcon,
      loadApiKeys,
      getUserEmail,
      generateApiKey,
      revokeApiKey,
      copyToClipboard,
      closeModal,
      closeKeyModal,
      showAlert,
      showConfirm,
      handleConfirmModalConfirm,
      handleConfirmModalCancel,
      handleAlertModalClose,
      formatDate,
    };
  },
};
</script>

<style scoped>
.api-key-management {
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

.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  border-radius: 1rem;
}

.filter-select {
  padding: 0.75rem 1rem;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(30, 41, 59, 0.4);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  min-width: 200px;
}

.filter-select:focus {
  outline: none;
  border-color: rgba(56, 189, 248, 0.5);
  background: rgba(30, 41, 59, 0.6);
}

.table-container {
  padding: 1.5rem;
  border-radius: 1rem;
  overflow: hidden;
}

.api-keys-table {
  width: 100%;
  border-collapse: collapse;
}

.api-keys-table th {
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

.api-keys-table td {
  padding: 1rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  color: #e6eef6;
}

.api-keys-table tr:hover {
  background: rgba(30, 41, 59, 0.3);
}

.key-prefix {
  background: rgba(30, 41, 59, 0.6);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-family: "Courier New", monospace;
  font-size: 0.85rem;
  color: #60a5fa;
  border: 1px solid rgba(96, 165, 250, 0.2);
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.btn-icon {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.2);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  width: 36px;
  height: 36px;
}

.btn-icon:hover:not(:disabled) {
  background: rgba(56, 189, 248, 0.1);
  border-color: rgba(56, 189, 248, 0.3);
  color: #38bdf8;
  transform: translateY(-2px);
}

.btn-danger-icon:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.btn-icon:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon :deep(svg) {
  display: block;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
  overflow-y: auto;
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.95),
    rgba(15, 23, 42, 0.9)
  );
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  padding: 0;
  border-radius: 1.25rem;
  min-width: 400px;
  max-width: 90vw;
  max-height: 90vh;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
  margin: auto;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
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

.modal-header h3 :deep(svg) {
  color: #38bdf8;
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

.key-display {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.api-key-value {
  flex: 1;
  background: rgba(30, 41, 59, 0.6);
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  font-family: "Courier New", monospace;
  font-size: 0.9rem;
  color: #60a5fa;
  border: 1px solid rgba(96, 165, 250, 0.2);
  word-break: break-all;
}

.btn-copy {
  flex-shrink: 0;
  white-space: nowrap;
}

.btn-copy.copied {
  background: rgba(34, 197, 94, 0.2);
  border-color: rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  width: 100%;
  box-sizing: border-box;
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

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.warning-message {
  padding: 1rem;
  border-radius: 0.75rem;
  margin: 1rem 0;
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  font-size: 0.9rem;
  border: 1px solid;
  width: 100%;
  box-sizing: border-box;
  background: rgba(251, 191, 36, 0.1);
  border-color: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}

.warning-message :deep(svg) {
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.loading,
.error {
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
</style>
