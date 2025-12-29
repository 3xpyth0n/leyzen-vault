<template>
  <div class="recent-view-container">
    <template v-if="!showEncryptionOverlay || !isMasterKeyRequired">
      <div class="recent-view">
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

        <AlertModal
          :show="showAlertModal"
          :type="alertModalConfig.type"
          :title="alertModalConfig.title"
          :message="alertModalConfig.message"
          @close="handleAlertModalClose"
          @ok="handleAlertModalClose"
        />

        <ConfirmationModal
          :show="showRevokeConfirm"
          title="Revoke Share Link"
          :message="revokeConfirmMessage"
          confirm-text="Revoke"
          :dangerous="true"
          @confirm="handleRevokeConfirm"
          @close="showRevokeConfirm = false"
        />

        <FileProperties
          :show="showProperties"
          :fileId="propertiesFileId"
          :vaultspaceId="propertiesVaultspaceId"
          @close="
            showProperties = false;
            propertiesFileId = null;
            propertiesVaultspaceId = null;
          "
          @navigate="handleNavigate"
          @action="handlePropertiesAction"
        />

        <FilePreview
          :show="showPreview"
          :fileId="previewFileId"
          :fileName="previewFileName"
          :mimeType="previewMimeType"
          :vaultspaceId="
            previewFileId
              ? recentFiles.find((f) => f.id === previewFileId)
                  ?.vaultspace_id || null
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

        <BatchActions
          v-if="selectedItems.length > 0"
          :selectedItems="selectedItems"
          :availableFolders="[]"
          @delete="handleBatchDelete"
          @download="handleBatchDownload"
          @clear="clearSelection"
        />

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
          <div v-else-if="error" class="error">{{ error }}</div>
          <div v-else-if="recentFiles.length === 0" class="empty-state">
            <p>No recent files</p>
            <p class="empty-hint">
              Files you've recently modified or accessed will appear here
            </p>
          </div>
          <div v-else class="files-list">
            <div class="files-info">
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
              @item-context-menu="handleContextMenu"
            />
          </div>
        </main>
      </div>
    </template>

    <Teleport
      v-if="showEncryptionOverlay && isMasterKeyRequired"
      to="#encryption-overlay-portal"
    >
      <div
        class="encryption-overlay"
        :style="{
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
            Enter your encryption password to decrypt and access your files.
            This password is used to decrypt your files and is not stored on the
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

    <Teleport v-if="showPasswordModal" to="body">
      <div
        class="password-modal-overlay"
        @click="closePasswordModal"
        role="dialog"
        aria-labelledby="password-modal-title"
        aria-modal="true"
      >
        <div class="password-modal-container" @click.stop>
          <div class="password-modal-content">
            <div class="password-modal-header">
              <h2 id="password-modal-title">Enter Encryption Password</h2>
              <button
                @click="closePasswordModal"
                class="password-modal-close"
                :disabled="passwordModalLoading"
                aria-label="Close modal"
              >
                &times;
              </button>
            </div>
            <div class="password-modal-body">
              <p class="password-modal-description">
                Enter your encryption password to access your files. This
                password is used to decrypt your files and is not stored on the
                server.
              </p>
              <div class="form-group">
                <label for="password-modal-password">Password</label>
                <PasswordInput
                  id="password-modal-password"
                  v-model="passwordModalPassword"
                  placeholder="Enter your encryption password"
                  @keyup.enter="handlePasswordSubmit"
                  :disabled="passwordModalLoading"
                  autofocus
                />
              </div>
              <div v-if="passwordModalError" class="password-modal-error">
                {{ passwordModalError }}
              </div>
            </div>
            <div class="password-modal-footer">
              <button
                @click="closePasswordModal"
                class="password-modal-btn password-modal-btn-cancel"
                :disabled="passwordModalLoading"
              >
                Cancel
              </button>
              <button
                @click="handlePasswordSubmit"
                class="password-modal-btn password-modal-btn-unlock"
                :disabled="passwordModalLoading || !passwordModalPassword"
              >
                {{ passwordModalLoading ? "Processing..." : "Unlock" }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, computed } from "vue";
import { useRouter } from "vue-router";
import { normalizeMimeType } from "../utils/mimeType";
import { files, vaultspaces, config } from "../services/api";
import { useAuthStore } from "../store/auth";
import FileListView from "../components/FileListView.vue";
import FileProperties from "../components/FileProperties.vue";
import FilePreview from "../components/FilePreview.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import BatchActions from "../components/BatchActions.vue";
import CustomSelect from "../components/CustomSelect.vue";
import { clipboardManager } from "../utils/clipboard";
import { decryptFileKey, decryptFile } from "../services/encryption.js";
import { useFileViewComposable } from "../composables/useFileViewComposable.js";
import PasswordInput from "../components/PasswordInput.vue";
import { zipFiles, generateZipFileName } from "../services/zipService.js";
import { showShareModal } from "../composables/useShareModal";
import {
  getUserMasterKey,
  decryptVaultSpaceKeyForUser,
  cacheVaultSpaceKey,
  getCachedVaultSpaceKey,
  createVaultSpaceKey,
} from "../services/keyManager.js";
import {
  getFileKey as getFileKeyFromStorage,
  storeFileKey,
} from "../services/fileKeyStorage.js";
import { arrayToBase64url, base64urlToArray } from "../services/encryption.js";

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
    const authStore = useAuthStore();
    const loading = ref(false);
    const error = ref(null);
    const recentFiles = ref([]);
    // Load days filter from localStorage or default to 30
    const loadDaysFilterFromStorage = () => {
      try {
        const saved = localStorage.getItem("recentViewDaysFilter");
        if (saved) {
          const value = parseInt(saved, 10);
          // Validate that the value is one of the valid options
          const validValues = [1, 7, 30, 90];
          if (validValues.includes(value)) {
            return value;
          }
        }
      } catch (err) {
        // Ignore localStorage errors
      }
      return 30; // Default value
    };

    const daysFilter = ref(loadDaysFilterFromStorage());
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
    const vaultspaceKeys = ref({});

    const daysOptions = [
      { value: 1, label: "Last 24 hours" },
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
      // Save to localStorage
      try {
        localStorage.setItem(
          "recentViewDaysFilter",
          daysFilter.value.toString(),
        );
      } catch (err) {
        // Ignore localStorage errors
      }
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
            if (vaultspaceKeys.value[vaultspaceId]) {
              return; // Already loaded
            }

            // Always decrypt from server with extractable: true
            // Even if key is cached, we need it to be extractable for file key decryption
            const vaultspaceKeyData = await vaultspaces.getKey(vaultspaceId);

            if (!vaultspaceKeyData) {
              // Key doesn't exist, create it
              const currentUser = await authStore.fetchCurrentUser();
              const { encryptedKey } = await createVaultSpaceKey(userMasterKey);
              await vaultspaces.share(
                vaultspaceId,
                currentUser.id,
                encryptedKey,
              );
              const vaultspaceKey = await decryptVaultSpaceKeyForUser(
                userMasterKey,
                encryptedKey,
                true, // extractable to use for file key decryption
              );
              cacheVaultSpaceKey(vaultspaceId, vaultspaceKey);
              vaultspaceKeys.value[vaultspaceId] = vaultspaceKey;
            } else {
              // Decrypt VaultSpace key with user master key
              try {
                const vaultspaceKey = await decryptVaultSpaceKeyForUser(
                  userMasterKey,
                  vaultspaceKeyData.encrypted_key,
                  true, // extractable to use for file key decryption
                );
                cacheVaultSpaceKey(vaultspaceId, vaultspaceKey);
                vaultspaceKeys.value[vaultspaceId] = vaultspaceKey;
              } catch (decryptErr) {
                // Decryption failed - VaultSpace key was encrypted with a different master key
                // Silently fail for this vaultspace
              }
            }
          } catch (err) {
            // Silently fail for individual vaultspaces
          }
        },
      );

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
      isSelected,
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

    const handleNavigate = (item) => {
      if (!item) return;

      // Logic for navigation:
      // 1. Root: navigate to root, no selection
      // 2. Folder/File: navigate to its PARENT and SELECT this item
      const vaultspaceId = item.vaultspace_id || propertiesVaultspaceId.value;

      if (item.isRoot) {
        router.push(`/vaultspace/${vaultspaceId}`);
        return;
      }

      // Determine parent folder ID
      const parentId =
        item.folder_id || item.parent_id || item.parentId || null;

      window.pendingSelection = {
        id: item.id,
        parentId: parentId,
        vaultspaceId: vaultspaceId,
      };

      // Navigate to the parent folder in VaultSpaceView
      const query = parentId ? { folder: parentId } : {};
      router.push({
        path: `/vaultspace/${vaultspaceId}`,
        query,
      });
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

        const index = recentFiles.value.findIndex((f) => f.id === item.id);
        if (index >= 0) {
          recentFiles.value[index].original_name = newName;
        }
        editingItemId.value = null;
      } catch (err) {
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

        if (window.Notifications) {
          window.Notifications.success(
            `${itemType} moved to trash successfully`,
          );
        }
      } catch (err) {
        deleteError.value = err.message || "Failed to move to trash";
        // Don't close modal on error so user can see the error
      } finally {
        deleting.value = false;
      }
    };

    const handleContextMenu = (item, event) => {
      event.preventDefault();
      showFileProperties(item.id, item.vaultspace_id);
    };

    const handleFileAction = async (action, item, newName = null) => {
      if (action === "star") {
        try {
          await files.toggleStar(item.id);
          await loadRecent(); // Reload to update star status
        } catch (err) {}
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
            true, // extractable to store it
          );

          // Store file key in IndexedDB for future use (e.g., sharing)
          try {
            const exportedKey = await crypto.subtle.exportKey("raw", fileKey);
            const keyArray = new Uint8Array(exportedKey);
            const keyBase64 = arrayToBase64url(keyArray);
            await storeFileKey(item.id, keyBase64);
          } catch (e) {
            // Silently fail if storage fails
          }

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
          showAlert({
            type: "error",
            title: "Error",
            message: "Download failed: " + err.message,
          });
        }
      } else if (action === "delete") {
        pendingDeleteFile.value = item;
        pendingDeleteFileName.value = item.original_name;
        showDeleteConfirm.value = true;
      } else if (action === "rename") {
        if (newName) {
          // Save rename with new name
          try {
            await files.rename(item.id, newName);

            const index = recentFiles.value.findIndex((f) => f.id === item.id);
            if (index >= 0) {
              recentFiles.value[index].original_name = newName;
            }
            editingItemId.value = null;
          } catch (err) {
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
        // This helps retrieve file key, but modal should open even without it
        let vaultspaceKey = null;

        try {
          const userMasterKey = await getUserMasterKey();
          if (userMasterKey) {
            try {
              const vaultspaceKeyData = await vaultspaces.getKey(
                item.vaultspace_id,
              );
              if (!vaultspaceKeyData) {
                // Key doesn't exist, create it
                const currentUser = await authStore.fetchCurrentUser();
                const { encryptedKey } =
                  await createVaultSpaceKey(userMasterKey);
                await vaultspaces.share(
                  item.vaultspace_id,
                  currentUser.id,
                  encryptedKey,
                );
                vaultspaceKey = await decryptVaultSpaceKeyForUser(
                  userMasterKey,
                  encryptedKey,
                  true, // extractable to use for file key decryption
                );
              } else {
                // Decrypt VaultSpace key with user master key
                vaultspaceKey = await decryptVaultSpaceKeyForUser(
                  userMasterKey,
                  vaultspaceKeyData.encrypted_key,
                  true, // extractable to use for file key decryption
                );
              }

              // Cache the key for future use
              cacheVaultSpaceKey(item.vaultspace_id, vaultspaceKey);
              vaultspaceKeys.value[item.vaultspace_id] = vaultspaceKey;
            } catch (e) {
              console.warn("Failed to load vaultspace key for sharing:", e);
              // Continue without key - modal should still open
            }
          }
        } catch (e) {
          console.warn("Failed to get user master key for sharing:", e);
          // Continue without key - modal should still open
        }

        try {
          const safeVaultspaceKey =
            vaultspaceKey !== undefined ? vaultspaceKey : null;
          await showShareModal(
            item.id,
            "file",
            item.vaultspace_id,
            safeVaultspaceKey,
          );
        } catch (err) {
          console.error("Failed to open share modal:", err);
          showAlert({
            type: "error",
            title: "Error",
            message: "Failed to open share dialog.",
          });
        }
      } else if (action === "properties") {
        showFileProperties(item.id, item.vaultspace_id);
      } else if (action === "preview") {
        // Clear selection when opening preview
        clearSelection();
        if (window.selectionManager) {
          window.selectionManager.deselectAll();
          window.selectionManager.updateUI();
        }

        previewFileId.value = item.id;
        previewFileName.value = item.original_name || item.name || "File";
        previewMimeType.value = normalizeMimeType(
          previewFileName.value,
          item.mime_type || "",
        );
        showPreview.value = true;
      } else if (action === "copy") {
        handleCopyAction(item);
      } else if (action === "cut") {
        if (clipboardManager) {
          clipboardManager.cut([item]);
          if (window.Notifications) {
            window.Notifications.success("Ready to move");
          }
        }
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
      return [];
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
      if (clipboardManager) {
        clipboardManager.cut([item]);
        if (window.Notifications) {
          window.Notifications.success("Ready to move");
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
      if (clipboardManager) {
        clipboardManager.copy([item]);
        if (window.Notifications) {
          window.Notifications.success("Copied to clipboard");
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
      // Filter out directories
      const filesToDownload = items.filter(
        (item) => item.mime_type !== "application/x-directory",
      );

      if (filesToDownload.length === 0) {
        showAlert({
          type: "error",
          title: "Error",
          message: "No files selected for download",
        });
        return;
      }

      if (filesToDownload.length === 1) {
        const item = filesToDownload[0];
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
            true, // extractable to store it
          );

          // Store file key in IndexedDB for future use (e.g., sharing)
          try {
            const exportedKey = await crypto.subtle.exportKey("raw", fileKey);
            const keyArray = new Uint8Array(exportedKey);
            const keyBase64 = arrayToBase64url(keyArray);
            await storeFileKey(item.id, keyBase64);
          } catch (e) {
            // Silently fail if storage fails
          }

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
          showAlert({
            type: "error",
            title: "Download Error",
            message: `Failed to download ${item.original_name}: ${err.message}`,
          });
        }
        clearSelection();
        return;
      }

      // Multiple files: create ZIP
      try {
        // Get timezone from config
        const configData = await config.getConfig();
        const timezone = configData.timezone || "UTC";

        // Generate ZIP filename
        const zipFileName = generateZipFileName(timezone);

        // Create ZIP with getter function for vaultspace keys
        const getVaultspaceKey = async (vaultspaceId) => {
          const key = await window.keyManager?.getVaultSpaceKey(vaultspaceId);
          if (!key) {
            throw new Error(
              `VaultSpace key not found for vaultspace ${vaultspaceId}. Please refresh the page.`,
            );
          }
          return key;
        };

        const zipBlob = await zipFiles(
          filesToDownload,
          (fileItem) => fileItem.vaultspace_id,
          getVaultspaceKey,
          null,
          timezone,
        );

        // Download ZIP
        const url = URL.createObjectURL(zipBlob);
        const a = document.createElement("a");
        a.href = url;
        a.download = zipFileName;
        a.click();
        URL.revokeObjectURL(url);
      } catch (err) {
        showAlert({
          type: "error",
          title: "Download Failed",
          message: "Failed to create ZIP: " + err.message,
        });
      }
      clearSelection();
    };

    onMounted(async () => {
      await checkEncryptionAccess();

      // Load recent files
      loadRecent();

      // Expose showConfirmationModal for modals to use
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
      handleNavigate,
      loadRecent,
      refreshRecent,
      handleItemClick,
      handleFileAction,
      handleRename,
      handleDeleteConfirm,
      handleContextMenu,
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
      handleSelectionChange,
      handleViewChange,
      clearSelection,
      handlePasswordSubmit,
      closePasswordModal,
      openPasswordModal,
      handleBatchDelete,
      handleBatchDownload,
      vaultspaceKeys,
    };
  },
};
</script>

<style scoped>
.recent-view {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  padding: 1.5rem 0;
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
  align-items: center;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.filter-group label {
  color: var(--text-secondary, #a9b7aa);
  font-size: 0.9rem;
}

.view-main {
  flex: 1;
  display: flex;
  flex-direction: column;
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

.empty-hint {
  margin-top: 1rem;
  font-size: 0.9rem;
  color: var(--text-muted, #a9b7aa);
}

.files-info {
  padding: 1rem;
  margin-bottom: 1rem;
}

/* Encryption Overlay (Glassmorphic) */
.encryption-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    140deg,
    rgba(0, 66, 37, 0.08),
    rgba(1, 10, 0, 0.12)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid var(--border-color); /* Match main-content border */
  border-radius: 1rem; /* Match main-content border-radius */
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
  color: rgba(0, 66, 37, 0.9);
  filter: drop-shadow(0 4px 12px rgba(0, 66, 37, 0.3));
  width: 64px;
  height: 64px;
}

.encryption-title {
  font-size: 1.75rem;
  font-weight: 600;
  color: #a9b7aa;
  margin: 0 0 1rem 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  letter-spacing: -0.02em;
}

.encryption-description {
  font-size: 1rem;
  color: #a9b7aa;
  line-height: 1.6;
  margin: 0 0 2rem 0;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.encryption-unlock-btn {
  padding: 0.875rem 2rem;
  font-size: 1rem;
  font-weight: 500;
  color: #a9b7aa;
  background: linear-gradient(
    135deg,
    rgba(0, 66, 37, 0.2),
    rgba(0, 66, 37, 0.15)
  );
  backdrop-filter: blur(20px) saturate(150%);
  -webkit-backdrop-filter: blur(20px) saturate(150%);
  border: 1px solid rgba(0, 66, 37, 0.3);

  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
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
    rgba(0, 66, 37, 0.3),
    rgba(0, 66, 37, 0.25)
  );
  border-color: rgba(0, 66, 37, 0.5);
  box-shadow:
    0 6px 24px rgba(0, 66, 37, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.15);
}

.encryption-unlock-btn:hover::before {
  left: 100%;
}

.encryption-unlock-btn:active {
  transform: translateY(0);
  box-shadow:
    0 2px 8px rgba(0, 66, 37, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* Password Modal */
.password-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
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

.password-modal-container {
  position: relative;
  width: 100%;
  max-width: 480px;
  background: var(--bg-modal);
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

.password-modal-content {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 0;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.password-modal-content::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
}

.password-modal-header {
  padding: 2rem 2rem 1.5rem 2rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
}

.password-modal-header h2 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
  flex: 1;
}

.password-modal-close {
  background: none;
  border: none;
  color: #a9b7aa;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.password-modal-close:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  color: #a9b7aa;
}

.password-modal-close:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-modal-body {
  padding: 2rem;
  flex: 1;
}

.password-modal-description {
  margin: 0 0 1.5rem 0;
  color: #a9b7aa;
  font-size: 1rem;
  line-height: 1.6;
}

.password-modal-body .form-group {
  margin-bottom: 1.5rem;
}

.password-modal-body .form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #a9b7aa;
  font-weight: 500;
  font-size: 0.95rem;
}

.password-modal-body .form-input {
  width: 100%;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid #004225;
  color: var(--slate-grey);
  font-size: 0.95rem;
  font-family: inherit;
  box-sizing: border-box;
  transition: all 0.2s ease;
}

.password-modal-body .form-input:focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: 0 0 0 3px rgba(88, 166, 255, 0.1);
}

.password-modal-body .form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.password-modal-body .form-input::placeholder {
  color: var(--slate-grey);
}

.password-modal-error {
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  color: #fca5a5;
  font-size: 0.9rem;
  margin-top: 1rem;
  line-height: 1.5;
}

.password-modal-footer {
  padding: 1.5rem 2rem 2rem 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.password-modal-btn {
  padding: 0.75rem 1.5rem;
  border: none;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 100px;
  font-family: inherit;
}

.password-modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.password-modal-btn-cancel {
  background: var(--bg-primary);
  color: #a9b7aa;
  border: 1px solid var(--slate-grey);
}

.password-modal-btn-cancel:hover:not(:disabled) {
  background: var(--bg-secondary);
}

.password-modal-btn-unlock {
  background: transparent;
  color: #a9b7aa;
  border: 1px solid var(--ash-grey);
}

.password-modal-btn-unlock:hover:not(:disabled) {
  background: var(--accent);
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

  .password-modal-container {
    max-width: 100%;
    margin: 0 1rem;
  }

  .password-modal-header,
  .password-modal-body,
  .password-modal-footer {
    padding-left: 1.5rem;
    padding-right: 1.5rem;
  }

  .password-modal-header {
    padding-top: 1.5rem;
  }

  .password-modal-footer {
    padding-bottom: 1.5rem;
    flex-direction: column-reverse;
  }

  .password-modal-btn {
    width: 100%;
  }
}
</style>
