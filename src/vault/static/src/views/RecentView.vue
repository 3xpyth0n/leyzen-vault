<template>
  <ConfirmationModal
    :show="showDeleteConfirm"
    title="Move to Trash"
    :message="getDeleteMessage()"
    confirm-text="Move to Trash"
    :dangerous="true"
    :disabled="deleting"
    @confirm="handleDeleteConfirm"
    @close="
      if (!deleting) {
        showDeleteConfirm = false;
        deleteError = null;
      }
    "
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

  <!-- Confirmation Modal for share link revocation -->
  <ConfirmationModal
    :show="showRevokeConfirm"
    title="Revoke Share Link"
    :message="revokeConfirmMessage"
    confirm-text="Revoke"
    :dangerous="true"
    @confirm="handleRevokeConfirm"
    @close="showRevokeConfirm = false"
  />

  <!-- File Properties Modal -->
  <FileProperties
    :show="showProperties"
    :fileId="propertiesFileId"
    :vaultspaceId="propertiesVaultspaceId"
    @close="
      showProperties = false;
      propertiesFileId = null;
      propertiesVaultspaceId = null;
    "
    @action="handlePropertiesAction"
  />

  <div class="recent-view glass glass-card">
    <header class="view-header">
      <h1>
        <span class="header-icon" v-html="getIcon('clock', 28)"></span>
        Recent Files
      </h1>
      <div class="header-actions">
        <div class="filter-group">
          <label>Days:</label>
          <CustomSelect
            v-model="daysFilter"
            :options="daysOptions"
            @change="handleDaysChange"
            size="small"
            placeholder="Select days"
          />
        </div>
        <button
          @click="refreshRecent"
          :disabled="loading"
          class="btn btn-secondary"
        >
          {{ loading ? "Loading..." : "Refresh" }}
        </button>
      </div>
    </header>

    <main class="view-main">
      <div v-if="loading" class="loading">Loading recent files...</div>
      <div v-else-if="error" class="error glass">{{ error }}</div>
      <div v-else-if="recentFiles.length === 0" class="empty-state">
        <p>No recent files</p>
        <p class="empty-hint">
          Files you've recently modified or accessed will appear here
        </p>
      </div>
      <div v-else class="files-list">
        <div class="files-info glass">
          <p>{{ recentFiles.length }} recent file(s)</p>
        </div>
        <FileListView
          :folders="folders"
          :files="filesList"
          :selectedItems="[]"
          viewMode="grid"
          :editingItemId="editingItemId"
          @item-click="handleItemClick"
          @action="handleFileAction"
          @rename="handleRename"
        />
      </div>
    </main>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { useRouter } from "vue-router";
import { files, auth } from "../services/api";
import FileListView from "../components/FileListView.vue";
import FileProperties from "../components/FileProperties.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import CustomSelect from "../components/CustomSelect.vue";
import { folderPicker } from "../utils/FolderPicker";
import { decryptFileKey, decryptFile } from "../services/encryption.js";

export default {
  name: "RecentView",
  components: {
    FileListView,
    FileProperties,
    ConfirmationModal,
    AlertModal,
    CustomSelect,
  },
  setup() {
    const router = useRouter();
    const loading = ref(false);
    const error = ref(null);
    const recentFiles = ref([]);
    const daysFilter = ref(30);
    const editingItemId = ref(null);
    const showDeleteConfirm = ref(false);
    const pendingDeleteFile = ref(null);
    const pendingDeleteFileName = ref("");
    const showRevokeConfirm = ref(false);
    const revokeConfirmMessage = ref("");
    const pendingRevokeCallback = ref(null);
    const deleting = ref(false);
    const deleteError = ref(null);
    const showProperties = ref(false);
    const propertiesFileId = ref(null);
    const propertiesVaultspaceId = ref(null);
    const showAlertModal = ref(false);
    const alertModalConfig = ref({
      type: "error",
      title: "Error",
      message: "",
    });

    const daysOptions = [
      { value: 7, label: "Last 7 days" },
      { value: 30, label: "Last 30 days" },
      { value: 90, label: "Last 90 days" },
    ];

    const showAlert = (config) => {
      alertModalConfig.value = {
        type: config.type || "error",
        title: config.title || "Alert",
        message: config.message || "",
      };
      showAlertModal.value = true;
    };

    const handleDaysChange = () => {
      loadRecent();
    };

    const folders = computed(() => {
      return recentFiles.value.filter(
        (f) => f.mime_type === "application/x-directory",
      );
    });

    const filesList = computed(() => {
      return recentFiles.value.filter(
        (f) => f.mime_type !== "application/x-directory",
      );
    });

    const loadRecent = async () => {
      loading.value = true;
      error.value = null;
      try {
        const data = await files.listRecent(null, 50, daysFilter.value);
        recentFiles.value = data.files || [];
      } catch (err) {
        error.value = err.message || "Failed to load recent files";
      } finally {
        loading.value = false;
      }
    };

    const refreshRecent = () => {
      loadRecent();
    };

    const handleItemClick = (item, event) => {
      if (item.mime_type === "application/x-directory") {
        router.push(`/vaultspace/${item.vaultspace_id}?folder=${item.id}`);
      } else {
        router.push(`/vaultspace/${item.vaultspace_id}`);
      }
    };

    const handleRename = async (item, newName) => {
      try {
        await files.rename(item.id, newName);
        // Update in list
        const index = recentFiles.value.findIndex((f) => f.id === item.id);
        if (index >= 0) {
          recentFiles.value[index].original_name = newName;
        }
        editingItemId.value = null;
      } catch (err) {
        console.error("Rename failed:", err);
        showAlert({
          type: "error",
          title: "Error",
          message: "Rename failed: " + err.message,
        });
      }
    };

    const getDeleteMessage = () => {
      if (!pendingDeleteFile.value) {
        return "Are you sure you want to move this item to trash? You can restore it from the trash later.";
      }
      const itemName = pendingDeleteFile.value.original_name || "this item";
      const itemType =
        pendingDeleteFile.value.mime_type === "application/x-directory"
          ? "folder"
          : "file";
      return `Are you sure you want to move "${itemName}" to trash? This ${itemType} will be moved to the trash and can be restored later.`;
    };

    const handleDeleteConfirm = async () => {
      const item = pendingDeleteFile.value;
      if (!item) return;

      deleting.value = true;
      deleteError.value = null;

      const itemType =
        item.mime_type === "application/x-directory" ? "Folder" : "File";

      try {
        await files.delete(item.id);
        // Remove from list
        recentFiles.value = recentFiles.value.filter((f) => f.id !== item.id);

        pendingDeleteFile.value = null;
        pendingDeleteFileName.value = "";
        showDeleteConfirm.value = false;

        // Show success message
        if (window.Notifications) {
          window.Notifications.success(
            `${itemType} moved to trash successfully`,
          );
        }
      } catch (err) {
        console.error("Delete failed:", err);
        deleteError.value = err.message || "Failed to move to trash";
        // Don't close modal on error so user can see the error
      } finally {
        deleting.value = false;
      }
    };

    const handleFileAction = async (action, item, newName = null) => {
      if (action === "star") {
        try {
          await files.toggleStar(item.id);
          await loadRecent(); // Reload to update star status
        } catch (err) {
          console.error("Failed to toggle star:", err);
        }
      } else if (action === "download") {
        try {
          // Download file
          const encryptedDataArrayBuffer = await files.download(
            item.id,
            item.vaultspace_id,
          );

          // Convert ArrayBuffer to Uint8Array
          const encryptedData = new Uint8Array(encryptedDataArrayBuffer);

          // Extract IV and encrypted content (IV is first 12 bytes)
          const iv = encryptedData.slice(0, 12);
          const encrypted = encryptedData.slice(12);

          // Get vaultspace key from keyManager
          const vaultspaceKey = await window.keyManager?.getVaultSpaceKey(
            item.vaultspace_id,
          );
          if (!vaultspaceKey) {
            throw new Error(
              "VaultSpace key not found. Please refresh the page.",
            );
          }

          // Get file details with FileKey
          const fileData = await files.get(item.id, item.vaultspace_id);
          if (!fileData || !fileData.file_key) {
            throw new Error("File key not found");
          }

          // Decrypt file key
          const fileKey = await decryptFileKey(
            vaultspaceKey,
            fileData.file_key.encrypted_key,
          );

          // Decrypt file
          const decrypted = await decryptFile(fileKey, encrypted.buffer, iv);

          // Create blob and download
          const blob = new Blob([decrypted]);
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = item.original_name;
          a.click();
          URL.revokeObjectURL(url);
        } catch (err) {
          console.error("Download failed:", err);
          showAlert({
            type: "error",
            title: "Error",
            message: "Download failed: " + err.message,
          });
        }
      } else if (action === "delete") {
        // Show confirmation modal
        pendingDeleteFile.value = item;
        pendingDeleteFileName.value = item.original_name;
        showDeleteConfirm.value = true;
      } else if (action === "rename") {
        if (newName) {
          // Save rename with new name
          try {
            await files.rename(item.id, newName);
            // Update in list
            const index = recentFiles.value.findIndex((f) => f.id === item.id);
            if (index >= 0) {
              recentFiles.value[index].original_name = newName;
            }
            editingItemId.value = null;
          } catch (err) {
            console.error("Rename failed:", err);
            showAlert({
              type: "error",
              title: "Error",
              message: "Rename failed: " + err.message,
            });
          }
        } else {
          // Start editing
          editingItemId.value = item.id;
        }
      } else if (action === "cancel-rename") {
        editingItemId.value = null;
      } else if (action === "share") {
        // Open share modal using SharingManager
        if (window.sharingManager) {
          const vaultspaceKey = await window.keyManager?.getVaultSpaceKey(
            item.vaultspace_id,
          );
          window.sharingManager.showShareModal(
            item.id,
            "file",
            item.vaultspace_id,
            vaultspaceKey,
          );
        } else {
          // Fallback: try to load sharing manager
          let retries = 0;
          const maxRetries = 30;
          const checkInterval = setInterval(() => {
            retries++;
            if (window.sharingManager) {
              clearInterval(checkInterval);
              window.keyManager
                ?.getVaultSpaceKey(item.vaultspace_id)
                .then((key) => {
                  window.sharingManager.showShareModal(
                    item.id,
                    "file",
                    item.vaultspace_id,
                    key,
                  );
                });
            } else if (retries >= maxRetries) {
              clearInterval(checkInterval);
              showAlert({
                type: "error",
                title: "Error",
                message:
                  "Share functionality is not available. Please refresh the page.",
              });
            }
          }, 100);
        }
      } else if (action === "properties") {
        // Show properties modal
        showFileProperties(item.id, item.vaultspace_id);
      } else if (action === "copy") {
        handleCopyAction(item);
      } else if (action === "move") {
        handleMoveAction(item);
      }
    };

    const handleRevokeConfirm = () => {
      showRevokeConfirm.value = false;
      if (pendingRevokeCallback.value) {
        const callback = pendingRevokeCallback.value;
        pendingRevokeCallback.value = null;
        callback();
      }
    };

    const getAllFolders = async (vaultspaceId) => {
      // Get all folders in the vaultspace for the picker
      try {
        if (!vaultspaceId) {
          return [];
        }
        const result = await files.list(vaultspaceId, null, 1, 100);
        return (result.files || []).filter(
          (f) => f.mime_type === "application/x-directory",
        );
      } catch (err) {
        console.error("Failed to load folders:", err);
        return [];
      }
    };

    const handleCopy = async (item, newParentId, newName) => {
      try {
        const copiedFile = await files.copy(item.id, {
          newParentId: newParentId,
          newVaultspaceId: null, // Keep in same vaultspace
          newName: newName, // Keep same name unless specified
        });

        // Reload recent files to show the new copy
        await loadRecent();
      } catch (err) {
        throw err;
      }
    };

    const handleMove = async (item, newParentId) => {
      try {
        await files.move(item.id, newParentId);
        // Remove from list since it's moved
        recentFiles.value = recentFiles.value.filter((f) => f.id !== item.id);
      } catch (err) {
        throw err;
      }
    };

    const handleMoveAction = async (item) => {
      try {
        // Get all folders in the vaultspace for the picker
        const allFolders = await getAllFolders(item.vaultspace_id);

        // Show folder picker
        const selectedFolderId = await folderPicker.show(
          allFolders,
          null, // Current folder ID (not applicable in RecentView)
          item.vaultspace_id,
          item.mime_type === "application/x-directory" ? item.id : null,
        );

        // User cancelled
        if (selectedFolderId === undefined) {
          return;
        }

        // Perform move
        await handleMove(item, selectedFolderId);

        // Reload recent files to reflect changes
        await loadRecent();

        // Show success message
        if (window.Notifications) {
          window.Notifications.success(
            `${item.mime_type === "application/x-directory" ? "Folder" : "File"} moved successfully`,
          );
        }
      } catch (err) {
        console.error("Move action error:", err);
        if (err.message === "Cancelled") {
          return; // User cancelled, don't show error
        }
        if (window.Notifications) {
          window.Notifications.error(err.message || "Failed to move item");
        } else {
          showAlert({
            type: "error",
            title: "Error",
            message: err.message || "Failed to move item",
          });
        }
      }
    };

    const showFileProperties = (fileId, vaultspaceId) => {
      propertiesFileId.value = fileId;
      propertiesVaultspaceId.value = vaultspaceId;
      showProperties.value = true;
    };

    const handlePropertiesAction = async (action, file) => {
      showProperties.value = false;
      if (action === "download") {
        await handleFileAction("download", file);
      } else if (action === "rename") {
        editingItemId.value = file.id;
      } else if (action === "move") {
        await handleMoveAction(file);
      } else if (action === "copy") {
        await handleCopyAction(file);
      } else if (action === "share") {
        await handleFileAction("share", file);
      } else if (action === "delete") {
        pendingDeleteFile.value = file;
        pendingDeleteFileName.value = file.original_name;
        showDeleteConfirm.value = true;
      }
      propertiesFileId.value = null;
      propertiesVaultspaceId.value = null;
    };

    const handleCopyAction = async (item) => {
      try {
        // Get all folders in the vaultspace for the picker
        const allFolders = await getAllFolders(item.vaultspace_id);

        // Show folder picker
        const selectedFolderId = await folderPicker.show(
          allFolders,
          null, // Current folder ID (not applicable in RecentView)
          item.vaultspace_id,
          item.mime_type === "application/x-directory" ? item.id : null,
        );

        // User cancelled
        if (selectedFolderId === undefined) {
          return;
        }

        // Perform copy
        await handleCopy(item, selectedFolderId, null);

        // Reload recent files to show the new copy
        await loadRecent();

        // Show success message
        if (window.Notifications) {
          window.Notifications.success(
            `${item.mime_type === "application/x-directory" ? "Folder" : "File"} copied successfully`,
          );
        }
      } catch (err) {
        console.error("Copy action error:", err);
        if (err.message === "Cancelled") {
          return; // User cancelled, don't show error
        }
        if (window.Notifications) {
          window.Notifications.error(err.message || "Failed to copy item");
        } else {
          showAlert({
            type: "error",
            title: "Error",
            message: err.message || "Failed to copy item",
          });
        }
      }
    };

    onMounted(() => {
      loadRecent();

      // Expose showConfirmationModal for sharing.js to use
      window.showConfirmationModal = (options) => {
        revokeConfirmMessage.value =
          options.message || "Are you sure you want to proceed?";
        pendingRevokeCallback.value = options.onConfirm || null;
        showRevokeConfirm.value = true;
      };
    });

    onBeforeUnmount(() => {
      // Cleanup global function
      if (window.showConfirmationModal) {
        delete window.showConfirmationModal;
      }
    });

    const getIcon = (iconName, size = 24) => {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      return window.Icons[iconName](size, "currentColor");
    };

    return {
      loading,
      error,
      recentFiles,
      folders,
      filesList,
      daysFilter,
      daysOptions,
      handleDaysChange,
      loadRecent,
      refreshRecent,
      handleItemClick,
      handleFileAction,
      handleRename,
      handleDeleteConfirm,
      editingItemId,
      showDeleteConfirm,
      pendingDeleteFileName,
      showRevokeConfirm,
      revokeConfirmMessage,
      handleRevokeConfirm,
      getDeleteMessage,
      deleting,
      deleteError,
      handleMoveAction,
      handleCopyAction,
      showFileProperties,
      handlePropertiesAction,
      showProperties,
      propertiesFileId,
      propertiesVaultspaceId,
      showAlertModal,
      alertModalConfig,
      handleAlertModalClose: () => {
        showAlertModal.value = false;
      },
      getIcon,
    };
  },
};
</script>

<style scoped>
.recent-view {
  min-height: 100vh;
  padding: 2rem;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding: 1.5rem 2rem;
  border-radius: 2rem;
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
  align-items: center;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-group label {
  color: var(--text-secondary, #cbd5e1);
  font-size: 0.9rem;
}

.input-sm {
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
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

.empty-hint {
  margin-top: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted, #94a3b8);
}

.files-info {
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: var(--radius-md, 8px);
}
</style>
