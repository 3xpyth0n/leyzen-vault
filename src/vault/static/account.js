/** @file account.js - Account management functionality */

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
  element.innerHTML = html;
}

// Load account information
async function loadAccountInfo() {
  const container = document.getElementById("account-info");
  if (!container) return;

  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required");
    }

    const response = await fetch("/api/auth/me", {
      headers: {
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error("Failed to load account information");
    }

    const data = await response.json();
    const user = data.user || data;
    const username = escapeHtml(user.email || user.username || "Unknown");
    const createdAt = user.created_at
      ? new Date(user.created_at).toLocaleString()
      : "Unknown";
    const lastLogin = user.last_login
      ? new Date(user.last_login).toLocaleString()
      : "Never";

    setInnerHTML(
      container,
      `
            <div class="info-item">
                <span class="info-label">Username:</span>
                <span class="info-value">${username}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Account Created:</span>
                <span class="info-value">${createdAt}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Last Login:</span>
                <span class="info-value">${lastLogin}</span>
            </div>
        `,
    );

    // Disable delete account section if user is superadmin
    if (user.global_role === "superadmin") {
      const deleteAccountForm = document.getElementById("delete-account-form");
      if (deleteAccountForm) {
        const deleteButton = deleteAccountForm.querySelector(
          'button[type="submit"]',
        );
        const deletePasswordInput = document.getElementById("delete-password");
        const deleteSection = deleteAccountForm.closest(
          ".account-section-danger",
        );

        if (deleteButton) {
          deleteButton.disabled = true;
        }
        if (deletePasswordInput) {
          deletePasswordInput.disabled = true;
        }
        if (deleteSection) {
          const warningText = document.createElement("p");
          warningText.className = "danger-text";
          warningText.style.marginBottom = "1rem";
          warningText.textContent =
            "Superadmin accounts cannot be deleted. Transfer the superadmin role to another user first.";
          deleteSection.insertBefore(warningText, deleteAccountForm);
        }
      }
    }
  } catch (error) {
    console.error("Error loading account info:", error);
    setInnerHTML(
      container,
      '<div class="error-message">Failed to load account information</div>',
    );
  }
}

// Change password
async function handlePasswordChange(e) {
  e.preventDefault();
  const errorDiv = document.getElementById("password-error");
  errorDiv.classList.add("hidden");

  const currentPassword = document.getElementById("current-password").value;
  const newPassword = document.getElementById("new-password").value;
  const confirmPassword = document.getElementById("confirm-password").value;

  // Validation
  if (newPassword !== confirmPassword) {
    errorDiv.textContent = "New passwords do not match";
    errorDiv.classList.remove("hidden");
    return;
  }

  if (newPassword.length < 8) {
    errorDiv.textContent = "Password must be at least 8 characters";
    errorDiv.classList.remove("hidden");
    return;
  }

  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      errorDiv.textContent = "Authentication required. Please log in again.";
      errorDiv.classList.remove("hidden");
      return;
    }

    const response = await fetch("/api/auth/account/password", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      errorDiv.textContent = data.error || "Failed to change password";
      errorDiv.classList.remove("hidden");
      return;
    }

    // Success
    if (window.Notifications) {
      window.Notifications.success("Password changed successfully");
    }

    // Clear form
    document.getElementById("change-password-form").reset();
  } catch (error) {
    console.error("Error changing password:", error);
    errorDiv.textContent = "An error occurred. Please try again.";
    errorDiv.classList.remove("hidden");
  }
}

// Delete account
async function handleDeleteAccount(e) {
  e.preventDefault();
  const errorDiv = document.getElementById("delete-error");
  errorDiv.classList.add("hidden");

  // Check if user is superadmin
  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (jwtToken) {
      const response = await fetch("/api/auth/me", {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
        credentials: "same-origin",
      });
      if (response.ok) {
        const data = await response.json();
        const user = data.user || data;
        if (user.global_role === "superadmin") {
          errorDiv.textContent =
            "Superadmin accounts cannot be deleted. Transfer the superadmin role to another user first.";
          errorDiv.classList.remove("hidden");
          return;
        }
      }
    }
  } catch (error) {
    console.error("Error checking user role:", error);
  }

  const password = document.getElementById("delete-password").value;

  // Confirm deletion
  if (typeof window.showConfirmationModal === "function") {
    const warningIcon = window.Icons?.warning
      ? window.Icons.warning(20, "currentColor")
      : "⚠️";
    window.showConfirmationModal({
      icon: warningIcon,
      title: "Delete Account",
      message:
        "Are you sure you want to delete your account? This action cannot be undone. All your files and data will be permanently deleted.",
      confirmText: "Delete Account",
      dangerous: true,
      onConfirm: async () => {
        await performDeleteAccount(password);
      },
    });
  } else {
    if (
      !confirm(
        "Are you sure you want to delete your account? This action cannot be undone.",
      )
    ) {
      return;
    }
    await performDeleteAccount(password);
  }
}

async function performDeleteAccount(password) {
  const errorDiv = document.getElementById("delete-error");

  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      errorDiv.textContent = "Authentication required. Please log in again.";
      errorDiv.classList.remove("hidden");
      return;
    }

    const response = await fetch("/api/auth/account", {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${jwtToken}`,
      },
      credentials: "same-origin",
      body: JSON.stringify({
        password: password,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      errorDiv.textContent = data.error || "Failed to delete account";
      errorDiv.classList.remove("hidden");
      return;
    }

    // Success - redirect to login
    if (window.Notifications) {
      window.Notifications.success("Account deleted successfully");
    }

    setTimeout(() => {
      window.location.href = "/login";
    }, 2000);
  } catch (error) {
    console.error("Error deleting account:", error);
    errorDiv.textContent = "An error occurred. Please try again.";
    errorDiv.classList.remove("hidden");
  }
}

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

// Initialize on DOM ready
document.addEventListener("DOMContentLoaded", async () => {
  await loadAccountInfo();

  // Set username in hidden fields
  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (jwtToken) {
      const response = await fetch("/api/auth/me", {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
        credentials: "same-origin",
      });
      if (response.ok) {
        const data = await response.json();
        const user = data.user || data;
        const username = user.email || user.username;
        const usernameInputChange = document.getElementById(
          "hidden-username-change",
        );
        const usernameInputDelete = document.getElementById(
          "hidden-username-delete",
        );
        if (usernameInputChange && username) {
          usernameInputChange.value = username;
        }
        if (usernameInputDelete && username) {
          usernameInputDelete.value = username;
        }
      }
    }
  } catch (error) {
    // Ignore errors, hidden fields are optional
  }

  const changePasswordForm = document.getElementById("change-password-form");
  if (changePasswordForm) {
    changePasswordForm.addEventListener("submit", handlePasswordChange);
  }

  const deleteAccountForm = document.getElementById("delete-account-form");
  if (deleteAccountForm) {
    deleteAccountForm.addEventListener("submit", handleDeleteAccount);
  }
});
