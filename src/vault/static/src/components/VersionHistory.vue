<template>
  <div v-if="show" class="version-history-overlay" @click="close">
    <div class="version-history-modal glass glass-card" @click.stop>
      <div class="modal-header">
        <h2>Version History</h2>
        <button @click="close" class="btn-icon">✕</button>
      </div>

      <div class="modal-content">
        <div v-if="loading" class="loading">Loading versions...</div>
        <div v-else-if="error" class="error-message glass">{{ error }}</div>
        <div v-else-if="versions.length === 0" class="empty-state">
          <p>No versions available</p>
        </div>
        <div v-else class="versions-list">
          <div
            v-for="version in versions"
            :key="version.id"
            class="version-item"
            :class="{ current: version.version_number === currentVersion }"
          >
            <div class="version-info">
              <div class="version-number">
                Version {{ version.version_number }}
              </div>
              <div class="version-date">
                {{ formatDate(version.created_at) }}
              </div>
              <div
                v-if="version.change_description"
                class="version-description"
              >
                {{ version.change_description }}
              </div>
              <div v-if="version.creator" class="version-creator">
                Created by: {{ version.creator.email || version.created_by }}
              </div>
            </div>
            <div class="version-actions">
              <button
                @click="previewVersion(version)"
                class="btn btn-secondary btn-sm"
              >
                Preview
              </button>
              <button
                @click="restoreVersion(version)"
                class="btn btn-primary btn-sm"
                :disabled="restoring"
              >
                {{ restoring ? "Restoring..." : "Restore" }}
              </button>
            </div>
          </div>
        </div>
        <div v-if="hasMore" class="load-more">
          <button @click="loadMore" class="btn btn-secondary">Load More</button>
        </div>
      </div>
    </div>

    <!-- Confirmation Modal -->
    <ConfirmationModal
      :show="showRestoreConfirm"
      title="Restore Version"
      :message="restoreConfirmMessage"
      confirm-text="Restore"
      :dangerous="false"
      @confirm="handleRestoreConfirm"
      @close="showRestoreConfirm = false"
    />
  </div>
</template>

<script>
import { ref, computed, watch } from "vue";
import { versions as versionsApi } from "../services/versions";
import ConfirmationModal from "./ConfirmationModal.vue";

export default {
  name: "VersionHistory",
  components: {
    ConfirmationModal,
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    fileId: {
      type: String,
      required: true,
    },
    currentVersion: {
      type: Number,
      default: null,
    },
  },
  emits: ["close", "restored", "preview"],
  setup(props, { emit }) {
    const loading = ref(false);
    const error = ref(null);
    const versions = ref([]);
    const restoring = ref(false);
    const hasMore = ref(false);
    const offset = ref(0);
    const limit = 20;
    const showRestoreConfirm = ref(false);
    const pendingRestoreVersion = ref(null);
    const restoreConfirmMessage = ref("");

    const loadVersions = async () => {
      if (!props.fileId) return;

      loading.value = true;
      error.value = null;

      try {
        const response = await versionsApi.getHistory(props.fileId, {
          limit,
          offset: offset.value,
        });

        if (offset.value === 0) {
          versions.value = response.versions || [];
        } else {
          versions.value = [...versions.value, ...(response.versions || [])];
        }

        hasMore.value = response.has_more || false;
      } catch (err) {
        console.error("Load versions error:", err);
        error.value = err.message || "Failed to load versions";
      } finally {
        loading.value = false;
      }
    };

    const loadMore = async () => {
      if (loading.value || !hasMore.value) return;
      offset.value += limit;
      await loadVersions();
    };

    const restoreVersion = (version) => {
      if (restoring.value) return;
      pendingRestoreVersion.value = version;
      restoreConfirmMessage.value = `Are you sure you want to restore version ${version.version_number}? This will create a new version with the restored content.`;
      showRestoreConfirm.value = true;
    };

    const handleRestoreConfirm = async () => {
      if (!pendingRestoreVersion.value) return;
      const version = pendingRestoreVersion.value;
      pendingRestoreVersion.value = null;
      showRestoreConfirm.value = false;

      restoring.value = true;
      try {
        await versionsApi.restore(props.fileId, version.id);
        emit("restored", version);
        // Reload versions to show the new restored version
        offset.value = 0;
        await loadVersions();
      } catch (err) {
        console.error("Restore error:", err);
        error.value = err.message || "Failed to restore version";
      } finally {
        restoring.value = false;
      }
    };

    const previewVersion = (version) => {
      emit("preview", version);
    };

    const close = () => {
      emit("close");
    };

    const formatDate = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleString();
    };

    // Watch for file changes
    watch(
      () => [props.show, props.fileId],
      ([newShow, newFileId]) => {
        if (newShow && newFileId) {
          offset.value = 0;
          loadVersions();
        }
      },
      { immediate: true },
    );

    return {
      loading,
      error,
      versions,
      restoring,
      hasMore,
      showRestoreConfirm,
      restoreConfirmMessage,
      loadVersions,
      loadMore,
      restoreVersion,
      handleRestoreConfirm,
      previewVersion,
      close,
      formatDate,
    };
  },
};
</script>

<style scoped>
.version-history-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 2rem;
}

.version-history-modal {
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-primary, #f1f5f9);
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.versions-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.version-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  transition: all 0.2s;
}

.version-item:hover {
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
  border-color: var(--border-color-hover, rgba(148, 163, 184, 0.4));
}

.version-item.current {
  border-color: var(--accent-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.1);
}

.version-info {
  flex: 1;
}

.version-number {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  margin-bottom: 0.25rem;
}

.version-date {
  font-size: 0.85rem;
  color: var(--text-muted, #94a3b8);
  margin-bottom: 0.5rem;
}

.version-description {
  font-size: 0.9rem;
  color: var(--text-secondary, #cbd5e1);
  margin-bottom: 0.25rem;
}

.version-creator {
  font-size: 0.85rem;
  color: var(--text-muted, #94a3b8);
}

.version-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-sm {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
}

.load-more {
  margin-top: 1.5rem;
  text-align: center;
}

.loading,
.empty-state {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary, #cbd5e1);
}

.error-message {
  padding: 1.5rem;
  text-align: center;
  color: var(--error, #ef4444);
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md, 8px);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #cbd5e1);
  font-size: 1.5rem;
  padding: 0.5rem;
  line-height: 1;
}

.btn-icon:hover {
  color: var(--text-primary, #f1f5f9);
}
</style>
