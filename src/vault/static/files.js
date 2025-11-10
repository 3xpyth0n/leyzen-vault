/** @file files.js - File explorer interface with E2EE */

let filesList = [];
let currentShareFileId = null;
let currentShareKey = null;
let currentView = "list"; // "grid" or "list"

// Export currentView for use in folders.js
if (typeof window !== "undefined") {
  window.currentView = currentView;
  Object.defineProperty(window, "currentView", {
    get: () => currentView,
    set: (value) => {
      currentView = value;
      // Re-render when view changes
      if (filesList.length > 0) {
        renderFilteredFiles();
      }
    },
  });
}

// Helper function to safely set innerHTML with Trusted Types
// Uses policies created in base.html before CSP enforcement
function setInnerHTML(element, html) {
  // Use the global policy created in base.html if available
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {
      // Fallback if policy fails
      console.warn("Failed to use vaultHTMLPolicy:", e);
    }
  }

  // Fallback: if Trusted Types is required but policy doesn't exist, this will fail
  // This should not happen if base.html script executed correctly
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {
      console.warn("Failed to use defaultPolicy:", e);
    }
  }

  // Last resort fallback - this will fail if CSP requires Trusted Types
  // but it's better than crashing silently
  try {
    element.innerHTML = html;
  } catch (e) {
    console.error("Failed to set innerHTML:", e);
    throw e;
  }
}

// Format file size
function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
}

// Format date
function formatDate(dateString) {
  const date = new Date(dateString);
  // Use browser's locale but ensure proper timezone handling
  // The date should already be timezone-aware from the backend
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone, // Use browser's timezone
  }).format(date);
}

// Escape HTML to prevent XSS attacks
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Get file icon based on extension
function getFileIcon(fileName) {
  const ext = fileName.split(".").pop()?.toLowerCase() || "";
  // Use SVG icons from Icons system
  if (window.Icons && window.Icons.file) {
    return window.Icons.file(24, "currentColor");
  }
  // Fallback to text if icons not available
  return "📄";
}

// Helper function to create file card element for virtual list
function createFileCardElement(file, index) {
  const escapedFileName = escapeHtml(file.original_name);
  const escapedFileId = escapeHtml(file.file_id);
  const hasActiveShare = file.has_active_share === true;
  const shareIcon = window.Icons?.link
    ? window.Icons.link(14, "currentColor")
    : "🔗";
  const shareIndicator = hasActiveShare
    ? `<span class="share-badge" title="This file has an active share link">${shareIcon} Shared</span>`
    : "";
  const lockIcon = window.Icons?.lock
    ? window.Icons.lock(14, "currentColor")
    : "🔒";
  const moreIcon = window.Icons?.moreVertical
    ? window.Icons.moreVertical(20, "currentColor")
    : "⋮";

  const card = document.createElement("div");
  card.className = "file-card";
  card.dataset.fileId = escapedFileId;

  const cardHTML = `
    <div class="file-icon">${getFileIcon(file.original_name)}</div>
    <div class="file-name" title="${escapedFileName}">${escapedFileName}</div>
    <div class="file-meta">
      ${formatFileSize(file.size)} • ${formatDate(file.created_at)}
    </div>
    <div class="file-badge">
      <span class="e2ee-badge">${lockIcon} E2EE</span>
      ${shareIndicator}
    </div>
    <div class="file-card-actions">
      <button class="file-menu-btn" data-file-id="${escapedFileId}" title="More options" aria-label="More options">
        ${moreIcon}
      </button>
    </div>
  `;

  // Set innerHTML using TrustedHTML if available
  if (window.vaultHTMLPolicy) {
    try {
      card.innerHTML = window.vaultHTMLPolicy.createHTML(cardHTML);
    } catch (e) {
      card.innerHTML = cardHTML;
    }
  } else {
    card.innerHTML = cardHTML;
  }

  return card;
}

// Attach event listeners for file menu buttons
function attachFileMenuListeners(container) {
  container.addEventListener("click", (e) => {
    const button = e.target.closest(".file-menu-btn");
    if (!button) return;

    const fileId = button.getAttribute("data-file-id");
    if (!fileId) return;

    e.stopPropagation();
    if (window.fileMenuManager) {
      window.fileMenuManager.show(fileId, "file", e);
    }
  });
}

// Modify attachFileActionListeners to handle menu buttons instead
// Keep the old listeners for backward compatibility but attach menu listeners
function attachFileActionListeners(container) {
  // Attach menu listeners
  attachFileMenuListeners(container);

  // Keep old action listeners for backward compatibility (if old buttons exist)
  container.addEventListener("click", (e) => {
    const button = e.target.closest(".file-action-btn");
    if (!button) return;

    const action = button.getAttribute("data-action");
    const fileId = button.getAttribute("data-file-id");

    if (!action || !fileId) return;

    switch (action) {
      case "preview":
        e.preventDefault();
        const file = filesList.find((f) => f.file_id === fileId);
        if (file && window.showFilePreview) {
          window.showFilePreview(fileId, file.original_name, file.mime_type);
        }
        break;
      case "download":
        e.preventDefault();
        downloadFile(fileId);
        break;
      case "share":
        e.preventDefault();
        // Use advanced sharing modal if available
        if (window.sharingManager && window.sharingManager.showShareModal) {
          window.sharingManager.showShareModal(fileId);
        } else if (window.shareFile) {
          // Fallback to old share method
          shareFile(fileId);
        }
        break;
      case "delete":
        e.preventDefault();
        deleteFile(fileId);
        break;
    }
  });
}

// Render files list
function renderFiles(files) {
  const container = document.getElementById("files-list");
  if (!container) return;

  if (files.length === 0) {
    const emptyMsg = '<div class="files-loading">No files uploaded</div>';
    if (container) setInnerHTML(container, emptyMsg);
    return;
  }

  if (currentView === "list") {
    renderFilesListView(files);
  } else {
    renderFilesGridView(files);
  }
}

// Render files in grid view
function renderFilesGridView(files) {
  const container = document.getElementById("files-list");
  if (!container) return;

  container.className = "files-grid";

  const filesHTML = files
    .map((file) => {
      // Escape user data to prevent XSS attacks
      const escapedFileName = escapeHtml(file.original_name);
      const escapedFileId = escapeHtml(file.file_id);
      const hasActiveShare = file.has_active_share === true;
      const shareIcon = window.Icons?.link
        ? window.Icons.link(14, "currentColor")
        : "🔗";
      const shareIndicator = hasActiveShare
        ? `<span class="share-badge" title="This file has an active share link">${shareIcon} Shared</span>`
        : "";
      const lockIcon = window.Icons?.lock
        ? window.Icons.lock(14, "currentColor")
        : "🔒";
      const moreIcon = window.Icons?.moreVertical
        ? window.Icons.moreVertical(20, "currentColor")
        : "⋮";
      return `
            <div class="file-card" data-file-id="${escapedFileId}">
                <div class="file-icon">${getFileIcon(file.original_name)}</div>
                <div class="file-name" title="${escapedFileName}">${escapedFileName}</div>
                <div class="file-meta">
                    ${formatFileSize(file.size)} • ${formatDate(file.created_at)}
                </div>
                <div class="file-badge">
                    <span class="e2ee-badge">${lockIcon} E2EE</span>
                    ${shareIndicator}
                </div>
                <div class="file-card-actions">
                    <button class="file-menu-btn" data-file-id="${escapedFileId}" title="More options" aria-label="More options">
                        ${moreIcon}
                    </button>
                </div>
            </div>
        `;
    })
    .join("");

  if (container) setInnerHTML(container, filesHTML);
}

// Render files in list view
function renderFilesListView(files) {
  const container = document.getElementById("files-list");
  if (!container) return;

  container.className = "files-list-view";

  // Use virtual scrolling for large lists (50+ items)
  if (files.length > 50 && window.virtualListManager) {
    const virtualList =
      window.virtualListManager.getList("files-list") ||
      window.virtualListManager.createList("files-list", {
        viewMode: "list",
        itemHeight: 60,
      });

    if (virtualList) {
      virtualList.setViewMode("list");
      virtualList.setItemRenderer((item, index) => {
        return createFileRowElement(item, index);
      });
      virtualList.setItems(files);
      return;
    }
  }

  // Fallback to regular rendering for small lists
  const filesHTML = files
    .map((file) => {
      const escapedFileName = escapeHtml(file.original_name);
      const escapedFileId = escapeHtml(file.file_id);
      const hasActiveShare = file.has_active_share === true;
      const shareIcon = window.Icons?.link
        ? window.Icons.link(14, "currentColor")
        : "🔗";
      const shareIndicator = hasActiveShare ? shareIcon : "";
      const moreIcon = window.Icons?.moreVertical
        ? window.Icons.moreVertical(20, "currentColor")
        : "⋮";

      return `
            <div class="file-row interactive" data-file-id="${escapedFileId}" data-id="${escapedFileId}">
                <div class="file-row-icon">${getFileIcon(file.original_name)}</div>
                <div class="file-row-name" title="${escapedFileName}">${escapedFileName} ${shareIndicator}</div>
                <div class="file-row-size">${formatFileSize(file.size)}</div>
                <div class="file-row-date">${formatDate(file.created_at)}</div>
                <div class="file-row-actions">
                    <button class="file-menu-btn" data-file-id="${escapedFileId}" title="More options" aria-label="More options">
                        ${moreIcon}
                    </button>
                </div>
            </div>
        `;
    })
    .join("");

  if (container) setInnerHTML(container, filesHTML);
}

// Helper function to create file row element for virtual list
function createFileRowElement(file, index) {
  const escapedFileName = escapeHtml(file.original_name);
  const escapedFileId = escapeHtml(file.file_id);
  const hasActiveShare = file.has_active_share === true;
  const shareIcon = window.Icons?.link
    ? window.Icons.link(14, "currentColor")
    : "🔗";
  const shareIndicator = hasActiveShare ? shareIcon : "";
  const moreIcon = window.Icons?.moreVertical
    ? window.Icons.moreVertical(20, "currentColor")
    : "⋮";

  const row = document.createElement("div");
  row.className = "file-row interactive";
  row.dataset.fileId = escapedFileId;
  row.dataset.id = escapedFileId;

  const rowHTML = `
    <div class="file-row-icon">${getFileIcon(file.original_name)}</div>
    <div class="file-row-name" title="${escapedFileName}">${escapedFileName} ${shareIndicator}</div>
    <div class="file-row-size">${formatFileSize(file.size)}</div>
    <div class="file-row-date">${formatDate(file.created_at)}</div>
    <div class="file-row-actions">
      <button class="file-menu-btn" data-file-id="${escapedFileId}" title="More options" aria-label="More options">
        ${moreIcon}
      </button>
    </div>
  `;

  // Set innerHTML using TrustedHTML if available
  if (window.vaultHTMLPolicy) {
    try {
      row.innerHTML = window.vaultHTMLPolicy.createHTML(rowHTML);
    } catch (e) {
      row.innerHTML = rowHTML;
    }
  } else {
    row.innerHTML = rowHTML;
  }

  return row;
}

// Helper function to create file card element for virtual list
function createFileCardElement(file, index) {
  const escapedFileName = escapeHtml(file.original_name);
  const escapedFileId = escapeHtml(file.file_id);
  const hasActiveShare = file.has_active_share === true;
  const shareIcon = window.Icons?.link
    ? window.Icons.link(14, "currentColor")
    : "🔗";
  const shareIndicator = hasActiveShare
    ? `<span class="share-badge" title="This file has an active share link">${shareIcon} Shared</span>`
    : "";
  const lockIcon = window.Icons?.lock
    ? window.Icons.lock(14, "currentColor")
    : "🔒";
  const moreIcon = window.Icons?.moreVertical
    ? window.Icons.moreVertical(20, "currentColor")
    : "⋮";

  const card = document.createElement("div");
  card.className = "file-card";
  card.dataset.fileId = escapedFileId;

  const cardHTML = `
    <div class="file-icon">${getFileIcon(file.original_name)}</div>
    <div class="file-name" title="${escapedFileName}">${escapedFileName}</div>
    <div class="file-meta">
      ${formatFileSize(file.size)} • ${formatDate(file.created_at)}
    </div>
    <div class="file-badge">
      <span class="e2ee-badge">${lockIcon} E2EE</span>
      ${shareIndicator}
    </div>
    <div class="file-card-actions">
      <button class="file-menu-btn" data-file-id="${escapedFileId}" title="More options" aria-label="More options">
        ${moreIcon}
      </button>
    </div>
  `;

  if (window.vaultHTMLPolicy) {
    try {
      card.innerHTML = window.vaultHTMLPolicy.createHTML(cardHTML);
    } catch (e) {
      card.innerHTML = cardHTML;
    }
  } else {
    card.innerHTML = cardHTML;
  }

  return card;
}

// Sort files
function sortFiles(files, sortBy) {
  const sorted = [...files];

  switch (sortBy) {
    case "date-desc":
      return sorted.sort(
        (a, b) => new Date(b.created_at) - new Date(a.created_at),
      );
    case "date-asc":
      return sorted.sort(
        (a, b) => new Date(a.created_at) - new Date(b.created_at),
      );
    case "name-asc":
      return sorted.sort((a, b) =>
        a.original_name.localeCompare(b.original_name),
      );
    case "name-desc":
      return sorted.sort((a, b) =>
        b.original_name.localeCompare(a.original_name),
      );
    case "size-asc":
      return sorted.sort((a, b) => a.size - b.size);
    case "size-desc":
      return sorted.sort((a, b) => b.size - a.size);
    default:
      return sorted;
  }
}

// Filter files by search query
function filterFiles(files, query) {
  if (!query) return files;

  const lowerQuery = query.toLowerCase();
  return files.filter((file) => {
    const name = file.original_name.toLowerCase();
    const ext = name.split(".").pop() || "";
    return name.includes(lowerQuery) || ext.includes(lowerQuery);
  });
}

// Debounce function
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Render files with current filters
function renderFilteredFiles() {
  const searchInput = document.getElementById("search-input");
  const sortSelect = document.getElementById("sort-select");

  const query = searchInput ? searchInput.value.trim() : "";
  const sortBy = sortSelect ? sortSelect.value : "date-desc";

  let filtered = filterFiles(filesList, query);
  filtered = sortFiles(filtered, sortBy);

  renderFiles(filtered);

  // Update result count if needed
  const container = document.getElementById("files-list");
  if (container && query) {
    const resultCount = filtered.length;
    const totalCount = filesList.length;
    if (resultCount !== totalCount) {
      // Could add a result counter here if needed
    }
  }
}

// Load files from API
async function loadFiles() {
  try {
    // Get current folder ID from folders.js if available
    const folderId = window.Folders
      ? window.Folders.getCurrentFolderId()
      : null;

    // Determine view type from path
    const path = window.location.pathname;
    let viewType = "all";
    if (path === "/recent") {
      viewType = "recent";
    } else if (path === "/starred") {
      viewType = "starred";
    } else if (path === "/shared") {
      viewType = "shared";
    } else if (path === "/trash") {
      viewType = "trash";
    }

    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    // Map view types to API v2 endpoints
    let url;
    if (viewType === "recent") {
      url = `/api/v2/files/recent`;
    } else if (viewType === "starred") {
      url = `/api/v2/files/starred`;
    } else if (viewType === "shared") {
      // Shared files might need a different endpoint
      url = `/api/v2/files`;
    } else if (viewType === "trash") {
      // Trash is handled by trash API
      url = `/api/v2/trash`;
    } else {
      url = `/api/v2/files`;
    }

    // Add query parameters
    const params = new URLSearchParams();
    if (
      folderId &&
      viewType !== "recent" &&
      viewType !== "starred" &&
      viewType !== "trash"
    ) {
      params.append("parent_id", folderId);
    }

    if (params.toString()) {
      url += `?${params.toString()}`;
    }

    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("Failed to fetch files");

    const data = await response.json();
    // API v2 returns files directly or in a files array
    filesList = data.files || data || [];

    // Apply filters and render
    renderFilteredFiles();
  } catch (error) {
    console.error("Error loading files:", error);
    const container = document.getElementById("files-list");
    if (container) {
      setInnerHTML(
        container,
        '<div class="files-loading">Error loading files</div>',
      );
    }
    if (window.Notifications) {
      window.Notifications.error("Failed to load files");
    }
  }
}

// Upload file with encryption and progress tracking
async function uploadFile(file) {
  if (!file) return;

  const statusEl = document.getElementById("upload-status");
  const progressEl = document.getElementById("upload-progress");
  const progressBar = document.getElementById("progress-bar");
  const progressPercent = document.getElementById("progress-percent");
  const progressSpeed = document.getElementById("progress-speed");
  const progressTime = document.getElementById("progress-time");

  if (statusEl) {
    statusEl.className = "status info";
    statusEl.textContent = `Encrypting ${file.name}...`;
    statusEl.classList.remove("hidden");
  }

  // Hide progress initially
  if (progressEl) {
    progressEl.classList.add("hidden");
  }

  try {
    // Encrypt file client-side
    const { encryptedData, key } = await VaultCrypto.encryptFile(file);

    // Create FormData
    const formData = new FormData();
    const encryptedBlob = new Blob([encryptedData], {
      type: "application/octet-stream",
    });
    formData.append("file", encryptedBlob, file.name);
    formData.append("original_size", file.size.toString());

    // Add CSRF token
    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content");
    if (csrfToken) {
      formData.append("csrf_token", csrfToken);
    }

    // Get current folder ID for upload
    const folderId = window.Folders
      ? window.Folders.getCurrentFolderId()
      : null;
    if (folderId) {
      formData.append("folder_id", folderId);
    }

    // Detect MIME type
    const mimeType = file.type || "application/octet-stream";
    formData.append("mime_type", mimeType);

    // Upload with progress tracking using XMLHttpRequest
    if (statusEl) {
      statusEl.textContent = `Uploading ${file.name}...`;
    }

    if (progressEl) {
      progressEl.classList.remove("hidden");
    }

    const startTime = Date.now();
    let lastLoaded = 0;
    let lastTime = startTime;

    const result = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 100);
          const currentTime = Date.now();
          const timeDiff = (currentTime - lastTime) / 1000; // seconds
          const loadedDiff = e.loaded - lastLoaded; // bytes

          if (progressBar) {
            progressBar.style.width = `${percent}%`;
          }
          if (progressPercent) {
            progressPercent.textContent = `${percent}%`;
          }

          // Calculate speed
          if (timeDiff > 0) {
            const speed = loadedDiff / timeDiff; // bytes per second
            const speedFormatted = formatFileSize(speed) + "/s";
            if (progressSpeed) {
              progressSpeed.textContent = speedFormatted;
            }

            // Estimate time remaining
            const remaining = e.total - e.loaded;
            const timeRemaining = remaining / speed; // seconds
            if (
              progressTime &&
              !isNaN(timeRemaining) &&
              isFinite(timeRemaining)
            ) {
              if (timeRemaining < 60) {
                progressTime.textContent = `${Math.round(timeRemaining)}s remaining`;
              } else {
                progressTime.textContent = `${Math.round(timeRemaining / 60)}m remaining`;
              }
            }
          }

          lastLoaded = e.loaded;
          lastTime = currentTime;
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (e) {
            reject(new Error("Invalid response"));
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            if (xhr.status === 429) {
              reject(
                new Error(
                  error.error || "Rate limit exceeded. Please try again later.",
                ),
              );
            } else if (xhr.status === 413) {
              reject(new Error(error.error || "File too large"));
            } else {
              reject(new Error(error.error || "Upload failed"));
            }
          } catch (e) {
            if (xhr.status === 429) {
              reject(new Error("Rate limit exceeded. Please try again later."));
            } else if (xhr.status === 413) {
              reject(new Error("File too large"));
            } else {
              reject(new Error(`Upload failed: ${xhr.status}`));
            }
          }
        }
      });

      xhr.addEventListener("error", () => {
        reject(new Error("Network error"));
      });

      xhr.addEventListener("abort", () => {
        reject(new Error("Upload cancelled"));
      });

      // Migrate to API v2 - requires JWT authentication
      const jwtToken = localStorage.getItem("jwt_token");
      if (!jwtToken) {
        reject(new Error("Authentication required"));
        return;
      }

      xhr.open("POST", "/api/v2/files");
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      xhr.setRequestHeader("Authorization", `Bearer ${jwtToken}`);
      // API v2 uses FormData, no CSRF token needed (JWT-based auth)
      xhr.send(formData);
    });

    const fileId = result.file_id;

    // Hide progress
    if (progressEl) {
      progressEl.classList.add("hidden");
    }

    // Store key locally for future downloads
    storeFileKey(fileId, key);

    if (statusEl) {
      statusEl.className = "status success";
      statusEl.textContent = `Upload successful: ${file.name}`;
    }

    // Show success notification
    if (window.Notifications) {
      window.Notifications.success(`File "${file.name}" uploaded successfully`);
    }

    // Reload files list
    await loadFiles();

    // Reset file input after successful upload
    const fileInput = document.getElementById("file-input");
    if (fileInput) {
      fileInput.value = "";
    }
  } catch (error) {
    console.error("Upload error:", error);
    if (progressEl) {
      progressEl.classList.add("hidden");
    }
    if (statusEl) {
      statusEl.className = "status error";
      statusEl.textContent = `Error: ${error.message}`;
    }
    if (window.Notifications) {
      window.Notifications.error(`Upload failed: ${error.message}`);
    }
  }
}

// Store key in localStorage (client-side only)
// Import IndexedDB-based file key storage
let fileKeyStorage = null;
(async () => {
  try {
    const module = await import("/static/src/services/fileKeyStorage.js");
    fileKeyStorage = module;
  } catch (e) {
    console.warn(
      "Failed to load IndexedDB file key storage, using localStorage fallback:",
      e,
    );
  }
})();

async function storeFileKey(fileId, key) {
  const keyStr = VaultCrypto.arrayToBase64url(key);
  if (fileKeyStorage) {
    try {
      await fileKeyStorage.storeFileKey(fileId, keyStr);
      return;
    } catch (e) {
      console.warn(
        "Failed to store file key in IndexedDB, using localStorage:",
        e,
      );
    }
  }
  // Fallback to localStorage
  try {
    const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
    keys[fileId] = keyStr;
    localStorage.setItem("vault_keys", JSON.stringify(keys));
  } catch (e) {
    console.warn("Failed to store key:", e);
  }
}

// Get key from IndexedDB or localStorage
async function getFileKey(fileId) {
  if (fileKeyStorage) {
    try {
      const keyStr = await fileKeyStorage.getFileKey(fileId);
      if (keyStr) {
        return VaultCrypto.base64urlToArray(keyStr);
      }
    } catch (e) {
      console.warn(
        "Failed to get file key from IndexedDB, using localStorage:",
        e,
      );
    }
  }
  // Fallback to localStorage
  try {
    const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
    const keyStr = keys[fileId];
    if (!keyStr) return null;
    return VaultCrypto.base64urlToArray(keyStr);
  } catch (e) {
    console.warn("Failed to get key:", e);
    return null;
  }
}

// Download file with decryption
async function downloadFile(fileId) {
  const file = filesList.find((f) => f.file_id === fileId);
  if (!file) {
    if (window.Notifications) {
      window.Notifications.error("File not found");
    }
    return;
  }

  try {
    // Get key from storage or prompt
    let key = getFileKey(fileId);

    if (!key) {
      const keyStr = prompt("Enter the decryption key (base64url):");
      if (!keyStr) return;
      try {
        key = VaultCrypto.base64urlToArray(keyStr);
        // Store for future use
        storeFileKey(fileId, key);
      } catch (e) {
        if (window.Notifications) {
          window.Notifications.error("Invalid decryption key");
        }
        return;
      }
    }

    // Show info notification
    if (window.Notifications) {
      window.Notifications.info(`Downloading "${file.original_name}"...`);
    }

    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    // Download encrypted file using API v2
    const response = await fetch(`/api/v2/files/${fileId}/download`, {
      headers: {
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
    });
    if (!response.ok) throw new Error("Download failed");

    const encryptedBlob = await response.blob();
    const encryptedArrayBuffer = await encryptedBlob.arrayBuffer();
    const encryptedData = new Uint8Array(encryptedArrayBuffer);

    // Decrypt
    const decryptedBuffer = await VaultCrypto.decryptFile(encryptedData, key);

    // Download
    const decryptedBlob = new Blob([decryptedBuffer]);
    const url = URL.createObjectURL(decryptedBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.original_name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    // Show success notification
    if (window.Notifications) {
      window.Notifications.success(
        `File "${file.original_name}" downloaded successfully`,
      );
    }
  } catch (error) {
    console.error("Download error:", error);
    if (window.Notifications) {
      window.Notifications.error(`Download failed: ${error.message}`);
    }
  }
}

// Helper function to generate HTML for existing share links
function generateExistingLinksHTML(activeLinks, fileId, key) {
  if (activeLinks.length === 0) {
    return "";
  }

  const linksHTML = activeLinks
    .map((link) => {
      const linkUrl = `${window.location.origin}/share/${link.link_id}#key=${VaultCrypto.arrayToBase64url(key)}&file=${fileId}`;
      const expiresText = link.expires_at
        ? `Expires: ${formatDate(link.expires_at)}`
        : "No expiration";
      const downloadsText = link.max_downloads
        ? `${link.download_count}/${link.max_downloads} downloads`
        : `${link.download_count} downloads`;
      return `
        <div class="existing-link-item">
          <div class="existing-link-info">
            <input type="text" value="${escapeHtml(linkUrl)}" readonly class="share-url-input-small" />
            <div class="link-meta">${escapeHtml(expiresText)} • ${escapeHtml(downloadsText)}</div>
          </div>
          <button class="btn btn-danger btn-small revoke-link-btn" data-link-token="${escapeHtml(link.link_id)}" title="Revoke link">
            Revoke
          </button>
        </div>
      `;
    })
    .join("");

  return `
    <div class="existing-links-header">
      <h4>Active share links (${activeLinks.length})</h4>
    </div>
    <div class="existing-links-list">
      ${linksHTML}
    </div>
    <hr class="share-divider" />
  `;
}

// Share file - show modal and create share link
async function shareFile(fileId, key = null) {
  currentShareFileId = fileId;

  // Get key from storage if not provided
  if (!key) {
    key = getFileKey(fileId);
  }

  if (!key) {
    if (window.Notifications) {
      window.Notifications.warning(
        "Decryption key not found. The file must be uploaded from this device to be shareable.",
      );
    }
    return;
  }

  currentShareKey = key;

  // Show modal first
  const modal = document.getElementById("share-modal");
  const shareUrlInput = document.getElementById("share-url");
  const existingLinksContainer = document.getElementById("existing-links");

  if (modal) modal.classList.remove("hidden");

  // Load existing share links
  try {
    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content");

    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      console.error("JWT token not found, cannot load share links");
      return;
    }

    const linksResponse = await fetch(
      `/api/v2/sharing/public-links?resource_id=${fileId}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
        credentials: "same-origin",
      },
    );

    if (linksResponse.ok) {
      const linksData = await linksResponse.json();
      // API v2 returns share_links array
      const shareLinks = linksData.share_links || [];
      // Map to legacy format
      const activeLinks = shareLinks
        .filter((link) => link.is_active && !link.is_expired)
        .map((link) => ({
          link_id: link.token || link.link_id,
          expires_at: link.expires_at,
          max_downloads: link.max_downloads,
          download_count: link.download_count || 0,
          is_active: link.is_active,
          is_expired: link.is_expired || false,
        }));

      if (activeLinks.length > 0 && existingLinksContainer) {
        const linksHTML = generateExistingLinksHTML(activeLinks, fileId, key);
        setInnerHTML(existingLinksContainer, linksHTML);

        // Attach event listeners for revoke buttons
        existingLinksContainer
          .querySelectorAll(".revoke-link-btn")
          .forEach((btn) => {
            btn.addEventListener("click", async (e) => {
              const linkToken = e.target.getAttribute("data-link-token");
              if (linkToken) {
                await revokeShareLink(fileId, linkToken);
              }
            });
          });
      } else if (existingLinksContainer) {
        setInnerHTML(existingLinksContainer, "");
      }
    }
  } catch (error) {
    console.error("Error loading existing links:", error);
    if (existingLinksContainer) {
      setInnerHTML(existingLinksContainer, "");
    }
  }

  // Create share link via API (without expiration/limits for now, can be extended)
  try {
    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content");

    // Migrate to API v2 - requires JWT authentication
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    const response = await fetch(`/api/v2/sharing/public-links`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        resource_id: fileId,
        resource_type: "file",
        expires_in_days: null, // Can be extended with UI inputs
        max_downloads: null, // Can be extended with UI inputs
        allow_download: true,
        allow_preview: true,
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to create share link");
    }

    const data = await response.json();
    const shareLink = data.share_link || data;
    const linkToken = shareLink.token || shareLink.link_id;

    // Create share URL with token and key in fragment
    const baseUrl = window.location.origin;
    const shareUrl = `${baseUrl}/share/${linkToken}#key=${VaultCrypto.arrayToBase64url(key)}&file=${fileId}`;

    if (shareUrlInput) shareUrlInput.value = shareUrl;

    if (window.Notifications) {
      window.Notifications.success("Share link created successfully");
    }

    // Reload existing links to show the new one
    if (existingLinksContainer) {
      const linksResponse = await fetch(
        `/api/v2/sharing/public-links?resource_id=${fileId}`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${jwtToken}`,
          },
          credentials: "same-origin",
        },
      );

      if (linksResponse.ok) {
        const linksData = await linksResponse.json();
        // API v2 returns share_links array
        const shareLinks = linksData.share_links || [];
        // Map to legacy format
        const activeLinks = shareLinks
          .filter((link) => link.is_active && !link.is_expired)
          .map((link) => ({
            link_id: link.token || link.link_id,
            expires_at: link.expires_at,
            max_downloads: link.max_downloads,
            download_count: link.download_count || 0,
            is_active: link.is_active,
            is_expired: link.is_expired || false,
          }));

        if (activeLinks.length > 0) {
          const linksHTML = generateExistingLinksHTML(activeLinks, fileId, key);
          setInnerHTML(existingLinksContainer, linksHTML);

          // Re-attach event listeners
          existingLinksContainer
            .querySelectorAll(".revoke-link-btn")
            .forEach((btn) => {
              btn.addEventListener("click", async (e) => {
                const linkToken = e.target.getAttribute("data-link-token");
                if (linkToken) {
                  await revokeShareLink(fileId, linkToken);
                }
              });
            });
        } else {
          setInnerHTML(existingLinksContainer, "");
        }
      }
    }
  } catch (error) {
    console.error("Error creating share link:", error);
    // Fallback to alternative URL format
    const shareUrl = VaultCrypto.createShareUrl(fileId, key);
    if (shareUrlInput) shareUrlInput.value = shareUrl;

    if (window.Notifications) {
      window.Notifications.warning("Using alternative share format");
    }
  }
}

// Revoke share link
async function revokeShareLink(fileId, linkToken) {
  try {
    // Get JWT token for authentication
    const token = localStorage.getItem("jwt_token");
    if (!token) {
      throw new Error("Not authenticated");
    }

    // Migrate to API v2 - use public-links endpoint
    const response = await fetch(`/api/v2/sharing/public-links/${linkToken}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      credentials: "same-origin",
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || "Failed to revoke share link");
    }

    if (window.Notifications) {
      window.Notifications.success("Share link revoked successfully");
    }

    // Reload files list to update the share indicator
    await loadFiles();

    // Reload existing links in the modal if it's open
    const modal = document.getElementById("share-modal");
    const existingLinksContainer = document.getElementById("existing-links");
    if (
      modal &&
      !modal.classList.contains("hidden") &&
      existingLinksContainer
    ) {
      const key = currentShareKey || getFileKey(fileId);
      if (key) {
        const linksResponse = await fetch(`/api/share/${fileId}/links`, {
          method: "GET",
          headers: {
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
          credentials: "same-origin",
        });

        if (linksResponse.ok) {
          const linksData = await linksResponse.json();
          const activeLinks = linksData.links.filter(
            (link) => link.is_active && !link.is_expired,
          );

          if (activeLinks.length > 0) {
            const linksHTML = generateExistingLinksHTML(
              activeLinks,
              fileId,
              key,
            );
            setInnerHTML(existingLinksContainer, linksHTML);

            // Re-attach event listeners
            existingLinksContainer
              .querySelectorAll(".revoke-link-btn")
              .forEach((btn) => {
                btn.addEventListener("click", async (e) => {
                  const linkToken = e.target.getAttribute("data-link-token");
                  if (linkToken) {
                    await revokeShareLink(fileId, linkToken);
                  }
                });
              });
          } else {
            setInnerHTML(existingLinksContainer, "");
          }
        }
      }
    }
  } catch (error) {
    console.error("Error revoking share link:", error);
    if (window.Notifications) {
      window.Notifications.error(
        `Failed to revoke share link: ${error.message}`,
      );
    }
  }
}

// Delete file
async function deleteFile(fileId) {
  const file = filesList.find((f) => f.file_id === fileId);
  if (!file) {
    if (window.Notifications) {
      window.Notifications.error("File not found");
    }
    return;
  }

  // Use styled confirmation modal instead of native confirm
  if (typeof window.showConfirmationModal === "function") {
    const deleteIcon = window.Icons?.delete
      ? window.Icons.delete(20, "currentColor")
      : "🗑️";
    window.showConfirmationModal({
      icon: deleteIcon,
      title: "Delete File",
      message: `Are you sure you want to delete "${file.original_name}"? This action cannot be undone.`,
      confirmText: "Delete",
      dangerous: true,
      onConfirm: async () => {
        try {
          // Migrate to API v2 - requires JWT authentication
          const jwtToken = localStorage.getItem("jwt_token");
          if (!jwtToken) {
            throw new Error("Authentication required");
          }

          const response = await fetch(`/api/v2/files/${fileId}`, {
            method: "DELETE",
            headers: {
              Authorization: `Bearer ${jwtToken}`,
            },
            credentials: "same-origin",
          });

          if (!response.ok) throw new Error("Delete failed");

          await loadFiles();

          if (window.Notifications) {
            window.Notifications.success(
              `File "${file.original_name}" deleted successfully`,
            );
          }
        } catch (error) {
          console.error("Delete error:", error);
          if (window.Notifications) {
            window.Notifications.error(`Delete failed: ${error.message}`);
          }
        }
      },
    });
  }
}

// Copy share URL
function copyShareUrl() {
  const input = document.getElementById("share-url");
  if (!input) return;

  input.select();
  document.execCommand("copy");

  const btn = document.getElementById("copy-share-btn");
  if (btn) {
    const originalText = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => {
      btn.textContent = originalText;
    }, 2000);
  }
}

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  // Setup file selection
  const filesContainer = document.getElementById("files-list");
  if (filesContainer) {
    filesContainer.addEventListener("click", (e) => {
      const fileCard = e.target.closest(".file-card, .file-row");
      if (
        fileCard &&
        !e.target.closest(
          ".file-actions, .file-row-actions, .file-menu-btn, .file-card-actions",
        )
      ) {
        const fileId = fileCard.dataset.fileId || fileCard.dataset.id;
        if (fileId && window.selectionManager) {
          window.selectionManager.toggle(fileId, e);
        }
      }
    });

    // Double-click to preview files
    filesContainer.addEventListener("dblclick", (e) => {
      const fileCard = e.target.closest(".file-card, .file-row");
      if (
        fileCard &&
        !e.target.closest(
          ".file-actions, .file-row-actions, .file-menu-btn, .file-card-actions",
        )
      ) {
        const fileId = fileCard.dataset.fileId || fileCard.dataset.id;
        if (fileId && window.showFilePreview) {
          const file = filesList.find((f) => f.file_id === fileId);
          if (file) {
            window.showFilePreview(fileId, file.original_name, file.mime_type);
          }
        }
      }
    });
  }

  // Setup folder selection
  const foldersContainer = document.getElementById("folders-list");
  if (foldersContainer) {
    foldersContainer.addEventListener("click", (e) => {
      const folderCard = e.target.closest(".folder-card, .folder-row");
      if (
        folderCard &&
        !e.target.closest(".folder-actions, .folder-row-actions")
      ) {
        const folderId = folderCard.dataset.folderId || folderCard.dataset.id;
        if (folderId && window.selectionManager) {
          window.selectionManager.toggle(folderId, e);
        }
      }
    });
  }

  // View toggle buttons
  const viewGridBtn = document.getElementById("view-grid-btn");
  const viewListBtn = document.getElementById("view-list-btn");

  if (viewGridBtn && viewListBtn) {
    viewGridBtn.addEventListener("click", () => {
      currentView = "grid";
      window.currentView = "grid";
      viewGridBtn.classList.add("active");
      viewListBtn.classList.remove("active");
      renderFilteredFiles();
      // Reload folders to update their view
      if (window.Folders && window.Folders.loadFolderContents) {
        const currentFolderId = window.Folders.getCurrentFolderId();
        window.Folders.loadFolderContents(currentFolderId);
      }
    });

    viewListBtn.addEventListener("click", () => {
      currentView = "list";
      window.currentView = "list";
      viewListBtn.classList.add("active");
      viewGridBtn.classList.remove("active");
      renderFilteredFiles();
      // Reload folders to update their view
      if (window.Folders && window.Folders.loadFolderContents) {
        const currentFolderId = window.Folders.getCurrentFolderId();
        window.Folders.loadFolderContents(currentFolderId);
      }
    });
  }

  // File input
  const fileInput = document.getElementById("file-input");
  const uploadArea = document.getElementById("upload-area");

  if (fileInput && uploadArea) {
    // Find the label element
    const label = uploadArea.querySelector("label[for='file-input']");

    // Remove the 'for' attribute from label to prevent native behavior
    // We'll handle the click manually
    if (label) {
      label.removeAttribute("for");
      label.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
      });
    }

    // Click to upload on the rest of the upload area
    uploadArea.addEventListener("click", (e) => {
      // Don't trigger if clicking on the label (we handle it separately above)
      if (label && (label.contains(e.target) || e.target === label)) {
        return;
      }
      fileInput.click();
    });

    // File selection - handle the change event
    fileInput.addEventListener("change", (e) => {
      const files = Array.from(e.target.files);
      if (files.length > 0 && window.uploadManager) {
        window.uploadManager.queueFiles(files);
      } else if (files.length > 0) {
        // Fallback to old upload method
        files.forEach((file) => uploadFile(file));
      }
    });

    // Drag and drop
    uploadArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadArea.classList.add("dragover");
    });

    uploadArea.addEventListener("dragleave", () => {
      uploadArea.classList.remove("dragover");
    });

    uploadArea.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadArea.classList.remove("dragover");
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0 && window.uploadManager) {
        window.uploadManager.queueFiles(files);
      } else if (files.length > 0) {
        // Fallback to old upload method
        files.forEach((file) => uploadFile(file));
      }
    });
  }

  // Search input with debounce
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    const debouncedSearch = debounce(() => {
      renderFilteredFiles();
    }, 300);

    searchInput.addEventListener("input", debouncedSearch);
  }

  // Sort select
  const sortSelect = document.getElementById("sort-select");
  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      renderFilteredFiles();
    });
  }

  // Modal close
  const modalClose = document.getElementById("modal-close");
  const modal = document.getElementById("share-modal");
  const modalBackdrop = modal?.querySelector(".modal-backdrop");

  if (modalClose) {
    modalClose.addEventListener("click", () => {
      if (modal) modal.classList.add("hidden");
    });
  }

  if (modalBackdrop) {
    modalBackdrop.addEventListener("click", () => {
      if (modal) modal.classList.add("hidden");
    });
  }

  // Copy share URL
  const copyBtn = document.getElementById("copy-share-btn");
  if (copyBtn) {
    copyBtn.addEventListener("click", copyShareUrl);
  }

  // Load files on page load
  loadFiles();

  // Attach event delegation for file actions
  const filesListContainer = document.getElementById("files-list");
  if (filesListContainer) {
    attachFileActionListeners(filesListContainer);
  }

  // Replace sidebar icons with SVG icons
  if (window.Icons) {
    const sidebarIcons = document.querySelectorAll(".sidebar-icon[data-icon]");
    sidebarIcons.forEach((iconEl) => {
      const iconName = iconEl.getAttribute("data-icon");
      if (window.Icons[iconName]) {
        const iconHTML = window.Icons[iconName](20, "currentColor");
        if (window.vaultHTMLPolicy) {
          try {
            iconEl.innerHTML = window.vaultHTMLPolicy.createHTML(iconHTML);
          } catch (e) {
            iconEl.innerHTML = iconHTML;
          }
        } else {
          iconEl.innerHTML = iconHTML;
        }
      }
    });
  }
});
