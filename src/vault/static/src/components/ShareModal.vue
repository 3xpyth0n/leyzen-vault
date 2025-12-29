<template>
  <Teleport v-if="show" to="body">
    <div class="modal-overlay" @click.self="close">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h2 class="modal-title">Share File</h2>
          <button
            @click="close"
            class="modal-close"
            aria-label="Close"
            type="button"
          >
            &times;
          </button>
        </div>
        <div class="share-modal-body">
          <form @submit.prevent="createLink" class="share-link-form">
            <div class="share-section share-section-create">
              <h3>Create Share Link</h3>
              <div class="share-link-options">
                <div class="form-group">
                  <label>
                    <input
                      v-model="formOptions.expires"
                      type="checkbox"
                      @change="onExpiresChange"
                    />
                    <span>Set expiration date</span>
                  </label>
                  <input
                    v-if="formOptions.expires"
                    v-model="formData.expiresDate"
                    type="datetime-local"
                    class="share-date-input"
                  />
                </div>
                <div class="form-group">
                  <label>
                    <input
                      v-model="formOptions.maxDownloads"
                      type="checkbox"
                      @change="onMaxDownloadsChange"
                    />
                    <span>Limit number of downloads</span>
                  </label>
                  <input
                    v-if="formOptions.maxDownloads"
                    v-model.number="formData.maxDownloads"
                    type="number"
                    class="share-number-input"
                    placeholder="Number of downloads"
                    min="1"
                  />
                </div>
                <div class="form-group">
                  <label>
                    <input
                      v-model="formOptions.password"
                      type="checkbox"
                      @change="onPasswordChange"
                    />
                    <span>Protect with password</span>
                  </label>
                  <div
                    v-if="formOptions.password"
                    class="share-password-input-wrapper"
                  >
                    <input
                      v-model="formData.password"
                      :type="showPassword ? 'text' : 'password'"
                      class="share-password-input"
                      placeholder="Enter password"
                      autocomplete="off"
                    />
                    <button
                      type="button"
                      class="password-toggle"
                      :class="{ 'is-visible': showPassword }"
                      :aria-label="
                        showPassword ? 'Hide password' : 'Show password'
                      "
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
                        <path
                          d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
                        ></path>
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
                        <path
                          d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
                        ></path>
                        <circle cx="12" cy="12" r="3"></circle>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
              <div class="share-actions">
                <button
                  type="submit"
                  class="btn btn-primary"
                  :disabled="isCreatingLink"
                >
                  {{ isCreatingLink ? "Creating..." : "Create Share Link" }}
                </button>
              </div>
            </div>
          </form>

          <div class="share-section">
            <h3>Active Share Links</h3>
            <div v-if="loadingLinks" class="loading-links">
              Loading links...
            </div>
            <div v-else-if="activeLinks.length === 0" class="share-empty">
              <p>No active share links</p>
            </div>
            <div v-else class="active-links-list">
              <div
                v-for="link in activeLinks"
                :key="link.id"
                class="active-link-item"
              >
                <div class="active-link-info">
                  <div
                    class="active-link-url"
                    :ref="(el) => setLinkUrlRef(link.id, el)"
                  >
                    {{ getLinkUrl(link) }}
                  </div>
                  <div class="active-link-meta">{{ getLinkMeta(link) }}</div>
                </div>
                <div class="active-link-actions">
                  <button
                    class="btn btn-small copy-link-btn"
                    @click="copyLink(link)"
                  >
                    Copy
                  </button>
                  <button
                    class="btn btn-small btn-danger revoke-link-btn"
                    @click="revokeLink(link.id)"
                  >
                    Revoke
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from "vue";
import { sharing } from "../services/api";
import { modalManager } from "../utils/ModalManager";
import { getVaultBaseUrl } from "../services/vault-config";

const props = defineProps({
  show: {
    type: Boolean,
    default: false,
  },
  fileId: {
    type: String,
    required: true,
  },
  fileType: {
    type: String,
    default: "file",
  },
  fileKey: {
    type: Uint8Array,
    default: null,
  },
});

const emit = defineEmits(["close", "update:show"]);

const formOptions = ref({
  expires: false,
  maxDownloads: false,
  password: false,
});

const formData = ref({
  expiresDate: "",
  maxDownloads: null,
  password: "",
});

const showPassword = ref(false);
const isCreatingLink = ref(false);
const activeLinks = ref([]);
const loadingLinks = ref(false);
const linkUrlRefs = ref({});
const baseUrl = ref(window.location.origin);

const setLinkUrlRef = (linkId, el) => {
  if (el) {
    linkUrlRefs.value[linkId] = el;
  }
};

// Load base URL on mount
const loadBaseUrl = async () => {
  try {
    baseUrl.value = await getVaultBaseUrl();
  } catch (error) {
    baseUrl.value = window.location.origin;
  }
};

// Compute link URLs synchronously
const computeLinkUrl = (link) => {
  const currentBaseUrl = baseUrl.value || window.location.origin;
  const linkToken = link.token || link.link_id;
  let shareUrl = link.share_url || `${currentBaseUrl}/share/${linkToken}`;

  if (props.fileKey) {
    let keyBase64;
    if (window.VaultCrypto && window.VaultCrypto.arrayToBase64url) {
      keyBase64 = window.VaultCrypto.arrayToBase64url(props.fileKey);
    } else if (typeof btoa !== "undefined") {
      const keyArray = Array.from(props.fileKey);
      keyBase64 = btoa(String.fromCharCode.apply(null, keyArray));
      keyBase64 = encodeURIComponent(keyBase64);
    }

    if (keyBase64) {
      shareUrl += `#key=${keyBase64}&file=${props.fileId}`;
    }
  }

  return shareUrl;
};

const onExpiresChange = () => {
  if (!formOptions.value.expires) {
    formData.value.expiresDate = "";
  }
};

const onMaxDownloadsChange = () => {
  if (!formOptions.value.maxDownloads) {
    formData.value.maxDownloads = null;
  }
};

const onPasswordChange = () => {
  if (!formOptions.value.password) {
    formData.value.password = "";
    showPassword.value = false;
  }
};

const togglePassword = () => {
  showPassword.value = !showPassword.value;
};

const close = () => {
  emit("update:show", false);
  emit("close");
};

const loadActiveLinks = async () => {
  if (!props.fileId) return;

  loadingLinks.value = true;
  try {
    const response = await sharing.listPublicLinks(props.fileId);
    const links = response.share_links || [];

    const now = new Date();
    const filtered = links.filter((link) => {
      if (link.is_available === false) return false;
      if (link.is_expired) return false;
      if (link.expires_at) {
        return new Date(link.expires_at) > now;
      }
      return true;
    });

    activeLinks.value = filtered;
  } catch (error) {
    if (window.Notifications) {
      window.Notifications.error(error.message || "Failed to load share links");
    }
    activeLinks.value = [];
  } finally {
    loadingLinks.value = false;
  }
};

const getLinkUrl = (link) => {
  return computeLinkUrl(link);
};

const getLinkMeta = (link) => {
  const parts = [];

  if (link.expires_at) {
    parts.push(`Expires: ${new Date(link.expires_at).toLocaleString()}`);
  } else {
    parts.push("No expiration");
  }

  if (link.max_downloads) {
    parts.push(`${link.download_count || 0}/${link.max_downloads} downloads`);
  } else {
    parts.push(`${link.download_count || 0} downloads`);
  }

  if (link.has_password) {
    parts.push("Password protected");
  }

  return parts.join(" • ");
};

const createLink = async () => {
  if (isCreatingLink.value) return;

  isCreatingLink.value = true;

  try {
    let expiresInDays = null;
    if (formOptions.value.expires && formData.value.expiresDate) {
      const expiresDate = new Date(formData.value.expiresDate);
      const now = new Date();
      const diffMs = expiresDate.getTime() - now.getTime();
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
      if (diffDays > 0) {
        expiresInDays = diffDays;
      }
    }

    const password =
      formOptions.value.password && formData.value.password.trim()
        ? formData.value.password.trim()
        : null;

    const maxDownloads =
      formOptions.value.maxDownloads && formData.value.maxDownloads
        ? parseInt(formData.value.maxDownloads, 10)
        : null;

    const response = await sharing.createPublicLink({
      resource_id: props.fileId,
      resource_type: props.fileType,
      password,
      expires_in_days: expiresInDays,
      max_downloads: maxDownloads,
      allow_download: true,
    });

    const shareLink = response.share_link || response;

    if (!shareLink) {
      throw new Error("Invalid response from server: no share_link");
    }

    let shareUrl = computeLinkUrl(shareLink);

    if (window.Notifications) {
      window.Notifications.success("Share link created successfully!");
    }

    // Copy to clipboard
    try {
      await navigator.clipboard.writeText(shareUrl);
      if (window.Notifications) {
        window.Notifications.info("Share link copied to clipboard");
      }
    } catch (e) {
      // Ignore clipboard errors
    }

    // Reset form
    formOptions.value = {
      expires: false,
      maxDownloads: false,
      password: false,
    };
    formData.value = {
      expiresDate: "",
      maxDownloads: null,
      password: "",
    };
    showPassword.value = false;

    // Reload active links
    await loadActiveLinks();
  } catch (error) {
    const errorMessage = error.message || error.toString() || "Unknown error";
    if (window.Notifications) {
      window.Notifications.error(
        `Failed to create share link: ${errorMessage}`,
      );
    }
  } finally {
    isCreatingLink.value = false;
  }
};

const copyLink = async (link) => {
  try {
    const url = getLinkUrl(link);
    await navigator.clipboard.writeText(url);

    if (window.Notifications) {
      window.Notifications.success("Link copied to clipboard");
    }

    const linkUrlElement = linkUrlRefs.value[link.id];
    if (linkUrlElement) {
      showCopyAnimation(linkUrlElement);
    }
  } catch (error) {
    if (window.Notifications) {
      window.Notifications.error("Failed to copy link");
    }
  }
};

const revokeLink = async (linkId) => {
  const confirmed =
    window.showConfirmationModal &&
    (await new Promise((resolve) => {
      window.showConfirmationModal({
        title: "Revoke Share Link",
        message:
          "Are you sure you want to revoke this share link? This action cannot be undone.",
        confirmText: "Revoke",
        dangerous: true,
        onConfirm: () => resolve(true),
        onCancel: () => resolve(false),
      });
    }));

  if (!confirmed) {
    if (!window.showConfirmationModal) {
      if (!confirm("Are you sure you want to revoke this share link?")) {
        return;
      }
    } else {
      return;
    }
  }

  try {
    await sharing.deletePublicLink(linkId);
    if (window.Notifications) {
      window.Notifications.success("Share link revoked");
    }
    await loadActiveLinks();
  } catch (error) {
    if (window.Notifications) {
      window.Notifications.error(`Failed to revoke link: ${error.message}`);
    }
  }
};

const showCopyAnimation = (element) => {
  if (!element) return;

  const existing = element.querySelector(".copy-animation-overlay");
  if (existing) {
    existing.remove();
  }

  const computedStyle = window.getComputedStyle(element);
  if (computedStyle.position === "static") {
    element.style.position = "relative";
  }

  // Create overlay
  const overlay = document.createElement("div");
  overlay.className = "copy-animation-overlay copy-animation-active";

  const checkmark = document.createElement("div");
  checkmark.className =
    "copy-animation-checkmark copy-animation-checkmark-active";
  checkmark.textContent = "✓";

  overlay.appendChild(checkmark);
  element.appendChild(overlay);

  // Remove after animation
  setTimeout(() => {
    overlay.classList.add("copy-animation-hide");
    setTimeout(() => {
      if (overlay.parentNode) {
        overlay.remove();
      }
    }, 300);
  }, 1000);
};

// Watch for show prop changes
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      loadActiveLinks();
      if (modalManager) {
        modalManager.open("share-file", () => {}, close);
      }
    } else {
      if (modalManager) {
        modalManager.close();
      }
    }
  },
);

// Load links when component mounts if already shown
onMounted(async () => {
  await loadBaseUrl();
  if (props.show) {
    loadActiveLinks();
  }
});
</script>

<style scoped>
.modal-overlay {
  position: fixed !important;
  inset: 0 !important;
  background: rgba(0, 0, 0, 0.7) !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  z-index: 10000 !important;
  padding: 1rem !important;
  opacity: 1 !important;
  visibility: visible !important;
}

.modal {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border-color);
  width: -webkit-fill-available;
}

.modal-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-close {
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: var(--accent);
  color: var(--text-primary);
}

.share-modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
  text-align: left;
  width: 100%;
}

.share-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  text-align: left;
  align-items: flex-start;
}

.share-section-create {
  margin-top: 0;
  padding-top: 0;
}

.share-section:not(:last-child) {
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.share-section:not(:first-of-type) {
  padding-top: 0;
  margin-top: 0;
}

.share-section h3 {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 1rem 0;
  padding: 0;
  text-align: left;
}

.share-section:first-of-type h3 {
  margin-top: 0;
}

.share-section:not(:first-of-type) h3 {
  margin-top: 0;
}

.share-link-form {
  text-align: left;
}

.share-link-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  text-align: left;
}

.share-link-options .form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.share-link-options label {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  color: var(--text-primary);
  font-size: 0.9rem;
  cursor: pointer;
  user-select: none;
  padding: 0.25rem 0;
}

.share-link-options label:hover {
  color: var(--text-primary);
}

.share-link-options input[type="checkbox"] {
  width: auto;
  margin: 0;
  cursor: pointer;
  flex-shrink: 0;
}

.share-link-options label span {
  flex: 1;
}

.share-date-input,
.share-number-input {
  width: 100%;
  max-width: 100%;
  padding: 0.625rem 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  font-size: 0.9rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.share-password-input-wrapper {
  position: relative;
  display: block;
  width: 100%;
}

.share-password-input {
  width: 100%;
  max-width: 100%;
  padding: 0.625rem 2.5rem 0.625rem 0.75rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  font-size: 0.9rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
}

.share-password-input-wrapper .password-toggle {
  position: absolute;
  right: 0.5rem;
  top: 50%;
  margin-top: -12px;
  background: transparent;
  border: none;
  color: var(--text-muted, #a9b7aa);
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

.share-password-input-wrapper .password-toggle:hover {
  opacity: 1;
  color: var(--text-primary, #a9b7aa);
}

.share-password-input-wrapper .password-toggle:active {
  opacity: 0.8;
}

.share-password-input-wrapper .password-toggle:focus {
  outline: none;
}

.share-password-input-wrapper .password-toggle-icon {
  display: block;
  width: 1.125rem;
  height: 1.125rem;
}

.share-password-input-wrapper .password-toggle-icon--show {
  display: none;
}

.share-password-input-wrapper
  .password-toggle.is-visible
  .password-toggle-icon--hide {
  display: none;
}

.share-password-input-wrapper
  .password-toggle.is-visible
  .password-toggle-icon--show {
  display: block;
}

.share-date-input:focus,
.share-number-input:focus,
.share-password-input:focus {
  outline: none;
  border-color: rgba(0, 66, 37, 0.5);
  background: rgba(255, 255, 255, 0.08);
}

.share-date-input::placeholder,
.share-number-input::placeholder {
  color: rgba(203, 213, 225, 0.5);
}

.share-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.5rem;
  justify-content: flex-end;
  width: -webkit-fill-available;
}

.loading-links {
  padding: 1rem 0;
  text-align: left;
  color: var(--text-primary);
}

.share-empty {
  text-align: center;
  color: var(--text-primary);
  padding: 0;
  font-size: 0.9rem;
  width: 100%;
  align-self: flex-start;
}

.share-empty p {
  text-align: center;
  margin: 0;
  width: 100%;
}

.active-links-list {
  max-height: 300px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.active-links-list::-webkit-scrollbar {
  width: 6px;
}

.active-links-list::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
}

.active-links-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
}

.active-links-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.25);
}

.active-link-item {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  border-bottom: 1px solid var(--ash-grey);
  transition: all 0.2s ease;
}

.active-link-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.12);
}

.active-link-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
  position: relative;
}

.active-link-url {
  font-size: 0.85rem;
  color: var(--text-primary);
  word-break: break-all;
  font-family: monospace;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--slate-grey);
  position: relative;
}

.active-link-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-primary);
}

.active-link-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex-shrink: 0;
  align-items: flex-end;
}

.btn {
  padding: 0.75rem 1.5rem;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid var(--accent);
  background: transparent;
  color: var(--text-primary);
}

.btn-primary {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--text-primary);
}

.btn-primary:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.1);
  border-color: var(--accent);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-small {
  padding: 0.375rem 0.75rem;
  font-size: 0.85rem;
}

.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;
  color: #fca5a5;
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.3);
  border-color: rgba(239, 68, 68, 0.4);
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
}

.copy-animation-overlay.copy-animation-active {
  opacity: 1;
}

.copy-animation-overlay.copy-animation-hide {
  opacity: 0;
}

.copy-animation-checkmark {
  font-size: 1.5rem;
  color: #a9b7aa;
  font-weight: bold;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  opacity: 0;
  transform: scale(0.5);
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}

.copy-animation-checkmark.copy-animation-checkmark-active {
  opacity: 1;
  transform: scale(1);
}
</style>
