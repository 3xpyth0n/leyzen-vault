/** @file files.js - File explorer interface with E2EE */

let filesList = [];
let currentShareFileId = null;
let currentShareKey = null;

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
  const icons = {
    pdf: "📄",
    doc: "📝",
    docx: "📝",
    xls: "📊",
    xlsx: "📊",
    ppt: "📊",
    pptx: "📊",
    jpg: "🖼️",
    jpeg: "🖼️",
    png: "🖼️",
    gif: "🖼️",
    svg: "🖼️",
    mp4: "🎬",
    avi: "🎬",
    mov: "🎬",
    mp3: "🎵",
    wav: "🎵",
    zip: "📦",
    rar: "📦",
    txt: "📄",
    code: "💻",
  };
  return icons[ext] || "📄";
}

// Attach event listeners for file actions using event delegation
function attachFileActionListeners(container) {
  // Use event delegation - attach once to the container
  // This works even when innerHTML is replaced
  container.addEventListener("click", (e) => {
    const button = e.target.closest(".file-action-btn");
    if (!button) return;

    const action = button.getAttribute("data-action");
    const fileId = button.getAttribute("data-file-id");

    if (!action || !fileId) return;

    switch (action) {
      case "download":
        e.preventDefault();
        downloadFile(fileId);
        break;
      case "share":
        e.preventDefault();
        shareFile(fileId);
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
    container.innerHTML = '<div class="files-loading">No files uploaded</div>';
    return;
  }

  container.innerHTML = files
    .map((file) => {
      // Escape user data to prevent XSS attacks
      const escapedFileName = escapeHtml(file.original_name);
      const escapedFileId = escapeHtml(file.file_id);
      return `
            <div class="file-card" data-file-id="${escapedFileId}">
                <div class="file-icon">${getFileIcon(file.original_name)}</div>
                <div class="file-name" title="${escapedFileName}">${escapedFileName}</div>
                <div class="file-meta">
                    ${formatFileSize(file.size)} • ${formatDate(file.created_at)}
                </div>
                <div class="file-badge">
                    <span class="e2ee-badge">🔒 E2EE</span>
                </div>
                <div class="file-actions">
                    <button class="file-action-btn" data-action="download" data-file-id="${escapedFileId}" title="Download">
                        ⬇️ Download
                    </button>
                    <button class="file-action-btn" data-action="share" data-file-id="${escapedFileId}" title="Share">
                        🔗 Share
                    </button>
                    <button class="file-action-btn" data-action="delete" data-file-id="${escapedFileId}" title="Delete">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
    })
    .join("");

  // Note: Event listeners are attached once in DOMContentLoaded
  // Using event delegation, so they work even after innerHTML changes
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
    const response = await fetch("/api/files");
    if (!response.ok) throw new Error("Failed to fetch files");

    const data = await response.json();
    filesList = data.files || [];

    // Apply filters and render
    renderFilteredFiles();
  } catch (error) {
    console.error("Error loading files:", error);
    const container = document.getElementById("files-list");
    if (container) {
      container.innerHTML =
        '<div class="files-loading">Error loading files</div>';
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

      xhr.open("POST", "/api/files");
      xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
      if (csrfToken) {
        xhr.setRequestHeader("X-CSRFToken", csrfToken);
      }
      xhr.send(formData);
    });

    const fileId = result.file_id;

    // Hide progress
    if (progressEl) {
      progressEl.classList.add("hidden");
    }

    // Store key locally for future downloads
    storeFileKey(fileId, key);

    // Store key for sharing
    currentShareFileId = fileId;
    currentShareKey = key;

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

    // Show share modal
    shareFile(fileId, key);
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
function storeFileKey(fileId, key) {
  try {
    const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
    keys[fileId] = VaultCrypto.arrayToBase64url(key);
    localStorage.setItem("vault_keys", JSON.stringify(keys));
  } catch (e) {
    console.warn("Failed to store key:", e);
  }
}

// Get key from localStorage
function getFileKey(fileId) {
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

    // Download encrypted file
    const response = await fetch(`/api/files/${fileId}`);
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

  if (modal) modal.classList.remove("hidden");

  // Create share link via API (without expiration/limits for now, can be extended)
  try {
    const csrfToken = document
      .querySelector('meta[name="csrf-token"]')
      ?.getAttribute("content");

    const response = await fetch(`/api/files/${fileId}/share`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
      },
      credentials: "same-origin",
      body: JSON.stringify({
        expires_in_hours: null, // Can be extended with UI inputs
        max_downloads: null, // Can be extended with UI inputs
      }),
    });

    if (!response.ok) {
      throw new Error("Failed to create share link");
    }

    const shareLink = await response.json();
    const linkToken = shareLink.link_id;

    // Create share URL with token and key in fragment
    const baseUrl = window.location.origin;
    const shareUrl = `${baseUrl}/share/${linkToken}#key=${VaultCrypto.arrayToBase64url(key)}&file=${fileId}`;

    if (shareUrlInput) shareUrlInput.value = shareUrl;

    if (window.Notifications) {
      window.Notifications.success("Share link created successfully");
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
    window.showConfirmationModal({
      icon: "🗑️",
      title: "Delete File",
      message: `Are you sure you want to delete "${file.original_name}"? This action cannot be undone.`,
      confirmText: "Delete",
      dangerous: true,
      onConfirm: async () => {
        try {
          const csrfToken = document
            .querySelector('meta[name="csrf-token"]')
            ?.getAttribute("content");
          const response = await fetch(`/api/files/${fileId}`, {
            method: "DELETE",
            credentials: "same-origin",
            headers: csrfToken
              ? {
                  "X-CSRFToken": csrfToken,
                }
              : {},
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
  } else {
    // Fallback to native confirm if modal function not available
    if (!confirm(`Are you sure you want to delete "${file.original_name}"?`))
      return;

    try {
      const csrfToken = document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");
      const response = await fetch(`/api/files/${fileId}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: csrfToken
          ? {
              "X-CSRFToken": csrfToken,
            }
          : {},
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
      if (files.length > 0) {
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
      files.forEach((file) => uploadFile(file));
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
});
