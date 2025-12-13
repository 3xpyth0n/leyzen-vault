<template>
  <div class="api-key-management">
    <div class="section-header glass glass-card">
      <h2>API Key Management</h2>
      <button @click="openCreateModal" class="btn btn-primary">
        Generate API Key
      </button>
    </div>

    <div class="filters glass glass-card">
      <CustomSelect
        v-model="filterUserId"
        :options="userFilterOptions"
        @change="loadApiKeys"
        placeholder="All Users"
      />
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
    <teleport to="body">
      <div
        v-if="showCreateModal"
        class="modal-overlay"
        @click.self="closeModal"
      >
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
          <div class="modal-body">
            <form @submit.prevent="generateApiKey" class="modal-form">
              <div v-if="isSuperadmin" class="form-group">
                <label>User:</label>
                <CustomSelect
                  :key="`user-select-${userOptions?.length || 0}-${showCreateModal}-${isSuperadmin}`"
                  v-model="apiKeyForm.userId"
                  :options="userOptions || []"
                  placeholder="Select a user"
                />
              </div>
              <div
                v-else-if="
                  currentUser && currentUser.global_role !== 'superadmin'
                "
                class="form-group"
              >
                <label>User:</label>
                <div class="form-help form-help-info">
                  API key will be generated for:
                  {{ currentUser.email || currentUser.id }}
                </div>
              </div>
              <div v-else class="form-group">
                <label>User:</label>
                <div class="form-help">
                  Loading user information... (Role:
                  {{ currentUser?.global_role || "unknown" }})
                </div>
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
                <button
                  type="button"
                  @click="closeModal"
                  class="btn btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Show Generated Key Modal -->
    <teleport to="body">
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
    </teleport>

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
import { ref, onMounted, computed, nextTick } from "vue";
import { admin, auth } from "../../services/api";
import ConfirmationModal from "../ConfirmationModal.vue";
import AlertModal from "../AlertModal.vue";
import CustomSelect from "../CustomSelect.vue";

export default {
  name: "ApiKeyManagement",
  components: {
    ConfirmationModal,
    AlertModal,
    CustomSelect,
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
    const currentUser = ref(null);
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
        return "";
      }
    };

    const loadUsers = async () => {
      try {
        const result = await admin.listUsers({ per_page: 1000 });
        users.value = result.users || [];
      } catch (err) {}
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

    const userFilterOptions = computed(() => {
      return [
        { value: "", label: "All Users" },
        ...users.value.map((user) => ({
          value: user.id,
          label: user.email,
        })),
      ];
    });

    const userOptions = computed(() => {
      if (!users.value || users.value.length === 0) {
        return [];
      }
      const options = users.value.map((user) => {
        const email = user.email || user.id || "Unknown";
        const role = user.global_role || "user";
        return {
          value: user.id,
          label: `${email} (${role})`,
        };
      });
      return options;
    });

    const isSuperadmin = computed(() => {
      return (
        currentUser.value && currentUser.value.global_role === "superadmin"
      );
    });

    const generateApiKey = async () => {
      // For admins, ensure userId is set to current user
      if (currentUser.value?.global_role === "admin") {
        apiKeyForm.value.userId = currentUser.value.id;
      }

      // Validate required fields
      if (!apiKeyForm.value.userId || !apiKeyForm.value.name.trim()) {
        showAlert({
          type: "error",
          title: "Error",
          message:
            currentUser.value?.global_role === "superadmin"
              ? "Please select a user and fill in the name"
              : "Please fill in the name",
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

    const openCreateModal = async () => {
      // Ensure currentUser is loaded
      if (!currentUser.value) {
        try {
          currentUser.value = await auth.getCurrentUser();
        } catch (err) {}
      }
      // Ensure users are loaded before opening modal
      if (users.value.length === 0) {
        await loadUsers();
      }
      // For admins, automatically set userId to current user
      if (currentUser.value?.global_role === "admin") {
        apiKeyForm.value.userId = currentUser.value.id;
      }
      showCreateModal.value = true;
      // Force re-render of CustomSelect after modal is shown
      await nextTick();
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
        return "Invalid Date";
      }
    };

    onMounted(async () => {
      try {
        currentUser.value = await auth.getCurrentUser();
      } catch (err) {}
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
      currentUser,
      apiKeyForm,
      showConfirmModal,
      confirmModalConfig,
      showAlertModal,
      alertModalConfig,
      getIcon,
      loadApiKeys,
      getUserEmail,
      userFilterOptions,
      userOptions,
      isSuperadmin,
      generateApiKey,
      revokeApiKey,
      copyToClipboard,
      closeModal,
      openCreateModal,
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

.api-keys-table {
  width: 100%;
  border-collapse: collapse;
}

.mobile-mode .api-keys-table {
  min-width: 600px;
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

.api-keys-table th:last-child {
  width: 100px;
  min-width: 100px;
  max-width: 100px;
  text-align: center;
}

.api-keys-table td {
  padding: 1rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  color: #e6eef6;
  vertical-align: middle;
}

.api-keys-table td:last-child {
  width: 100px;
  min-width: 100px;
  max-width: 100px;
  text-align: center;
  white-space: nowrap;
  padding: 1rem 0.5rem;
  vertical-align: middle;
  display: table-cell;
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
  display: inline-flex;
  gap: 0.5rem;
  justify-content: center;
  align-items: center;
  vertical-align: middle;
}

.api-keys-table td:last-child .actions {
  display: inline-flex;
  vertical-align: middle;
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
  position: fixed !important;
  inset: 0 !important;
  z-index: 100000 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 2rem;
  padding-left: calc(2rem + 250px); /* Default: sidebar expanded (250px) */
  background: rgba(7, 14, 28, 0.6);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  overflow-y: auto;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  opacity: 1 !important;
  visibility: visible !important;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(2rem + 70px); /* Sidebar collapsed (70px) */
}

/* Remove sidebar padding in mobile mode */
body.mobile-mode .modal-overlay {
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
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes slideUp {
  from {
    transform: scale(0.95) translateY(20px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
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
  margin-bottom: 1.5rem;
  padding: 0 0 1.5rem 0;
  border-bottom: 1px solid var(--border-color);
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
  gap: 1.25rem;
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

/* Force CustomSelect visibility - using higher specificity */
.modal-form .form-group :deep(.custom-select) {
  width: 100% !important;
  display: block !important;
  margin-bottom: 0.5rem !important;
  visibility: visible !important;
  opacity: 1 !important;
  height: auto !important;
  min-height: 40px !important;
  position: relative !important;
}

.modal-form .form-group :deep(.custom-select-trigger) {
  width: 100% !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  visibility: visible !important;
  opacity: 1 !important;
  min-height: 44px !important;
  height: auto !important;
  padding: 0.75rem 1rem !important;
  padding-right: 2.5rem !important;
  background: rgba(30, 41, 59, 0.4) !important;
  backdrop-filter: blur(20px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
  border: 1px solid rgba(148, 163, 184, 0.2) !important;
  border-radius: 0.75rem !important;
  color: #e6eef6 !important;
  font-size: 0.95rem !important;
  font-family:
    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, sans-serif !important;
  cursor: pointer !important;
  position: relative !important;
  box-sizing: border-box !important;
}

.modal-form .form-group :deep(.custom-select-value) {
  display: block !important;
  visibility: visible !important;
  opacity: 1 !important;
  color: #94a3b8 !important;
  flex: 1 !important;
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
  min-height: 1.2em !important;
  line-height: 1.5 !important;
}

.modal-form
  .form-group
  :deep(.custom-select.is-placeholder .custom-select-value) {
  color: #94a3b8 !important;
}

.modal-form .form-group :deep(.custom-select-arrow) {
  display: flex !important;
  visibility: visible !important;
  opacity: 1 !important;
  position: absolute !important;
  right: 0.75rem !important;
  top: 50% !important;
  transform: translateY(-50%) !important;
  width: 1rem !important;
  height: 1rem !important;
  color: #94a3b8 !important;
  transition: transform 0.2s ease !important;
  pointer-events: none !important;
  flex-shrink: 0 !important;
}

.modal-form .form-group :deep(.custom-select-arrow svg) {
  display: block !important;
  width: 16px !important;
  height: 16px !important;
  color: #94a3b8 !important;
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
  border-top: 1px solid var(--border-color);
  width: 100%;
  box-sizing: border-box;
  flex-shrink: 0;
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

.form-help {
  font-size: 0.8rem;
  color: #94a3b8;
  margin-top: 0.5rem;
  display: block;
}

.form-help-success {
  color: #22c55e;
}

.form-help-info {
  color: #94a3b8;
  padding: 0.5rem;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 0.5rem;
}

.form-input-loading {
  min-height: 44px;
  display: flex;
  align-items: center;
  color: #94a3b8;
  cursor: default;
}
</style>
