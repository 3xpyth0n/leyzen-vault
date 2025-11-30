<template>
  <div>
    <header
      v-if="!showEncryptionOverlay || !isMasterKeyRequired"
      class="view-header"
    >
      <button @click="$router.push('/dashboard')" class="btn btn-back">
        ← Back
      </button>
      <h1>{{ vaultspace?.name || "Loading..." }}</h1>
      <div class="header-actions">
        <button @click="createFolderDirect" class="btn btn-primary">
          New Folder
        </button>
        <button @click="handleUploadClick" class="btn btn-primary">
          Upload File
        </button>
      </div>
    </header>

    <main
      v-if="!showEncryptionOverlay || !isMasterKeyRequired"
      class="view-main"
    >
      <!-- Breadcrumbs -->
      <!-- Search Bar -->
      <div class="search-container">
        <SearchBar
          :vaultspaceId="$route.params.id"
          :parentId="currentParentId"
          placeholder="Search files and folders..."
          @result-click="handleSearchResultClick"
        />
      </div>

      <div
        v-if="breadcrumbs.length > 0 || currentParentId"
        class="breadcrumbs glass"
      >
        <button @click="navigateToFolder(null)" class="breadcrumb-link">
          {{ vaultspace?.name || "Home" }}
        </button>
        <template v-if="breadcrumbs.length > 0">
          <template v-for="(crumb, index) in breadcrumbs" :key="crumb.id">
            <span class="breadcrumb-separator">/</span>
            <button
              v-if="index < breadcrumbs.length - 1"
              @click="navigateToFolder(crumb.id)"
              class="breadcrumb-link"
            >
              {{ crumb.name }}
            </button>
            <span v-else class="breadcrumb-active">
              {{ crumb.name }}
            </span>
          </template>
        </template>
        <template v-else-if="currentParentId">
          <span class="breadcrumb-separator">/</span>
          <span class="breadcrumb-active">Loading...</span>
        </template>
      </div>

      <div v-if="loading" class="loading">Loading files...</div>
      <div v-else-if="error" class="error glass">{{ error }}</div>

      <div v-else class="files-list glass">
        <div
          v-if="folders.length === 0 && filesList.length === 0"
          class="empty-state"
        >
          <p>No files or folders in this location</p>
          <div class="empty-actions">
            <button @click="createFolderDirect" class="btn btn-primary">
              Create Folder
            </button>
            <button @click="handleUploadClick" class="btn btn-primary">
              Upload File
            </button>
          </div>
        </div>

        <!-- File List View Component -->
        <FileListView
          v-else
          :key="fileListKey"
          :folders="folders"
          :files="filesList"
          :selectedItems="selectedItems"
          :viewMode="viewMode"
          :editingItemId="editingItemId"
          :newlyCreatedItemId="newlyCreatedItemIdForAnimation"
          :vaultspaceId="$route.params.id"
          @view-change="handleViewChange"
          @item-click="handleItemClick"
          @action="handleFileAction"
          @selection-change="handleSelectionChange"
          @item-context-menu="handleContextMenu"
          @rename="handleInlineRename"
          @drag-start="handleDragStart"
          @drag-over="handleDragOver"
          @drag-leave="handleDragLeave"
          @drop="handleDrop"
        />
      </div>
    </main>

    <!-- Upload Progress Bar (Sticky at bottom) -->
    <Teleport to="body">
      <ProgressBar
        v-if="uploading && uploadProgress !== null"
        :progress="uploadProgress"
        :speed="uploadSpeed"
        :time-remaining="uploadTimeRemaining"
        :file-name="uploadFileName"
        :status="uploadCancelled ? 'Cancelled' : 'Uploading...'"
        :sticky="true"
        :on-cancel="uploadCancelled ? null : handleUploadCancel"
      />
    </Teleport>

    <!-- Download Progress Bar (Sticky at bottom) -->
    <Teleport to="body">
      <ProgressBar
        v-if="downloading && downloadProgress !== null"
        :progress="downloadProgress"
        :speed="downloadSpeed"
        :time-remaining="downloadTimeRemaining"
        :file-name="downloadFileName"
        status="Downloading..."
        :sticky="true"
      />
    </Teleport>

    <!-- ZIP Progress Bar (Sticky at bottom) -->
    <Teleport to="body">
      <ProgressBar
        v-if="zipping && zipProgress !== null"
        :progress="zipProgress"
        :file-name="zipMessage"
        status="Zipping folder..."
        :sticky="true"
      />
    </Teleport>

    <!-- Extract Progress Bar (Sticky at bottom) -->
    <Teleport to="body">
      <ProgressBar
        v-if="extracting && extractProgress !== null"
        :progress="extractProgress"
        :file-name="extractMessage"
        status="Extracting ZIP..."
        :sticky="true"
      />
    </Teleport>

    <!-- Batch Actions Bar -->
    <BatchActions
      v-if="selectedItems.length > 0"
      :selectedItems="selectedItems"
      :availableFolders="allFolders"
      @delete="handleBatchDelete"
      @download="handleBatchDownload"
      @clear="clearSelection"
    />
  </div>

  <!-- Hidden file input for direct upload (programmatically triggered) -->
  <input
    type="file"
    @change="handleFileSelect"
    ref="fileInput"
    class="file-input-hidden"
    multiple
  />

  <!-- Delete Confirmation Modal -->
  <ConfirmationModal
    :show="showDeleteConfirmModal"
    title="Move to Trash"
    :message="getDeleteMessage()"
    confirm-text="Move to Trash"
    :dangerous="true"
    :disabled="deleting"
    @confirm="confirmDelete"
    @close="
      if (!deleting) {
        showDeleteConfirmModal = false;
        deleteError = null;
      }
    "
  />

  <!-- Password Modal for SSO Users -->
  <Teleport to="body">
    <div
      v-if="showPasswordModal"
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
              You need to enter your encryption password to access this
              VaultSpace. This password is used to decrypt your files and is not
              stored on the server.
            </p>
            <div class="form-group">
              <label for="password-modal-password">Password</label>
              <PasswordInput
                id="password-modal-password"
                v-model="passwordModalPassword"
                placeholder="Enter your encryption password"
                :disabled="passwordModalLoading"
                @keyup.enter="handlePasswordModalSubmit"
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
              @click="handlePasswordModalSubmit"
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

  <!-- Alert Modal (for better UX) -->
  <AlertModal
    :show="showAlertModal"
    :type="alertModalConfig.type"
    :title="alertModalConfig.title"
    :message="alertModalConfig.message"
    @close="handleAlertModalClose"
    @ok="handleAlertModalClose"
  />

  <!-- Conflict Resolution Modal -->
  <ConflictResolutionModal
    :show="showConflictModal"
    :title="conflictData?.title || 'File Already Exists'"
    :message="conflictData?.message || 'A file with this name already exists.'"
    :show-apply-to-all="conflictData?.showApplyToAll || false"
    :remaining-count="conflictData?.remainingCount"
    @replace="handleConflictReplace"
    @keep-both="handleConflictKeepBoth"
    @skip="handleConflictSkip"
    @close="handleConflictClose"
  />

  <!-- File Properties Modal -->
  <FileProperties
    :show="showProperties"
    :fileId="propertiesFileId"
    :vaultspaceId="$route.params.id"
    @close="
      showProperties = false;
      propertiesFileId = null;
    "
  />

  <!-- File Preview Modal -->
  <FilePreview
    :show="showPreview"
    :fileId="previewFileId"
    :fileName="previewFileName"
    :mimeType="previewMimeType"
    :vaultspaceId="$route.params.id"
    @close="
      showPreview = false;
      previewFileId = null;
      previewFileName = '';
      previewMimeType = '';
    "
    @download="handlePreviewDownload"
  />

  <!-- Encryption Overlay (Glassmorphic) - Fixed position covering page-content -->
  <Teleport to="body">
    <div
      v-if="showEncryptionOverlay && isMasterKeyRequired"
      class="encryption-overlay"
      :style="{
        ...overlayStyle,
        'pointer-events': showPasswordModal ? 'none' : 'auto',
        'z-index': '9999',
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
          @click.stop.prevent="openPasswordModal"
          @mousedown.stop
          @mouseup.stop
          class="encryption-unlock-btn"
          type="button"
          style="
            pointer-events: auto !important;
            z-index: 10001 !important;
            position: relative !important;
          "
        >
          Unlock Files
        </button>
      </div>
    </div>
  </Teleport>

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
</template>

<script>
import { files, vaultspaces, auth } from "../services/api";
import BatchActions from "../components/BatchActions.vue";
import DragDropUpload from "../components/DragDropUpload.vue";
import FileListView from "../components/FileListView.vue";
import FileProperties from "../components/FileProperties.vue";
import FilePreview from "../components/FilePreview.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import ProgressBar from "../components/ProgressBar.vue";
import SearchBar from "../components/SearchBar.vue";
import { clipboardManager } from "../utils/clipboard";
import {
  generateFileKey,
  encryptFile,
  encryptFileKey,
  decryptFile,
  decryptFileKey,
} from "../services/encryption";
import {
  getUserMasterKey,
  decryptVaultSpaceKeyForUser,
  cacheVaultSpaceKey,
  getCachedVaultSpaceKey,
  createVaultSpaceKey,
  clearUserMasterKey,
  getStoredSalt,
  initializeUserMasterKey,
} from "../services/keyManager";
import { debounce } from "../utils/debounce";
import { folderPicker } from "../utils/FolderPicker";
import { logger } from "../utils/logger.js";
import AlertModal from "../components/AlertModal.vue";
import ConflictResolutionModal from "../components/ConflictResolutionModal.vue";
import { zipFolder, extractZip } from "../services/zipService.js";
import PasswordInput from "../components/PasswordInput.vue";

export default {
  name: "VaultSpaceView",
  components: {
    BatchActions,
    DragDropUpload,
    FileListView,
    FileProperties,
    FilePreview,
    ConfirmationModal,
    SearchBar,
    ProgressBar,
    AlertModal,
    ConflictResolutionModal,
    PasswordInput,
  },
  data() {
    return {
      vaultspace: null,
      files: [],
      folders: [],
      filesList: [],
      currentParentId: null,
      breadcrumbs: [], // Array of { id, name } for breadcrumb path
      loading: false,
      error: null,
      showDeleteConfirmModal: false,
      showAlertModal: false,
      alertModalConfig: {
        type: "error",
        title: "Error",
        message: "",
      },
      uploading: false,
      uploadProgress: null,
      uploadSpeed: 0,
      uploadTimeRemaining: null,
      uploadFileName: "",
      uploadCancelFunctions: [], // Array of cancel functions for active uploads
      uploadCancelled: false, // Flag to track if upload was cancelled
      uploadCancellationMessageShown: false, // Flag to track if cancellation message was shown
      downloading: false,
      _folderCreateRetryCount: 0,
      downloadProgress: null,
      downloadSpeed: 0,
      downloadTimeRemaining: null,
      downloadFileName: "",
      deleting: false,
      zipping: false,
      zipProgress: null,
      zipMessage: "",
      extracting: false,
      extractProgress: null,
      extractMessage: "",
      selectedFiles: [], // Array of File objects for upload
      uploadedFileIds: [], // Array of file IDs uploaded in current batch (for verification)
      itemToDelete: null,
      uploadError: null,
      deleteError: null,
      vaultspaceKey: null, // Decrypted VaultSpace key (stored in memory only)
      selectedItems: [], // Array of selected file/folder objects
      viewMode: "grid", // 'grid' or 'list'
      showProperties: false,
      propertiesFileId: null,
      showPreview: false,
      previewFileId: null,
      previewFileName: "",
      previewMimeType: "",
      editingItemId: null,
      showRevokeConfirm: false,
      revokeConfirmMessage: "",
      newlyCreatedFolderId: null,
      newlyCreatedFileIds: [], // Array of file IDs that were just uploaded (for animation)
      pendingRevokeCallback: null,
      showPasswordModal: false,
      passwordModalPassword: "",
      passwordModalError: "",
      passwordModalLoading: false,
      showEncryptionOverlay: false,
      isMasterKeyRequired: false,
      overlayStyle: {},
      showConflictModal: false,
      conflictData: null,
      conflictApplyToAll: false,
      conflictResolution: null,
      pendingUploadFile: null,
      pendingUploadIndex: -1,
      pendingUploadFiles: [],
      pendingFolderName: null,
      pendingRenameItem: null,
      pendingRenameNewName: null,
    };
  },
  created() {
    // Create debounced version of loadFiles to preserve 'this' context
    this.debouncedLoadFiles = debounce((parentId = null) => {
      this.loadFilesInternal(parentId);
    }, 300);
  },
  async mounted() {
    // Check if user master key is available first
    const userMasterKey = await getUserMasterKey();
    if (!userMasterKey) {
      // Check if salt exists - indicates master key is not available
      const storedSalt = getStoredSalt();
      if (storedSalt) {
        // User is authenticated but master key is not available
        // User needs to re-enter password to access encrypted content
        // Don't logout - keep JWT token so user doesn't need to re-authenticate
        console.warn(
          "Master key lost from memory but salt exists. This is normal after page refresh.",
        );
        console.warn(
          "User needs to re-enter password to access encrypted content.",
        );
        // Show error message but don't redirect - user can still navigate
        this.showAlert({
          type: "error",
          title: "Session Expired",
          message:
            "Your encryption session has expired. Please log in again to access encrypted content.",
        });
        // Don't load encrypted content, but don't disconnect user
        // User can navigate to other pages or go to login to re-enter password
        return;
      } else {
        // No salt and no master key
        // Check if user is still authenticated (could be SSO user without password)
        try {
          const currentUser = await auth.getCurrentUser();
          if (currentUser) {
            // User is authenticated but has no master key or salt
            // This is normal for SSO users - show encryption overlay instead of modal
            // Load VaultSpace metadata but show overlay to indicate encryption is needed
            this.showEncryptionOverlay = true;
            this.isMasterKeyRequired = true;
            // Still load VaultSpace metadata (non-encrypted info)
            await this.loadVaultSpace();
            // Calculate overlay position after DOM is ready
            this.$nextTick(() => {
              this.calculateOverlayPosition();
              // Recalculate on window resize
              const resizeHandler = () => this.calculateOverlayPosition();
              window.addEventListener("resize", resizeHandler);
              this._overlayResizeHandler = resizeHandler;

              // Recalculate when sidebar toggles (observe sidebar width changes)
              this.observeSidebarChanges();

              // Protect overlay from being removed via DevTools
              this.protectOverlay();
            });
            return;
          }
        } catch (err) {
          // User is not authenticated - redirect to login
          console.warn(
            "User master key not available and user is not authenticated. Redirecting to login.",
          );
          this.showAlert({
            type: "error",
            title: "Authentication Required",
            message: "You must be logged in to access this VaultSpace.",
          });
          setTimeout(() => {
            auth.logout();
            this.$router.push("/login");
          }, 2000);
          return;
        }
      }
    }

    // Master key is available, proceed with loading
    // Load view mode preference from localStorage
    const savedViewMode = localStorage.getItem("fileViewMode_vaultspace");
    if (savedViewMode === "grid" || savedViewMode === "list") {
      this.viewMode = savedViewMode;
    }

    await this.loadVaultSpace();
    await this.loadVaultSpaceKey();

    // Check if folder parameter is in URL query string
    // This handles direct navigation to a folder (e.g., from favorites)
    const folderIdFromQuery = this.$route.query.folder;
    if (folderIdFromQuery) {
      // Load the specific folder immediately (bypass debounce for initial load)
      // Set currentParentId first to ensure state is correct
      this.currentParentId = folderIdFromQuery;
      await this.loadFilesInternal(folderIdFromQuery, false);
    } else {
      // Load root folder immediately (bypass debounce for initial load)
      this.currentParentId = null;
      await this.loadFilesInternal(null, false);
    }

    // Setup keyboard shortcuts
    this.setupKeyboardShortcuts();

    // Expose showConfirmationModal for sharing.js to use
    window.showConfirmationModal = (options) => {
      this.revokeConfirmMessage =
        options.message || "Are you sure you want to proceed?";
      this.pendingRevokeCallback = options.onConfirm || null;
      this.showRevokeConfirm = true;
    };
  },
  beforeUnmount() {
    // Deselect all items when component is unmounted
    this.clearSelection();
    if (window.selectionManager) {
      window.selectionManager.deselectAll();
    }

    // Cleanup resize handler
    if (this._overlayResizeHandler) {
      window.removeEventListener("resize", this._overlayResizeHandler);
    }
    // Cleanup resize observers
    if (this._sidebarResizeObserver) {
      this._sidebarResizeObserver.disconnect();
    }
    if (this._mainContentResizeObserver) {
      this._mainContentResizeObserver.disconnect();
    }
    if (this._pageContentResizeObserver) {
      this._pageContentResizeObserver.disconnect();
    }
    // Cleanup overlay protection
    if (this._overlayProtectionInterval) {
      clearInterval(this._overlayProtectionInterval);
    }
    if (this._overlayMutationObserver) {
      this._overlayMutationObserver.disconnect();
    }
    // Cleanup keyboard shortcuts
    if (this._keyboardShortcutHandler) {
      document.removeEventListener("keydown", this._keyboardShortcutHandler);
    }
    // Cleanup global function
    if (window.showConfirmationModal) {
      delete window.showConfirmationModal;
    }
  },
  computed: {
    allFolders() {
      // Return all folders for move destination selection
      return this.folders;
    },
    fileListKey() {
      // Generate a stable key that only changes on important transitions:
      // - When changing folders (currentParentId changes)
      // - When transitioning from empty to non-empty (or vice versa)
      // This prevents the component from being recreated on every file upload
      const hasItems = this.folders.length > 0 || this.filesList.length > 0;
      return `file-list-${hasItems ? "has-items" : "empty"}-${this.currentParentId || "root"}`;
    },
    newlyCreatedItemIdForAnimation() {
      // Return the newly created folder ID if available, otherwise the array of uploaded file IDs
      // This is used to trigger the animation for newly created items
      // FileListView now supports both single ID and array of IDs
      if (this.newlyCreatedFolderId) {
        return this.newlyCreatedFolderId;
      }
      if (this.newlyCreatedFileIds && this.newlyCreatedFileIds.length > 0) {
        // Return array if multiple files, single ID if only one
        return this.newlyCreatedFileIds.length === 1
          ? this.newlyCreatedFileIds[0]
          : this.newlyCreatedFileIds;
      }
      return null;
    },
  },
  watch: {
    "$route.query.folder": {
      handler(newFolderId, oldFolderId) {
        // Deselect all items when folder parameter changes
        this.clearSelection();
        if (window.selectionManager) {
          window.selectionManager.deselectAll();
        }

        // Load files when folder parameter changes
        // This handles browser back/forward navigation and external navigation (from starred/recent)
        if (this.vaultspace) {
          const folderId = newFolderId || null;
          // Only load if folder ID actually changed to avoid unnecessary reloads
          // Also check if currentParentId doesn't match to avoid double loading
          // Skip if this is the initial load (oldFolderId is undefined and we're already loading)
          if (
            newFolderId !== oldFolderId &&
            this.currentParentId !== folderId &&
            oldFolderId !== undefined
          ) {
            // Use loadFilesInternal directly to bypass debounce for route changes
            this.loadFilesInternal(folderId, false);
          }
        }
      },
      immediate: false,
    },
    "$route.path": {
      handler(newPath, oldPath) {
        // Deselect all items when route path changes (e.g., navigating to a different page)
        if (newPath !== oldPath && oldPath !== undefined) {
          this.clearSelection();
          if (window.selectionManager) {
            window.selectionManager.deselectAll();
          }
        }
      },
      immediate: false,
    },
  },
  methods: {
    async loadVaultSpace() {
      try {
        this.vaultspace = await vaultspaces.get(this.$route.params.id);
      } catch (err) {
        this.error = err.message;
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to load VaultSpace: " + err.message,
        });
      }
    },

    async loadVaultSpaceKey() {
      try {
        // Check if VaultSpace key is already cached
        const cachedKey = getCachedVaultSpaceKey(this.$route.params.id);
        if (cachedKey) {
          this.vaultspaceKey = cachedKey;
          return;
        }

        // Get user master key from key manager
        const userMasterKey = await getUserMasterKey();
        if (!userMasterKey) {
          // Check if salt exists in sessionStorage - this indicates a lost session
          const storedSalt = getStoredSalt();
          if (storedSalt) {
            console.warn(
              "Master key lost from memory but salt exists in sessionStorage. Session may have expired.",
            );
          } else {
            console.warn(
              "User master key not available, VaultSpace key will be loaded on demand",
            );
          }
          return;
        }

        // Try to get encrypted VaultSpace key from server
        const vaultspaceKeyData = await vaultspaces.getKey(
          this.$route.params.id,
        );

        if (!vaultspaceKeyData) {
          // Key doesn't exist, create it
          const currentUser = await auth.getCurrentUser();

          // Create VaultSpace key and store it
          const { encryptedKey } = await createVaultSpaceKey(userMasterKey);

          // Store the encrypted key on the server (share with self)
          await vaultspaces.share(
            this.$route.params.id,
            currentUser.id,
            encryptedKey,
          );

          // Decrypt and cache
          this.vaultspaceKey = await decryptVaultSpaceKeyForUser(
            userMasterKey,
            encryptedKey,
          );
          cacheVaultSpaceKey(this.$route.params.id, this.vaultspaceKey);
        } else {
          // Decrypt VaultSpace key with user master key
          try {
            this.vaultspaceKey = await decryptVaultSpaceKeyForUser(
              userMasterKey,
              vaultspaceKeyData.encrypted_key,
            );

            // Cache the decrypted key
            cacheVaultSpaceKey(this.$route.params.id, this.vaultspaceKey);
          } catch (decryptErr) {
            // Decryption failed - VaultSpace key was encrypted with a different master key
            logger.error("Failed to decrypt VaultSpace key:", decryptErr);
            if (decryptErr.name === "OperationError") {
              logger.warn(
                "OperationError: The VaultSpace key was encrypted with a different master key.",
              );
              logger.warn("Creating a new VaultSpace key...");

              // Create a new VaultSpace key with the current master key
              // Files encrypted with the previous VaultSpace key will become inaccessible
              try {
                const currentUser = await auth.getCurrentUser();

                // Create new VaultSpace key and store it
                // The backend will update the existing key if it already exists
                const { encryptedKey } =
                  await createVaultSpaceKey(userMasterKey);

                // Store/update the encrypted key on the server (share with self)
                // This will update the key if it already exists (for existing users)
                await vaultspaces.share(
                  this.$route.params.id,
                  currentUser.id,
                  encryptedKey,
                );

                // Decrypt and cache the new key
                this.vaultspaceKey = await decryptVaultSpaceKeyForUser(
                  userMasterKey,
                  encryptedKey,
                );
                cacheVaultSpaceKey(this.$route.params.id, this.vaultspaceKey);

                // Show warning about existing files
                this.showAlert({
                  type: "warning",
                  title: "Warning",
                  message:
                    "Warning: A new VaultSpace key has been created. " +
                    "Existing files encrypted with the old key will no longer be accessible. " +
                    "You can now use this VaultSpace normally.",
                });
              } catch (recreateErr) {
                console.error(
                  "Failed to recreate VaultSpace key:",
                  recreateErr,
                );
                this.error =
                  "Unable to decrypt VaultSpace key and failed to create a new key. " +
                  "Please contact support.";
                this.showAlert({
                  type: "error",
                  title: "Error",
                  message:
                    "Error: Unable to decrypt existing VaultSpace key and failed to create a new key. " +
                    "Please contact technical support.",
                });
                throw recreateErr;
              }
            } else {
              throw decryptErr;
            }
          }
        }
      } catch (err) {
        // Don't show error modal here, just log
        // The error will be shown when user tries to perform an action that needs the key
        logger.error("Failed to load VaultSpace key:", err);
        this.error = err.message;
      }
    },

    goToPage(page) {
      if (page >= 1 && page <= this.totalPages) {
        this.currentPage = page;
        this.loadFiles(this.currentParentId);
      }
    },

    // Debounced loadFiles for better performance
    loadFiles(parentId = null) {
      this.debouncedLoadFiles(parentId);
    },

    loadFilesInternal(parentId = null, cacheBust = false, showLoading = true) {
      if (showLoading) {
        this.loading = true;
      }
      this.error = null;

      // Ensure parentId is set correctly before loading
      // This prevents state inconsistencies
      const targetParentId = parentId || null;

      // Deselect all items when loading files (folder change)
      // Do this before loading to ensure clean state
      this.clearSelection();
      if (window.selectionManager) {
        window.selectionManager.deselectAll();
      }

      // Clear animation IDs when changing folders
      if (this.currentParentId !== targetParentId) {
        this.newlyCreatedFileIds = [];
        this.newlyCreatedFolderId = null;
      }

      return files
        .list(
          this.$route.params.id,
          targetParentId,
          this.currentPage,
          this.perPage,
          cacheBust,
        )
        .then((result) => {
          const allItems = result.files || [];
          this.totalFiles = result.pagination?.total || 0;
          this.totalPages = result.pagination?.pages || 1;

          // Separate folders and files
          // In Vue 3, direct assignment is reactive - no need for $set
          const newFolders = allItems.filter(
            (item) => item.mime_type === "application/x-directory",
          );
          const newFilesList = allItems.filter(
            (item) => item.mime_type !== "application/x-directory",
          );

          // Direct assignment - Vue 3 reactivity handles this automatically
          this.folders = newFolders;
          this.filesList = newFilesList;
          this.files = allItems;
          // Always set currentParentId to match what was requested
          // This ensures state consistency
          this.currentParentId = targetParentId;

          // Update breadcrumbs if in a folder
          // Use nextTick to ensure folders are loaded before updating breadcrumbs
          if (targetParentId) {
            this.$nextTick(() => {
              this.updateBreadcrumbs(targetParentId);
            });
          } else {
            this.breadcrumbs = [];
          }

          // Ensure selection UI is updated after files are loaded
          // This ensures that any lingering selection state is cleared from the DOM
          this.$nextTick(() => {
            // Clear selection again after DOM update to ensure it's really cleared
            this.clearSelection();
            if (window.selectionManager) {
              window.selectionManager.deselectAll();
              window.selectionManager.updateUI();
            }
          });

          return result;
        })
        .catch((err) => {
          this.error = err.message;
          // Don't reset currentParentId on error - keep it as requested
          // Only show error, don't revert to root
          this.showAlert({
            type: "error",
            title: "Error",
            message: "Failed to load files: " + err.message,
          });
          throw err;
        })
        .finally(() => {
          if (showLoading) {
            this.loading = false;
          }
        });
    },

    /**
     * Reload files with retry mechanism to ensure uploaded files appear.
     * Retries up to 3 times if uploaded files are not found in the response.
     *
     * @param {string|null} parentId - Parent folder ID
     * @param {string[]} uploadedFileIds - Array of file IDs that were uploaded
     * @param {number} maxRetries - Maximum number of retry attempts (default: 3)
     * @param {number} initialDelay - Initial delay in milliseconds (default: 300)
     */
    async reloadFilesWithRetry(
      parentId = null,
      uploadedFileIds = [],
      maxRetries = 3,
      initialDelay = 300,
    ) {
      if (!uploadedFileIds || uploadedFileIds.length === 0) {
        // No files to verify, just reload once
        // Don't show loading indicator to avoid flash
        await new Promise((resolve) => setTimeout(resolve, initialDelay));
        await this.loadFilesInternal(parentId, true, false);
        return;
      }

      let retryCount = 0;
      let allFilesFound = false;

      while (retryCount <= maxRetries && !allFilesFound) {
        // Wait before reloading (longer delay on first attempt)
        const delay = retryCount === 0 ? initialDelay : 100;
        await new Promise((resolve) => setTimeout(resolve, delay));

        try {
          // Reload files with cache-busting
          // Don't show loading indicator to avoid flash
          const result = await this.loadFilesInternal(parentId, true, false);
          const allItems = result.files || [];

          // Check if all uploaded files are present in the response
          const foundFileIds = allItems.map((item) => item.id);
          const missingFileIds = uploadedFileIds.filter(
            (id) => !foundFileIds.includes(id),
          );

          if (missingFileIds.length === 0) {
            // All files found, success!
            allFilesFound = true;
            // Force Vue to update after successful reload
            await this.$nextTick();
            this.$forceUpdate();
          } else if (retryCount < maxRetries) {
            // Some files still missing, retry
            retryCount++;
            logger.debug(
              `Files not yet visible, retrying... (attempt ${retryCount}/${maxRetries})`,
            );
          } else {
            // Max retries reached, but files still not found
            // This might happen if files are on a different page due to pagination
            // Log warning but don't fail - files might still be there
            // Still update the UI with what we have
            logger.warn(
              `Some uploaded files not found after ${maxRetries} retries. They may be on a different page.`,
            );
            allFilesFound = true; // Stop retrying
            // Force Vue to update even if files not found
            await this.$nextTick();
            this.$forceUpdate();
          }
        } catch (err) {
          // If reload fails, retry if we haven't exceeded max retries
          if (retryCount < maxRetries) {
            retryCount++;
            logger.warn(
              `Failed to reload files, retrying... (attempt ${retryCount}/${maxRetries}):`,
              err,
            );
          } else {
            // Max retries reached, throw error
            throw err;
          }
        }
      }
    },

    async navigateToFolder(folderId) {
      // Deselect all items when changing folder
      this.clearSelection();
      if (window.selectionManager) {
        window.selectionManager.deselectAll();
      }

      // Update URL with folder parameter
      const currentFolderId = this.$route.query.folder || null;
      const newFolderId = folderId || null;

      // Build new query object
      const newQuery = { ...this.$route.query };
      if (newFolderId) {
        newQuery.folder = newFolderId;
      } else {
        // Remove folder parameter if navigating to root
        delete newQuery.folder;
      }

      // Build URL string for direct manipulation
      const queryString =
        Object.keys(newQuery).length > 0
          ? "?" + new URLSearchParams(newQuery).toString()
          : "";
      const newUrl = `${this.$route.path}${queryString}`;

      // Always update URL first using direct history manipulation
      // This ensures the URL is updated immediately
      window.history.replaceState(
        { ...window.history.state, query: newQuery },
        "",
        newUrl,
      );

      // Then update Vue Router's internal state
      // This ensures Vue Router knows about the change
      this.$router
        .replace({
          path: this.$route.path,
          query: newQuery,
        })
        .catch(() => {
          // Ignore navigation errors - URL is already updated
        });

      // Load files immediately
      await this.loadFiles(newFolderId);
    },

    async updateBreadcrumbs(folderId) {
      if (!folderId) {
        this.breadcrumbs = [];
        return;
      }

      try {
        // Build breadcrumbs by traversing up the parent chain
        // Key insight: the current folder is not in this.folders (which contains its children)
        // We need to load it from its parent, but we don't know the parent_id
        // Solution: use a recursive approach - load each folder from its parent

        const pathFolders = [];
        let currentFolderId = folderId;
        const visited = new Set();
        const maxDepth = 50;
        let depth = 0;

        // Helper to load a folder by searching in a specific parent
        const loadFolderFromParent = async (
          folderIdToFind,
          parentIdToSearch,
        ) => {
          try {
            const response = await files.list(
              this.$route.params.id,
              parentIdToSearch,
              1,
              100,
            );
            return (response.files || []).find(
              (f) =>
                f.id === folderIdToFind &&
                f.mime_type === "application/x-directory",
            );
          } catch (err) {
            return null;
          }
        };

        // Build path from current folder up to root
        while (currentFolderId && depth < maxDepth) {
          if (visited.has(currentFolderId)) {
            break;
          }
          visited.add(currentFolderId);

          let currentFolder = null;

          // Try to find in loaded data first
          currentFolder =
            this.folders.find((f) => f.id === currentFolderId) ||
            this.files.find((f) => f.id === currentFolderId) ||
            this.filesList.find((f) => f.id === currentFolderId);

          // If not found, we need to load it
          if (!currentFolder) {
            if (pathFolders.length === 0) {
              // Looking for current folder
              // The current folder is not in this.folders (which contains its children)
              // Use files.get() to get folder info directly
              try {
                const folderData = await files.get(
                  currentFolderId,
                  this.$route.params.id,
                );
                if (folderData && folderData.file) {
                  currentFolder = {
                    id: folderData.file.id,
                    name: folderData.file.name || folderData.file.original_name,
                    parent_id: folderData.file.parent_id,
                    mime_type: folderData.file.mime_type,
                  };
                }
              } catch (err) {
                // If files.get() fails, try loading from root
                currentFolder = await loadFolderFromParent(
                  currentFolderId,
                  null,
                );
              }
            } else {
              // Looking for parent of previous folder
              // The previous folder's parent_id is currentFolderId
              // To find currentFolderId, search in its parent
              // Use files.get() to get the folder info directly
              // This provides the parent_id needed to locate the folder
              try {
                const folderData = await files.get(
                  currentFolderId,
                  this.$route.params.id,
                );
                if (folderData && folderData.file) {
                  currentFolder = {
                    id: folderData.file.id,
                    name: folderData.file.name || folderData.file.original_name,
                    parent_id: folderData.file.parent_id,
                    mime_type: folderData.file.mime_type,
                  };
                }
              } catch (err) {
                // If files.get() fails, try loading from root
                currentFolder = await loadFolderFromParent(
                  currentFolderId,
                  null,
                );

                // If not in root, try searching in each known parent folder
                if (!currentFolder) {
                  for (const knownFolder of pathFolders) {
                    currentFolder = await loadFolderFromParent(
                      currentFolderId,
                      knownFolder.id,
                    );
                    if (currentFolder) break;
                  }
                }
              }
            }
          }

          if (currentFolder && currentFolder.name) {
            pathFolders.push({
              id: currentFolderId,
              name: currentFolder.name,
              parent_id: currentFolder.parent_id || null,
            });

            if (currentFolder.parent_id) {
              currentFolderId = currentFolder.parent_id;
            } else {
              break; // Reached root
            }
          } else if (pathFolders.length === 0) {
            // Cannot find current folder
            // The folder is not in root and its parent_id is unknown
            // Cannot construct the breadcrumb without at least the current folder name
            // Break and let the template show "Loading..."
            // This occurs when the folder is nested and cannot be found in root
            break;
          } else {
            // Can't find parent folder, stop here
            break;
          }

          depth++;
        }

        // Reverse to get root -> current order
        this.breadcrumbs = pathFolders.reverse();

        // If still no breadcrumbs, at least try to show current folder
        // by getting its name from a child folder's parent reference
        if (this.breadcrumbs.length === 0) {
          // Try to find a child folder that references this as parent
          const childFolder = this.folders.find(
            (f) => f.parent_id === folderId,
          );
          if (childFolder) {
            // We know we're in folderId, but we don't have its name
            // We can't infer it from children...
            // So we'll just show an empty breadcrumb or try one more API call
          }
        }
      } catch (error) {
        console.error("Error updating breadcrumbs:", error);
        this.breadcrumbs = [];
      }
    },

    async handleUploadClick() {
      // Load VaultSpace key if not already loaded
      if (!this.vaultspaceKey) {
        try {
          await this.loadVaultSpaceKey();

          // Check again if key is loaded
          if (!this.vaultspaceKey) {
            // Key still not loaded - check if user master key is available
            const userMasterKey = await getUserMasterKey();
            if (!userMasterKey) {
              // Check if salt exists - this indicates session was lost
              const storedSalt = getStoredSalt();
              let errorMessage =
                "Your session has expired. Please log in again.";

              if (storedSalt) {
                console.warn(
                  "Master key lost from memory but salt exists in sessionStorage. Session expired.",
                );
                errorMessage =
                  "Your session has expired. The encryption key has been lost. Please log in again.";
              } else {
                console.warn(
                  "User master key not available, no salt found. User needs to login.",
                );
              }

              // Clear any stale data and redirect to login
              clearUserMasterKey();
              this.showAlert({
                type: "error",
                title: "Session Expired",
                message: errorMessage,
              });
              setTimeout(() => {
                auth.logout();
                this.$router.push("/login");
              }, 2000);
              return;
            }
          }
        } catch (err) {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "Failed to load VaultSpace key: " + err.message,
          });
          return;
        }
      }

      if (!this.vaultspaceKey) {
        this.showAlert({
          type: "error",
          title: "Error",
          message:
            "The VaultSpace key could not be loaded. Please try again or refresh the page.",
        });
        return;
      }

      // Open file picker directly without modal
      this.$nextTick(() => {
        const fileInput = this.$refs.fileInput;
        if (fileInput) {
          fileInput.click();
        }
      });
    },
    async generateUniqueFolderName(baseName = "New Folder", retryAttempt = 0) {
      try {
        // Use local state first (it's already up-to-date from the last load)
        // This is faster and avoids cache issues
        const localFolderNames = new Set(
          (this.folders || [])
            .filter(
              (f) =>
                f &&
                f.mime_type === "application/x-directory" &&
                f.name && // Ensure name exists
                (f.parent_id === this.currentParentId ||
                  (!f.parent_id && !this.currentParentId)),
            )
            .map((f) => (f.name || "").trim()) // Normalize: trim whitespace, handle null/undefined
            .filter((name) => name.length > 0), // Filter out empty names
        );

        // Also fetch from API to get the absolute latest (with cache-busting on retry)
        let apiFolderNames = new Set();
        try {
          // Fetch all folders from API with pagination (max 100 per page)
          const allFolders = [];
          let page = 1;
          const perPage = 100; // API limit
          let hasMore = true;

          while (hasMore && page <= 10) {
            // Safety limit: max 10 pages (1000 folders)
            const result = await files.list(
              this.$route.params.id,
              this.currentParentId,
              page,
              perPage,
              retryAttempt > 0, // Use cache-busting on retry
            );

            const items = result.files || [];
            allFolders.push(...items);

            // Check if there are more pages
            const pagination = result.pagination || {};
            const totalPages = pagination.pages || 1;
            hasMore = page < totalPages && items.length > 0;
            page++;

            // If no items returned, we've reached the end
            if (items.length === 0) {
              hasMore = false;
            }
          }

          // Filter folders in the current parent directory
          const existingFolders = allFolders.filter(
            (item) =>
              item &&
              item.mime_type === "application/x-directory" &&
              item.name && // Ensure name exists
              (item.parent_id === this.currentParentId ||
                (!item.parent_id && !this.currentParentId)),
          );

          apiFolderNames = new Set(
            existingFolders
              .map((f) => (f.name || "").trim()) // Normalize: trim whitespace, handle null/undefined
              .filter((name) => name.length > 0), // Filter out empty names
          );
        } catch (apiError) {
          // Failed to fetch from API, will use local state only
        }

        // Merge both sets to get the most complete list
        const existingNames = new Set([...localFolderNames, ...apiFolderNames]);

        // Check if base name is available
        if (!existingNames.has(baseName)) {
          return baseName;
        }

        // Find the next available number
        let counter = 1;
        let newName = `${baseName}(${counter})`;

        while (existingNames.has(newName)) {
          counter++;
          newName = `${baseName}(${counter})`;

          // Safety limit to prevent infinite loop
          if (counter > 1000) {
            // Use UUID as fallback to guarantee uniqueness
            const uuid = crypto.randomUUID().slice(0, 8);
            newName = `${baseName}(${uuid})`;
            break;
          }
        }

        return newName;
      } catch (error) {
        // Fallback: use local state and add a UUID to ensure uniqueness
        const existingNames = new Set(
          (this.folders || [])
            .filter(
              (f) =>
                f &&
                f.mime_type === "application/x-directory" &&
                f.name && // Ensure name exists
                (f.parent_id === this.currentParentId ||
                  (!f.parent_id && !this.currentParentId)),
            )
            .map((f) => (f.name || "").trim()) // Normalize: trim whitespace, handle null/undefined
            .filter((name) => name.length > 0), // Filter out empty names
        );

        // Try base name first
        if (!existingNames.has(baseName)) {
          return baseName;
        }

        // Try numbered versions
        let counter = 1;
        let newName = `${baseName}(${counter})`;

        while (existingNames.has(newName) && counter <= 100) {
          counter++;
          newName = `${baseName}(${counter})`;
        }

        // If we still have conflicts, use UUID to guarantee uniqueness
        if (existingNames.has(newName)) {
          const uuid = crypto.randomUUID().slice(0, 8);
          newName = `${baseName}(${uuid})`;
        }

        return newName;
      }
    },
    async createFolderDirect() {
      // Check if master key is required
      if (this.isMasterKeyRequired) {
        this.showAlert({
          type: "error",
          title: "Encryption Required",
          message:
            "Please unlock your files by entering your encryption password to create folders.",
        });
        this.openPasswordModal();
        return;
      }

      // Normalize parent_id for comparison (null and undefined should be treated the same)
      const normalizedParentId = this.currentParentId || null;

      // Track known folder names (from local state + conflicts encountered)
      const knownFolderNames = new Set(
        (this.folders || [])
          .filter((f) => {
            if (!f || f.mime_type !== "application/x-directory" || !f.name)
              return false;
            const fParentId = f.parent_id || null;
            return fParentId === normalizedParentId;
          })
          .map((f) => (f.name || "").trim())
          .filter((name) => name.length > 0),
      );

      // Helper function to generate unique name
      const generateUniqueName = (existingNames) => {
        let name = "New Folder";
        if (existingNames.has(name)) {
          let counter = 1;
          name = `New Folder(${counter})`;
          while (existingNames.has(name)) {
            counter++;
            name = `New Folder(${counter})`;
          }
        }
        return name;
      };

      // Helper function to add folder to local state and animate
      const addFolderToUI = (folder) => {
        const folderToAdd = {
          ...folder,
          mime_type: folder.mime_type || "application/x-directory",
          parent_id: folder.parent_id || null,
          name: folder.name,
        };
        this.folders.push(folderToAdd);
        this.files.push(folderToAdd);

        this.newlyCreatedFolderId = folder.id;
        this.$nextTick(() => {
          setTimeout(() => {
            const element = document.querySelector(
              `[data-folder-id="${folder.id}"]`,
            );
            if (element) {
              element.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
            setTimeout(() => {
              this.newlyCreatedFolderId = null;
            }, 600);
          }, 50);
        });
      };

      // Try to create folder
      try {
        const folder = await files.createFolder(
          this.$route.params.id,
          "New Folder",
          normalizedParentId,
        );

        // Add to UI (optimistic update)
        addFolderToUI(folder);

        // Refresh from server with cache-busting to ensure consistency
        await this.loadFilesInternal(normalizedParentId, true);

        // Success - exit
        return;
      } catch (err) {
        // Check if it's a 409 conflict error
        const isConflict =
          err.message &&
          (err.message.toLowerCase().includes("already exists") ||
            err.message.includes("409") ||
            err.message.includes("CONFLICT"));

        if (isConflict) {
          // Store pending folder info
          this.pendingFolderName = "New Folder";
          this.conflictApplyToAll = false;
          this.conflictResolution = null;

          // Show conflict modal
          this.conflictData = {
            title: "Folder Already Exists",
            message: `A folder named "New Folder" already exists in this location.`,
            showApplyToAll: false,
            remainingCount: null,
          };
          this.showConflictModal = true;

          // Wait for user decision
          await new Promise((resolve) => {
            const checkResolution = () => {
              if (this.conflictResolution) {
                resolve();
              } else {
                setTimeout(checkResolution, 100);
              }
            };
            checkResolution();
          });

          // Store resolution
          const resolution = this.conflictResolution;
          this.pendingFolderName = null;
          this.conflictResolution = null;

          // Handle resolution
          if (resolution === "skip") {
            // Skip folder creation
            return;
          } else if (resolution === "replace") {
            // Retry with overwrite
            try {
              const folder = await files.createFolder(
                this.$route.params.id,
                "New Folder",
                normalizedParentId,
                true,
              );

              addFolderToUI(folder);
              await this.loadFilesInternal(normalizedParentId, true);
              return;
            } catch (replaceErr) {
              this.showAlert({
                type: "error",
                title: "Error",
                message: `Failed to replace folder: ${replaceErr.message}`,
              });
              return;
            }
          } else if (resolution === "keep-both") {
            // Generate unique name and retry
            const existingNames = new Set(
              this.folders
                .filter(
                  (f) =>
                    f &&
                    f.mime_type === "application/x-directory" &&
                    f.name &&
                    (f.parent_id === normalizedParentId ||
                      (!f.parent_id && !normalizedParentId)),
                )
                .map((f) => (f.name || "").trim())
                .filter((name) => name.length > 0),
            );
            const uniqueName = this.generateUniqueName(
              "New Folder",
              existingNames,
              false,
            );

            try {
              const folder = await files.createFolder(
                this.$route.params.id,
                uniqueName,
                normalizedParentId,
              );

              addFolderToUI(folder);
              await this.loadFilesInternal(normalizedParentId, true);
              return;
            } catch (keepBothErr) {
              this.showAlert({
                type: "error",
                title: "Error",
                message: `Failed to create folder: ${keepBothErr.message}`,
              });
              return;
            }
          }
        } else {
          // Not a conflict
          this.showAlert({
            type: "error",
            title: "Error",
            message: "Failed to create folder: " + err.message,
          });
          return;
        }
      }
    },

    async handleFileSelect(event) {
      const files = Array.from(event.target.files);
      if (files.length === 0) return;

      this.selectedFiles = files;
      this.uploadError = null;

      // Auto-upload files immediately after selection
      await this.handleUpload();
    },

    handleFilesSelected(files) {
      this.selectedFiles = files;
      // Auto-upload when files are dropped
      if (files.length > 0) {
        this.handleUpload();
      }
    },

    async handleUpload() {
      this.uploadError = null;

      // Check if master key is required
      if (this.isMasterKeyRequired) {
        this.showAlert({
          type: "error",
          title: "Encryption Required",
          message:
            "Please unlock your files by entering your encryption password to upload files.",
        });
        this.openPasswordModal();
        return;
      }

      if (this.selectedFiles.length === 0) {
        this.uploadError = "Please select at least one file";
        return;
      }

      if (!this.vaultspaceKey) {
        this.uploadError =
          "VaultSpace key not loaded. Please wait or refresh the page.";
        return;
      }

      this.uploading = true;
      this.uploadProgress = 0;
      this.uploadSpeed = 0;
      this.uploadTimeRemaining = null;
      this.uploadCancelFunctions = [];
      this.uploadCancelled = false;
      this.uploadCancellationMessageShown = false;
      this.uploadedFileIds = []; // Reset uploaded file IDs for this upload batch

      try {
        const totalFiles = this.selectedFiles.length;
        let uploadedCount = 0;

        for (
          let fileIndex = 0;
          fileIndex < this.selectedFiles.length && !this.uploadCancelled;
          fileIndex++
        ) {
          const file = this.selectedFiles[fileIndex];

          // Prepare file data (needed for conflict resolution)
          let fileKey = null;
          let fileData = null;
          let encrypted = null;
          let iv = null;
          let encryptedFileKey = null;
          let encryptedDataBlob = null;

          // Calculate progress values (needed for conflict resolution)
          const baseProgress = (uploadedCount / totalFiles) * 100;
          const fileProgressWeight = (1 / totalFiles) * 100;

          try {
            // Set current file name for progress display
            this.uploadFileName = file.name;

            // Generate file key
            fileKey = await generateFileKey();

            // Read file data
            fileData = await file.arrayBuffer();

            // Encrypt file
            const encryptedResult = await encryptFile(fileKey, fileData);
            encrypted = encryptedResult.encrypted;
            iv = encryptedResult.iv;

            // Encrypt file key with VaultSpace key
            encryptedFileKey = await encryptFileKey(
              this.vaultspaceKey,
              fileKey,
            );

            // Combine IV with encrypted data for storage
            const combined = new Uint8Array(iv.length + encrypted.byteLength);
            combined.set(iv, 0);
            combined.set(new Uint8Array(encrypted), iv.length);
            encryptedDataBlob = new Blob([combined]);

            // Check if file is large enough for chunked upload (5MB threshold)
            const CHUNK_SIZE_THRESHOLD = 5 * 1024 * 1024; // 5MB
            const encryptedSize = encryptedDataBlob.size;

            let result;

            // Check for conflict first if we have a resolution from previous conflict
            let fileNameToUse = file.name;
            let shouldOverwrite = false;

            // Use chunked upload for large files
            if (encryptedSize > CHUNK_SIZE_THRESHOLD) {
              // Create upload session
              const sessionInfo = await files.createUploadSession({
                vaultspaceId: this.$route.params.id,
                originalName: fileNameToUse,
                totalSize: encryptedSize,
                chunkSize: CHUNK_SIZE_THRESHOLD,
                encryptedFileKey: encryptedFileKey,
                parentId: this.currentParentId,
                mimeType: file.type || null,
              });

              const sessionId = sessionInfo.session_id;
              const chunkSize = sessionInfo.chunk_size;
              const totalChunks = sessionInfo.total_chunks;

              // Store session data to send with chunks (workaround for rollback issue)
              const sessionDataForChunks = JSON.stringify({
                vaultspace_id: sessionInfo.vaultspace_id,
                file_id: sessionInfo.file_id,
                original_name: sessionInfo.original_name,
                total_size: sessionInfo.total_size,
                chunk_size: sessionInfo.chunk_size,
                total_chunks: sessionInfo.total_chunks,
                encrypted_file_key: sessionInfo.encrypted_file_key,
                parent_id: sessionInfo.parent_id,
                mime_type: sessionInfo.mime_type,
                expires_at: sessionInfo.expires_at,
              });

              // Split encrypted data into chunks
              const chunks = [];
              for (let i = 0; i < encryptedSize; i += chunkSize) {
                chunks.push(encryptedDataBlob.slice(i, i + chunkSize));
              }

              // Upload chunks sequentially with progress tracking
              for (
                let chunkIndex = 0;
                chunkIndex < chunks.length;
                chunkIndex++
              ) {
                // Check if upload was cancelled
                if (this.uploadCancelled) {
                  // Cancel upload session
                  try {
                    await files.cancelUpload(sessionId);
                  } catch (e) {
                    console.warn("Failed to cancel upload session:", e);
                  }
                  throw new Error("Upload cancelled");
                }

                const chunk = chunks[chunkIndex];
                const chunkProgressBase =
                  (chunkIndex / chunks.length) * fileProgressWeight;

                try {
                  // Upload chunk with progress tracking
                  const chunkResult = files.uploadChunk(
                    sessionId,
                    chunkIndex,
                    chunk,
                    sessionDataForChunks,
                    (loaded, total) => {
                      if (!this.uploadCancelled) {
                        const chunkProgress =
                          (loaded / total) *
                          (fileProgressWeight / chunks.length);
                        this.uploadProgress = Math.round(
                          baseProgress + chunkProgressBase + chunkProgress,
                        );
                      }
                    },
                  );

                  // Store cancel function
                  this.uploadCancelFunctions.push(chunkResult.cancel);

                  // Wait for chunk upload to complete
                  const chunkResponse = await chunkResult.promise;

                  // Check if response is valid
                  if (!chunkResponse || typeof chunkResponse !== "object") {
                    console.error(
                      "Invalid chunk response:",
                      chunkResponse,
                      "Type:",
                      typeof chunkResponse,
                    );
                    throw new Error("Invalid response from server");
                  }

                  // Update progress
                  if (!this.uploadCancelled) {
                    const uploadedSize =
                      chunkResponse.uploaded_size !== undefined
                        ? chunkResponse.uploaded_size
                        : 0;
                    const totalSize =
                      chunkResponse.total_size !== undefined
                        ? chunkResponse.total_size
                        : encryptedSize;
                    const fileProgress =
                      (uploadedSize / totalSize) * fileProgressWeight;
                    this.uploadProgress = Math.round(
                      baseProgress + fileProgress,
                    );
                  }

                  // Check if all chunks are uploaded
                  if (chunkResponse.is_complete === true) {
                    break;
                  }
                } catch (chunkError) {
                  console.error(
                    `Failed to upload chunk ${chunkIndex}:`,
                    chunkError,
                  );
                  // Cancel upload session on error
                  try {
                    await files.cancelUpload(sessionId);
                  } catch (cancelError) {
                    console.warn(
                      "Failed to cancel upload session:",
                      cancelError,
                    );
                  }
                  throw chunkError;
                }
              }

              // Complete upload
              result = await files.completeUpload(sessionId);
            } else {
              // Use regular upload for small files
              const uploadResult = files.upload(
                {
                  file: encryptedDataBlob,
                  originalName: file.name,
                  vaultspaceId: this.$route.params.id,
                  encryptedFileKey: encryptedFileKey,
                  parentId: this.currentParentId,
                },
                (loaded, total, speed, timeRemaining) => {
                  // Only update progress if not cancelled
                  if (!this.uploadCancelled) {
                    // Calculate overall progress across all files
                    const fileProgress = (loaded / total) * fileProgressWeight;
                    this.uploadProgress = Math.round(
                      baseProgress + fileProgress,
                    );
                    this.uploadSpeed = speed || 0;
                    this.uploadTimeRemaining = timeRemaining;
                  }
                },
              );

              // Store cancel function
              this.uploadCancelFunctions.push(uploadResult.cancel);

              // Wait for upload to complete
              result = await uploadResult.promise;
            }

            // Check if upload was cancelled
            if (this.uploadCancelled) {
              break;
            }

            // Store uploaded file IDs for verification after reload
            if (!this.uploadedFileIds) {
              this.uploadedFileIds = [];
            }
            if (result && result.file) {
              this.uploadedFileIds.push(result.file.id);
              uploadedCount++;
            }
          } catch (err) {
            // Check if error is due to cancellation
            if (err.message === "Upload cancelled" || this.uploadCancelled) {
              this.uploadCancelled = true;
              break;
            }

            // Check if it's a 409 conflict error (don't log it, we'll handle it)
            const isConflict =
              err.isConflict ||
              err.status === 409 ||
              (err.message &&
                (err.message.toLowerCase().includes("already exists") ||
                  err.message.includes("409") ||
                  err.message.includes("CONFLICT")));

            // Only log non-conflict errors
            if (!isConflict) {
              console.error(`Failed to upload ${file.name}:`, err);
            }

            // Check if error is quota-related and show modal
            if (
              err.message &&
              (err.message.includes("quota exceeded") ||
                err.message.includes("Quota exceeded"))
            ) {
              // Extract quota info if available
              let quotaMessage = err.message;
              if (err.quota_info) {
                const quotaInfo = err.quota_info;
                if (quotaInfo.limit !== null && quotaInfo.limit !== undefined) {
                  const used = quotaInfo.used || 0;
                  const limit = quotaInfo.limit;
                  const available = quotaInfo.available || 0;

                  if (err.message.includes("File quota")) {
                    quotaMessage = `You have reached your file limit.\n\nUsed: ${used} / ${limit} files\nAvailable: ${available} files`;
                  } else if (err.message.includes("Storage quota")) {
                    // Format storage sizes
                    const formatSize = (bytes) => {
                      if (bytes === 0) return "0 B";
                      const k = 1024;
                      const sizes = ["B", "KB", "MB", "GB", "TB"];
                      const i = Math.floor(Math.log(bytes) / Math.log(k));
                      return (
                        Math.round((bytes / Math.pow(k, i)) * 100) / 100 +
                        " " +
                        sizes[i]
                      );
                    };
                    quotaMessage = `You have reached your storage limit.\n\nUsed: ${formatSize(used)} / ${formatSize(limit)}\nAvailable: ${formatSize(available)}`;
                  }
                }
              }

              this.showAlert({
                type: "error",
                title: "Quota Exceeded",
                message: quotaMessage,
              });

              // Stop uploading remaining files
              break;
            } else if (isConflict) {
              // Handle conflict
              // Check if we have a resolution from "apply to all"
              let resolution = this.conflictResolution;
              let applyToAll = this.conflictApplyToAll;

              // If no resolution yet, show modal
              if (!resolution) {
                // Store pending upload info
                this.pendingUploadFile = file;
                this.pendingUploadIndex = fileIndex;
                this.pendingUploadFiles = this.selectedFiles.slice(fileIndex);
                this.conflictApplyToAll = false;
                this.conflictResolution = null;

                // Calculate remaining files count
                const remainingCount = this.selectedFiles.length - fileIndex;

                // Show conflict modal
                this.conflictData = {
                  title: "File Already Exists",
                  message: `A file named "${file.name}" already exists in this folder.`,
                  showApplyToAll: remainingCount > 1,
                  remainingCount: remainingCount > 1 ? remainingCount : null,
                };
                this.showConflictModal = true;

                // Wait for user decision
                await new Promise((resolve) => {
                  const checkResolution = () => {
                    if (this.conflictResolution) {
                      resolve();
                    } else {
                      setTimeout(checkResolution, 100);
                    }
                  };
                  checkResolution();
                });

                // Store resolution for apply to all
                resolution = this.conflictResolution;
                applyToAll = this.conflictApplyToAll;

                // Reset conflict state (but keep resolution if apply to all)
                this.pendingUploadFile = null;
                this.pendingUploadIndex = -1;
                this.pendingUploadFiles = [];
                if (!applyToAll) {
                  this.conflictResolution = null;
                }
              }

              // Handle resolution
              let uploadSucceeded = false;
              if (resolution === "skip") {
                // Skip this file and continue
                uploadSucceeded = true; // Mark as handled
                continue;
              } else if (resolution === "replace") {
                // Retry with overwrite - need to re-encrypt if data not available
                if (!encryptedDataBlob || !encryptedFileKey) {
                  // Re-encrypt file
                  fileKey = await generateFileKey();
                  fileData = await file.arrayBuffer();
                  const encryptedResult = await encryptFile(fileKey, fileData);
                  encrypted = encryptedResult.encrypted;
                  iv = encryptedResult.iv;
                  encryptedFileKey = await encryptFileKey(
                    this.vaultspaceKey,
                    fileKey,
                  );
                  const combined = new Uint8Array(
                    iv.length + encrypted.byteLength,
                  );
                  combined.set(iv, 0);
                  combined.set(new Uint8Array(encrypted), iv.length);
                  encryptedDataBlob = new Blob([combined]);
                }

                // Retry with overwrite
                try {
                  const uploadResult = files.upload(
                    {
                      file: encryptedDataBlob,
                      originalName: file.name,
                      vaultspaceId: this.$route.params.id,
                      encryptedFileKey: encryptedFileKey,
                      parentId: this.currentParentId,
                      overwrite: true,
                    },
                    (loaded, total, speed, timeRemaining) => {
                      if (!this.uploadCancelled) {
                        const fileProgress =
                          (loaded / total) * fileProgressWeight;
                        this.uploadProgress = Math.round(
                          baseProgress + fileProgress,
                        );
                        this.uploadSpeed = speed || 0;
                        this.uploadTimeRemaining = timeRemaining;
                      }
                    },
                  );

                  this.uploadCancelFunctions.push(uploadResult.cancel);
                  const replaceResult = await uploadResult.promise;
                  this.uploadedFileIds.push(replaceResult.file.id);
                  uploadedCount++;
                  uploadSucceeded = true;
                } catch (replaceErr) {
                  console.error(`Failed to replace ${file.name}:`, replaceErr);
                  this.uploadError = `Failed to replace ${file.name}: ${replaceErr.message}`;
                  if (!applyToAll) {
                    this.conflictResolution = null;
                    this.conflictApplyToAll = false;
                  }
                  continue;
                }
              } else if (resolution === "keep-both") {
                // Generate unique name and retry - need to re-encrypt if data not available
                if (!encryptedDataBlob || !encryptedFileKey) {
                  // Re-encrypt file
                  fileKey = await generateFileKey();
                  fileData = await file.arrayBuffer();
                  const encryptedResult = await encryptFile(fileKey, fileData);
                  encrypted = encryptedResult.encrypted;
                  iv = encryptedResult.iv;
                  encryptedFileKey = await encryptFileKey(
                    this.vaultspaceKey,
                    fileKey,
                  );
                  const combined = new Uint8Array(
                    iv.length + encrypted.byteLength,
                  );
                  combined.set(iv, 0);
                  combined.set(new Uint8Array(encrypted), iv.length);
                  encryptedDataBlob = new Blob([combined]);
                }

                // Generate unique name and retry
                const existingNames = new Set(
                  this.filesList.map((f) => f.original_name || f.name || ""),
                );
                const uniqueName = this.generateUniqueName(
                  file.name,
                  existingNames,
                  true,
                );

                try {
                  const uploadResult = files.upload(
                    {
                      file: encryptedDataBlob,
                      originalName: uniqueName,
                      vaultspaceId: this.$route.params.id,
                      encryptedFileKey: encryptedFileKey,
                      parentId: this.currentParentId,
                    },
                    (loaded, total, speed, timeRemaining) => {
                      if (!this.uploadCancelled) {
                        const fileProgress =
                          (loaded / total) * fileProgressWeight;
                        this.uploadProgress = Math.round(
                          baseProgress + fileProgress,
                        );
                        this.uploadSpeed = speed || 0;
                        this.uploadTimeRemaining = timeRemaining;
                      }
                    },
                  );

                  this.uploadCancelFunctions.push(uploadResult.cancel);
                  const keepBothResult = await uploadResult.promise;
                  this.uploadedFileIds.push(keepBothResult.file.id);
                  uploadedCount++;
                  uploadSucceeded = true;
                } catch (keepBothErr) {
                  console.error(`Failed to upload ${uniqueName}:`, keepBothErr);
                  this.uploadError = `Failed to upload ${uniqueName}: ${keepBothErr.message}`;
                  if (!applyToAll) {
                    this.conflictResolution = null;
                    this.conflictApplyToAll = false;
                  }
                  continue;
                }
              }

              // Reset apply to all after processing all files
              if (fileIndex === this.selectedFiles.length - 1) {
                this.conflictResolution = null;
                this.conflictApplyToAll = false;
              }

              // If upload succeeded, continue to next file
              if (uploadSucceeded) {
                continue;
              }
            } else {
              this.uploadError = `Failed to upload ${file.name}: ${err.message}`;
            }
          }
        }

        if (this.uploadCancelled) {
          // Show cancellation message if not already shown
          if (!this.uploadCancellationMessageShown) {
            // Always show alert modal for visibility
            this.showAlert({
              type: "info",
              title: "Upload Cancelled",
              message: "The upload has been cancelled successfully.",
            });

            // Also try to show toast notification if available (non-blocking)
            if (
              window.Notifications &&
              typeof window.Notifications.info === "function"
            ) {
              window.Notifications.info("Upload cancelled", 3000);
            }

            this.uploadCancellationMessageShown = true;
          }

          // Wait a moment to show the cancelled status in the progress bar, then clean up
          setTimeout(() => {
            this.uploadProgress = null;
            this.uploadSpeed = 0;
            this.uploadTimeRemaining = null;
            this.uploadFileName = "";
            this.uploadCancelFunctions = [];
            this.uploadError = "Upload cancelled";
            this.uploadCancellationMessageShown = false;
          }, 1500);
        } else if (uploadedCount === totalFiles) {
          this.selectedFiles = [];
          this.uploadProgress = 100;
          this.uploadSpeed = 0;
          this.uploadTimeRemaining = null;
          this.uploadFileName = "";
          this.uploadCancelFunctions = [];

          // Hide progress after a short delay
          setTimeout(() => {
            this.uploadProgress = null;
          }, 1000);

          if (this.$refs.fileInput) {
            this.$refs.fileInput.value = "";
          }

          // Reload files with retry mechanism to ensure uploaded files appear
          await this.reloadFilesWithRetry(
            this.currentParentId,
            this.uploadedFileIds,
          );

          // Store uploaded file IDs for animation
          // This will trigger the fade-in animation for newly uploaded files
          this.newlyCreatedFileIds = [...this.uploadedFileIds];

          // Force multiple DOM update cycles to ensure FileListView is properly rendered
          // This is especially important when transitioning from empty to non-empty state
          await this.$nextTick();
          await this.$nextTick();

          // Force Vue to re-render by triggering a reactive update
          this.$forceUpdate();

          // Clear uploaded file IDs after successful reload
          this.uploadedFileIds = [];

          // Clear animation IDs after animation completes (0.6s animation + small buffer)
          setTimeout(() => {
            this.newlyCreatedFileIds = [];
          }, 700);
        }
      } catch (err) {
        // Check if error is due to cancellation
        if (err.message === "Upload cancelled" || this.uploadCancelled) {
          // Show cancellation message if not already shown
          if (!this.uploadCancellationMessageShown) {
            // Always show alert modal for visibility
            this.showAlert({
              type: "info",
              title: "Upload Cancelled",
              message: "The upload has been cancelled successfully.",
            });

            // Also try to show toast notification if available (non-blocking)
            if (
              window.Notifications &&
              typeof window.Notifications.info === "function"
            ) {
              window.Notifications.info("Upload cancelled", 3000);
            }

            this.uploadCancellationMessageShown = true;
          }

          // Wait a moment to show the cancelled status, then clean up
          setTimeout(() => {
            this.uploadProgress = null;
            this.uploadSpeed = 0;
            this.uploadTimeRemaining = null;
            this.uploadFileName = "";
            this.uploadCancelFunctions = [];
            this.uploadError = "Upload cancelled";
            this.uploadCancellationMessageShown = false;
          }, 1500);
        } else {
          // Check if error is quota-related and show modal
          if (
            err.message &&
            (err.message.includes("quota exceeded") ||
              err.message.includes("Quota exceeded"))
          ) {
            // Extract quota info if available
            let quotaMessage = err.message;
            if (err.quota_info) {
              const quotaInfo = err.quota_info;
              if (quotaInfo.limit !== null && quotaInfo.limit !== undefined) {
                const used = quotaInfo.used || 0;
                const limit = quotaInfo.limit;
                const available = quotaInfo.available || 0;

                if (err.message.includes("File quota")) {
                  quotaMessage = `You have reached your file limit.\n\nUsed: ${used} / ${limit} files\nAvailable: ${available} files`;
                } else if (err.message.includes("Storage quota")) {
                  // Format storage sizes
                  const formatSize = (bytes) => {
                    if (bytes === 0) return "0 B";
                    const k = 1024;
                    const sizes = ["B", "KB", "MB", "GB", "TB"];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return (
                      Math.round((bytes / Math.pow(k, i)) * 100) / 100 +
                      " " +
                      sizes[i]
                    );
                  };
                  quotaMessage = `You have reached your storage limit.\n\nUsed: ${formatSize(used)} / ${formatSize(limit)}\nAvailable: ${formatSize(available)}`;
                }
              }
            }

            this.showAlert({
              type: "error",
              title: "Quota Exceeded",
              message: quotaMessage,
            });
          } else {
            this.uploadError = err.message || "Upload failed";
          }
          this.uploadProgress = null;
          this.uploadSpeed = 0;
          this.uploadTimeRemaining = null;
          this.uploadFileName = "";
          this.uploadCancelFunctions = [];
        }
      } finally {
        this.uploading = false;
        if (this.uploadProgress !== 100 && this.uploadProgress !== null) {
          // Only clear if not cancelled (cancelled state is handled above)
          if (!this.uploadError || this.uploadError !== "Upload cancelled") {
            this.uploadProgress = null;
            this.uploadSpeed = 0;
            this.uploadTimeRemaining = null;
            this.uploadFileName = "";
          }
        }
        // Reset cancel flag
        this.uploadCancelled = false;
      }
    },

    handleUploadCancel() {
      // Set cancellation flag
      this.uploadCancelled = true;
      // Cancel all active uploads
      this.uploadCancelFunctions.forEach((cancelFn) => {
        if (cancelFn) {
          cancelFn();
        }
      });
      this.uploadCancelFunctions = [];

      // Show cancellation message immediately (only once)
      if (!this.uploadCancellationMessageShown) {
        // Always show alert modal for visibility, and also try toast notification
        this.showAlert({
          type: "info",
          title: "Upload Cancelled",
          message: "The upload has been cancelled successfully.",
        });

        // Also try to show toast notification if available (non-blocking)
        if (
          window.Notifications &&
          typeof window.Notifications.info === "function"
        ) {
          window.Notifications.info("Upload cancelled", 3000);
        }

        this.uploadCancellationMessageShown = true;
      }
    },

    async downloadFile(file) {
      try {
        if (!this.vaultspaceKey) {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "VaultSpace key not loaded",
          });
          return;
        }

        // Initialize download progress
        this.downloading = true;
        this.downloadProgress = 0;
        this.downloadSpeed = 0;
        this.downloadTimeRemaining = null;
        this.downloadFileName = file.original_name || file.name || "file";

        // Get file and encrypted FileKey from server
        const fileData = await files.get(file.id, this.$route.params.id);

        // Decrypt FileKey with VaultSpace key
        const fileKey = await decryptFileKey(
          this.vaultspaceKey,
          fileData.file_key.encrypted_key,
        );

        // Download encrypted file data from server with progress callback
        const encryptedDataArrayBuffer = await files.download(
          file.id,
          this.$route.params.id,
          (loaded, total, speed, timeRemaining) => {
            if (total > 0) {
              this.downloadProgress = Math.round((loaded / total) * 100);
            }
            this.downloadSpeed = speed || 0;
            this.downloadTimeRemaining = timeRemaining;
          },
        );

        // Convert ArrayBuffer to Uint8Array
        const encryptedData = new Uint8Array(encryptedDataArrayBuffer);

        // Extract IV and encrypted content (IV is first 12 bytes)
        const iv = encryptedData.slice(0, 12);
        const encrypted = encryptedData.slice(12);

        // Update status for decryption phase
        this.downloadProgress = 95;
        this.downloadSpeed = 0;
        this.downloadTimeRemaining = null;

        // Decrypt file
        const decrypted = await decryptFile(fileKey, encrypted.buffer, iv);

        // Update progress to complete
        this.downloadProgress = 100;

        // Create blob and download
        const blob = new Blob([decrypted]);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = file.original_name;
        a.click();
        URL.revokeObjectURL(url);

        // Hide progress after a short delay
        setTimeout(() => {
          this.downloadProgress = null;
          this.downloadSpeed = 0;
          this.downloadTimeRemaining = null;
          this.downloadFileName = "";
        }, 1000);
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Download Failed",
          message: "Download failed: " + err.message,
        });
        this.downloadProgress = null;
        this.downloadSpeed = 0;
        this.downloadTimeRemaining = null;
        this.downloadFileName = "";
      } finally {
        this.downloading = false;
        if (this.downloadProgress !== 100) {
          this.downloadProgress = null;
          this.downloadSpeed = 0;
          this.downloadTimeRemaining = null;
          this.downloadFileName = "";
        }
      }
    },

    showDeleteConfirm(file) {
      this.itemToDelete = file;
      this.showDeleteConfirmModal = true;
      this.deleteError = null;
    },

    getDeleteMessage() {
      if (!this.itemToDelete) {
        return "Are you sure you want to move this item to trash? You can restore it from the trash later.";
      }
      const itemName = this.itemToDelete.original_name || "this item";
      const itemType =
        this.itemToDelete.mime_type === "application/x-directory"
          ? "folder"
          : "file";
      return `Are you sure you want to move "${itemName}" to trash? This ${itemType} will be moved to the trash and can be restored later.`;
    },

    async confirmDelete() {
      if (!this.itemToDelete) {
        return;
      }

      this.deleting = true;
      this.deleteError = null;

      const itemToDelete = this.itemToDelete; // Store reference before deletion
      const itemType =
        itemToDelete.mime_type === "application/x-directory"
          ? "Folder"
          : "File";

      try {
        await files.delete(itemToDelete.id);

        // Remove from appropriate list (optimistic update)
        if (itemToDelete.mime_type === "application/x-directory") {
          this.folders = this.folders.filter((f) => f.id !== itemToDelete.id);
        } else {
          this.filesList = this.filesList.filter(
            (f) => f.id !== itemToDelete.id,
          );
        }
        this.files = this.files.filter((f) => f.id !== itemToDelete.id);

        // Small delay to ensure cache invalidation is complete on server side
        await new Promise((resolve) => setTimeout(resolve, 50));

        // Refresh from server with cache-busting to ensure consistency
        await this.loadFilesInternal(this.currentParentId, true);

        this.showDeleteConfirmModal = false;
        this.itemToDelete = null;

        // Show success message
        if (window.Notifications) {
          window.Notifications.success(
            `${itemType} moved to trash successfully`,
          );
        }
      } catch (err) {
        this.deleteError = err.message || "Failed to move to trash";
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Failed to move to trash",
        });
      } finally {
        this.deleting = false;
      }
    },

    showAlert(config) {
      this.alertModalConfig = {
        type: config.type || "error",
        title: config.title || "Error",
        message: config.message || "",
      };
      this.showAlertModal = true;
    },
    handleAlertModalClose() {
      this.showAlertModal = false;
    },
    generateUniqueName(baseName, existingNames, isFile = false) {
      // For files, preserve extension
      let nameWithoutExt = baseName;
      let extension = "";
      if (isFile) {
        const lastDot = baseName.lastIndexOf(".");
        if (lastDot > 0) {
          nameWithoutExt = baseName.substring(0, lastDot);
          extension = baseName.substring(lastDot);
        }
      }

      // Check if base name is available
      if (!existingNames.has(baseName)) {
        return baseName;
      }

      // Find the next available number
      let counter = 1;
      let newName = isFile
        ? `${nameWithoutExt}(${counter})${extension}`
        : `${baseName}(${counter})`;

      while (existingNames.has(newName)) {
        counter++;
        newName = isFile
          ? `${nameWithoutExt}(${counter})${extension}`
          : `${baseName}(${counter})`;

        // Safety limit to prevent infinite loop
        if (counter > 1000) {
          // Use UUID as fallback to guarantee uniqueness
          const uuid = crypto.randomUUID().slice(0, 8);
          newName = isFile
            ? `${nameWithoutExt}(${uuid})${extension}`
            : `${baseName}(${uuid})`;
          break;
        }
      }

      return newName;
    },
    handleConflictReplace(applyToAll) {
      this.conflictApplyToAll = applyToAll;
      this.conflictResolution = "replace";
      this.showConflictModal = false;
    },
    handleConflictKeepBoth(applyToAll) {
      this.conflictApplyToAll = applyToAll;
      this.conflictResolution = "keep-both";
      this.showConflictModal = false;
    },
    handleConflictSkip(applyToAll) {
      this.conflictApplyToAll = applyToAll;
      this.conflictResolution = "skip";
      this.showConflictModal = false;
    },
    handleConflictClose() {
      // If closed without action, treat as skip
      if (!this.conflictResolution) {
        this.conflictResolution = "skip";
      }
      this.showConflictModal = false;
    },
    async initSharingManager(fileId) {
      try {
        // Check if sharing manager is already available
        if (window.sharingManager) {
          window.sharingManager.showShareModal(fileId, "file");
          return;
        }

        // Try to use the showShareModalAdvanced function if available
        if (window.showShareModalAdvanced) {
          window.showShareModalAdvanced(fileId, "file");
          return;
        }

        // Wait for SharingManager to initialize (it's loaded in index.html)
        let retries = 0;
        const maxRetries = 30; // 3 seconds max
        const checkInterval = setInterval(() => {
          retries++;
          if (window.sharingManager) {
            clearInterval(checkInterval);
            window.sharingManager.showShareModal(fileId, "file");
          } else if (window.showShareModalAdvanced) {
            clearInterval(checkInterval);
            window.showShareModalAdvanced(fileId, "file");
          } else if (retries >= maxRetries) {
            clearInterval(checkInterval);
            this.showAlert({
              type: "error",
              title: "Error",
              message:
                "Share functionality is not available. Please refresh the page.",
            });
          }
        }, 100);
      } catch (err) {
        console.error("Error initializing sharing manager:", err);
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to open share dialog. Please refresh the page.",
        });
      }
    },

    showFileMenu(file, event) {
      // Context menu implementation would go here
    },

    formatSize(bytes) {
      if (bytes === 0) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    },

    formatDate(dateString) {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleDateString();
    },

    // Selection methods
    toggleSelection(item) {
      const index = this.selectedItems.findIndex((i) => i.id === item.id);
      if (index >= 0) {
        this.selectedItems.splice(index, 1);
      } else {
        this.selectedItems.push(item);
      }
    },

    isSelected(itemId) {
      return this.selectedItems.some((item) => item.id === itemId);
    },

    selectAll() {
      this.selectedItems = [...this.folders, ...this.filesList];
    },

    clearSelection() {
      this.selectedItems = [];
    },

    handleViewChange(mode) {
      this.viewMode = mode;
      localStorage.setItem("fileViewMode_vaultspace", mode);
    },

    handleSelectionChange(change) {
      if (change.action === "select") {
        if (!this.isSelected(change.item.id)) {
          this.selectedItems.push(change.item);
        }
      } else if (change.action === "deselect") {
        const index = this.selectedItems.findIndex(
          (i) => i.id === change.item.id,
        );
        if (index >= 0) {
          this.selectedItems.splice(index, 1);
        }
      } else if (change.action === "select-all") {
        this.selectedItems = [...change.items];
      } else if (change.action === "clear") {
        this.selectedItems = [];
      }
    },

    async handleSearchResultClick(item) {
      // Navigate to the file or folder from search results
      if (item.mime_type === "application/x-directory") {
        // Navigate to folder
        await this.navigateToFolder(item.id);
      } else {
        // Navigate to file - first navigate to its parent folder, then select the file
        const parentId = item.folder_id || item.parent_id || null;
        await this.navigateToFolder(parentId);

        // Wait for files to load and render
        await this.$nextTick();

        // Retry mechanism to find and select the file
        const maxRetries = 10;
        let retries = 0;

        const trySelectFile = () => {
          // Find the file in the loaded files
          const allItems = [...this.folders, ...this.filesList];
          const fileItem = allItems.find((f) => f.id === item.id);

          if (fileItem) {
            // Clear selection and select the file
            this.clearSelection();
            this.toggleSelection(fileItem);

            // Scroll to the file after a short delay to ensure it's rendered
            setTimeout(() => {
              const fileElement = document.querySelector(
                `[data-file-id="${item.id}"], [data-folder-id="${item.id}"]`,
              );
              if (fileElement) {
                fileElement.scrollIntoView({
                  behavior: "smooth",
                  block: "center",
                });
                // Add a highlight effect
                fileElement.classList.add("search-highlighted");
                setTimeout(() => {
                  fileElement.classList.remove("search-highlighted");
                }, 2000);
              }
            }, 100);
          } else if (retries < maxRetries) {
            // File not found yet, retry after a short delay
            retries++;
            setTimeout(trySelectFile, 100);
          }
        };

        // Start trying to select the file
        setTimeout(trySelectFile, 200);
      }
    },

    handleItemClick(item, event) {
      // If clicking checkbox, don't navigate
      if (event.target.type === "checkbox") {
        return;
      }

      // If Ctrl/Cmd key is pressed, toggle selection
      if (event.ctrlKey || event.metaKey) {
        this.toggleSelection(item);
        return;
      }

      // If Shift key is pressed, select range
      if (event.shiftKey && this.selectedItems.length > 0) {
        // Select range from last selected to current
        const allItems = [...this.folders, ...this.filesList];
        const lastSelectedIndex = allItems.findIndex(
          (i) => i.id === this.selectedItems[this.selectedItems.length - 1].id,
        );
        const currentIndex = allItems.findIndex((i) => i.id === item.id);

        if (lastSelectedIndex >= 0 && currentIndex >= 0) {
          const start = Math.min(lastSelectedIndex, currentIndex);
          const end = Math.max(lastSelectedIndex, currentIndex);
          const range = allItems.slice(start, end + 1);
          this.selectedItems = [...new Set([...this.selectedItems, ...range])];
        }
        return;
      }

      // Normal click: navigate for folders, select for files
      if (item.mime_type === "application/x-directory") {
        // Clear selection before navigating to folder
        this.clearSelection();
        if (window.selectionManager) {
          window.selectionManager.deselectAll();
        }
        // navigateToFolder will update the URL
        this.navigateToFolder(item.id);
      } else {
        // For files, toggle selection if not already selected
        if (!this.isSelected(item.id)) {
          this.clearSelection();
          this.toggleSelection(item);
        }
      }
    },

    handleFileAction(action, item, newName = null) {
      if (action === "download") {
        this.downloadFile(item);
      } else if (action === "preview") {
        this.showFilePreview(item);
      } else if (action === "delete") {
        this.showDeleteConfirm(item);
      } else if (action === "properties") {
        this.showFileProperties(item.id);
      } else if (action === "star") {
        this.toggleStar(item);
      } else if (action === "rename") {
        if (newName) {
          // Save rename with new name
          this.handleRename(item, newName);
        } else {
          // Start editing
          this.editingItemId = item.id;
        }
      } else if (action === "copy") {
        this.handleCopyAction(item);
      } else if (action === "share") {
        // Open share modal using SharingManager
        if (window.sharingManager) {
          window.sharingManager.showShareModal(
            item.id,
            "file",
            this.$route.params.id,
            this.vaultspaceKey,
          );
        } else {
          // Fallback: try to load sharing manager
          this.initSharingManager(item.id);
        }
      } else if (action === "zip-folder") {
        this.handleZipFolder(item);
      } else if (action === "extract-zip") {
        this.handleExtractZip(item);
      } else if (action === "cancel-rename") {
        this.editingItemId = null;
      }
    },

    handleContextMenu(item, event) {
      // Right-click context menu - could be enhanced with a custom menu component
      // For now, just show properties
      event.preventDefault();
      this.showFileProperties(item.id);
    },

    showFileProperties(fileId) {
      this.propertiesFileId = fileId;
      this.showProperties = true;
    },

    showFilePreview(item) {
      // Clear selection when opening preview
      this.clearSelection();
      if (window.selectionManager) {
        window.selectionManager.deselectAll();
        window.selectionManager.updateUI();
      }

      this.previewFileId = item.id;
      this.previewFileName = item.original_name || item.name || "File";
      this.previewMimeType = item.mime_type || "";
      this.showPreview = true;
    },

    handlePreviewDownload(fileId) {
      const file = this.filesList.find((f) => f.id === fileId);
      if (file) {
        this.downloadFile(file);
      }
    },

    handleRevokeConfirm() {
      this.showRevokeConfirm = false;
      if (this.pendingRevokeCallback) {
        const callback = this.pendingRevokeCallback;
        this.pendingRevokeCallback = null;
        callback();
      }
    },

    async handlePasswordModalSubmit() {
      if (!this.passwordModalPassword) {
        this.passwordModalError = "Password is required";
        return;
      }

      this.passwordModalError = "";
      this.passwordModalLoading = true;

      try {
        // Get master key salt from API
        // Use direct fetch to avoid automatic logout on 401
        const token = localStorage.getItem("jwt_token");
        if (!token) {
          throw new Error(
            "No authentication token found. Please log in again.",
          );
        }

        const response = await fetch("/api/auth/account/master-key-salt", {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
        });

        if (!response.ok) {
          if (response.status === 401) {
            throw new Error("Authentication failed. Please log in again.");
          }
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || "Failed to get master key salt");
        }

        const data = await response.json();
        const saltBase64 = data.master_key_salt;
        if (!saltBase64) {
          throw new Error("Master key salt not available");
        }

        // Convert base64 salt to Uint8Array
        const saltStr = atob(saltBase64);
        const salt = Uint8Array.from(saltStr, (c) => c.charCodeAt(0));

        // Derive master key from password and salt
        const masterKey = await initializeUserMasterKey(
          this.passwordModalPassword,
          salt,
        );

        if (!masterKey) {
          throw new Error("Failed to derive master key");
        }

        // Close modal and clear password
        this.showPasswordModal = false;
        this.passwordModalPassword = "";
        this.passwordModalError = "";

        // Hide overlay and mark master key as no longer required
        this.showEncryptionOverlay = false;
        this.isMasterKeyRequired = false;

        // Reload VaultSpace with the new master key
        await this.loadVaultSpace();
        await this.loadVaultSpaceKey();
        await this.loadFiles();
      } catch (err) {
        logger.error("Failed to initialize master key:", err);
        this.passwordModalError =
          err.message || "Failed to initialize encryption. Please try again.";
      } finally {
        this.passwordModalLoading = false;
      }
    },

    closePasswordModal() {
      if (!this.passwordModalLoading) {
        this.showPasswordModal = false;
        this.passwordModalPassword = "";
        this.passwordModalError = "";
        // Keep overlay visible if master key is still required
        // Don't hide overlay on cancel - user needs to unlock to proceed
      }
    },
    openPasswordModal() {
      this.showPasswordModal = true;
    },
    calculateOverlayPosition() {
      // Calculate position to cover page-content (which contains view-header and view-main)
      // but not app-header (which is outside page-content)
      // The overlay should cover the entire content area without margins,
      // starting below the header and next to the sidebar
      this.$nextTick(() => {
        const header = document.querySelector(".app-header");
        const pageContent = document.querySelector(".page-content");
        if (header && pageContent) {
          const headerRect = header.getBoundingClientRect();
          const pageContentRect = pageContent.getBoundingClientRect();
          // Calculate overlay to start exactly below the header
          // and extend to the right edge of viewport and bottom of viewport
          const overlayTop = headerRect.bottom; // Start exactly below header
          const overlayLeft = pageContentRect.left; // Start at page-content left edge
          const overlayWidth = window.innerWidth - overlayLeft;
          const overlayHeight = window.innerHeight - overlayTop;

          this.overlayStyle = {
            position: "fixed",
            top: `${overlayTop}px`,
            left: `${overlayLeft}px`,
            width: `${overlayWidth}px`,
            height: `${overlayHeight}px`,
            zIndex: 0, // Below header (z-index: 1) and sidebar (z-index: 100)
          };
        }
      });
    },
    observeSidebarChanges() {
      // Observe sidebar width changes to recalculate overlay position
      const sidebar = document.querySelector(".sidebar");
      if (sidebar && window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          // Use requestAnimationFrame to ensure DOM has updated
          requestAnimationFrame(() => {
            this.calculateOverlayPosition();
          });
        });
        observer.observe(sidebar);
        this._sidebarResizeObserver = observer;
      }

      // Observe header changes (height might change)
      const header = document.querySelector(".app-header");
      if (header && window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          requestAnimationFrame(() => {
            this.calculateOverlayPosition();
          });
        });
        observer.observe(header);
      }

      // Also observe main-content changes (which moves when sidebar toggles)
      const mainContent = document.querySelector(".main-content");
      if (mainContent && window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          requestAnimationFrame(() => {
            this.calculateOverlayPosition();
          });
        });
        observer.observe(mainContent);
        this._mainContentResizeObserver = observer;
      }

      // Also observe page-content directly
      const pageContent = document.querySelector(".page-content");
      if (pageContent && window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          requestAnimationFrame(() => {
            this.calculateOverlayPosition();
          });
        });
        observer.observe(pageContent);
        this._pageContentResizeObserver = observer;
      }
    },
    protectOverlay() {
      // Protect overlay from being removed via DevTools
      // Check periodically if overlay still exists and recreate if needed
      if (this._overlayProtectionInterval) {
        clearInterval(this._overlayProtectionInterval);
      }

      this._overlayProtectionInterval = setInterval(() => {
        if (this.showEncryptionOverlay && this.isMasterKeyRequired) {
          const overlay = document.querySelector(
            '[data-encryption-overlay="true"]',
          );
          if (!overlay) {
            // Overlay was removed, force re-render
            this.$forceUpdate();
            this.$nextTick(() => {
              this.calculateOverlayPosition();
            });
          }
        }
      }, 500);

      // Also use MutationObserver to detect removal
      const observer = new MutationObserver((mutations) => {
        if (this.showEncryptionOverlay && this.isMasterKeyRequired) {
          const overlay = document.querySelector(
            '[data-encryption-overlay="true"]',
          );
          if (!overlay) {
            // Overlay was removed, force re-render
            this.$forceUpdate();
            this.$nextTick(() => {
              this.calculateOverlayPosition();
            });
          }
        }
      });

      const body = document.body;
      if (body) {
        observer.observe(body, {
          childList: true,
          subtree: true,
        });
        this._overlayMutationObserver = observer;
      }
    },

    async handleInlineRename(item) {
      this.editingItemId = item.id;
    },

    async handleRename(item, newName) {
      try {
        await files.rename(item.id, newName);

        // Optimistic update for immediate UI feedback
        const index = this.filesList.findIndex((f) => f.id === item.id);
        if (index >= 0) {
          this.filesList[index].original_name = newName;
        }
        const folderIndex = this.folders.findIndex((f) => f.id === item.id);
        if (folderIndex >= 0) {
          this.folders[folderIndex].original_name = newName;
        }
        const fileIndex = this.files.findIndex((f) => f.id === item.id);
        if (fileIndex >= 0) {
          this.files[fileIndex].original_name = newName;
        }

        // Refresh from server with cache-busting to ensure consistency
        await this.loadFilesInternal(this.currentParentId, true);

        this.editingItemId = null;
      } catch (err) {
        // Check if it's a 409 conflict error
        const isConflict =
          err.message &&
          (err.message.toLowerCase().includes("already exists") ||
            err.message.includes("409") ||
            err.message.includes("CONFLICT"));

        if (isConflict) {
          // Store pending rename info
          this.pendingRenameItem = item;
          this.pendingRenameNewName = newName;
          this.conflictApplyToAll = false;
          this.conflictResolution = null;

          // Show conflict modal
          this.conflictData = {
            title: "Name Already Exists",
            message: `A file or folder named "${newName}" already exists in this folder.`,
            showApplyToAll: false,
            remainingCount: null,
          };
          this.showConflictModal = true;

          // Wait for user decision
          await new Promise((resolve) => {
            const checkResolution = () => {
              if (this.conflictResolution) {
                resolve();
              } else {
                setTimeout(checkResolution, 100);
              }
            };
            checkResolution();
          });

          // Store resolution
          const resolution = this.conflictResolution;
          const renameItem = this.pendingRenameItem;
          const renameNewName = this.pendingRenameNewName;
          this.pendingRenameItem = null;
          this.pendingRenameNewName = null;
          this.conflictResolution = null;

          // Handle resolution
          if (resolution === "skip") {
            // Cancel rename
            this.editingItemId = null;
            return;
          } else if (resolution === "replace") {
            // Delete existing item then rename (backend doesn't support overwrite for rename)
            try {
              // Find existing item with the same name
              const existingItem = this.filesList.find(
                (f) =>
                  f.original_name === renameNewName &&
                  f.id !== renameItem.id &&
                  f.parent_id === renameItem.parent_id,
              );

              if (existingItem) {
                // Delete existing item
                await files.delete(existingItem.id);
              }

              // Now rename
              await files.rename(renameItem.id, renameNewName);

              // Optimistic update
              const index = this.filesList.findIndex(
                (f) => f.id === renameItem.id,
              );
              if (index >= 0) {
                this.filesList[index].original_name = renameNewName;
              }
              const folderIndex = this.folders.findIndex(
                (f) => f.id === renameItem.id,
              );
              if (folderIndex >= 0) {
                this.folders[folderIndex].original_name = renameNewName;
              }
              const fileIndex = this.files.findIndex(
                (f) => f.id === renameItem.id,
              );
              if (fileIndex >= 0) {
                this.files[fileIndex].original_name = renameNewName;
              }

              await this.loadFilesInternal(this.currentParentId, true);
              this.editingItemId = null;
            } catch (replaceErr) {
              this.showAlert({
                type: "error",
                title: "Error",
                message: `Failed to replace: ${replaceErr.message}`,
              });
              this.editingItemId = null;
            }
          } else if (resolution === "keep-both") {
            // Generate unique name and retry
            const existingNames = new Set(
              this.filesList
                .filter(
                  (f) =>
                    f.id !== renameItem.id &&
                    f.parent_id === renameItem.parent_id,
                )
                .map((f) => f.original_name || f.name || ""),
            );
            const uniqueName = this.generateUniqueName(
              renameNewName,
              existingNames,
              renameItem.mime_type !== "application/x-directory",
            );

            try {
              await files.rename(renameItem.id, uniqueName);

              // Optimistic update
              const index = this.filesList.findIndex(
                (f) => f.id === renameItem.id,
              );
              if (index >= 0) {
                this.filesList[index].original_name = uniqueName;
              }
              const folderIndex = this.folders.findIndex(
                (f) => f.id === renameItem.id,
              );
              if (folderIndex >= 0) {
                this.folders[folderIndex].original_name = uniqueName;
              }
              const fileIndex = this.files.findIndex(
                (f) => f.id === renameItem.id,
              );
              if (fileIndex >= 0) {
                this.files[fileIndex].original_name = uniqueName;
              }

              await this.loadFilesInternal(this.currentParentId, true);
              this.editingItemId = null;
            } catch (keepBothErr) {
              this.showAlert({
                type: "error",
                title: "Error",
                message: `Failed to rename: ${keepBothErr.message}`,
              });
              this.editingItemId = null;
            }
          }
        } else {
          this.showAlert({
            type: "error",
            title: "Error",
            message: err.message || "Error renaming",
          });
          this.editingItemId = null;
        }
      }
    },

    async handleMove(item, newParentId) {
      try {
        const updatedFile = await files.move(item.id, newParentId);

        // Optimistic update for immediate UI feedback
        const index = this.filesList.findIndex((f) => f.id === item.id);
        if (index >= 0) {
          this.filesList[index] = updatedFile;
        }
        const folderIndex = this.folders.findIndex((f) => f.id === item.id);
        if (folderIndex >= 0) {
          this.folders[folderIndex] = updatedFile;
        }
        const fileIndex = this.files.findIndex((f) => f.id === item.id);
        if (fileIndex >= 0) {
          this.files[fileIndex] = updatedFile;
        }
        if (newParentId !== this.currentParentId) {
          this.folders = this.folders.filter((f) => f.id !== item.id);
          this.filesList = this.filesList.filter((f) => f.id !== item.id);
          this.files = this.files.filter((f) => f.id !== item.id);
        }

        // Small delay to ensure cache invalidation is complete on server side
        await new Promise((resolve) => setTimeout(resolve, 50));

        // Refresh from server with cache-busting to ensure consistency
        await this.loadFilesInternal(this.currentParentId, true);
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Error moving",
        });
        throw err; // Re-throw to allow caller to handle
      }
    },

    async handleCopyAction(item) {
      try {
        // Verify folderPicker is available
        if (!folderPicker) {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "Folder picker is not available. Please refresh the page.",
          });
          return;
        }

        // Get folders at the same level as the current item
        const itemParentId = item.parent_id || this.currentParentId;
        const allFolders = await this.getAllFolders(itemParentId);

        if (allFolders.length === 0) {
          this.showAlert({
            type: "info",
            title: "No Folders",
            message: "No folders available. You can only copy to the root.",
          });
        }

        // Show folder picker
        const selectedFolderId = await folderPicker.show(
          allFolders,
          this.currentParentId,
          this.$route.params.id,
          item.mime_type === "application/x-directory" ? item.id : null,
        );

        // User cancelled
        if (selectedFolderId === undefined) {
          return;
        }

        // Perform copy
        await this.handleCopy(item, selectedFolderId, null);

        // Reload files to show the new copy
        await this.loadFiles();

        // Show success message
        if (window.Notifications) {
          window.Notifications.success(
            `${item.mime_type === "application/x-directory" ? "Folder" : "File"} copied successfully`,
          );
        }
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Failed to copy item",
        });
      }
    },

    async getAllFolders(parentId = null) {
      // Get folders at the same level (same parent_id) as the current item
      // Only return sibling folders, not root and not subfolders
      try {
        if (!this.$route.params.id) {
          return [];
        }

        // Use the provided parentId or currentParentId
        const targetParentId =
          parentId !== undefined ? parentId : this.currentParentId;

        // Load folders from the same parent, paginating if necessary
        const allFolders = [];
        let page = 1;
        const perPage = 100; // API maximum
        let hasMorePages = true;

        while (hasMorePages) {
          const result = await files.list(
            this.$route.params.id,
            targetParentId,
            page,
            perPage,
            true, // cache-bust to ensure fresh data
          );

          const folders = (result.files || []).filter(
            (f) => f.mime_type === "application/x-directory",
          );

          allFolders.push(...folders);

          // Check if there are more pages
          const totalPages = result.pagination?.pages || 1;
          hasMorePages = page < totalPages;
          page++;
        }

        return allFolders;
      } catch (err) {
        return [];
      }
    },

    async handleZipFolder(folder) {
      try {
        if (!this.vaultspaceKey) {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "VaultSpace key not loaded",
          });
          return;
        }

        if (folder.mime_type !== "application/x-directory") {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "Selected item is not a folder",
          });
          return;
        }

        // Initialize ZIP progress
        this.zipping = true;
        this.zipProgress = 0;
        this.zipMessage = `Preparing ${folder.original_name}...`;

        try {
          // Zip the folder
          const zipFileId = await zipFolder(
            folder.id,
            this.$route.params.id,
            this.vaultspaceKey,
            (current, total, message) => {
              // Update progress
              if (total > 0) {
                this.zipProgress = Math.round((current / total) * 100);
              } else {
                this.zipProgress = current;
              }
              this.zipMessage = message || `Zipping ${folder.original_name}...`;
            },
          );

          // Reload files to show the new ZIP file
          await this.loadFiles();

          // Show success message
          if (window.Notifications) {
            window.Notifications.success(
              `Folder "${folder.original_name}" zipped successfully`,
            );
          }
        } finally {
          this.zipping = false;
          this.zipProgress = null;
          this.zipMessage = "";
        }
      } catch (err) {
        logger.error("Failed to zip folder:", err);
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Failed to zip folder. Please try again.",
        });
        this.zipping = false;
        this.zipProgress = null;
        this.zipMessage = "";
      }
    },

    async handleExtractZip(zipFile) {
      try {
        if (!this.vaultspaceKey) {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "VaultSpace key not loaded",
          });
          return;
        }

        const isZipFile =
          zipFile.mime_type === "application/zip" ||
          zipFile.mime_type === "application/x-zip-compressed" ||
          (zipFile.original_name &&
            zipFile.original_name.toLowerCase().endsWith(".zip"));

        if (!isZipFile) {
          this.showAlert({
            type: "error",
            title: "Error",
            message: "Selected file is not a ZIP file",
          });
          return;
        }

        // Initialize extract progress
        this.extracting = true;
        this.extractProgress = 0;
        this.extractMessage = `Preparing extraction of ${zipFile.original_name}...`;

        try {
          // Extract the ZIP file
          const extractedFolderId = await extractZip(
            zipFile.id,
            this.$route.params.id,
            this.vaultspaceKey,
            this.currentParentId,
            (current, total, message) => {
              // Update progress
              if (total > 0) {
                this.extractProgress = Math.round((current / total) * 100);
              } else {
                this.extractProgress = current;
              }
              this.extractMessage =
                message || `Extracting ${zipFile.original_name}...`;
            },
          );

          // Reload files to show extracted files
          await this.loadFiles();

          // Show success message
          if (window.Notifications) {
            window.Notifications.success(
              `ZIP file "${zipFile.original_name}" extracted successfully`,
            );
          }
        } finally {
          this.extracting = false;
          this.extractProgress = null;
          this.extractMessage = "";
        }
      } catch (err) {
        logger.error("Failed to extract ZIP:", err);
        this.showAlert({
          type: "error",
          title: "Error",
          message:
            err.message || "Failed to extract ZIP file. Please try again.",
        });
        this.extracting = false;
        this.extractProgress = null;
        this.extractMessage = "";
      }
    },

    async handleCopy(item, newParentId, newName) {
      try {
        const copiedFile = await files.copy(item.id, {
          newParentId: newParentId,
          newVaultspaceId: null, // Keep in same vaultspace
          newName: newName, // Keep same name unless specified
        });

        // Reload files to show the new copy with cache-busting
        await this.loadFilesInternal(this.currentParentId, true);
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Error copying",
        });
        throw err;
      }
    },

    handleDragStart(item, event) {
      // Drag data is already set in FileListView
    },

    handleDragOver(item, event) {
      // Visual feedback handled in FileListView
    },

    handleDragLeave(item, event) {
      // Visual feedback handled in FileListView
    },

    async handleDrop(targetFolder, event) {
      event.preventDefault();
      event.stopPropagation(); // Prevent other handlers from intercepting

      try {
        const dragData = JSON.parse(
          event.dataTransfer.getData("application/json"),
        );
        if (!dragData || !dragData.id) {
          return;
        }

        const sourceItem = this.files.find((f) => f.id === dragData.id);
        if (!sourceItem) {
          return;
        }

        const targetFolderId = targetFolder.id;
        if (sourceItem.id === targetFolderId) {
          return; // Can't drop on itself
        }

        // Clear clipboard to prevent copy operation
        if (clipboardManager) {
          clipboardManager.clear();
        }

        // Perform move (not copy)
        try {
          await this.handleMove(sourceItem, targetFolderId);

          // Show success notification
          if (window.Notifications) {
            window.Notifications.success(
              `${sourceItem.mime_type === "application/x-directory" ? "Folder" : "File"} moved successfully`,
            );
          }
        } catch (moveErr) {
          // Error is already handled in handleMove
          throw moveErr; // Re-throw to be caught by outer catch
        }
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Error moving item",
        });
      }
    },

    setupKeyboardShortcuts() {
      const handleKeyDown = (event) => {
        // Don't trigger shortcuts when typing in inputs
        if (
          event.target.tagName === "INPUT" ||
          event.target.tagName === "TEXTAREA" ||
          event.target.isContentEditable
        ) {
          // Allow Escape to cancel editing
          if (event.key === "Escape" && this.editingItemId) {
            this.editingItemId = null;
          }
          return;
        }

        // Ctrl+C or Cmd+C - Copy selected items
        if ((event.ctrlKey || event.metaKey) && event.key === "c") {
          event.preventDefault();
          if (this.selectedItems.length > 0) {
            clipboardManager.copy(this.selectedItems);
          }
        }

        // Ctrl+V or Cmd+V - Paste clipboard items
        if ((event.ctrlKey || event.metaKey) && event.key === "v") {
          event.preventDefault();
          if (clipboardManager.hasItems()) {
            this.handlePaste();
          }
        }

        // Escape - Cancel editing or close modals
        if (event.key === "Escape") {
          if (this.editingItemId) {
            this.editingItemId = null;
          }
        }
      };

      document.addEventListener("keydown", handleKeyDown);

      // Store handler for cleanup
      this._keyboardShortcutHandler = handleKeyDown;
    },

    async handlePaste() {
      const items = clipboardManager.getItems();
      if (items.length === 0) {
        return;
      }

      try {
        for (const item of items) {
          const sourceItem = this.files.find((f) => f.id === item.id);
          if (sourceItem) {
            await this.handleCopy(sourceItem, this.currentParentId, null);
          }
        }
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: err.message || "Error pasting items",
        });
      }
    },

    async toggleStar(file) {
      try {
        const updatedFile = await files.toggleStar(file.id);
        // Update in lists
        const index = this.filesList.findIndex((f) => f.id === file.id);
        if (index >= 0) {
          this.filesList[index].is_starred = updatedFile.is_starred;
        }
        const folderIndex = this.folders.findIndex((f) => f.id === file.id);
        if (folderIndex >= 0) {
          this.folders[folderIndex].is_starred = updatedFile.is_starred;
        }
        // Update in main files array
        const fileIndex = this.files.findIndex((f) => f.id === file.id);
        if (fileIndex >= 0) {
          this.files[fileIndex].is_starred = updatedFile.is_starred;
        }
      } catch (err) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: "Failed to toggle star: " + err.message,
        });
      }
    },

    async handleBatchDelete(result) {
      // Remove deleted items from lists
      const deletedIds = new Set(
        result.errors.length === 0
          ? this.selectedItems.map((i) => i.id)
          : this.selectedItems
              .filter((item) =>
                result.errors.every((e) => e.file_id !== item.id),
              )
              .map((i) => i.id),
      );

      this.folders = this.folders.filter((f) => !deletedIds.has(f.id));
      this.filesList = this.filesList.filter((f) => !deletedIds.has(f.id));
      this.files = this.files.filter((f) => !deletedIds.has(f.id));

      if (result.errors.length > 0) {
        this.showAlert({
          type: "error",
          title: "Error",
          message: `Some items could not be deleted: ${result.errors.map((e) => e.error).join(", ")}`,
        });
      }
    },

    async handleBatchDownload(items) {
      // Download files individually
      // In the future, we could create a ZIP file on the server
      for (const item of items) {
        if (item.mime_type !== "application/x-directory") {
          try {
            await this.downloadFile(item);
          } catch (err) {
            console.error(`Failed to download ${item.original_name}:`, err);
          }
        }
      }
    },
  },
};
</script>

<style scoped>
.vaultspace-view {
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.view-header {
  background: var(--bg-glass);
  backdrop-filter: var(--blur);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  box-shadow: var(--shadow-md);
  position: relative;
  z-index: 2;
}

.view-header h1 {
  margin: 0;
  flex: 1;
  text-align: center;
  color: var(--text-primary);
  font-size: 1.75rem;
  font-weight: 600;
}

.search-container {
  margin-bottom: 1.5rem;
  width: 100%;
}

.header-actions {
  display: flex;
  gap: 0.75rem;
  position: relative;
  z-index: 3;
}

.header-actions .btn {
  position: relative;
  z-index: 3;
  pointer-events: auto;
}

.view-header .btn-primary,
.header-actions .btn-primary {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: var(--text-primary, #e6eef6);
  box-shadow: none;
}

.view-header .btn-primary:hover,
.header-actions .btn-primary:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(148, 163, 184, 0.4);
  transform: translateY(0);
}

.view-main {
  max-width: 1400px;
  margin: 0 auto;
  position: relative;
}

.breadcrumbs {
  padding: 0.75rem 1.5rem;
  border-radius: var(--radius-md);
  margin-bottom: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.breadcrumb-link {
  background: none;
  border: none;
  color: var(--accent-blue);
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  font-size: 0.9rem;
}

.breadcrumb-link:hover {
  color: var(--accent-blue-dark);
}

.breadcrumb-active {
  font-weight: 600;
  color: var(--text-primary);
}

.breadcrumb-separator {
  color: var(--text-muted);
}

.files-list {
  padding: 2rem;
  border-radius: var(--radius-lg);
  min-height: 400px;
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  color: var(--text-secondary);
}

.empty-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 2rem;
}

.files-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1.5rem;
}

.file-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.5rem;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  position: relative;
  transition: all var(--transition-base);
  cursor: default;
}

.file-card.selected {
  border-color: var(--accent-blue, #38bdf8);
  background: rgba(56, 189, 248, 0.1);
}

.file-card.search-highlighted,
.grid-body-row.search-highlighted {
  position: relative;
  animation: searchHighlight 0.5s ease-in-out;
  border-color: var(--accent-blue, #38bdf8) !important;
  box-shadow: 0 0 20px rgba(56, 189, 248, 0.5);
}

.file-card.search-highlighted::before,
.grid-body-row.search-highlighted::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(56, 189, 248, 0.2);
  border-radius: inherit;
  z-index: -1;
  animation: searchPulse 2s ease-in-out;
}

@keyframes searchHighlight {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
  }
}

@keyframes searchPulse {
  0%,
  100% {
    opacity: 0.2;
  }
  50% {
    opacity: 0.4;
  }
}

.file-checkbox {
  margin-right: 0.75rem;
  margin-top: 0.25rem;
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.selection-controls {
  grid-column: 1 / -1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: var(--radius-md, 8px);
}

.selection-count {
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
}

.file-card:hover {
  border-color: var(--border-color-hover);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.folder-card {
  cursor: pointer;
}

.folder-card:hover {
  background: var(--bg-glass-hover);
}

.file-icon {
  font-size: 3.5rem;
  text-align: center;
  margin-bottom: 1rem;
}

.file-info {
  flex: 1;
}

.file-info h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  word-break: break-word;
  color: var(--text-primary);
}

.file-size,
.file-date,
.file-type {
  margin: 0.25rem 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.file-type {
  font-style: italic;
}

.file-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
  justify-content: flex-end;
}

.btn-icon {
  background: var(--bg-glass);
  backdrop-filter: var(--blur);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0.5rem;
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-base);
}

.btn-icon:hover {
  background: var(--bg-glass-hover);
  border-color: var(--border-color-hover);
  transform: scale(1.1);
}

.btn-back {
  background: var(--bg-glass);
  backdrop-filter: var(--blur);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
}

.btn-back:hover {
  background: var(--bg-glass-hover);
  color: var(--text-primary);
}

.loading,
.error {
  padding: 3rem;
  text-align: center;
  color: var(--text-secondary);
  font-size: 1.1rem;
}

.error {
  color: var(--error);
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
}

.modal-overlay {
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  background: rgba(7, 14, 28, 0.4) !important;
  backdrop-filter: blur(15px) !important;
  -webkit-backdrop-filter: blur(15px) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 10000 !important;
  visibility: visible !important;
  opacity: 1 !important;
  padding: 2rem !important;
  padding-left: calc(
    2rem + 250px
  ) !important; /* Default: sidebar expanded (250px) */
  overflow-y: auto !important;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(2rem + 70px) !important; /* Sidebar collapsed (70px) */
}

.modal {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  ) !important;
  backdrop-filter: blur(40px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
  padding: 2rem !important;
  border-radius: 2rem !important;
  min-width: 400px !important;
  max-width: 90vw !important;
  max-height: 90vh !important;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
  position: relative !important;
  z-index: 10001 !important;
  visibility: visible !important;
  opacity: 1 !important;
  color: var(--text-primary, #f1f5f9) !important;
  display: flex !important;
  flex-direction: column !important;
  box-sizing: border-box !important;
  overflow-y: auto !important;
}

.modal-header {
  padding: 1.5rem !important;
  margin-bottom: 1.5rem !important;
  border-bottom: 1px solid var(--border-color) !important;
  flex-shrink: 0 !important;
}

.modal-content {
  padding: 0 !important;
  flex: 1 !important;
  overflow-y: auto !important;
}

.modal-form {
  padding: 0 !important;
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 1.25rem !important;
}

.modal h2 {
  margin: 0 !important;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center !important;
}

.modal p {
  color: var(--text-secondary);
  margin-bottom: 1.5rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.modal .form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.modal .form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-weight: 500;
}

.modal .form-group input {
  width: 100%;
  padding: 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #e6eef6;
  font-size: 0.95rem;
  font-family: inherit;
  box-sizing: border-box;
}

.modal .form-group input:focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.5);
  background: rgba(255, 255, 255, 0.08);
}

.modal .form-group input::placeholder {
  color: rgba(148, 163, 184, 0.6);
}

.form-actions {
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
  flex-shrink: 0;
  margin-bottom: 0;
}

.modal .form-actions {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 0px !important;
  margin-bottom: 0;
  padding-bottom: 0;
}

.upload-progress {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--bg-glass);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-secondary);
}

.error-message {
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md);
  color: var(--error);
  margin-bottom: 1.5rem;
}

.file-input-hidden {
  display: none !important;
  visibility: hidden !important;
  position: absolute !important;
  width: 0 !important;
  height: 0 !important;
  opacity: 0 !important;
  pointer-events: none !important;
}

.form-group input[type="file"] {
  padding: var(--space-2);
  cursor: pointer;
}

.form-group input[type="file"]::file-selector-button {
  background: var(--bg-glass);
  backdrop-filter: var(--blur);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  padding: var(--space-2) var(--space-3);
  margin-right: var(--space-3);
  cursor: pointer;
  transition: all var(--transition-base);
}

.form-group input[type="file"]::file-selector-button:hover {
  background: var(--bg-glass-hover);
  border-color: var(--border-color-hover);
}

.selected-files {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: var(--radius-md, 8px);
}

.selected-files ul {
  margin: 0.5rem 0 0 0;
  padding-left: 1.5rem;
  color: var(--text-secondary, #cbd5e1);
}

.selected-files li {
  margin: 0.25rem 0;
  font-size: 0.9rem;
}
/* Password Modal Styles */
.password-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(7, 14, 28, 0.4);
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
  border-radius: 2rem;
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
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  flex: 1;
}

.password-modal-close {
  background: none;
  border: none;
  color: #cbd5e1;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.password-modal-close:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  color: #e6eef6;
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
  color: #cbd5e1;
  font-size: 1rem;
  line-height: 1.6;
}

.password-modal-body .form-group {
  margin-bottom: 1.5rem;
}

.password-modal-body .form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-weight: 500;
  font-size: 0.95rem;
}

.password-modal-body .form-input {
  width: 100%;
  padding: 0.75rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.5rem;
  color: #e6eef6;
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
  color: rgba(148, 163, 184, 0.6);
}

.password-modal-error {
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.5rem;
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
  border-radius: 0.5rem;
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
  background: rgba(148, 163, 184, 0.2);
  color: #e6eef6;
}

.password-modal-btn-cancel:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.3);
}

.password-modal-btn-unlock {
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  color: white;
}

.password-modal-btn-unlock:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .password-modal-container {
    max-width: 100%;
    margin: 0 1rem;
  }

  .password-modal-content {
    border-radius: 1rem;
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

/* Encryption Overlay (Glassmorphic) */
.encryption-overlay {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.15),
    rgba(15, 23, 42, 0.12)
  ) !important;
  backdrop-filter: blur(40px) saturate(180%) !important;
  -webkit-backdrop-filter: blur(40px) saturate(180%) !important;
  border: none !important;
  border-radius: 0 0 0 1rem !important; /* Rounded bottom-left corner to match sidebar */
  box-shadow: none !important;
  animation: overlayFadeIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) !important;
  /* pointer-events is controlled via inline style */
  /* Ensure overlay covers content but stays below modals */
  isolation: isolate !important;
  pointer-events: auto !important;
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
  display: flex !important;
  flex-direction: column !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
  padding: 3rem 2rem !important;
  max-width: 500px !important;
  animation: gentlePulse 3s ease-in-out infinite !important;
  pointer-events: auto !important;
  position: relative !important;
  z-index: 10000 !important;
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
  padding: 0.875rem 2rem !important;
  font-size: 1rem !important;
  font-weight: 500 !important;
  color: #ffffff !important;
  background: linear-gradient(
    135deg,
    rgba(88, 166, 255, 0.2),
    rgba(56, 189, 248, 0.15)
  ) !important;
  backdrop-filter: blur(20px) saturate(150%) !important;
  -webkit-backdrop-filter: blur(20px) saturate(150%) !important;
  border: 1px solid rgba(88, 166, 255, 0.3) !important;
  border-radius: 0.75rem !important;
  cursor: pointer !important;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
  box-shadow:
    0 4px 16px rgba(88, 166, 255, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
  font-family: inherit !important;
  position: relative !important;
  overflow: hidden !important;
  pointer-events: auto !important;
  z-index: 10001 !important;
  user-select: none !important;
  -webkit-user-select: none !important;
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
}
</style>
