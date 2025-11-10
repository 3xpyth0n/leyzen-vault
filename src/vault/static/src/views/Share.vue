<template>
  <div class="share-page">
    <div v-if="loading" class="share-card glass glass-card">
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading share information...</p>
      </div>
    </div>
    <div v-else-if="shareInfo" class="share-card glass glass-card">
      <!-- Status Badge -->
      <div
        class="status-badge"
        :class="{
          'status-available': isAvailable,
          'status-expired': isExpired,
        }"
      >
        <span class="status-icon">{{ isAvailable ? "✓" : "✗" }}</span>
        <span class="status-text">{{
          isAvailable ? "Available" : "Expired"
        }}</span>
      </div>

      <!-- File Information -->
      <div class="file-header">
        <div class="file-icon">
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"
            ></path>
            <polyline points="13 2 13 9 20 9"></polyline>
          </svg>
        </div>
        <div class="file-title-section">
          <h1 class="file-name">{{ shareInfo.filename || "Unknown file" }}</h1>
          <div class="file-meta">
            <span v-if="shareInfo.size" class="meta-item">
              <span class="meta-label">Size:</span>
              <span class="meta-value">{{ formatSize(shareInfo.size) }}</span>
            </span>
            <span v-if="shareInfo.expires_at" class="meta-item">
              <span class="meta-label">Expires:</span>
              <span class="meta-value">{{
                formatDate(shareInfo.expires_at)
              }}</span>
            </span>
            <span v-if="shareInfo.max_downloads" class="meta-item">
              <span class="meta-label">Downloads remaining:</span>
              <span class="meta-value">{{
                shareInfo.max_downloads - shareInfo.download_count
              }}</span>
            </span>
          </div>
        </div>
      </div>

      <!-- Error Message (if expired/invalid) -->
      <div v-if="isExpired && shareInfo.error" class="error-message glass">
        <p>{{ shareInfo.error }}</p>
      </div>

      <!-- Error Message (for download errors) -->
      <div v-if="error && !isExpired" class="error-message glass">
        <p>{{ error }}</p>
      </div>

      <!-- Download Progress Bar -->
      <ProgressBar
        v-if="downloadProgress !== null && downloadProgress >= 0"
        :progress="downloadProgress"
        :speed="downloadSpeed"
        :time-remaining="downloadTimeRemaining"
        :file-name="shareInfo?.filename || ''"
        :status="downloadStatus"
      />

      <!-- Download Button -->
      <div class="action-section">
        <button
          @click="downloadFile"
          :disabled="downloadLoading || isExpired"
          class="download-btn btn btn-primary"
          :class="{ 'btn-disabled': isExpired }"
        >
          <span
            v-if="downloadLoading && downloadProgress === null"
            class="btn-content"
          >
            <span class="spinner-small"></span>
            <span>Downloading...</span>
          </span>
          <span v-else-if="isExpired" class="btn-content">
            <span>File Expired</span>
          </span>
          <span v-else class="btn-content">
            <span>Download File</span>
          </span>
        </button>
        <p v-if="isAvailable" class="security-note">
          <span class="security-icon" v-html="getIcon('lock', 16)"></span>
          This file is end-to-end encrypted and will be decrypted in your
          browser
        </p>
      </div>
    </div>
    <div v-else class="share-card glass glass-card">
      <div class="error-state">
        <div class="error-icon" v-html="getIcon('warning', 48)"></div>
        <h2>Error</h2>
        <p>{{ error || "Failed to load share information" }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { logger } from "../utils/logger.js";
import ProgressBar from "../components/ProgressBar.vue";
import {
  decryptFileLegacy,
  parseShareUrl,
  base64urlToArray,
} from "../services/encryption.js";

const route = useRoute();
const loading = ref(true);
const error = ref("");
const shareInfo = ref(null);
const downloadLoading = ref(false);
const downloadProgress = ref(null);
const downloadSpeed = ref(0);
const downloadTimeRemaining = ref(null);
const downloadStatus = ref("");

const formatSize = (bytes) => {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
};

const formatDate = (dateString) => {
  if (!dateString) return "";
  const date = new Date(dateString);
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const getIcon = (iconName, size = 24) => {
  if (!window.Icons || !window.Icons[iconName]) {
    return "";
  }
  return window.Icons[iconName](size, "currentColor");
};

const isExpired = computed(() => {
  if (!shareInfo.value) return false;

  // Check if explicitly marked as invalid
  if (shareInfo.value.is_valid === false) {
    return true;
  }

  // Check expiration date
  if (shareInfo.value.expires_at) {
    const expiresDate = new Date(shareInfo.value.expires_at);
    const now = new Date();
    if (expiresDate <= now) {
      return true;
    }
  }

  // Check max downloads
  if (shareInfo.value.max_downloads) {
    const remaining =
      shareInfo.value.max_downloads - (shareInfo.value.download_count || 0);
    if (remaining <= 0) {
      return true;
    }
  }

  return false;
});

const isAvailable = computed(() => {
  return shareInfo.value && !isExpired.value;
});

const loadShareInfo = async () => {
  const token = route.params.token;
  if (!token) {
    error.value = "Invalid share link";
    loading.value = false;
    return;
  }

  try {
    // Migrate to API v2 - use public-links endpoint
    const response = await fetch(`/api/v2/sharing/public-links/${token}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      error.value = errorData.error || "Failed to load share information";
      loading.value = false;
      return;
    }
    const data = await response.json();
    // API v2 returns data in legacy format for compatibility
    // Store shareInfo even if invalid/expired to show status
    shareInfo.value = data;

    // Track access to the share link (increment access count)
    try {
      await fetch(`/api/v2/sharing/public-links/${token}/access`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      // Silently handle errors - this is tracking-only, don't block UI
    } catch (accessErr) {
      logger.debug("Failed to track share link access:", accessErr);
    }
  } catch (err) {
    error.value = err.message || "Failed to load share information";
  } finally {
    loading.value = false;
  }
};

const downloadFile = async () => {
  const token = route.params.token;
  if (!token || !shareInfo.value) {
    error.value = "Missing share information. Please refresh the page.";
    return;
  }

  // Clear previous errors
  error.value = "";
  downloadLoading.value = true;

  // Get decryption key from URL fragment
  let key = null;
  try {
    // First try using parseShareUrl which looks for "file" and "key" in hash
    const parsed = parseShareUrl();

    if (parsed.fileId === shareInfo.value.file_id && parsed.key) {
      key = parsed.key;
    } else {
      // Fallback: try to get key directly from URL hash
      const hash = window.location.hash.substring(1);
      if (hash) {
        const params = new URLSearchParams(hash);
        const keyBase64url = params.get("key");
        const fileIdFromHash = params.get("file");

        // Verify file ID matches and key is present
        if (fileIdFromHash === shareInfo.value.file_id && keyBase64url) {
          try {
            key = base64urlToArray(keyBase64url);
          } catch (e) {
            logger.error("Failed to decode key:", e);
          }
        }
      }
    }
  } catch (err) {
    logger.error("Error parsing key from URL:", err);
  }

  if (!key) {
    error.value =
      "Decryption key missing from URL. Please use the complete share link with the key in the URL fragment (after #).";
    downloadLoading.value = false;
    return;
  }

  try {
    // Initialize download progress
    downloadProgress.value = 0;
    downloadSpeed.value = 0;
    downloadTimeRemaining.value = null;
    downloadStatus.value = "Downloading...";

    // Download encrypted file with progress tracking using XMLHttpRequest
    const encryptedDataArrayBuffer = await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.responseType = "arraybuffer";

      // Progress tracking
      let lastLoaded = 0;
      let lastTime = Date.now();
      const PROGRESS_MARGIN = 2.5; // Margin of 2-3 seconds for remaining time

      xhr.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const currentTime = Date.now();
          const timeDiff = (currentTime - lastTime) / 1000; // seconds
          const loadedDiff = e.loaded - lastLoaded; // bytes

          let speed = 0;
          let timeRemaining = null;

          if (timeDiff > 0 && loadedDiff > 0) {
            speed = loadedDiff / timeDiff; // bytes per second
            const remaining = e.total - e.loaded;
            const calculatedTime = remaining / speed;
            // Add the margin of 2-3 seconds
            timeRemaining = calculatedTime + PROGRESS_MARGIN;
          }

          if (e.total > 0) {
            downloadProgress.value = Math.round((e.loaded / e.total) * 100);
          }
          downloadSpeed.value = speed || 0;
          downloadTimeRemaining.value = timeRemaining;

          lastLoaded = e.loaded;
          lastTime = currentTime;
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(xhr.response);
        } else {
          try {
            const errorText = new TextDecoder().decode(xhr.response);
            const errorData = JSON.parse(errorText);
            if (xhr.status === 404) {
              reject(new Error("File not found"));
            } else if (xhr.status === 403) {
              reject(new Error(errorData.error || "Access denied"));
            } else {
              reject(new Error(errorData.error || "Failed to download file"));
            }
          } catch (e) {
            if (xhr.status === 404) {
              reject(new Error("File not found"));
            } else if (xhr.status === 403) {
              reject(new Error("Access denied"));
            } else {
              reject(new Error(`Download failed: ${xhr.status}`));
            }
          }
        }
      });

      xhr.addEventListener("error", () => {
        reject(new Error("Network error during download"));
      });

      xhr.addEventListener("abort", () => {
        reject(new Error("Download cancelled"));
      });

      // Migrate to API v2 - use public-links download endpoint
      const url = `/api/v2/sharing/public-links/${token}/download`;
      logger.debug(
        `Downloading file via share link: token=${token.substring(0, 20)}...`,
      );
      xhr.open("GET", url);
      xhr.send();
    });

    // Convert ArrayBuffer to Uint8Array
    const encryptedData = new Uint8Array(encryptedDataArrayBuffer);

    // Update status for decryption phase
    downloadProgress.value = 95;
    downloadSpeed.value = 0;
    downloadTimeRemaining.value = null;
    downloadStatus.value = "Decrypting...";

    // Decrypt the file client-side
    const decryptedBuffer = await decryptFileLegacy(encryptedData, key);

    // Update progress to complete
    downloadProgress.value = 100;
    downloadStatus.value = "Download complete";

    // Create download link for decrypted file
    const decryptedBlob = new Blob([decryptedBuffer]);
    const url = window.URL.createObjectURL(decryptedBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = shareInfo.value.filename || "file";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    // Wait a bit before removing to ensure download starts
    setTimeout(() => {
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    }, 100);

    // Hide progress after a short delay
    setTimeout(() => {
      downloadProgress.value = null;
      downloadSpeed.value = 0;
      downloadTimeRemaining.value = null;
      downloadStatus.value = "";
    }, 1000);
  } catch (err) {
    logger.error("Download error:", err);
    error.value = err.message || "Failed to download file";
    downloadProgress.value = null;
    downloadSpeed.value = 0;
    downloadTimeRemaining.value = null;
    downloadStatus.value = "";
  } finally {
    downloadLoading.value = false;
  }
};

onMounted(() => {
  loadShareInfo();
});
</script>

<style scoped>
.share-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: var(--bg-primary, #0a0e1a);
}

.share-card {
  width: 100%;
  max-width: 800px;
  max-height: 500px;
  padding: 3rem;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2rem;
  background: var(--bg-glass, rgba(30, 41, 59, 0.4));
  backdrop-filter: var(--blur, blur(16px));
  -webkit-backdrop-filter: var(--blur, blur(16px));
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.2));
  border-radius: 1.5rem;
  box-shadow:
    var(--shadow-lg, 0 10px 15px rgba(0, 0, 0, 0.1)),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.status-badge {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 1rem;
  font-size: 0.875rem;
  font-weight: 600;
  backdrop-filter: blur(10px);
}

.status-available {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-expired {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.status-icon {
  font-size: 1rem;
  font-weight: bold;
}

.status-text {
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem;
  text-align: center;
  min-height: 300px;
}

.loading-state p,
.error-state p {
  color: var(--text-secondary, #cbd5e1);
  font-size: 1rem;
}

.error-state h2 {
  color: var(--text-primary, #f1f5f9);
  margin: 0;
}

.error-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
  margin-bottom: 1rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(148, 163, 184, 0.2);
  border-top-color: var(--accent-blue, #38bdf8);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.file-header {
  display: flex;
  align-items: flex-start;
  gap: 1.5rem;
  flex: 1;
}

.file-icon {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.1);
  border-radius: 1rem;
  color: var(--accent-blue, #38bdf8);
  border: 1px solid rgba(56, 189, 248, 0.2);
}

.file-title-section {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary, #f1f5f9);
  margin: 0 0 1rem 0;
  word-break: break-word;
  line-height: 1.3;
}

.file-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.meta-label {
  color: var(--text-secondary, #cbd5e1);
}

.meta-value {
  color: var(--text-primary, #f1f5f9);
  font-weight: 500;
}

.error-message {
  padding: 1rem 1.5rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.75rem;
  color: #ef4444;
}

.error-message.glass {
  backdrop-filter: var(--blur, blur(16px));
  -webkit-backdrop-filter: var(--blur, blur(16px));
}

.error-message p {
  margin: 0;
  font-size: 0.9rem;
}

.action-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.download-btn {
  width: 100%;
  padding: 1rem 2rem;
  font-size: 1.125rem;
  font-weight: 600;
  border-radius: 0.75rem;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.download-btn.btn-disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.security-note {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  text-align: center;
  color: var(--text-muted, #94a3b8);
  font-size: 0.875rem;
  margin: 0;
}

.security-icon {
  display: inline-flex;
  align-items: center;
  color: currentColor;
}

@media (max-width: 768px) {
  .share-card {
    max-width: 100%;
    padding: 2rem;
    max-height: none;
  }

  .file-header {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .file-meta {
    justify-content: center;
  }

  .status-badge {
    position: static;
    align-self: flex-end;
    margin-bottom: 1rem;
  }
}
</style>
