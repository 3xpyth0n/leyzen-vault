/** @file context-menu.js - Context menu for files and folders */

class ContextMenu {
  constructor() {
    this.menu = null;
    this.currentTarget = null;
  }

  init() {
    // Create context menu element
    if (!document.getElementById("context-menu")) {
      const menu = document.createElement("div");
      menu.id = "context-menu";
      menu.className = "context-menu hidden";
      document.body.appendChild(menu);
      this.menu = menu;
    } else {
      this.menu = document.getElementById("context-menu");
    }

    document.addEventListener("click", (e) => {
      if (
        !this.menu.contains(e.target) &&
        !e.target.closest("[data-context-target]")
      ) {
        this.hide();
      }
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !this.menu.classList.contains("hidden")) {
        this.hide();
      }
    });
  }

  show(event, target, type) {
    event.preventDefault();
    event.stopPropagation();

    this.currentTarget = target;
    const menuItems = this.getMenuItems(type);

    if (!this.menu) {
      this.init();
    }

    const menuHTML = menuItems
      .map((item) => {
        if (item === "divider") {
          return '<div class="context-menu-divider"></div>';
        }
        const icon = item.icon || "";
        const disabled = item.disabled ? "disabled" : "";
        return `
                <button class="context-menu-item ${disabled}" data-action="${item.action}" ${disabled}>
                    <span class="context-menu-icon">${icon}</span>
                    <span class="context-menu-label">${item.label}</span>
                </button>
            `;
      })
      .join("");

    // Use setInnerHTML if available
    if (window.vaultHTMLPolicy) {
      try {
        this.menu.innerHTML = window.vaultHTMLPolicy.createHTML(menuHTML);
      } catch (e) {
        this.menu.innerHTML = menuHTML;
      }
    } else {
      this.menu.innerHTML = menuHTML;
    }

    // Position menu
    const x = event.clientX;
    const y = event.clientY;
    this.menu.style.left = `${x}px`;
    this.menu.style.top = `${y}px`;

    this.menu.classList.remove("hidden");
    const rect = this.menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      this.menu.style.left = `${window.innerWidth - rect.width - 10}px`;
    }
    if (rect.bottom > window.innerHeight) {
      this.menu.style.top = `${window.innerHeight - rect.height - 10}px`;
    }

    // Attach event listeners
    this.menu.querySelectorAll(".context-menu-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const action = item.getAttribute("data-action");
        this.handleAction(action, target, type);
        this.hide();
      });
    });
  }

  hide() {
    if (this.menu) {
      this.menu.classList.add("hidden");
      this.currentTarget = null;
    }
  }

  getMenuItems(type) {
    if (type === "file") {
      return [
        {
          icon: window.Icons.eye(16, "currentColor"),
          label: "Preview",
          action: "preview",
        },
        { icon: "✏️", label: "Rename", action: "rename" },
        "divider",
        { icon: "⬇️", label: "Download", action: "download" },
        {
          icon: window.Icons.link(16, "currentColor"),
          label: "Share",
          action: "share",
        },
        {
          icon: window.Icons.clipboard(16, "currentColor"),
          label: "Properties",
          action: "properties",
        },
        "divider",
        {
          icon: window.Icons.trash(16, "currentColor"),
          label: "Delete",
          action: "delete",
          dangerous: true,
        },
      ];
    } else if (type === "folder") {
      return [
        {
          icon: window.Icons.folder(16, "currentColor"),
          label: "Open",
          action: "open",
        },
        "divider",
        { icon: "✏️", label: "Rename", action: "rename" },
        {
          icon: window.Icons.clipboard(16, "currentColor"),
          label: "Properties",
          action: "properties",
        },
        "divider",
        {
          icon: window.Icons.trash(16, "currentColor"),
          label: "Delete",
          action: "delete",
          dangerous: true,
        },
      ];
    }
    return [];
  }

  handleAction(action, target, type) {
    const id =
      target.getAttribute("data-file-id") ||
      target.getAttribute("data-folder-id");
    if (!id) return;

    switch (action) {
      case "download":
        if (type === "file" && window.downloadFile) {
          window.downloadFile(id);
        }
        break;
      case "preview":
        if (type === "file" && window.showFilePreview) {
          const file = window.filesList?.find((f) => f.file_id === id);
          if (file) {
            window.showFilePreview(id, file.original_name, file.mime_type);
          }
        }
        break;
      case "share":
        if (type === "file" && window.shareFile) {
          window.shareFile(id);
        }
        break;
      case "open":
        if (
          type === "folder" &&
          window.Folders &&
          window.Folders.navigateToFolder
        ) {
          window.Folders.navigateToFolder(id);
        }
        break;
      case "rename":
        this.handleRename(id, target, type);
        break;
      case "properties":
        this.handleProperties(id, target, type);
        break;
      case "delete":
        if (type === "file" && window.deleteFile) {
          window.deleteFile(id);
        } else if (
          type === "folder" &&
          window.Folders &&
          window.Folders.deleteFolder
        ) {
          window.Folders.deleteFolder(id);
        }
        break;
    }
  }

  /**
   * Handle rename action
   */
  async handleRename(id, target, type) {
    try {
      // Helper functions to extract extension and name without extension
      const getExtension = (filename) => {
        if (!filename) return null;
        const lastDot = filename.lastIndexOf(".");
        if (lastDot === -1 || lastDot === 0) return null;
        return filename.substring(lastDot);
      };

      const getNameWithoutExtension = (filename) => {
        if (!filename) return filename;
        const lastDot = filename.lastIndexOf(".");
        if (lastDot === -1 || lastDot === 0) return filename;
        return filename.substring(0, lastDot);
      };

      // Get current name
      let currentName = "";
      let fileExtension = null;
      const filesList = window.filesList || [];
      const foldersList = window.foldersList || [];

      if (type === "file") {
        const file =
          filesList.find((f) => f.id === id || f.file_id === id) ||
          filesList.find((f) => f.file_id === id);
        currentName = file?.original_name || file?.name || "";
        // Extract extension for files
        fileExtension = getExtension(currentName);
        currentName = getNameWithoutExtension(currentName);
      } else {
        const folder =
          foldersList.find((f) => f.id === id || f.folder_id === id) ||
          foldersList.find((f) => f.folder_id === id);
        currentName = folder?.original_name || folder?.name || "";
        // Folders don't have extensions
        fileExtension = null;
      }

      // Fallback: try to get from DOM
      if (!currentName) {
        const nameElement = target.querySelector(
          ".file-name, .folder-name, .file-row-name, .folder-row-name",
        );
        const fullName = nameElement?.textContent?.trim() || "";
        if (fullName && type === "file") {
          fileExtension = getExtension(fullName);
          currentName = getNameWithoutExtension(fullName);
        } else {
          currentName = fullName;
        }
      }

      if (!currentName) {
        currentName = type === "file" ? "Untitled" : "Untitled Folder";
      }

      // Prompt for new name (without extension for files)
      const newName = prompt(`Enter new name:`, currentName);
      if (!newName || newName.trim() === "" || newName === currentName) {
        return; // User cancelled or didn't change name
      }

      // Reattach extension for files before sending to API
      let finalName = newName.trim();
      if (type === "file" && fileExtension) {
        finalName = finalName + fileExtension;
      }

      // Load files API
      let files;
      try {
        const apiModule = await import(
          window.location.origin + "/static/src/services/api.js"
        );
        files = apiModule.files;
      } catch (e1) {
        try {
          const apiModule2 = await import("../src/services/api.js");
          files = apiModule2.files;
        } catch (e2) {
          if (window.Notifications) {
            window.Notifications.error(
              "Files API not available. Please refresh the page.",
            );
          } else {
            alert("Files API not available. Please refresh the page.");
          }
          return;
        }
      }

      // Rename file or folder
      await files.rename(id, finalName);

      if (window.Notifications) {
        window.Notifications.success(
          `${type === "file" ? "File" : "Folder"} renamed successfully`,
        );
      }

      // Reload files
      if (window.loadFiles) {
        await window.loadFiles();
      } else if (window.Folders && window.Folders.loadFolderContents) {
        const currentFolderId =
          (window.Folders &&
            typeof window.Folders.getCurrentFolderId === "function" &&
            window.Folders.getCurrentFolderId()) ||
          window.folderId ||
          null;
        await window.Folders.loadFolderContents(currentFolderId);
      } else {
        // Fallback: reload page
        window.location.reload();
      }
    } catch (error) {
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to rename: ${error.message || "Unknown error"}`,
        );
      } else {
        alert(`Failed to rename: ${error.message || "Unknown error"}`);
      }
    }
  }

  /**
   * Handle properties action
   */
  async handleProperties(id, target, type) {
    try {
      // Get vaultspace ID
      const vaultspaceId =
        target.getAttribute("data-vaultspace-id") ||
        window.currentVaultspaceId ||
        (() => {
          const match = window.location.pathname.match(/\/vaultspace\/([^/]+)/);
          return match
            ? match[1]
            : localStorage.getItem("current_vaultspace_id");
        })();

      let fileVaultspaceId = vaultspaceId;
      if (!fileVaultspaceId) {
        const filesList = window.filesList || [];
        const foldersList = window.foldersList || [];
        const file = filesList.find((f) => f.id === id || f.file_id === id);
        const folder = foldersList.find(
          (f) => f.id === id || f.folder_id === id,
        );
        fileVaultspaceId = file?.vaultspace_id || folder?.vaultspace_id || null;
      }

      if (!fileVaultspaceId) {
        if (window.Notifications) {
          window.Notifications.error(
            "Cannot show properties: VaultSpace ID not found",
          );
        } else {
          alert("Cannot show properties: VaultSpace ID not found");
        }
        return;
      }

      if (window.showFileProperties) {
        window.showFileProperties(id, fileVaultspaceId);
        return;
      }

      const propertiesEvent = new CustomEvent("showFileProperties", {
        detail: {
          fileId: id,
          vaultspaceId: fileVaultspaceId,
          type: type,
        },
      });
      document.dispatchEvent(propertiesEvent);

      // This is a fallback for Vue components that might be listening
      if (window.Notifications) {
        window.Notifications.info(
          "Properties modal should appear. If not, please use the file menu.",
        );
      }
    } catch (error) {
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to show properties: ${error.message || "Unknown error"}`,
        );
      } else {
        alert(`Failed to show properties: ${error.message || "Unknown error"}`);
      }
    }
  }
}

// Global context menu instance
let contextMenu = null;

function initContextMenu() {
  if (!contextMenu) {
    contextMenu = new ContextMenu();
    contextMenu.init();
  }
  return contextMenu;
}

document.addEventListener("DOMContentLoaded", () => {
  initContextMenu();

  // Attach context menu to files and folders
  document.addEventListener("contextmenu", (e) => {
    const fileCard = e.target.closest(".file-card, .file-row");
    const folderCard = e.target.closest(".folder-card, .folder-row");

    if (fileCard) {
      e.preventDefault();
      contextMenu.show(e, fileCard, "file");
    } else if (folderCard) {
      e.preventDefault();
      contextMenu.show(e, folderCard, "folder");
    }
  });
});

if (typeof window !== "undefined") {
  window.ContextMenu = ContextMenu;
  window.initContextMenu = initContextMenu;
}
