<template>
  <AppLayout @logout="logout">
    <div class="trash-view glass glass-card">
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
        <div v-else-if="error" class="error glass">{{ error }}</div>
        <div v-else-if="trashFiles.length === 0" class="empty-state">
          <p>Trash is empty</p>
        </div>
        <div v-else class="trash-list">
          <div class="trash-info glass">
            <p>{{ trashFiles.length }} item(s) in trash</p>
          </div>
          <div class="files-grid">
            <div
              v-for="file in trashFiles"
              :key="file.id"
              class="file-card trash-item glass"
              :class="{ selected: isSelected(file.id) }"
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
                <p class="file-type">
                  {{
                    file.mime_type === "application/x-directory"
                      ? "Folder"
                      : file.mime_type
                  }}
                </p>
                <p class="file-size" v-if="file.size">
                  {{ formatSize(file.size) }}
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

          <!-- Batch Actions Bar -->
          <div v-if="selectedItems.length > 0" class="batch-actions-bar glass">
            <span class="selected-count"
              >{{ selectedItems.length }} item(s) selected</span
            >
            <div class="actions">
              <button @click="batchRestore" class="btn btn-primary btn-sm">
                Restore Selected
              </button>
              <button
                @click="batchPermanentDelete"
                class="btn btn-danger btn-sm"
              >
                Delete Permanently
              </button>
              <button @click="clearSelection" class="btn btn-secondary btn-sm">
                Clear Selection
              </button>
            </div>
          </div>
        </div>
      </main>

      <!-- Restore Confirmation Modal -->
      <div
        v-if="showRestoreConfirm"
        class="modal-overlay"
        @click="showRestoreConfirm = false"
      >
        <div class="modal glass glass-card" @click.stop>
          <h2>Restore File</h2>
          <p>
            Are you sure you want to restore "{{
              itemToRestore?.original_name
            }}"?
          </p>
          <div v-if="restoreError" class="error-message glass">
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

      <!-- Permanent Delete Confirmation Modal -->
      <div
        v-if="showDeleteConfirm"
        class="modal-overlay"
        @click="showDeleteConfirm = false"
      >
        <div class="modal glass glass-card" @click.stop>
          <h2>Permanently Delete File</h2>
          <p>
            Are you sure you want to permanently delete "{{
              itemToDelete?.original_name
            }}"? This action cannot be undone.
          </p>
          <div v-if="deleteError" class="error-message glass">
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

      <!-- Empty Trash Confirmation Modal -->
      <div
        v-if="showEmptyTrashConfirm"
        class="modal-overlay"
        @click="showEmptyTrashConfirm = false"
      >
        <div class="modal glass glass-card" @click.stop>
          <h2>Empty Trash</h2>
          <p>
            Are you sure you want to permanently delete all
            {{ trashFiles.length }} item(s) in trash? This action cannot be
            undone.
          </p>
          <div v-if="emptyTrashError" class="error-message glass">
            {{ emptyTrashError }}
          </div>
          <div class="form-actions">
            <button
              @click="confirmEmptyTrash"
              :disabled="emptying"
              class="btn btn-danger"
            >
              {{ emptying ? "Deleting..." : "Empty Trash" }}
            </button>
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
          </div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script>
import { ref, onMounted, watch } from "vue";
import { useRouter, useRoute } from "vue-router";
import { trash, auth } from "../services/api";
import AppLayout from "../components/AppLayout.vue";

export default {
  name: "TrashView",
  components: {
    AppLayout,
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
          } catch (err) {
            console.error(`Failed to restore ${item.original_name}:`, err);
          }
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
          } catch (err) {
            console.error(`Failed to delete ${item.original_name}:`, err);
          }
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
          } catch (err) {
            console.error(`Failed to delete ${file.original_name}:`, err);
          }
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
      return window.Icons[iconName](size, "currentColor");
    };

    const getFileIcon = (file) => {
      if (file.mime_type === "application/x-directory") {
        return getIcon("folder", 48);
      }
      return getIcon("file", 48);
    };

    onMounted(() => {
      loadTrash();
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

    const logout = () => {
      auth.logout();
      router.push("/login");
    };

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
      logout,
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
  border-radius: var(--radius-lg, 12px);
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
  color: var(--text-secondary, #cbd5e1);
}

.trash-info {
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: var(--radius-md, 8px);
}

.files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.5rem;
}

.file-card {
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-radius: var(--radius-md, 8px);
  padding: 1.5rem;
  transition: all var(--transition-base, 0.2s);
  cursor: pointer;
}

.file-card:hover {
  border-color: var(--border-color-hover, rgba(148, 163, 184, 0.4));
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
}

.file-card.selected {
  border-color: var(--accent-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.1);
}

.file-checkbox {
  margin-right: 0.75rem;
  margin-top: 0.25rem;
  cursor: pointer;
  width: 18px;
  height: 18px;
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
  color: var(--text-secondary, #cbd5e1);
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
  color: var(--text-secondary, #cbd5e1);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--radius-md, 8px);
  transition: all var(--transition-base, 0.2s);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-icon:hover {
  background: var(--bg-glass-hover, rgba(30, 41, 59, 0.6));
  color: var(--text-primary, #f1f5f9);
}

.btn-icon svg {
  display: block;
}

.batch-actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  margin-top: 2rem;
  border-radius: var(--radius-md, 8px);
}

.selected-count {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.actions {
  display: flex;
  gap: 0.75rem;
}

.modal-overlay {
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

.modal {
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  backdrop-filter: var(--blur, blur(16px));
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-radius: var(--radius-lg, 12px);
  padding: 2rem;
  max-width: 500px;
  width: 100%;
}

.modal h2 {
  margin: 0 0 1rem 0;
  font-size: 1.5rem;
}

.modal p {
  margin: 0 0 1.5rem 0;
  color: var(--text-secondary, #cbd5e1);
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.error-message {
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: var(--radius-md, 8px);
}
</style>
