/**
 * API client service for Leyzen Vault.
 *
 * Handles all HTTP requests to the backend API with JWT authentication.
 */

import { clearUserMasterKey } from "./keyManager";

const API_BASE_URL = "/api";

/**
 * Get JWT token from localStorage.
 *
 * @returns {string|null} JWT token or null
 */
function getToken() {
  return localStorage.getItem("jwt_token");
}

/**
 * Set JWT token in localStorage.
 *
 * @param {string} token - JWT token
 */
function setToken(token) {
  localStorage.setItem("jwt_token", token);
}

/**
 * Remove JWT token from localStorage.
 */
function removeToken() {
  localStorage.removeItem("jwt_token");
}

/**
 * Parse error response from API.
 * Handles both JSON and HTML error responses.
 *
 * @param {Response} response - Fetch response
 * @returns {Promise<object>} Error object with message
 */
export async function parseErrorResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    try {
      const error = await response.json();
      return {
        error: error.error || `Request failed with status ${response.status}`,
        status: response.status,
      };
    } catch (e) {
      // Fallback if JSON parsing fails
      return {
        error: `Request failed with status ${response.status}`,
        status: response.status,
      };
    }
  } else {
    // Response is HTML or other non-JSON format
    const statusText = response.statusText || `HTTP ${response.status}`;
    return {
      error: `Server error: ${statusText} (${response.status})`,
      status: response.status,
    };
  }
}

/**
 * Make authenticated API request.
 *
 * @param {string} endpoint - API endpoint
 * @param {object} options - Fetch options
 * @param {boolean} options.skipAutoRefresh - If true, skip automatic token refresh and redirect
 * @returns {Promise<Response>} Fetch response
 */
export async function apiRequest(endpoint, options = {}) {
  const { skipAutoRefresh = false, ...fetchOptions } = options;
  const token = getToken();
  const url = `${API_BASE_URL}${endpoint}`;

  const headers = {
    "Content-Type": "application/json",
    ...fetchOptions.headers,
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let response = await fetch(url, {
    ...fetchOptions,
    headers,
    credentials: "same-origin", // Include cookies (session) in requests
  });

  // Handle token refresh if needed (for 401 errors)
  if (response.status === 401 && token && !skipAutoRefresh) {
    try {
      // Try to refresh the token before giving up
      // Call refresh endpoint directly to avoid circular dependency
      const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        credentials: "same-origin",
        body: JSON.stringify({ token }),
      });

      if (refreshResponse.ok) {
        const refreshData = await refreshResponse.json();

        if (refreshData.token) {
          // Store new token
          setToken(refreshData.token);

          // Retry the original request with new token
          headers["Authorization"] = `Bearer ${refreshData.token}`;
          response = await fetch(url, {
            ...fetchOptions,
            headers,
            credentials: "same-origin",
          });

          // If still 401 after refresh, token is truly invalid
          if (response.status === 401) {
            // Don't redirect for critical operations - let caller handle it
            if (
              fetchOptions.method === "POST" ||
              fetchOptions.method === "DELETE"
            ) {
              return response; // Return response so caller can handle error
            }
            removeToken();
            window.location.href = "/login";
            throw new Error("Unauthorized");
          }
        } else {
          // Refresh failed - don't redirect for critical operations
          if (
            fetchOptions.method === "POST" ||
            fetchOptions.method === "DELETE"
          ) {
            return response;
          }
          removeToken();
          window.location.href = "/login";
          throw new Error("Unauthorized");
        }
      } else {
        // Refresh failed - don't redirect for critical operations
        if (
          fetchOptions.method === "POST" ||
          fetchOptions.method === "DELETE"
        ) {
          return response; // Return response so caller can handle error
        }
        removeToken();
        window.location.href = "/login";
        throw new Error("Unauthorized");
      }
    } catch (refreshError) {
      // Refresh failed - don't redirect for critical operations
      if (fetchOptions.method === "POST" || fetchOptions.method === "DELETE") {
        return response; // Return response so caller can handle error
      }
      removeToken();
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }
  } else if (response.status === 401) {
    // No token at all or skipAutoRefresh is true
    if (
      skipAutoRefresh ||
      fetchOptions.method === "POST" ||
      fetchOptions.method === "DELETE"
    ) {
      return response; // Return response so caller can handle error
    }
    removeToken();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  return response;
}

/**
 * Authentication API methods
 */
export const auth = {
  /**
   * Check if public signup is enabled.
   *
   * @returns {Promise<boolean>} True if signup is allowed
   */
  async isSignupEnabled() {
    try {
      const response = await fetch("/api/auth/signup/status", {
        method: "GET",
      });
      if (!response.ok) {
        return true; // Default to enabled if check fails
      }
      const data = await response.json();
      return data.allow_signup === true;
    } catch (err) {
      console.error("Failed to check signup status:", err);
      return true; // Default to enabled if check fails
    }
  },

  /**
   * Check if setup is complete.
   *
   * @returns {Promise<boolean>} True if setup is complete
   */
  async isSetupComplete() {
    try {
      const response = await fetch("/api/auth/setup/status", {
        method: "GET",
      });
      if (!response.ok) {
        return true; // Default to complete if check fails
      }
      const data = await response.json();
      return data.is_setup_complete === true;
    } catch (err) {
      console.error("Failed to check setup status:", err);
      return true; // Default to complete if check fails
    }
  },

  /**
   * Create initial superadmin account (setup).
   *
   * @param {string} email - Admin email
   * @param {string} password - Admin password
   * @param {string} confirmPassword - Confirm password
   * @returns {Promise<object>} User and token
   */
  async setup(email, password, confirmPassword) {
    const response = await apiRequest("/auth/setup", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        confirm_password: confirmPassword,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Setup failed");
    }

    const data = await response.json();
    if (data.token) {
      setToken(data.token);
    }
    return data;
  },

  /**
   * Sign up a new user.
   *
   * @param {string} email - User email
   * @param {string} password - User password
   * @returns {Promise<object>} User and token
   */
  async signup(email, password, encryptedVaultSpaceKey = null) {
    const body = { email, password };
    if (encryptedVaultSpaceKey) {
      body.encrypted_vaultspace_key = encryptedVaultSpaceKey;
    }

    const response = await apiRequest("/auth/signup", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Signup failed");
    }

    const data = await response.json();
    if (data.token) {
      setToken(data.token);
    }
    return data;
  },

  /**
   * Login user.
   *
   * @param {string} usernameOrEmail - Username or email
   * @param {string} password - User password
   * @param {string} captchaNonce - CAPTCHA nonce (optional)
   * @param {string} captchaResponse - CAPTCHA response (optional)
   * @returns {Promise<object>} User and token
   */
  async login(
    usernameOrEmail,
    password,
    captchaNonce = "",
    captchaResponse = "",
    totpToken = null,
  ) {
    const body = { email: usernameOrEmail, password };
    // CAPTCHA response is now required - always send it (even if empty, backend will validate)
    body.captcha = captchaResponse || "";
    // Nonce is optional - only send if provided
    if (captchaNonce) {
      body.captcha_nonce = captchaNonce;
    }
    // 2FA token is optional - only send if provided
    if (totpToken) {
      body.totp_token = totpToken;
    }
    const response = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Login failed");
    }

    const data = await response.json();
    if (data.token) {
      setToken(data.token);
    }
    return data;
  },

  /**
   * Get current user profile.
   *
   * @returns {Promise<object>} Current user
   */
  async getCurrentUser() {
    const response = await apiRequest("/auth/me");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get current user");
    }
    const data = await response.json();
    return data.user;
  },

  /**
   * Get master key salt for current user.
   * Used by SSO users to retrieve their salt for master key derivation.
   *
   * @returns {Promise<string>} Base64-encoded master key salt
   */
  async getMasterKeySalt() {
    const response = await apiRequest("/auth/account/master-key-salt");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get master key salt");
    }
    const data = await response.json();
    return data.master_key_salt;
  },

  /**
   * Logout user.
   */
  async logout() {
    const token = getToken();
    // Try to call logout API to blacklist token (best effort)
    if (token) {
      try {
        await apiRequest("/auth/logout", {
          method: "POST",
        });
      } catch (error) {
        // Ignore errors - token might already be invalid
        // Still continue with local cleanup
      }
    }
    removeToken();
    // Clear master key and salt from sessionStorage and IndexedDB
    await clearUserMasterKey();
  },

  /**
   * Refresh JWT token.
   *
   * @returns {Promise<object>} New token
   */
  async refreshToken() {
    const response = await apiRequest("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ token: getToken() }),
    });

    if (!response.ok) {
      removeToken();
      throw new Error("Token refresh failed");
    }

    const data = await response.json();
    if (data.token) {
      setToken(data.token);
    }
    return data;
  },

  /**
   * Verify email using verification token.
   *
   * @param {string} token - Verification token
   * @returns {Promise<object>} User and JWT token
   */
  async verifyEmailToken(token) {
    const response = await apiRequest(`/auth/account/verify/${token}`, {
      method: "POST",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to verify email");
    }

    const data = await response.json();
    if (data.token) {
      setToken(data.token);
    }
    return data;
  },

  /**
   * Resend verification email.
   *
   * @param {string} userId - User ID (optional if email provided)
   * @param {string} email - Email address (optional if userId provided)
   * @returns {Promise<object>} Response with user_id if email was used
   */
  async resendVerificationEmail(userId, email = null) {
    const body = {};
    if (userId) {
      body.user_id = userId;
    } else if (email) {
      body.email = email;
    } else {
      throw new Error("Either userId or email is required");
    }

    const response = await apiRequest(`/auth/account/resend-verification`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to resend verification email");
    }
    return await response.json();
  },
};

/**
 * Two-Factor Authentication API methods.
 */
export const twoFactor = {
  /**
   * Get current user's 2FA status.
   *
   * @returns {Promise<object>} 2FA status
   */
  async getStatus() {
    const response = await apiRequest("/auth/2fa/status");
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new Error(error.error);
    }
    return await response.json();
  },

  /**
   * Start 2FA setup process.
   * Generates a new TOTP secret and QR code.
   *
   * @returns {Promise<object>} Setup data with secret, URI, and QR code
   */
  async setup() {
    const response = await apiRequest("/auth/2fa/setup", {
      method: "POST",
    });
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new Error(error.error);
    }
    return await response.json();
  },

  /**
   * Verify 2FA setup by providing a TOTP token.
   *
   * @param {string} token - 6-digit TOTP token
   * @returns {Promise<object>} Result with backup codes
   */
  async verifySetup(token) {
    const response = await apiRequest("/auth/2fa/verify-setup", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new Error(error.error);
    }
    return await response.json();
  },

  /**
   * Disable 2FA for the current user.
   *
   * @param {string} password - User's password for confirmation
   * @returns {Promise<object>} Result
   */
  async disable(password) {
    const response = await apiRequest("/auth/2fa/disable", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new Error(error.error);
    }
    return await response.json();
  },

  /**
   * Regenerate backup recovery codes.
   *
   * @param {string} password - User's password for confirmation
   * @returns {Promise<object>} New backup codes
   */
  async regenerateBackupCodes(password) {
    const response = await apiRequest("/auth/2fa/regenerate-backup", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new Error(error.error);
    }
    return await response.json();
  },
};

/**
 * Account API methods
 */
export const account = {
  /**
   * Get current user account information.
   *
   * @returns {Promise<object>} Current user account info
   */
  async getAccount() {
    const response = await apiRequest("/auth/me");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get account information");
    }
    const data = await response.json();
    return data.user;
  },

  /**
   * Update user email.
   *
   * @param {string} email - New email address
   * @param {string} password - Current password for verification
   * @returns {Promise<object>} Updated user info
   */
  async updateEmail(email, password) {
    const response = await apiRequest("/auth/account/email", {
      method: "PUT",
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update email");
    }

    const data = await response.json();
    return data.user;
  },

  /**
   * Change user password.
   *
   * @param {string} currentPassword - Current password
   * @param {string} newPassword - New password
   * @returns {Promise<void>}
   */
  async changePassword(currentPassword, newPassword) {
    const response = await apiRequest("/auth/account/password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to change password");
    }
  },

  /**
   * Delete user account.
   *
   * @param {string} password - Current password for confirmation
   * @returns {Promise<void>}
   */
  async deleteAccount(password) {
    const response = await apiRequest("/auth/account", {
      method: "DELETE",
      body: JSON.stringify({ password }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete account");
    }
  },
};

/**
 * VaultSpace API methods
 */
export const vaultspaces = {
  /**
   * List all VaultSpaces for current user.
   *
   * @returns {Promise<Array>} List of VaultSpaces
   */
  async list() {
    const response = await apiRequest("/vaultspaces");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list VaultSpaces");
    }
    const data = await response.json();
    return data.vaultspaces || [];
  },

  /**
   * Get VaultSpace details.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @returns {Promise<object>} VaultSpace details
   */
  async get(vaultspaceId) {
    const response = await apiRequest(`/vaultspaces/${vaultspaceId}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get VaultSpace");
    }
    const data = await response.json();
    return data.vaultspace;
  },

  /**
   * Create a new VaultSpace.
   *
   * @param {object} vaultspace - VaultSpace data
   * @returns {Promise<object>} Created VaultSpace
   */
  async create(vaultspace) {
    const response = await apiRequest("/vaultspaces", {
      method: "POST",
      body: JSON.stringify(vaultspace),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create VaultSpace");
    }
    const data = await response.json();
    return data.vaultspace;
  },

  /**
   * Update VaultSpace.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {object} updates - Updates to apply
   * @returns {Promise<object>} Updated VaultSpace
   */
  async update(vaultspaceId, updates) {
    const response = await apiRequest(`/vaultspaces/${vaultspaceId}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update VaultSpace");
    }
    const data = await response.json();
    return data.vaultspace;
  },

  /**
   * Delete VaultSpace.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @returns {Promise<void>}
   */
  async delete(vaultspaceId) {
    const response = await apiRequest(`/vaultspaces/${vaultspaceId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete VaultSpace");
    }
  },

  /**
   * Get VaultSpace encrypted key for current user.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @returns {Promise<object|null>} VaultSpaceKey or null if not found (404)
   */
  async getKey(vaultspaceId) {
    const response = await apiRequest(`/vaultspaces/${vaultspaceId}/keys`);
    if (!response.ok) {
      // Return null for 404 (key not found) - this is expected and handled by caller
      if (response.status === 404) {
        return null;
      }
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get VaultSpace key");
    }
    const data = await response.json();
    return data.vaultspace_key;
  },

  /**
   * Share VaultSpace with a user.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {string} userId - User ID to share with
   * @param {string} encryptedKey - Encrypted VaultSpace key
   * @returns {Promise<object>} VaultSpaceKey
   */
  async share(vaultspaceId, userId, encryptedKey) {
    const response = await apiRequest(`/vaultspaces/${vaultspaceId}/share`, {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        encrypted_key: encryptedKey,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to share VaultSpace");
    }
    const data = await response.json();
    return data.vaultspace_key;
  },
};

/**
 * Files API methods
 */
export const files = {
  /**
   * List files in a VaultSpace.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {string} parentId - Optional parent folder ID
   * @param {number} page - Page number (default: 1)
   * @param {number} perPage - Items per page (default: 50)
   * @returns {Promise<object>} List of files with pagination info
   */
  async list(
    vaultspaceId,
    parentId = null,
    page = 1,
    perPage = 50,
    cacheBust = false,
  ) {
    const params = new URLSearchParams({ vaultspace_id: vaultspaceId });
    if (parentId) {
      params.append("parent_id", parentId);
    }
    params.append("page", page.toString());
    params.append("per_page", perPage.toString());

    // Add cache-busting parameter if requested (for immediate reload after creation)
    // Use timestamp with high-resolution time to ensure uniqueness
    if (cacheBust) {
      const timestamp = Date.now();
      const highResTime = performance.now ? performance.now() : 0;
      // Combine timestamp with high-res time for better uniqueness
      params.append("_t", `${timestamp}_${highResTime.toFixed(3)}`);
    }

    const response = await apiRequest(`/v2/files?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list files");
    }
    const data = await response.json();
    return data;
  },

  /**
   * Get file details and encrypted FileKey.
   *
   * @param {string} fileId - File ID
   * @param {string} vaultspaceId - VaultSpace ID
   * @returns {Promise<object>} File and FileKey
   */
  async get(fileId, vaultspaceId) {
    const params = new URLSearchParams({ vaultspace_id: vaultspaceId });
    const response = await apiRequest(
      `/v2/files/${fileId}?${params.toString()}`,
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get file");
    }
    const data = await response.json();
    return data;
  },

  /**
   * Upload a file.
   *
   * @param {object} fileData - File upload data
   * @param {function} onProgress - Optional progress callback (loaded, total, speed, timeRemaining)
   * @returns {object} Object with `promise` and `cancel` function
   */
  upload(fileData, onProgress = null) {
    const formData = new FormData();
    // Pass the original filename when appending the blob to FormData
    const fileName = fileData.originalName || "unnamed";
    formData.append("file", fileData.file, fileName);
    formData.append("vaultspace_id", fileData.vaultspaceId);
    formData.append("encrypted_file_key", fileData.encryptedFileKey);
    if (fileData.parentId) {
      formData.append("parent_id", fileData.parentId);
    }
    if (fileData.encryptedMetadata) {
      formData.append("encrypted_metadata", fileData.encryptedMetadata);
    }

    const token = getToken();
    const url = `${API_BASE_URL}/v2/files`;

    let xhr = null;
    let isCancelled = false;

    const promise = new Promise((resolve, reject) => {
      xhr = new XMLHttpRequest();

      // Progress tracking
      let lastLoaded = 0;
      let lastTime = Date.now();
      const PROGRESS_MARGIN = 2.5; // Margin of 2-3 seconds for remaining time

      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress && !isCancelled) {
          const currentTime = Date.now();
          const timeDiff = (currentTime - lastTime) / 1000; // seconds
          const loadedDiff = e.loaded - lastLoaded; // bytes

          let speed = 0;
          let timeRemaining = null;

          if (timeDiff > 0 && loadedDiff > 0) {
            speed = loadedDiff / timeDiff; // bytes per second
            const remaining = e.total - e.loaded;
            const calculatedTime = remaining / speed;
            // Add the margin of 2-3 seconds
            timeRemaining = calculatedTime + PROGRESS_MARGIN;
          }

          onProgress(e.loaded, e.total, speed, timeRemaining);

          lastLoaded = e.loaded;
          lastTime = currentTime;
        }
      });

      xhr.addEventListener("load", () => {
        if (isCancelled) {
          return;
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const data = JSON.parse(xhr.responseText);
            resolve(data);
          } catch (e) {
            reject(new Error("Invalid response format"));
          }
        } else {
          try {
            const errorData = JSON.parse(xhr.responseText);
            const error = new Error(errorData.error || "Failed to upload file");
            // Attach quota_info if available
            if (errorData.quota_info) {
              error.quota_info = errorData.quota_info;
            }
            reject(error);
          } catch (e) {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener("error", () => {
        if (!isCancelled) {
          reject(new Error("Network error during upload"));
        }
      });

      xhr.addEventListener("abort", () => {
        isCancelled = true;
        reject(new Error("Upload cancelled"));
      });

      xhr.open("POST", url);
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.send(formData);
    });

    const cancel = () => {
      if (xhr && xhr.readyState !== XMLHttpRequest.DONE) {
        isCancelled = true;
        xhr.abort();
      }
    };

    return {
      promise,
      cancel,
    };
  },

  /**
   * Delete a file.
   *
   * @param {string} fileId - File ID
   * @returns {Promise<void>}
   */
  async delete(fileId) {
    const response = await apiRequest(`/v2/files/${fileId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete file");
    }
  },

  /**
   * Create a folder.
   *
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {string} name - Folder name
   * @param {string} parentId - Optional parent folder ID
   * @returns {Promise<object>} Created folder
   */
  async createFolder(vaultspaceId, name, parentId = null) {
    const response = await apiRequest("/v2/files/folders", {
      method: "POST",
      body: JSON.stringify({
        vaultspace_id: vaultspaceId,
        name: name,
        parent_id: parentId,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create folder");
    }

    const data = await response.json();
    return data.folder;
  },

  /**
   * Rename a file or folder.
   *
   * @param {string} fileId - File ID
   * @param {string} newName - New name
   * @returns {Promise<object>} Updated file
   */
  async rename(fileId, newName) {
    const response = await apiRequest(`/v2/files/${fileId}/rename`, {
      method: "PUT",
      body: JSON.stringify({ name: newName }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to rename file");
    }
    const data = await response.json();
    return data.file;
  },

  /**
   * Move a file or folder.
   *
   * @param {string} fileId - File ID
   * @param {string} newParentId - New parent folder ID (null for root)
   * @returns {Promise<object>} Updated file
   */
  async move(fileId, newParentId = null) {
    const response = await apiRequest(`/v2/files/${fileId}/move`, {
      method: "PUT",
      body: JSON.stringify({ parent_id: newParentId }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to move file");
    }
    const data = await response.json();
    return data.file;
  },

  /**
   * Toggle star status of a file.
   *
   * @param {string} fileId - File ID
   * @returns {Promise<object>} Updated file
   */
  async toggleStar(fileId) {
    const response = await apiRequest(`/v2/files/${fileId}/star`, {
      method: "POST",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to toggle star");
    }
    const data = await response.json();
    return data.file;
  },

  /**
   * List all starred files.
   *
   * @param {string} vaultspaceId - Optional VaultSpace ID filter
   * @returns {Promise<object>} List of starred files
   */
  async listStarred(vaultspaceId = null, cacheBust = false) {
    const params = new URLSearchParams();
    if (vaultspaceId) {
      params.append("vaultspace_id", vaultspaceId);
    }

    // Add cache-busting parameter if requested
    if (cacheBust) {
      const timestamp = Date.now();
      const highResTime = performance.now ? performance.now() : 0;
      params.append("_t", `${timestamp}_${highResTime.toFixed(3)}`);
    }

    const response = await apiRequest(`/v2/files/starred?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list starred files");
    }
    return await response.json();
  },

  /**
   * List recently accessed/modified files.
   *
   * @param {string} vaultspaceId - Optional VaultSpace ID filter
   * @param {number} limit - Maximum number of files (default: 50)
   * @param {number} days - Number of days to look back (default: 30)
   * @returns {Promise<object>} List of recent files
   */
  async listRecent(
    vaultspaceId = null,
    limit = 50,
    days = 30,
    cacheBust = false,
  ) {
    const params = new URLSearchParams();
    if (vaultspaceId) {
      params.append("vaultspace_id", vaultspaceId);
    }
    params.append("limit", limit.toString());
    params.append("days", days.toString());

    // Add cache-busting parameter if requested
    if (cacheBust) {
      const timestamp = Date.now();
      const highResTime = performance.now ? performance.now() : 0;
      params.append("_t", `${timestamp}_${highResTime.toFixed(3)}`);
    }

    const response = await apiRequest(`/v2/files/recent?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list recent files");
    }
    return await response.json();
  },

  /**
   * Download encrypted file data.
   *
   * @param {string} fileId - File ID
   * @param {string} vaultspaceId - VaultSpace ID
   * @param {function} onProgress - Optional progress callback (loaded, total, speed, timeRemaining)
   * @returns {Promise<ArrayBuffer>} Encrypted file data
   */
  async download(fileId, vaultspaceId, onProgress = null) {
    const params = new URLSearchParams({ vaultspace_id: vaultspaceId });
    const token = getToken();
    const url = `${API_BASE_URL}/v2/files/${fileId}/download?${params.toString()}`;

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.responseType = "arraybuffer";

      // Progress tracking
      let lastLoaded = 0;
      let lastTime = Date.now();
      const PROGRESS_MARGIN = 2.5; // Margin of 2-3 seconds for remaining time

      xhr.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress) {
          const currentTime = Date.now();
          const timeDiff = (currentTime - lastTime) / 1000; // seconds
          const loadedDiff = e.loaded - lastLoaded; // bytes

          let speed = 0;
          let timeRemaining = null;

          if (timeDiff > 0 && loadedDiff > 0) {
            speed = loadedDiff / timeDiff; // bytes per second
            const remaining = e.total - e.loaded;
            const calculatedTime = remaining / speed;
            // Add the margin of 2-3 seconds
            timeRemaining = calculatedTime + PROGRESS_MARGIN;
          }

          onProgress(e.loaded, e.total, speed, timeRemaining);

          lastLoaded = e.loaded;
          lastTime = currentTime;
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(xhr.response);
        } else {
          try {
            const errorText = new TextDecoder().decode(xhr.response);
            const errorData = JSON.parse(errorText);
            reject(new Error(errorData.error || "Failed to download file"));
          } catch (e) {
            reject(new Error(`Download failed: ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener("error", () => {
        reject(new Error("Network error during download"));
      });

      xhr.addEventListener("abort", () => {
        reject(new Error("Download cancelled"));
      });

      xhr.open("GET", url);
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.send();
    });
  },

  /**
   * Batch delete multiple files.
   *
   * @param {string[]} fileIds - Array of file IDs to delete
   * @returns {Promise<object>} Batch operation results
   */
  async batchDelete(fileIds) {
    const response = await apiRequest("/v2/files/batch/delete", {
      method: "POST",
      body: JSON.stringify({ file_ids: fileIds }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete files");
    }
    return await response.json();
  },

  /**
   * Batch move multiple files.
   *
   * @param {string[]} fileIds - Array of file IDs to move
   * @param {string|null} newParentId - New parent folder ID (null for root)
   * @returns {Promise<object>} Batch operation results
   */
  async batchMove(fileIds, newParentId = null) {
    const response = await apiRequest("/v2/files/batch/move", {
      method: "POST",
      body: JSON.stringify({
        file_ids: fileIds,
        new_parent_id: newParentId,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to move files");
    }
    return await response.json();
  },

  /**
   * Batch rename multiple files.
   *
   * @param {Array<{file_id: string, new_name: string}>} fileRenames - Array of rename operations
   * @returns {Promise<object>} Batch operation results
   */
  async batchRename(fileRenames) {
    const response = await apiRequest("/v2/files/batch/rename", {
      method: "POST",
      body: JSON.stringify({ file_renames: fileRenames }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to rename files");
    }
    return await response.json();
  },

  /**
   * Copy a file or folder.
   *
   * @param {string} fileId - File ID to copy
   * @param {object} options - Copy options
   * @param {string|null} options.newParentId - New parent folder ID (null for root)
   * @param {string|null} options.newVaultspaceId - New VaultSpace ID (null to keep same)
   * @param {string|null} options.newName - New name (null to keep same)
   * @returns {Promise<object>} Copied file
   */
  async copy(fileId, options = {}) {
    const response = await apiRequest(`/v2/files/${fileId}/copy`, {
      method: "POST",
      body: JSON.stringify({
        new_parent_id: options.newParentId || null,
        new_vaultspace_id: options.newVaultspaceId || null,
        new_name: options.newName || null,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to copy file");
    }
    const data = await response.json();
    return data.file;
  },

  /**
   * Create an upload session for chunked file uploads.
   *
   * @param {object} fileData - File upload data
   * @param {string} fileData.vaultspaceId - VaultSpace ID
   * @param {string} fileData.originalName - Original filename
   * @param {number} fileData.totalSize - Total file size in bytes
   * @param {number} fileData.chunkSize - Chunk size in bytes (default 5MB)
   * @param {string} fileData.encryptedFileKey - Encrypted file key
   * @param {string|null} fileData.parentId - Parent folder ID (optional)
   * @param {string|null} fileData.encryptedMetadata - Encrypted metadata (optional)
   * @param {string|null} fileData.mimeType - MIME type (optional)
   * @returns {Promise<object>} Session info with session_id and file_id
   */
  async createUploadSession(fileData) {
    const response = await apiRequest("/v2/files/upload/session", {
      method: "POST",
      body: JSON.stringify({
        vaultspace_id: fileData.vaultspaceId,
        original_name: fileData.originalName,
        total_size: fileData.totalSize,
        chunk_size: fileData.chunkSize || 5 * 1024 * 1024, // Default 5MB
        encrypted_file_key: fileData.encryptedFileKey,
        parent_id: fileData.parentId || null,
        encrypted_metadata: fileData.encryptedMetadata || null,
        mime_type: fileData.mimeType || null,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create upload session");
    }

    return await response.json();
  },

  /**
   * Upload a single chunk for chunked file uploads.
   *
   * @param {string} sessionId - Upload session ID
   * @param {number} chunkIndex - Zero-based chunk index
   * @param {Blob} chunk - Chunk data as Blob
   * @param {string|null} sessionData - Optional JSON string with session data for fallback recreation
   * @param {function} onProgress - Optional progress callback (uploadedSize, totalSize)
   * @returns {object} Object with `promise` and `cancel` function
   */
  uploadChunk(
    sessionId,
    chunkIndex,
    chunk,
    sessionData = null,
    onProgress = null,
  ) {
    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("chunk_index", chunkIndex.toString());
    formData.append("chunk", chunk);
    if (sessionData) {
      formData.append("session_data", sessionData);
    }

    const token = getToken();
    const url = `${API_BASE_URL}/v2/files/upload/chunk`;

    let xhr = null;
    let isCancelled = false;

    let resolvePromise, rejectPromise;
    const promise = new Promise((resolve, reject) => {
      resolvePromise = resolve;
      rejectPromise = reject;
    });

    xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress && !isCancelled) {
        onProgress(e.loaded, e.total);
      }
    });

    xhr.addEventListener("load", () => {
      if (isCancelled) {
        return;
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        // Check if response is empty
        if (!xhr.responseText || xhr.responseText.trim() === "") {
          console.error("Empty response from server for chunk upload");
          if (rejectPromise)
            rejectPromise(new Error("Empty response from server"));
          return;
        }

        try {
          const data = JSON.parse(xhr.responseText);
          // Validate response structure
          if (!data || typeof data !== "object") {
            console.error(
              "Invalid chunk upload response:",
              data,
              "Raw:",
              xhr.responseText,
            );
            if (rejectPromise)
              rejectPromise(new Error("Invalid response format from server"));
            return;
          }
          if (resolvePromise) {
            resolvePromise(data);
            // Clear references to prevent double resolution
            resolvePromise = null;
            rejectPromise = null;
          }
        } catch (e) {
          console.error(
            "Failed to parse chunk upload response:",
            e,
            "Raw response:",
            xhr.responseText,
          );
          if (rejectPromise)
            rejectPromise(new Error(`Invalid response format: ${e.message}`));
        }
      } else {
        // Handle error responses
        try {
          if (xhr.responseText) {
            const errorData = JSON.parse(xhr.responseText);
            if (rejectPromise)
              rejectPromise(
                new Error(errorData.error || "Failed to upload chunk"),
              );
          } else {
            if (rejectPromise) {
              rejectPromise(
                new Error(
                  `Upload chunk failed with status ${xhr.status}: No response body`,
                ),
              );
            }
          }
        } catch (e) {
          console.error(
            "Failed to parse error response:",
            e,
            "Status:",
            xhr.status,
            "Response:",
            xhr.responseText,
          );
          if (rejectPromise) {
            rejectPromise(
              new Error(
                `Upload chunk failed: HTTP ${xhr.status} - ${xhr.statusText || "Unknown error"}`,
              ),
            );
          }
        }
      }
    });

    xhr.addEventListener("error", (event) => {
      if (!isCancelled) {
        console.error("Network error during chunk upload:", event);
        if (rejectPromise)
          rejectPromise(new Error("Network error during chunk upload"));
      }
    });

    xhr.addEventListener("timeout", () => {
      if (!isCancelled) {
        console.error("Timeout during chunk upload");
        if (rejectPromise) rejectPromise(new Error("Upload timeout"));
      }
    });

    xhr.addEventListener("abort", () => {
      isCancelled = true;
      if (rejectPromise) rejectPromise(new Error("Chunk upload cancelled"));
    });

    xhr.open("POST", url);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(formData);

    const cancel = () => {
      if (xhr && xhr.readyState !== XMLHttpRequest.DONE) {
        isCancelled = true;
        xhr.abort();
      }
    };

    return {
      promise,
      cancel,
    };
  },

  /**
   * Complete chunked upload and create File record.
   *
   * @param {string} sessionId - Upload session ID
   * @param {string|null} encryptedHash - Optional encrypted hash (computed if not provided)
   * @returns {Promise<object>} File info and FileKey
   */
  async completeUpload(sessionId, encryptedHash = null) {
    const response = await apiRequest("/v2/files/upload/complete", {
      method: "POST",
      body: JSON.stringify({
        session_id: sessionId,
        encrypted_hash: encryptedHash,
      }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to complete upload");
    }

    return await response.json();
  },

  /**
   * Get upload session status.
   *
   * @param {string} sessionId - Upload session ID
   * @returns {Promise<object>} Session status and progress
   */
  async getUploadStatus(sessionId) {
    const response = await apiRequest(`/v2/files/upload/session/${sessionId}`, {
      method: "GET",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get upload status");
    }

    return await response.json();
  },

  /**
   * Cancel upload session and delete temporary file.
   *
   * @param {string} sessionId - Upload session ID
   * @returns {Promise<void>}
   */
  async cancelUpload(sessionId) {
    const response = await apiRequest(`/v2/files/upload/session/${sessionId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to cancel upload");
    }
  },
};

/**
 * Admin API methods
 */
export const admin = {
  /**
   * Get system statistics.
   *
   * @returns {Promise<object>} System statistics
   */
  async getStats() {
    const response = await apiRequest("/admin/stats");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get stats");
    }
    return await response.json();
  },

  /**
   * List users with search and filters.
   *
   * @param {object} options - Search options
   * @param {string} options.query - Search query
   * @param {string} options.role - Filter by role
   * @param {number} options.page - Page number
   * @param {number} options.per_page - Items per page
   * @returns {Promise<object>} Paginated users
   */
  async listUsers(options = {}) {
    const params = new URLSearchParams();
    if (options.query) params.append("query", String(options.query));
    if (options.role) params.append("role", String(options.role));
    if (options.page !== undefined && options.page !== null) {
      params.append("page", String(options.page));
    }
    if (options.per_page !== undefined && options.per_page !== null) {
      params.append("per_page", String(options.per_page));
    }

    const response = await apiRequest(`/admin/users?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list users");
    }
    return await response.json();
  },

  /**
   * Get user details.
   *
   * @param {string} userId - User ID
   * @returns {Promise<object>} User details
   */
  async getUserDetails(userId) {
    const response = await apiRequest(`/admin/users/${userId}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get user details");
    }
    return await response.json();
  },

  /**
   * Update user.
   *
   * @param {string} userId - User ID
   * @param {object} data - User data to update
   * @returns {Promise<object>} Updated user
   */
  async updateUser(userId, data) {
    const response = await apiRequest(`/admin/users/${userId}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update user");
    }
    return await response.json();
  },

  /**
   * Delete user.
   *
   * @param {string} userId - User ID
   * @returns {Promise<void>}
   */
  async deleteUser(userId) {
    const response = await apiRequest(`/admin/users/${userId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete user");
    }
  },

  /**
   * Update user role.
   *
   * @param {string} userId - User ID
   * @param {string} role - New role (user, admin, superadmin)
   * @returns {Promise<object>} Updated user
   */
  async updateUserRole(userId, role) {
    const response = await apiRequest(`/admin/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ global_role: role }),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update user role");
    }
    return await response.json();
  },

  /**
   * List quotas.
   *
   * @returns {Promise<Array>} List of quotas
   */
  async listQuotas() {
    const response = await apiRequest("/admin/quotas");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list quotas");
    }
    const data = await response.json();
    return data.quotas || [];
  },

  /**
   * Create or update quota.
   *
   * @param {object} quotaData - Quota data
   * @param {string} quotaData.user_id - User ID
   * @param {number} [quotaData.max_storage_bytes] - Max storage in bytes
   * @param {number} [quotaData.max_files] - Max files
   * @returns {Promise<object>} Created/updated quota
   */
  async createOrUpdateQuota(quotaData) {
    const response = await apiRequest("/admin/quotas", {
      method: "POST",
      body: JSON.stringify(quotaData),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create/update quota");
    }
    return await response.json();
  },

  /**
   * Get audit logs with filters.
   *
   * @param {object} options - Filter options
   * @param {number} options.limit - Maximum number of logs
   * @param {string} options.action - Filter by action
   * @param {string} options.file_id - Filter by file ID
   * @param {boolean} options.success - Filter by success status
   * @param {string} options.user_ip - Filter by user IP
   * @returns {Promise<object>} Audit logs
   */
  async getAuditLogs(options = {}) {
    const params = new URLSearchParams();
    if (options.limit) params.append("limit", options.limit.toString());
    if (options.action) params.append("action", options.action);
    if (options.file_id) params.append("file_id", options.file_id);
    if (options.success !== undefined)
      params.append("success", options.success.toString());
    if (options.user_ip) params.append("user_ip", options.user_ip);

    const response = await apiRequest(`/admin/audit-logs?${params.toString()}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get audit logs");
    }
    return await response.json();
  },

  /**
   * Export audit logs as CSV.
   *
   * @param {number} limit - Maximum number of logs to export
   * @returns {Promise<Blob>} CSV file blob
   */
  async exportAuditLogsCSV(limit = 1000) {
    const params = new URLSearchParams();
    params.append("limit", limit.toString());

    const response = await apiRequest(
      `/admin/audit-logs/export/csv?${params.toString()}`,
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to export audit logs");
    }
    return await response.blob();
  },

  /**
   * Export audit logs as JSON.
   *
   * @param {number} limit - Maximum number of logs to export
   * @returns {Promise<Blob>} JSON file blob
   */
  async exportAuditLogsJSON(limit = 1000) {
    const params = new URLSearchParams();
    params.append("limit", limit.toString());

    const response = await apiRequest(
      `/admin/audit-logs/export/json?${params.toString()}`,
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to export audit logs");
    }
    return await response.blob();
  },

  /**
   * Invite a user by email.
   *
   * @param {string} email - Email address to invite
   * @returns {Promise<object>} Invitation object
   */
  async inviteUser(email) {
    const response = await apiRequest("/admin/users/invite", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to invite user");
    }
    const data = await response.json();
    return data.invitation;
  },

  /**
   * Send verification email to user.
   *
   * @param {string} userId - User ID
   * @returns {Promise<void>}
   */
  async sendVerificationEmail(userId) {
    const response = await apiRequest(
      `/admin/users/${userId}/send-verification`,
      {
        method: "POST",
      },
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to send verification email");
    }
  },

  /**
   * List invitations.
   *
   * @param {object} options - Filter options
   * @param {string} options.invited_by - Filter by inviter user ID
   * @param {string} options.status - Filter by status (pending, accepted, expired)
   * @param {number} options.page - Page number
   * @param {number} options.per_page - Items per page
   * @returns {Promise<object>} Paginated invitations
   */
  async listInvitations(options = {}) {
    const params = new URLSearchParams();
    if (options.invited_by) params.append("invited_by", options.invited_by);
    if (options.status) params.append("status", options.status);
    if (options.page) params.append("page", options.page.toString());
    if (options.per_page)
      params.append("per_page", options.per_page.toString());

    const response = await apiRequest(
      `/admin/invitations?${params.toString()}`,
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list invitations");
    }
    return await response.json();
  },

  /**
   * Create invitation.
   *
   * @param {string} email - Email address
   * @returns {Promise<object>} Invitation object
   */
  async createInvitation(email) {
    const response = await apiRequest("/admin/invitations", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create invitation");
    }
    const data = await response.json();
    return data.invitation;
  },

  /**
   * Resend invitation.
   *
   * @param {string} invitationId - Invitation ID
   * @returns {Promise<void>}
   */
  async resendInvitation(invitationId) {
    const response = await apiRequest(
      `/admin/invitations/${invitationId}/resend`,
      {
        method: "POST",
      },
    );
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to resend invitation");
    }
  },

  /**
   * Cancel invitation.
   *
   * @param {string} invitationId - Invitation ID
   * @returns {Promise<void>}
   */
  async cancelInvitation(invitationId) {
    const response = await apiRequest(`/admin/invitations/${invitationId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to cancel invitation");
    }
  },

  /**
   * Get system settings.
   *
   * @returns {Promise<object>} System settings
   */
  async getSettings() {
    const response = await apiRequest("/admin/settings");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get settings");
    }
    const data = await response.json();
    return data.settings;
  },

  /**
   * Update system settings.
   *
   * @param {object} settings - Settings to update
   * @returns {Promise<void>}
   */
  async updateSettings(settings) {
    const response = await apiRequest("/admin/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update settings");
    }
  },

  /**
   * Get password authentication status.
   *
   * @returns {Promise<boolean>} Password authentication enabled status
   */
  async getPasswordAuthStatus() {
    const settings = await this.getSettings();
    return (
      settings.password_authentication_enabled === "true" ||
      settings.password_authentication_enabled === true
    );
  },

  /**
   * Update password authentication status.
   *
   * @param {boolean} enabled - Whether password authentication is enabled
   * @returns {Promise<void>}
   */
  async updatePasswordAuthStatus(enabled) {
    await this.updateSettings({
      password_authentication_enabled: enabled,
    });
  },

  /**
   * List domain rules.
   *
   * @returns {Promise<Array>} List of domain rules
   */
  async listDomainRules() {
    const response = await apiRequest("/admin/domain-rules");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list domain rules");
    }
    const data = await response.json();
    return data.rules || [];
  },

  /**
   * Create domain rule.
   *
   * @param {object} rule - Domain rule data
   * @returns {Promise<object>} Created rule
   */
  async createDomainRule(rule) {
    const response = await apiRequest("/admin/domain-rules", {
      method: "POST",
      body: JSON.stringify(rule),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create domain rule");
    }
    const data = await response.json();
    return data.rule;
  },

  /**
   * Update domain rule.
   *
   * @param {string} ruleId - Rule ID
   * @param {object} rule - Rule data to update
   * @returns {Promise<object>} Updated rule
   */
  async updateDomainRule(ruleId, rule) {
    const response = await apiRequest(`/admin/domain-rules/${ruleId}`, {
      method: "PUT",
      body: JSON.stringify(rule),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update domain rule");
    }
    const data = await response.json();
    return data.rule;
  },

  /**
   * Delete domain rule.
   *
   * @param {string} ruleId - Rule ID
   * @returns {Promise<void>}
   */
  async deleteDomainRule(ruleId) {
    const response = await apiRequest(`/admin/domain-rules/${ruleId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete domain rule");
    }
  },

  /**
   * List all API keys.
   *
   * @returns {Promise<Array>} List of API keys
   */
  async listApiKeys() {
    const response = await apiRequest("/admin/api-keys");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list API keys");
    }
    const data = await response.json();
    return data.api_keys || [];
  },

  /**
   * Generate a new API key.
   *
   * @param {string} userId - User ID
   * @param {string} name - API key name/description
   * @returns {Promise<object>} API key object with plaintext key (shown only once)
   */
  async generateApiKey(userId, name) {
    const response = await apiRequest("/admin/api-keys", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, name }),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to generate API key");
    }
    const data = await response.json();
    return {
      api_key: data.api_key,
      key: data.key, // Plaintext key shown only once
    };
  },

  /**
   * Revoke (delete) an API key.
   *
   * @param {string} keyId - API key ID
   * @returns {Promise<void>}
   */
  async revokeApiKey(keyId) {
    const response = await apiRequest(`/admin/api-keys/${keyId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to revoke API key");
    }
  },

  /**
   * List API keys for a specific user.
   *
   * @param {string} userId - User ID
   * @returns {Promise<Array>} List of API keys for the user
   */
  async listUserApiKeys(userId) {
    const response = await apiRequest(`/admin/api-keys/user/${userId}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list user API keys");
    }
    const data = await response.json();
    return data.api_keys || [];
  },

  /**
   * List SSO providers.
   *
   * @returns {Promise<Array>} List of SSO providers
   */
  async listSSOProviders() {
    const response = await apiRequest("/admin/sso-providers");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list SSO providers");
    }
    const data = await response.json();
    return data.providers || [];
  },

  /**
   * Get a specific SSO provider.
   *
   * @param {string} providerId - Provider ID
   * @returns {Promise<object>} SSO provider
   */
  async getSSOProvider(providerId) {
    const response = await apiRequest(`/admin/sso-providers/${providerId}`);
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to get SSO provider");
    }
    const data = await response.json();
    return data.provider;
  },

  /**
   * Create a new SSO provider.
   *
   * @param {object} provider - SSO provider data
   * @returns {Promise<object>} Created provider
   */
  async createSSOProvider(provider) {
    const response = await apiRequest("/admin/sso-providers", {
      method: "POST",
      body: JSON.stringify(provider),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to create SSO provider");
    }
    const data = await response.json();
    return data.provider;
  },

  /**
   * Update an SSO provider.
   *
   * @param {string} providerId - Provider ID
   * @param {object} provider - Provider data to update
   * @returns {Promise<object>} Updated provider
   */
  async updateSSOProvider(providerId, provider) {
    const response = await apiRequest(`/admin/sso-providers/${providerId}`, {
      method: "PUT",
      body: JSON.stringify(provider),
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to update SSO provider");
    }
    const data = await response.json();
    return data.provider;
  },

  /**
   * Delete an SSO provider.
   *
   * @param {string} providerId - Provider ID
   * @returns {Promise<void>}
   */
  async deleteSSOProvider(providerId) {
    const response = await apiRequest(`/admin/sso-providers/${providerId}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to delete SSO provider");
    }
  },

  /**
   * Test SMTP configuration by sending a test email.
   *
   * @returns {Promise<object>} Test result with success/error message
   */
  async testSMTP() {
    const response = await apiRequest("/admin/test-smtp", {
      method: "POST",
    });
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to test SMTP");
    }
    return await response.json();
  },
};

/**
 * SSO API methods
 */
export const sso = {
  /**
   * List active SSO providers (public endpoint).
   *
   * @returns {Promise<Array>} List of active SSO providers
   */
  async listProviders() {
    const response = await apiRequest("/sso/providers");
    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to list SSO providers");
    }
    const data = await response.json();
    return data.providers || [];
  },

  /**
   * Initiate SSO login flow.
   *
   * @param {string} providerId - SSO provider ID
   * @param {string} returnUrl - Optional return URL after authentication
   * @returns {Promise<string>} Redirect URL to SSO provider
   */
  async initiateLogin(providerId, returnUrl = null) {
    const body = {};
    if (returnUrl) {
      body.return_url = returnUrl;
    }

    const response = await apiRequest(`/sso/login/${providerId}`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to initiate SSO login");
    }

    const data = await response.json();
    return data.redirect_url;
  },

  /**
   * Initiate magic link login (requires email).
   *
   * @param {string} providerId - SSO provider ID
   * @param {string} email - Email address
   * @param {string} returnUrl - Optional return URL after login
   * @returns {Promise<object>} Response with message
   */
  async initiateMagicLinkLogin(providerId, email, returnUrl = null) {
    const body = { email };
    if (returnUrl) {
      body.return_url = returnUrl;
    }

    const response = await apiRequest(`/sso/login/${providerId}`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to send magic link");
    }

    return await response.json();
  },

  /**
   * Check if an email domain requires SSO authentication.
   *
   * @param {string} email - Email address to check
   * @returns {Promise<object>} Domain info with SSO requirement
   */
  async checkDomain(email) {
    const response = await apiRequest("/sso/check-domain", {
      method: "POST",
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      const errorData = await parseErrorResponse(response);
      throw new Error(errorData.error || "Failed to check domain");
    }

    return await response.json();
  },
};

export default {
  auth,
  account,
  vaultspaces,
  files,
  admin,
  sso,
};

// Export search service
export { search } from "./search";

// Export preview service
export { preview } from "./preview";

// Export trash service
export { trash } from "./trash";

// Export quota service
export { quota } from "./quota";

// Export thumbnails service
export { thumbnails } from "./thumbnails";
