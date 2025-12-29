<template>
  <div class="database-backup-config">
    <div class="integration-card" @click="openModal">
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
      <div class="integration-actions">
        <div class="backup-controls-card">
          <CustomSelect
            v-model="manualBackupStorage"
            :options="manualBackupStorageOptions"
            placeholder="Select storage"
            :disabled="backupRunning"
            size="small"
            class="backup-storage-select-card"
            @click.stop
          />
          <button
            @click.stop="createManualBackup"
            class="btn-backup-trigger"
            :disabled="backupRunning"
            :title="
              backupRunning ? 'Backup in progress...' : 'Create manual backup'
            "
          >
            <span
              v-html="getIcon(backupRunning ? 'clock' : 'database', 18)"
            ></span>
          </button>
        </div>
        <div class="integration-arrow">
          <span v-html="getIcon('arrow-right', 20)"></span>
        </div>
      </div>
    </div>

    <!-- Configuration Modal -->
    <Teleport v-if="showModal" to="body">
      <div class="modal-overlay" @click.self="closeModal">
        <div class="modal modal-wide" @click.stop>
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
                  Backups History
                </button>
                <button
                  :ref="(el) => setTabRef(el, 'restore')"
                  @click="activeTab = 'restore'"
                  :class="['tab-button', { active: activeTab === 'restore' }]"
                >
                  Restore
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
                        :value="config.cron_expression"
                        @input="handleCronInput"
                        type="text"
                        placeholder="0 2 * * * (daily at 2 AM)"
                        class="form-input"
                      />
                      <div v-if="isCronLoading" class="cron-status loading">
                        <span class="spinner-small"></span>
                        Calculating next run...
                      </div>
                      <div v-else-if="cronError" class="cron-status error">
                        {{ cronError }}
                      </div>
                      <div v-else-if="cronInfo" class="cron-status info">
                        {{ cronInfo }}
                      </div>
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
                      class="btn btn-primary"
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

              <!-- Restore Tab -->
              <div v-if="activeTab === 'restore'" class="tab-content">
                <div v-if="loadingBackups" class="loading">
                  <span v-html="getIcon('clock', 24)"></span>
                  Loading backups...
                </div>
                <div v-else-if="backupsError" class="error">
                  {{ backupsError }}
                </div>
                <div v-else class="restore-section">
                  <div class="restore-header">
                    <h4>Restore from Backup</h4>
                    <p>
                      Restore the database from a previous backup. The
                      application will be put in maintenance mode during
                      restoration.
                    </p>
                  </div>

                  <!-- Search and Filters -->
                  <div class="restore-filters">
                    <div class="filter-row">
                      <div class="filter-group">
                        <label>Search:</label>
                        <input
                          v-model="restoreSearchQuery"
                          type="text"
                          placeholder="Search by date, ID, or location..."
                          class="form-input filter-input"
                          @input="restorePage = 1"
                        />
                      </div>
                      <div class="filter-group">
                        <label>Type:</label>
                        <CustomSelect
                          v-model="restoreFilters.type"
                          :options="backupTypeFilterOptions"
                          placeholder="All types"
                          @change="restorePage = 1"
                        />
                      </div>
                      <div class="filter-group">
                        <label>Status:</label>
                        <CustomSelect
                          v-model="restoreFilters.status"
                          :options="backupStatusFilterOptions"
                          placeholder="All statuses"
                          @change="restorePage = 1"
                        />
                      </div>
                      <div class="filter-group">
                        <label>Storage:</label>
                        <CustomSelect
                          v-model="restoreFilters.storage"
                          :options="backupStorageFilterOptions"
                          placeholder="All storage"
                          @change="restorePage = 1"
                        />
                      </div>
                    </div>
                  </div>

                  <!-- Backups Table -->
                  <div class="restore-table-container">
                    <table class="restore-table">
                      <thead>
                        <tr>
                          <th class="col-select"></th>
                          <th
                            class="col-date sortable"
                            @click="sortBackups('created_at')"
                          >
                            Date
                            <span
                              v-if="restoreSortBy === 'created_at'"
                              class="sort-indicator"
                            >
                              {{ restoreSortOrder === "asc" ? "↑" : "↓" }}
                            </span>
                          </th>
                          <th class="col-type">Type</th>
                          <th class="col-status">Status</th>
                          <th
                            class="col-size sortable"
                            @click="sortBackups('size_bytes')"
                          >
                            Size
                            <span
                              v-if="restoreSortBy === 'size_bytes'"
                              class="sort-indicator"
                            >
                              {{ restoreSortOrder === "asc" ? "↑" : "↓" }}
                            </span>
                          </th>
                          <th class="col-storage">Storage</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-if="paginatedBackups.length === 0"
                          class="empty-row"
                        >
                          <td colspan="6" class="text-center">
                            No backups found matching your criteria
                          </td>
                        </tr>
                        <tr
                          v-for="backup in paginatedBackups"
                          :key="backup.id"
                          :class="{
                            'row-selected': selectedBackupId === backup.id,
                            'row-disabled': backup.status !== 'completed',
                          }"
                          @click="
                            backup.status === 'completed' &&
                              selectBackupForRestore(backup.id)
                          "
                        >
                          <td class="col-select">
                            <input
                              type="radio"
                              :checked="selectedBackupId === backup.id"
                              :disabled="backup.status !== 'completed'"
                              @click.stop="
                                backup.status === 'completed' &&
                                  selectBackupForRestore(backup.id)
                              "
                            />
                          </td>
                          <td class="col-date">
                            {{ formatDate(backup.created_at) }}
                          </td>
                          <td class="col-type">
                            <span class="backup-type-badge">{{
                              backup.backup_type
                            }}</span>
                          </td>
                          <td class="col-status">
                            <span
                              :class="[
                                'backup-status-badge',
                                `status-${backup.status}`,
                              ]"
                            >
                              {{ formatStatus(backup.status) }}
                            </span>
                          </td>
                          <td class="col-size">
                            {{ formatSize(backup.size_bytes) }}
                          </td>
                          <td class="col-storage">
                            <span
                              v-if="backup.storageTargets"
                              class="storage-badge-small"
                            >
                              {{ getStorageLabelShort(backup.storageTargets) }}
                            </span>
                            <span v-else class="storage-badge-small">
                              {{ inferStorageType(backup) }}
                            </span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>

                  <!-- Pagination -->
                  <div class="restore-pagination">
                    <div class="pagination-info">
                      <span>
                        Showing
                        {{ (restorePage - 1) * restorePageSize + 1 }} to
                        {{
                          Math.min(
                            restorePage * restorePageSize,
                            filteredAndSortedBackups.length,
                          )
                        }}
                        of {{ filteredAndSortedBackups.length }} backups
                      </span>
                      <div class="pagination-size">
                        <label>Per page:</label>
                        <CustomSelect
                          v-model="restorePageSize"
                          :options="pageSizeOptions"
                          @change="restorePage = 1"
                        />
                      </div>
                    </div>
                    <div class="pagination-controls">
                      <button
                        @click="restorePage = Math.max(1, restorePage - 1)"
                        :disabled="restorePage === 1"
                        class="btn btn-secondary btn-small"
                      >
                        Previous
                      </button>
                      <span class="page-numbers">
                        Page {{ restorePage }} of
                        {{ totalPages }}
                      </span>
                      <button
                        @click="
                          restorePage = Math.min(totalPages, restorePage + 1)
                        "
                        :disabled="restorePage >= totalPages"
                        class="btn btn-secondary btn-small"
                      >
                        Next
                      </button>
                    </div>
                  </div>

                  <!-- Restore Action -->
                  <div class="restore-actions">
                    <button
                      @click="restoreBackup"
                      class="btn btn-warning restore-btn"
                      :disabled="!selectedBackupId || restoreRunning"
                    >
                      {{ restoreRunning ? "Restoring..." : "Restore Backup" }}
                    </button>
                    <div v-if="restoreRunning" class="form-help">
                      <strong>Warning:</strong> The application is in
                      maintenance mode. Do not close this page.
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

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
import { admin, config as configApi, cron } from "../../services/api";
import CustomSelect from "../CustomSelect.vue";
import AlertModal from "../AlertModal.vue";
import MaintenanceModal from "../MaintenanceModal.vue";
import { useHealthCheck } from "../../composables/useHealthCheck";
import { debounce } from "../../utils/debounce";

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

    // Cron description state
    const cronInfo = ref(null);
    const cronError = ref(null);
    const isCronLoading = ref(false);

    // Cache for backups list
    const BACKUPS_CACHE_TTL = 120000; // 120 seconds
    const backupsCache = ref(null);
    const backupsCacheTimestamp = ref(null);

    // Timezone state
    const timezone = ref("UTC");

    // Indicator and Tab state
    const tabsContainer = ref(null);
    const indicator = ref(null);
    const tabRefs = ref({});
    const indicatorStyle = ref({
      left: "0px",
      width: "0px",
    });
    let resizeObserver = null;

    // Config state
    const config = ref({
      enabled: false,
      cron_expression: "",
      storage_type: "local",
      retention_policy: { type: "count", value: 10 },
    });

    const retentionType = ref("count");
    const retentionValue = ref(10);

    // Manual backup state
    const manualBackupStorage = ref("local");
    const manualBackupStorageOptions = [
      { label: "Local", value: "local" },
      { label: "S3", value: "s3" },
      { label: "Both", value: "both" },
    ];

    // Restore state
    const restoreSearchQuery = ref("");
    const restoreFilters = ref({
      type: "all",
      status: "completed",
      storage: "all",
    });
    const restoreSortBy = ref("created_at");
    const restoreSortOrder = ref("desc");
    const restorePage = ref(1);
    const restorePageSize = ref(5);
    const selectedBackupId = ref(null);
    const restoreRunning = ref(false);
    const previousRestoreRunning = ref(false);
    const hasStartedRestore = ref(false);

    // UI State
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "success",
      title: "Success",
      message: "",
    });
    const saveResult = ref(null);
    const deletingBackup = ref(null);
    const backupRunning = ref(false);

    // Constants
    const dbLogoPath = "/static/public/database-backup.png";
    const storageTypeOptions = [
      { label: "Local", value: "local" },
      { label: "S3", value: "s3" },
      { label: "Both", value: "both" },
    ];
    const retentionTypeOptions = [
      { label: "Count", value: "count" },
      { label: "Days", value: "days" },
    ];
    const backupTypeFilterOptions = [
      { label: "All types", value: "all" },
      { label: "Manual", value: "manual" },
      { label: "Scheduled", value: "scheduled" },
    ];
    const backupStatusFilterOptions = [
      { label: "All statuses", value: "all" },
      { label: "Completed", value: "completed" },
      { label: "Running", value: "running" },
      { label: "Pending", value: "pending" },
      { label: "Failed", value: "failed" },
    ];
    const backupStorageFilterOptions = [
      { label: "All storage", value: "all" },
      { label: "Local", value: "local" },
      { label: "S3", value: "s3" },
      { label: "Both", value: "both" },
    ];
    const pageSizeOptions = [
      { label: "5", value: 5 },
      { label: "10", value: 10 },
      { label: "25", value: 25 },
      { label: "50", value: 50 },
      { label: "100", value: 100 },
    ];

    // Helper functions (defined early)
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

    const inferStorageType = (backup) => {
      const storageTargets = inferStorageTargets(backup);
      if (storageTargets.local && storageTargets.s3) {
        return "Both";
      }
      if (storageTargets.s3) {
        return "S3";
      }
      return "Local";
    };

    const getStorageLabelShort = (targets) => {
      if (targets?.local && targets?.s3) {
        return "Both";
      }
      if (targets?.s3) {
        return "S3";
      }
      return "Local";
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

    const filteredAndSortedBackups = computed(() => {
      let filtered = [...backups.value];

      // Apply search filter
      if (restoreSearchQuery.value.trim()) {
        const query = restoreSearchQuery.value.toLowerCase().trim();
        filtered = filtered.filter((backup) => {
          const dateStr = formatDate(backup.created_at).toLowerCase();
          const idStr = backup.id.toLowerCase();
          const locationStr = (backup.storage_location || "").toLowerCase();
          return (
            dateStr.includes(query) ||
            idStr.includes(query) ||
            locationStr.includes(query)
          );
        });
      }

      // Apply type filter
      if (restoreFilters.value.type && restoreFilters.value.type !== "all") {
        filtered = filtered.filter(
          (backup) => backup.backup_type === restoreFilters.value.type,
        );
      }

      // Apply status filter
      if (
        restoreFilters.value.status &&
        restoreFilters.value.status !== "all"
      ) {
        filtered = filtered.filter(
          (backup) => backup.status === restoreFilters.value.status,
        );
      }

      // Apply storage filter
      if (
        restoreFilters.value.storage &&
        restoreFilters.value.storage !== "all"
      ) {
        filtered = filtered.filter((backup) => {
          const storageTargets = inferStorageTargets(backup);
          if (restoreFilters.value.storage === "both") {
            return storageTargets.local && storageTargets.s3;
          }
          if (restoreFilters.value.storage === "s3") {
            return storageTargets.s3 && !storageTargets.local;
          }
          if (restoreFilters.value.storage === "local") {
            return storageTargets.local && !storageTargets.s3;
          }
          return true;
        });
      }

      // Apply sorting
      filtered.sort((a, b) => {
        let aValue, bValue;

        if (restoreSortBy.value === "created_at") {
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
        } else if (restoreSortBy.value === "size_bytes") {
          aValue = a.size_bytes || 0;
          bValue = b.size_bytes || 0;
        } else {
          return 0;
        }

        if (restoreSortOrder.value === "asc") {
          return aValue - bValue;
        } else {
          return bValue - aValue;
        }
      });

      return filtered;
    });

    const totalPages = computed(() => {
      return Math.ceil(
        filteredAndSortedBackups.value.length / restorePageSize.value,
      );
    });

    const paginatedBackups = computed(() => {
      const start = (restorePage.value - 1) * restorePageSize.value;
      const end = start + restorePageSize.value;
      return filteredAndSortedBackups.value.slice(start, end);
    });

    const sortBackups = (field) => {
      if (restoreSortBy.value === field) {
        restoreSortOrder.value =
          restoreSortOrder.value === "asc" ? "desc" : "asc";
      } else {
        restoreSortBy.value = field;
        restoreSortOrder.value = "desc";
      }
      restorePage.value = 1;
    };

    const selectBackupForRestore = (backupId) => {
      selectedBackupId.value = backupId;
    };

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

        // Fetch cron description on load
        if (config.value.cron_expression) {
          fetchCronDescription(config.value.cron_expression);
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

    const invalidateBackupsCache = () => {
      backupsCache.value = null;
      backupsCacheTimestamp.value = null;
    };

    const addBackupToList = (backupData) => {
      backups.value = [backupData, ...backups.value];
    };

    const removeBackupFromList = (backupId) => {
      backups.value = backups.value.filter((b) => b.id !== backupId);
    };

    const handleCronInput = (event) => {
      let value = event.target.value;

      // Only allow: digits, *, /, -, , and space
      // Remove everything else
      value = value.replace(/[^0-9*\/\,\- ]/g, "");

      // Replace multiple spaces with a single space
      value = value.replace(/\s\s+/g, " ");

      // Update the reactive state
      if (config.value) {
        config.value.cron_expression = value;
      }

      // Ensure the input field matches the sanitized value
      event.target.value = value;
    };

    const fetchCronDescription = async (expression) => {
      if (!expression || expression.trim() === "") {
        cronInfo.value = null;
        cronError.value = null;
        return;
      }

      isCronLoading.value = true;
      cronError.value = null;
      try {
        const data = await cron.describe(expression);
        if (data && data.description) {
          cronInfo.value = data.description;
        } else {
          cronInfo.value = null;
        }
      } catch (err) {
        cronError.value = err.message;
        cronInfo.value = null;
      } finally {
        isCronLoading.value = false;
      }
    };

    const debouncedFetchCronDescription = debounce((expression) => {
      fetchCronDescription(expression);
    }, 500);

    const loadBackups = async () => {
      // Check if cache is valid
      const now = Date.now();
      if (
        backupsCache.value !== null &&
        backupsCacheTimestamp.value !== null &&
        now - backupsCacheTimestamp.value < BACKUPS_CACHE_TTL
      ) {
        // Use cached data
        backups.value = backupsCache.value;
        loadingBackups.value = false;
        return;
      }

      // Cache invalid or missing, fetch from API
      loadingBackups.value = true;
      backupsError.value = null;
      try {
        // Ensure timezone is loaded before formatting dates
        await loadTimezone();
        const response = await admin.listDatabaseBackups();
        const backupsList = response.backups || [];
        backups.value = backupsList;

        // Update cache
        backupsCache.value = backupsList;
        backupsCacheTimestamp.value = now;
      } catch (err) {
        backupsError.value = err.message || "Failed to load backups";
      } finally {
        loadingBackups.value = false;
      }
    };

    const saveConfig = async () => {
      // Validate cron expression before saving if enabled
      if (config.value.enabled) {
        const cronRegex =
          /^(\s*(\*|\d+)([\/,-](\*|\d+))*\s*)(\s+(\*|\d+)([\/,-](\*|\d+))*){0,4}$/;
        if (!cronRegex.test(config.value.cron_expression.trim())) {
          saveResult.value = {
            success: false,
            message: "Invalid cron syntax. Please correct it before saving.",
          };
          return;
        }
      }

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

        // Create temporary backup entry
        const tempBackup = {
          id: `temp-${Date.now()}`,
          backup_type: "manual",
          status: "running",
          storage_location:
            manualBackupStorage.value === "s3"
              ? "s3://"
              : manualBackupStorage.value === "both"
                ? "local & s3://"
                : "local",
          created_at: new Date().toISOString(),
          size_bytes: 0,
          metadata: {
            storage_type: manualBackupStorage.value,
          },
        };

        // Add to list immediately
        addBackupToList(tempBackup);

        // Invalidate cache so next load will fetch fresh data
        invalidateBackupsCache();

        showAlert({
          type: "success",
          title: "Backup Started",
          message: "Database backup has been started in the background.",
        });

        // Optionally refresh after delay to update temp entry with real data
        if (activeTab.value === "history" || activeTab.value === "restore") {
          setTimeout(() => {
            loadBackups();
          }, 5000);
        }
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

        // Remove from list immediately
        removeBackupFromList(backupId);

        // Invalidate cache
        invalidateBackupsCache();

        showAlert({
          type: "success",
          title: "Backup Deleted",
          message: "Backup has been deleted successfully.",
        });
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
      if (activeTab.value === "history" || activeTab.value === "restore") {
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
      if (newTab === "history" || newTab === "restore") {
        // Ensure timezone is loaded before loading backups
        await loadTimezone();
        loadBackups();
      }
    });

    // Reset pagination when filters change
    watch(
      [
        restoreSearchQuery,
        () => restoreFilters.value.type,
        () => restoreFilters.value.status,
        () => restoreFilters.value.storage,
      ],
      () => {
        restorePage.value = 1;
      },
    );

    // Ensure page is valid when page size changes
    watch(restorePageSize, () => {
      if (restorePage.value > totalPages.value) {
        restorePage.value = Math.max(1, totalPages.value);
      }
    });

    watch(
      () => config.value?.cron_expression,
      (newVal) => {
        debouncedFetchCronDescription(newVal);
      },
    );

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

    const setTabRef = (el, tabId) => {
      if (el) {
        tabRefs.value[tabId] = el;
        // Observe the new tab element if ResizeObserver is set up
        if (resizeObserver && typeof ResizeObserver !== "undefined") {
          resizeObserver.observe(el);
        }
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
        const left =
          tabRect.left - containerRect.left + tabsContainer.value.scrollLeft;
        const width = tabRect.width;

        // Calculate vertical position based on which line the tab is on
        // Use getBoundingClientRect for top position relative to container
        const activeTabTop = tabRect.top - containerRect.top;
        const activeTabHeight = tabRect.height;

        // Calculate top position: indicator should be at the bottom of the active tab's line
        // top = position of tab + height of tab - height of indicator
        const top = activeTabTop + activeTabHeight - 2.5;

        indicatorStyle.value = {
          left: `${left}px`,
          width: `${width}px`,
          top: `${top}px`,
        };
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

    // Handle scroll on tabs container to update indicator position
    const handleScroll = () => {
      updateIndicatorPosition();
    };

    // Handle window resize to update indicator position
    const handleResize = () => {
      updateIndicatorPosition();
    };

    onMounted(async () => {
      // Load timezone first, before any other operations
      await loadTimezone();
      loadConfig();
      // Update indicator position after mounting
      setTimeout(() => {
        updateIndicatorPosition();
      }, 100);

      // Add scroll listener to tabs container
      if (tabsContainer.value) {
        tabsContainer.value.addEventListener("scroll", handleScroll);
      }

      // Add window resize listener
      if (typeof window !== "undefined") {
        window.addEventListener("resize", handleResize);
      }

      // Setup ResizeObserver to watch for size changes
      if (typeof ResizeObserver !== "undefined") {
        resizeObserver = new ResizeObserver(() => {
          requestAnimationFrame(() => {
            updateIndicatorPosition();
          });
        });

        // Observe the tabs container
        if (tabsContainer.value) {
          resizeObserver.observe(tabsContainer.value);
        }

        // Observe each tab button
        nextTick(() => {
          Object.values(tabRefs.value).forEach((tabEl) => {
            if (tabEl) {
              resizeObserver.observe(tabEl);
            }
          });
        });
      }
    });

    onUnmounted(() => {
      // Remove scroll listener from tabs container
      if (tabsContainer.value) {
        tabsContainer.value.removeEventListener("scroll", handleScroll);
      }

      // Remove window resize listener
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", handleResize);
      }

      // Disconnect ResizeObserver
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
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
      deletingBackup,
      backupRunning,
      restoreRunning,
      selectedBackupId,
      cronInfo,
      cronError,
      isCronLoading,
      showAlertModal,
      alertModalConfig,
      saveResult,
      handleCronInput,
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
      restoreSearchQuery,
      restoreFilters,
      restoreSortBy,
      restoreSortOrder,
      restorePage,
      restorePageSize,
      backupTypeFilterOptions,
      backupStatusFilterOptions,
      backupStorageFilterOptions,
      pageSizeOptions,
      filteredAndSortedBackups,
      totalPages,
      paginatedBackups,
      sortBackups,
      selectBackupForRestore,
      inferStorageType,
      getStorageLabelShort,
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

  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid var(--border-color);
  min-height: 120px;
}

@media (min-width: 769px) {
  .integration-card {
    box-sizing: border-box;
  }

  .integration-content {
    justify-content: center;
    flex: 1;
    min-width: 0;
  }

  .integration-content h3 {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
  min-width: 0;
  overflow: hidden;
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

.backup-controls-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 1;
  min-width: 0;
  max-width: 100%;
  padding-top: 2px;
  overflow: visible;
}

.backup-storage-select-card {
  min-width: 140px;
  max-width: 160px;
  flex-shrink: 1;
  position: relative;
  z-index: 1;
}

.backup-storage-select-card :deep(.custom-select-trigger-sm) {
  min-height: 2.5rem;
  height: 2.5rem;
  padding: 0.5rem 1rem;
  padding-right: 1.75rem;
  box-sizing: border-box;
  position: relative;
  z-index: 1;
}

.backup-storage-select-card:hover :deep(.custom-select-trigger-sm) {
  z-index: 2;
}

.btn-backup-trigger {
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

.btn-backup-trigger:hover:not(:disabled) {
  background: var(--bg-primary);
  border-color: var(--slate-grey);
  transform: translateY(-1px);
  z-index: 2;
}

.btn-backup-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-backup-trigger span {
  display: flex;
  align-items: center;
  justify-content: center;
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
  border-bottom: 1px solid var(--slate-grey);
  margin-bottom: 1.5rem;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: thin;
  scrollbar-color: var(--accent) transparent;
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
  background: var(--accent);
}

.tabs-header::-webkit-scrollbar-thumb:hover {
  background: var(--accent);
}

.tab-button {
  background: transparent;
  border: none;
  color: var(--text-primary);
  padding: 0.75rem 1.25rem;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 500;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  z-index: 1;

  flex: 1;
  min-width: 0;
  white-space: nowrap;
  flex-shrink: 0;
}

.tab-button:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.tab-button.active {
  color: var(--text-primary);
  background: rgba(0, 66, 37, 0.1);
}

/* Tab indicator */
.tab-indicator {
  position: absolute;
  height: 2.5px;
  background: var(--accent);
  transition:
    left 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
    width 0.35s cubic-bezier(0.34, 1.56, 0.64, 1),
    top 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 2;
  pointer-events: none;
  will-change: left, width;
  margin-top: 0.3rem;
}

.tab-content {
  min-height: 300px;
}

.config-section {
  padding: 1.5rem;
  background: var(--bg-primary);

  border: 1px solid var(--slate-grey);
  margin-bottom: 1.5rem;
}

.config-section h4 {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1.1rem;
  font-weight: 600;
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

.form-help code {
  background: var(--bg-primary);
  padding: 0.125rem 0.375rem;

  font-family: monospace;
  font-size: 0.85em;
  color: var(--text-primary);
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
  background-color: var(--text-primary);

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

/* Button styles use global .btn, .btn-primary, .btn-secondary, .btn-danger, .btn-warning from vault.css */
.btn-small {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.backups-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  contain: layout style paint;
}

.backups-count-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);

  margin-bottom: 1rem;
  font-size: 0.9rem;
  color: var(--text-primary);
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
  background: var(--bg-primary);

  border: 1px solid var(--slate-grey);
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
  color: var(--text-primary);
  text-transform: capitalize;
}

.backup-status {
  padding: 0.25rem 0.75rem;

  font-size: 0.85rem;
  font-weight: 500;
}

.storage-badge {
  display: inline-block;
  padding: 0.25rem 0.65rem;

  font-size: 0.8rem;
  font-weight: 500;
  background: var(--bg-primary);
  color: var(--ash-grey);
  border: 1px solid var(--slate-grey);
  white-space: nowrap;
  flex-shrink: 0;
}

.status-completed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-running {
  background: rgba(0, 66, 37, 0.15);
  color: var(--text-primary);
  border: 1px solid rgba(0, 66, 37, 0.3);
}

.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.status-pending {
  background: var(--accent);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.backup-details {
  font-size: 0.85rem;
  color: var(--text-primary);
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
  color: var(--text-primary);
  font-size: 0.9rem;
  flex-shrink: 0;
}

.checksum-value {
  display: block;
  font-family: "Courier New", monospace;
  font-size: 0.85rem;
  padding: 0.5rem;
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);

  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  color: var(--text-primary);
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
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  color: #ef4444;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: var(--text-primary);
}

.empty-state span {
  font-size: 4rem;
  display: block;
  margin-bottom: 1rem;
}

.restore-section {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.restore-header {
  margin-bottom: 1rem;
}

.restore-header h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.1rem;
  color: var(--text-primary);
  font-weight: 600;
}

.restore-header p {
  margin: 0;
  color: var(--text-primary);
  font-size: 0.9rem;
  line-height: 1.5;
}

.restore-filters {
  background: var(--bg-primary);

  border: 1px solid var(--slate-grey);
  padding: 1rem;
}

.filter-row {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  min-width: 150px;
}

.filter-group label {
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 500;
}

.filter-input {
  background: var(--bg-primary);
  border: 1px solid var(--slate-grey);

  padding: 0.75rem;
  color: var(--text-primary);
  font-size: 0.95rem;
  transition: all 0.2s ease;
  width: 100%;
  box-sizing: border-box;
}

.filter-input:focus {
  outline: none;
  border-color: var(--border-color);
  box-shadow: 0 0 0 3px rgba(0, 66, 37, 0.1);
}

.restore-table-container {
  overflow-x: auto;

  border: 1px solid var(--slate-grey);
  background: var(--bg-primary);
}

.restore-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 800px;
}

.restore-table thead {
  background: var(--bg-primary);
}

.restore-table th {
  padding: 0.75rem 1rem;
  text-align: left;
  color: var(--text-primary);
  font-size: 0.85rem;
  font-weight: 600;
  border-bottom: 1px solid var(--slate-grey);
}

.restore-table th.sortable {
  cursor: pointer;
  user-select: none;
  transition: background 0.2s ease;
}

.restore-table th.sortable:hover {
  background: var(--accent);
}

.sort-indicator {
  margin-left: 0.5rem;
  color: var(--text-primary);
  font-weight: bold;
}

.restore-table td {
  padding: 0.75rem 1rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  border-bottom: 1px solid var(--slate-grey);
}

.restore-table tbody tr {
  transition: background 0.2s ease;
  cursor: pointer;
}

.restore-table tbody tr:hover:not(.empty-row):not(.row-disabled) {
  background: var(--bg-secondary);
}

.restore-table tbody tr.row-selected {
  background: var(--bg-primary);
  border-left: 3px solid var(--slate-grey);
}

.restore-table tbody tr.row-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.restore-table tbody tr.empty-row {
  cursor: default;
}

.restore-table tbody tr.empty-row:hover {
  background: transparent;
}

.restore-table .text-center {
  text-align: center;
  padding: 2rem;
  color: var(--text-primary);
}

.col-select {
  width: 50px;
  text-align: center;
}

.col-date {
  min-width: 180px;
}

.col-type {
  min-width: 100px;
}

.col-status {
  min-width: 100px;
}

.col-size {
  min-width: 100px;
}

.col-storage {
  min-width: 100px;
}

.backup-type-badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;

  background: var(--bg-primary);
  color: var(--ash-grey);
  font-size: 0.8rem;
  font-weight: 500;
  text-transform: capitalize;
}

.backup-status-badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;

  font-size: 0.8rem;
  font-weight: 500;
}

.backup-status-badge.status-completed {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.backup-status-badge.status-running {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--slate-grey);
}

.backup-status-badge.status-failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.backup-status-badge.status-pending {
  background: var(--accent);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.storage-badge-small {
  display: inline-block;
  padding: 0.25rem 0.5rem;

  background: var(--bg-primary);
  color: var(--ash-grey);
  font-size: 0.8rem;
  font-weight: 500;
}

.restore-pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  padding: 1rem;
  background: var(--bg-primary);

  border: 1px solid var(--slate-grey);
}

.pagination-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  flex-wrap: nowrap;
}

.pagination-size {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: nowrap;
  white-space: nowrap;
  flex-shrink: 0;
}

.pagination-size label {
  color: var(--text-primary);
  font-size: 0.85rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.page-numbers {
  color: var(--text-primary);
  font-size: 0.9rem;
}

.restore-actions {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-top: 1rem;
  border-top: 1px solid var(--slate-grey);
  align-items: flex-end;
}

.restore-btn {
  align-self: flex-end;
}

.modal {
  max-width: 90%;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;

  display: flex;
  flex-direction: column;
}

.modal-wide {
  width: 90%;
  overflow-y: visible;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--slate-grey);
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
  transform: translateZ(0);
  contain: layout style paint;
  -webkit-overflow-scrolling: touch;
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

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--slate-grey);
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  color: var(--text-primary);
}

.error {
  color: #f87171;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.test-result,
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
    width: 90%;
    overflow-y: visible;
  }

  .tabs-header {
    padding: 0.5rem 0.75rem;
    gap: 0.5rem;
    margin-bottom: 1rem;
    justify-content: flex-start;
    flex-wrap: wrap;
    overflow-x: visible;
    overflow-y: visible;
  }

  .tab-button {
    padding: 0.5rem 0.75rem;
    font-size: 0.85rem;
    flex: 0 0 calc(50% - 0.25rem);
    min-width: 0;
    white-space: nowrap;
  }

  .tab-button:nth-child(3) {
    flex: 0 0 100%;
  }

  .backup-controls-card {
    width: 100%;
    flex-direction: row;
    justify-content: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .backup-storage-select-card {
    flex: 1;
    min-width: 0;
    max-width: 100%;
  }

  .filter-row {
    flex-direction: column;
  }

  .filter-group {
    min-width: 100%;
  }

  .restore-table-container {
    overflow-x: auto;
  }

  .restore-pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .pagination-info {
    flex-direction: column;
    align-items: flex-start;
    width: 100%;
  }

  .pagination-controls {
    width: 100%;
    justify-content: space-between;
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
    gap: 0.5rem;
    flex-wrap: wrap;
    overflow-x: visible;
    overflow-y: visible;
  }

  .tab-button {
    padding: 0.5rem 0.6rem;
    font-size: 0.8rem;
    flex: 0 0 calc(50% - 0.25rem);
  }

  .tab-button:nth-child(3) {
    flex: 0 0 100%;
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

/* Cron status styles */
.cron-status {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  border-radius: 4px;
}

.cron-status.loading {
  color: var(--text-primary);
  background: rgba(var(--slate-grey-rgb, 100, 116, 139), 0.1);
}

.cron-status.error {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.cron-status.info {
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.spinner-small {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(var(--text-primary-rgb, 255, 255, 255), 0.3);
  border-top-color: var(--text-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
