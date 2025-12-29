/** @file notifications.js - Toast notification system for Leyzen Vault */

// Helper function to safely set innerHTML with Trusted Types
// Uses policies created in base.html before CSP enforcement
function setInnerHTML(element, html) {
  // Use the global policy created in base.html if available
  if (window.notificationsHTMLPolicy) {
    try {
      element.innerHTML = window.notificationsHTMLPolicy.createHTML(html);
      return;
    } catch (e) {
      // Fallback if policy fails
    }
  }

  // Fallback: if Trusted Types is required but policy doesn't exist, this will fail
  // This should not happen if base.html script executed correctly
  if (window.trustedTypes && window.trustedTypes.defaultPolicy) {
    try {
      element.innerHTML = window.trustedTypes.defaultPolicy.createHTML(html);
      return;
    } catch (e) {}
  }

  // Last resort fallback - this will fail if CSP requires Trusted Types
  // but it's better than crashing silently
  try {
    element.innerHTML = html;
  } catch (e) {
    throw e;
  }
}

const NotificationType = {
  SUCCESS: "success",
  ERROR: "error",
  WARNING: "warning",
  INFO: "info",
};

class NotificationManager {
  constructor() {
    this.container = null;
    this.init();
  }

  init() {
    // Create container if it doesn't exist
    if (!document.getElementById("toast-container")) {
      this.container = document.createElement("div");
      this.container.id = "toast-container";
      this.container.className = "toast-container";
      document.body.appendChild(this.container);
    } else {
      this.container = document.getElementById("toast-container");
    }
  }

  show(message, type = NotificationType.INFO, duration = 5000) {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    // Icon based on type
    const icons = {
      success: "✓",
      error: "✕",
      warning: "⚠",
      info: "ℹ",
    };

    const toastHTML = `
      <span class="toast-icon">${icons[type] || icons.info}</span>
      <span class="toast-message">${this.escapeHtml(message)}</span>
      <button class="toast-close" aria-label="Close">&times;</button>
    `;

    setInnerHTML(toast, toastHTML);

    this.container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
      toast.classList.add("toast-show");
    });

    // Auto-dismiss
    const timeoutId = setTimeout(() => {
      this.dismiss(toast);
    }, duration);

    // Manual dismiss
    const closeBtn = toast.querySelector(".toast-close");
    closeBtn.addEventListener("click", () => {
      clearTimeout(timeoutId);
      this.dismiss(toast);
    });

    return toast;
  }

  dismiss(toast) {
    toast.classList.remove("toast-show");
    toast.classList.add("toast-hide");
    setTimeout(() => {
      if (toast.parentNode) {
        toast.parentNode.removeChild(toast);
      }
    }, 300);
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  success(message, duration) {
    return this.show(message, NotificationType.SUCCESS, duration);
  }

  error(message, duration) {
    return this.show(message, NotificationType.ERROR, duration);
  }

  warning(message, duration) {
    return this.show(message, NotificationType.WARNING, duration);
  }

  info(message, duration) {
    return this.show(message, NotificationType.INFO, duration);
  }
}

// Global instance
const Notifications = new NotificationManager();

if (typeof window !== "undefined") {
  window.Notifications = Notifications;
}
