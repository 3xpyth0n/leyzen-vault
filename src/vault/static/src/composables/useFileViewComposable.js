/**
 * Composable for file view functionality shared across VaultSpaceView, StarredView, and RecentView.
 *
 * Provides:
 * - Selection management (single, multiple, range selection)
 * - View mode management (grid/list with localStorage persistence)
 * - Encryption overlay management for SSO users
 */

import { ref, computed, onMounted, onUnmounted, nextTick } from "vue";
import {
  getUserMasterKey,
  getStoredSalt,
  initializeUserMasterKey,
} from "../services/keyManager";
import { useAuthStore } from "../store/auth";
import { clipboardManager } from "../utils/clipboard";
import { logger } from "../utils/logger.js";

/**
 * Composable for file view functionality
 *
 * @param {Object} options - Configuration options
 * @param {string} options.viewType - Type of view: 'vaultspace' | 'starred' | 'recent'
 * @param {boolean} options.enableEncryptionCheck - Whether to check for encryption access
 * @param {Function} options.onEncryptionUnlocked - Callback when encryption is unlocked
 * @returns {Object} Composable API
 */
export function useFileViewComposable(options = {}) {
  const authStore = useAuthStore();
  const {
    viewType = "vaultspace",
    enableEncryptionCheck = false,
    onEncryptionUnlocked = null,
  } = options;

  // Selection state
  const selectedItems = ref([]);

  // View mode state (persisted in localStorage)
  const viewModeStorageKey = `fileViewMode_${viewType}`;
  const viewMode = ref(localStorage.getItem(viewModeStorageKey) || "grid");

  // Encryption overlay state
  const showEncryptionOverlay = ref(false);
  const isMasterKeyRequired = ref(false);
  const showPasswordModal = ref(false);
  const passwordModalPassword = ref("");
  const passwordModalError = ref("");
  const passwordModalLoading = ref(false);

  /**
   * Check if an item is selected
   * @param {string|number} itemId - Item ID
   * @returns {boolean}
   */
  const isSelected = (itemId) => {
    return selectedItems.value.some((item) => item.id === itemId);
  };

  /**
   * Toggle selection of an item
   * @param {Object} item - Item to toggle
   */
  const toggleSelection = (item) => {
    const index = selectedItems.value.findIndex((i) => i.id === item.id);
    if (index >= 0) {
      selectedItems.value.splice(index, 1);
    } else {
      selectedItems.value.push(item);
    }
  };

  /**
   * Clear all selections
   */
  const clearSelection = () => {
    selectedItems.value = [];
  };

  /**
   * Select all items
   * @param {Array} items - Items to select
   */
  const selectAll = (items) => {
    selectedItems.value = [...items];
  };

  /**
   * Handle selection change from FileListView
   * @param {Object|Array} change - Selection change object or array of items
   */
  const handleSelectionChange = (change) => {
    if (Array.isArray(change)) {
      // Direct array of items (from simple selection)
      selectedItems.value = change;
      return;
    }

    // Handle different selection actions
    if (change.action === "select") {
      if (!isSelected(change.item.id)) {
        selectedItems.value.push(change.item);
      }
    } else if (change.action === "deselect") {
      const index = selectedItems.value.findIndex(
        (i) => i.id === change.item.id,
      );
      if (index >= 0) {
        selectedItems.value.splice(index, 1);
      }
    } else if (change.action === "select-all") {
      selectedItems.value = [...change.items];
    } else if (change.action === "clear") {
      selectedItems.value = [];
    }
  };

  /**
   * Handle view mode change
   * @param {string} mode - New view mode ('grid' or 'list')
   */
  const handleViewChange = (mode) => {
    viewMode.value = mode;
    localStorage.setItem(viewModeStorageKey, mode);
  };

  /**
   * Global keydown handler for Escape key
   */
  const handleGlobalKeydown = (event) => {
    if (event.key === "Escape") {
      clearSelection();
      clipboardManager.clear();
    }
  };

  /**
   * Check encryption access and show overlay if needed
   */
  const checkEncryptionAccess = async () => {
    if (!enableEncryptionCheck) {
      return;
    }

    const userMasterKey = await getUserMasterKey();
    if (!userMasterKey) {
      // User is authenticated but master key is missing
      // This can happen after page refresh or for SSO users
      try {
        const currentUser = await authStore.fetchCurrentUser();
        if (currentUser) {
          showEncryptionOverlay.value = true;
          isMasterKeyRequired.value = true;
        }
      } catch (err) {
        // User is not authenticated - don't show overlay
        logger.warn(
          "User master key not available and user is not authenticated.",
        );
      }
    }
  };

  /**
   * Handle password submission for encryption unlock
   */
  const handlePasswordSubmit = async () => {
    if (!passwordModalPassword.value.trim()) {
      passwordModalError.value = "Password is required";
      return;
    }

    passwordModalLoading.value = true;
    passwordModalError.value = "";

    try {
      // Rate limit unlock attempts
      try {
        await authStore.encryptionUnlockAttempt();
      } catch (limitErr) {
        passwordModalError.value =
          limitErr.message || "Too many attempts. Please try again later.";
        return;
      }

      // Get master key salt from server
      const saltBase64 = await authStore.getMasterKeySalt();

      if (!saltBase64) {
        throw new Error("Master key salt not available");
      }

      // Convert base64 salt to Uint8Array
      const saltStr = atob(saltBase64);
      const salt = Uint8Array.from(saltStr, (c) => c.charCodeAt(0));

      // Derive master key from password and salt
      const masterKey = await initializeUserMasterKey(
        passwordModalPassword.value,
        salt,
      );

      if (!masterKey) {
        throw new Error("Failed to derive master key");
      }

      // Keep modal open until actual content unlock is confirmed
      // Call callback if provided to verify unlock (e.g., key decryption)
      let unlocked = true;
      if (onEncryptionUnlocked) {
        try {
          const result = await onEncryptionUnlocked();
          unlocked = result === true;
        } catch (e) {
          unlocked = false;
        }
      }
      if (unlocked) {
        showPasswordModal.value = false;
        passwordModalPassword.value = "";
        passwordModalError.value = "";
        showEncryptionOverlay.value = false;
        isMasterKeyRequired.value = false;
      } else {
        passwordModalError.value = "Invalid password";
      }
    } catch (err) {
      logger.error("Failed to initialize master key:", err);
      passwordModalError.value = "Invalid password";
    } finally {
      passwordModalLoading.value = false;
    }
  };

  /**
   * Close password modal
   */
  const closePasswordModal = () => {
    if (!passwordModalLoading.value) {
      showPasswordModal.value = false;
      passwordModalPassword.value = "";
      passwordModalError.value = "";
      // Keep overlay visible if master key is still required
      // Don't hide overlay on cancel - user needs to unlock to proceed
    }
  };

  /**
   * Open password modal
   */
  const openPasswordModal = () => {
    showPasswordModal.value = true;
  };

  /**
   * Cleanup function to remove event listeners and observers
   */
  const cleanup = () => {};

  // Cleanup on unmount
  onMounted(() => {
    window.addEventListener("keydown", handleGlobalKeydown);
  });

  onUnmounted(() => {
    window.removeEventListener("keydown", handleGlobalKeydown);
    cleanup();
  });

  return {
    // Selection state and methods
    selectedItems,
    isSelected,
    toggleSelection,
    clearSelection,
    selectAll,
    handleSelectionChange,

    // View mode state and methods
    viewMode,
    handleViewChange,

    // Encryption overlay state and methods
    showEncryptionOverlay,
    isMasterKeyRequired,
    showPasswordModal,
    passwordModalPassword,
    passwordModalError,
    passwordModalLoading,
    checkEncryptionAccess,
    handlePasswordSubmit,
    closePasswordModal,
    openPasswordModal,

    // Cleanup
    cleanup,
  };
}
