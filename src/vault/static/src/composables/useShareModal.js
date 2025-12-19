/**
 * Composable for managing the share modal
 * Handles file key retrieval and modal state management
 */

import { ref, createApp } from "vue";
import ShareModal from "../components/ShareModal.vue";
import { files } from "../services/api";

let fileKeyStorage = null;

// Lazy load fileKeyStorage
const getFileKeyStorage = async () => {
  if (fileKeyStorage) {
    return fileKeyStorage;
  }

  try {
    const module = await import("../services/fileKeyStorage.js");
    fileKeyStorage = module;
    return module;
  } catch (e) {
    try {
      const module = await import("/static/src/services/fileKeyStorage.js");
      fileKeyStorage = module;
      return module;
    } catch (e2) {
      return null;
    }
  }
};

/**
 * Get file key from various sources
 * @param {string} fileId - File ID
 * @param {string|null} vaultspaceId - VaultSpace ID
 * @param {CryptoKey|null} vaultspaceKey - VaultSpace key
 * @returns {Promise<Uint8Array|null>} File key
 */
const getFileKey = async (
  fileId,
  vaultspaceId = null,
  vaultspaceKey = null,
) => {
  let fileKey = null;

  // First: Try to get key from IndexedDB via fileKeyStorage
  const currentFileKeyStorage = await getFileKeyStorage();
  if (currentFileKeyStorage) {
    try {
      const keyStr = await currentFileKeyStorage.getFileKey(fileId);
      if (keyStr) {
        if (window.VaultCrypto && window.VaultCrypto.base64urlToArray) {
          fileKey = window.VaultCrypto.base64urlToArray(keyStr);
        } else {
          // Fallback: decode base64url manually
          try {
            const binaryString = atob(
              keyStr.replace(/-/g, "+").replace(/_/g, "/"),
            );
            fileKey = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              fileKey[i] = binaryString.charCodeAt(i);
            }
          } catch (e) {
            fileKey = null;
          }
        }
      }
    } catch (e) {
      fileKey = null;
    }
  }

  // Second: Fallback to localStorage
  if (!fileKey) {
    try {
      const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
      const keyStr = keys[fileId];
      if (keyStr) {
        if (window.VaultCrypto && window.VaultCrypto.base64urlToArray) {
          fileKey = window.VaultCrypto.base64urlToArray(keyStr);
          // Store in IndexedDB for future use
          if (currentFileKeyStorage) {
            try {
              await currentFileKeyStorage.storeFileKey(fileId, keyStr);
            } catch (e) {}
          }
        } else {
          // Fallback: decode base64url manually
          try {
            const binaryString = atob(
              keyStr.replace(/-/g, "+").replace(/_/g, "/"),
            );
            fileKey = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              fileKey[i] = binaryString.charCodeAt(i);
            }
            // Store in IndexedDB for future use
            if (currentFileKeyStorage) {
              try {
                await currentFileKeyStorage.storeFileKey(fileId, keyStr);
              } catch (e) {}
            }
          } catch (e) {
            fileKey = null;
          }
        }
      }
    } catch (e) {
      fileKey = null;
    }
  }

  // Third: Try to get from global function
  if (!fileKey) {
    if (typeof getFileKey === "function") {
      fileKey = getFileKey(fileId);
    } else if (window.getFileKey) {
      fileKey = window.getFileKey(fileId);
    }
  }

  // Fourth: If still not found and we have vaultspaceId and vaultspaceKey, try API
  if (
    !fileKey &&
    vaultspaceId &&
    vaultspaceKey &&
    vaultspaceKey instanceof CryptoKey
  ) {
    try {
      const jwtToken = localStorage.getItem("jwt_token");
      if (!jwtToken) {
        return null;
      }

      const fileData = await files.getFile(fileId, vaultspaceId);
      if (fileData && fileData.file_key && fileData.file_key.encrypted_key) {
        try {
          let decryptFileKeyFunc = window.decryptFileKey;
          if (!decryptFileKeyFunc) {
            try {
              const encryptionModule =
                await import("../services/encryption.js");
              decryptFileKeyFunc = encryptionModule.decryptFileKey;
            } catch (e) {
              // Fallback failed
            }
          }

          if (decryptFileKeyFunc) {
            const decryptedKey = await decryptFileKeyFunc(
              vaultspaceKey,
              fileData.file_key.encrypted_key,
              true, // extractable: true
            );
            // Convert CryptoKey to Uint8Array
            const keyArrayBuffer = await crypto.subtle.exportKey(
              "raw",
              decryptedKey,
            );
            fileKey = new Uint8Array(keyArrayBuffer);

            // Store in IndexedDB and localStorage
            try {
              let keyBase64 = null;
              if (window.VaultCrypto && window.VaultCrypto.arrayToBase64url) {
                keyBase64 = window.VaultCrypto.arrayToBase64url(fileKey);
              } else {
                keyBase64 = btoa(String.fromCharCode.apply(null, fileKey));
              }

              if (currentFileKeyStorage && keyBase64) {
                try {
                  await currentFileKeyStorage.storeFileKey(fileId, keyBase64);
                } catch (e) {}
              }

              try {
                const keys = JSON.parse(
                  localStorage.getItem("vault_keys") || "{}",
                );
                keys[fileId] = keyBase64;
                localStorage.setItem("vault_keys", JSON.stringify(keys));
              } catch (e) {}
            } catch (e) {
              // Ignore storage errors
            }
          }
        } catch (e) {
          // Decryption failed
        }
      }
    } catch (e) {
      // API call failed
    }
  }

  return fileKey;
};

/**
 * Show share modal
 * @param {string} fileId - File ID
 * @param {string} fileType - File type (default: "file")
 * @param {string|null} vaultspaceId - VaultSpace ID
 * @param {CryptoKey|null} vaultspaceKey - VaultSpace key
 */
export const showShareModal = async (
  fileId,
  fileType = "file",
  vaultspaceId = null,
  vaultspaceKey = null,
) => {
  if (!fileId) {
    if (window.Notifications) {
      window.Notifications.error("File ID is required");
    }
    return;
  }

  // Get file key
  let fileKey = null;
  try {
    fileKey = await getFileKey(fileId, vaultspaceId, vaultspaceKey);
  } catch (error) {
    if (window.Notifications) {
      window.Notifications.warning(
        "Decryption key not found. You may need to decrypt this file first to share it.",
      );
    }
  }

  try {
    // Remove existing modal if any
    const existingContainer = document.getElementById("share-modal-container");
    if (existingContainer) {
      existingContainer.remove();
    }

    // Create modal container
    const modalContainer = document.createElement("div");
    modalContainer.id = "share-modal-container";
    document.body.appendChild(modalContainer);

    // Create Vue app instance for the modal
    const show = ref(true);

    const closeModal = () => {
      show.value = false;
      setTimeout(() => {
        if (modalContainer && modalContainer.parentNode) {
          app.unmount();
          modalContainer.remove();
        }
      }, 300);
    };

    // Create Vue app
    const app = createApp(ShareModal, {
      show: show.value,
      fileId,
      fileType,
      fileKey,
      "onUpdate:show": (value) => {
        show.value = value;
        if (!value) {
          closeModal();
        }
      },
      onClose: closeModal,
    });

    app.mount(modalContainer);
  } catch (error) {
    // Only show error if modal rendering actually failed
    console.error("Failed to render share modal:", error);
    if (window.Notifications) {
      window.Notifications.error(
        "Failed to open share dialog. Please refresh the page.",
      );
    }
    // Don't throw error - let the modal try to open anyway
    // The error might be non-critical
  }
};

// Export for use in Vue components
export function useShareModal() {
  return {
    showShareModal,
  };
}

// Also expose globally for backward compatibility
if (typeof window !== "undefined") {
  window.showShareModalAdvanced = showShareModal;
  window.showShareModal = showShareModal;

  // Create a mock sharingManager object for backward compatibility
  window.sharingManager = {
    showShareModal: showShareModal,
  };
}
