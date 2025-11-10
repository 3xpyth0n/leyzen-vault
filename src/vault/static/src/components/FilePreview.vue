<template>
  <div v-if="show" class="file-preview-overlay" @click="close">
    <div class="file-preview-modal glass glass-card" @click.stop>
      <div class="preview-header">
        <h2>{{ fileName }}</h2>
        <div class="preview-actions">
          <button @click="download" class="btn btn-secondary">Download</button>
          <button @click="close" class="btn-icon">✕</button>
        </div>
      </div>

      <div class="preview-content" v-if="loading">
        <div class="loading">Loading preview...</div>
      </div>

      <div class="preview-content" v-else-if="error">
        <div class="error-message glass">{{ error }}</div>
      </div>

      <div class="preview-content" v-else>
        <!-- Image Preview -->
        <div v-if="isImage" class="image-preview">
          <img :src="previewUrl" :alt="fileName" @load="onImageLoad" />
          <div v-if="imageLoading" class="loading-overlay">Loading...</div>
        </div>

        <!-- PDF Preview -->
        <div v-else-if="isPdf" class="pdf-preview">
          <iframe :src="previewUrl" class="pdf-iframe"></iframe>
        </div>

        <!-- Video Preview -->
        <div v-else-if="isVideo" class="video-preview">
          <video :src="previewUrl" controls class="video-player">
            Your browser does not support video playback.
          </video>
        </div>

        <!-- Audio Preview -->
        <div v-else-if="isAudio" class="audio-preview">
          <div class="audio-info">
            <h3>{{ fileName }}</h3>
            <audio :src="previewUrl" controls class="audio-player">
              Your browser does not support audio playback.
            </audio>
          </div>
        </div>

        <!-- Text Preview -->
        <div v-else-if="isText" class="text-preview">
          <pre class="text-content">{{ textContent }}</pre>
        </div>

        <!-- Unsupported Type -->
        <div v-else class="unsupported-preview">
          <p>Preview not available for this file type.</p>
          <p class="mime-type">{{ mimeType }}</p>
          <button @click="download" class="btn btn-primary">
            Download File
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch } from "vue";
import { files } from "../services/api";
import {
  getUserMasterKey,
  getCachedVaultSpaceKey,
  decryptVaultSpaceKeyForUser,
} from "../services/keyManager";
import { decryptFile } from "../services/encryption";

export default {
  name: "FilePreview",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    fileId: {
      type: String,
      default: null,
    },
    fileName: {
      type: String,
      default: "",
    },
    mimeType: {
      type: String,
      default: "",
    },
    vaultspaceId: {
      type: String,
      required: true,
    },
  },
  emits: ["close", "download"],
  setup(props, { emit }) {
    const loading = ref(false);
    const error = ref(null);
    const previewUrl = ref(null);
    const textContent = ref("");
    const imageLoading = ref(false);

    const isImage = computed(() => {
      return props.mimeType && props.mimeType.startsWith("image/");
    });

    const isPdf = computed(() => {
      return props.mimeType === "application/pdf";
    });

    const isVideo = computed(() => {
      return props.mimeType && props.mimeType.startsWith("video/");
    });

    const isAudio = computed(() => {
      return props.mimeType && props.mimeType.startsWith("audio/");
    });

    const isText = computed(() => {
      return (
        props.mimeType &&
        (props.mimeType.startsWith("text/") ||
          props.mimeType === "application/json" ||
          props.mimeType === "application/xml" ||
          props.mimeType.includes("javascript") ||
          props.mimeType.includes("css") ||
          props.mimeType.includes("html"))
      );
    });

    const loadPreview = async () => {
      if (!props.fileId || !props.vaultspaceId) return;

      loading.value = true;
      error.value = null;
      previewUrl.value = null;
      textContent.value = "";

      try {
        // Get VaultSpace key
        const vaultspaceKey = getCachedVaultSpaceKey(props.vaultspaceId);
        if (!vaultspaceKey) {
          throw new Error("VaultSpace key not loaded");
        }

        // Download encrypted file
        const encryptedData = await files.download(
          props.fileId,
          props.vaultspaceId,
        );

        // Get file key from server
        const fileData = await files.get(props.fileId, props.vaultspaceId);
        if (!fileData.file_key) {
          throw new Error("File key not found");
        }

        // Decrypt file key with VaultSpace key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileData.file_key.encrypted_key,
        );

        // Decrypt file data
        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Create preview based on file type
        if (isImage.value || isVideo.value || isAudio.value) {
          // Create blob URL for media files
          const blob = new Blob([decryptedData], { type: props.mimeType });
          previewUrl.value = URL.createObjectURL(blob);
        } else if (isPdf.value) {
          // For PDFs, create blob URL
          const blob = new Blob([decryptedData], { type: "application/pdf" });
          previewUrl.value = URL.createObjectURL(blob);
        } else if (isText.value) {
          // For text files, decode and display
          const decoder = new TextDecoder("utf-8");
          textContent.value = decoder.decode(decryptedData);
        }
      } catch (err) {
        console.error("Preview error:", err);
        error.value = err.message || "Failed to load preview";
      } finally {
        loading.value = false;
      }
    };

    const close = () => {
      // Clean up blob URLs
      if (previewUrl.value) {
        URL.revokeObjectURL(previewUrl.value);
        previewUrl.value = null;
      }
      emit("close");
    };

    const download = () => {
      emit("download", props.fileId);
    };

    const onImageLoad = () => {
      imageLoading.value = false;
    };

    // Watch for file changes
    watch(
      () => [props.show, props.fileId],
      ([newShow, newFileId]) => {
        if (newShow && newFileId) {
          loadPreview();
        } else if (!newShow) {
          // Clean up when closing
          if (previewUrl.value) {
            URL.revokeObjectURL(previewUrl.value);
            previewUrl.value = null;
          }
        }
      },
      { immediate: true },
    );

    return {
      loading,
      error,
      previewUrl,
      textContent,
      imageLoading,
      isImage,
      isPdf,
      isVideo,
      isAudio,
      isText,
      loadPreview,
      close,
      download,
      onImageLoad,
    };
  },
};
</script>

<style scoped>
.file-preview-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 2rem;
}

.file-preview-modal {
  width: 100%;
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
}

.preview-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--text-primary, #f1f5f9);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.preview-content {
  flex: 1;
  overflow: auto;
  padding: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.image-preview {
  position: relative;
  max-width: 100%;
  max-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-preview img {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: var(--radius-md, 8px);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
  color: white;
}

.pdf-preview {
  width: 100%;
  height: 70vh;
}

.pdf-iframe {
  width: 100%;
  height: 100%;
  border: none;
  border-radius: var(--radius-md, 8px);
}

.video-preview {
  width: 100%;
  max-width: 800px;
}

.video-player {
  width: 100%;
  max-height: 70vh;
  border-radius: var(--radius-md, 8px);
}

.audio-preview {
  width: 100%;
  max-width: 600px;
}

.audio-info {
  text-align: center;
}

.audio-info h3 {
  margin: 0 0 1.5rem 0;
  color: var(--text-primary, #f1f5f9);
}

.audio-player {
  width: 100%;
}

.text-preview {
  width: 100%;
  max-width: 900px;
  max-height: 70vh;
  overflow: auto;
}

.text-content {
  margin: 0;
  padding: 1rem;
  background: var(--bg-secondary, #141b2d);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #f1f5f9);
  font-family: "Courier New", monospace;
  font-size: 0.9rem;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.unsupported-preview {
  text-align: center;
  padding: 3rem;
}

.unsupported-preview p {
  margin: 0.5rem 0;
  color: var(--text-secondary, #cbd5e1);
}

.mime-type {
  font-family: monospace;
  font-size: 0.9rem;
  color: var(--text-muted, #94a3b8);
}

.loading {
  padding: 2rem;
  text-align: center;
  color: var(--text-secondary, #cbd5e1);
}

.error-message {
  padding: 1.5rem;
  text-align: center;
  color: var(--error, #ef4444);
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: var(--radius-md, 8px);
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary, #cbd5e1);
  font-size: 1.5rem;
  padding: 0.5rem;
  line-height: 1;
}

.btn-icon:hover {
  color: var(--text-primary, #f1f5f9);
}
</style>
