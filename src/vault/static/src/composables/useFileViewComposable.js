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
import { auth } from "../services/api";
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
  const overlayStyle = ref({});

  // Resize observers and intervals for cleanup
  const _overlayResizeHandler = ref(null);
  const _mobileModeChangeHandler = ref(null);
  const _sidebarResizeObserver = ref(null);
  const _mainContentResizeObserver = ref(null);
  const _pageContentResizeObserver = ref(null);
  const _bottomBarResizeObserver = ref(null);
  const _overlayProtectionInterval = ref(null);
  const _overlayMutationObserver = ref(null);

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
   * Check encryption access and show overlay if needed
   */
  const checkEncryptionAccess = async () => {
    if (!enableEncryptionCheck) {
      return;
    }

    // Check if user master key is available
    const userMasterKey = await getUserMasterKey();
    if (!userMasterKey) {
      // Check if salt exists - this means master key was lost
      const storedSalt = getStoredSalt();
      if (storedSalt) {
        // User is authenticated but master key is lost (likely after page refresh)
        // This is normal - user needs to re-enter password to access encrypted content
        logger.warn(
          "Master key lost from memory but salt exists. This is normal after page refresh.",
        );
        logger.warn(
          "User needs to re-enter password to access encrypted content.",
        );
        // Don't show overlay for lost session - let component handle it
        return;
      } else {
        // No salt and no master key
        // Check if user is still authenticated (could be SSO user without password)
        try {
          const currentUser = await auth.getCurrentUser();
          if (currentUser) {
            // User is authenticated but has no master key or salt
            // This is normal for SSO users - show encryption overlay
            showEncryptionOverlay.value = true;
            isMasterKeyRequired.value = true;

            // Calculate overlay position after DOM is ready
            await nextTick();
            calculateOverlayPosition();

            // Recalculate on window resize
            const resizeHandler = () => calculateOverlayPosition();
            window.addEventListener("resize", resizeHandler);
            _overlayResizeHandler.value = resizeHandler;

            // Recalculate when mobile mode changes
            const mobileModeChangeHandler = () => {
              // Wait a bit for DOM to update after mode change
              setTimeout(() => {
                calculateOverlayPosition();
                // Re-observe elements as they may have changed
                observeSidebarChanges();
              }, 100);
            };
            window.addEventListener(
              "mobile-mode-changed",
              mobileModeChangeHandler,
            );
            _mobileModeChangeHandler.value = mobileModeChangeHandler;

            // Recalculate when sidebar toggles (observe sidebar width changes)
            observeSidebarChanges();

            // Protect overlay from being removed via DevTools
            protectOverlay();
          }
        } catch (err) {
          // User is not authenticated - don't show overlay
          logger.warn(
            "User master key not available and user is not authenticated.",
          );
        }
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
      // Get master key salt from server
      const response = await fetch("/api/auth/account/master-key-salt", {
        method: "GET",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("jwt_token")}`,
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
        passwordModalPassword.value,
        salt,
      );

      if (!masterKey) {
        throw new Error("Failed to derive master key");
      }

      // Close modal and clear password
      showPasswordModal.value = false;
      passwordModalPassword.value = "";
      passwordModalError.value = "";

      // Hide overlay and mark master key as no longer required
      showEncryptionOverlay.value = false;
      isMasterKeyRequired.value = false;

      // Call callback if provided
      if (onEncryptionUnlocked) {
        await onEncryptionUnlocked();
      }
    } catch (err) {
      logger.error("Failed to initialize master key:", err);
      passwordModalError.value =
        err.message || "Failed to initialize encryption. Please try again.";
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
   * Calculate overlay position to cover main-content
   * The overlay should cover the entire main-content area with the same border-radius
   * In mobile mode, exclude header and bottom bar to keep them accessible
   */
  const calculateOverlayPosition = () => {
    nextTick(() => {
      const mainContent = document.querySelector(".main-content");
      const isMobileMode = document.body.classList.contains("mobile-mode");
      if (mainContent) {
        const mainContentRect = mainContent.getBoundingClientRect();

        let overlayTop = mainContentRect.top;
        let overlayLeft = mainContentRect.left;
        let overlayWidth = mainContentRect.width;
        let overlayHeight = mainContentRect.height;

        // In mobile mode, adjust overlay to exclude header and bottom bar
        if (isMobileMode) {
          // Get header height
          const header = document.querySelector(".app-header");
          const headerHeight = header ? header.offsetHeight : 0;

          // Get bottom bar position and dimensions
          const bottomBar = document.querySelector(".bottom-navigation");
          let bottomBorderRadius = "0";
          if (bottomBar) {
            const bottomBarRect = bottomBar.getBoundingClientRect();
            const bottomBarTop = bottomBarRect.top;
            const bottomBarWidth = bottomBarRect.width;
            const isExpanded = bottomBar.classList.contains("expanded");

            // Add a gap between overlay and bottom bar for visual separation
            // This creates the effect of the overlay "curving around" the bottom bar
            const gap = 16;
            const availableHeight = bottomBarTop - headerHeight - gap;

            overlayTop = headerHeight;
            overlayHeight = Math.max(0, availableHeight);

            // Create rounded bottom corners that complement the circular bottom bar
            // The bottom bar has border-radius: 1.5rem (24px)
            // Use a larger border-radius on the bottom of the overlay to create
            // a smooth curve that visually flows around the bottom bar
            if (isExpanded) {
              // When expanded, bottom bar is wider (95% width), use matching border-radius
              bottomBorderRadius = "0 0 1.5rem 1.5rem";
            } else {
              // When collapsed, bottom bar is circular (80px wide, 40px high)
              // Use a larger radius to create a smooth transition that curves around it
              // The radius should be slightly larger than the bottom bar's radius
              bottomBorderRadius = "0 0 2.5rem 2.5rem";
            }
          } else {
            // No bottom bar, just exclude header
            overlayTop = headerHeight;
            overlayHeight = window.innerHeight - headerHeight;
          }

          // Full width in mobile
          overlayLeft = 0;
          overlayWidth = window.innerWidth;

          overlayStyle.value = {
            position: "fixed",
            top: `${overlayTop}px`,
            left: `${overlayLeft}px`,
            width: `${overlayWidth}px`,
            height: `${overlayHeight}px`,
            borderRadius: isMobileMode ? bottomBorderRadius : "1rem", // Match main-content border-radius in desktop mode
            zIndex: 50, // Above content but below header (100), dropdown (1000), and bottom bar (99999)
            pointerEvents: "auto", // Ensure overlay is interactive
          };
        } else {
          // Desktop mode - use original logic
          overlayStyle.value = {
            position: "fixed",
            top: `${overlayTop}px`,
            left: `${overlayLeft}px`,
            width: `${overlayWidth}px`,
            height: `${overlayHeight}px`,
            borderRadius: isMobileMode ? "0" : "1rem",
            zIndex: 50,
            pointerEvents: "auto",
          };
        }
      }
    });
  };

  /**
   * Observe sidebar changes to recalculate overlay position
   */
  const observeSidebarChanges = () => {
    // Clean up existing observers first
    if (_sidebarResizeObserver.value) {
      _sidebarResizeObserver.value.disconnect();
      _sidebarResizeObserver.value = null;
    }
    if (_mainContentResizeObserver.value) {
      _mainContentResizeObserver.value.disconnect();
      _mainContentResizeObserver.value = null;
    }
    if (_pageContentResizeObserver.value) {
      _pageContentResizeObserver.value.disconnect();
      _pageContentResizeObserver.value = null;
    }
    if (_bottomBarResizeObserver.value) {
      _bottomBarResizeObserver.value.disconnect();
      _bottomBarResizeObserver.value = null;
    }

    // Observe sidebar width changes
    const sidebar = document.querySelector(".sidebar");
    if (sidebar && window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          calculateOverlayPosition();
        });
      });
      observer.observe(sidebar);
      _sidebarResizeObserver.value = observer;
    }

    // Observe header changes (height might change)
    const header = document.querySelector(".app-header");
    if (header && window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          calculateOverlayPosition();
        });
      });
      observer.observe(header);
    }

    // Observe main-content changes (which moves when sidebar toggles)
    const mainContent = document.querySelector(".main-content");
    if (mainContent && window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          calculateOverlayPosition();
        });
      });
      observer.observe(mainContent);
      _mainContentResizeObserver.value = observer;
    }

    // Observe page-content directly
    const pageContent = document.querySelector(".page-content");
    if (pageContent && window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          calculateOverlayPosition();
        });
      });
      observer.observe(pageContent);
      _pageContentResizeObserver.value = observer;
    }

    // Observe bottom bar changes (height changes when collapsed/expanded)
    const bottomBar = document.querySelector(".bottom-navigation");
    if (bottomBar && window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        requestAnimationFrame(() => {
          calculateOverlayPosition();
        });
      });
      observer.observe(bottomBar);
      _bottomBarResizeObserver.value = observer;
    }
  };

  /**
   * Protect overlay from being removed via DevTools
   */
  const protectOverlay = () => {
    // Check periodically if overlay still exists and recreate if needed
    if (_overlayProtectionInterval.value) {
      clearInterval(_overlayProtectionInterval.value);
    }

    _overlayProtectionInterval.value = setInterval(() => {
      if (showEncryptionOverlay.value && isMasterKeyRequired.value) {
        const overlay = document.querySelector(
          '[data-encryption-overlay="true"]',
        );
        if (!overlay) {
          // Overlay was removed, force re-render
          // Note: This requires access to component instance, so we'll handle it in the component
          calculateOverlayPosition();
        }
      }
    }, 500);

    // Also use MutationObserver to detect removal
    const observer = new MutationObserver(() => {
      if (showEncryptionOverlay.value && isMasterKeyRequired.value) {
        const overlay = document.querySelector(
          '[data-encryption-overlay="true"]',
        );
        if (!overlay) {
          // Overlay was removed, force re-render
          calculateOverlayPosition();
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    _overlayMutationObserver.value = observer;
  };

  /**
   * Cleanup function to remove event listeners and observers
   */
  const cleanup = () => {
    // Remove resize handler
    if (_overlayResizeHandler.value) {
      window.removeEventListener("resize", _overlayResizeHandler.value);
      _overlayResizeHandler.value = null;
    }

    // Remove mobile mode change handler
    if (_mobileModeChangeHandler.value) {
      window.removeEventListener(
        "mobile-mode-changed",
        _mobileModeChangeHandler.value,
      );
      _mobileModeChangeHandler.value = null;
    }

    // Disconnect resize observers
    if (_sidebarResizeObserver.value) {
      _sidebarResizeObserver.value.disconnect();
      _sidebarResizeObserver.value = null;
    }

    if (_mainContentResizeObserver.value) {
      _mainContentResizeObserver.value.disconnect();
      _mainContentResizeObserver.value = null;
    }

    if (_pageContentResizeObserver.value) {
      _pageContentResizeObserver.value.disconnect();
      _pageContentResizeObserver.value = null;
    }

    if (_bottomBarResizeObserver.value) {
      _bottomBarResizeObserver.value.disconnect();
      _bottomBarResizeObserver.value = null;
    }

    // Clear protection interval
    if (_overlayProtectionInterval.value) {
      clearInterval(_overlayProtectionInterval.value);
      _overlayProtectionInterval.value = null;
    }

    // Disconnect mutation observer
    if (_overlayMutationObserver.value) {
      _overlayMutationObserver.value.disconnect();
      _overlayMutationObserver.value = null;
    }
  };

  // Cleanup on unmount
  onUnmounted(() => {
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
    overlayStyle,
    checkEncryptionAccess,
    handlePasswordSubmit,
    closePasswordModal,
    openPasswordModal,
    calculateOverlayPosition,

    // Cleanup
    cleanup,
  };
}
