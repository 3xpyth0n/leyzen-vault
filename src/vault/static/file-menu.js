/** @file file-menu.js - File menu with 3 dots (Google Drive style) */

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

class FileMenuManager {
  constructor() {
    this.activeMenu = null;
    this.menuContainer = null;
    this.init();
  }

  init() {
    // Create menu container
    this.menuContainer = document.createElement("div");
    this.menuContainer.id = "file-menu-container";
    this.menuContainer.className = "file-menu-container hidden";
    document.body.appendChild(this.menuContainer);

    // Close menu on outside click
    document.addEventListener("click", (e) => {
      if (
        this.activeMenu &&
        !this.menuContainer.contains(e.target) &&
        !e.target.closest(".file-menu-btn") &&
        !e.target.closest(".file-menu-dropdown")
      ) {
        this.hide();
      }
    });

    // Close menu on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.activeMenu) {
        this.hide();
      }
    });
  }

  show(fileId, fileType, event) {
    // Hide any existing menu
    this.hide();

    // Get file or folder data
    let resource = null;
    if (fileType === "file") {
      resource = window.filesList?.find((f) => f.file_id === fileId);
    } else if (fileType === "folder") {
      resource = window.foldersList?.find((f) => f.folder_id === fileId);
    }

    if (!resource) return;

    // Position menu near the button
    const button = event.target.closest(".file-menu-btn");
    if (!button) return;

    const rect = button.getBoundingClientRect();
    this.menuContainer.style.left = `${rect.left}px`;
    this.menuContainer.style.top = `${rect.bottom + 4}px`;

    // Create menu items based on resource type
    let menuItems = [];

    if (fileType === "file") {
      menuItems = [
        {
          icon: "eye",
          label: "Preview",
          action: () => {
            if (window.showFilePreview) {
              window.showFilePreview(
                resource.file_id,
                resource.original_name,
                resource.mime_type,
              );
            }
          },
        },
        {
          icon: "download",
          label: "Download",
          action: () => {
            window.location.href = `/api/files/${fileId}`;
          },
        },
        {
          icon: "link",
          label: "Share",
          action: () => {
            if (window.sharingManager) {
              window.sharingManager.showShareModal(fileId, "file");
            } else if (typeof shareFile === "function") {
              shareFile(fileId);
            }
          },
        },
        {
          icon: "copy",
          label: "Copy",
          action: () => {
            this.handleCopy(fileId, fileType, resource);
          },
        },
        {
          icon: "move",
          label: "Move",
          action: () => {
            this.handleMove(fileId, fileType, resource);
          },
        },
        {
          icon: "edit",
          label: "Rename",
          action: () => {
            alert("Rename functionality coming soon");
          },
        },
        {
          icon: "clipboard",
          label: "Properties",
          action: () => {
            alert("Properties functionality coming soon");
          },
        },
        {
          icon: "delete",
          label: "Delete",
          dangerous: true,
          action: () => {
            if (window.showConfirmationModal) {
              const warningIcon = window.Icons?.warning
                ? window.Icons.warning(20, "currentColor")
                : "⚠️";
              window.showConfirmationModal({
                icon: warningIcon,
                title: "Delete File",
                message: `Are you sure you want to delete "${resource.original_name}"? This action cannot be undone.`,
                confirmText: "Delete",
                dangerous: true,
                onConfirm: () => {
                  if (typeof deleteFile === "function") {
                    deleteFile(fileId);
                  }
                },
              });
            }
          },
        },
      ];
    } else if (fileType === "folder") {
      menuItems = [
        {
          icon: "folder",
          label: "Open",
          action: () => {
            if (window.Folders && window.Folders.navigateToFolder) {
              window.Folders.navigateToFolder(fileId);
            } else if (typeof navigateToFolder === "function") {
              navigateToFolder(fileId);
            }
          },
        },
        {
          icon: "link",
          label: "Share",
          action: () => {
            if (window.sharingManager) {
              window.sharingManager.showShareModal(fileId, "folder");
            }
          },
        },
        {
          icon: "copy",
          label: "Copy",
          action: () => {
            this.handleCopy(fileId, fileType, resource);
          },
        },
        {
          icon: "move",
          label: "Move",
          action: () => {
            this.handleMove(fileId, fileType, resource);
          },
        },
        {
          icon: "edit",
          label: "Rename",
          action: () => {
            alert("Rename functionality coming soon");
          },
        },
        {
          icon: "clipboard",
          label: "Properties",
          action: () => {
            alert("Properties functionality coming soon");
          },
        },
        {
          icon: "delete",
          label: "Delete",
          dangerous: true,
          action: () => {
            if (
              window.showConfirmationModal &&
              typeof deleteFolder === "function"
            ) {
              const warningIcon = window.Icons?.warning
                ? window.Icons.warning(20, "currentColor")
                : "⚠️";
              window.showConfirmationModal({
                icon: warningIcon,
                title: "Delete Folder",
                message:
                  "Are you sure you want to delete this folder? Files inside will be moved to the parent folder.",
                confirmText: "Delete",
                dangerous: true,
                onConfirm: () => {
                  deleteFolder(fileId);
                },
              });
            }
          },
        },
      ];
    }

    // Build menu HTML
    const menuHTML = menuItems
      .map((item) => {
        const iconHTML = window.Icons?.[item.icon]
          ? window.Icons[item.icon](16, "currentColor")
          : "";
        const dangerousClass = item.dangerous ? "dangerous" : "";
        return `
          <button class="file-menu-item ${dangerousClass}" data-action="${item.label.toLowerCase()}">
            <span class="file-menu-icon">${iconHTML}</span>
            <span class="file-menu-label">${item.label}</span>
          </button>
        `;
      })
      .join("");

    setInnerHTML(
      this.menuContainer,
      `<div class="file-menu-dropdown">${menuHTML}</div>`,
    );

    // Add event listeners
    menuItems.forEach((item, index) => {
      const menuItem =
        this.menuContainer.querySelectorAll(".file-menu-item")[index];
      if (menuItem) {
        menuItem.addEventListener("click", (e) => {
          e.stopPropagation();
          item.action();
          this.hide();
        });
      }
    });

    // Show menu
    this.menuContainer.classList.remove("hidden");
    this.activeMenu = { fileId, fileType };

    // Adjust position if menu goes off screen
    setTimeout(() => {
      const menuRect = this.menuContainer.getBoundingClientRect();
      if (menuRect.right > window.innerWidth) {
        this.menuContainer.style.left = `${rect.right - menuRect.width}px`;
      }
      if (menuRect.bottom > window.innerHeight) {
        this.menuContainer.style.top = `${rect.top - menuRect.height - 4}px`;
      }
    }, 0);
  }

  hide() {
    if (this.menuContainer) {
      this.menuContainer.classList.add("hidden");
      this.activeMenu = null;
    }
  }

  /**
   * Handle copy action
   */
  async handleCopy(fileId, fileType, resource) {
    this.hide();

    try {
      // Get current folders and vaultspace info
      const folders = window.foldersList || [];
      const currentFolderId = window.currentFolderId || null;
      const vaultspaceId =
        resource?.vaultspace_id || window.currentVaultspaceId;

      if (!vaultspaceId) {
        if (window.Notifications) {
          window.Notifications.error("Cannot copy: VaultSpace ID not found");
        }
        return;
      }

      // Get folder picker - try global first, then load dynamically
      let folderPicker = window.folderPicker;
      if (!folderPicker) {
        try {
          // Try loading from the utils directory
          const folderPickerModule = await import(
            window.location.origin + "/static/src/utils/FolderPicker.js"
          );
          folderPicker = folderPickerModule.folderPicker;
          window.folderPicker = folderPicker;
        } catch (e1) {
          try {
            // Alternative path
            const folderPickerModule2 = await import(
              "../src/utils/FolderPicker.js"
            );
            folderPicker = folderPickerModule2.folderPicker;
            window.folderPicker = folderPicker;
          } catch (e2) {
            console.error("Failed to load folder picker:", e1, e2);
            if (window.Notifications) {
              window.Notifications.error(
                "Folder picker not available. Please refresh the page.",
              );
            }
            return;
          }
        }
      }

      // Show folder picker
      const selectedFolderId = await folderPicker.show(
        folders,
        currentFolderId,
        vaultspaceId,
        fileType === "folder" ? fileId : null,
      );

      if (selectedFolderId === undefined) {
        // User cancelled
        return;
      }

      // Perform copy
      const csrfToken = document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");

      const response = await fetch(`/v2/files/${fileId}/copy`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
        },
        credentials: "same-origin",
        body: JSON.stringify({
          new_parent_id: selectedFolderId || null,
          new_vaultspace_id: null, // Keep in same vaultspace
          new_name: null, // Keep same name
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to copy");
      }

      if (window.Notifications) {
        window.Notifications.success(
          `${fileType === "file" ? "File" : "Folder"} copied successfully`,
        );
      }

      // Reload files
      if (window.loadFiles) {
        await window.loadFiles();
      } else if (window.Folders && window.Folders.loadFolderContents) {
        await window.Folders.loadFolderContents(currentFolderId);
      }
    } catch (error) {
      console.error("Copy error:", error);
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to copy: ${error.message || "Unknown error"}`,
        );
      }
    }
  }

  /**
   * Handle move action
   */
  async handleMove(fileId, fileType, resource) {
    this.hide();

    try {
      // Get current folders and vaultspace info
      const folders = window.foldersList || [];
      const currentFolderId = window.currentFolderId || null;
      const vaultspaceId =
        resource?.vaultspace_id || window.currentVaultspaceId;

      if (!vaultspaceId) {
        if (window.Notifications) {
          window.Notifications.error("Cannot move: VaultSpace ID not found");
        }
        return;
      }

      // Get folder picker - try global first, then load dynamically
      let folderPicker = window.folderPicker;
      if (!folderPicker) {
        try {
          const folderPickerModule = await import(
            window.location.origin + "/static/src/utils/FolderPicker.js"
          );
          folderPicker = folderPickerModule.folderPicker;
          window.folderPicker = folderPicker;
        } catch (e1) {
          try {
            const folderPickerModule2 = await import(
              "../src/utils/FolderPicker.js"
            );
            folderPicker = folderPickerModule2.folderPicker;
            window.folderPicker = folderPicker;
          } catch (e2) {
            console.error("Failed to load folder picker:", e1, e2);
            if (window.Notifications) {
              window.Notifications.error(
                "Folder picker not available. Please refresh the page.",
              );
            }
            return;
          }
        }
      }

      // Show folder picker
      const selectedFolderId = await folderPicker.show(
        folders,
        currentFolderId,
        vaultspaceId,
        fileType === "folder" ? fileId : null,
      );

      if (selectedFolderId === undefined) {
        // User cancelled
        return;
      }

      // Perform move
      const csrfToken = document
        .querySelector('meta[name="csrf-token"]')
        ?.getAttribute("content");

      let response;
      if (fileType === "file") {
        response = await fetch(`/api/files/${fileId}/move`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            ...(csrfToken ? { "X-CSRFToken": csrfToken } : {}),
          },
          credentials: "same-origin",
          body: JSON.stringify({
            parent_id: selectedFolderId || null,
          }),
        });
      } else {
        // Move folder
        // Migrate to API v2 - requires JWT authentication
        const jwtToken = localStorage.getItem("jwt_token");
        if (!jwtToken) {
          throw new Error("Authentication required");
        }

        response = await fetch(`/api/v2/files/${fileId}/move`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${jwtToken}`,
          },
          credentials: "same-origin",
          body: JSON.stringify({
            new_parent_id: selectedFolderId || null,
          }),
        });
      }

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to move");
      }

      if (window.Notifications) {
        window.Notifications.success(
          `${fileType === "file" ? "File" : "Folder"} moved successfully`,
        );
      }

      // Reload files
      if (window.loadFiles) {
        await window.loadFiles();
      } else if (window.Folders && window.Folders.loadFolderContents) {
        await window.Folders.loadFolderContents(currentFolderId);
      }
    } catch (error) {
      console.error("Move error:", error);
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to move: ${error.message || "Unknown error"}`,
        );
      }
    }
  }
}

// Initialize file menu manager
let fileMenuManager = null;

document.addEventListener("DOMContentLoaded", () => {
  fileMenuManager = new FileMenuManager();

  // Export for use in other scripts
  if (typeof window !== "undefined") {
    window.FileMenuManager = FileMenuManager;
    window.fileMenuManager = fileMenuManager;
  }
});

// Export for use in other scripts
if (typeof window !== "undefined") {
  window.FileMenuManager = FileMenuManager;
}
