<template>
  <AppLayout @logout="logout">
    <ConfirmationModal
      :show="showRevokeConfirm"
      title="Revoke Share Link"
      message="Are you sure you want to revoke this share link? This action cannot be undone."
      confirm-text="Revoke"
      :dangerous="true"
      @confirm="handleRevokeConfirm"
      @close="showRevokeConfirm = false"
    />
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
        <div v-else class="shared-files-list glass">
          <div v-for="file in files" :key="file.id" class="shared-file-item">
            <div class="file-info">
              <div class="file-icon" v-html="getIcon('file', 32)"></div>
              <div class="file-details">
                <h3 class="file-name">{{ file.original_name }}</h3>
                <p class="file-meta">
                  Size: {{ formatSize(file.size) }} • Created:
                  {{ formatDate(file.created_at) }}
                </p>
              </div>
            </div>
            <div class="share-links-info">
              <div
                v-for="link in file.share_links || []"
                :key="link.link_id"
                class="share-link-card"
              >
                <div class="link-info">
                  <div :data-link-id="link.link_id" class="link-url">
                    {{ getShareUrl(link, file.id) }}
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
                    <span v-else>
                      • {{ link.access_count || 0 }} accesses
                    </span>
                    <span v-if="link.has_password"> • Password protected </span>
                  </div>
                  <div class="link-status">
                    <span
                      :class="{
                        'status-active':
                          link.is_active &&
                          (!link.expires_at ||
                            new Date(link.expires_at) > new Date()),
                        'status-expired':
                          link.expires_at &&
                          new Date(link.expires_at) <= new Date(),
                        'status-revoked': !link.is_active,
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
                      !link.is_active ||
                      (link.expires_at &&
                        new Date(link.expires_at) <= new Date())
                    "
                  >
                    Copy Link
                  </button>
                  <button
                    @click="revokeLink(link.link_id, file.id)"
                    class="btn btn-small btn-danger"
                    :disabled="!link.is_active"
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
  </AppLayout>
</template>

<script>
import AppLayout from "../components/AppLayout.vue";
import ConfirmationModal from "../components/ConfirmationModal.vue";
import { auth } from "../services/api";
import { arrayToBase64url, base64urlToArray } from "../services/encryption.js";

export default {
  name: "SharedView",
  components: {
    AppLayout,
    ConfirmationModal,
  },
  data() {
    return {
      files: [],
      loading: true,
      error: null,
      showRevokeConfirm: false,
      pendingRevokeLinkId: null,
      pendingRevokeFileId: null,
    };
  },
  async mounted() {
    await this.loadSharedFiles();
  },
  methods: {
    getIcon(iconName, size = 24) {
      if (!window.Icons || !window.Icons[iconName]) {
        return "";
      }
      return window.Icons[iconName](size, "currentColor");
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

          if (!link.is_active) {
            continue;
          }

          if (link.expires_at && new Date(link.expires_at) <= now) {
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

          const shareLinkData = {
            ...link,
            link_id: link.token || link.id,
            share_url:
              link.share_url ||
              `${window.location.origin}/share/${link.token || link.id}`,
            has_password: link.has_password || false,
          };

          filesMap.get(fileId).share_links.push(shareLinkData);
        }

        this.files = Array.from(filesMap.values());
      } catch (err) {
        this.error = err.message || "Failed to load shared files";
      } finally {
        this.loading = false;
      }
    },
    showCopyAnimation(linkUrlElement) {
      if (!linkUrlElement) {
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
        const url = this.getShareUrl(link, fileId);

        await navigator.clipboard.writeText(url);

        // Show animation on link URL element
        // Find the element by data-link-id attribute within the component
        this.$nextTick(() => {
          const linkUrlElement =
            this.$el?.querySelector(`[data-link-id="${link.link_id}"]`) ||
            document.querySelector(`[data-link-id="${link.link_id}"]`);
          if (linkUrlElement) {
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
    getShareUrl(link, fileId) {
      // Get file key if available
      let fileKey = null;
      try {
        // Try to get key from localStorage
        const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
        const keyStr = keys[fileId];
        if (keyStr) {
          if (base64urlToArray) {
            fileKey = base64urlToArray(keyStr);
          } else if (
            window.VaultCrypto &&
            window.VaultCrypto.base64urlToArray
          ) {
            fileKey = window.VaultCrypto.base64urlToArray(keyStr);
          }
        }
      } catch (e) {
        console.warn("Failed to get file key from localStorage:", e);
      }

      // Try global functions as fallback
      if (!fileKey) {
        if (typeof getFileKey === "function") {
          fileKey = getFileKey(fileId);
        } else if (window.getFileKey) {
          fileKey = window.getFileKey(fileId);
        }
      }

      // Use share_url from backend if available (includes VAULT_URL), otherwise construct from window.location
      let url =
        link.share_url || `${window.location.origin}/share/${link.link_id}`;

      // Add key to fragment if available
      if (fileKey) {
        try {
          const keyBase64 = arrayToBase64url(fileKey);
          url += `#key=${keyBase64}&file=${fileId}`;
        } catch (e) {
          console.warn("Failed to encode key for share URL:", e);
        }
      }

      return url;
    },
    getLinkStatus(link) {
      if (!link.is_active) {
        return "Revoked";
      }
      if (link.expires_at && new Date(link.expires_at) <= new Date()) {
        return "Expired";
      }
      if (link.max_downloads && link.download_count >= link.max_downloads) {
        return "Max downloads reached";
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
    logout() {
      auth.logout();
      this.$router.push("/login");
    },
  },
};
</script>

<style scoped>
.shared-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
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

.shared-file-item:hover {
  border-color: rgba(88, 166, 255, 0.3);
  background: rgba(255, 255, 255, 0.05);
}

.file-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.file-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
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
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.link-info {
  flex: 1;
  min-width: 0;
}

.link-url {
  font-size: 0.85rem;
  color: #94a3b8;
  word-break: break-all;
  margin-bottom: 0.5rem;
  font-family: monospace;
  position: relative;
  padding: 0.5rem 0.75rem;
  background: rgba(15, 23, 42, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 0.375rem;
}

.link-meta {
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.link-status {
  font-size: 0.75rem;
  font-weight: 500;
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
</style>
