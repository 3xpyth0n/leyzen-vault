<template>
  <div class="trash-view">
    <header class="view-header">
      <h1>
        <span class="header-icon" v-html="getIcon('trash', 28)"></span>
        Trash
      </h1>
      <div class="header-actions">
        <button
          @click="emptyTrash"
          :disabled="loading || trashFiles.length === 0"
          class="btn btn-danger"
        >
          Empty Trash
        </button>
        <button
          @click="refreshTrash"
          :disabled="loading"
          class="btn btn-secondary"
        >
          {{ loading ? "Loading..." : "Refresh" }}
        </button>
      </div>
    </header>

    <main class="view-main">
      <div v-if="loading" class="loading">Loading trash...</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <div v-else-if="trashFiles.length === 0" class="empty-state">
        <p>Trash is empty</p>
      </div>
      <div v-else class="trash-list">
        <div class="trash-info">
          <p>{{ trashFiles.length }} item(s) in trash</p>
        </div>
        <div class="files-grid">
          <div
            v-for="file in trashFiles"
            :key="file.id"
            class="file-card trash-item"
            :class="{ selected: isSelected(file.id) }"
            @click="handleItemClick(file, $event)"
          >
            <input
              type="checkbox"
              :checked="isSelected(file.id)"
              @click.stop="toggleSelection(file)"
              class="file-checkbox"
            />
            <div class="file-icon" v-html="getFileIcon(file)"></div>
            <div class="file-info">
              <h3>{{ file.original_name }}</h3>
              <p class="file-size" v-if="file.size">
                Size: {{ formatSize(file.size) }}
              </p>
              <p class="file-date">
                Deleted: {{ formatDate(file.deleted_at) }}
              </p>
            </div>
            <div class="file-actions">
              <button
                @click.stop="restoreFile(file)"
                class="btn-icon"
                title="Restore"
                v-html="getIcon('restore', 20)"
              ></button>
              <button
                @click.stop="permanentlyDeleteFile(file)"
                class="btn-icon"
                title="Delete Permanently"
                v-html="getIcon('trash', 20)"
              ></button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Restore Confirmation Modal -->
    <teleport to="body">
      <div
        v-if="showRestoreConfirm"
        class="modal-overlay"
        @click="showRestoreConfirm = false"
      >
        <div class="modal" @click.stop>
          <h2>Restore File</h2>
          <p>
            Are you sure you want to restore "{{
              itemToRestore?.original_name
            }}"?
          </p>
          <div v-if="restoreError" class="error-message">
            {{ restoreError }}
          </div>
          <div class="form-actions">
            <button
              @click="confirmRestore"
              :disabled="restoring"
              class="btn btn-primary"
            >
              {{ restoring ? "Restoring..." : "Restore" }}
            </button>
            <button
              type="button"
              @click="
                showRestoreConfirm = false;
                restoreError = null;
                itemToRestore = null;
              "
              class="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Permanent Delete Confirmation Modal -->
    <teleport to="body">
      <div
        v-if="showDeleteConfirm"
        class="modal-overlay"
        @click="showDeleteConfirm = false"
      >
        <div class="modal" @click.stop>
          <h2>Permanently Delete File</h2>
          <p>
            Are you sure you want to permanently delete "{{
              itemToDelete?.original_name
            }}"? This action cannot be undone.
          </p>
          <div v-if="deleteError" class="error-message">
            {{ deleteError }}
          </div>
          <div class="form-actions">
            <button
              @click="confirmPermanentDelete"
              :disabled="deleting"
              class="btn btn-danger"
            >
              {{ deleting ? "Deleting..." : "Delete Permanently" }}
            </button>
            <button
              type="button"
              @click="
                showDeleteConfirm = false;
                deleteError = null;
                itemToDelete = null;
              "
              class="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </teleport>

    <!-- Empty Trash Confirmation Modal -->
    <teleport to="body">
      <div
        v-if="showEmptyTrashConfirm"
        class="modal-overlay"
        @click="showEmptyTrashConfirm = false"
      >
        <div class="trash-modal" @click.stop>
          <h2>Empty Trash</h2>
          <p>
            Are you sure you want to permanently delete all
            {{ trashFiles.length }} item(s) in trash? This action cannot be
            undone.
          </p>
          <div v-if="emptyTrashError" class="error-message">
            {{ emptyTrashError }}
          </div>
          <div class="form-actions">
            <button
              type="button"
              @click="
                showEmptyTrashConfirm = false;
                emptyTrashError = null;
              "
              class="btn btn-secondary"
            >
              Cancel
            </button>
            <button
              @click="confirmEmptyTrash"
              :disabled="emptying"
              class="btn btn-danger"
            >
              {{ emptying ? "Deleting..." : "Empty Trash" }}
            </button>
          </div>
        </div>
      </div>
    </teleport>
  </div>

  <!-- Batch Actions Bar -->
  <BatchActionsTrash
    :selectedItems="selectedItems"
    :processing="restoring || deleting"
    :actionType="restoring ? 'restore' : deleting ? 'delete' : null"
    @restore="batchRestore"
    @delete="batchPermanentDelete"
    @clear="clearSelection"
  />
</template>

<script>
import { ref, onMounted, onUnmounted, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { trash, auth } from "../services/api";
import BatchActionsTrash from "../components/BatchActionsTrash.vue";

export default {
  name: "TrashView",
  components: {
    BatchActionsTrash,
  },
  setup() {
    const router = useRouter();
    const route = useRoute();
    const loading = ref(false);
    const error = ref(null);
    const trashFiles = ref([]);
    const selectedItems = ref([]);
    const showRestoreConfirm = ref(false);
    const showDeleteConfirm = ref(false);
    const showEmptyTrashConfirm = ref(false);
    const itemToRestore = ref(null);
    const itemToDelete = ref(null);
    const restoring = ref(false);
    const deleting = ref(false);
    const emptying = ref(false);
    const restoreError = ref(null);
    const deleteError = ref(null);
    const emptyTrashError = ref(null);

    const loadTrash = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await trash.list();
        trashFiles.value = data.files || [];
      } catch (err) {
        error.value = err.message || "Failed to load trash";
      } finally {
        loading.value = false;
      }
    };

    const refreshTrash = () => {
      loadTrash();
    };

    const isSelected = (fileId) => {
      return selectedItems.value.some((item) => item.id === fileId);
    };

    const toggleSelection = (file) => {
      const index = selectedItems.value.findIndex(
        (item) => item.id === file.id,
      );
      if (index >= 0) {
        selectedItems.value.splice(index, 1);
      } else {
        selectedItems.value.push(file);
      }
    };

    const handleItemClick = (file, event) => {
      // If clicking checkbox, don't process card click
      if (event.target.type === "checkbox") {
        return;
      }

      // If clicking action buttons, don't process card click
      if (
        event.target.closest(".file-actions") ||
        event.target.closest(".btn-icon")
      ) {
        return;
      }

      // If Ctrl/Cmd key is pressed, toggle selection
      if (event.ctrlKey || event.metaKey) {
        toggleSelection(file);
        return;
      }

      // If Shift key is pressed, select range
      if (event.shiftKey && selectedItems.value.length > 0) {
        // Select range from last selected to current
        const lastSelectedIndex = trashFiles.value.findIndex(
          (i) =>
            i.id === selectedItems.value[selectedItems.value.length - 1].id,
        );
        const currentIndex = trashFiles.value.findIndex(
          (i) => i.id === file.id,
        );

        if (lastSelectedIndex >= 0 && currentIndex >= 0) {
          const start = Math.min(lastSelectedIndex, currentIndex);
          const end = Math.max(lastSelectedIndex, currentIndex);
          const range = trashFiles.value.slice(start, end + 1);
          // Merge with existing selection, avoiding duplicates
          const newSelection = [...selectedItems.value];
          range.forEach((item) => {
            if (!newSelection.some((s) => s.id === item.id)) {
              newSelection.push(item);
            }
          });
          selectedItems.value = newSelection;
        }
        return;
      }

      // Normal click: select item (clear other selections first if not already selected)
      if (!isSelected(file.id)) {
        clearSelection();
        toggleSelection(file);
      }
      // If already selected, do nothing (keep selection) - matches VaultSpaceView behavior
    };

    const clearSelection = () => {
      selectedItems.value = [];
    };

    const restoreFile = (file) => {
      itemToRestore.value = file;
      showRestoreConfirm.value = true;
    };

    const confirmRestore = async () => {
      if (!itemToRestore.value) return;
      restoring.value = true;
      restoreError.value = null;
      try {
        await trash.restore(itemToRestore.value.id);
        await loadTrash();
        showRestoreConfirm.value = false;
        itemToRestore.value = null;
      } catch (err) {
        restoreError.value = err.message || "Failed to restore file";
      } finally {
        restoring.value = false;
      }
    };

    const permanentlyDeleteFile = (file) => {
      itemToDelete.value = file;
      showDeleteConfirm.value = true;
    };

    const confirmPermanentDelete = async () => {
      if (!itemToDelete.value) return;
      deleting.value = true;
      deleteError.value = null;
      try {
        await trash.permanentlyDelete(itemToDelete.value.id);
        await loadTrash();
        showDeleteConfirm.value = false;
        itemToDelete.value = null;
      } catch (err) {
        deleteError.value = err.message || "Failed to permanently delete file";
      } finally {
        deleting.value = false;
      }
    };

    const batchRestore = async () => {
      if (selectedItems.value.length === 0) return;
      restoring.value = true;
      restoreError.value = null;
      try {
        for (const item of selectedItems.value) {
          try {
            await trash.restore(item.id);
          } catch (err) {}
        }
        await loadTrash();
        clearSelection();
      } catch (err) {
        restoreError.value = err.message || "Failed to restore files";
      } finally {
        restoring.value = false;
      }
    };

    const batchPermanentDelete = async () => {
      if (selectedItems.value.length === 0) return;
      deleting.value = true;
      deleteError.value = null;
      try {
        for (const item of selectedItems.value) {
          try {
            await trash.permanentlyDelete(item.id);
          } catch (err) {}
        }
        await loadTrash();
        clearSelection();
      } catch (err) {
        deleteError.value = err.message || "Failed to delete files";
      } finally {
        deleting.value = false;
      }
    };

    const emptyTrash = () => {
      if (trashFiles.value.length === 0) return;
      showEmptyTrashConfirm.value = true;
    };

    const confirmEmptyTrash = async () => {
      emptying.value = true;
      emptyTrashError.value = null;
      try {
        for (const file of trashFiles.value) {
          try {
            await trash.permanentlyDelete(file.id);
          } catch (err) {}
        }
        await loadTrash();
        showEmptyTrashConfirm.value = false;
      } catch (err) {
        emptyTrashError.value = err.message || "Failed to empty trash";
      } finally {
        emptying.value = false;
      }
    };

    const formatSize = (bytes) => {
      if (!bytes || bytes === 0) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB", "TB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    };

    const formatDate = (dateString) => {
      if (!dateString) return "Unknown";
      const date = new Date(dateString);
      return date.toLocaleDateString() + " " + date.toLocaleTimeString();
    };

    const getIcon = (iconName, size = 24) => {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      const iconFunction = window.Icons[iconName];
      if (typeof iconFunction === "function") {
        return iconFunction.call(window.Icons, size, "currentColor");
      }
      return "";
    };

    const getFileIcon = (file, size = 48) => {
      if (file.mime_type === "application/x-directory") {
        return getIcon("folder", 48);
      }

      // Use the centralized icon helper function
      const iconName = window.Icons.getFileIconName
        ? window.Icons.getFileIconName(file.mime_type, file.original_name)
        : "file";

      return getIcon(iconName, 48);
    };

    const handleDocumentClick = (event) => {
      // Don't clear selection if clicking on:
      // - File cards or their children
      // - Modals
      // - Batch actions bar
      // - Header actions
      // - Inputs, textareas, or contenteditable elements
      if (
        event.target.closest(".file-card") ||
        event.target.closest(".modal-overlay") ||
        event.target.closest(".trash-modal") ||
        event.target.closest(".batch-actions-bar") ||
        event.target.closest(".header-actions") ||
        event.target.closest(".view-header") ||
        event.target.tagName === "INPUT" ||
        event.target.tagName === "TEXTAREA" ||
        event.target.isContentEditable
      ) {
        return;
      }

      // Clear selection when clicking elsewhere
      if (selectedItems.value.length > 0) {
        clearSelection();
      }
    };

    onMounted(() => {
      loadTrash();
      // Add global click handler to clear selection when clicking outside
      document.addEventListener("click", handleDocumentClick);
    });

    onUnmounted(() => {
      // Remove global click handler when component is unmounted
      document.removeEventListener("click", handleDocumentClick);
    });

    // Watch for route changes to refresh when user returns to this view
    watch(
      () => route.name,
      (newRouteName, oldRouteName) => {
        // Refresh when navigating to this view from another route
        if (
          newRouteName === "Trash" &&
          oldRouteName &&
          oldRouteName !== "Trash"
        ) {
          loadTrash();
        }
      },
    );

    // Also watch the full path to catch route changes even if name doesn't change
    watch(
      () => route.path,
      (newPath, oldPath) => {
        // Refresh when navigating to trash view from another path
        if (newPath === "/trash" && oldPath && oldPath !== "/trash") {
          loadTrash();
        }
      },
    );

    return {
      loading,
      error,
      trashFiles,
      selectedItems,
      showRestoreConfirm,
      showDeleteConfirm,
      showEmptyTrashConfirm,
      itemToRestore,
      itemToDelete,
      restoring,
      deleting,
      emptying,
      restoreError,
      deleteError,
      emptyTrashError,
      refreshTrash,
      isSelected,
      toggleSelection,
      handleItemClick,
      clearSelection,
      restoreFile,
      confirmRestore,
      permanentlyDeleteFile,
      confirmPermanentDelete,
      batchRestore,
      batchPermanentDelete,
      emptyTrash,
      confirmEmptyTrash,
      formatSize,
      formatDate,
      getIcon,
      getFileIcon,
    };
  },
};
</script>

<style scoped>
.trash-view {
  min-height: 100vh;
  padding: 2rem;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding: 1.5rem 2rem;
}

.view-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  display: inline-flex;
  align-items: center;
  color: currentColor;
  margin-top: 0.2rem;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
}

.view-main {
  padding: 1rem 0;
}

.loading,
.error {
  text-align: center;
  padding: 2rem;
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text-secondary, #a9b7aa);
}

.trash-info {
  padding: 1rem;
  margin-bottom: 1rem;
}

.files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.5rem;
}

.file-card {
  background: var(--bg-modal) !important;
  padding: 1.5rem;
  transition: all var(--transition-base, 0.2s);
  cursor: pointer;
}

.file-card:hover {
  background: var(--bg-secondary);
}

.file-card.selected {
  border: 1px solid var(--accent, #004225);
  background: rgba(56, 189, 248, 0.1);
}

.file-checkbox {
  margin-right: 0.75rem;
  margin-top: 0.25rem;
  cursor: pointer;
  width: 13px;
  height: 13px;
}

.file-icon {
  text-align: center;
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
}

.file-info h3 {
  margin: 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  word-break: break-word;
}

.file-info p {
  margin: 0.25rem 0;
  font-size: 0.85rem;
  color: var(--text-secondary, #a9b7aa);
}

.file-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
  justify-content: flex-end;
}

.btn-icon {
  background: transparent;
  border: none;
  color: var(--text-secondary, #a9b7aa);
  cursor: pointer;
  padding: 0.5rem;

  transition: all var(--transition-base, 0.2s);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
  color: var(--text-primary, #a9b7aa);
}

.btn-icon svg {
  display: block;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: #000000c4;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100000;
  padding: 2rem;
  overflow-y: auto;
}

.trash-modal {
  background: var(--bg-modal);
  border: 1px solid var(--slate-grey);
  padding: 2rem;
  max-width: 500px;
  width: 60%;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.modal h2 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
  color: var(--text-primary, #a9b7aa);
  font-weight: 600;
}

.modal p {
  margin: 0 0 1.5rem 0;
  color: var(--text-secondary, #a9b7aa);
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
}

.error-message {
  padding: 1rem;
  margin-bottom: 1rem;
}
</style>
