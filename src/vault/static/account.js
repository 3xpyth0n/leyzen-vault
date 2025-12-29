/** @file account.js - Account management functionality */

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

// Crypto Helper for account operations
const CryptoHelper = {
  getCryptoAPI() {
    const cryptoAPI =
      (typeof window !== "undefined" && window.crypto) ||
      (typeof self !== "undefined" && self.crypto) ||
      (typeof globalThis !== "undefined" && globalThis.crypto) ||
      null;

    if (!cryptoAPI || !cryptoAPI.subtle) {
      throw new Error("Web Crypto API is not available");
    }
    return cryptoAPI;
  },

  async deriveUserKey(password, salt) {
    if (!window.argon2) {
      throw new Error("Argon2 library not loaded");
    }

    const argon2Prefix = new TextEncoder().encode("argon2:");

    let saltBytes;
    if (typeof salt === "string") {
      // Assume base64
      const binaryString = atob(salt);
      saltBytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        saltBytes[i] = binaryString.charCodeAt(i);
      }
    } else {
      saltBytes = salt;
    }

    // Verify prefix
    if (saltBytes.length < argon2Prefix.length) {
      throw new Error("Invalid salt: too short");
    }

    for (let i = 0; i < argon2Prefix.length; i++) {
      if (saltBytes[i] !== argon2Prefix[i]) {
        throw new Error("Invalid salt: missing 'argon2:' prefix");
      }
    }

    const actualSalt = saltBytes.slice(argon2Prefix.length);

    try {
      const result = await window.argon2.hash({
        pass: password,
        salt: actualSalt,
        type: window.argon2.ArgonType.Argon2id,
        time: 3,
        mem: 4096,
        parallelism: 4,
        hashLen: 32,
      });

      const cryptoAPI = this.getCryptoAPI();
      return await cryptoAPI.subtle.importKey(
        "raw",
        result.hash,
        { name: "AES-GCM", length: 256 },
        false, // not extractable
        ["encrypt", "decrypt"],
      );
    } catch (error) {
      console.error("Argon2 derivation failed:", error);
      throw error;
    }
  },

  async deriveSigningKey(masterKey) {
    const cryptoAPI = this.getCryptoAPI();
    // We need to derive a signing key. Since masterKey is not extractable (usually),
    // we can't export it to use as HKDF input if it was imported as non-extractable.
    // However, in our deriveUserKey above, we import it as non-extractable.
    // Wait, encryption.js uses deriveKey which requires the base key to be extractable OR
    // used as a base key.
    // encryption.js implementation exports the key first!
    // "const rawKey = await cryptoAPI.subtle.exportKey("raw", masterKey);"
    // This implies masterKey MUST be extractable in encryption.js.

    // initializeUserMasterKey calls deriveUserKey(..., true).

    return Promise.reject(
      new Error(
        "Signing key derivation not implemented without extractable master key",
      ),
    );
  },

  // Revised deriveUserKey to be extractable
  async deriveUserKeyExtractable(password, salt) {
    // Same as above but extractable=true
    if (!window.argon2) throw new Error("Argon2 library not loaded");

    // ... salt processing ...
    const argon2Prefix = new TextEncoder().encode("argon2:");
    let saltBytes;
    if (typeof salt === "string") {
      const binaryString = atob(salt);
      saltBytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        saltBytes[i] = binaryString.charCodeAt(i);
      }
    } else {
      saltBytes = salt;
    }
    const actualSalt = saltBytes.slice(argon2Prefix.length);

    const result = await window.argon2.hash({
      pass: password,
      salt: actualSalt,
      type: window.argon2.ArgonType.Argon2id,
      time: 3,
      mem: 4096,
      parallelism: 4,
      hashLen: 32,
    });

    const cryptoAPI = this.getCryptoAPI();
    return await cryptoAPI.subtle.importKey(
      "raw",
      result.hash,
      { name: "AES-GCM", length: 256 },
      true, // EXTRACTABLE for signing key derivation
      ["encrypt", "decrypt"],
    );
  },

  async deriveSigningKeyFromExtractable(masterKey) {
    const cryptoAPI = this.getCryptoAPI();
    const rawKey = await cryptoAPI.subtle.exportKey("raw", masterKey);
    const keyMaterial = await cryptoAPI.subtle.importKey(
      "raw",
      rawKey,
      { name: "HKDF", hash: "SHA-256" },
      false,
      ["deriveKey"],
    );

    const encoder = new TextEncoder();
    const info = encoder.encode("leyzen-key-signature-v1");
    const salt = encoder.encode("leyzen-vault-hkdf-salt-2024-!!!!");

    return await cryptoAPI.subtle.deriveKey(
      { name: "HKDF", salt: salt, info: info, hash: "SHA-256" },
      keyMaterial,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
  },

  async decryptVaultSpaceKey(userKey, encryptedKeyBase64) {
    const combined = Uint8Array.from(atob(encryptedKeyBase64), (c) =>
      c.charCodeAt(0),
    );
    const cryptoAPI = this.getCryptoAPI();

    let encryptedData = combined;

    if (combined.length >= 92) {
      try {
        const signingKey = await this.deriveSigningKeyFromExtractable(userKey);
        const signature = combined.slice(-32);
        const data = combined.slice(0, -32);
        const isValid = await cryptoAPI.subtle.verify(
          "HMAC",
          signingKey,
          signature,
          data,
        );
        if (isValid) {
          encryptedData = data;
        }
      } catch (e) {
        console.warn("Signature verification failed", e);
      }
    }

    const iv = encryptedData.slice(0, 12);
    const ciphertext = encryptedData.slice(12);

    const decrypted = await cryptoAPI.subtle.decrypt(
      { name: "AES-GCM", iv: iv },
      userKey,
      ciphertext,
    );

    return await cryptoAPI.subtle.importKey(
      "raw",
      decrypted,
      { name: "AES-GCM", length: 256 },
      true,
      ["encrypt", "decrypt"],
    );
  },

  async encryptVaultSpaceKey(userKey, vaultspaceKey) {
    const cryptoAPI = this.getCryptoAPI();
    const rawKey = await cryptoAPI.subtle.exportKey("raw", vaultspaceKey);
    const iv = cryptoAPI.getRandomValues(new Uint8Array(12));

    const encrypted = await cryptoAPI.subtle.encrypt(
      { name: "AES-GCM", iv: iv },
      userKey,
      rawKey,
    );

    const combined = new Uint8Array(iv.length + encrypted.byteLength);
    combined.set(iv, 0);
    combined.set(new Uint8Array(encrypted), iv.length);

    // Add signature
    try {
      const signingKey = await this.deriveSigningKeyFromExtractable(userKey);
      const signature = await cryptoAPI.subtle.sign(
        "HMAC",
        signingKey,
        combined,
      );
      const withSig = new Uint8Array(combined.length + 32);
      withSig.set(combined, 0);
      withSig.set(new Uint8Array(signature), combined.length);
      return btoa(String.fromCharCode(...withSig));
    } catch (e) {
      return btoa(String.fromCharCode(...combined));
    }
  },
};

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

  const submitButton = e.target.querySelector('button[type="submit"]');
  const originalButtonText = submitButton.textContent;
  submitButton.disabled = true;
  submitButton.textContent = "Processing encryption...";

  try {
    const jwtToken = localStorage.getItem("jwt_token");
    if (!jwtToken) {
      throw new Error("Authentication required. Please log in again.");
    }

    // 1. Get Salt
    let salt = sessionStorage.getItem("user_master_key_salt");
    if (!salt) {
      const saltResp = await fetch("/api/auth/account/master-key-salt", {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      if (saltResp.ok) {
        const saltData = await saltResp.json();
        salt = saltData.master_key_salt;
        sessionStorage.setItem("user_master_key_salt", salt);
      } else {
        throw new Error(
          "Could not retrieve master key salt. Please log in again.",
        );
      }
    }

    // 2. Fetch User Keys
    const keysResp = await fetch("/api/auth/account/keys", {
      headers: { Authorization: `Bearer ${jwtToken}` },
    });
    if (!keysResp.ok) {
      throw new Error("Failed to retrieve encryption keys");
    }
    const keysData = await keysResp.json();

    // 3. Re-encrypt keys
    const oldMasterKey = await CryptoHelper.deriveUserKeyExtractable(
      currentPassword,
      salt,
    );
    const newMasterKey = await CryptoHelper.deriveUserKeyExtractable(
      newPassword,
      salt,
    );

    const reencryptedKeys = [];
    for (const keyData of keysData.keys) {
      try {
        const vaultspaceKey = await CryptoHelper.decryptVaultSpaceKey(
          oldMasterKey,
          keyData.encrypted_key,
        );
        const newEncryptedKey = await CryptoHelper.encryptVaultSpaceKey(
          newMasterKey,
          vaultspaceKey,
        );
        reencryptedKeys.push({
          vaultspace_id: keyData.vaultspace_id,
          encrypted_key: newEncryptedKey,
        });
      } catch (err) {
        console.error(
          `Failed to re-encrypt key for vaultspace ${keyData.vaultspace_id}`,
          err,
        );
        throw new Error(
          "Failed to verify current password for encryption keys. Are you sure it's correct?",
        );
      }
    }

    submitButton.textContent = "Updating password...";

    // 4. Send Update
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
        reencrypted_keys: reencryptedKeys,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Failed to change password");
    }

    // Success
    if (window.Notifications) {
      window.Notifications.success("Password changed successfully");
    }

    // Clear form
    document.getElementById("change-password-form").reset();
  } catch (error) {
    errorDiv.textContent =
      error.message || "An error occurred. Please try again.";
    errorDiv.classList.remove("hidden");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = originalButtonText;
  }
}

// Delete account
async function handleDeleteAccount(e) {
  e.preventDefault();
  const errorDiv = document.getElementById("delete-error");
  errorDiv.classList.add("hidden");

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
  } catch (error) {}

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

document.addEventListener("DOMContentLoaded", async () => {
  await loadAccountInfo();

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
