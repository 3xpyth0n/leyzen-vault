/** @file logout.js - Logout confirmation modal */

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

  iconEl.textContent = options.icon || "⚠️";
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

  // Remove existing listeners
  const newCancelBtn = cancelBtn.cloneNode(true);
  const newConfirmBtn = confirmBtn.cloneNode(true);
  cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);
  confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

  // Add new listeners
  newCancelBtn.addEventListener("click", hideConfirmationModal);
  newConfirmBtn.addEventListener("click", () => {
    hideConfirmationModal();
    if (options.onConfirm) {
      options.onConfirm();
    }
  });

  // Close on backdrop click (one-time handler)
  const backdropHandler = (e) => {
    if (e.target === modal) {
      hideConfirmationModal();
      modal.removeEventListener("click", backdropHandler);
    }
  };
  modal.addEventListener("click", backdropHandler);

  // Show modal
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");

  // Focus on cancel button for accessibility
  setTimeout(() => newCancelBtn.focus(), 100);

  // Close on Escape key
  const escapeHandler = (e) => {
    if (e.key === "Escape") {
      hideConfirmationModal();
      document.removeEventListener("keydown", escapeHandler);
      modal.removeEventListener("click", backdropHandler);
    }
  };
  document.addEventListener("keydown", escapeHandler);
};

// Make hideConfirmationModal globally available
window.hideConfirmationModal = function hideConfirmationModal() {
  const modal = document.getElementById("confirmationModal");
  if (modal) {
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  }
};

// Handle logout confirmation
document.addEventListener("DOMContentLoaded", () => {
  const logoutForm = document.getElementById("logout-form");

  if (logoutForm) {
    logoutForm.addEventListener("submit", function (event) {
      event.preventDefault();
      showConfirmationModal({
        icon: "🚪",
        title: "Logout",
        message: "Are you sure you want to logout?",
        confirmText: "Logout",
        dangerous: false,
        onConfirm: () => {
          logoutForm.submit();
        },
      });
    });
  }
});
