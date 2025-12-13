<template>
  <div class="database-backup-config">
    <div class="integration-card glass glass-card" @click="openModal">
      <div class="integration-logo">
        <img :src="dbLogoPath" alt="Database Backup" />
      </div>
      <div class="integration-content">
        <h3>Database Backup</h3>
        <p class="integration-description">
          Configure automated database backups with scheduling, retention
          policies, and remote database support.
        </p>
        <div class="integration-status" v-if="config">
          <span
            class="status-badge"
            :class="
              config.enabled &&
              config.cron_expression &&
              config.cron_expression.trim() !== ''
                ? 'active'
                : 'inactive'
            "
          >
            {{ getStatusText() }}
          </span>
        </div>
      </div>
    </div>

    <!-- Configuration Modal -->
    <teleport to="body">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal glass glass-card modal-wide" @click.stop>
          <div class="modal-header">
            <div class="modal-title">
              <img :src="dbLogoPath" alt="Database Backup" class="modal-logo" />
              <h3>Database Backup Configuration</h3>
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
            <div v-else class="config-tabs">
              <!-- Tabs -->
              <div class="tabs-header" ref="tabsContainer">
                <button
                  :ref="(el) => setTabRef(el, 'configuration')"
                  @click="activeTab = 'configuration'"
                  :class="[
                    'tab-button',
                    { active: activeTab === 'configuration' },
                  ]"
                >
                  Configuration
                </button>
                <button
                  :ref="(el) => setTabRef(el, 'history')"
                  @click="activeTab = 'history'"
                  :class="['tab-button', { active: activeTab === 'history' }]"
                >
                  Backups List
                </button>
                <button
                  :ref="(el) => setTabRef(el, 'actions')"
                  @click="activeTab = 'actions'"
                  :class="['tab-button', { active: activeTab === 'actions' }]"
                >
                  Actions
                </button>
                <div
                  class="tab-indicator"
                  ref="indicator"
                  :style="indicatorStyle"
                ></div>
              </div>

              <!-- Configuration Tab -->
              <div v-if="activeTab === 'configuration'" class="tab-content">
                <form @submit.prevent="saveConfig" class="config-form">
                  <div class="form-group">
                    <div class="toggle-group">
                      <label class="toggle-label">Enable Database Backup</label>
                      <label class="toggle-switch">
                        <input
                          v-model="config.enabled"
                          type="checkbox"
                          class="toggle-input"
                        />
                        <span class="toggle-slider"></span>
                      </label>
                    </div>
                  </div>

                  <div v-if="config.enabled" class="config-section">
                    <h4>Schedule</h4>
                    <div class="form-group">
                      <label>Cron Expression:</label>
                      <input
                        v-model="config.cron_expression"
                        type="text"
                        placeholder="0 2 * * * (daily at 2 AM)"
                        class="form-input"
                      />
                      <div class="form-help">
                        Cron expression for backup schedule. Examples:
                        <ul>
                          <li><code>0 2 * * *</code> - Daily at 2 AM</li>
                          <li><code>0 3 * * 1</code> - Every Monday at 3 AM</li>
                          <li>
                            <code>0 0 1 * *</code> - First day of month at
                            midnight
                          </li>
                        </ul>
                      </div>
                    </div>

                    <h4>Storage</h4>
                    <div class="form-group">
                      <label>Storage Type:</label>
                      <CustomSelect
                        v-model="config.storage_type"
                        :options="storageTypeOptions"
                        placeholder="Select storage type"
                      />
                      <div class="form-help">
                        <ul>
                          <li>
                            <strong>Local:</strong> Store backups on local
                            filesystem
                          </li>
                          <li>
                            <strong>S3:</strong> Store backups in S3 (requires
                            S3 configuration)
                          </li>
                          <li>
                            <strong>Both:</strong> Store backups both locally
                            and in S3 (requires S3 configuration)
                          </li>
                        </ul>
                      </div>
                    </div>

                    <h4>Retention Policy</h4>
                    <div class="form-group">
                      <label>Retention Type:</label>
                      <CustomSelect
                        v-model="retentionType"
                        :options="retentionTypeOptions"
                        placeholder="Select retention type"
                      />
                    </div>
                    <div class="form-group">
                      <label>Retention Value:</label>
                      <input
                        v-model.number="retentionValue"
                        type="number"
                        min="1"
                        class="form-input"
                      />
                      <div class="form-help">
                        <span v-if="retentionType === 'count'"
                          >Number of backups to keep</span
                        >
                        <span v-else>Number of days to keep backups</span>
                      </div>
                    </div>
                  </div>

                  <div class="form-actions">
                    <button
                      type="submit"
                      class="btn-primary"
                      :disabled="saving"
                    >
                      {{ saving ? "Saving..." : "Save Configuration" }}
                    </button>
                  </div>

                  <div
                    v-if="saveResult"
                    class="save-result"
                    :class="saveResult.success ? 'success' : 'error'"
                  >
                    <span
                      v-html="
                        getIcon(saveResult.success ? 'check' : 'warning', 16)
                      "
                    ></span>
                    {{ saveResult.message }}
                  </div>
                </form>
              </div>

              <!-- History Tab -->
              <div v-if="activeTab === 'history'" class="tab-content">
                <div v-if="loadingBackups" class="loading">
                  <span v-html="getIcon('clock', 24)"></span>
                  Loading backups...
                </div>
                <div v-else-if="backupsError" class="error">
                  {{ backupsError }}
                </div>
                <div v-else-if="backups.length === 0" class="empty-state">
                  <span v-html="getIcon('database', 48)"></span>
                  <p>No backups found</p>
                </div>
                <div v-else class="backups-list">
                  <div class="backups-count-info">
                    <span v-html="getIcon('info', 16)"></span>
                    <span>
                      {{ dedupedBackups.length }}
                      {{ dedupedBackups.length === 1 ? "backup" : "backups" }}
                      found
                    </span>
                  </div>
                  <div
                    v-for="backup in dedupedBackups"
                    :key="backup.id"
                    class="backup-item"
                  >
                    <div class="backup-info">
                      <div class="backup-header">
                        <span class="backup-type">{{
                          backup.backup_type
                        }}</span>
                        <span
                          :class="['backup-status', `status-${backup.status}`]"
                        >
                          {{ formatStatus(backup.status) }}
                        </span>
                        <span
                          v-if="backup.storageTargets"
                          class="storage-badge"
                        >
                          {{ getStorageLabel(backup.storageTargets) }}
                        </span>
                      </div>
                      <div class="backup-details">
                        <div>Created: {{ formatDate(backup.created_at) }}</div>
                        <div>Size: {{ formatSize(backup.size_bytes) }}</div>
                        <div v-if="backup.checksum" class="checksum-display">
                          <span class="checksum-label">SHA256:</span>
                          <code class="checksum-value">{{
                            backup.checksum
                          }}</code>
                        </div>
                      </div>
                    </div>
                    <div class="backup-actions">
                      <button
                        @click="deleteBackup(backup.id)"
                        class="btn-danger btn-small"
                        :disabled="deletingBackup === backup.id"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Actions Tab -->
              <div v-if="activeTab === 'actions'" class="tab-content">
                <div class="actions-section">
                  <h4>Manual Backup</h4>
                  <p>Create a backup of the database immediately.</p>
                  <div class="backup-controls">
                    <CustomSelect
                      v-model="manualBackupStorage"
                      :options="manualBackupStorageOptions"
                      placeholder="Select storage"
                      :disabled="backupRunning"
                      class="backup-storage-select"
                    />
                    <button
                      @click="createManualBackup"
                      class="btn-primary"
                      :disabled="backupRunning"
                    >
                      {{
                        backupRunning
                          ? "Backup in progress..."
                          : "Create Backup"
                      }}
                    </button>
                  </div>
                </div>

                <div class="actions-section">
                  <h4>Restore from Backup</h4>
                  <p>
                    Restore the database from a previous backup. The application
                    will be put in maintenance mode during restoration.
                  </p>
                  <div class="form-group">
                    <label>Select Backup:</label>
                    <CustomSelect
                      v-model="selectedBackupId"
                      :options="backupOptions"
                      placeholder="Select a backup to restore"
                      :disabled="restoreRunning"
                    />
                  </div>
                  <button
                    @click="restoreBackup"
                    class="btn-warning restore-btn"
                    :disabled="!selectedBackupId || restoreRunning"
                  >
                    {{ restoreRunning ? "Restoring..." : "Restore Backup" }}
                  </button>
                  <div v-if="restoreRunning" class="form-help">
                    <strong>Warning:</strong> The application is in maintenance
                    mode. Do not close this page.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Alert Modal -->
    <AlertModal
      :show="showAlertModal"
      :type="alertModalConfig.type"
      :title="alertModalConfig.title"
      :message="alertModalConfig.message"
      @close="handleAlertModalClose"
      @ok="handleAlertModalClose"
    />

    <!-- Maintenance Modal -->
    <MaintenanceModal />
  </div>
</template>

<script>
import { ref, onMounted, computed, watch, nextTick, onUnmounted } from "vue";
import { admin, config as configApi } from "../../services/api";
import CustomSelect from "../CustomSelect.vue";
import AlertModal from "../AlertModal.vue";
import MaintenanceModal from "../MaintenanceModal.vue";
import { useHealthCheck } from "../../composables/useHealthCheck";

export default {
  name: "DatabaseBackupConfig",
  components: {
    CustomSelect,
    AlertModal,
    MaintenanceModal,
  },
  setup() {
    const loading = ref(true);
    const error = ref(null);
    const saving = ref(false);
    const showModal = ref(false);
    const activeTab = ref("configuration");
    const loadingBackups = ref(false);
    const backupsError = ref(null);
    const backups = ref([]);
    const inferStorageTargets = (backup) => {
      const metadata = backup.metadata || {};
      // First check metadata.storage.type (correct location in metadata.json)
      // Fallback to metadata.storage_type for backward compatibility
      const storageType =
        metadata.storage?.type || metadata.storage_type || null;
      const location = backup.storage_location || "";

      const hasS3Location =
        location.startsWith("s3://") ||
        !!metadata.storage?.s3_location ||
        !!metadata.s3_location;
      const hasLocalLocation = !!location && !location.startsWith("s3://");

      const isBoth = storageType === "both";
      const hasS3 = isBoth || storageType === "s3" || hasS3Location;
      const hasLocal = isBoth || storageType === "local" || hasLocalLocation;

      return {
        local: hasLocal,
        s3: hasS3,
      };
    };

    const dedupedBackups = computed(() => {
      const statusPriority = {
        completed: 3,
        running: 2,
        pending: 1,
        failed: 0,
      };

      const groups = new Map();

      for (const backup of backups.value || []) {
        const key = backup.checksum || backup.id;
        const createdTs = backup.created_at
          ? Date.parse(backup.created_at) || 0
          : 0;
        const storageTargets = inferStorageTargets(backup);

        if (!groups.has(key)) {
          groups.set(key, { ...backup, storageTargets, _ts: createdTs });
          continue;
        }

        const existing = groups.get(key);
        const mergedTargets = {
          local: existing.storageTargets?.local || storageTargets.local,
          s3: existing.storageTargets?.s3 || storageTargets.s3,
        };

        const existingPriority = statusPriority[existing.status] ?? -1;
        const newPriority = statusPriority[backup.status] ?? -1;

        const shouldReplace =
          newPriority > existingPriority ||
          (newPriority === existingPriority && createdTs > (existing._ts || 0));

        if (shouldReplace) {
          groups.set(key, {
            ...backup,
            storageTargets: mergedTargets,
            _ts: createdTs,
          });
        } else {
          groups.set(key, { ...existing, storageTargets: mergedTargets });
        }
      }

      return Array.from(groups.values()).map(({ _ts, ...rest }) => rest);
    });
    // Use health check stream for restore status
    const {
      restoreRunning: streamRestoreRunning,
      restoreError: streamRestoreError,
    } = useHealthCheck();

    const deletingBackup = ref(null);
    const backupRunning = ref(false);
    const restoreRunning = ref(false);
    const selectedBackupId = ref(null);
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "success",
      title: "Success",
      message: "",
    });
    const saveResult = ref(null);

    // Tab indicator refs and state
    const tabsContainer = ref(null);
    const indicator = ref(null);
    const tabRefs = ref({});
    const indicatorStyle = ref({
      left: "0px",
      width: "0px",
    });

    // Store the logo path in a variable to avoid Vite treating it as a module import
    const dbLogoPath = "/static/icons/database-backup.png";

    const config = ref({
      enabled: false,
      cron_expression: "",
      storage_type: "local",
      retention_policy: { type: "count", value: 10 },
    });

    const retentionType = ref("count");
    const retentionValue = ref(10);

    // Manual backup storage selection
    const manualBackupStorage = ref("local");
    const manualBackupStorageOptions = [
      { label: "Local", value: "local" },
      { label: "S3", value: "s3" },
      { label: "Both", value: "both" },
    ];

    const storageTypeOptions = [
      { label: "Local", value: "local" },
      { label: "S3", value: "s3" },
      { label: "Both", value: "both" },
    ];

    const retentionTypeOptions = [
      { label: "Count", value: "count" },
      { label: "Days", value: "days" },
    ];

    // Declare timezone before using it in computed
    const timezone = ref("UTC");

    const backupOptions = computed(() => {
      // Include timezone.value in the computed to make it reactive
      // Access timezone.value directly to ensure reactivity
      const tz = timezone.value;
      return backups.value
        .filter((b) => b.status === "completed")
        .map((b) => ({
          label: `${formatDate(b.created_at)} - ${formatSize(b.size_bytes)}`,
          value: b.id,
        }));
    });

    const loadConfig = async () => {
      loading.value = true;
      error.value = null;
      try {
        // Load timezone from config if not already loaded
        await loadTimezone();

        const response = await admin.getDatabaseBackupConfig();
        config.value = {
          enabled: response.enabled || false,
          cron_expression: response.cron_expression || "",
          storage_type: response.storage_type || "local",
          retention_policy: response.retention_policy || {
            type: "count",
            value: 10,
          },
        };

        if (response.retention_policy) {
          retentionType.value = response.retention_policy.type || "count";
          retentionValue.value = response.retention_policy.value || 10;
        }
      } catch (err) {
        error.value = err.message || "Failed to load configuration";
      } finally {
        loading.value = false;
      }
    };

    const loadTimezone = async () => {
      if (timezone.value === "UTC") {
        try {
          if (configApi && typeof configApi.getConfig === "function") {
            const configData = await configApi.getConfig();
            if (configData.timezone) {
              timezone.value = configData.timezone;
            }
          } else {
            // Fallback to direct fetch if configApi is not available
            const response = await fetch("/api/v2/config", {
              method: "GET",
              credentials: "same-origin",
            });
            if (response.ok) {
              const configData = await response.json();
              if (configData.timezone) {
                timezone.value = configData.timezone;
              }
            }
          }
        } catch (err) {
          // Use UTC as default if config fails
        }
      }
    };

    const loadBackups = async () => {
      loadingBackups.value = true;
      backupsError.value = null;
      try {
        // Ensure timezone is loaded before formatting dates
        await loadTimezone();
        const response = await admin.listDatabaseBackups();
        backups.value = response.backups || [];
      } catch (err) {
        backupsError.value = err.message || "Failed to load backups";
      } finally {
        loadingBackups.value = false;
      }
    };

    const saveConfig = async () => {
      saving.value = true;
      saveResult.value = null;

      try {
        const configToSave = {
          enabled: config.value.enabled,
          cron_expression: config.value.cron_expression,
          storage_type: config.value.storage_type,
          retention_policy: {
            type: retentionType.value,
            value: retentionValue.value,
          },
        };

        await admin.saveDatabaseBackupConfig(configToSave);

        // Reload config to get updated values
        await loadConfig();

        // Close modal immediately on success
        await closeModal();

        // Show success alert modal after modal closes
        // Use nextTick to ensure modal is fully closed before showing alert
        await nextTick();
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

    const createManualBackup = async () => {
      if (backupRunning.value) return;

      backupRunning.value = true;
      try {
        await admin.createDatabaseBackup({
          storage_type: manualBackupStorage.value,
        });
        showAlert({
          type: "success",
          title: "Backup Started",
          message: "Database backup has been started in the background.",
        });
        // Reload backups after a delay
        setTimeout(() => {
          loadBackups();
        }, 2000);
      } catch (err) {
        showAlert({
          type: "error",
          title: "Backup Failed",
          message: err.message || "Failed to start backup",
        });
      } finally {
        backupRunning.value = false;
      }
    };

    // Track previous restore running state to detect completion
    const previousRestoreRunning = ref(false);
    const hasStartedRestore = ref(false);

    // Sync local restoreRunning with stream data and detect completion
    watch(
      streamRestoreRunning,
      (newValue) => {
        const wasRunning = previousRestoreRunning.value;
        const isNowRunning = newValue;
        previousRestoreRunning.value = newValue;
        restoreRunning.value = newValue;

        // If we started a restore and stream confirms it's running, mark it
        if (hasStartedRestore.value && isNowRunning) {
          // Restore confirmed running via stream
        }

        // Detect restore completion: was running, now not running
        // Only trigger if we actually started a restore (to avoid false positives)
        if (hasStartedRestore.value && wasRunning && !isNowRunning) {
          hasStartedRestore.value = false;
          const error = streamRestoreError.value;
          if (error) {
            showAlert({
              type: "error",
              title: "Restore Failed",
              message: error || "Database restore failed",
            });
          } else {
            showAlert({
              type: "success",
              title: "Restore Completed",
              message:
                "Database restore completed successfully. The page will reload.",
            });
            // Reload page after a short delay to ensure restore is complete
            setTimeout(() => {
              window.location.reload();
            }, 2000);
          }
        }
      },
      { immediate: true },
    );

    // Also watch restoreError directly in case it changes while running
    watch(streamRestoreError, (error) => {
      // If there's an error and restore was running, it means restore failed
      if (error && restoreRunning.value && hasStartedRestore.value) {
        hasStartedRestore.value = false;
        restoreRunning.value = false;
        previousRestoreRunning.value = false;
        showAlert({
          type: "error",
          title: "Restore Failed",
          message: error || "Database restore failed",
        });
      }
    });

    const restoreBackup = async () => {
      if (!selectedBackupId.value || restoreRunning.value) return;

      if (
        !confirm(
          "Are you sure you want to restore from this backup? This will overwrite the current database.",
        )
      ) {
        return;
      }

      // Mark that we started a restore
      hasStartedRestore.value = true;
      // Initialize previousRestoreRunning to current stream value before starting
      previousRestoreRunning.value = streamRestoreRunning.value;
      restoreRunning.value = true;
      try {
        await admin.restoreDatabaseBackup(selectedBackupId.value);
        showAlert({
          type: "success",
          title: "Restore Started",
          message:
            "Database restore has been started. The application is now in maintenance mode.",
        });
        // Restore status will be updated via the healthz/stream
        // The watch will detect when streamRestoreRunning becomes true, then false
      } catch (err) {
        hasStartedRestore.value = false;
        showAlert({
          type: "error",
          title: "Restore Failed",
          message: err.message || "Failed to start restore",
        });
        restoreRunning.value = false;
        previousRestoreRunning.value = false;
      }
    };

    const deleteBackup = async (backupId) => {
      if (!confirm("Are you sure you want to delete this backup?")) {
        return;
      }

      deletingBackup.value = backupId;
      try {
        await admin.deleteDatabaseBackup(backupId);
        showAlert({
          type: "success",
          title: "Backup Deleted",
          message: "Backup has been deleted successfully.",
        });
        await loadBackups();
      } catch (err) {
        showAlert({
          type: "error",
          title: "Delete Failed",
          message: err.message || "Failed to delete backup",
        });
      } finally {
        deletingBackup.value = null;
      }
    };

    const openModal = async () => {
      showModal.value = true;
      // Load timezone first before any operations that use formatDate
      await loadTimezone();
      loadConfig();
      if (activeTab.value === "history" || activeTab.value === "actions") {
        loadBackups();
      }
      // Update indicator position when modal opens
      // Use double requestAnimationFrame to ensure DOM is fully rendered
      nextTick(() => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            updateIndicatorPosition();
          });
        });
      });
    };

    const closeModal = async () => {
      showModal.value = false;
      activeTab.value = "configuration";
      saveResult.value = null;

      // Reload config from server to ensure we have the true saved state
      await loadConfig();
    };

    watch(activeTab, async (newTab) => {
      if (newTab === "history" || newTab === "actions") {
        // Ensure timezone is loaded before loading backups
        await loadTimezone();
        loadBackups();
      }
    });

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

    const formatDate = (dateString) => {
      if (!dateString) return "Unknown";
      try {
        // Get current timezone value (ensure we have the latest value)
        const tz = timezone.value || "UTC";

        // Normalize the date string to ensure UTC interpretation
        let dateStr = String(dateString).trim();
        // Replace +00:00 with Z for better compatibility
        dateStr = dateStr.replace(/\+00:00$/, "Z");
        // If no timezone info, assume UTC
        if (!dateStr.endsWith("Z") && !dateStr.match(/[+-]\d{2}:\d{2}$/)) {
          dateStr = dateStr + "Z";
        }
        const date = new Date(dateStr);
        // Verify the date is valid
        if (isNaN(date.getTime())) {
          return "Invalid date";
        }
        // Format with the specified timezone
        return new Intl.DateTimeFormat("en-GB", {
          timeZone: tz,
          day: "2-digit",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }).format(date);
      } catch (err) {
        return "Invalid date";
      }
    };

    const formatSize = (bytes) => {
      if (!bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    };

    const getStorageLabel = (targets) => {
      if (targets?.local && targets?.s3) {
        return "Stored in: local & S3";
      }
      if (targets?.s3) {
        return "Stored in: S3";
      }
      return "Stored in: local";
    };

    const formatStatus = (status) => {
      if (status === "completed") {
        return "available";
      }
      return status;
    };

    const getStatusText = () => {
      if (!config.value) {
        return "Disabled";
      }
      // Check if backup is actually configured (enabled AND has cron_expression)
      const isConfigured =
        config.value.enabled &&
        config.value.cron_expression &&
        config.value.cron_expression.trim() !== "";
      return isConfigured ? "Enabled" : "Disabled";
    };

    const getIcon = (name, size = 24) => {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(name, size, "currentColor");
      }
      const iconFn = window.Icons[name];
      if (typeof iconFn === "function") {
        return iconFn.call(window.Icons, size, "currentColor");
      }
      return "";
    };

    const setTabRef = (el, tabId) => {
      if (el) {
        tabRefs.value[tabId] = el;
      }
    };

    const updateIndicatorPosition = () => {
      nextTick(() => {
        const activeTabElement = tabRefs.value[activeTab.value];
        if (!activeTabElement || !tabsContainer.value) {
          // If refs are not ready, try again after a short delay
          setTimeout(() => {
            updateIndicatorPosition();
          }, 50);
          return;
        }

        const containerRect = tabsContainer.value.getBoundingClientRect();
        const tabRect = activeTabElement.getBoundingClientRect();

        // Only update if we have valid dimensions
        if (containerRect.width > 0 && tabRect.width > 0) {
          const left = tabRect.left - containerRect.left;
          const width = tabRect.width;

          indicatorStyle.value = {
            left: `${left}px`,
            width: `${width}px`,
          };
        }
      });
    };

    // Watch for activeTab changes to update indicator position
    watch(activeTab, () => {
      updateIndicatorPosition();
    });

    // Watch for modal opening to update indicator position
    watch(showModal, (isOpen) => {
      if (isOpen) {
        // Use nextTick to ensure DOM is updated, then requestAnimationFrame for rendering
        nextTick(() => {
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              updateIndicatorPosition();
            });
          });
        });
      }
    });

    onMounted(async () => {
      // Load timezone first, before any other operations
      await loadTimezone();
      loadConfig();
      // Update indicator position after mounting
      setTimeout(() => {
        updateIndicatorPosition();
      }, 100);
    });

    return {
      loading,
      error,
      saving,
      showModal,
      activeTab,
      config,
      retentionType,
      retentionValue,
      storageTypeOptions,
      retentionTypeOptions,
      manualBackupStorage,
      manualBackupStorageOptions,
      loadingBackups,
      backupsError,
      backups,
      dedupedBackups,
      backupOptions,
      deletingBackup,
      backupRunning,
      restoreRunning,
      selectedBackupId,
      showAlertModal,
      alertModalConfig,
      saveResult,
      loadConfig,
      loadTimezone,
      saveConfig,
      createManualBackup,
      restoreBackup,
      deleteBackup,
      openModal,
      closeModal,
      showAlert,
      handleAlertModalClose,
      formatDate,
      formatSize,
      formatStatus,
      getStorageLabel,
      getIcon,
      getStatusText,
      dbLogoPath,
      tabsContainer,
      indicator,
      indicatorStyle,
      setTabRef,
    };
  },
};
</script>

<style scoped>
.database-backup-config {
  width: 100%;
}

.integration-card {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 1.5rem;
  border-radius: 1rem;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid rgba(148, 163, 184, 0.1);
  min-height: 120px; /* Ensure minimum height for consistency */
}

@media (min-width: 769px) {
  .integration-card {
    box-sizing: border-box;
  }

  .integration-content {
    justify-content: center; /* Center content vertically */
  }

  .integration-content h3 {
    white-space: nowrap; /* Prevent wrapping on desktop */
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.integration-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  border-color: rgba(96, 165, 250, 0.3);
}

.integration-logo {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 41, 59, 0.4);
  border-radius: 0.75rem;
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
  color: #e6eef6;
  font-size: 1.25rem;
  font-weight: 600;
}

.integration-description {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
  line-height: 1.5;
}

.integration-status {
  margin-top: 0.5rem;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.status-badge.active {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-badge.inactive {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
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
  color: #64748b;
  transition: all 0.2s ease;
}

.integration-card:hover .integration-arrow {
  color: #60a5fa;
  transform: translateX(4px);
}

.config-tabs {
  margin-top: 1rem;
}

.tabs-header {
  display: flex;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  position: relative;
  justify-content: center;
  align-items: center;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  margin-bottom: 1.5rem;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.3) transparent;
  width: 100%;
  box-sizing: border-box;
}

.tabs-header::-webkit-scrollbar {
  height: 6px;
}

.tabs-header::-webkit-scrollbar-track {
  background: transparent;
}

.tabs-header::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 3px;
}

.tabs-header::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.5);
}

.tab-button {
  background: transparent;
  border: none;
  color: #64748b;
  padding: 0.75rem 1.25rem;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;
  border-radius: 0.5rem;
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  flex-shrink: 0;
}

.tab-button:hover {
  color: #cbd5e1;
  background: rgba(255, 255, 255, 0.05);
}

.tab-button.active {
  color: #60a5fa;
  background: rgba(88, 166, 255, 0.1);
}

/* Liquid glass indicator */
.tab-indicator {
  position: absolute;
  bottom: 0;
  height: 2.5px;
  background: linear-gradient(
    90deg,
    rgba(96, 165, 250, 1),
    rgba(56, 189, 248, 1),
    rgba(96, 165, 250, 1)
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-radius: 999px;
  box-shadow:
    0 0 8px rgba(96, 165, 250, 0.6),
    0 0 16px rgba(56, 189, 248, 0.4),
    inset 0 1px 1px rgba(255, 255, 255, 0.3);
  transition:
    left 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
    width 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 2;
  pointer-events: none;
  will-change: left, width;
}

.tab-content {
  min-height: 300px;
}

.config-section {
  padding: 1.5rem;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.1);
  margin-bottom: 1.5rem;
}

.config-section h4 {
  margin: 0 0 1rem 0;
  color: #cbd5e1;
  font-size: 1.1rem;
  font-weight: 600;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group label {
  color: #cbd5e1;
  font-size: 0.9rem;
  font-weight: 500;
}

.form-input,
.form-select {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  padding: 0.75rem;
  color: #e6eef6;
  font-size: 0.95rem;
  transition: all 0.2s ease;
}

.form-input:focus,
.form-select:focus {
  outline: none;
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
}

.form-help {
  color: #94a3b8;
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

.form-help code {
  background: rgba(30, 41, 59, 0.5);
  padding: 0.125rem 0.375rem;
  border-radius: 3px;
  font-family: monospace;
  font-size: 0.85em;
  color: #cbd5e1;
}

.toggle-group {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.toggle-label {
  color: #cbd5e1;
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
  background-color: rgba(148, 163, 184, 0.3);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 24px;
  transition: all 0.3s ease;
}

.toggle-slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background-color: #e6eef6;
  border-radius: 50%;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.toggle-input:checked + .toggle-slider {
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  border-color: rgba(96, 165, 250, 0.5);
}

.toggle-input:checked + .toggle-slider:before {
  transform: translateX(24px);
}

.toggle-input:focus + .toggle-slider {
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
}

.toggle-switch:hover .toggle-slider {
  border-color: rgba(148, 163, 184, 0.4);
}

.toggle-switch:hover .toggle-input:checked + .toggle-slider {
  border-color: rgba(96, 165, 250, 0.7);
}

.form-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(96, 165, 250, 0.3);
}

.btn-secondary {
  background: rgba(30, 41, 59, 0.6);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(148, 163, 184, 0.4);
}

.btn-warning {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
}

.btn-warning:hover:not(:disabled) {
  background: linear-gradient(135deg, #d97706, #b45309);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
}

.btn-danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: linear-gradient(135deg, #dc2626, #b91c1c);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
}

.btn-small {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.backups-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.backups-count-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: #93c5fd;
}

.backups-count-info svg {
  flex-shrink: 0;
  margin-top: 0.3rem;
}

.backup-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: rgba(30, 41, 59, 0.3);
  border-radius: 0.5rem;
  border: 1px solid rgba(148, 163, 184, 0.1);
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
}

.backup-info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  max-width: 100%;
}

.backup-header {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
}

.backup-type {
  font-weight: 500;
  color: #cbd5e1;
  text-transform: capitalize;
}

.backup-status {
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.storage-badge {
  display: inline-block;
  padding: 0.25rem 0.65rem;
  border-radius: 0.5rem;
  font-size: 0.8rem;
  font-weight: 500;
  background: rgba(139, 92, 246, 0.15);
  color: #c4b5fd;
  border: 1px solid rgba(139, 92, 246, 0.35);
  white-space: nowrap;
  flex-shrink: 0;
}

.status-completed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-running {
  background: rgba(96, 165, 250, 0.15);
  color: #60a5fa;
  border: 1px solid rgba(96, 165, 250, 0.3);
}

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.status-pending {
  background: rgba(148, 163, 184, 0.15);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.backup-details {
  font-size: 0.85rem;
  color: #94a3b8;
  width: 100%;
  min-width: 0;
  overflow: hidden;
}

.backup-details div {
  margin: 0.25rem 0;
}

.checksum-display {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
  min-width: 0;
}

.checksum-label {
  font-weight: 500;
  color: #cbd5e1;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.checksum-value {
  display: block;
  font-family: "Courier New", monospace;
  font-size: 0.85rem;
  padding: 0.5rem;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.1);
  border-radius: 4px;
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  color: #cbd5e1;
  word-break: keep-all;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  min-width: 0;
  -webkit-overflow-scrolling: touch;
}

.backup-actions {
  display: flex;
  gap: 0.5rem;
}

.save-result {
  padding: 1rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1rem;
}

.save-result.success {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #10b981;
}

.save-result.error {
  background: rgba(239, 68, 68, 0.15);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #94a3b8;
}

.empty-state span {
  font-size: 4rem;
  display: block;
  margin-bottom: 1rem;
}

.actions-section {
  margin-bottom: 2rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
}

.actions-section:last-child {
  border-bottom: none;
}

.backup-controls {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-top: 1rem;
  width: fit-content;
  max-width: 45%;
}

.backup-storage-select {
  flex: 0 0 auto;
  width: 150px;
  min-width: 150px;
}

.actions-section h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.1rem;
  color: #cbd5e1;
  font-weight: 600;
}

.actions-section p {
  margin: 0 0 1rem 0;
  color: #94a3b8;
  font-size: 0.9rem;
  line-height: 1.5;
}

.restore-btn {
  margin-top: 1rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
}

.modal {
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  border-radius: 1rem;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
}

.modal-wide {
  max-width: 95vw;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
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
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.5;
}

.modal-close-btn {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.modal-close-btn:hover {
  background: rgba(148, 163, 184, 0.1);
  color: #e6eef6;
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

.loading,
.error {
  padding: 2rem;
  text-align: center;
  border-radius: 1rem;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: #94a3b8;
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.test-result,
.save-result {
  padding: 1rem;
  border-radius: 0.5rem;
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
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.success {
  color: #10b981;
}

.error {
  color: #f87171;
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

  .modal-overlay {
    padding: 1rem;
  }

  .modal-wide {
    max-width: 95vw;
  }

  .tabs-header {
    padding: 0.5rem 0.75rem;
    gap: 0.25rem;
    margin-bottom: 1rem;
    justify-content: flex-start;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
  }

  .tab-button {
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
    flex: 0 0 auto;
    min-width: fit-content;
    white-space: nowrap;
  }

  .backup-controls {
    flex-direction: row;
    align-items: center;
    gap: 0.75rem;
    max-width: 100%;
    width: fit-content;
  }

  .backup-storage-select {
    width: 130px;
    min-width: 130px;
    flex: 0 0 auto;
  }

  .checksum-value {
    font-size: 0.75rem;
    padding: 0.4rem;
  }

  .backup-header {
    flex-wrap: wrap;
    gap: 0.5rem;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .backup-info {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .storage-badge {
    padding: 0.3rem 0.75rem;
    font-size: 0.75rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .backup-type {
    font-size: 0.9rem;
  }

  .backup-status {
    font-size: 0.8rem;
    padding: 0.25rem 0.6rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .backup-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }

  .backup-actions {
    width: 100%;
    align-self: stretch;
  }

  .backup-actions .btn-danger {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .tabs-header {
    padding: 0.5rem 0.5rem;
    gap: 0.2rem;
  }

  .tab-button {
    padding: 0.5rem 0.6rem;
    font-size: 0.8rem;
  }

  .backup-header {
    gap: 0.4rem;
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .backup-info {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .storage-badge {
    padding: 0.25rem 0.6rem;
    font-size: 0.7rem;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .backup-type {
    font-size: 0.85rem;
  }

  .backup-status {
    font-size: 0.75rem;
    padding: 0.2rem 0.5rem;
  }

  .backup-item {
    padding: 0.75rem;
  }
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

.modal-overlay {
  padding: 1rem;
}

.modal-wide {
  max-width: 95vw;
}

.tabs-header {
  padding: 0.5rem 0.75rem;
  gap: 0.25rem;
  margin-bottom: 1rem;
}

.tab-button {
  padding: 0.5rem 0.5rem;
  font-size: 0.85rem;
  flex: 1;
  min-width: 0;
}

.backup-controls {
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
  max-width: 100%;
  width: fit-content;
}

.backup-storage-select {
  width: 130px;
  min-width: 130px;
  flex: 0 0 auto;
}
</style>
