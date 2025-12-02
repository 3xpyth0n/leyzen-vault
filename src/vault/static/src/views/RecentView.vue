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

  <!-- File Preview Modal -->
  <FilePreview
    :show="showPreview"
    :fileId="previewFileId"
    :fileName="previewFileName"
    :mimeType="previewMimeType"
    :vaultspaceId="
      previewFileId
        ? recentFiles.find((f) => f.id === previewFileId)?.vaultspace_id || null
        : null
    "
    @close="
      showPreview = false;
      previewFileId = null;
      previewFileName = '';
      previewMimeType = '';
    "
    @download="handlePreviewDownload"
  />

  <!-- Batch Actions Bar -->
  <BatchActions
    v-if="selectedItems.length > 0"
    :selectedItems="selectedItems"
    :availableFolders="[]"
    @delete="handleBatchDelete"
    @download="handleBatchDownload"
    @clear="clearSelection"
  />

  <!-- Encryption Overlay -->
  <Teleport to="body">
    <div
      v-if="showEncryptionOverlay && isMasterKeyRequired"
      class="encryption-overlay"
      :style="{
        ...overlayStyle,
        'pointer-events': showPasswordModal ? 'none' : 'auto',
      }"
      data-encryption-overlay="true"
    >
      <div class="encryption-overlay-content">
        <div class="encryption-icon-wrapper">
          <svg
            class="encryption-icon"
            width="64"
            height="64"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M12 1L3 5V11C3 16.55 6.84 21.74 12 23C17.16 21.74 21 16.55 21 11V5L12 1Z"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M12 12V16"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
        <h2 class="encryption-title">Files are encrypted</h2>
        <p class="encryption-description">
          Enter your encryption password to decrypt and access your files. This
          password is used to decrypt your files and is not stored on the
          server.
        </p>
        <button
          @click="openPasswordModal"
          class="encryption-unlock-btn"
          type="button"
        >
          Unlock Files
        </button>
      </div>
    </div>
  </Teleport>

  <!-- Password Modal for SSO Users -->
  <Teleport to="body">
    <div
      v-if="showPasswordModal"
      class="password-modal-overlay"
      @click.self="closePasswordModal"
    >
      <div class="password-modal glass glass-card">
        <h2>Enter Encryption Password</h2>
        <p class="password-modal-description">
          Enter your encryption password to access your files. This password is
          used to decrypt your files and is not stored on the server.
        </p>
        <div v-if="passwordModalError" class="error-message">
          {{ passwordModalError }}
        </div>
        <div class="form-group">
          <label for="password-input">Password</label>
          <PasswordInput
            id="password-input"
            v-model="passwordModalPassword"
            placeholder="Enter your encryption password"
            @keyup.enter="handlePasswordSubmit"
            :disabled="passwordModalLoading"
          />
        </div>
        <div class="form-actions">
          <button
            @click="closePasswordModal"
            class="btn btn-secondary"
            :disabled="passwordModalLoading"
          >
            Cancel
          </button>
          <button
            @click="handlePasswordSubmit"
            class="btn btn-primary"
            :disabled="passwordModalLoading || !passwordModalPassword.trim()"
          >
            {{ passwordModalLoading ? "Unlocking..." : "Unlock" }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>

  <div
    class="recent-view glass glass-card"
    v-if="!showEncryptionOverlay || !isMasterKeyRequired"
  >
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
          :selectedItems="selectedItems"
          :viewMode="viewMode"
          :editingItemId="editingItemId"
          defaultSortBy="date"
          defaultSortOrder="desc"
          @view-change="handleViewChange"
          @item-click="handleItemClick"
          @action="handleFileAction"
          @selection-change="handleSelectionChange"
          @rename="handleRename"
        />
      </div>
    </main>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { useRouter } from "vue-router";
import { files, auth, vaultspaces } from "../services/api";
import FileListView from "../components/FileListView.vue";
import FileProperties from "../components/FileProperties.vue";
import FilePreview from "../components/FilePreview.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import BatchActions from "../components/BatchActions.vue";
import CustomSelect from "../components/CustomSelect.vue";
import { folderPicker } from "../utils/FolderPicker";
import { decryptFileKey, decryptFile } from "../services/encryption.js";
import { useFileViewComposable } from "../composables/useFileViewComposable.js";
import PasswordInput from "../components/PasswordInput.vue";
import {
  getUserMasterKey,
  decryptVaultSpaceKeyForUser,
  cacheVaultSpaceKey,
  getCachedVaultSpaceKey,
  createVaultSpaceKey,
} from "../services/keyManager.js";

export default {
  name: "RecentView",
  components: {
    FileListView,
    FileProperties,
    FilePreview,
    ConfirmationModal,
    AlertModal,
    BatchActions,
    CustomSelect,
    PasswordInput,
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
    const showPreview = ref(false);
    const previewFileId = ref(null);
    const previewFileName = ref("");
    const previewMimeType = ref("");
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

    const loadRecent = async (cacheBust = false) => {
      loading.value = true;
      error.value = null;
      try {
        const data = await files.listRecent(
          null,
          50,
          daysFilter.value,
          cacheBust,
        );
        // Filter out any deleted files that might have slipped through (defensive)
        recentFiles.value = (data.files || []).filter((f) => !f.deleted_at);

        // Load VaultSpace keys for all unique vaultspace_ids
        await loadVaultSpaceKeysForFiles();
      } catch (err) {
        error.value = err.message || "Failed to load recent files";
      } finally {
        loading.value = false;
      }
    };

    const loadVaultSpaceKeysForFiles = async () => {
      // Check if master key is available
      const userMasterKey = await getUserMasterKey();
      if (!userMasterKey) {
        return; // Silently return if master key is not available
      }

      // Extract unique vaultspace_ids from files
      const vaultspaceIds = new Set();
      recentFiles.value.forEach((file) => {
        if (file.vaultspace_id) {
          vaultspaceIds.add(file.vaultspace_id);
        }
      });

      // Load keys for each vaultspace_id in parallel
      const loadKeyPromises = Array.from(vaultspaceIds).map(
        async (vaultspaceId) => {
          try {
            // Check if key is already cached
            const cachedKey = getCachedVaultSpaceKey(vaultspaceId);
            if (cachedKey) {
              return; // Already cached
            }

            // Try to get encrypted VaultSpace key from server
            const vaultspaceKeyData = await vaultspaces.getKey(vaultspaceId);

            if (!vaultspaceKeyData) {
              // Key doesn't exist, create it
              const currentUser = await auth.getCurrentUser();
              const { encryptedKey } = await createVaultSpaceKey(userMasterKey);
              await vaultspaces.share(
                vaultspaceId,
                currentUser.id,
                encryptedKey,
              );
              const vaultspaceKey = await decryptVaultSpaceKeyForUser(
                userMasterKey,
                encryptedKey,
              );
              cacheVaultSpaceKey(vaultspaceId, vaultspaceKey);
            } else {
              // Decrypt VaultSpace key with user master key
              try {
                const vaultspaceKey = await decryptVaultSpaceKeyForUser(
                  userMasterKey,
                  vaultspaceKeyData.encrypted_key,
                );
                cacheVaultSpaceKey(vaultspaceId, vaultspaceKey);
              } catch (decryptErr) {
                // Decryption failed - VaultSpace key was encrypted with a different master key
                // Silently fail for this vaultspace
                console.debug(
                  `Failed to decrypt VaultSpace key for ${vaultspaceId}:`,
                  decryptErr,
                );
              }
            }
          } catch (err) {
            // Silently fail for individual vaultspaces
            console.debug(
              `Failed to load VaultSpace key for ${vaultspaceId}:`,
              err,
            );
          }
        },
      );

      // Wait for all keys to load (or fail silently)
      await Promise.allSettled(loadKeyPromises);
    };

    // Use file view composable for shared functionality
    const {
      selectedItems,
      viewMode,
      showEncryptionOverlay,
      isMasterKeyRequired,
      showPasswordModal,
      passwordModalPassword,
      passwordModalError,
      passwordModalLoading,
      overlayStyle,
      handleSelectionChange,
      handleViewChange,
      clearSelection,
      checkEncryptionAccess,
      handlePasswordSubmit,
      closePasswordModal,
      openPasswordModal,
    } = useFileViewComposable({
      viewType: "recent",
      enableEncryptionCheck: true,
      onEncryptionUnlocked: async () => {
        // Reload recent files after encryption is unlocked
        await loadRecent(true);
      },
    });

    const refreshRecent = () => {
      loadRecent(true); // Force cache-busting on manual refresh
    };

    const handleItemClick = (item, event) => {
      if (item.mime_type === "application/x-directory") {
        router.push(`/vaultspace/${item.vaultspace_id}?folder=${item.id}`);
      } else {
        // For files, check if it's a double-click to open preview
        if (event && event.detail === 2) {
          handleFileAction("preview", item);
        }
      }
    };

    const handlePreviewDownload = (fileId) => {
      const file = recentFiles.value.find((f) => f.id === fileId);
      if (file) {
        handleFileAction("download", file);
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
        // Remove from list immediately
        recentFiles.value = recentFiles.value.filter((f) => f.id !== item.id);

        // Force refresh with cache-busting to ensure consistency
        await loadRecent(true);

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
      } else if (action === "preview") {
        // Clear selection when opening preview
        clearSelection();
        if (window.selectionManager) {
          window.selectionManager.deselectAll();
          window.selectionManager.updateUI();
        }
        // Show file preview
        previewFileId.value = item.id;
        previewFileName.value = item.original_name || item.name || "File";
        previewMimeType.value = item.mime_type || "";
        showPreview.value = true;
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

        // Reload recent files with cache-busting to show the new copy
        await loadRecent(true);
      } catch (err) {
        throw err;
      }
    };

    const handleMove = async (item, newParentId) => {
      try {
        await files.move(item.id, newParentId);
        // Remove from list immediately since it's moved
        recentFiles.value = recentFiles.value.filter((f) => f.id !== item.id);

        // Force refresh with cache-busting to ensure consistency
        await loadRecent(true);
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

        // Note: handleMove already calls loadRecent(true), but we ensure it here too
        await loadRecent(true);

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

        // Note: handleCopy already calls loadRecent(true), but we ensure it here too
        await loadRecent(true);

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

    // Batch actions handlers
    const handleBatchDelete = async (result) => {
      // Reload recent files after batch delete
      await loadRecent(true);
      clearSelection();
    };

    const handleBatchDownload = async (items) => {
      // Download each file individually
      for (const item of items) {
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
              `VaultSpace key not found for file ${item.original_name}. Please refresh the page.`,
            );
          }

          // Get file details with FileKey
          const fileData = await files.get(item.id, item.vaultspace_id);
          if (!fileData || !fileData.file_key) {
            throw new Error(`File key not found for ${item.original_name}`);
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
          console.error(`Download failed for ${item.original_name}:`, err);
          showAlert({
            type: "error",
            title: "Download Error",
            message: `Failed to download ${item.original_name}: ${err.message}`,
          });
        }
      }
      clearSelection();
    };

    onMounted(async () => {
      // Check encryption access first
      await checkEncryptionAccess();

      // Load recent files
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
      showPreview,
      previewFileId,
      previewFileName,
      previewMimeType,
      handlePreviewDownload,
      showAlertModal,
      alertModalConfig,
      handleAlertModalClose: () => {
        showAlertModal.value = false;
      },
      getIcon,
      // Composable properties
      selectedItems,
      viewMode,
      showEncryptionOverlay,
      isMasterKeyRequired,
      showPasswordModal,
      passwordModalPassword,
      passwordModalError,
      passwordModalLoading,
      overlayStyle,
      handleSelectionChange,
      handleViewChange,
      clearSelection,
      handlePasswordSubmit,
      closePasswordModal,
      openPasswordModal,
      handleBatchDelete,
      handleBatchDownload,
    };
  },
};
</script>

<style scoped>
.recent-view {
  min-height: 100vh;
  padding: 2rem;
}

.mobile-mode .recent-view {
  padding: 1rem;
  padding-bottom: calc(1rem + 64px);
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding: 1.5rem 2rem;
  border-radius: 2rem;
}

.mobile-mode .view-header {
  padding: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.view-header h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.mobile-mode .view-header h1 {
  font-size: 1.25rem;
  width: 100%;
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
  flex-wrap: wrap;
}

.mobile-mode .header-actions {
  width: 100%;
  justify-content: flex-start;
  gap: 0.5rem;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.mobile-mode .filter-group {
  width: 100%;
  justify-content: space-between;
  flex-wrap: wrap;
}

.mobile-mode .filter-group label {
  font-size: 0.85rem;
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

/* Encryption Overlay (Glassmorphic) */
.encryption-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.15),
    rgba(15, 23, 42, 0.12)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: none;
  border-radius: 0 0 0 1rem; /* Rounded bottom-left corner to match sidebar */
  box-shadow: none;
  animation: overlayFadeIn 0.4s cubic-bezier(0.22, 1, 0.36, 1);
  /* pointer-events is controlled via inline style */
  isolation: isolate;
  z-index: 50 !important; /* Below header (100), dropdown (1000), bottom bar (99999) but above content */
}

@keyframes overlayFadeIn {
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.encryption-overlay-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 3rem 2rem;
  max-width: 500px;
  animation: gentlePulse 3s ease-in-out infinite;
  pointer-events: auto;
  position: relative;
  z-index: 1;
}

@keyframes gentlePulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.02);
    opacity: 0.98;
  }
}

.encryption-icon-wrapper {
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: iconFloat 3s ease-in-out infinite;
}

@keyframes iconFloat {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

.encryption-icon {
  color: rgba(88, 166, 255, 0.9);
  filter: drop-shadow(0 4px 12px rgba(88, 166, 255, 0.3));
  width: 64px;
  height: 64px;
}

.encryption-title {
  font-size: 1.75rem;
  font-weight: 600;
  color: #e6eef6;
  margin: 0 0 1rem 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  letter-spacing: -0.02em;
}

.encryption-description {
  font-size: 1rem;
  color: #cbd5e1;
  line-height: 1.6;
  margin: 0 0 2rem 0;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.encryption-unlock-btn {
  padding: 0.875rem 2rem;
  font-size: 1rem;
  font-weight: 500;
  color: #ffffff;
  background: linear-gradient(
    135deg,
    rgba(88, 166, 255, 0.2),
    rgba(56, 189, 248, 0.15)
  );
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow:
    0 4px 16px rgba(88, 166, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
  font-family: inherit;
  position: relative;
  overflow: hidden;
}

.encryption-unlock-btn::before {
  content: "";
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
  transition: left 0.5s ease;
}

.encryption-unlock-btn:hover {
  transform: translateY(-2px);
  background: linear-gradient(
    135deg,
    rgba(88, 166, 255, 0.3),
    rgba(56, 189, 248, 0.25)
  );
  border-color: rgba(88, 166, 255, 0.5);
  box-shadow:
    0 6px 24px rgba(88, 166, 255, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.encryption-unlock-btn:hover::before {
  left: 100%;
}

.encryption-unlock-btn:active {
  transform: translateY(0);
  box-shadow:
    0 2px 8px rgba(88, 166, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* Password Modal */
.password-modal-overlay {
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
  z-index: 10000;
}

.password-modal {
  padding: 2rem;
  min-width: 400px;
  max-width: 90vw;
  border-radius: 2rem;
}

.password-modal h2 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: var(--text-primary, #f1f5f9);
}

.password-modal-description {
  margin-bottom: 1.5rem;
  color: var(--text-secondary, #cbd5e1);
  font-size: 0.95rem;
  line-height: 1.5;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-secondary, #cbd5e1);
  font-weight: 500;
}

.form-input {
  width: 100%;
  padding: 0.75rem;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #f1f5f9);
  font-size: 1rem;
  font-family: inherit;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent-blue, #38bdf8);
  box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
}

.form-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
}

.error-message {
  padding: 1rem;
  margin-bottom: 1rem;
  color: var(--error, #ef4444);
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md, 8px);
  font-size: 0.9rem;
}

/* Responsive adjustments for encryption overlay */
@media (max-width: 768px) {
  .encryption-overlay-content {
    padding: 2rem 1.5rem;
    max-width: 100%;
  }

  .encryption-title {
    font-size: 1.5rem;
  }

  .encryption-description {
    font-size: 0.9rem;
  }

  .encryption-icon {
    width: 56px;
    height: 56px;
  }

  .encryption-unlock-btn {
    padding: 0.75rem 1.5rem;
    font-size: 0.95rem;
    width: 100%;
    max-width: 280px;
  }

  .password-modal {
    min-width: auto;
    width: 90%;
    padding: 1.5rem;
  }
}
</style>
