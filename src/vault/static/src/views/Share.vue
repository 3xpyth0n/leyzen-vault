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
            <span v-if="shareInfo.has_password" class="meta-item">
              <span class="meta-label">Protection:</span>
              <span class="meta-value">Password protected</span>
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

      <!-- Password Input (if password protected) -->
      <div
        v-if="shareInfo?.has_password && isAvailable"
        class="password-section glass"
      >
        <label for="share-password-input" class="password-label">
          <span class="password-icon" v-html="getIcon('lock', 16)"></span>
          This share link is password protected
        </label>
        <div class="password-input-wrapper">
          <input
            id="share-password-input"
            v-model="sharePassword"
            :type="showPassword ? 'text' : 'password'"
            class="password-input"
            placeholder="Enter password"
            @keyup.enter="downloadFile"
          />
          <button
            type="button"
            class="password-toggle"
            :class="{ 'is-visible': showPassword }"
            :aria-label="showPassword ? 'Hide password' : 'Show password'"
            @click="togglePassword"
          >
            <svg
              class="password-toggle-icon password-toggle-icon--hide"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <path
                d="M8 12.5c0 .5.5 1.5 4 1.5s4-1 4-1.5"
                stroke-linecap="round"
              ></path>
            </svg>
            <svg
              class="password-toggle-icon password-toggle-icon--show"
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </button>
        </div>
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
const sharePassword = ref("");
const showPassword = ref(false);
const downloadLoading = ref(false);
const downloadProgress = ref(null);
const downloadSpeed = ref(0);
const downloadTimeRemaining = ref(null);
const downloadStatus = ref("");

const togglePassword = () => {
  showPassword.value = !showPassword.value;
};

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
    // First try without password to check if password is required
    const response = await fetch(`/api/v2/sharing/public-links/${token}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      if (response.status === 403 && errorData.error === "Invalid password") {
        // Password required but not provided or incorrect
        // The share link exists but requires password
        // We need to get the share link info to show password field
        // Use the verify endpoint which doesn't require password to check if link exists
        try {
          const verifyResponse = await fetch(
            `/api/v2/sharing/public-links/${token}/verify`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({}),
            },
          );
          if (verifyResponse.ok) {
            const verifyData = await verifyResponse.json();
            if (verifyData.share_link?.has_password) {
              shareInfo.value = {
                has_password: true,
                error: "Password required",
                filename: verifyData.share_link.resource_id,
              };
              error.value = "";
              loading.value = false;
              return;
            }
          }
        } catch (verifyErr) {
          logger.debug("Failed to verify share link:", verifyErr);
        }
        error.value = "Password required";
      } else {
        error.value = errorData.error || "Failed to load share information";
      }
      loading.value = false;
      return;
    }
    const data = await response.json();
    // API v2 returns data in legacy format for compatibility
    // Store shareInfo even if invalid/expired to show status
    // Check if has_password is in share_link or directly in data
    if (data.share_link && data.share_link.has_password !== undefined) {
      data.has_password = data.share_link.has_password;
    }
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

  // Check if password is required
  if (shareInfo.value?.has_password && !sharePassword.value) {
    error.value = "Password is required to download this file";
    return;
  }

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
              const errorMsg = errorData.error || "Access denied";
              if (
                errorMsg === "Invalid password" ||
                errorMsg.includes("password")
              ) {
                reject(
                  new Error(
                    "Invalid password. Please check your password and try again.",
                  ),
                );
              } else {
                reject(new Error(errorMsg));
              }
            } else {
              reject(new Error(errorData.error || "Failed to download file"));
            }
          } catch (e) {
            if (xhr.status === 404) {
              reject(new Error("File not found"));
            } else if (xhr.status === 403) {
              reject(
                new Error("Access denied. Invalid password or link expired."),
              );
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
      // Include password in query parameter if provided
      let url = `/api/v2/sharing/public-links/${token}/download`;
      if (shareInfo.value?.has_password && sharePassword.value) {
        url += `?password=${encodeURIComponent(sharePassword.value)}`;
      }
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

.password-section {
  padding: 1.5rem;
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.password-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-primary, #f1f5f9);
  font-size: 0.9rem;
  font-weight: 500;
  margin: 0;
}

.password-icon {
  display: inline-flex;
  align-items: center;
  color: var(--accent-blue, #38bdf8);
}

.password-input-wrapper {
  position: relative;
  display: block;
  width: 100%;
}

.password-input {
  width: 100%;
  padding: 0.75rem 2.5rem 0.75rem 1rem;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 0.5rem;
  color: var(--text-primary, #f1f5f9);
  font-size: 1rem;
  transition: all 0.2s ease;
}

.password-input:focus {
  outline: none;
  border-color: var(--accent-blue, #38bdf8);
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1);
}

.password-input::placeholder {
  color: var(--text-muted, #94a3b8);
}

.password-toggle {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  margin-top: -12px;
  background: transparent;
  border: none;
  color: var(--text-muted, #94a3b8);
  opacity: 0.7;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  transition:
    opacity 0.2s ease,
    color 0.2s ease;
  z-index: 1;
  box-sizing: border-box;
  line-height: 1;
  vertical-align: baseline;
}

.password-toggle:hover {
  opacity: 1;
  color: var(--text-primary, #f1f5f9);
  margin-top: -12px;
}

.password-toggle:active {
  opacity: 0.8;
  margin-top: -12px;
}

.password-toggle:focus {
  outline: none;
  margin-top: -12px;
}

.password-toggle-icon {
  display: block;
  width: 1.125rem;
  height: 1.125rem;
}

.password-toggle-icon--show {
  display: none;
}

.password-toggle.is-visible .password-toggle-icon--hide {
  display: none;
}

.password-toggle.is-visible .password-toggle-icon--show {
  display: block;
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
