/** @file logout.js - Logout confirmation modal */

// Helper function to safely set innerHTML with Trusted Types
function setInnerHTML(element, html) {
  if (window.vaultHTMLPolicy) {
    try {
      element.innerHTML = window.vaultHTMLPolicy.createHTML(html);
      return;
    } catch (e) {}
  }
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {}
  }
  element.innerHTML = html;
}

// Make showConfirmationModal globally available
window.showConfirmationModal = function showConfirmationModal(options) {
  const modal = document.getElementById("confirmationModal");
  const iconEl = document.getElementById("modalIcon");
  const titleEl = document.getElementById("modalTitle");
  const messageEl = document.getElementById("modalMessage");
  const cancelBtn = document.getElementById("modalCancel");
  const confirmBtn = document.getElementById("modalConfirm");

  if (
    !modal ||
    !iconEl ||
    !titleEl ||
    !messageEl ||
    !cancelBtn ||
    !confirmBtn
  ) {
    // Fallback to native confirm if modal elements not found
    const confirmed = confirm(options.message || "Are you sure?");
    if (confirmed && options.onConfirm) {
      options.onConfirm();
    }
    return;
  }

  // Set icon as HTML if it contains SVG, otherwise as text
  if (typeof options.icon === "string" && options.icon.includes("<svg")) {
    setInnerHTML(iconEl, options.icon);
  } else {
    iconEl.textContent = options.icon || "⚠️";
  }
  titleEl.textContent = options.title || "Confirm Action";
  messageEl.textContent =
    options.message || "Are you sure you want to proceed?";
  confirmBtn.textContent = options.confirmText || "Confirm";

  // Apply different styles based on action type
  if (options.dangerous) {
    confirmBtn.className = "modal-btn modal-btn-confirm modal-btn-danger";
  } else {
    confirmBtn.className = "modal-btn modal-btn-confirm";
  }

  // Remove existing listeners by cloning buttons
  const newCancelBtn = cancelBtn.cloneNode(true);
  const newConfirmBtn = confirmBtn.cloneNode(true);
  cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
  confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

  // Add new listeners with proper event handling
  const handleCancel = (e) => {
    e.preventDefault();
    e.stopPropagation();
    hideConfirmationModal();
  };

  const handleConfirm = (e) => {
    e.preventDefault();
    e.stopPropagation();
    hideConfirmationModal();
    if (options.onConfirm) {
      // Use setTimeout to ensure modal is hidden before callback
      setTimeout(() => {
        if (options.onConfirm) {
          options.onConfirm();
        }
      }, 100);
    }
  };

  newCancelBtn.addEventListener("click", handleCancel);
  newConfirmBtn.addEventListener("click", handleConfirm);

  // Close on backdrop click (one-time handler)
  const backdropHandler = (e) => {
    if (e.target === modal) {
      e.preventDefault();
      e.stopPropagation();
      hideConfirmationModal();
      modal.removeEventListener("click", backdropHandler);
    }
  };
  modal.addEventListener("click", backdropHandler, true);

  // Show modal
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  // Force show with inline styles
  modal.style.display = "flex";
  modal.style.visibility = "visible";
  modal.style.opacity = "1";

  // Focus on cancel button for accessibility
  setTimeout(() => newCancelBtn.focus(), 100);

  // Close on Escape key
  const escapeHandler = (e) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      hideConfirmationModal();
      document.removeEventListener("keydown", escapeHandler);
      modal.removeEventListener("click", backdropHandler);
    }
  };
  document.addEventListener("keydown", escapeHandler, true);
};

// Make hideConfirmationModal globally available
window.hideConfirmationModal = function hideConfirmationModal() {
  const modal = document.getElementById("confirmationModal");
  if (modal) {
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
    // Force hide with inline styles as fallback
    modal.style.display = "none";
    modal.style.visibility = "hidden";
    modal.style.opacity = "0";
  }
};

// Handle logout confirmation
document.addEventListener("DOMContentLoaded", () => {
  const logoutForm = document.getElementById("logout-form");

  if (logoutForm) {
    logoutForm.addEventListener("submit", function (event) {
      event.preventDefault();
      const logoutIcon = window.Icons?.logout
        ? window.Icons.logout(20, "currentColor")
        : "🚪";
      showConfirmationModal({
        icon: logoutIcon,
        title: "Logout",
        message: "Are you sure you want to logout?",
        confirmText: "Logout",
        dangerous: false,
        onConfirm: () => {
          // Clear service worker cache if available
          if (
            "serviceWorker" in navigator &&
            navigator.serviceWorker.controller
          ) {
            navigator.serviceWorker.controller.postMessage({
              type: "CLEAR_CACHE",
            });
          }
          // Force redirect to login with cache busting
          window.location.href = "/login?t=" + Date.now();
        },
      });
    });
  }
});
