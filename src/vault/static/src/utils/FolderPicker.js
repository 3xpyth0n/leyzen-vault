/**
 * Folder Picker Modal
 * Allows user to select a destination folder for move/copy operations
 */

// Helper function to safely set innerHTML with Trusted Types
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
  element.innerHTML = html;
}

class FolderPicker {
  constructor() {
    this.modal = null;
    this.selectedFolderId = null;
    this.resolvePromise = null;
    this.rejectPromise = null;
    this.folders = [];
    this.allFolders = [];
    this.folderTree = {};
    this.expandedFolders = new Set();
    this.currentFolderId = null;
    this.vaultspaceId = null;
    this.vaultspaceInfo = null;
  }

  /**
   * Recursively fetch all folders from the vaultspace
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {string|null} parentId - Parent folder ID (null for root, ignored when fetching all)
   * @returns {Promise<Array>} Array of all folders
   */
  async fetchAllFolders(vaultspaceId, parentId = null) {
    const allFolders = [];
    const fetched = new Set();
    const foldersToProcess = [null]; // Start with root

    const token = localStorage.getItem("jwt_token");
    if (!token) {
      throw new Error("Authentication required");
    }

    // Process folders queue (breadth-first)
    while (foldersToProcess.length > 0) {
      const currentParentId = foldersToProcess.shift();

      let page = 1;
      const perPage = 100;
      let hasMorePages = true;

      while (hasMorePages) {
        const params = new URLSearchParams({
          vaultspace_id: vaultspaceId,
          page: page.toString(),
          per_page: perPage.toString(),
        });
        if (currentParentId) {
          params.append("parent_id", currentParentId);
        }

        const response = await fetch(`/api/v2/files?${params.toString()}`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
          credentials: "same-origin",
        });

        if (!response.ok) {
          throw new Error("Failed to fetch folders");
        }

        const data = await response.json();
        const folders = (data.files || []).filter(
          (f) => f.mime_type === "application/x-directory" && !f.deleted_at, // Exclude deleted folders
        );

        for (const folder of folders) {
          if (!fetched.has(folder.id)) {
            fetched.add(folder.id);
            allFolders.push(folder);
            // Add to queue to process its children
            foldersToProcess.push(folder.id);
          }
        }

        const totalPages = data.pagination?.pages || 1;
        hasMorePages = page < totalPages;
        page++;
      }
    }

    return allFolders;
  }

  /**
   * Build hierarchical tree structure from folders list
   * @param {Array} folders - Flat list of folders with parent_id
   * @returns {Object} Tree structure
   */
  buildFolderTree(folders) {
    const tree = {};
    const folderMap = new Map();

    // First pass: create map of folders by ID
    folders.forEach((folder) => {
      const folderId = folder.id || folder.folder_id;
      folderMap.set(folderId, {
        id: folderId,
        name:
          folder.original_name || folder.name || folder.encrypted_name || "",
        parent_id: folder.parent_id || null,
        children: {},
      });
    });

    // Second pass: build tree structure
    folders.forEach((folder) => {
      const folderId = folder.id || folder.folder_id;
      const folderData = folderMap.get(folderId);
      if (!folderData) return;

      const parentId = folder.parent_id || null;
      if (parentId === null) {
        // Root folder
        tree[folderId] = folderData;
      } else {
        // Subfolder - find parent
        const parent = folderMap.get(parentId);
        if (parent) {
          parent.children[folderId] = folderData;
        } else {
          // Parent not in list, treat as root (orphaned folder)
          tree[folderId] = folderData;
        }
      }
    });

    // Sort tree recursively
    const sortTree = (node) => {
      const sorted = {};
      const entries = Object.entries(node).sort(([aKey, a], [bKey, b]) => {
        const nameA = a.name || "";
        const nameB = b.name || "";
        return nameA.localeCompare(nameB);
      });

      entries.forEach(([key, item]) => {
        sorted[key] = { ...item };
        if (item.children && Object.keys(item.children).length > 0) {
          sorted[key].children = sortTree(item.children);
        }
      });

      return sorted;
    };

    return sortTree(tree);
  }

  /**
   * Show folder picker modal
   * @param {Array} folders - List of folders (optional, will fetch all if not provided)
   * @param {string} currentFolderId - Current folder ID
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {string} excludeFolderId - Folder ID to exclude (e.g., source folder)
   * @param {Object} vaultspaceInfo - Optional vaultspace info {name, icon_name}
   * @returns {Promise<string|null>} Selected folder ID or null
   */
  async show(
    folders,
    currentFolderId,
    vaultspaceId,
    excludeFolderId = null,
    vaultspaceInfo = null,
  ) {
    this.currentFolderId = currentFolderId;
    this.vaultspaceId = vaultspaceId;
    this.selectedFolderId = null;
    this.excludeFolderId = excludeFolderId;
    this.vaultspaceInfo = vaultspaceInfo;
    this.expandedFolders.clear();

    // If folders not provided or empty, fetch all folders recursively
    if (!folders || folders.length === 0) {
      try {
        this.allFolders = await this.fetchAllFolders(vaultspaceId, null);
      } catch (error) {
        console.error("Failed to fetch all folders:", error);
        this.allFolders = folders || [];
      }
    } else {
      // Filter out deleted folders from provided list
      this.allFolders = folders.filter((f) => !f.deleted_at);
      // Try to fetch all folders anyway to get complete tree
      try {
        const allFetchedFolders = await this.fetchAllFolders(
          vaultspaceId,
          null,
        );
        // Merge with provided folders, avoiding duplicates
        const existingIds = new Set(this.allFolders.map((f) => f.id));
        allFetchedFolders.forEach((f) => {
          if (!existingIds.has(f.id) && !f.deleted_at) {
            this.allFolders.push(f);
          }
        });
      } catch (error) {
        console.warn(
          "Failed to fetch all folders, using provided list:",
          error,
        );
      }
    }

    // Filter out excluded folder
    this.allFolders = this.allFolders.filter(
      (f) => f.id !== this.excludeFolderId,
    );

    // Build tree structure
    this.folderTree = this.buildFolderTree(this.allFolders);

    return new Promise((resolve, reject) => {
      this.resolvePromise = resolve;
      this.rejectPromise = reject;
      this.createModal();
      this.renderFolders();

      // Enable confirm button if Root is selected by default
      if (this.selectedFolderId === null) {
        const confirmBtn = document.getElementById("folder-picker-confirm");
        if (confirmBtn) {
          confirmBtn.disabled = false;
        }
      }

      // Ensure modal is visible
      if (this.modal) {
        this.modal.classList.remove("hidden");

        // Force display styles to ensure visibility
        const modalOverlay = this.modal;

        if (modalOverlay) {
          // Ensure modal is always centered
          modalOverlay.style.position = "fixed";
          modalOverlay.style.top = "0";
          modalOverlay.style.left = "0";
          modalOverlay.style.right = "0";
          modalOverlay.style.bottom = "0";
          modalOverlay.style.display = "flex";
          modalOverlay.style.alignItems = "center";
          modalOverlay.style.justifyContent = "center";
          modalOverlay.style.visibility = "visible";
          modalOverlay.style.opacity = "1";
          modalOverlay.style.zIndex = "10000";
        }

        // Verify modal is in DOM
        if (!document.body.contains(this.modal)) {
          document.body.appendChild(this.modal);
        }
      }
    });
  }

  /**
   * Create modal HTML
   */
  createModal() {
    // Remove existing modal if any
    const existing = document.getElementById("folder-picker-modal");
    if (existing) {
      existing.remove();
    }

    const modalHTML = `
      <div id="folder-picker-modal" class="modal-overlay">
        <div class="modal folder-picker-modal">
          <div class="modal-header">
            <h2>Select Destination Folder</h2>
            <button class="modal-close" id="folder-picker-close">&times;</button>
          </div>
          <div class="modal-content">
            <div class="folder-picker-options">
              <div id="folder-picker-list" class="folder-picker-list"></div>
            </div>
            <div class="modal-actions">
              <button class="btn btn-secondary" id="folder-picker-cancel">Cancel</button>
              <button class="btn btn-primary" id="folder-picker-confirm" disabled>Select</button>
            </div>
          </div>
        </div>
      </div>
    `;

    // Use safe HTML insertion with Trusted Types
    // Create a temporary container, set its innerHTML with Trusted Types, then append the modal
    try {
      const tempContainer = document.createElement("div");
      setInnerHTML(tempContainer, modalHTML);
      const modalElement = tempContainer.firstElementChild;
      if (modalElement) {
        document.body.appendChild(modalElement);
        this.modal = document.getElementById("folder-picker-modal");
      }
    } catch (error) {
      throw error;
    }

    // Setup event listeners
    const closeBtn = document.getElementById("folder-picker-close");
    const cancelBtn = document.getElementById("folder-picker-cancel");
    const confirmBtn = document.getElementById("folder-picker-confirm");

    const closeHandler = () => {
      this.hide();
      // Resolve with undefined instead of rejecting - cancellation is not an error
      if (this.resolvePromise) {
        this.resolvePromise(undefined);
      }
      // Clear reject promise since we're resolving instead
      this.rejectPromise = null;
    };

    closeBtn.addEventListener("click", closeHandler);
    cancelBtn.addEventListener("click", closeHandler);
    this.modal.addEventListener("click", (e) => {
      if (e.target === this.modal) {
        closeHandler();
      }
    });

    confirmBtn.addEventListener("click", () => {
      this.hide();
      if (this.resolvePromise) {
        this.resolvePromise(this.selectedFolderId);
      }
      // Clear reject promise since we resolved
      this.rejectPromise = null;
    });

    // Handle escape key
    const escapeHandler = (e) => {
      if (e.key === "Escape" && !this.modal.classList.contains("hidden")) {
        closeHandler();
        document.removeEventListener("keydown", escapeHandler);
      }
    };
    document.addEventListener("keydown", escapeHandler);
  }

  /**
   * Generate visible list from tree based on expanded folders
   * @param {Object} tree - Folder tree structure
   * @param {Set} expanded - Set of expanded folder IDs
   * @param {number} depth - Current depth level
   * @returns {Array} List of visible folders with depth information
   */
  generateVisibleList(tree, expanded, depth = 0) {
    const visible = [];

    const traverse = (node, currentDepth = 0) => {
      const children = Object.values(node).sort((a, b) => {
        const nameA = a.original_name || a.name || "";
        const nameB = b.original_name || b.name || "";
        return nameA.localeCompare(nameB);
      });

      children.forEach((folder) => {
        const folderId = folder.id || folder.folder_id;
        const hasChildren =
          folder.children && Object.keys(folder.children).length > 0;

        visible.push({
          id: folderId,
          name: folder.name || folder.original_name || "",
          depth: currentDepth,
          hasChildren: hasChildren,
        });

        // If folder is expanded and has children, traverse them
        if (hasChildren && expanded.has(folderId)) {
          traverse(folder.children, currentDepth + 1);
        }
      });
    };

    traverse(tree, depth);
    return visible;
  }

  /**
   * Toggle folder expansion
   * @param {string} folderId - Folder ID to toggle
   */
  toggleFolder(folderId) {
    if (this.expandedFolders.has(folderId)) {
      this.expandedFolders.delete(folderId);
    } else {
      this.expandedFolders.add(folderId);
    }
    this.renderFolders();
  }

  /**
   * Check if folder is expanded
   * @param {string} folderId - Folder ID
   * @returns {boolean} True if expanded
   */
  isFolderExpanded(folderId) {
    return this.expandedFolders.has(folderId);
  }

  /**
   * Get icon from Lucide library
   * @param {string} iconName - Icon name
   * @param {number} size - Icon size
   * @returns {string} Icon HTML
   */
  getIcon(iconName, size = 24) {
    if (!window.Icons) {
      return "";
    }
    if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
      return window.Icons.getIcon(iconName, size, "currentColor");
    }
    // Fallback to old method
    if (window.Icons[iconName]) {
      const iconFunction = window.Icons[iconName];
      if (typeof iconFunction === "function") {
        return iconFunction.call(window.Icons, size, "currentColor");
      }
    }
    return "";
  }

  /**
   * Render folders list with tree structure
   */
  renderFolders() {
    const list = document.getElementById("folder-picker-list");
    if (!list) return;

    // Always add root option (null parent) at the top
    // Use vaultspace name and icon if available
    const vaultspaceName = this.vaultspaceInfo?.name || "Root";
    const vaultspaceIcon = this.vaultspaceInfo?.icon_name || "folder";
    const rootOption = `
      <button class="folder-picker-option folder-picker-root folder-picker-depth-0 ${this.selectedFolderId === null ? "selected" : ""}" 
              data-folder-id="root"
              data-depth="0">
        <span class="folder-expand-placeholder"></span>
        <span class="folder-icon folder-picker-vaultspace-icon">${this.getIcon(vaultspaceIcon, 20)}</span>
        <span class="folder-name">${this.escapeHtml(vaultspaceName)}</span>
      </button>
    `;

    // Check if there are any folders in the tree
    if (!this.folderTree || Object.keys(this.folderTree).length === 0) {
      // Only show root option if no folders
      setInnerHTML(list, rootOption);

      // Setup click handlers for root option
      list.querySelectorAll(".folder-picker-option").forEach((btn) => {
        const folderId = btn.dataset.folderId;
        btn.addEventListener("click", (e) => {
          const id = folderId === "root" ? null : folderId;
          list.querySelectorAll(".folder-picker-option").forEach((b) => {
            b.classList.remove("selected");
          });
          btn.classList.add("selected");
          this.selectedFolderId = id;
          const confirmBtn = document.getElementById("folder-picker-confirm");
          if (confirmBtn) {
            confirmBtn.disabled = false;
          }
        });
      });
      return;
    }

    // Generate visible list from tree
    const visibleFolders = this.generateVisibleList(
      this.folderTree,
      this.expandedFolders,
    );

    const foldersHTML =
      rootOption +
      visibleFolders
        .map((folder) => {
          const isSelected = this.selectedFolderId === folder.id;
          const folderIcon = this.getIcon("folder", 20);
          const chevronIcon = folder.hasChildren
            ? this.getIcon(
                this.isFolderExpanded(folder.id)
                  ? "chevronDown"
                  : "chevronRight",
                14,
              )
            : "";

          // Use depth class, limit to 20 for predefined classes
          const depth = Math.min(folder.depth, 20);
          const depthClass = `folder-picker-depth-${depth}`;
          return `
            <button class="folder-picker-option ${depthClass} ${isSelected ? "selected" : ""} ${folder.hasChildren ? "folder-clickable" : ""}" 
                    data-folder-id="${folder.id}"
                    data-has-children="${folder.hasChildren}"
                    data-depth="${folder.depth}">
              ${folder.hasChildren ? `<span class="folder-expand-icon">${chevronIcon}</span>` : '<span class="folder-expand-placeholder"></span>'}
              <span class="folder-icon">${folderIcon}</span>
              <span class="folder-name">${this.escapeHtml(folder.name)}</span>
            </button>
          `;
        })
        .join("");

    setInnerHTML(list, foldersHTML);

    // Add click handlers
    list.querySelectorAll(".folder-picker-option").forEach((btn) => {
      const folderId = btn.dataset.folderId;
      const hasChildren = btn.dataset.hasChildren === "true";

      // Add click handler for chevron (expand/collapse)
      if (hasChildren) {
        const expandIcon = btn.querySelector(".folder-expand-icon");
        if (expandIcon) {
          expandIcon.addEventListener("click", (e) => {
            e.stopPropagation();
            const id = folderId === "root" ? null : folderId;
            if (id !== null) {
              this.toggleFolder(id);
            }
          });
        }
      }

      // Add click handler for folder selection
      btn.addEventListener("click", (e) => {
        // Don't select if clicking on expand icon
        if (e.target.closest(".folder-expand-icon")) {
          return;
        }

        // Select folder
        const id = folderId === "root" ? null : folderId;

        // Update selection
        list.querySelectorAll(".folder-picker-option").forEach((b) => {
          b.classList.remove("selected");
        });
        btn.classList.add("selected");
        this.selectedFolderId = id;

        // Enable confirm button
        const confirmBtn = document.getElementById("folder-picker-confirm");
        if (confirmBtn) {
          confirmBtn.disabled = false;
        }
      });
    });
  }

  /**
   * Hide modal
   */
  hide() {
    if (this.modal) {
      this.modal.classList.add("hidden");
      setTimeout(() => {
        if (this.modal && this.modal.parentNode) {
          this.modal.remove();
        }
      }, 300);
    }
  }

  /**
   * Escape HTML
   */
  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
}

// Export singleton instance
export const folderPicker = new FolderPicker();

// Make available globally for non-module scripts
if (typeof window !== "undefined") {
  window.folderPicker = folderPicker;
}
