/** @file cleanup-modal.js - Remove any stuck confirmation modal */

// Remove confirmation modal if it exists (runs immediately)
(function () {
  // Remove confirmation modal if it exists and is visible
  const modal = document.getElementById("confirmationModal");
  if (modal) {
    modal.remove();
  }
  // Remove modal-open class from body
  if (document.body) {
    document.body.classList.remove("modal-open");
  }

  // Also run on DOMContentLoaded in case modal is added later
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      const modal = document.getElementById("confirmationModal");
      if (modal) {
        modal.remove();
      }
      document.body.classList.remove("modal-open");
    });
  }
})();
