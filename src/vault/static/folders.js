/** @file folders.js - Folder explorer interface with navigation */

let currentFolderId = null; // null = root folder
let foldersList = [];
let foldersCache = {}; // Cache for decrypted folder names
let keyManager = null;

// Initialize key manager
async function initKeyManager() {
  if (window.KeyManager) {
    keyManager = new window.KeyManager();
    await keyManager.init();
  }
}

// Load folder structure
async function loadFolders(parentId = null) {
  try {
    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    // API v2 requires vaultspace_id - we'll need to get it from context
    // For legacy compatibility, try to get vaultspace_id from URL or global state
    const vaultspaceId = window.currentVaultspaceId || getVaultspaceIdFromURL();
    if (!vaultspaceId) {
      console.warn("vaultspace_id not found, folders may not load correctly");
      return [];
    }

    const params = new URLSearchParams();
    params.append("vaultspace_id", vaultspaceId);
    if (parentId) {
      params.append("parent_id", parentId);
    }

    const url = `/api/v2/files?${params.toString()}`;
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("Failed to fetch folders");

    const data = await response.json();
    // API v2 returns files array - filter for folders only
    const folders = (data.files || []).filter(
      (f) => f.mime_type === "application/x-directory" || f.is_folder === true,
    );
    return folders;
  } catch (error) {
    console.error("Error loading folders:", error);
    return [];
  }
}

// Helper function to get vaultspace_id from URL
function getVaultspaceIdFromURL() {
  const path = window.location.pathname;
  // Try to extract from URL patterns like /vaultspace/{id} or /dashboard
  const match = path.match(/\/vaultspace\/([^/]+)/);
  if (match) {
    return match[1];
  }
  // Try to get from global state or localStorage
  return localStorage.getItem("current_vaultspace_id");
}

// Get folder path from root
async function getFolderPath(folderId) {
  if (!folderId) return [];

  try {
    // Migrate to API v2 - folder path may need to be computed client-side
    // API v2 doesn't have a direct path endpoint, so we'll build it from file hierarchy
    // For now, return empty array and let the calling code handle it
    console.warn(
      "getFolderPath: API v2 doesn't have direct path endpoint, returning empty",
    );
    return [];
  } catch (error) {
    console.error("Error loading folder path:", error);
    return [];
  }
}

// Decrypt folder name
// encryptedName: encrypted folder name
// parentId: ID of the parent folder (null for root)
async function decryptFolderName(encryptedName, parentId) {
  if (!keyManager) {
    await initKeyManager();
  }

  if (!keyManager) {
    // Fallback: return placeholder if key manager not available
    return "[Encrypted Folder]";
  }

  try {
    // Get master key or generate temporary one for legacy mode
    let masterKeyData = await keyManager.getMasterKey();

    // If no master key found (legacy mode), generate a temporary one
    if (!masterKeyData) {
      // In legacy mode, use the same fixed salt and derive from the same fixed value
      // This matches the key used in createFolder for consistency
      const legacyPassword = "leyzen-legacy-default-master-key";
      const salt = new Uint8Array(32); // Zero salt for legacy (not secure but consistent)

      // Derive temporary master key
      masterKeyData = await keyManager.deriveUserMasterKey(
        legacyPassword,
        salt,
      );

      // Store it temporarily for this session
      await keyManager.storeMasterKey(
        masterKeyData.masterKey,
        masterKeyData.salt,
      );
    }

    // Get parent folder path (same logic as createFolder)
    const path = parentId ? await getFolderPath(parentId) : [];
    const folderPathIds = path.map((f) => f.folder_id);
    if (parentId) {
      folderPathIds.push(parentId);
    }

    // Derive folder key (same as createFolder)
    const folderKey = await keyManager.deriveFolderKey(
      masterKeyData.masterKey,
      folderPathIds,
    );

    // Decrypt folder name
    const encryptedData = keyManager.base64urlToArray(encryptedName);
    const decryptedName = await keyManager.decryptFolderName(
      encryptedData,
      folderKey,
    );

    return decryptedName;
  } catch (error) {
    console.error("Error decrypting folder name:", error);
    return "[Encrypted Folder]";
  }
}

// Render breadcrumbs
async function renderBreadcrumbs(folderId) {
  const breadcrumbsContainer = document.getElementById("breadcrumbs");
  if (!breadcrumbsContainer) return;

  const path = folderId ? await getFolderPath(folderId) : [];
  const breadcrumbs = [];

  // Root breadcrumb - always visible as Home button
  breadcrumbs.push(
    '<button class="breadcrumb-item breadcrumb-home" data-folder-id="" title="Go to root">🏠 Home</button>',
  );

  // Folder breadcrumbs
  for (let i = 0; i < path.length; i++) {
    const folder = path[i];
    // For breadcrumbs, use the parent of the current folder in the path
    // First folder has parentId = null (root), others have parentId = previous folder's id
    const parentId = i === 0 ? null : path[i - 1].folder_id;
    const folderName = await decryptFolderName(folder.encrypted_name, parentId);
    const escapedName = escapeHtml(folderName);
    breadcrumbs.push(
      `<span class="breadcrumb-separator">›</span><button class="breadcrumb-item" data-folder-id="${escapeHtml(
        folder.folder_id,
      )}" title="${escapedName}">${escapedName}</button>`,
    );
  }

  if (breadcrumbsContainer) {
    setInnerHTML(breadcrumbsContainer, breadcrumbs.join(""));

    // Attach click listeners
    breadcrumbsContainer
      .querySelectorAll(".breadcrumb-item")
      .forEach((item) => {
        item.addEventListener("click", async (e) => {
          const targetFolderId = e.target.getAttribute("data-folder-id");
          await navigateToFolder(targetFolderId || null);
        });
      });
  }
}

// Render folders list
async function renderFolders(folders, parentId) {
  const container = document.getElementById("folders-list");
  if (!container) return;

  if (folders.length === 0) {
    setInnerHTML(container, "");
    return;
  }

  // Check current view mode from files.js
  const currentView = window.currentView || "grid";

  if (currentView === "list") {
    await renderFoldersListView(folders, parentId);
  } else {
    await renderFoldersGridView(folders, parentId);
  }
}

// Render folders in grid view
async function renderFoldersGridView(folders, parentId) {
  const container = document.getElementById("folders-list");
  if (!container) return;

  container.className = "folders-grid";

  const foldersHTML = await Promise.all(
    folders.map(async (folder) => {
      // Use parent_id from folder object (passed from API)
      // parentId parameter is the current folder we're viewing, which is the parent of these folders
      const folderName = await decryptFolderName(
        folder.encrypted_name,
        folder.parent_id || parentId,
      );
      const escapedName = escapeHtml(folderName);
      const escapedFolderId = escapeHtml(folder.folder_id);

      const folderIcon = window.Icons?.folder
        ? window.Icons.folder(48, "currentColor")
        : "📁";
      const moreIcon = window.Icons?.moreVertical
        ? window.Icons.moreVertical(20, "currentColor")
        : "⋮";

      return `
                <div class="folder-card" data-folder-id="${escapedFolderId}">
                    <div class="folder-icon">${folderIcon}</div>
                    <div class="folder-name" title="${escapedName}">${escapedName}</div>
                    <div class="folder-card-actions">
                        <button class="file-menu-btn" data-folder-id="${escapedFolderId}" title="More options" aria-label="More options">
                            ${moreIcon}
                        </button>
                    </div>
                </div>
            `;
    }),
  );

  setInnerHTML(container, foldersHTML.join(""));

  // Attach event listeners for folder menu buttons
  container
    .querySelectorAll(".file-menu-btn[data-folder-id]")
    .forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const folderId = btn.getAttribute("data-folder-id");
        if (folderId && window.fileMenuManager) {
          window.fileMenuManager.show(folderId, "folder", e);
        }
      });
    });
}

// Render folders in list view
async function renderFoldersListView(folders, parentId) {
  const container = document.getElementById("folders-list");
  if (!container) return;

  container.className = "folders-list-view";

  const foldersHTML = await Promise.all(
    folders.map(async (folder) => {
      const folderName = await decryptFolderName(
        folder.encrypted_name,
        folder.parent_id || parentId,
      );
      const escapedName = escapeHtml(folderName);
      const escapedFolderId = escapeHtml(folder.folder_id);
      const moreIcon = window.Icons?.moreVertical
        ? window.Icons.moreVertical(20, "currentColor")
        : "⋮";

      return `
                <div class="folder-row" data-folder-id="${escapedFolderId}">
                    <div class="folder-row-icon">${window.Icons?.folder ? window.Icons.folder(24, "currentColor") : "📁"}</div>
                    <div class="folder-row-name" title="${escapedName}">${escapedName}</div>
                    <div class="folder-row-actions">
                        <button class="file-menu-btn" data-folder-id="${escapedFolderId}" title="More options" aria-label="More options">
                            ${moreIcon}
                        </button>
                    </div>
                </div>
            `;
    }),
  );

  setInnerHTML(container, foldersHTML.join(""));

  // Attach event listeners for folder menu buttons
  container
    .querySelectorAll(".file-menu-btn[data-folder-id]")
    .forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const folderId = btn.getAttribute("data-folder-id");
        if (folderId && window.fileMenuManager) {
          window.fileMenuManager.show(folderId, "folder", e);
        }
      });
    });
}

// Navigate to folder
async function navigateToFolder(folderId) {
  // Deselect all items when changing folder
  if (window.selectionManager) {
    window.selectionManager.deselectAll();
  }

  currentFolderId = folderId;
  await renderBreadcrumbs(folderId);
  await loadFolderContents(folderId);
}

// Load folder contents (files and subfolders)
async function loadFolderContents(folderId) {
  try {
    // Load folders
    const folders = await loadFolders(folderId);
    await renderFolders(folders, folderId);

    // Load files
    const url = folderId ? `/api/files?folder_id=${folderId}` : `/api/files`;
    const response = await fetch(url);
    if (!response.ok) throw new Error("Failed to fetch files");

    const data = await response.json();
    if (window.renderFiles) {
      window.renderFiles(data.files || []);
    }
  } catch (error) {
    console.error("Error loading folder contents:", error);
    if (window.Notifications) {
      window.Notifications.error("Failed to load folder contents");
    }
  }
}

// Generate unique folder name
async function generateUniqueFolderName(
  baseName = "New Folder",
  parentId = null,
) {
  try {
    // Load existing folders in the parent directory
    const folders = await loadFolders(parentId);

    // Decrypt all folder names
    const existingNames = await Promise.all(
      folders.map(async (folder) => {
        try {
          return await decryptFolderName(
            folder.encrypted_name,
            folder.parent_id || parentId,
          );
        } catch (e) {
          console.warn("Failed to decrypt folder name:", e);
          return null;
        }
      }),
    );

    // Filter out null values (decryption failures)
    const validNames = existingNames.filter((name) => name !== null);

    // Check if base name is available
    if (!validNames.includes(baseName)) {
      return baseName;
    }

    // Find the next available number
    let counter = 1;
    let newName = `${baseName}(${counter})`;

    while (validNames.includes(newName)) {
      counter++;
      newName = `${baseName}(${counter})`;
    }

    return newName;
  } catch (error) {
    console.error("Error generating unique folder name:", error);
    // Fallback to base name if there's an error
    return baseName;
  }
}

// Create new folder
async function createFolder(name, parentId = null) {
  if (!keyManager) {
    await initKeyManager();
  }

  if (!keyManager) {
    if (window.Notifications) {
      window.Notifications.error("Key manager not available");
    }
    return;
  }

  try {
    // If name is not provided or is the default, generate a unique name
    if (!name || name.trim() === "") {
      name = await generateUniqueFolderName("New Folder", parentId);
    } else {
      // Check if the provided name is already taken and generate unique if needed
      const uniqueName = await generateUniqueFolderName(name, parentId);
      if (uniqueName !== name) {
        // Name conflict detected, use the unique name
        name = uniqueName;
      }
    }
    // Get master key or generate temporary one for legacy mode
    let masterKeyData = await keyManager.getMasterKey();

    // If no master key found (legacy mode), generate a temporary one
    if (!masterKeyData) {
      // In legacy mode, use a fixed salt and derive from a fixed value
      // This allows folder creation in legacy mode with consistent encryption
      // Note: This is less secure than user-specific keys but necessary for legacy compatibility
      const legacyPassword = "leyzen-legacy-default-master-key";
      const salt = new Uint8Array(32); // Zero salt for legacy (not secure but consistent)

      // Derive temporary master key
      masterKeyData = await keyManager.deriveUserMasterKey(
        legacyPassword,
        salt,
      );

      // Store it temporarily for this session
      await keyManager.storeMasterKey(
        masterKeyData.masterKey,
        masterKeyData.salt,
      );
    }

    // Get folder path
    const path = parentId ? await getFolderPath(parentId) : [];
    const folderPathIds = path.map((f) => f.folder_id);
    if (parentId) {
      folderPathIds.push(parentId);
    }

    // Derive folder key
    const folderKey = await keyManager.deriveFolderKey(
      masterKeyData.masterKey,
      folderPathIds,
    );

    // Encrypt folder name
    const { encrypted, nameHash } = await keyManager.encryptFolderName(
      name,
      folderKey,
    );

    const encryptedBase64 = keyManager.arrayToBase64url(encrypted);

    // Migrate to API v2 - requires JWT authentication and vaultspace_id
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    // API v2 requires vaultspace_id - get it from context
    const vaultspaceId = window.currentVaultspaceId || getVaultspaceIdFromURL();
    if (!vaultspaceId) {
      throw new Error("vaultspace_id is required to create folder");
    }

    // API v2 uses plain name, not encrypted_name - encryption is handled by the service
    // However, for legacy compatibility, we may need to send the name as-is
    // Check API v2 documentation for the expected format
    const response = await fetch("/api/v2/files/folders", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        vaultspace_id: vaultspaceId,
        name: name, // API v2 expects plain name
        parent_id: parentId,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      const errorMessage = error.error || "Failed to create folder";
      // Handle duplicate name error specifically
      if (response.status === 409) {
        if (window.Notifications) {
          window.Notifications.error(errorMessage);
        }
      }
      throw new Error(errorMessage);
    }

    if (window.Notifications) {
      window.Notifications.success(`Folder "${name}" created successfully`);
    }

    // Reload current folder
    await loadFolderContents(currentFolderId);
  } catch (error) {
    console.error("Error creating folder:", error);
    if (window.Notifications) {
      window.Notifications.error(`Failed to create folder: ${error.message}`);
    }
  }
}

// Delete folder
async function deleteFolder(folderId) {
  if (typeof window.showConfirmationModal === "function") {
    window.showConfirmationModal({
      icon: window.Icons?.warning
        ? window.Icons.warning(20, "currentColor")
        : "⚠️",
      title: "Delete Folder",
      message:
        "Are you sure you want to delete this folder? Files inside will be moved to the parent folder.",
      confirmText: "Delete",
      dangerous: true,
      onConfirm: async () => {
        await performDeleteFolder(folderId);
      },
    });
  }
}

async function performDeleteFolder(folderId) {
  try {
    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    const response = await fetch(`/api/v2/files/${folderId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
    });

    if (!response.ok) throw new Error("Delete failed");

    if (window.Notifications) {
      window.Notifications.success("Folder deleted successfully");
    }

    // Reload current folder
    await loadFolderContents(currentFolderId);
  } catch (error) {
    console.error("Delete error:", error);
    if (window.Notifications) {
      window.Notifications.error(`Delete failed: ${error.message}`);
    }
  }
}

// Helper function to safely set innerHTML
function setInnerHTML(element, html) {
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {
      console.warn("Failed to use vaultHTMLPolicy:", e);
    }
  }

  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {
      console.warn("Failed to use defaultPolicy:", e);
    }
  }

  try {
    element.innerHTML = html;
  } catch (e) {
    console.error("Failed to set innerHTML:", e);
    throw e;
  }
}

// Escape HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Initialize
document.addEventListener("DOMContentLoaded", async () => {
  await initKeyManager();
  await navigateToFolder(null); // Start at root

  // New folder button
  const newFolderBtn = document.getElementById("new-folder-btn");
  if (newFolderBtn) {
    newFolderBtn.addEventListener("click", async () => {
      // Generate unique name automatically
      const uniqueName = await generateUniqueFolderName(
        "New Folder",
        currentFolderId,
      );
      await createFolder(uniqueName, currentFolderId);
    });
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.Folders = {
    navigateToFolder,
    createFolder,
    deleteFolder,
    loadFolderContents,
    getCurrentFolderId: () => currentFolderId,
  };
}
