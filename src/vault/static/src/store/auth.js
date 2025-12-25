import { defineStore } from "pinia";
import {
  apiRequest,
  parseErrorResponse,
  isNetworkError,
  removeToken as apiRemoveToken,
} from "../services/api";
import { clearUserMasterKey } from "../services/keyManager";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    token: localStorage.getItem("jwt_token") || null,
    isAuthenticated: !!localStorage.getItem("jwt_token"),
    authConfig: null,
    // Default to true to prevent redirect loops on existing installations
    // It will be updated to false if backend explicitly says so
    isSetupComplete: true,
  }),

  actions: {
    setAuth(user, token) {
      this.user = user;
      this.token = token;
      this.isAuthenticated = true;
      if (token) {
        localStorage.setItem("jwt_token", token);
      }
    },

    async login(
      usernameOrEmail,
      password,
      captchaNonce = "",
      captchaResponse = "",
      totpToken = null,
    ) {
      const body = {
        email: usernameOrEmail,
        password,
        captcha: captchaResponse || "",
      };
      if (captchaNonce) body.captcha_nonce = captchaNonce;
      if (totpToken) body.totp_token = totpToken;

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
        this.setAuth(data.user, data.token);
      }
      return data;
    },

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
        this.setAuth(data.user, data.token);
      }
      return data;
    },

    async setup(email, password, confirmPassword) {
      this.purgeState();

      const response = await apiRequest("/auth/setup", {
        method: "POST",
        body: JSON.stringify({
          email,
          password,
          confirm_password: confirmPassword,
        }),
        skipAutoRefresh: true,
      });

      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Setup failed");
      }

      const data = await response.json();
      this.purgeState();
      this.isSetupComplete = true;

      return {
        user: data.user ?? null,
        email_verification_required: data.email_verification_required ?? false,
        message:
          data.message ??
          "Superadmin account created successfully. Please log in to continue.",
      };
    },

    async logout() {
      if (this.token) {
        try {
          await apiRequest("/auth/logout", { method: "POST" });
        } catch (error) {
          // Ignore
        }
      }
      await this.purgeState();
    },

    async purgeState() {
      this.user = null;
      this.token = null;
      this.isAuthenticated = false;

      localStorage.clear();
      sessionStorage.clear();

      try {
        await clearUserMasterKey();
      } catch (e) {
        // Ignore
      }

      // Clear cookies
      if (typeof document !== "undefined") {
        const cookies = document.cookie.split(";");
        for (const cookie of cookies) {
          const eqPos = cookie.indexOf("=");
          const name =
            eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();
          document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
        }
      }
    },

    async fetchCurrentUser() {
      try {
        const response = await apiRequest("/auth/me");
        if (!response.ok) {
          if (response.status === 401) {
            this.purgeState();
          }
          throw new Error("Failed to fetch user");
        }
        const data = await response.json();
        this.user = data.user;
        if (data.token) {
          this.setAuth(this.user, data.token);
        }
        return this.user;
      } catch (error) {
        if (isNetworkError(error)) throw error;
        this.purgeState();
        throw error;
      }
    },

    async getMasterKeySalt() {
      const response = await apiRequest("/auth/account/master-key-salt");
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to get master key salt");
      }
      const data = await response.json();
      return data.master_key_salt;
    },

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
      if (data.user) {
        this.user = data.user;
      }
      return data;
    },

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
      return await response.json();
    },

    async deleteAccount(password) {
      const response = await apiRequest("/auth/account", {
        method: "DELETE",
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to delete account");
      }
      await this.purgeState();
      return await response.json();
    },

    async fetchAuthConfig() {
      try {
        const response = await fetch("/api/v2/config");
        if (!response.ok) throw new Error("Config request failed");
        const data = await response.json();
        this.authConfig = {
          allow_signup: data.allow_signup,
          password_authentication_enabled: data.password_authentication_enabled,
          orchestrator_enabled: data.orchestrator_enabled,
        };
        // Explicitly set isSetupComplete from response
        this.isSetupComplete = data.is_setup_complete === true;
      } catch (err) {
        console.error("fetchAuthConfig error:", err);
        // Fallback for existing installations to avoid redirect loops
        this.authConfig = {
          allow_signup: false,
          password_authentication_enabled: true,
        };
        // If config fails, assume setup is complete for safety
        if (this.isSetupComplete === null) {
          this.isSetupComplete = true;
        }
      }
      return this.authConfig;
    },

    async checkSetupStatus() {
      if (this.isSetupComplete !== null) {
        return this.isSetupComplete;
      }
      await this.fetchAuthConfig();
      return this.isSetupComplete;
    },

    async get2FAStatus() {
      const response = await apiRequest("/auth/2fa/status");
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to get 2FA status");
      }
      return await response.json();
    },

    async setup2FA() {
      const response = await apiRequest("/auth/2fa/setup", {
        method: "POST",
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to setup 2FA");
      }
      return await response.json();
    },

    async verify2FASetup(token) {
      const response = await apiRequest("/auth/2fa/verify-setup", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to verify 2FA setup");
      }
      return await response.json();
    },

    async disable2FA(password) {
      const response = await apiRequest("/auth/2fa/disable", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to disable 2FA");
      }
      return await response.json();
    },

    async regenerateBackupCodes(password) {
      const response = await apiRequest("/auth/2fa/regenerate-backup", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to regenerate backup codes");
      }
      return await response.json();
    },

    async verifyEmailToken(token) {
      const response = await apiRequest(`/auth/account/verify/${token}`, {
        method: "POST",
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Email verification failed");
      }
      return await response.json();
    },

    async resendVerificationEmail(userId = null, email = null) {
      const response = await apiRequest("/auth/account/resend-verification", {
        method: "POST",
        body: JSON.stringify({ user_id: userId, email }),
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(
          errorData.error || "Failed to resend verification email",
        );
      }
      return await response.json();
    },

    async getInvitation(token) {
      const response = await apiRequest(`/auth/invitations/accept/${token}`, {
        method: "GET",
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to load invitation");
      }
      return await response.json();
    },

    async acceptInvitation(token, password) {
      const response = await apiRequest(`/auth/invitations/accept/${token}`, {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const errorData = await parseErrorResponse(response);
        throw new Error(errorData.error || "Failed to accept invitation");
      }
      return await response.json();
    },
  },
});
