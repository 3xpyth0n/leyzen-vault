<template>
  <Teleport v-if="show" to="body">
    <div class="file-properties-overlay" @click="close">
      <div class="file-properties-modal" @click.stop>
        <div class="file-properties-header">
          <h2>File Properties</h2>
          <button @click="close" class="btn-icon">✕</button>
        </div>

        <div class="modal-content-scrollable" v-if="loading">
          <div class="loading">Loading properties...</div>
        </div>

        <div class="modal-content-scrollable" v-else-if="error">
          <div class="error-message">{{ error }}</div>
        </div>

        <div class="modal-content-scrollable" v-else-if="file">
          <div class="properties-section">
            <h3>General</h3>
            <div class="property-row">
              <span class="property-label">Name:</span>
              <span class="property-value">{{ file.original_name }}</span>
            </div>
            <div class="property-row">
              <span class="property-label">Type:</span>
              <span class="property-value">{{ getFileType(file) }}</span>
            </div>
            <div class="property-row">
              <span class="property-label">Size:</span>
              <span class="property-value">{{
                formatSize(file.total_size || file.size)
              }}</span>
            </div>
            <div
              class="property-row"
              v-if="file.mime_type !== 'application/x-directory'"
            >
              <span class="property-label">Encrypted Size:</span>
              <span class="property-value">{{
                formatSize(file.encrypted_size)
              }}</span>
            </div>
            <div class="property-row">
              <span class="property-label">Location:</span>
              <div
                class="property-value breadcrumb-path"
                ref="breadcrumbContainer"
              >
                <template
                  v-for="(item, index) in breadcrumbPath"
                  :key="item.id || 'root'"
                >
                  <span v-if="index > 0" class="breadcrumb-separator">/</span>
                  <button
                    class="breadcrumb-link"
                    @click="handleBreadcrumbClick(item)"
                    :title="item.name"
                  >
                    {{ item.name }}
                  </button>
                </template>
              </div>
            </div>
          </div>

          <div class="properties-section">
            <h3>Dates</h3>
            <div class="property-row">
              <span class="property-label">Created:</span>
              <span class="property-value">{{
                formatDateTime(file.created_at)
              }}</span>
            </div>
            <div class="property-row">
              <span class="property-label">Modified:</span>
              <span class="property-value">{{
                formatDateTime(file.updated_at)
              }}</span>
            </div>
          </div>

          <div class="properties-section" v-if="permissions">
            <h3>Permissions</h3>
            <div class="property-row">
              <span class="property-label">Owner:</span>
              <span class="property-value">{{
                permissions.owner || "Unknown"
              }}</span>
            </div>
            <div
              class="property-row"
              v-if="permissions.sharedWith && permissions.sharedWith.length > 0"
            >
              <span class="property-label">Shared With:</span>
              <span class="property-value"
                >{{ permissions.sharedWith.length }} user(s)</span
              >
            </div>
            <div class="property-row" v-if="permissions.permissions">
              <span class="property-label">Your Permissions:</span>
              <span class="property-value">{{
                permissions.permissions.join(", ")
              }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script>
import { ref, watch, nextTick } from "vue";
import { useRouter, useRoute } from "vue-router";
import { files, vaultspaces } from "../services/api";
import { normalizeMimeType } from "../utils/mimeType";

export default {
  name: "FileProperties",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    fileId: {
      type: String,
      default: null,
    },
    vaultspaceId: {
      type: String,
      required: true,
    },
  },
  emits: ["close", "navigate"],
  setup(props, { emit }) {
    const router = useRouter();
    const route = useRoute();
    const loading = ref(false);
    const error = ref(null);
    const file = ref(null);
    const permissions = ref(null);
    const breadcrumbPath = ref([]);
    const breadcrumbContainer = ref(null);
    const vaultspace = ref(null);

    const scrollToRight = () => {
      nextTick(() => {
        if (breadcrumbContainer.value) {
          breadcrumbContainer.value.scrollLeft =
            breadcrumbContainer.value.scrollWidth;
        }
      });
    };

    const fetchBreadcrumbs = async (targetFile) => {
      const path = [];
      let currentId = targetFile.id;
      let currentParentId = targetFile.parent_id;

      // Add the file itself as the last segment
      path.unshift({
        id: targetFile.id,
        name: targetFile.original_name || targetFile.name,
        parentId: targetFile.parent_id,
        isRoot: false,
        isFile: true,
      });

      // Traverse up to find all parent folders
      let depth = 0;
      const maxDepth = 50;
      while (currentParentId && depth < maxDepth) {
        try {
          const parentData = await files.get(
            currentParentId,
            props.vaultspaceId,
          );
          if (parentData && parentData.file) {
            path.unshift({
              id: parentData.file.id,
              name: parentData.file.original_name || parentData.file.name,
              parentId: parentData.file.parent_id,
              isRoot: false,
              isFile: false,
            });
            currentParentId = parentData.file.parent_id;
          } else {
            break;
          }
        } catch (err) {
          break;
        }
        depth++;
      }

      // Add the VaultSpace root as the first segment
      if (!vaultspace.value) {
        try {
          vaultspace.value = await vaultspaces.get(props.vaultspaceId);
        } catch (err) {
          // Fallback if vaultspace loading fails
        }
      }

      path.unshift({
        id: null,
        name: vaultspace.value?.name || "Home",
        parentId: null,
        isRoot: true,
        isFile: false,
      });

      breadcrumbPath.value = path;
    };

    const handleBreadcrumbClick = (item) => {
      // Logic for navigation and selection:
      // 1. Root: navigate to root, no selection
      // 2. Folder: navigate to its PARENT and SELECT this folder
      // 3. File: navigate to its PARENT and SELECT this file

      emit("navigate", item);
      close();
    };

    const loadProperties = async () => {
      if (!props.fileId || !props.vaultspaceId) return;

      loading.value = true;
      error.value = null;

      try {
        // Load file details
        const fileData = await files.get(props.fileId, props.vaultspaceId);
        file.value = fileData.file;

        await fetchBreadcrumbs(file.value);
        scrollToRight();

        // Load permissions (if available in fileData)
        if (fileData.permissions) {
          permissions.value = {
            permissions: fileData.permissions,
            owner: file.value.owner_user_id,
            sharedWith: [], // Would need separate API call
          };
        }
      } catch (err) {
        error.value = err.message || "Failed to load properties";
      } finally {
        loading.value = false;
      }
    };

    const close = () => {
      emit("close");
    };

    const formatSize = (bytes) => {
      if (!bytes) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    };

    const formatDateTime = (dateString) => {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleString();
    };

    const getFileType = (fileObj) => {
      if (fileObj.mime_type === "application/x-directory") {
        return "Folder";
      }

      const mimeType = normalizeMimeType(
        fileObj.original_name,
        fileObj.mime_type,
      );

      // Map of extensions to readable file types
      const extensionMap = {
        // Images
        png: "PNG Image",
        jpg: "JPEG Image",
        jpeg: "JPEG Image",
        gif: "GIF Image",
        webp: "WebP Image",
        svg: "SVG Image",
        bmp: "Bitmap Image",
        ico: "Icon",
        // Documents
        pdf: "PDF Document",
        doc: "Word Document",
        docx: "Word Document",
        xls: "Excel Spreadsheet",
        xlsx: "Excel Spreadsheet",
        ppt: "PowerPoint Presentation",
        pptx: "PowerPoint Presentation",
        odt: "OpenDocument Text",
        ods: "OpenDocument Spreadsheet",
        odp: "OpenDocument Presentation",
        // Text
        txt: "Text File",
        md: "Markdown File",
        rtf: "Rich Text Format",
        // Archives
        zip: "ZIP Archive",
        rar: "RAR Archive",
        "7z": "7-Zip Archive",
        tar: "TAR Archive",
        gz: "GZIP Archive",
        // Code
        js: "JavaScript File",
        ts: "TypeScript File",
        py: "Python File",
        java: "Java File",
        cpp: "C++ File",
        c: "C File",
        html: "HTML File",
        css: "CSS File",
        json: "JSON File",
        xml: "XML File",
        // Audio
        mp3: "MP3 Audio",
        wav: "WAV Audio",
        flac: "FLAC Audio",
        ogg: "OGG Audio",
        m4a: "M4A Audio",
        // Video
        mp4: "MP4 Video",
        avi: "AVI Video",
        mkv: "MKV Video",
        mov: "QuickTime Video",
        wmv: "WMV Video",
        // Other
        exe: "Executable",
        dmg: "Disk Image",
        iso: "ISO Image",
      };

      const isGenericMimeType =
        !mimeType ||
        mimeType === "application/octet-stream" ||
        mimeType === "application/x-unknown" ||
        mimeType === "binary/octet-stream";

      if (isGenericMimeType && fileObj.original_name) {
        const extension = fileObj.original_name.split(".").pop()?.toLowerCase();
        if (extension && extensionMap[extension]) {
          return extensionMap[extension];
        }

        if (extension) {
          return extension.toUpperCase() + " File";
        }
      }

      // Use mimeType if available and not generic
      if (mimeType && !isGenericMimeType) {
        const parts = mimeType.split("/");
        const subtype = parts[parts.length - 1];

        // Improve display for certain common types
        const mimeTypeMap = {
          "octet-stream": "Binary File",
          "x-directory": "Folder",
          pdf: "PDF Document",
          msword: "Word Document",
          "vnd.openxmlformats-officedocument.wordprocessingml.document":
            "Word Document",
          "vnd.ms-excel": "Excel Spreadsheet",
          "vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            "Excel Spreadsheet",
          "vnd.ms-powerpoint": "PowerPoint Presentation",
          "vnd.openxmlformats-officedocument.presentationml.presentation":
            "PowerPoint Presentation",
          zip: "ZIP Archive",
          "x-rar-compressed": "RAR Archive",
          "x-7z-compressed": "7-Zip Archive",
          "x-tar": "TAR Archive",
          gzip: "GZIP Archive",
        };

        if (mimeTypeMap[subtype]) {
          return mimeTypeMap[subtype];
        }

        const readableType = subtype.includes(".")
          ? subtype.split(".").pop()
          : subtype;
        return readableType
          .replace(/-/g, " ")
          .replace(/\b\w/g, (l) => l.toUpperCase());
      }

      return "Unknown";
    };

    const getLocation = () => {
      // Would need to build path from breadcrumbs
      return props.vaultspaceId; // Simplified
    };

    // Watch for file changes
    watch(
      () => [props.show, props.fileId],
      ([newShow, newFileId]) => {
        if (newShow && newFileId) {
          loadProperties();
        }
      },
      { immediate: true },
    );

    return {
      loading,
      error,
      file,
      permissions,
      loadProperties,
      close,
      formatSize,
      formatDateTime,
      getFileType,
      breadcrumbPath,
      breadcrumbContainer,
      handleBreadcrumbClick,
    };
  },
};
</script>

<style scoped>
.file-properties-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100000;
  padding: 2rem;
  will-change: opacity;
  transform: translateZ(0);
}

.file-properties-modal {
  width: 100%;
  max-width: 600px;
  max-height: calc(90vh - 2rem);
  display: flex;
  flex-direction: column;
  background: var(--bg-modal);
  border: 1px solid var(--ash-grey);

  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  box-sizing: border-box;
  isolation: isolate;
}

.file-properties-modal .file-properties-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  flex-shrink: 0;
}

.file-properties-modal .file-properties-header h2 {
  margin: 0;
  padding: 0;
  font-size: 1.25rem;
  color: var(--text-primary, #a9b7aa);
  font-weight: 600;
}

.modal-content-scrollable {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 1.5rem;
  min-height: 0;
  /* Optimizations for smooth scrolling */
  -webkit-overflow-scrolling: touch;
  /* Force GPU for smoother scrolling - creates a new composition layer */
  transform: translateZ(0);
  -webkit-transform: translateZ(0);
  /* Prevent overlay issues */
  position: relative;
  z-index: 0;
}

.properties-section {
  margin-bottom: 2rem;
  width: 100%;
}

.properties-section:last-child {
  margin-bottom: 0;
}

.properties-section h3 {
  margin: 0 0 1rem 0;
  font-size: 1.1rem;
  color: var(--text-primary, #a9b7aa);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 0.5rem;
  font-weight: 600;
  /* Prevent overlap */
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.property-row {
  display: flex;
  flex-direction: row;
  gap: 1rem;
  padding: 0.875rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  align-items: flex-start;
}

.property-label {
  font-weight: 600;
  color: var(--text-secondary, #a9b7aa);
  white-space: nowrap;
  flex-shrink: 0;
  width: 140px;
  padding-right: 0.5rem;
}

.property-value {
  color: var(--text-primary, #a9b7aa);
  text-align: right;
  word-break: break-word;
  overflow-wrap: break-word;
  flex: 1;
  min-width: 0;
  line-height: 1.5;
  margin-left: auto;
}

.breadcrumb-path {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.25rem;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 8px;
  scrollbar-width: thin;
  scrollbar-color: var(--accent) transparent;
}

.breadcrumb-path::before {
  content: "";
  margin-left: auto;
}

.breadcrumb-path::-webkit-scrollbar {
  height: 1px;
}

.breadcrumb-path::-webkit-scrollbar-track {
  background: transparent;
}

.breadcrumb-path::-webkit-scrollbar-thumb {
  background: var(--accent);
}

.breadcrumb-link {
  background: none;
  border: none;
  padding: 0;
  margin: 0;
  color: var(--primary, #3b82f6);
  cursor: pointer;
  font-size: inherit;
  font-family: inherit;
  text-decoration: none;
  white-space: nowrap;
  flex-shrink: 0;
}

.breadcrumb-link:hover {
  text-decoration: underline;
  color: var(--primary-hover, #2563eb);
}

.breadcrumb-separator {
  color: var(--text-secondary, #a9b7aa);
  opacity: 0.5;
  font-size: 0.8rem;
  flex-shrink: 0;
}

.loading,
.error-message {
  padding: 2rem;
  text-align: center;
}

.error-message {
  color: var(--error, #ef4444);
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #a9b7aa);
  font-size: 1.5rem;
  padding: 0.5rem;
  line-height: 1;
}

.btn-icon:hover {
  color: var(--text-primary, #a9b7aa);
}
</style>
