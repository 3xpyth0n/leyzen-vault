<template>
  <div class="external-storage-config">
    <div class="integration-card" @click="openModal">
      <div class="integration-logo">
        <img :src="s3LogoPath" alt="S3 Storage" />
      </div>
      <div class="integration-content">
        <h3>S3 Storage</h3>
        <p class="integration-description">
          Configure S3-compatible external storage for your files. Supports AWS
          S3, MinIO, and other S3-compatible services.
        </p>
        <div class="integration-status" v-if="config">
          <span
            class="status-badge"
            :class="config.storage_mode === 'local' ? 'inactive' : 'active'"
          >
            {{ getStatusText() }}
          </span>
        </div>
      </div>
      <div class="integration-actions">
        <div
          v-if="config && config.storage_mode !== 'local'"
          class="sync-controls"
        >
          <button
            @click.stop="openInfoModal"
            class="btn-info"
            title="Learn about synchronization modes"
            type="button"
          >
            <span v-html="getIcon('info', 18)"></span>
          </button>
          <CustomSelect
            v-model="selectedSyncMode"
            :options="syncModeOptions"
            placeholder="Select sync mode"
            :disabled="syncing"
            size="small"
            class="sync-mode-select"
          />
          <button
            @click.stop="syncVaultspaces"
            class="btn-sync-trigger"
            :disabled="syncing"
            :title="
              syncing
                ? 'Synchronizing...'
                : `Start ${getSyncModeLabel(selectedSyncMode)} synchronization`
            "
          >
            <span
              v-html="getIcon(syncing ? 'clock' : 'refresh-ccw', 18)"
            ></span>
          </button>
        </div>
        <div class="integration-arrow">
          <span v-html="getIcon('arrow-right', 20)"></span>
        </div>
      </div>
    </div>

    <Teleport v-if="showModal" to="body">
      <div class="modal-overlay" @click.self="closeModal">
        <div class="modal modal-wide" @click.stop>
          <div class="modal-header">
            <div class="modal-title">
              <img :src="s3LogoPath" alt="S3 Storage" class="modal-logo" />
              <h3>S3 External Storage Configuration</h3>
            </div>
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
            <div v-if="loading" class="loading">
              <span v-html="getIcon('clock', 24)"></span>
              Loading configuration...
            </div>
            <div v-else-if="error" class="error">{{ error }}</div>
            <form v-else @submit.prevent="saveConfig" class="config-form">
              <div class="form-group">
                <label>Storage Mode:</label>
                <CustomSelect
                  v-model="config.storage_mode"
                  :options="storageModeOptions"
                  placeholder="Select storage mode"
                />
                <div class="form-help">
                  <ul>
                    <li>
                      <strong>Local Only:</strong> Uses only local storage
                    </li>
                    <li><strong>S3 Only:</strong> Uses only S3 storage</li>
                    <li>
                      <strong>Hybrid:</strong> Uses both local and S3 with
                      synchronization
                    </li>
                  </ul>
                </div>
              </div>

              <div
                v-if="testResult"
                class="test-result"
                :class="testResult.success ? 'success' : 'error'"
              >
                <span
                  v-html="getIcon(testResult.success ? 'check' : 'warning', 16)"
                ></span>
                {{ testResult.message }}
              </div>

              <div class="form-actions">
                <div class="test-connection-wrapper">
                  <button
                    v-if="config.storage_mode !== 'local'"
                    @click="testConnection"
                    type="button"
                    class="btn btn-secondary"
                    :disabled="testing"
                  >
                    <span v-if="testing">Testing...</span>
                    <span v-else>Test Connection</span>
                  </button>
                </div>
                <div class="save-actions">
                  <button
                    type="submit"
                    class="btn btn-primary"
                    :disabled="
                      saving ||
                      (config.storage_mode !== 'local' && !testSuccessful)
                    "
                  >
                    <span v-if="saving">Saving...</span>
                    <span v-else>Save Configuration</span>
                  </button>
                  <button
                    type="button"
                    @click="closeModal"
                    class="btn btn-secondary"
                  >
                    Cancel
                  </button>
                </div>
              </div>

              <div
                v-if="saveResult"
                class="save-result"
                :class="saveResult.success ? 'success' : 'error'"
              >
                <span
                  v-html="getIcon(saveResult.success ? 'check' : 'warning', 16)"
                ></span>
                {{ saveResult.message }}
              </div>
            </form>
          </div>
        </div>
      </div>
    </Teleport>

    <AlertModal
      :show="showAlertModal"
      :type="alertModalConfig.type"
      :title="alertModalConfig.title"
      :message="alertModalConfig.message"
      @close="handleAlertModalClose"
      @ok="handleAlertModalClose"
    />

    <Teleport v-if="showInfoModal" to="body">
      <div class="modal-overlay" @click.self="closeInfoModal">
        <div class="modal" @click.stop>
          <div class="modal-header">
            <div class="modal-title">
              <h3>Synchronization Modes</h3>
            </div>
            <button
              @click="closeInfoModal"
              class="modal-close-btn"
              aria-label="Close"
              type="button"
            >
              ×
            </button>
          </div>
          <div class="modal-body">
            <div class="info-modal-content">
              <div class="sync-mode-explanation">
                <h4>Bidirectional</h4>
                <p>
                  Synchronizes files in both directions. If a file exists in
                  both locations, the newer version (based on modification
                  timestamp) is kept. Files only in local storage are uploaded
                  to S3, and files only in S3 are downloaded to local storage.
                </p>
              </div>
              <div class="sync-mode-explanation">
                <h4>Upload to S3</h4>
                <p>
                  Overwrites all files in S3 with the content from local
                  storage. All local files are uploaded to S3, replacing any
                  existing files with the same name. Files that don't exist
                  locally are skipped.
                </p>
              </div>
              <div class="sync-mode-explanation">
                <h4>Download from S3</h4>
                <p>
                  Overwrites all local files with the content from S3. All files
                  in S3 are downloaded to local storage, replacing any existing
                  local files with the same name. Files that don't exist in S3
                  are skipped.
                </p>
              </div>
              <div class="info-modal-footer">
                <p>
                  <strong>How to use:</strong> Select a synchronization mode
                  from the dropdown menu, then click the sync button to start
                  the synchronization process.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch } from "vue";
import { admin } from "../../services/api";
import CustomSelect from "../CustomSelect.vue";
import AlertModal from "../AlertModal.vue";

export default {
  name: "ExternalStorageConfig",
  components: {
    CustomSelect,
    AlertModal,
  },
  setup() {
    const loading = ref(true);
    const error = ref(null);
    const saving = ref(false);
    const testing = ref(false);
    const testResult = ref(null);
    const testSuccessful = ref(false);
    const saveResult = ref(null);
    const showModal = ref(false);
    const originalConfig = ref(null); // Store original config when opening modal
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "success",
      title: "Success",
      message: "",
    });
    const syncing = ref(false);
    const selectedSyncMode = ref("bidirectional"); // Default sync mode
    const showInfoModal = ref(false); // Control info modal visibility
    const showSecretKey = ref(false); // Control secret key visibility
    const config = ref({
      storage_mode: "local",
    });

    let syncStatusInterval = null; // Interval for polling sync status

    // Store the logo path in a variable to avoid Vite treating it as a module import
    // The binding :src in the template should prevent Vite from resolving it at build time
    const s3LogoPath = "/static/public/s3-logo.png";

    // Storage mode options for CustomSelect
    const storageModeOptions = [
      { label: "Local Only", value: "local" },
      { label: "S3 Only", value: "s3" },
      { label: "Hybrid (Local + S3)", value: "hybrid" },
    ];

    // Sync mode options for CustomSelect
    const syncModeOptions = [
      { label: "Bidirectional", value: "bidirectional" },
      { label: "Upload to S3", value: "to_s3" },
      { label: "Download from S3", value: "from_s3" },
    ];

    const onStorageModeChange = () => {
      testResult.value = null;
      saveResult.value = null;
    };

    // Watch for storage mode changes
    watch(
      () => config.value.storage_mode,
      (newMode) => {
        testSuccessful.value = newMode === "local";
        testResult.value = null;
        onStorageModeChange();
      },
    );

    const loadConfig = async () => {
      loading.value = true;
      error.value = null;
      try {
        const response = await admin.getExternalStorageConfig();

        config.value = {
          storage_mode: response.storage_mode || "local",
        };

        testSuccessful.value = config.value.storage_mode === "local";
      } catch (err) {
        error.value = err.message || "Failed to load configuration";
      } finally {
        loading.value = false;
      }
    };

    const testConnection = async () => {
      if (config.value.storage_mode === "local") {
        testResult.value = {
          success: false,
          message: "Please select S3 Only or Hybrid mode to test connection",
        };
        return;
      }

      testing.value = true;
      testResult.value = null;
      testSuccessful.value = false;

      try {
        const response = await admin.testExternalStorageConnection();

        testResult.value = {
          success: response.success,
          message:
            response.message || response.error || "Connection test completed",
        };
        testSuccessful.value = response.success;
        console.debug("Test successful set to:", testSuccessful.value);
      } catch (err) {
        testResult.value = {
          success: false,
          message: err.message || "Connection test failed",
        };
        testSuccessful.value = false;
        console.debug("Test failed, successful set to:", testSuccessful.value);
      } finally {
        testing.value = false;
      }
    };

    const saveConfig = async () => {
      saving.value = true;
      saveResult.value = null;

      try {
        const payload = {
          storage_mode: config.value.storage_mode,
        };

        const response = await admin.saveExternalStorageConfig(payload);

        // Reload config to get updated values
        await loadConfig(false);

        originalConfig.value = JSON.parse(JSON.stringify(config.value));

        await closeModal();

        showAlert({
          type: "success",
          title: "Success",
          message: "Configuration saved successfully",
        });
      } catch (err) {
        // Keep modal open and show error in the modal
        saveResult.value = {
          success: false,
          message: err.message || "Failed to save configuration",
        };
      } finally {
        saving.value = false;
      }
    };

    const getIcon = (iconName, size = 24) => {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      const iconFn = window.Icons[iconName];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    };

    const openModal = async () => {
      // Save current config state before opening modal
      originalConfig.value = JSON.parse(JSON.stringify(config.value));
      showModal.value = true;

      // Reload config when opening modal to get latest state
      // Both Access Key ID and Secret Access Key will be loaded from server (decrypted)
      await loadConfig(false);

      originalConfig.value = JSON.parse(JSON.stringify(config.value));
    };

    const closeModal = async () => {
      showModal.value = false;
      testResult.value = null;
      saveResult.value = null;

      // Reload config from server to ensure we have the true saved state
      // Both Access Key ID and Secret Access Key will be loaded from server (decrypted)
      await loadConfig(false);
    };

    const getStatusText = () => {
      if (!config.value || !config.value.storage_mode) {
        return "Not configured";
      }
      const mode = config.value.storage_mode;
      if (mode === "local") {
        return "Local Only";
      } else if (mode === "s3") {
        return "S3 Only";
      } else if (mode === "hybrid") {
        return "Hybrid Mode";
      }
      return "Not configured";
    };

    const checkSyncStatus = async () => {
      try {
        const status = await admin.getExternalStorageStatus();
        syncing.value = status.sync_running || false;

        if (!status.sync_running && syncStatusInterval) {
          clearInterval(syncStatusInterval);
          syncStatusInterval = null;
        }
      } catch (err) {}
    };

    const showAlert = (config) => {
      alertModalConfig.value = {
        type: config.type || "success",
        title: config.title || "Alert",
        message: config.message || "",
      };
      showAlertModal.value = true;
    };

    const handleAlertModalClose = () => {
      showAlertModal.value = false;
    };

    const openInfoModal = () => {
      showInfoModal.value = true;
    };

    const closeInfoModal = () => {
      showInfoModal.value = false;
    };

    const toggleSecretKey = () => {
      showSecretKey.value = !showSecretKey.value;
    };

    const handleSecretKeyFocus = (event) => {
      const input = event.target;
      if (input.type === "password") {
        input.setAttribute("readonly", "readonly");
        setTimeout(() => {
          input.removeAttribute("readonly");
        }, 100);
      }
    };

    onMounted(() => {
      // Load config on mount to show status in card
      loadConfig();

      checkSyncStatus();
      // Start polling sync status every 2 seconds
      syncStatusInterval = setInterval(checkSyncStatus, 2000);
    });

    onUnmounted(() => {
      // Cleanup interval on unmount
      if (syncStatusInterval) {
        clearInterval(syncStatusInterval);
        syncStatusInterval = null;
      }
    });

    const getSyncModeLabel = (mode) => {
      const option = syncModeOptions.find((opt) => opt.value === mode);
      return option ? option.label : "Bidirectional";
    };

    const syncVaultspaces = async () => {
      if (syncing.value) return;

      syncing.value = true;
      try {
        // Use selected sync mode (default: "bidirectional")
        await admin.syncExternalStorage(
          selectedSyncMode.value || "bidirectional",
        );
        // Start polling sync status every 2 seconds
        if (syncStatusInterval) {
          clearInterval(syncStatusInterval);
        }
        syncStatusInterval = setInterval(checkSyncStatus, 2000);
        // No popup - synchronization runs in background
        // User can leave the page, sync will continue
      } catch (err) {
        // Only show error popup if sync failed to start
        showAlert({
          type: "error",
          title: "Synchronization Failed",
          message: err.message || "Failed to start synchronization",
        });
        syncing.value = false; // Re-enable button on error
        if (syncStatusInterval) {
          clearInterval(syncStatusInterval);
          syncStatusInterval = null;
        }
      }
    };

    return {
      loading,
      error,
      saving,
      testing,
      testSuccessful,
      config,
      testResult,
      saveResult,
      showModal,
      showAlertModal,
      alertModalConfig,
      syncing,
      selectedSyncMode,
      s3LogoPath,
      storageModeOptions,
      syncModeOptions,
      loadConfig,
      onStorageModeChange,
      testConnection,
      saveConfig,
      getIcon,
      openModal,
      closeModal,
      getStatusText,
      showAlert,
      handleAlertModalClose,
      syncVaultspaces,
      getSyncModeLabel,
      showInfoModal,
      openInfoModal,
      closeInfoModal,
      showSecretKey,
      toggleSecretKey,
      handleSecretKeyFocus,
    };
  },
};
</script>

<style scoped>
.external-storage-config {
  width: 100%;
}

.integration-card {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem;

  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid var(--border-color);
  min-height: 120px; /* Ensure minimum height for consistency */
}

@media (min-width: 769px) {
  .integration-card {
    box-sizing: border-box;
  }

  .integration-content {
    justify-content: center; /* Center content vertically */
  }
}

.integration-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  border-color: var(--slate-grey);
}

.integration-logo {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);

  padding: 0.75rem;
}

.integration-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.integration-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.integration-content h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.25rem;
  font-weight: 600;
}

.integration-description {
  margin: 0;
  color: var(--text-primary);
  font-size: 0.9rem;
  line-height: 1.5;
}

.integration-status {
  margin-top: 0.5rem;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;

  font-size: 0.85rem;
  font-weight: 500;
}

.status-badge.active {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-badge.inactive {
  background: var(--accent);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.integration-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-shrink: 0;
  padding-right: 0.5rem;
  padding-top: 2px;
  overflow: visible;
}

.integration-arrow {
  flex-shrink: 0;
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.integration-card:hover .integration-arrow {
  color: var(--text-primary);
  transform: translateX(4px);
}

.sync-controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 1;
  min-width: 0;
  max-width: 100%;
  padding-top: 2px;
  overflow: visible;
}

.sync-mode-select-wrapper {
  flex-shrink: 1;
  min-width: 0;
}

.sync-mode-select {
  min-width: 140px;
  max-width: 160px;
  flex-shrink: 1;
  position: relative;
  z-index: 1;
}

.sync-mode-select :deep(.custom-select-trigger-sm) {
  min-height: 2.5rem;
  height: 2.5rem;
  padding: 0.5rem 1rem;
  padding-right: 1.75rem;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
}

.sync-mode-select:hover :deep(.custom-select-trigger-sm) {
  z-index: 2;
}

.btn-sync-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.625rem;
  min-width: 2.5rem;
  width: 2.5rem;
  min-height: 2.5rem;
  height: 2.5rem;
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);

  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
}

.btn-sync-trigger:hover:not(:disabled) {
  background: var(--bg-primary);
  border-color: var(--slate-grey);
  transform: translateY(-1px);
  z-index: 2;
}

.btn-sync-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sync-trigger span {
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-info {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.625rem;
  padding-right: 0rem;
  min-width: 2.5rem;
  width: 2.5rem;
  min-height: 2.5rem;
  height: 2.5rem;
  color: var(--ash-grey);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
}

.btn-info:hover {
  color: var(--text-primary);
  transform: translateY(-1px);
  z-index: 2;
}

.btn-info span {
  display: flex;
  align-items: center;
  justify-content: center;
}

.info-modal-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.sync-mode-explanation {
  padding: 1rem;
  background: var(--bg-primary);

  border-left: 3px solid var(--accent);
}

.sync-mode-explanation h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 600;
}

.sync-mode-explanation p {
  margin: 0;
  color: var(--text-primary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.info-modal-footer {
  margin-top: 0.5rem;
  padding: 1rem;
  background: var(--bg-primary);

  border: 1px solid var(--slate-grey);
}

.info-modal-footer p {
  margin: 0;
  color: var(--text-primary);
  font-size: 0.9rem;
  line-height: 1.6;
}

.info-modal-footer strong {
  color: var(--text-primary);
}

/* Modal styles use global .modal-overlay and .modal from vault.css */

.modal-wide {
  width: 90%;
  overflow-y: visible;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
  width: 100%;
  flex-shrink: 0;
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.modal-logo {
  width: 40px;
  height: 40px;
  object-fit: contain;
}

.modal-title h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.5;
}

.modal-close-btn {
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;

  transition: all 0.2s ease;
}

.modal-close-btn:hover {
  background: var(--accent);
  color: var(--text-primary);
}

.modal-body {
  padding: 0.5rem;
  width: 100%;
  flex: 1;
  overflow-y: auto;
}

.config-card {
  padding: 0;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
  box-sizing: border-box;
}

.s3-config-section {
  padding: 1.5rem;
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);
}

.s3-config-section h3 {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1.1rem;
  font-weight: 600;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.form-group label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 500;
}

.form-input,
.form-select {
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);

  padding: 0.75rem;
  color: var(--text-primary);
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(0, 66, 37, 0.1);
}

.form-checkbox {
  margin-right: 0.5rem;
}

.toggle-group {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.toggle-label {
  color: var(--text-primary);
  font-size: 0.9rem;
  font-weight: 500;
  margin: 0;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 48px;
  height: 24px;
  cursor: pointer;
  flex-shrink: 0;
}

.toggle-input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 66, 37, 0.3);
  border: 1px solid var(--border-color);

  transition: all 0.3s ease;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background-color: #a9b7aa;

  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.toggle-input:checked + .toggle-slider {
  background: var(--accent);
  border-color: var(--accent);
}

.toggle-input:checked + .toggle-slider:before {
  transform: translateX(24px);
}

.toggle-input:focus + .toggle-slider {
  box-shadow: 0 0 0 3px rgba(0, 66, 37, 0.1);
}

.toggle-switch:hover .toggle-slider {
  border-color: var(--border-color);
}

.toggle-switch:hover .toggle-input:checked + .toggle-slider {
  border-color: var(--accent);
}

.form-help {
  color: var(--text-primary);
  font-size: 0.85rem;
  margin-top: 0.25rem;
}

.form-help ul {
  margin: 0.5rem 0 0 0;
  padding-left: 1.5rem;
}

.form-help li {
  margin: 0.25rem 0;
}

.secret-key-input-wrapper {
  position: relative;
  display: block;
  width: 100%;
}

.secret-key-input {
  padding-right: 2.5rem !important;
  width: 100%;
  box-sizing: border-box;
}

.secret-key-toggle {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  margin-top: -12px;
  height: 24px;
  width: 24px;
  background: transparent;
  border: none;
  color: var(--ash-grey);
  opacity: 0.7;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    opacity 0.2s ease,
    color 0.2s ease;
  z-index: 10;
  box-sizing: border-box;
  line-height: 1;
  vertical-align: baseline;
}

.secret-key-toggle:hover:not(:disabled) {
  opacity: 1;
  color: var(--ash-grey);
}

.secret-key-toggle:active:not(:disabled) {
  opacity: 0.8;
}

.secret-key-toggle:focus {
  outline: none;
}

.secret-key-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secret-key-toggle-icon {
  display: block;
  width: 18px;
  height: 18px;
}

.secret-key-toggle-icon--show {
  display: none;
}

.secret-key-toggle.is-visible .secret-key-toggle-icon--hide {
  display: none;
}

.secret-key-toggle.is-visible .secret-key-toggle-icon--show {
  display: block;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  margin-top: 2rem;
}

.save-actions {
  display: flex;
  gap: 0.75rem;
}

.test-connection-wrapper {
  flex: 1;
}

.btn {
  padding: 0.75rem 1.5rem;

  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-primary {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--text-primary);
}

.btn-primary:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.1);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.btn-secondary {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--slate-grey);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-primary);
  border-color: var(--slate-grey);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.test-result {
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.save-result {
  padding: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1rem;
}

.test-result.success,
.save-result.success {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.test-result.error,
.save-result.error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  color: #f87171;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

/* Mobile responsive styles */
@media (max-width: 768px) {
  .integration-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 1rem;
    padding: 1rem;
  }

  .integration-logo {
    width: 48px;
    height: 48px;
  }

  .integration-content {
    align-items: center;
    text-align: center;
    width: 100%;
  }

  .integration-content h3 {
    font-size: 1.1rem;
  }

  .integration-description {
    font-size: 0.85rem;
  }

  .integration-status {
    margin-top: 0.75rem;
  }

  .integration-actions {
    flex-direction: column;
    width: 100%;
    gap: 0.75rem;
    padding-right: 0;
    align-items: stretch;
  }

  .integration-arrow {
    display: none;
  }

  .sync-controls {
    width: 100%;
    flex-direction: row;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .sync-mode-select {
    flex: 1;
    min-width: 0;
    max-width: 100%;
  }

  .btn-info,
  .btn-sync-trigger {
    flex-shrink: 0;
  }
}
</style>
