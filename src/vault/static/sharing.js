/** @file sharing.js - Share file with download links */

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

  // Fallback: use DOM API instead of innerHTML for better security on browsers without Trusted Types
  const temp = document.createElement("div");
  temp.innerHTML = html;
  while (temp.firstChild) {
    element.appendChild(temp.firstChild);
  }
}

class SharingManager {
  constructor() {
    this.currentFileId = null;
    this.currentFileKey = null;
    this.modalCreated = false;
    // Store event handlers to allow removal
    this.eventHandlers = {
      closeBtn: null,
      createBtn: null,
      linkExpiresCheckbox: null,
      linkMaxDownloadsCheckbox: null,
      linkPasswordCheckbox: null,
      passwordToggle: null,
      modal: null,
      escapeKey: null,
    };
    // Flag to prevent double-click
    this.isCreatingLink = false;
    // Don't initialize modal immediately - create it lazily when needed
    // this.init();
  }

  async ensureModalCreated() {
    if (this.modalCreated || document.getElementById("share-modal-advanced")) {
      this.modalCreated = true;
      return;
    }

    // Check if Trusted Types is supported by the browser
    const trustedTypesSupported = !!(
      window.trustedTypes && window.trustedTypes.createPolicy
    );

    // Check if Trusted Types policies are available
    const hasPolicies =
      window.vaultHTMLPolicy ||
      (window.trustedTypes && window.trustedTypes.defaultPolicy);

    // If Trusted Types is not supported by the browser, proceed without waiting
    // (we'll use DOM API methods instead of innerHTML)
    if (!trustedTypesSupported) {
      await this.createShareModal();
      this.modalCreated = true;
      return;
    }

    // If Trusted Types is supported but policies aren't ready yet, wait and retry
    if (!hasPolicies) {
      // Policies not available yet, wait and retry
      return new Promise((resolve) => {
        setTimeout(async () => {
          await this.ensureModalCreated();
          resolve();
        }, 100);
      });
    }

    // Policies are available, create modal
    await this.createShareModal();
    this.modalCreated = true;
  }

  /**
   * Create share modal
   */
  async createShareModal() {
    if (document.getElementById("share-modal-advanced")) {
      this.modalCreated = true;
      return;
    }

    // Ensure document.body exists
    if (!document.body) {
      setTimeout(() => this.createShareModal(), 100);
      return;
    }

    // Check if Trusted Types is supported by the browser
    const trustedTypesSupported = !!(
      window.trustedTypes && window.trustedTypes.createPolicy
    );

    // Check if Trusted Types policies are available
    const hasPolicies =
      window.vaultHTMLPolicy ||
      (window.trustedTypes && window.trustedTypes.defaultPolicy);

    // If Trusted Types is not supported, use DOM API to create modal
    if (!trustedTypesSupported) {
      this.createShareModalWithDOM();
      return;
    }

    // If Trusted Types is supported but policies aren't available, use fallback
    // (This shouldn't happen if ensureModalCreated() worked correctly, but it's a safety net)
    if (!hasPolicies) {
      console.warn(
        "[SharingManager] Trusted Types supported but policies not available, using DOM API fallback",
      );
      this.createShareModalWithDOM();
      return;
    }

    const modalHTML = `
      <div id="share-modal-advanced" class="modal-overlay hidden" aria-hidden="true">
        <div class="modal-container modal-large">
          <div class="modal-content-share">
            <div class="modal-header">
              <h2 class="modal-title">Share File</h2>
              <button class="modal-close" id="share-modal-close">&times;</button>
            </div>
            <div class="share-modal-body">
              <!-- Create New Link Section -->
              <form id="share-link-form" onsubmit="return false;">
              <div class="share-section">
                <h3>Create Share Link</h3>
                <div class="share-link-options">
                  <div class="form-group">
                    <label>
                      <input type="checkbox" id="share-link-expires" />
                      <span>Set expiration date</span>
                    </label>
                    <input 
                      type="datetime-local" 
                      id="share-link-expires-date" 
                      class="share-date-input hidden" 
                    />
                  </div>
                  <div class="form-group">
                    <label>
                      <input type="checkbox" id="share-link-max-downloads" />
                      <span>Limit number of downloads</span>
                    </label>
                    <input 
                      type="number" 
                      id="share-link-max-downloads-input" 
                      class="share-number-input hidden" 
                      placeholder="Number of downloads"
                      min="1"
                    />
                  </div>
                  <div class="form-group">
                    <label>
                      <input type="checkbox" id="share-link-password" />
                      <span>Protect with password</span>
                    </label>
                    <div class="share-password-input-wrapper hidden" id="share-link-password-wrapper">
                      <input 
                        type="password" 
                        id="share-link-password-input" 
                        class="share-password-input" 
                        placeholder="Enter password"
                        autocomplete="off"
                        form="share-link-form"
                      />
                      <button
                        type="button"
                        class="password-toggle"
                        id="share-link-password-toggle"
                        aria-label="Show password"
                        data-password-toggle
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
                </div>
                <div class="share-actions">
                  <button id="create-share-link-btn" class="btn btn-primary">Create Share Link</button>
                </div>
              </div>

              <!-- Active Links Section -->
              <div class="share-section">
                <h3>Active Share Links</h3>
                <div id="active-links-list" class="active-links-list">
                  <p class="share-empty">No active share links</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;

    // Create and insert modal HTML
    try {
      // Remove existing modal if any
      const existing = document.getElementById("share-modal-advanced");
      if (existing) {
        existing.remove();
      }

      let inserted = false;

      // Try using Trusted Types policies
      if (window.vaultHTMLPolicy) {
        try {
          const safeHTML = window.vaultHTMLPolicy.createHTML(modalHTML);
          document.body.insertAdjacentHTML("beforeend", safeHTML);
          inserted = true;
        } catch (e) {
          console.error("Failed to use vaultHTMLPolicy:", e);
          // Don't try fallback here - Trusted Types is required
        }
      } else if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
        try {
          const safeHTML =
            window.trustedTypes.defaultPolicy.createHTML(modalHTML);
          document.body.insertAdjacentHTML("beforeend", safeHTML);
          inserted = true;
        } catch (e) {
          console.error("Failed to use defaultPolicy:", e);
        }
      } else {
        // Fallback: use DOM API to create modal
        this.createShareModalWithDOM();
        inserted = true;
      }

      if (!inserted) {
        throw new Error("Failed to insert modal HTML - all methods failed");
      }

      // Wait a bit for DOM to update
      await new Promise((resolve) => setTimeout(resolve, 10));

      // Wait a bit longer for DOM to fully update
      await new Promise((resolve) => setTimeout(resolve, 50));

      // Verify modal was created
      const createdModal = document.getElementById("share-modal-advanced");
      if (!createdModal) {
        console.error("Modal element not found after insertion!");
        throw new Error("Modal element was not created in DOM");
      }

      // Check the actual DOM structure
      const modalContent = createdModal.querySelector(".modal-content-share");

      if (!modalContent) {
        console.error("Modal content not found!");
        throw new Error("Modal content element not found");
      }

      this.modalCreated = true;

      // Setup event listeners after a short delay to ensure DOM is ready
      setTimeout(() => {
        this.setupShareModalListeners();
      }, 50);
    } catch (e) {
      console.error("Failed to create share modal:", e);
      console.error("Error details:", e.message);
      console.error("Stack:", e.stack);

      // If all else fails, retry later
      if (!this.modalCreated) {
        console.warn(
          "Will retry modal creation after Trusted Types policies are available",
        );
        setTimeout(() => {
          if (!document.getElementById("share-modal-advanced")) {
            this.createShareModal();
          }
        }, 500);
      }
      return;
    }
  }

  /**
   * Create share modal using DOM API (for browsers without Trusted Types support)
   */
  createShareModalWithDOM() {
    // Remove existing modal if any
    const existing = document.getElementById("share-modal-advanced");
    if (existing) {
      existing.remove();
    }

    // Create modal overlay
    const overlay = document.createElement("div");
    overlay.id = "share-modal-advanced";
    overlay.className = "modal-overlay hidden";
    overlay.setAttribute("aria-hidden", "true");

    // Create modal container
    const container = document.createElement("div");
    container.className = "modal-container modal-large";

    // Create modal content
    const content = document.createElement("div");
    content.className = "modal-content-share";

    // Create modal header
    const header = document.createElement("div");
    header.className = "modal-header";
    const title = document.createElement("h2");
    title.className = "modal-title";
    title.textContent = "Share File";
    const closeBtn = document.createElement("button");
    closeBtn.className = "modal-close";
    closeBtn.id = "share-modal-close";
    closeBtn.textContent = "×";
    header.appendChild(title);
    header.appendChild(closeBtn);

    // Create modal body
    const body = document.createElement("div");
    body.className = "share-modal-body";

    // Create form for share link creation
    const shareForm = document.createElement("form");
    shareForm.id = "share-link-form";
    shareForm.onsubmit = function (e) {
      e.preventDefault();
      return false;
    };

    // Create "Create New Link" section
    const createSection = document.createElement("div");
    createSection.className = "share-section";
    const createTitle = document.createElement("h3");
    createTitle.textContent = "Create Share Link";
    createSection.appendChild(createTitle);

    const linkOptions = document.createElement("div");
    linkOptions.className = "share-link-options";

    // Expiration date option
    const expiresGroup = document.createElement("div");
    expiresGroup.className = "form-group";
    const expiresLabel = document.createElement("label");
    const expiresCheckbox = document.createElement("input");
    expiresCheckbox.type = "checkbox";
    expiresCheckbox.id = "share-link-expires";
    const expiresSpan = document.createElement("span");
    expiresSpan.textContent = "Set expiration date";
    expiresLabel.appendChild(expiresCheckbox);
    expiresLabel.appendChild(expiresSpan);
    const expiresDateInput = document.createElement("input");
    expiresDateInput.type = "datetime-local";
    expiresDateInput.id = "share-link-expires-date";
    expiresDateInput.className = "share-date-input hidden";
    expiresGroup.appendChild(expiresLabel);
    expiresGroup.appendChild(expiresDateInput);
    linkOptions.appendChild(expiresGroup);

    // Max downloads option
    const maxDownloadsGroup = document.createElement("div");
    maxDownloadsGroup.className = "form-group";
    const maxDownloadsLabel = document.createElement("label");
    const maxDownloadsCheckbox = document.createElement("input");
    maxDownloadsCheckbox.type = "checkbox";
    maxDownloadsCheckbox.id = "share-link-max-downloads";
    const maxDownloadsSpan = document.createElement("span");
    maxDownloadsSpan.textContent = "Limit number of downloads";
    maxDownloadsLabel.appendChild(maxDownloadsCheckbox);
    maxDownloadsLabel.appendChild(maxDownloadsSpan);
    const maxDownloadsInput = document.createElement("input");
    maxDownloadsInput.type = "number";
    maxDownloadsInput.id = "share-link-max-downloads-input";
    maxDownloadsInput.className = "share-number-input hidden";
    maxDownloadsInput.placeholder = "Number of downloads";
    maxDownloadsInput.min = "1";
    maxDownloadsGroup.appendChild(maxDownloadsLabel);
    maxDownloadsGroup.appendChild(maxDownloadsInput);
    linkOptions.appendChild(maxDownloadsGroup);

    // Password option
    const passwordGroup = document.createElement("div");
    passwordGroup.className = "form-group";
    const passwordLabel = document.createElement("label");
    const passwordCheckbox = document.createElement("input");
    passwordCheckbox.type = "checkbox";
    passwordCheckbox.id = "share-link-password";
    const passwordSpan = document.createElement("span");
    passwordSpan.textContent = "Protect with password";
    passwordLabel.appendChild(passwordCheckbox);
    passwordLabel.appendChild(passwordSpan);
    const passwordWrapper = document.createElement("div");
    passwordWrapper.className = "share-password-input-wrapper hidden";
    passwordWrapper.id = "share-link-password-wrapper";
    const passwordInput = document.createElement("input");
    passwordInput.type = "password";
    passwordInput.id = "share-link-password-input";
    passwordInput.className = "share-password-input";
    passwordInput.placeholder = "Enter password";
    passwordInput.autocomplete = "off";
    passwordInput.setAttribute("form", "share-link-form");
    const passwordToggle = document.createElement("button");
    passwordToggle.type = "button";
    passwordToggle.className = "password-toggle";
    passwordToggle.id = "share-link-password-toggle";
    passwordToggle.setAttribute("aria-label", "Show password");
    passwordToggle.setAttribute("data-password-toggle", "");
    // Add SVG icons for password toggle (simplified - just text for now)
    passwordToggle.textContent = "👁";
    passwordWrapper.appendChild(passwordInput);
    passwordWrapper.appendChild(passwordToggle);
    passwordGroup.appendChild(passwordLabel);
    passwordGroup.appendChild(passwordWrapper);
    linkOptions.appendChild(passwordGroup);

    createSection.appendChild(linkOptions);

    // Create button
    const actions = document.createElement("div");
    actions.className = "share-actions";
    const createBtn = document.createElement("button");
    createBtn.id = "create-share-link-btn";
    createBtn.className = "btn btn-primary";
    createBtn.type = "button";
    createBtn.textContent = "Create Share Link";
    actions.appendChild(createBtn);
    createSection.appendChild(actions);

    // Add create section to form
    shareForm.appendChild(createSection);

    // Create "Active Links" section
    const activeSection = document.createElement("div");
    activeSection.className = "share-section";
    const activeTitle = document.createElement("h3");
    activeTitle.textContent = "Active Share Links";
    const activeList = document.createElement("div");
    activeList.id = "active-links-list";
    activeList.className = "active-links-list";
    const emptyMsg = document.createElement("p");
    emptyMsg.className = "share-empty";
    emptyMsg.textContent = "No active share links";
    activeList.appendChild(emptyMsg);
    activeSection.appendChild(activeTitle);
    activeSection.appendChild(activeList);

    // Assemble modal
    body.appendChild(shareForm);
    body.appendChild(activeSection);
    content.appendChild(header);
    content.appendChild(body);
    container.appendChild(content);
    overlay.appendChild(container);
    document.body.appendChild(overlay);

    this.modalCreated = true;

    // Setup event listeners
    setTimeout(() => {
      this.setupShareModalListeners();
    }, 50);
  }

  /**
   * Remove existing event listeners
   */
  removeShareModalListeners() {
    const modal = document.getElementById("share-modal-advanced");
    const closeBtn = document.getElementById("share-modal-close");
    const createBtn = document.getElementById("create-share-link-btn");
    const linkExpiresCheckbox = document.getElementById("share-link-expires");
    const linkMaxDownloadsCheckbox = document.getElementById(
      "share-link-max-downloads",
    );
    const linkPasswordCheckbox = document.getElementById("share-link-password");

    // Remove existing listeners if they exist
    if (closeBtn && this.eventHandlers.closeBtn) {
      closeBtn.removeEventListener("click", this.eventHandlers.closeBtn);
      this.eventHandlers.closeBtn = null;
    }

    if (createBtn && this.eventHandlers.createBtn) {
      createBtn.removeEventListener("click", this.eventHandlers.createBtn);
      this.eventHandlers.createBtn = null;
    }

    if (linkExpiresCheckbox && this.eventHandlers.linkExpiresCheckbox) {
      linkExpiresCheckbox.removeEventListener(
        "change",
        this.eventHandlers.linkExpiresCheckbox,
      );
      this.eventHandlers.linkExpiresCheckbox = null;
    }

    if (
      linkMaxDownloadsCheckbox &&
      this.eventHandlers.linkMaxDownloadsCheckbox
    ) {
      linkMaxDownloadsCheckbox.removeEventListener(
        "change",
        this.eventHandlers.linkMaxDownloadsCheckbox,
      );
      this.eventHandlers.linkMaxDownloadsCheckbox = null;
    }

    if (linkPasswordCheckbox && this.eventHandlers.linkPasswordCheckbox) {
      linkPasswordCheckbox.removeEventListener(
        "change",
        this.eventHandlers.linkPasswordCheckbox,
      );
      this.eventHandlers.linkPasswordCheckbox = null;
    }

    const passwordToggle = document.getElementById(
      "share-link-password-toggle",
    );
    if (passwordToggle && this.eventHandlers.passwordToggle) {
      passwordToggle.removeEventListener(
        "click",
        this.eventHandlers.passwordToggle,
      );
      this.eventHandlers.passwordToggle = null;
    }

    if (modal && this.eventHandlers.modal) {
      modal.removeEventListener("click", this.eventHandlers.modal);
      this.eventHandlers.modal = null;
    }

    if (this.eventHandlers.escapeKey) {
      document.removeEventListener("keydown", this.eventHandlers.escapeKey);
      this.eventHandlers.escapeKey = null;
    }
  }

  /**
   * Setup share modal event listeners
   */
  setupShareModalListeners() {
    // Remove existing listeners first to prevent duplicates
    this.removeShareModalListeners();

    const modal = document.getElementById("share-modal-advanced");
    const closeBtn = document.getElementById("share-modal-close");
    const createBtn = document.getElementById("create-share-link-btn");
    const linkExpiresCheckbox = document.getElementById("share-link-expires");
    const linkMaxDownloadsCheckbox = document.getElementById(
      "share-link-max-downloads",
    );
    const linkPasswordCheckbox = document.getElementById("share-link-password");

    if (closeBtn) {
      // Remove any existing handler first
      if (this.eventHandlers.closeBtn) {
        closeBtn.removeEventListener(
          "click",
          this.eventHandlers.closeBtn,
          true,
        );
      }

      this.eventHandlers.closeBtn = (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        // Remove focus before hiding to prevent accessibility violations
        if (document.activeElement === closeBtn) {
          closeBtn.blur();
        }
        // Call hideModal directly
        this.hideModal();
      };
      // Use capture phase to ensure this handler runs first
      closeBtn.addEventListener("click", this.eventHandlers.closeBtn, true);

      // Also handle mousedown to prevent any issues
      closeBtn.addEventListener(
        "mousedown",
        (e) => {
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();
        },
        true,
      );

      // Also handle mouseup to ensure click works
      closeBtn.addEventListener(
        "mouseup",
        (e) => {
          e.preventDefault();
          e.stopPropagation();
        },
        true,
      );
    } else {
      console.error("Close button not found!");
    }

    if (createBtn) {
      this.eventHandlers.createBtn = () => {
        // Prevent double-click
        if (this.isCreatingLink) {
          console.warn("Share link creation already in progress");
          return;
        }
        this.createShareLink();
      };
      createBtn.addEventListener("click", this.eventHandlers.createBtn);
    }

    if (linkExpiresCheckbox) {
      this.eventHandlers.linkExpiresCheckbox = (e) => {
        const dateInput = document.getElementById("share-link-expires-date");
        if (dateInput) {
          dateInput.classList.toggle("hidden", !e.target.checked);
          if (!e.target.checked) {
            dateInput.value = "";
          }
        }
      };
      linkExpiresCheckbox.addEventListener(
        "change",
        this.eventHandlers.linkExpiresCheckbox,
      );
    }

    if (linkMaxDownloadsCheckbox) {
      this.eventHandlers.linkMaxDownloadsCheckbox = (e) => {
        const numberInput = document.getElementById(
          "share-link-max-downloads-input",
        );
        if (numberInput) {
          numberInput.classList.toggle("hidden", !e.target.checked);
          if (!e.target.checked) {
            numberInput.value = "";
          }
        }
      };
      linkMaxDownloadsCheckbox.addEventListener(
        "change",
        this.eventHandlers.linkMaxDownloadsCheckbox,
      );
    }

    if (linkPasswordCheckbox) {
      this.eventHandlers.linkPasswordCheckbox = (e) => {
        const passwordWrapper = document.getElementById(
          "share-link-password-wrapper",
        );
        if (passwordWrapper) {
          passwordWrapper.classList.toggle("hidden", !e.target.checked);
          if (!e.target.checked) {
            const passwordInput = document.getElementById(
              "share-link-password-input",
            );
            if (passwordInput) {
              passwordInput.value = "";
              passwordInput.type = "password";
            }
            const passwordToggle = document.getElementById(
              "share-link-password-toggle",
            );
            if (passwordToggle) {
              passwordToggle.classList.remove("is-visible");
              passwordToggle.setAttribute("aria-label", "Show password");
            }
          }
        }
      };
      linkPasswordCheckbox.addEventListener(
        "change",
        this.eventHandlers.linkPasswordCheckbox,
      );
    }

    // Setup password toggle functionality
    const passwordToggle = document.getElementById(
      "share-link-password-toggle",
    );
    const passwordInput = document.getElementById("share-link-password-input");

    if (passwordToggle && passwordInput) {
      const showIcon = passwordToggle.querySelector(
        ".password-toggle-icon--show",
      );
      const hideIcon = passwordToggle.querySelector(
        ".password-toggle-icon--hide",
      );

      if (showIcon && hideIcon) {
        this.eventHandlers.passwordToggle = (event) => {
          event.preventDefault();
          const isPassword = passwordInput.type === "password";

          if (isPassword) {
            passwordInput.type = "text";
            passwordToggle.setAttribute("aria-label", "Hide password");
            passwordToggle.classList.add("is-visible");
          } else {
            passwordInput.type = "password";
            passwordToggle.setAttribute("aria-label", "Show password");
            passwordToggle.classList.remove("is-visible");
          }
        };
        passwordToggle.addEventListener(
          "click",
          this.eventHandlers.passwordToggle,
        );
      }
    }

    // Close on overlay click (click outside modal content)
    if (modal) {
      // Remove any existing handler first
      if (this.eventHandlers.modal) {
        modal.removeEventListener("click", this.eventHandlers.modal);
      }

      this.eventHandlers.modal = (e) => {
        // Don't close if clicking on the close button or its children
        if (e.target.closest("#share-modal-close")) {
          return;
        }
        // Don't close if clicking inside modal content
        if (e.target.closest(".modal-container")) {
          return;
        }
        // Only close if clicking directly on the overlay
        if (
          e.target === modal ||
          e.target.classList.contains("modal-overlay")
        ) {
          this.hideModal();
        }
      };
      // Use bubbling phase (default) so close button handler runs first in capture
      modal.addEventListener("click", this.eventHandlers.modal, false);
    }

    // Close on Escape
    this.eventHandlers.escapeKey = (e) => {
      if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
        this.hideModal();
      }
    };
    document.addEventListener("keydown", this.eventHandlers.escapeKey);
  }

  /**
   * Show share modal for file
   * @param {string} fileId - File ID
   * @param {string} fileType - File type ('file' or 'folder')
   * @param {string} vaultspaceId - VaultSpace ID (optional, for API key retrieval)
   * @param {CryptoKey} vaultspaceKey - Decrypted VaultSpace key (optional, for key decryption)
   */
  async showShareModal(
    fileId,
    fileType = "file",
    vaultspaceId = null,
    vaultspaceKey = null,
  ) {
    this.currentFileId = fileId;

    // Ensure modal is created before showing it
    await this.ensureModalCreated();

    // Wait for modal to be created (with timeout)
    let modalReady = false;
    for (let i = 0; i < 40; i++) {
      if (document.getElementById("share-modal-advanced")) {
        modalReady = true;
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }

    if (!modalReady) {
      console.error("Share modal failed to be created");
      if (window.Notifications) {
        window.Notifications.error(
          "Failed to open share dialog. Please refresh the page.",
        );
      }
      return;
    }

    // Get file key from localStorage directly (same method as getFileKey in files.js)
    let fileKey = null;
    try {
      // Try to get key from localStorage first
      const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
      const keyStr = keys[fileId];
      if (keyStr) {
        // Use VaultCrypto if available (from vault.js or global)
        if (window.VaultCrypto && window.VaultCrypto.base64urlToArray) {
          fileKey = window.VaultCrypto.base64urlToArray(keyStr);
        } else {
          // Fallback: try to decode base64url manually
          console.warn("VaultCrypto not available, trying fallback");
          try {
            const binaryString = atob(
              keyStr.replace(/-/g, "+").replace(/_/g, "/"),
            );
            fileKey = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              fileKey[i] = binaryString.charCodeAt(i);
            }
          } catch (e) {
            console.error("Failed to decode key:", e);
            fileKey = null;
          }
        }
      }
    } catch (e) {
      console.warn("Failed to get file key from localStorage:", e);
      fileKey = null;
    }

    // If not in localStorage, try to get from global function
    if (!fileKey) {
      if (typeof getFileKey === "function") {
        fileKey = getFileKey(fileId);
      } else if (window.getFileKey) {
        fileKey = window.getFileKey(fileId);
      }
    }

    // If still not found and we have vaultspaceId and vaultspaceKey, try to get from API
    if (!fileKey && vaultspaceId && vaultspaceKey) {
      try {
        const jwtToken = localStorage.getItem("jwt_token");

        if (!jwtToken) {
          console.warn("JWT token not found, cannot fetch file key from API");
          return;
        }

        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${jwtToken}`,
        };

        const response = await fetch(
          `/api/v2/files/${fileId}?vaultspace_id=${vaultspaceId}`,
          {
            headers,
            credentials: "same-origin",
          },
        );

        if (response.ok) {
          const fileData = await response.json();
          if (fileData.file_key && fileData.file_key.encrypted_key) {
            // Decrypt file key using vaultspace key
            try {
              // Use window.decryptFileKey if available (exposed from main.js)
              if (window.decryptFileKey) {
                const decryptedKey = await window.decryptFileKey(
                  vaultspaceKey,
                  fileData.file_key.encrypted_key,
                  true, // extractable: true to allow export for storage
                );
                // Convert CryptoKey to Uint8Array for storage
                const keyArrayBuffer = await crypto.subtle.exportKey(
                  "raw",
                  decryptedKey,
                );
                fileKey = new Uint8Array(keyArrayBuffer);

                // Store in localStorage for future use
                try {
                  const keys = JSON.parse(
                    localStorage.getItem("vault_keys") || "{}",
                  );
                  if (
                    window.VaultCrypto &&
                    window.VaultCrypto.arrayToBase64url
                  ) {
                    keys[fileId] = window.VaultCrypto.arrayToBase64url(fileKey);
                  } else {
                    // Fallback to base64
                    keys[fileId] = btoa(
                      String.fromCharCode.apply(null, fileKey),
                    );
                  }
                  localStorage.setItem("vault_keys", JSON.stringify(keys));
                } catch (e) {
                  console.warn("Failed to store key in localStorage:", e);
                }
              } else {
                console.warn(
                  "decryptFileKey function not available on window object",
                );
              }
            } catch (e) {
              console.error("Failed to decrypt file key:", e);
            }
          }
        }
      } catch (e) {
        console.error("Error fetching file key from API:", e);
      }
    }

    // Store the key
    this.currentFileKey = fileKey;

    if (!fileKey) {
      // Don't return - let the modal show, but warn user
      if (window.Notifications) {
        window.Notifications.warning(
          "Decryption key not found. You may need to decrypt this file first to share it.",
        );
      }
    }

    // Show the modal
    const modalEl = document.getElementById("share-modal-advanced");
    if (!modalEl) {
      console.error("Share modal element not found after creation");
      if (window.Notifications) {
        window.Notifications.error(
          "Failed to open share dialog. Please refresh the page.",
        );
      }
      return;
    }

    // CRITICAL: Remove focus from any element that might have it before showing modal
    // This prevents accessibility violations
    const previouslyFocused = document.activeElement;
    if (previouslyFocused && modalEl.contains(previouslyFocused)) {
      previouslyFocused.blur();
    }

    // CRITICAL: Set aria-hidden to false FIRST (before removing hidden class)
    // This prevents accessibility violations - must be done before removing hidden
    // Use setAttribute with explicit value to ensure it's set correctly
    modalEl.setAttribute("aria-hidden", "false");

    // CRITICAL: Remove hidden class AFTER setting aria-hidden
    // This ensures the modal is accessible when it becomes visible
    modalEl.classList.remove("hidden");

    // Set initial state for fade in animation (opacity 0, visible for transition)
    modalEl.style.setProperty("display", "flex", "important");
    modalEl.style.setProperty("opacity", "0", "important");
    modalEl.style.setProperty("visibility", "visible", "important");

    // Add transition for smooth fade in
    modalEl.style.setProperty(
      "transition",
      "opacity 0.3s ease, visibility 0.3s ease",
      "important",
    );

    // Get modal container for scale animation (will be used later too)
    let modalContainerForAnimation = modalEl.querySelector(".modal-container");
    if (modalContainerForAnimation) {
      // Set initial transform state
      modalContainerForAnimation.style.setProperty(
        "transform",
        "scale(0.95) translateY(20px)",
        "important",
      );
      modalContainerForAnimation.style.setProperty(
        "transition",
        "transform 0.3s cubic-bezier(0.22, 1, 0.36, 1)",
        "important",
      );
    }

    // Force a reflow to ensure changes are processed
    void modalEl.offsetHeight;

    // Start fade in animation after a tiny delay to ensure initial state is applied
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        modalEl.style.setProperty("opacity", "1", "important");
        if (modalContainerForAnimation) {
          modalContainerForAnimation.style.setProperty(
            "transform",
            "scale(1) translateY(0)",
            "important",
          );
        }
      });
    });

    // Set up a MutationObserver to prevent aria-hidden from being set back to true
    // This ensures the modal stays accessible
    // But only when the modal is actually visible (not being closed)
    if (!this.ariaHiddenObserver) {
      this.isClosing = false; // Flag to prevent observer from interfering with closing
      this.ariaHiddenObserver = new MutationObserver((mutations) => {
        // Don't interfere if we're in the process of closing
        if (this.isClosing) {
          return;
        }

        mutations.forEach((mutation) => {
          if (
            mutation.type === "attributes" &&
            mutation.attributeName === "aria-hidden"
          ) {
            const modal = document.getElementById("share-modal-advanced");
            // Only correct if modal is visible (no hidden class) and we're not closing
            if (
              modal &&
              !modal.classList.contains("hidden") &&
              !this.isClosing
            ) {
              // If modal is visible but aria-hidden is being set to true, prevent it
              if (modal.getAttribute("aria-hidden") === "true") {
                console.warn(
                  "Prevented aria-hidden from being set to true on visible modal",
                );
                modal.setAttribute("aria-hidden", "false");
              }
            }
          }
          if (
            mutation.type === "attributes" &&
            mutation.attributeName === "class"
          ) {
            const modal = document.getElementById("share-modal-advanced");
            // Only correct if modal is accessible and we're not closing
            if (
              modal &&
              modal.getAttribute("aria-hidden") === "false" &&
              !this.isClosing
            ) {
              // If modal is accessible but hidden class is being added, prevent it
              if (modal.classList.contains("hidden")) {
                console.warn(
                  "Prevented hidden class from being added to accessible modal",
                );
                modal.classList.remove("hidden");
              }
            }
          }
        });
      });
    }

    // Start observing the modal for attribute changes
    this.ariaHiddenObserver.observe(modalEl, {
      attributes: true,
      attributeFilter: ["aria-hidden", "class"],
    });

    // Double-check that aria-hidden is false and hidden class is removed
    // Use requestAnimationFrame to ensure DOM updates are complete
    requestAnimationFrame(() => {
      if (modalEl.getAttribute("aria-hidden") !== "false") {
        modalEl.setAttribute("aria-hidden", "false");
      }
      if (modalEl.classList.contains("hidden")) {
        modalEl.classList.remove("hidden");
      }

      // Verify the modal is actually visible
      const computedStyle = window.getComputedStyle(modalEl);
      if (
        computedStyle.display === "none" ||
        computedStyle.visibility === "hidden"
      ) {
        console.warn(
          "Modal is still hidden after show attempt, forcing visibility",
        );
        modalEl.style.setProperty("display", "flex", "important");
        modalEl.style.setProperty("visibility", "visible", "important");
        modalEl.setAttribute("aria-hidden", "false");
        modalEl.classList.remove("hidden");
      }
    });

    // Verify styles after changes
    const computedStyle = window.getComputedStyle(modalEl);

    // If still hidden, force visibility
    if (computedStyle.display === "none") {
      modalEl.style.setProperty("display", "flex", "important");
    }
    if (computedStyle.visibility === "hidden") {
      modalEl.style.setProperty("visibility", "visible", "important");
    }
    if (parseFloat(computedStyle.opacity) < 0.1) {
      modalEl.style.setProperty("opacity", "1", "important");
    }

    // Ensure z-index is high enough
    const currentZIndex = parseInt(computedStyle.zIndex) || 0;
    if (currentZIndex < 9999) {
      modalEl.style.setProperty("z-index", "99999", "important");
    }

    // Verify modal content exists and get references
    const modalContent = modalEl.querySelector(".modal-content-share");
    const modalContainer = modalEl.querySelector(".modal-container");

    // Ensure modal container is visible
    if (modalContainer) {
      const containerComputedStyle = window.getComputedStyle(modalContainer);
      const containerRect = modalContainer.getBoundingClientRect();

      if (containerComputedStyle.display === "none") {
        modalContainer.style.setProperty("display", "block", "important");
      }

      // Ensure container has dimensions
      if (containerRect.width === 0 || containerRect.height === 0) {
        modalContainer.style.setProperty("width", "100%", "important");
        modalContainer.style.setProperty("max-width", "600px", "important");
      }
    }

    // Ensure modal content is visible
    if (modalContent) {
      const contentComputedStyle = window.getComputedStyle(modalContent);
      const contentRect = modalContent.getBoundingClientRect();

      if (contentComputedStyle.display === "none") {
        modalContent.style.setProperty("display", "block", "important");
      }

      // If content has no dimensions, force it
      if (contentRect.width === 0 || contentRect.height === 0) {
        modalContent.style.setProperty("min-width", "400px", "important");
        modalContent.style.setProperty("min-height", "200px", "important");
      }

      // Ensure content is above backdrop (z-index)
      const contentZIndex = parseInt(contentComputedStyle.zIndex) || 0;
      if (contentZIndex <= 0) {
        modalContent.style.setProperty("position", "relative", "important");
        modalContent.style.setProperty("z-index", "10", "important");
      }
    }

    // Check if children are actually in the DOM
    if (modalContent) {
      const header = modalContent.querySelector(".modal-header");
      const body = modalContent.querySelector(".share-modal-body");

      if (header) {
        const title = header.querySelector("h2.modal-title");
        // Force header to be visible
        header.style.setProperty("display", "block", "important");
        header.style.setProperty("visibility", "visible", "important");
        if (title) {
          title.style.setProperty("color", "#e6eef6", "important");
        }
      }

      if (body) {
        body.style.setProperty("display", "block", "important");
        body.style.setProperty("visibility", "visible", "important");
      }

      // Force all children to be visible
      Array.from(modalContent.children).forEach((child) => {
        child.style.setProperty("display", "block", "important");
        child.style.setProperty("visibility", "visible", "important");
      });
    }

    if (modalContainer) {
      // Make sure container children are visible
      Array.from(modalContainer.children).forEach((child) => {
        child.style.setProperty("display", "block", "important");
        child.style.setProperty("visibility", "visible", "important");
      });
    }

    // Ensure event listeners are attached
    this.setupShareModalListeners();

    // Use modal manager to prevent stacking (if available)
    let modalManager = null;
    try {
      // Try global first, then import
      modalManager = window.modalManager;
      if (!modalManager) {
        try {
          const modalManagerModule =
            await import("../src/utils/ModalManager.js");
          modalManager = modalManagerModule.modalManager;
          window.modalManager = modalManager;
        } catch (e) {
          // ModalManager not available, continue without it
          console.warn("ModalManager not available:", e);
        }
      }

      if (modalManager) {
        // Define open and close callbacks
        const openCallback = () => {
          // Modal is already shown above
        };
        const closeCallback = () => {
          // Only hide if not already closing to prevent infinite loops
          if (!this.isClosing) {
            this.hideModal();
          }
        };

        modalManager.open("share-file", openCallback, closeCallback);
      }
    } catch (e) {
      console.warn("Error using modal manager:", e);
      // Continue without modal manager - modal is already shown
    }

    // Reset form
    const expiresCheckbox = document.getElementById("share-link-expires");
    const expiresDateInput = document.getElementById("share-link-expires-date");
    const maxDownloadsCheckbox = document.getElementById(
      "share-link-max-downloads",
    );
    const maxDownloadsInput = document.getElementById(
      "share-link-max-downloads-input",
    );

    if (expiresCheckbox) expiresCheckbox.checked = false;
    if (expiresDateInput) {
      expiresDateInput.value = "";
      expiresDateInput.classList.add("hidden");
    }
    if (maxDownloadsCheckbox) maxDownloadsCheckbox.checked = false;
    if (maxDownloadsInput) {
      maxDownloadsInput.value = "";
      maxDownloadsInput.classList.add("hidden");
    }

    // Load active share links (don't block modal display if this fails)
    this.loadActiveLinks(fileId).catch((err) => {
      console.warn("Failed to load active links (non-critical):", err);
      // Show empty state in links list
      const container = document.getElementById("active-links-list");
      if (container) {
        const emptyHTML = '<p class="share-empty">No active share links</p>';
        setInnerHTML(container, emptyHTML);
      }
    });
  }

  /**
   * Hide share modal
   */
  hideModal() {
    // Prevent infinite loops - if already closing, return
    if (this.isClosing) {
      return;
    }

    const modal = document.getElementById("share-modal-advanced");
    if (!modal) {
      return;
    }

    // Set flag to prevent MutationObserver and infinite loops
    this.isClosing = true;

    // Stop observing before making changes
    if (this.ariaHiddenObserver) {
      this.ariaHiddenObserver.disconnect();
      this.ariaHiddenObserver = null;
    }

    // Remove focus from any element inside the modal before hiding
    const focusedElement = modal.querySelector(":focus");
    if (focusedElement) {
      focusedElement.blur();
    }

    // Add transition for smooth fade out
    modal.style.setProperty(
      "transition",
      "opacity 0.3s ease, visibility 0.3s ease",
      "important",
    );

    // Start fade out animation
    modal.style.setProperty("opacity", "0", "important");
    modal.style.setProperty("visibility", "hidden", "important");

    // Get modal container for scale animation
    const modalContainer = modal.querySelector(".modal-container");
    if (modalContainer) {
      modalContainer.style.setProperty(
        "transition",
        "transform 0.3s cubic-bezier(0.22, 1, 0.36, 1)",
        "important",
      );
      modalContainer.style.setProperty(
        "transform",
        "scale(0.95) translateY(20px)",
        "important",
      );
    }

    // Set aria-hidden to true
    modal.setAttribute("aria-hidden", "true");

    // Wait for transition to complete before hiding completely
    setTimeout(() => {
      // Hide completely after fade out
      modal.style.setProperty("display", "none", "important");
      modal.classList.add("hidden");

      // Reset closing flag
      this.isClosing = false;
    }, 300); // Match transition duration

    this.currentFileId = null;
    this.currentFileKey = null;

    // Don't call modalManager.close() here - it would trigger the closeCallback
    // which calls hideModal() again, creating an infinite loop
    // The modalManager should be notified separately if needed
  }

  /**
   * Load active share links
   */
  async loadActiveLinks(fileId) {
    try {
      const jwtToken = localStorage.getItem("jwt_token");

      if (!jwtToken) {
        console.warn("JWT token not found, cannot load active links");
        return;
      }

      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      };

      // Migrate to API v2 - use public-links endpoint with resource_id filter
      const response = await fetch(
        `/api/v2/sharing/public-links?resource_id=${fileId}`,
        {
          headers,
          credentials: "same-origin",
        },
      );

      if (response.ok) {
        const data = await response.json();
        // API v2 returns share_links array
        const links = data.share_links || [];
        // Map API v2 format to legacy format if needed
        const mappedLinks = links.map((link) => ({
          link_id: link.token || link.link_id,
          token: link.token,
          expires_at: link.expires_at,
          max_downloads: link.max_downloads,
          download_count: link.download_count || 0,
          is_available:
            typeof link.is_available === "boolean" ? link.is_available : true,
          is_expired: link.is_expired || false,
          share_url: link.share_url,
          has_password: link.has_password || false,
        }));
        await this.renderActiveLinks(mappedLinks, fileId);
      } else {
        console.error("API response not OK, status:", response.status);
      }
    } catch (error) {
      console.error("Error loading share links:", error);
    }
  }

  /**
   * Create share link
   */
  async createShareLink() {
    // Prevent double-click/double-execution
    if (this.isCreatingLink) {
      console.warn("Share link creation already in progress");
      return;
    }

    if (!this.currentFileId) {
      if (window.Notifications) {
        window.Notifications.error("File ID not found. Please try again.");
      }
      console.error("Cannot create share link: file ID is missing");
      return;
    }

    if (!this.currentFileKey) {
      if (window.Notifications) {
        window.Notifications.error(
          "File decryption key not found. You need to access this file first before sharing it. Please download or open the file once to decrypt it, then try sharing again.",
        );
      }
      console.error("Cannot create share link: file key is missing");
      return;
    }

    // Set flag to prevent double execution
    this.isCreatingLink = true;

    // Disable button during creation (declare here so it's accessible in finally)
    const createBtn = document.getElementById("create-share-link-btn");
    const originalText = createBtn?.textContent || "Create Share Link";
    if (createBtn) {
      createBtn.disabled = true;
      createBtn.textContent = "Creating...";
    }

    try {
      const expiresCheckbox = document.getElementById("share-link-expires");
      const expiresDateInput = document.getElementById(
        "share-link-expires-date",
      );
      const maxDownloadsCheckbox = document.getElementById(
        "share-link-max-downloads",
      );
      const maxDownloadsInput = document.getElementById(
        "share-link-max-downloads-input",
      );
      const passwordCheckbox = document.getElementById("share-link-password");
      const passwordInput = document.getElementById(
        "share-link-password-input",
      );

      let expiresInHours = null;
      if (
        expiresCheckbox &&
        expiresCheckbox.checked &&
        expiresDateInput &&
        expiresDateInput.value
      ) {
        const expiresDate = new Date(expiresDateInput.value);
        const now = new Date();
        const diffHours = Math.ceil(
          (expiresDate.getTime() - now.getTime()) / (1000 * 60 * 60),
        );
        if (diffHours > 0) {
          expiresInHours = diffHours;
        }
      }

      let maxDownloads = null;
      if (
        maxDownloadsCheckbox &&
        maxDownloadsCheckbox.checked &&
        maxDownloadsInput &&
        maxDownloadsInput.value
      ) {
        const num = parseInt(maxDownloadsInput.value, 10);
        if (num > 0) {
          maxDownloads = num;
        }
      }

      let password = null;
      if (
        passwordCheckbox &&
        passwordCheckbox.checked &&
        passwordInput &&
        passwordInput.value
      ) {
        password = passwordInput.value.trim();
        if (password === "") {
          password = null;
        }
      }

      const jwtToken = localStorage.getItem("jwt_token");

      if (!jwtToken) {
        throw new Error("Authentication required. Please log in again.");
      }

      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      };

      // Migrate to API v2 - use public-links endpoint
      // Convert expires_in_hours to expires_in_days
      const expiresInDays = expiresInHours
        ? Math.ceil(expiresInHours / 24)
        : null;

      const response = await fetch(`/api/v2/sharing/public-links`, {
        method: "POST",
        headers,
        credentials: "same-origin",
        body: JSON.stringify({
          resource_id: this.currentFileId,
          resource_type: "file",
          password: password,
          expires_in_days: expiresInDays,
          max_downloads: maxDownloads,
          allow_download: true,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to create share link");
      }

      const data = await response.json();
      const shareLink = data.share_link || data;

      // Use share_url from backend (includes VAULT_URL if configured)
      // Fallback to VAULT_URL or window.location.origin if not provided
      const linkToken = shareLink.token || shareLink.link_id;

      // Get base URL using VAULT_URL (with fallback to window.location.origin)
      let baseUrl;
      try {
        // Try to use the vault-config service if available
        if (window.getVaultBaseUrl) {
          baseUrl = await window.getVaultBaseUrl();
        } else {
          // Fallback: try to import dynamically
          const { getVaultBaseUrl } =
            await import("/static/src/services/vault-config.js");
          baseUrl = await getVaultBaseUrl();
        }
      } catch (e) {
        console.warn(
          "Failed to get vault base URL, using window.location.origin:",
          e,
        );
        baseUrl = window.location.origin;
      }

      let shareUrl = shareLink.share_url || `${baseUrl}/share/${linkToken}`;

      // Add key and file ID to fragment
      if (window.VaultCrypto && window.VaultCrypto.arrayToBase64url) {
        const keyBase64 = window.VaultCrypto.arrayToBase64url(
          this.currentFileKey,
        );
        shareUrl += `#key=${keyBase64}&file=${this.currentFileId}`;
      } else if (typeof btoa !== "undefined") {
        // Fallback to base64
        const keyArray = Array.from(this.currentFileKey);
        const keyBase64 = btoa(String.fromCharCode.apply(null, keyArray));
        shareUrl += `#key=${encodeURIComponent(keyBase64)}&file=${this.currentFileId}`;
      }

      // Show success message with link
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
        console.warn("Failed to copy to clipboard:", e);
      }

      // Reload active links after creation
      await this.loadActiveLinks(this.currentFileId);

      // Reset form
      const expiresCheckboxReset =
        document.getElementById("share-link-expires");
      const expiresDateInputReset = document.getElementById(
        "share-link-expires-date",
      );
      const maxDownloadsCheckboxReset = document.getElementById(
        "share-link-max-downloads",
      );
      const maxDownloadsInputReset = document.getElementById(
        "share-link-max-downloads-input",
      );
      const passwordCheckboxReset = document.getElementById(
        "share-link-password",
      );
      const passwordWrapperReset = document.getElementById(
        "share-link-password-wrapper",
      );
      const passwordInputReset = document.getElementById(
        "share-link-password-input",
      );
      const passwordToggleReset = document.getElementById(
        "share-link-password-toggle",
      );

      if (expiresCheckboxReset) expiresCheckboxReset.checked = false;
      if (expiresDateInputReset) {
        expiresDateInputReset.value = "";
        expiresDateInputReset.classList.add("hidden");
      }
      if (maxDownloadsCheckboxReset) maxDownloadsCheckboxReset.checked = false;
      if (maxDownloadsInputReset) {
        maxDownloadsInputReset.value = "";
        maxDownloadsInputReset.classList.add("hidden");
      }
      if (passwordCheckboxReset) passwordCheckboxReset.checked = false;
      if (passwordWrapperReset) {
        passwordWrapperReset.classList.add("hidden");
      }
      if (passwordInputReset) {
        passwordInputReset.value = "";
        passwordInputReset.type = "password";
      }
      if (passwordToggleReset) {
        passwordToggleReset.classList.remove("is-visible");
        passwordToggleReset.setAttribute("aria-label", "Show password");
      }
    } catch (error) {
      console.error("Error creating share link:", error);
      if (window.Notifications) {
        window.Notifications.error(
          `Failed to create share link: ${error.message}`,
        );
      }
    } finally {
      // Reset flag and button state
      this.isCreatingLink = false;
      if (createBtn) {
        createBtn.disabled = false;
        createBtn.textContent = originalText;
      }
    }
  }

  /**
   * Render active links
   */
  async renderActiveLinks(links, fileId) {
    const container = document.getElementById("active-links-list");
    if (!container) {
      console.error("active-links-list container not found!");
      return;
    }

    const now = new Date();
    const activeLinks = links.filter((link) => {
      if (link.is_available === false) {
        return false;
      }
      if (link.is_expired) {
        return false;
      }
      if (link.expires_at) {
        return new Date(link.expires_at) > now;
      }
      return true;
    });

    if (activeLinks.length === 0) {
      const emptyHTML = '<p class="share-empty">No active share links</p>';
      setInnerHTML(container, emptyHTML);
      return;
    }

    // Get base URL using VAULT_URL (with fallback to window.location.origin)
    let baseUrl;
    try {
      // Try to use the vault-config service if available
      if (window.getVaultBaseUrl) {
        baseUrl = await window.getVaultBaseUrl();
      } else {
        // Fallback: try to import dynamically
        const { getVaultBaseUrl } =
          await import("/static/src/services/vault-config.js");
        baseUrl = await getVaultBaseUrl();
      }
    } catch (e) {
      console.warn(
        "Failed to get vault base URL, using window.location.origin:",
        e,
      );
      baseUrl = window.location.origin;
    }

    // Get file key to include in share URL
    let fileKey = this.currentFileKey;
    if (!fileKey) {
      // Try to get key from localStorage
      try {
        const keys = JSON.parse(localStorage.getItem("vault_keys") || "{}");
        const keyStr = keys[fileId];
        if (keyStr) {
          if (window.VaultCrypto && window.VaultCrypto.base64urlToArray) {
            fileKey = window.VaultCrypto.base64urlToArray(keyStr);
          }
        }
      } catch (e) {
        console.warn("Failed to get file key from localStorage:", e);
      }
    }

    const linksHTML = activeLinks
      .map((link) => {
        // Use share_url from backend (includes VAULT_URL if configured)
        // Fallback to VAULT_URL or window.location.origin if not provided
        // Use token if available, otherwise fallback to link_id
        const linkToken = link.token || link.link_id;
        const linkUrl = link.share_url || `${baseUrl}/share/${linkToken}`;

        // Always include key and file ID in the URL fragment for E2EE
        let fullUrl = linkUrl;
        if (fileKey) {
          if (window.VaultCrypto && window.VaultCrypto.arrayToBase64url) {
            const keyBase64 = window.VaultCrypto.arrayToBase64url(fileKey);
            fullUrl = `${linkUrl}#key=${keyBase64}&file=${fileId}`;
          } else if (typeof btoa !== "undefined") {
            // Fallback to base64
            const keyArray = Array.from(fileKey);
            const keyBase64 = btoa(String.fromCharCode.apply(null, keyArray));
            fullUrl = `${linkUrl}#key=${encodeURIComponent(keyBase64)}&file=${fileId}`;
          }
        } else {
          console.warn(
            "File key not available for share link. The link will not work for decryption.",
          );
        }

        const expiresText = link.expires_at
          ? `Expires: ${new Date(link.expires_at).toLocaleString()}`
          : "No expiration";
        const downloadsText = link.max_downloads
          ? `${link.download_count || 0}/${link.max_downloads} downloads`
          : `${link.download_count || 0} downloads`;
        const passwordText = link.has_password ? "Password protected" : "";

        // Build meta text with proper spacing
        const metaParts = [expiresText, downloadsText];
        if (passwordText) {
          metaParts.push(passwordText);
        }
        const metaText = metaParts.join(" • ");

        return `
          <div class="active-link-item">
            <div class="active-link-info">
              <div class="active-link-url">${this.escapeHtml(fullUrl)}</div>
              <div class="active-link-meta">${this.escapeHtml(metaText)}</div>
            </div>
            <div class="active-link-actions">
              <button class="btn btn-small copy-link-btn" data-url="${this.escapeHtml(fullUrl)}">Copy</button>
              <button class="btn btn-small btn-danger revoke-link-btn" data-link-id="${this.escapeHtml(link.link_id)}">Revoke</button>
            </div>
          </div>
        `;
      })
      .join("");

    setInnerHTML(container, linksHTML);

    // Use event delegation on the container instead of attaching to individual buttons
    // This works even if buttons are added/removed dynamically
    const self = this;

    // Wait a tiny bit to ensure DOM is updated after setInnerHTML
    // Use event delegation - attach listener to the container
    // This will work for all buttons, even if they're added later
    setTimeout(() => {
      container.addEventListener("click", async (e) => {
        // Check if the clicked element is a copy button
        const copyBtn = e.target.closest(".copy-link-btn");
        if (copyBtn) {
          e.preventDefault();
          e.stopPropagation();

          const url = copyBtn.dataset.url;
          if (!url) {
            console.error("No URL found in button dataset");
            return;
          }

          try {
            await navigator.clipboard.writeText(url);

            // Show visual feedback animations
            // Find the .active-link-url element (the actual link field)
            const linkItem = copyBtn.closest(".active-link-item");
            const linkUrlElement = linkItem?.querySelector(".active-link-url");

            // Show popup notification
            if (self && typeof self.showCopyNotification === "function") {
              self.showCopyNotification();
            }

            // Show animation on link field
            if (
              linkUrlElement &&
              self &&
              typeof self.showCopyAnimation === "function"
            ) {
              self.showCopyAnimation(linkUrlElement);
            }
          } catch (err) {
            console.error("Failed to copy:", err);
            if (window.Notifications) {
              window.Notifications.error("Failed to copy link");
            }
          }
          return; // Exit early after handling copy button
        }

        // Also check for revoke buttons in the same handler
        const revokeBtn = e.target.closest(".revoke-link-btn");
        if (revokeBtn) {
          e.preventDefault();
          e.stopPropagation();

          const linkId = revokeBtn.dataset.linkId;
          // Use confirmation modal if available, otherwise fallback to native confirm
          if (window.showConfirmationModal) {
            window.showConfirmationModal({
              title: "Revoke Share Link",
              message:
                "Are you sure you want to revoke this share link? This action cannot be undone.",
              confirmText: "Revoke",
              dangerous: true,
              onConfirm: async () => {
                await self.revokeLink(linkId);
              },
            });
          } else {
            // Fallback to native confirm
            if (confirm("Are you sure you want to revoke this share link?")) {
              await self.revokeLink(linkId);
            }
          }
          return;
        }
      });
    }, 50); // Small delay to ensure DOM is ready
  }

  /**
   * Revoke share link
   */
  async revokeLink(linkId) {
    try {
      // Get JWT token for authentication
      const jwtToken = localStorage.getItem("jwt_token");

      if (!jwtToken) {
        throw new Error("Authentication required. Please log in again.");
      }

      const headers = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      };

      // Migrate to API v2 - use public-links endpoint
      const response = await fetch(`/api/v2/sharing/public-links/${linkId}`, {
        method: "DELETE",
        headers,
        credentials: "same-origin",
      });

      if (response.ok) {
        if (window.Notifications) {
          window.Notifications.success("Share link revoked");
        }
        await this.loadActiveLinks(this.currentFileId);
      } else {
        const error = await response.json();
        throw new Error(error.error || "Failed to revoke link");
      }
    } catch (error) {
      console.error("Error revoking link:", error);
      if (window.Notifications) {
        window.Notifications.error(`Failed to revoke link: ${error.message}`);
      }
    }
  }

  /**
   * Show copy notification popup at top center of screen
   */
  showCopyNotification() {
    try {
      // Remove any existing notification
      const existing = document.querySelector(".copy-notification-popup");
      if (existing) {
        existing.remove();
      }

      // Create notification element
      const notification = document.createElement("div");
      notification.className = "copy-notification-popup";
      notification.textContent = "Link copied to clipboard";
      notification.setAttribute("aria-live", "polite");
      notification.setAttribute("role", "status");

      // Apply inline styles as fallback to ensure visibility
      notification.style.cssText = `
        position: fixed !important;
        top: 2rem !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 10000 !important;
        background: rgba(16, 185, 129, 0.9) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        color: white !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 0.75rem !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3) !important;
        opacity: 0 !important;
        pointer-events: none !important;
        transition: opacity 0.3s ease, transform 0.3s ease !important;
        white-space: nowrap !important;
      `;

      // Insert into body
      if (!document.body) {
        return;
      }
      document.body.appendChild(notification);

      // Force reflow to ensure initial state is applied
      void notification.offsetHeight;

      // Trigger fade in animation
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          notification.classList.add("copy-notification-show");
          // Also set opacity directly as fallback
          notification.style.opacity = "1";
          notification.style.transform = "translateX(-50%) translateY(0)";
        });
      });

      // Remove after animation completes
      setTimeout(() => {
        notification.classList.remove("copy-notification-show");
        notification.classList.add("copy-notification-hide");
        // Also fade out using inline styles
        notification.style.opacity = "0";
        notification.style.transform = "translateX(-50%) translateY(-20px)";
        setTimeout(() => {
          if (notification.parentNode) {
            notification.remove();
          }
        }, 300); // Match fade out duration
      }, 2000); // Show for 2 seconds
    } catch (error) {
      // Silent fail for notification display
    }
  }

  /**
   * Show copy animation overlay on link field
   * @param {HTMLElement} linkUrlElement - The .active-link-url element containing the link
   */
  showCopyAnimation(linkUrlElement) {
    try {
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

      // Apply inline styles as fallback
      overlay.style.cssText = `
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
        background: rgba(16, 185, 129, 0.3) !important;
        backdrop-filter: blur(4px) !important;
        -webkit-backdrop-filter: blur(4px) !important;
        border-radius: 0.375rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        z-index: 10 !important;
        opacity: 0 !important;
        transition: opacity 0.3s ease !important;
        pointer-events: none !important;
        box-shadow: 0 0 20px rgba(16, 185, 129, 0.4) inset !important;
      `;

      // Create checkmark element
      const checkmark = document.createElement("div");
      checkmark.className = "copy-animation-checkmark";
      checkmark.textContent = "✔";
      checkmark.setAttribute("aria-hidden", "true");

      // Apply inline styles for checkmark
      checkmark.style.cssText = `
        font-size: 1.5rem !important;
        color: white !important;
        font-weight: bold !important;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.5) !important;
        opacity: 0 !important;
        transform: scale(0.5) !important;
        transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
      `;

      overlay.appendChild(checkmark);
      linkUrlElement.appendChild(overlay);

      // Force reflow to ensure initial state is applied
      void overlay.offsetHeight;
      void checkmark.offsetHeight;

      // Trigger animation
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          overlay.classList.add("copy-animation-active");
          // Also set opacity directly as fallback
          overlay.style.opacity = "1";
          checkmark.style.opacity = "1";
          checkmark.style.transform = "scale(1)";
        });
      });

      // Remove after animation completes
      setTimeout(() => {
        overlay.classList.remove("copy-animation-active");
        overlay.classList.add("copy-animation-hide");
        // Also fade out using inline styles
        overlay.style.opacity = "0";
        checkmark.style.opacity = "0";
        checkmark.style.transform = "scale(0.8)";
        setTimeout(() => {
          if (overlay.parentNode) {
            overlay.remove();
          }
        }, 300); // Match fade out duration
      }, 1000); // Animation lasts 1 second
    } catch (error) {
      // Silent fail for animation display
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

// Initialize sharing manager lazily (only when needed, after Trusted Types policies are available)
let sharingManager = null;

// Export SharingManager class immediately
if (typeof window !== "undefined") {
  window.SharingManager = SharingManager;

  // Function to initialize sharing manager
  function initSharingManager() {
    // Don't initialize if already initialized
    if (sharingManager) {
      return;
    }

    const retryCount = (initSharingManager.retryCount || 0) + 1;
    initSharingManager.retryCount = retryCount;

    // Check if Trusted Types is supported by the browser
    const trustedTypesSupported = !!(
      window.trustedTypes && window.trustedTypes.createPolicy
    );

    // Check if Trusted Types policies are available (only if Trusted Types is supported)
    let hasPolicies = false;
    if (trustedTypesSupported) {
      // Check if they're assigned to window
      hasPolicies =
        window.vaultHTMLPolicy ||
        (window.trustedTypes && window.trustedTypes.defaultPolicy);
    } else {
      // Trusted Types is not supported - we'll use DOM API methods, so policies are not required
      hasPolicies = true;
    }

    // Check if DOM is ready
    const domReady = document.body && document.readyState !== "loading";

    if (!hasPolicies || !domReady) {
      // Wait a bit and retry (max 50 retries = 5 seconds)
      let retryCount = (initSharingManager.retryCount || 0) + 1;
      initSharingManager.retryCount = retryCount;
      if (retryCount < 50) {
        setTimeout(initSharingManager, 100);
      } else {
        console.error(
          "Failed to initialize SharingManager: policies or DOM not ready after 5 seconds",
        );
      }
      return;
    }

    // Everything is ready, initialize sharing manager
    try {
      sharingManager = new SharingManager();
      window.sharingManager = sharingManager;
      window.showShareModalAdvanced = (
        fileId,
        fileType,
        vaultspaceId,
        vaultspaceKey,
      ) => {
        if (sharingManager) {
          sharingManager.showShareModal(
            fileId,
            fileType,
            vaultspaceId,
            vaultspaceKey,
          );
        } else {
          // Manager not initialized yet, wait and retry
          setTimeout(() => {
            if (sharingManager) {
              sharingManager.showShareModal(
                fileId,
                fileType,
                vaultspaceId,
                vaultspaceKey,
              );
            } else {
              console.error("SharingManager failed to initialize");
              if (window.Notifications) {
                window.Notifications.error(
                  "Share functionality is not available. Please refresh the page.",
                );
              }
            }
          }, 500);
        }
      };
    } catch (error) {
      console.error("Error initializing SharingManager:", error);
    }
  }

  // Start initialization when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      // Wait for Trusted Types policies to be available
      setTimeout(initSharingManager, 200);
    });
  } else {
    // DOM is already ready
    setTimeout(initSharingManager, 200);
  }

  // Also try to initialize on window load (in case policies are loaded later)
  window.addEventListener("load", () => {
    if (!sharingManager) {
      setTimeout(initSharingManager, 100);
    }
  });
}
