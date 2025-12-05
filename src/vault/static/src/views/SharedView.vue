<template>
  <ConfirmationModal
    :show="showRevokeConfirm"
    title="Revoke Share Link"
    message="Are you sure you want to revoke this share link? This action cannot be undone."
    confirm-text="Revoke"
    :dangerous="true"
    @confirm="handleRevokeConfirm"
    @close="showRevokeConfirm = false"
  />
  <AlertModal
    :show="showAlertModal"
    :type="alertType"
    :title="alertTitle"
    :message="alertMessage"
    @close="showAlertModal = false"
    @ok="showAlertModal = false"
  />
  <teleport to="body">
    <div
      v-if="showEmailModal"
      class="modal-overlay"
      @click.self="closeEmailModal"
      role="dialog"
      aria-labelledby="email-modal-title"
      aria-modal="true"
    >
      <div class="modal-container email-modal" @click.stop>
        <div class="modal-content-email">
          <div class="modal-header">
            <h2 id="email-modal-title" class="modal-title">
              Send Share Link via Email
            </h2>
            <button class="modal-close" @click="closeEmailModal">
              &times;
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label for="recipient-email">Recipient Email</label>
              <input
                id="recipient-email"
                v-model="emailForm.recipientEmail"
                type="email"
                placeholder="recipient@example.com"
                class="form-input"
                :disabled="emailForm.loading"
                @keyup.enter="handleSendEmail"
              />
            </div>
            <div v-if="emailForm.error" class="form-error">
              {{ emailForm.error }}
            </div>
          </div>
          <div class="modal-footer">
            <button
              class="btn btn-secondary"
              @click="closeEmailModal"
              :disabled="emailForm.loading"
            >
              Cancel
            </button>
            <button
              class="btn btn-primary"
              @click="handleSendEmail"
              :disabled="emailForm.loading || !emailForm.recipientEmail"
            >
              <span v-if="emailForm.loading">Sending...</span>
              <span v-else>Send Email</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
  <div class="shared-view">
    <header class="view-header">
      <h1>Shared Files</h1>
      <p class="view-description">
        Files you have shared with others via download links
      </p>
    </header>

    <main class="view-main">
      <div v-if="loading" class="loading">Loading shared files...</div>
      <div v-else-if="error" class="error glass">{{ error }}</div>
      <div v-else-if="files.length === 0" class="empty-state glass">
        <p>No shared files yet</p>
        <p class="empty-hint">
          Share a file to generate a download link that others can use
        </p>
      </div>
      <div v-else class="shared-files-list">
        <div v-for="file in files" :key="file.id" class="shared-file-item">
          <div class="file-info">
            <div class="file-icon">
              <img
                v-if="
                  hasThumbnail(file) &&
                  (isImageFile(file) || isAudioFile(file)) &&
                  getThumbnailUrl(file.id)
                "
                :key="`thumb-${file.id}-${thumbnailUpdateTrigger}`"
                :src="getThumbnailUrl(file.id)"
                :alt="file.original_name"
                class="file-thumbnail"
                @error="
                  (event) => {
                    event.target.style.display = 'none';
                  }
                "
              />
              <span v-else v-html="getFileIcon(file)"></span>
            </div>
            <div class="file-details">
              <h3 class="file-name">{{ file.original_name }}</h3>
              <p class="file-meta">
                Size: {{ formatSize(file.size) }} • Created:
                {{ formatDate(file.created_at) }}
              </p>
            </div>
            <div class="file-actions">
              <button
                v-if="
                  file.share_links &&
                  file.share_links.length > 0 &&
                  hasAvailableLink(file.share_links)
                "
                @click="openSendEmailModalForFile(file)"
                class="btn btn-small btn-send-email"
                :title="'Send share link via email'"
              >
                Send Email
              </button>
            </div>
          </div>
          <div class="share-links-info">
            <div
              v-for="link in file.share_links || []"
              :key="link.link_id"
              class="share-link-card"
            >
              <div class="link-info">
                <div
                  v-if="hasDecryptionKey(link, file.id)"
                  :data-link-id="link.link_id"
                  class="link-url"
                >
                  {{ getShareUrlDisplay(link, file.id) }}
                </div>
                <div v-else class="link-warning">
                  <span class="warning-icon">⚠️</span>
                  <span class="warning-text">
                    Decryption key missing. Open the file from the VaultSpace to
                    retrieve the key.
                  </span>
                </div>
                <div class="link-meta">
                  <span v-if="link.expires_at">
                    Expires: {{ formatDate(link.expires_at) }}
                  </span>
                  <span v-else>No expiration</span>
                  <span v-if="link.max_downloads">
                    • {{ link.download_count || 0 }}/{{ link.max_downloads }}
                    downloads
                  </span>
                  <span v-else>
                    • {{ link.download_count || 0 }} downloads
                  </span>
                  <span v-if="link.max_access_count">
                    • {{ link.access_count || 0 }}/{{ link.max_access_count }}
                    accesses
                  </span>
                  <span v-else> • {{ link.access_count || 0 }} accesses </span>
                  <span v-if="link.has_password"> • Password protected </span>
                </div>
                <div class="link-status">
                  <span
                    :class="{
                      'status-active': isLinkAvailable(link),
                      'status-expired': isLinkExpired(link),
                    }"
                  >
                    {{ getLinkStatus(link) }}
                  </span>
                </div>
              </div>
              <div class="link-actions">
                <button
                  @click="copyLink(link, file.id)"
                  class="btn btn-small"
                  :disabled="
                    !isLinkAvailable(link) || !hasDecryptionKey(link, file.id)
                  "
                >
                  Copy Link
                </button>
                <button
                  @click="revokeLink(link.link_id, file.id)"
                  class="btn btn-small btn-danger"
                >
                  Revoke
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import ConfirmationModal from "../components/ConfirmationModal.vue";
import AlertModal from "../components/AlertModal.vue";
import { auth, files, vaultspaces } from "../services/api";
import { arrayToBase64url, base64urlToArray } from "../services/encryption.js";
import { decryptFile, decryptFileKey } from "../services/encryption";
import {
  getCachedVaultSpaceKey,
  getUserMasterKey,
  decryptVaultSpaceKeyForUser,
  cacheVaultSpaceKey,
  createVaultSpaceKey,
} from "../services/keyManager";
import { getVaultBaseUrl } from "../services/vault-config.js";
import {
  getFileKey as getFileKeyFromStorage,
  storeFileKey,
} from "../services/fileKeyStorage.js";
import * as mm from "music-metadata";

export default {
  name: "SharedView",
  components: {
    ConfirmationModal,
    AlertModal,
  },
  data() {
    return {
      files: [],
      loading: true,
      error: null,
      showRevokeConfirm: false,
      pendingRevokeLinkId: null,
      pendingRevokeFileId: null,
      showAlertModal: false,
      alertType: "error",
      alertTitle: "Error",
      alertMessage: "",
      showEmailModal: false,
      emailForm: {
        recipientEmail: "",
        loading: false,
        error: null,
      },
      pendingEmailLink: null,
      pendingEmailFileId: null,
      pendingEmailFileName: null,
      shareUrlCache: new Map(), // Cache for share URLs
      shareUrlKeyStatus: new Map(), // Cache for key availability status
      thumbnailUrls: {}, // Cache blob URLs for thumbnails
      thumbnailUpdateTrigger: 0, // Force reactivity trigger
    };
  },
  async mounted() {
    await this.loadSharedFiles();
  },
  methods: {
    getIcon(iconName, size = 24) {
      if (!window.Icons) {
        return "";
      }
      if (window.Icons.getIcon && typeof window.Icons.getIcon === "function") {
        return window.Icons.getIcon(iconName, size, "currentColor");
      }
      if (
        window.Icons[iconName] &&
        typeof window.Icons[iconName] === "function"
      ) {
        return window.Icons[iconName](size, "currentColor");
      }
      return "";
    },
    getFileIcon(file) {
      if (!window.Icons) {
        return "";
      }
      if (file.mime_type === "application/x-directory") {
        return this.getIcon("folder", 48);
      }
      const iconName = window.Icons.getFileIconName
        ? window.Icons.getFileIconName(file.mime_type, file.original_name)
        : "file";
      return this.getIcon(iconName, 48);
    },
    async loadSharedFiles() {
      this.loading = true;
      this.error = null;
      try {
        const jwtToken = localStorage.getItem("jwt_token");
        if (!jwtToken) {
          throw new Error("Not authenticated");
        }

        // Migrate to API v2 - use public-links endpoint to get shared files
        // Note: API v2 doesn't have a direct "shared files" endpoint
        // We'll need to get all public links and extract the files
        const response = await fetch("/api/v2/sharing/public-links", {
          headers: {
            Authorization: `Bearer ${jwtToken}`,
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
        });

        if (!response.ok) {
          if (response.status === 401) {
            auth.logout();
            this.$router.push("/login");
            return;
          }
          const errorData = await response.json();
          throw new Error(errorData.error || "Failed to load shared files");
        }

        const data = await response.json();
        const shareLinks = data.share_links || [];

        const filesMap = new Map();
        const now = new Date();

        for (const link of shareLinks) {
          if (link.resource_type !== "file" || !link.resource) {
            continue;
          }

          if (link.is_available === false) {
            continue;
          }

          const expiredFlag =
            typeof link.is_expired === "boolean"
              ? link.is_expired
              : link.expires_at && new Date(link.expires_at) <= now;
          if (expiredFlag) {
            continue;
          }

          const file = link.resource;
          const fileId = file.id;

          if (!filesMap.has(fileId)) {
            filesMap.set(fileId, {
              ...file,
              share_links: [],
            });
          }

          // Note: share_url will be constructed in getShareUrl() using VAULT_URL
          const shareLinkData = {
            ...link,
            link_id: link.token || link.id,
            share_url: link.share_url || null, // Will be constructed in getShareUrl()
            has_password: link.has_password || false,
          };

          filesMap.get(fileId).share_links.push(shareLinkData);
        }

        this.files = Array.from(filesMap.values());

        // Preload share URLs and recover missing keys for all links
        this.$nextTick(async () => {
          for (const file of this.files) {
            if (file.share_links) {
              for (const link of file.share_links) {
                await this.loadShareUrl(link, file.id);
                // Try to recover missing keys
                await this.ensureFileKeyAvailable(file.id, file.vaultspace_id);
              }
            }
            // Load thumbnails for images and audio files
            if (this.isImageFile(file) || this.isAudioFile(file)) {
              this.loadThumbnailUrl(file.id, file);
            }
          }
        });
      } catch (err) {
        this.error = err.message || "Failed to load shared files";
      } finally {
        this.loading = false;
      }
    },
    showCopyAnimation(linkUrlElement) {
      // Verify that linkUrlElement is a valid DOM element
      if (
        !linkUrlElement ||
        linkUrlElement.nodeType !== Node.ELEMENT_NODE ||
        typeof linkUrlElement.appendChild !== "function"
      ) {
        console.warn("showCopyAnimation: Invalid element", linkUrlElement);
        return;
      }

      // Remove any existing animation
      const existing = linkUrlElement.querySelector(".copy-animation-overlay");
      if (existing) {
        existing.remove();
      }

      // Ensure the linkUrlElement has position: relative for absolute positioning
      const computedStyle = window.getComputedStyle(linkUrlElement);
      if (computedStyle.position === "static") {
        linkUrlElement.style.position = "relative";
      }

      // Create overlay element
      const overlay = document.createElement("div");
      overlay.className = "copy-animation-overlay";

      // Create checkmark element
      const checkmark = document.createElement("div");
      checkmark.className = "copy-animation-checkmark";
      checkmark.textContent = "✔";
      checkmark.setAttribute("aria-hidden", "true");

      overlay.appendChild(checkmark);
      linkUrlElement.appendChild(overlay);

      // Force reflow to ensure initial state is applied
      void overlay.offsetHeight;
      void checkmark.offsetHeight;

      // Trigger animation
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.add("copy-animation-active");
        });
      });

      // Remove after animation completes
      setTimeout(() => {
        overlay.classList.remove("copy-animation-active");
        overlay.classList.add("copy-animation-hide");
        setTimeout(() => {
          if (overlay.parentNode) {
            overlay.remove();
          }
        }, 300); // Match fade out duration
      }, 1000); // Animation lasts 1 second
    },
    async copyLink(link, fileId) {
      try {
        // Use the same logic as getShareUrl to ensure we get the complete URL with key
        const result = await this.getShareUrl(link, fileId);

        if (!result.hasKey) {
          this.showAlert(
            "error",
            "Missing key",
            "The decryption key is not available. Please open the file from the VaultSpace to retrieve the key.",
          );
          return;
        }

        await navigator.clipboard.writeText(result.url);

        // Show animation on link URL element
        // Find the element by data-link-id attribute
        this.$nextTick(() => {
          // Use document.querySelector directly since Vue 3 $el can be a Fragment
          const linkUrlElement = document.querySelector(
            `[data-link-id="${link.link_id}"]`,
          );

          // Verify it's a valid DOM element (HTMLElement or Element)
          if (
            linkUrlElement &&
            linkUrlElement.nodeType === Node.ELEMENT_NODE &&
            typeof linkUrlElement.appendChild === "function"
          ) {
            this.showCopyAnimation(linkUrlElement);
          }
        });

        if (window.Notifications) {
          window.Notifications.success("Link copied to clipboard");
        }
      } catch (err) {
        console.error("Failed to copy link:", err);
        if (window.Notifications) {
          window.Notifications.error("Failed to copy link");
        }
      }
    },
    async revokeLink(linkId, fileId) {
      this.pendingRevokeLinkId = linkId;
      this.pendingRevokeFileId = fileId;
      this.showRevokeConfirm = true;
    },
    async handleRevokeConfirm() {
      const linkId = this.pendingRevokeLinkId;
      const fileId = this.pendingRevokeFileId;
      this.pendingRevokeLinkId = null;
      this.pendingRevokeFileId = null;

      try {
        // Get JWT token for authentication
        const token = localStorage.getItem("jwt_token");
        if (!token) {
          throw new Error("Not authenticated");
        }

        // Migrate to API v2 - use public-links endpoint
        const response = await fetch(`/api/v2/sharing/public-links/${linkId}`, {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || "Failed to revoke link");
        }

        if (window.Notifications) {
          window.Notifications.success("Share link revoked");
        }

        // Reload shared files
        await this.loadSharedFiles();
      } catch (err) {
        console.error("Failed to revoke link:", err);
        if (window.Notifications) {
          window.Notifications.error(`Failed to revoke link: ${err.message}`);
        }
      }
    },
    getOrigin() {
      return window.location.origin;
    },
    getShareUrlDisplay(link, fileId) {
      // Synchronous method for template display
      // Returns cached URL or placeholder while loading
      const cacheKey = `${link.link_id}-${fileId}`;
      if (this.shareUrlCache.has(cacheKey)) {
        return this.shareUrlCache.get(cacheKey);
      }
      // Trigger async loading
      this.loadShareUrl(link, fileId);
      // Return placeholder while loading
      return "Loading...";
    },
    async loadShareUrl(link, fileId) {
      // Async method to load and cache share URL
      const cacheKey = `${link.link_id}-${fileId}`;
      try {
        const result = await this.getShareUrl(link, fileId);
        this.shareUrlCache.set(cacheKey, result.url);
        this.shareUrlKeyStatus.set(cacheKey, result.hasKey);
        this.$forceUpdate(); // Force Vue to re-render
      } catch (e) {
        console.error("Failed to load share URL:", e);
        this.shareUrlCache.set(cacheKey, "Error loading URL");
        this.shareUrlKeyStatus.set(cacheKey, false);
        this.$forceUpdate();
      }
    },
    hasDecryptionKey(link, fileId) {
      // Check if decryption key is available for this link
      const cacheKey = `${link.link_id}-${fileId}`;
      if (this.shareUrlKeyStatus.has(cacheKey)) {
        return this.shareUrlKeyStatus.get(cacheKey);
      }
      // If not yet loaded, assume true to avoid showing warning prematurely
      return true;
    },
    async getShareUrl(link, fileId) {
      // Get file key if available
      let fileKey = null;
      let hasKey = false;

      try {
        // First, try to get key from IndexedDB via fileKeyStorage
        const keyStr = await getFileKeyFromStorage(fileId);
        if (keyStr) {
          try {
            fileKey = base64urlToArray(keyStr);
            hasKey = true;
          } catch (e) {
            console.warn("Failed to decode key from IndexedDB:", e);
          }
        }
      } catch (e) {
        console.warn("Failed to get file key from IndexedDB:", e);
      }

      // Fallback to localStorage if not found in IndexedDB
      if (!fileKey) {
        try {
          const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
          const keyStr = keys[fileId];
          if (keyStr) {
            if (base64urlToArray) {
              fileKey = base64urlToArray(keyStr);
              hasKey = true;
              // Store in IndexedDB for future use
              try {
                await storeFileKey(fileId, keyStr);
              } catch (e) {
                console.warn("Failed to store key in IndexedDB:", e);
              }
            } else if (
              window.VaultCrypto &&
              window.VaultCrypto.base64urlToArray
            ) {
              fileKey = window.VaultCrypto.base64urlToArray(keyStr);
              hasKey = true;
            }
          }
        } catch (e) {
          console.warn("Failed to get file key from localStorage:", e);
        }
      }

      // Try global functions as fallback
      if (!fileKey) {
        if (typeof getFileKey === "function") {
          fileKey = getFileKey(fileId);
          if (fileKey) hasKey = true;
        } else if (window.getFileKey) {
          fileKey = window.getFileKey(fileId);
          if (fileKey) hasKey = true;
        }
      }

      // Get base URL using VAULT_URL (with fallback to window.location.origin)
      const baseUrl = await getVaultBaseUrl();

      // Use share_url from backend if available (includes VAULT_URL), otherwise construct from baseUrl
      let url = link.share_url || `${baseUrl}/share/${link.link_id}`;

      // Add key to fragment if available
      if (fileKey) {
        try {
          const keyBase64 = arrayToBase64url(fileKey);
          url += `#key=${keyBase64}&file=${fileId}`;
        } catch (e) {
          console.warn("Failed to encode key for share URL:", e);
          hasKey = false;
        }
      }

      return { url, hasKey };
    },
    async ensureFileKeyAvailable(fileId, vaultspaceId) {
      // Check if key is available, if not try to recover it from the file
      try {
        const keyStr = await getFileKeyFromStorage(fileId);
        if (keyStr) {
          return; // Key already available
        }
      } catch (e) {
        // Continue to try recovery
      }

      // Key not found, try to recover from file
      if (!vaultspaceId) {
        return; // Cannot recover without vaultspace
      }

      try {
        // Get VaultSpace key (load from server if not cached)
        const vaultspaceKey =
          await this.loadVaultSpaceKeyIfNeeded(vaultspaceId);
        if (!vaultspaceKey) {
          return; // VaultSpace key not available
        }

        // Get file details with FileKey
        const fileData = await files.get(fileId, vaultspaceId);
        if (!fileData || !fileData.file_key) {
          return; // File key not found in file data
        }

        // Decrypt file key
        const fileKey = await decryptFileKey(
          vaultspaceKey,
          fileData.file_key.encrypted_key,
          true, // extractable to store it
        );

        // Export key as raw bytes
        const exportedKey = await crypto.subtle.exportKey("raw", fileKey);
        const keyArray = new Uint8Array(exportedKey);

        // Convert to base64url for storage
        const keyBase64 = arrayToBase64url(keyArray);

        // Store in IndexedDB
        await storeFileKey(fileId, keyBase64);

        // Also store in localStorage as fallback
        try {
          const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
          keys[fileId] = keyBase64;
          localStorage.setItem("vault_keys", JSON.stringify(keys));
        } catch (e) {
          console.warn("Failed to store key in localStorage:", e);
        }

        // Reload share URLs for this file
        const file = this.files.find((f) => f.id === fileId);
        if (file && file.share_links) {
          for (const link of file.share_links) {
            await this.loadShareUrl(link, fileId);
          }
        }

        // Reload thumbnail if applicable
        if (file && (this.isImageFile(file) || this.isAudioFile(file))) {
          this.loadThumbnailUrl(file.id, file);
        }
      } catch (error) {
        console.warn(`Failed to recover file key for ${fileId}:`, error);
      }
    },
    isLinkExpired(link) {
      if (typeof link.is_expired === "boolean") {
        return link.is_expired;
      }
      if (!link.expires_at) {
        return false;
      }
      return new Date(link.expires_at) <= new Date();
    },
    isDownloadLimitReached(link) {
      if (typeof link.is_download_limit_reached === "boolean") {
        return link.is_download_limit_reached;
      }
      if (!link.max_downloads) {
        return false;
      }
      const downloads = link.download_count || 0;
      return downloads >= link.max_downloads;
    },
    isLinkAvailable(link) {
      if (typeof link.is_available === "boolean" && !link.is_available) {
        return false;
      }
      if (this.isLinkExpired(link)) {
        return false;
      }
      if (this.isDownloadLimitReached(link)) {
        return false;
      }
      return true;
    },
    getLinkStatus(link) {
      if (!this.isLinkAvailable(link)) {
        if (this.isLinkExpired(link)) {
          return "Expired";
        }
        if (this.isDownloadLimitReached(link)) {
          return "Max downloads reached";
        }
        return "Unavailable";
      }
      return "Active";
    },
    formatSize(bytes) {
      if (bytes === 0) return "0 B";
      const k = 1024;
      const sizes = ["B", "KB", "MB", "GB"];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
    },
    formatDate(dateString) {
      if (!dateString) return "";
      const date = new Date(dateString);
      return date.toLocaleString();
    },
    hasAvailableLink(shareLinks) {
      if (!shareLinks || shareLinks.length === 0) {
        return false;
      }
      return shareLinks.some((link) => this.isLinkAvailable(link));
    },
    getFirstAvailableLink(shareLinks) {
      if (!shareLinks || shareLinks.length === 0) {
        return null;
      }
      return shareLinks.find((link) => this.isLinkAvailable(link)) || null;
    },
    async openSendEmailModalForFile(file) {
      // Find the first available link
      const link = this.getFirstAvailableLink(file.share_links);
      if (!link) {
        this.showAlert(
          "error",
          "No Available Link",
          "No available share links found for this file.",
        );
        return;
      }

      await this.openSendEmailModal(link, file.id, file.original_name);
    },
    async openSendEmailModal(link, fileId, fileName) {
      // Validate that the share URL contains the decryption key
      const result = await this.getShareUrl(link, fileId);
      if (!result.hasKey || !result.url.includes("#key=")) {
        this.showAlert(
          "error",
          "Unable to send email",
          "The share link does not have a decryption key. Please open the file from the VaultSpace to retrieve the key.",
        );
        return;
      }

      // Check if link is available
      if (!this.isLinkAvailable(link)) {
        this.showAlert(
          "error",
          "Link Not Available",
          "This share link is no longer available (expired or limit reached).",
        );
        return;
      }

      this.pendingEmailLink = link;
      this.pendingEmailFileId = fileId;
      this.pendingEmailFileName = fileName;
      this.emailForm.recipientEmail = "";
      this.emailForm.error = null;
      this.showEmailModal = true;
    },
    closeEmailModal() {
      // Allow closing even if loading (will be handled by the finally block)
      this.showEmailModal = false;
      this.emailForm.recipientEmail = "";
      this.emailForm.error = null;
      this.emailForm.loading = false;
      this.pendingEmailLink = null;
      this.pendingEmailFileId = null;
      this.pendingEmailFileName = null;
    },
    async handleSendEmail() {
      if (!this.emailForm.recipientEmail || this.emailForm.loading) {
        return;
      }

      // Validate email format
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(this.emailForm.recipientEmail)) {
        this.emailForm.error = "Please enter a valid email address";
        return;
      }

      this.emailForm.loading = true;
      this.emailForm.error = null;

      try {
        // Get the full share URL with key
        const result = await this.getShareUrl(
          this.pendingEmailLink,
          this.pendingEmailFileId,
        );

        // Double-check that the key is present
        if (!result.hasKey || !result.url.includes("#key=")) {
          throw new Error(
            "The share link does not have a decryption key. Unable to send email.",
          );
        }

        const shareUrl = result.url;

        const jwtToken = localStorage.getItem("jwt_token");
        if (!jwtToken) {
          throw new Error("Not authenticated");
        }

        const response = await fetch(
          `/api/v2/sharing/public-links/${this.pendingEmailLink.link_id}/send-email`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${jwtToken}`,
              "Content-Type": "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify({
              to_email: this.emailForm.recipientEmail,
              share_url: shareUrl,
            }),
          },
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || "Failed to send email");
        }

        // Parse response to ensure it's successful
        const responseData = await response.json().catch(() => ({}));

        // Success - close modal first, then show notification
        this.emailForm.loading = false;
        this.closeEmailModal();

        // Show success notification
        if (window.Notifications) {
          window.Notifications.success(
            "Share link sent via email successfully",
          );
        } else {
          // Fallback if Notifications is not available
          this.showAlert(
            "success",
            "Email Sent",
            "The share link has been sent successfully via email.",
          );
        }
      } catch (err) {
        console.error("Failed to send email:", err);
        this.emailForm.loading = false;
        this.emailForm.error = err.message || "Failed to send email";
        this.showAlert(
          "error",
          "Failed to Send Email",
          err.message ||
            "An error occurred while sending the email. Please try again.",
        );
      }
    },
    showAlert(type, title, message) {
      this.alertType = type;
      this.alertTitle = title;
      this.alertMessage = message;
      this.showAlertModal = true;
    },
    // Check if file is an image based on mime_type or file extension
    isImageFile(file) {
      // Check mime_type first
      if (file.mime_type?.startsWith("image/")) {
        return true;
      }

      // Fallback: check file extension for common image formats
      if (file.original_name) {
        const extension = file.original_name.split(".").pop()?.toLowerCase();
        const imageExtensions = [
          "png",
          "jpg",
          "jpeg",
          "gif",
          "webp",
          "bmp",
          "svg",
          "ico",
          "tiff",
          "tif",
        ];
        return imageExtensions.includes(extension);
      }

      return false;
    },
    // Check if file is an audio file based on mime_type or file extension
    isAudioFile(file) {
      // Check mime_type first
      if (file.mime_type?.startsWith("audio/")) {
        return true;
      }

      // Fallback: check file extension for common audio formats
      if (file.original_name) {
        const extension = file.original_name.split(".").pop()?.toLowerCase();
        const audioExtensions = ["mp3", "wav", "flac", "ogg", "m4a", "aac"];
        return audioExtensions.includes(extension);
      }

      return false;
    },
    // Get thumbnail URL for a file
    getThumbnailUrl(fileId) {
      // Access thumbnailUpdateTrigger to create dependency
      void this.thumbnailUpdateTrigger;
      // Return cached URL if available
      return this.thumbnailUrls[fileId] || "";
    },
    // Check if file has a thumbnail available
    hasThumbnail(file) {
      // For images, always try to show thumbnail (either from storage or load image directly)
      // For audio files, check if thumbnail URL is already cached (meaning cover was found)
      return (
        this.isImageFile(file) ||
        (this.isAudioFile(file) && this.thumbnailUrls[file.id])
      );
    },
    // Load VaultSpace key if not cached
    async loadVaultSpaceKeyIfNeeded(vaultspaceId) {
      // Check if already cached
      let vaultspaceKey = getCachedVaultSpaceKey(vaultspaceId);
      if (vaultspaceKey) {
        return vaultspaceKey;
      }

      // Try to load from server
      try {
        const userMasterKey = await getUserMasterKey();
        if (!userMasterKey) {
          return null;
        }

        // Get encrypted VaultSpace key from server
        const vaultspaceKeyData = await vaultspaces.getKey(vaultspaceId);
        if (!vaultspaceKeyData) {
          return null;
        }

        // Decrypt VaultSpace key
        vaultspaceKey = await decryptVaultSpaceKeyForUser(
          userMasterKey,
          vaultspaceKeyData.encrypted_key,
        );

        // Cache the decrypted key
        cacheVaultSpaceKey(vaultspaceId, vaultspaceKey);
        return vaultspaceKey;
      } catch (error) {
        console.warn(
          `Failed to load VaultSpace key for ${vaultspaceId}:`,
          error,
        );
        return null;
      }
    },
    // Load image directly as thumbnail
    async loadImageAsThumbnail(file) {
      const vaultspaceId = file.vaultspace_id;
      if (!vaultspaceId) {
        return;
      }

      try {
        // Get VaultSpace key (load from server if not cached)
        const vaultspaceKey =
          await this.loadVaultSpaceKeyIfNeeded(vaultspaceId);
        if (!vaultspaceKey) {
          return;
        }

        // Try to get file key from storage first
        let fileKey = null;
        try {
          const keyStr = await getFileKeyFromStorage(file.id);
          if (keyStr) {
            const keyArray = base64urlToArray(keyStr);
            fileKey = await crypto.subtle.importKey(
              "raw",
              keyArray,
              { name: "AES-GCM", length: 256 },
              false,
              ["encrypt", "decrypt"],
            );
          }
        } catch (e) {
          // Continue to get from file
        }

        // If key not in storage, get from file
        if (!fileKey) {
          // Get file key
          const fileData = await files.get(file.id, vaultspaceId);
          if (!fileData.file_key) {
            return;
          }

          // Decrypt file key
          fileKey = await decryptFileKey(
            vaultspaceKey,
            fileData.file_key.encrypted_key,
            true, // extractable to store it
          );

          // Store key for future use
          try {
            const exportedKey = await crypto.subtle.exportKey("raw", fileKey);
            const keyArray = new Uint8Array(exportedKey);
            const keyBase64 = arrayToBase64url(keyArray);
            await storeFileKey(file.id, keyBase64);
          } catch (e) {
            console.warn("Failed to store file key:", e);
          }
        }

        // Download encrypted file
        const encryptedData = await files.download(file.id, vaultspaceId);

        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Create blob URL for the image
        const blob = new Blob([decryptedData], { type: file.mime_type });
        const blobUrl = URL.createObjectURL(blob);

        // Store in cache (create new object to ensure reactivity)
        this.thumbnailUrls = {
          ...this.thumbnailUrls,
          [file.id]: blobUrl,
        };

        // Force Vue to update
        this.thumbnailUpdateTrigger++;
        await this.$nextTick();
      } catch (error) {
        console.debug(
          `Failed to load image as thumbnail for ${file.id}:`,
          error,
        );
      }
    },
    // Load audio cover art as thumbnail
    async loadAudioCoverAsThumbnail(file) {
      const vaultspaceId = file.vaultspace_id;
      if (!vaultspaceId) {
        return;
      }

      try {
        // Get VaultSpace key (load from server if not cached)
        const vaultspaceKey =
          await this.loadVaultSpaceKeyIfNeeded(vaultspaceId);
        if (!vaultspaceKey) {
          return;
        }

        // Try to get file key from storage first
        let fileKey = null;
        try {
          const keyStr = await getFileKeyFromStorage(file.id);
          if (keyStr) {
            const keyArray = base64urlToArray(keyStr);
            fileKey = await crypto.subtle.importKey(
              "raw",
              keyArray,
              { name: "AES-GCM", length: 256 },
              false,
              ["encrypt", "decrypt"],
            );
          }
        } catch (e) {
          // Continue to get from file
        }

        // If key not in storage, get from file
        if (!fileKey) {
          // Get file key
          const fileData = await files.get(file.id, vaultspaceId);
          if (!fileData.file_key) {
            return;
          }

          // Decrypt file key
          fileKey = await decryptFileKey(
            vaultspaceKey,
            fileData.file_key.encrypted_key,
            true, // extractable to store it
          );

          // Store key for future use
          try {
            const exportedKey = await crypto.subtle.exportKey("raw", fileKey);
            const keyArray = new Uint8Array(exportedKey);
            const keyBase64 = arrayToBase64url(keyArray);
            await storeFileKey(file.id, keyBase64);
          } catch (e) {
            console.warn("Failed to store file key:", e);
          }
        }

        // Download encrypted file
        const encryptedData = await files.download(file.id, vaultspaceId);

        // Extract IV and encrypted content (IV is first 12 bytes)
        const encryptedDataArray = new Uint8Array(encryptedData);
        const iv = encryptedDataArray.slice(0, 12);
        const encrypted = encryptedDataArray.slice(12);

        // Decrypt file
        const decryptedData = await decryptFile(fileKey, encrypted.buffer, iv);

        // Create a Blob from the decrypted data
        const arrayBuffer =
          decryptedData instanceof ArrayBuffer
            ? decryptedData
            : decryptedData.buffer || new Uint8Array(decryptedData).buffer;

        const blob = new Blob([arrayBuffer], {
          type: file.mime_type || "audio/mpeg",
        });

        // Parse metadata using music-metadata
        // Convert blob to ArrayBuffer for parsing
        const audioArrayBuffer = await blob.arrayBuffer();
        const metadata = await mm.parseBuffer(
          new Uint8Array(audioArrayBuffer),
          blob.type,
        );

        // Check if there's a picture/cover art in the metadata
        if (metadata.common?.picture && metadata.common.picture.length > 0) {
          // Get the first picture (usually the album cover)
          const picture = metadata.common.picture[0];

          if (picture?.data) {
            // Convert picture.data to Uint8Array
            let pictureData;
            if (picture.data instanceof Uint8Array) {
              pictureData = picture.data;
            } else if (picture.data instanceof ArrayBuffer) {
              pictureData = new Uint8Array(picture.data);
            } else if (Buffer && Buffer.isBuffer(picture.data)) {
              pictureData = new Uint8Array(picture.data);
            } else if (Array.isArray(picture.data)) {
              pictureData = new Uint8Array(picture.data);
            } else {
              pictureData = new Uint8Array(Object.values(picture.data));
            }

            // Determine MIME type from format
            let pictureFormat = "image/jpeg"; // Default
            if (picture.format) {
              const format = picture.format.toLowerCase();
              if (format.startsWith("image/")) {
                pictureFormat = picture.format;
              } else {
                const formatMap = {
                  jpeg: "image/jpeg",
                  jpg: "image/jpeg",
                  png: "image/png",
                  gif: "image/gif",
                  bmp: "image/bmp",
                  webp: "image/webp",
                };
                pictureFormat = formatMap[format] || "image/jpeg";
              }
            }

            const pictureBlob = new Blob([pictureData], {
              type: pictureFormat,
            });
            const blobUrl = URL.createObjectURL(pictureBlob);

            // Store in cache (create new object to ensure reactivity)
            this.thumbnailUrls = {
              ...this.thumbnailUrls,
              [file.id]: blobUrl,
            };

            // Force Vue to update
            this.thumbnailUpdateTrigger++;
            await this.$nextTick();
          }
        }
      } catch (error) {
        // Silently fail - no cover art available
        console.debug(
          `Failed to load audio cover as thumbnail for ${file.id}:`,
          error,
        );
      }
    },
    // Load thumbnail URL - for images, load the image directly without checking for thumbnail
    // This avoids 404 errors in the network tab
    async loadThumbnailUrl(fileId, file = null) {
      if (this.thumbnailUrls[fileId]) {
        return; // Already loaded
      }

      // Find file object if not provided
      if (!file) {
        file = this.files.find((f) => f.id === fileId);
      }

      if (!file) {
        return;
      }

      // Load image thumbnail
      if (this.isImageFile(file)) {
        try {
          await this.loadImageAsThumbnail(file);
        } catch (imageError) {
          console.debug(
            `Failed to load image as thumbnail for ${fileId}:`,
            imageError,
          );
        }
        return;
      }

      // Load audio cover as thumbnail
      if (this.isAudioFile(file)) {
        try {
          await this.loadAudioCoverAsThumbnail(file);
        } catch (audioError) {
          // Silently fail - no cover art available
          console.debug(
            `No cover art available for audio file ${fileId}:`,
            audioError,
          );
        }
        return;
      }
    },
  },
  beforeUnmount() {
    // Clean up all blob URLs
    for (const fileId in this.thumbnailUrls) {
      if (this.thumbnailUrls[fileId]) {
        URL.revokeObjectURL(this.thumbnailUrls[fileId]);
      }
    }
  },
};
</script>

<style scoped>
.shared-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.mobile-mode .shared-view {
  padding: 1rem;
  padding-bottom: calc(1rem + 64px);
}

.view-header {
  margin-bottom: 2rem;
}

.view-header h1 {
  margin: 0 0 0.5rem 0;
  color: #e6eef6;
  font-size: 2rem;
  font-weight: 600;
}

.view-description {
  margin: 0;
  color: #94a3b8;
  font-size: 0.95rem;
}

.shared-files-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.shared-file-item {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 1rem;
  padding: 1.5rem;
  transition: all 0.2s ease;
}

.mobile-mode .shared-file-item {
  padding: 1rem;
}

.shared-file-item:hover {
  border-color: rgba(88, 166, 255, 0.3);
  background: rgba(255, 255, 255, 0.05);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
  position: relative;
  width: 100%;
}

.file-details {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.file-actions {
  display: flex;
  align-items: center;
  padding: 0;
  margin: 0;
  margin-left: auto;
}

.file-actions .btn,
.file-actions .btn-send-email {
  margin: 0 !important;
  margin-left: 0 !important;
  margin-right: 0 !important;
}

.btn.btn-small.btn-send-email {
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  padding: 0.5rem 1rem !important;
  font-size: 0.875rem;
  white-space: nowrap;
  line-height: 1.5 !important;
  text-align: center;
  vertical-align: middle;
  transition: all 0.3s ease;
  transform: translateY(0);
}

.btn.btn-small.btn-send-email:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(88, 166, 255, 0.4);
  opacity: 0.95;
}

.btn.btn-small.btn-send-email:active {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(88, 166, 255, 0.3);
}

.file-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
  width: 48px;
  height: 48px;
  min-width: 48px;
  min-height: 48px;
}

.file-thumbnail {
  max-height: 48px;
  max-width: 48px;
  width: auto;
  height: auto;
  object-fit: cover;
  border-radius: 0.25rem;
}

.file-details {
  flex: 1;
  min-width: 0;
}

.file-name {
  margin: 0 0 0.25rem 0;
  color: #e6eef6;
  font-size: 1.1rem;
  font-weight: 600;
  word-break: break-word;
}

.file-meta {
  margin: 0;
  color: #94a3b8;
  font-size: 0.85rem;
}

.share-links-info {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.share-link-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0.75rem;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mobile-mode .share-link-card {
  padding: 0.75rem;
  gap: 0.75rem;
  flex-direction: row;
  align-items: flex-start;
}

.link-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.mobile-mode .link-info {
  gap: 0.375rem;
  flex: 1;
  min-width: 0;
}

.link-url {
  font-size: 0.85rem;
  color: #94a3b8;
  word-break: break-all;
  margin-bottom: 0;
  font-family: monospace;
  position: relative;
  padding: 0.5rem 0.75rem;
  background: rgba(15, 23, 42, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0.375rem;
}

.mobile-mode .link-url {
  font-size: 0.75rem;
  padding: 0.5rem;
  max-height: 3rem;
  overflow-y: auto;
}

.link-warning {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 0.5rem;
  color: #fbbf24;
  font-size: 0.875rem;
}

.warning-icon {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.warning-text {
  flex: 1;
  line-height: 1.5;
}

.link-meta {
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.mobile-mode .link-meta {
  font-size: 0.7rem;
  line-height: 1.4;
}

.link-status {
  font-size: 0.75rem;
  font-weight: 500;
}

.mobile-mode .link-status {
  font-size: 0.7rem;
}

.status-active {
  color: #10b981;
}

.status-expired {
  color: #f59e0b;
}

.status-revoked {
  color: #ef4444;
}

.link-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
  align-items: flex-start;
}

.mobile-mode .link-actions {
  flex-direction: column;
  gap: 0.5rem;
  flex-shrink: 0;
  min-width: 100px;
  align-self: flex-start;
}

.mobile-mode .link-actions .btn {
  width: 100%;
  white-space: nowrap;
  padding: 0.5rem 0.75rem;
  font-size: 0.8rem;
}

.btn-small {
  padding: 0.375rem 0.75rem;
  font-size: 0.85rem;
}

.empty-state {
  text-align: center;
  padding: 4rem 2rem;
  color: #94a3b8;
}

.empty-state p {
  margin: 0.5rem 0;
}

.empty-hint {
  font-size: 0.9rem;
  color: #64748b;
}

.loading {
  text-align: center;
  padding: 4rem 2rem;
  color: #94a3b8;
}

.error {
  padding: 1rem;
  text-align: center;
  color: #f85149;
  background-color: rgba(248, 81, 73, 0.1);
  border: 1px solid rgba(248, 81, 73, 0.3);
  border-radius: 0.5rem;
}

/* Copy Animation Overlay */
.copy-animation-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(16, 185, 129, 0.3);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border-radius: 0.375rem;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.4) inset;
}

.copy-animation-overlay.copy-animation-active {
  opacity: 1;
}

.copy-animation-overlay.copy-animation-hide {
  opacity: 0;
}

.copy-animation-checkmark {
  font-size: 1.5rem;
  color: white;
  font-weight: bold;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  opacity: 0;
  transform: scale(0.5);
  transition:
    opacity 0.3s ease,
    transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.copy-animation-overlay.copy-animation-active .copy-animation-checkmark {
  opacity: 1;
  transform: scale(1);
}

.copy-animation-overlay.copy-animation-hide .copy-animation-checkmark {
  opacity: 0;
  transform: scale(0.8);
}

/* Email Modal Styles */
.email-modal .modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  animation: fadeIn 0.2s ease;
}

.email-modal .modal-container {
  position: relative;
  width: 100%;
  max-width: 500px;
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

.email-modal .modal-content-email {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 2rem;
  padding: 2rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
}

.email-modal .modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.email-modal .modal-title {
  margin: 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
}

.email-modal .modal-close {
  background: none;
  border: none;
  color: #94a3b8;
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.email-modal .modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e6eef6;
}

.email-modal .modal-body {
  margin-bottom: 1.5rem;
}

.email-modal .form-group {
  margin-bottom: 1rem;
}

.email-modal .form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #cbd5e1;
  font-weight: 500;
  font-size: 0.9rem;
}

.email-modal .form-input {
  width: 100%;
  padding: 0.75rem 1rem;
  background: rgba(15, 23, 42, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 0.5rem;
  color: #e6eef6;
  font-size: 1rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.email-modal .form-input:focus {
  outline: none;
  border-color: rgba(88, 166, 255, 0.5);
  background: rgba(15, 23, 42, 0.5);
}

.email-modal .form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.email-modal .form-error {
  color: #ef4444;
  font-size: 0.875rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 0.375rem;
}

.email-modal .modal-footer {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}

.email-modal .btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 100px;
}

.email-modal .btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.email-modal .btn-primary {
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  color: white;
}

.email-modal .btn-primary:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.email-modal .btn-secondary {
  background: rgba(255, 255, 255, 0.1);
  color: #cbd5e1;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.email-modal .btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.15);
}
</style>
