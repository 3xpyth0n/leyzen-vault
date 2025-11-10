/** @file logout-modal.js - Styled logout confirmation modal for non-Vue pages */

// Create and show logout confirmation modal
function showLogoutModal() {
  // Remove existing modal if any
  const existingModal = document.getElementById("logout-confirmation-modal");
  if (existingModal) {
    existingModal.remove();
  }

  // Create modal overlay
  const overlay = document.createElement("div");
  overlay.id = "logout-confirmation-modal";
  overlay.className = "logout-modal-overlay";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-labelledby", "logout-modal-title");
  overlay.setAttribute("aria-modal", "true");

  // Logout icon SVG - use professional icon from icons.js
  // Get error color from CSS variable or use default
  let errorColor = "#ef4444";
  if (typeof getComputedStyle !== "undefined") {
    const root = document.documentElement;
    const computed = getComputedStyle(root);
    const cssError = computed.getPropertyValue("--error")?.trim();
    if (cssError) {
      errorColor = cssError;
    }
  }

  const logoutIconSvg =
    window.Icons && window.Icons.logout
      ? window.Icons.logout(48, errorColor)
      : `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
    <polyline points="16 17 21 12 16 7"></polyline>
    <line x1="21" y1="12" x2="9" y2="12"></line>
  </svg>`;

  // Modal content - use Trusted Types if available
  const modalHTML = `
    <div class="logout-modal-container">
      <div class="logout-modal-content">
        <div class="logout-modal-icon">${logoutIconSvg}</div>
        <h2 id="logout-modal-title" class="logout-modal-title">Logout</h2>
        <p class="logout-modal-message">Are you sure you want to logout?</p>
        <div class="logout-modal-buttons">
          <button id="logout-modal-cancel" class="logout-modal-btn logout-modal-btn-cancel">Cancel</button>
          <button id="logout-modal-confirm" class="logout-modal-btn logout-modal-btn-confirm">Logout</button>
        </div>
      </div>
    </div>
  `;

  // Use Trusted Types policy if available (for CSP compliance)
  if (window.vaultHTMLPolicy) {
    overlay.innerHTML = window.vaultHTMLPolicy.createHTML(modalHTML);
  } else {
    overlay.innerHTML = modalHTML;
  }

  // Add to body
  document.body.appendChild(overlay);
  document.body.style.overflow = "hidden";

  // Get buttons
  const cancelBtn = document.getElementById("logout-modal-cancel");
  const confirmBtn = document.getElementById("logout-modal-confirm");

  // Handle cancel
  const handleCancel = (e) => {
    e.preventDefault();
    e.stopPropagation();
    hideLogoutModal();
  };

  // Handle confirm
  const handleConfirm = (e) => {
    e.preventDefault();
    e.stopPropagation();
    hideLogoutModal();

    // Clear service worker cache if available
    if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: "CLEAR_CACHE",
      });
    }

    // Redirect to login
    window.location.href = "/login?t=" + Date.now();
  };

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === overlay) {
      hideLogoutModal();
    }
  };

  // Handle Escape key
  const handleEscape = (e) => {
    if (e.key === "Escape") {
      hideLogoutModal();
    }
  };

  // Add event listeners
  cancelBtn.addEventListener("click", handleCancel);
  confirmBtn.addEventListener("click", handleConfirm);
  overlay.addEventListener("click", handleBackdropClick);
  document.addEventListener("keydown", handleEscape);

  // Focus on cancel button
  setTimeout(() => {
    cancelBtn.focus();
  }, 100);

  // Cleanup function
  overlay._cleanup = () => {
    cancelBtn.removeEventListener("click", handleCancel);
    confirmBtn.removeEventListener("click", handleConfirm);
    overlay.removeEventListener("click", handleBackdropClick);
    document.removeEventListener("keydown", handleEscape);
  };
}

// Hide logout modal
function hideLogoutModal() {
  const modal = document.getElementById("logout-confirmation-modal");
  if (modal) {
    if (modal._cleanup) {
      modal._cleanup();
    }
    modal.remove();
    document.body.style.overflow = "";
  }
}

// Make functions globally available
window.showLogoutModal = showLogoutModal;
window.hideLogoutModal = hideLogoutModal;
