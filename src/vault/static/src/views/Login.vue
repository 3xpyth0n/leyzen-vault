<template>
  <div class="login-wrapper">
    <div class="login-content">
      <h1>Leyzen Vault Login</h1>
      <div v-if="setupSuccessMessage" class="success-banner">
        {{ setupSuccessMessage }}
      </div>
      <div v-if="restoreSuccessMessage" class="success-banner">
        {{ restoreSuccessMessage }}
      </div>
      <div v-if="error" class="error">
        {{ error }}
        <div v-if="showVerificationLink" class="verification-link">
          <router-link
            :to="{
              name: 'EmailVerification',
              query: { email: emailForVerification },
            }"
          >
            Verify my email
          </router-link>
        </div>
      </div>
      <div v-if="ssoProviders && ssoProviders.length > 0" class="sso-section">
        <div v-for="provider in ssoProviders" :key="provider.id">
          <!-- Email Magic Link: Show email input form -->
          <div
            v-if="provider.provider_type === 'email-magic-link'"
            class="magic-link-form"
          >
            <h3>{{ provider.name }}</h3>
            <form @submit.prevent="handleMagicLinkLogin(provider.id)">
              <input
                v-model="magicLinkEmail"
                type="email"
                placeholder="Enter your email address"
                autocomplete="email"
                required
                :disabled="loading || magicLinkLoading"
                class="magic-link-input"
              />
              <button
                type="submit"
                class="sso-button magic-link-button"
                :disabled="loading || magicLinkLoading"
              >
                {{ magicLinkLoading ? "Sending..." : "Send Magic Link" }}
              </button>
            </form>
            <div v-if="magicLinkSuccess" class="magic-link-success">
              Magic link sent! Please check your email.
            </div>
          </div>
          <!-- Other SSO providers: Show button -->
          <button
            v-else
            type="button"
            class="sso-button"
            :disabled="loading || ssoLoading"
            @click="handleSSOLogin(provider.id)"
          >
            {{ ssoLoading ? "Connecting..." : `Sign in with ${provider.name}` }}
          </button>
        </div>
        <div v-if="passwordAuthEnabled" class="separator">
          <span>Or</span>
        </div>
      </div>
      <form v-if="passwordAuthEnabled" @submit.prevent="handleLogin">
        <input
          v-model="username"
          type="text"
          placeholder="Username or Email"
          autocomplete="username"
          required
          :disabled="loading"
        />
        <PasswordInput
          v-model="password"
          id="password"
          placeholder="Password"
          autocomplete="current-password"
          required
          :disabled="loading"
        ></PasswordInput>
        <div class="captcha-section">
          <div class="captcha-image-wrapper">
            <img
              :src="captchaImageUrl"
              alt="CAPTCHA"
              class="captcha-image"
              @click="showCaptchaOverlay"
            />
            <button
              type="button"
              class="captcha-refresh"
              @click="refreshCaptcha"
              :disabled="loading"
            >
              ↻
            </button>
          </div>
          <input
            v-model="captchaResponse"
            type="text"
            placeholder="Enter CAPTCHA"
            required
            :disabled="loading"
            class="captcha-input"
          />
        </div>
        <button type="submit" :disabled="loading">
          {{ loading ? "Logging in..." : "Login" }}
        </button>
      </form>
      <p v-if="signupEnabled">
        Don't have an account?
        <router-link to="/register">Register here</router-link>
      </p>
    </div>
    <div
      class="captcha-overlay"
      :class="{ 'captcha-overlay--visible': showOverlay }"
      :aria-hidden="!showOverlay"
      data-captcha-overlay
      @click="handleOverlayClick"
    >
      <img
        :src="captchaImageUrl"
        alt="Captcha enlarged"
        class="captcha-overlay__image"
        data-captcha-overlay-image
        @click.stop
      />
    </div>

    <!-- Two-Factor Authentication Modal -->
    <TwoFactorVerify
      v-if="show2FAModal"
      :isLoading="loading"
      :error="twoFactorError"
      @verify="handle2FAVerify"
      @cancel="cancel2FA"
    ></TwoFactorVerify>

    <!-- Maintenance Modal -->
    <MaintenanceModal></MaintenanceModal>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { auth, sso } from "../services/api";
import {
  initializeUserMasterKey,
  clearUserMasterKey,
} from "../services/keyManager";
import { logger } from "../utils/logger.js";
import PasswordInput from "../components/PasswordInput.vue";
import TwoFactorVerify from "../components/TwoFactorVerify.vue";

const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const captchaResponse = ref("");
const captchaNonce = ref("");
const loading = ref(false);
const ssoLoading = ref(false);
const error = ref("");
const showVerificationLink = ref(false);
const emailForVerification = ref("");
const signupEnabled = ref(true);
const ssoProviders = ref([]);
const passwordAuthEnabled = ref(true);
const magicLinkEmail = ref("");
const magicLinkLoading = ref(false);
const magicLinkSuccess = ref(false);
const setupSuccessMessage = ref("");
const restoreSuccessMessage = ref("");

const captchaImageUrl = ref("");
let currentCaptchaBlobUrl = null; // Track blob URL to revoke it when creating new one
const showOverlay = ref(false);
const show2FAModal = ref(false);
const twoFactorError = ref("");

// Handle Escape key to close overlay
let handleKeyDown = null;

const showCaptchaOverlay = () => {
  if (captchaImageUrl.value) {
    showOverlay.value = true;
    document.body.classList.add("captcha-overlay-open");
  }
};

const hideCaptchaOverlay = () => {
  showOverlay.value = false;
  document.body.classList.remove("captcha-overlay-open");
};

const handleOverlayClick = (event) => {
  if (event.target === event.currentTarget) {
    hideCaptchaOverlay();
  }
};

/**
 * Fetches a CAPTCHA image and captures the nonce from response headers.
 * Returns the nonce and blob URL for the image, or null if the request failed.
 * Uses GET instead of HEAD to actually fetch the image, and returns a blob URL
 * that can be used directly in <img> tags.
 */
const fetchCaptchaWithNonce = async (url) => {
  try {
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
    });

    if (!response.ok) {
      logger.warn("Failed to fetch CAPTCHA image:", response.status);
      return null;
    }

    // Capture nonce from header (always present if server generated new CAPTCHA)
    // If header is present, use it (server generated new CAPTCHA)
    // Otherwise, extract nonce from URL (CAPTCHA already existed)
    let nonce = response.headers.get("X-Captcha-Nonce");

    // Convert response to blob and create blob URL
    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);

    // If no nonce in header, try to extract it from URL
    if (!nonce) {
      try {
        const urlObj = new URL(url, window.location.origin);
        nonce = urlObj.searchParams.get("nonce");
      } catch (e) {
        // Invalid URL, will handle below
        logger.debug("Failed to parse URL for nonce extraction:", e);
      }
    }

    if (nonce) {
      return { nonce, imageUrl: blobUrl, isBlob: true };
    }

    // Should not happen if server is working correctly, but handle gracefully
    logger.warn(
      "No nonce found in CAPTCHA response header or URL, server may have an issue",
    );
    URL.revokeObjectURL(blobUrl);
    return null;
  } catch (error) {
    logger.error("Error fetching CAPTCHA with nonce:", error);
    return null;
  }
};

const refreshCaptcha = async () => {
  // Revoke previous blob URL if it exists
  if (currentCaptchaBlobUrl) {
    URL.revokeObjectURL(currentCaptchaBlobUrl);
    currentCaptchaBlobUrl = null;
  }

  try {
    // Request a new captcha using the refresh endpoint to get the nonce
    const response = await fetch("/api/auth/captcha-refresh", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (response.ok) {
      const data = await response.json();

      // CRITICAL: Always fetch the actual image to capture the correct nonce
      // This ensures the nonce matches the displayed image
      if (data.nonce) {
        // Fetch the image with the nonce to get both image and verify/capture nonce
        const imageUrl =
          data.image_url || `/api/auth/captcha-image?nonce=${data.nonce}`;
        const result = await fetchCaptchaWithNonce(imageUrl);

        if (result && result.nonce) {
          captchaNonce.value = result.nonce;
          captchaImageUrl.value = result.imageUrl;
          currentCaptchaBlobUrl = result.imageUrl; // Track blob URL
        } else {
          // Fallback: use nonce from response even if we couldn't fetch image
          logger.warn(
            "Failed to fetch CAPTCHA image, using nonce from response",
          );
          captchaNonce.value = data.nonce;
          // Use regular URL as fallback
          const separator = imageUrl.includes("?") ? "&" : "?";
          captchaImageUrl.value = `${imageUrl}${separator}t=${Date.now()}`;
        }
      } else {
        // No nonce in response - use renew with nonce capture
        logger.warn(
          "CAPTCHA refresh returned no nonce, using renew with nonce capture",
        );
        const renewUrl = `/api/auth/captcha-image?renew=1&t=${Date.now()}`;
        const result = await fetchCaptchaWithNonce(renewUrl);

        if (result && result.nonce) {
          captchaNonce.value = result.nonce;
          captchaImageUrl.value = result.imageUrl;
          currentCaptchaBlobUrl = result.imageUrl;
        } else {
          logger.error("Failed to capture nonce from renew request");
          // Last resort: try one more time
          const retryResult = await fetchCaptchaWithNonce(renewUrl);
          if (retryResult && retryResult.nonce) {
            captchaNonce.value = retryResult.nonce;
            captchaImageUrl.value = retryResult.imageUrl;
            currentCaptchaBlobUrl = retryResult.imageUrl;
          } else {
            logger.error("Failed to refresh CAPTCHA after retry");
          }
        }
      }
    } else {
      // Refresh endpoint failed - use renew with nonce capture
      logger.warn(
        "CAPTCHA refresh endpoint failed, using renew with nonce capture",
      );
      const renewUrl = `/api/auth/captcha-image?renew=1&t=${Date.now()}`;
      const result = await fetchCaptchaWithNonce(renewUrl);

      if (result && result.nonce) {
        captchaNonce.value = result.nonce;
        captchaImageUrl.value = result.imageUrl;
        currentCaptchaBlobUrl = result.imageUrl;
      } else {
        logger.error("Failed to capture nonce from renew fallback");
      }
    }
  } catch (error) {
    // Last resort: try to get a fresh CAPTCHA with nonce capture
    logger.error("Failed to refresh CAPTCHA:", error);
    const renewUrl = `/api/auth/captcha-image?renew=1&t=${Date.now()}`;
    const result = await fetchCaptchaWithNonce(renewUrl);

    if (result && result.nonce) {
      captchaNonce.value = result.nonce;
      captchaImageUrl.value = result.imageUrl;
      currentCaptchaBlobUrl = result.imageUrl;
    } else {
      logger.error("Failed to recover CAPTCHA after error");
    }
  }

  // Clear the captcha response input
  captchaResponse.value = "";
  // Sync overlay image if visible
  if (showOverlay.value) {
    // Image will update automatically via :src binding
  }
};

onMounted(async () => {
  // Clean up query parameters (error/setup) while surfacing user feedback
  const nextQuery = { ...route.query };
  let shouldReplaceQuery = false;

  if (route.query.error) {
    error.value = decodeURIComponent(route.query.error);
    delete nextQuery.error;
    shouldReplaceQuery = true;
  }

  if (route.query.setup === "done") {
    setupSuccessMessage.value =
      "Superadmin account created. Please log in to initialize your master key.";
    delete nextQuery.setup;
    shouldReplaceQuery = true;
  }

  if (route.query.restore === "success") {
    restoreSuccessMessage.value =
      "Database restore completed successfully! You can now log in.";
    delete nextQuery.restore;
    shouldReplaceQuery = true;
  }

  if (shouldReplaceQuery) {
    router.replace({ query: nextQuery });
  }

  // Get authentication configuration (consolidated endpoint)
  try {
    const config = await auth.getAuthConfig();
    passwordAuthEnabled.value = config.password_authentication_enabled === true;
    signupEnabled.value = config.allow_signup === true;
  } catch (err) {
    logger.error("Failed to get auth config:", err);
    passwordAuthEnabled.value = true; // Default to enabled
    signupEnabled.value = true; // Default to enabled
  }

  // Load captcha only if password auth is enabled
  if (passwordAuthEnabled.value) {
    refreshCaptcha();
  }
  // Load SSO providers
  try {
    ssoProviders.value = await sso.listProviders();
  } catch (err) {
    logger.error("Failed to load SSO providers:", err);
    // Don't show error to user, just log it
  }

  // Handle Escape key to close overlay
  handleKeyDown = (event) => {
    if (event.key === "Escape" && showOverlay.value) {
      hideCaptchaOverlay();
    }
  };
  document.addEventListener("keydown", handleKeyDown);
});

onUnmounted(() => {
  // Clean up event listener and body class
  if (handleKeyDown) {
    document.removeEventListener("keydown", handleKeyDown);
  }
  document.body.classList.remove("captcha-overlay-open");

  // Clean up blob URL if it exists
  if (currentCaptchaBlobUrl) {
    URL.revokeObjectURL(currentCaptchaBlobUrl);
    currentCaptchaBlobUrl = null;
  }
});

const handleLogin = async () => {
  error.value = "";
  loading.value = true;

  // CRITICAL: Ensure we have a valid nonce before submitting
  if (!captchaNonce.value) {
    logger.warn("No CAPTCHA nonce available, refreshing before login");
    await refreshCaptcha();
    // If still no nonce after refresh, show error
    if (!captchaNonce.value) {
      error.value = "Failed to load CAPTCHA. Please refresh the page.";
      loading.value = false;
      return;
    }
  }

  try {
    // Pass the nonce - should always be available at this point
    const response = await auth.login(
      username.value,
      password.value,
      captchaNonce.value,
      captchaResponse.value,
    );

    // Check if 2FA is required
    if (response.requires_2fa) {
      show2FAModal.value = true;
      twoFactorError.value = "";
      loading.value = false;
      // Do NOT refresh CAPTCHA - it's already been validated
      return;
    }

    if (response.token) {
      await completeLogin(response);
    }
  } catch (err) {
    error.value = err.message || "Login failed. Please try again.";

    // Check if error is about CAPTCHA expiration
    const isCaptchaExpired =
      err.message &&
      (err.message.includes("CAPTCHA expired") ||
        err.message.includes("CAPTCHA invalid") ||
        err.message.includes("Please refresh the CAPTCHA"));

    // Check if error is about unverified email
    if (err.message && err.message.includes("not verified")) {
      showVerificationLink.value = true;
      emailForVerification.value = username.value;
    } else {
      showVerificationLink.value = false;
    }

    // If CAPTCHA expired, refresh it automatically and update error message
    if (isCaptchaExpired) {
      logger.info("CAPTCHA expired, automatically refreshing");
      await refreshCaptcha();
      error.value =
        "The security code has expired. A new code has been generated. Please enter it below.";
    } else {
      // For other errors, also refresh CAPTCHA but don't modify error message
      refreshCaptcha();
    }
    captchaResponse.value = "";
  } finally {
    loading.value = false;
  }
};

const handle2FAVerify = async (totpToken) => {
  error.value = "";
  twoFactorError.value = "";
  loading.value = true;

  try {
    const response = await auth.login(
      username.value,
      password.value,
      captchaNonce.value || "",
      captchaResponse.value,
      totpToken, // Pass the TOTP token
    );

    if (response.token) {
      show2FAModal.value = false;
      await completeLogin(response);
    } else if (response.requires_2fa) {
      // Still requires 2FA (invalid token)
      twoFactorError.value = "Invalid code. Please try again.";
      loading.value = false;
      // Do NOT refresh CAPTCHA - credentials already validated
    }
  } catch (err) {
    // Check if error is about CAPTCHA expiration
    const isCaptchaExpired =
      err.message &&
      (err.message.includes("CAPTCHA expired") ||
        err.message.includes("CAPTCHA invalid") ||
        err.message.includes("Please refresh the CAPTCHA"));

    if (isCaptchaExpired) {
      logger.info("CAPTCHA expired during 2FA, automatically refreshing");
      await refreshCaptcha();
      twoFactorError.value =
        "The security code has expired. A new code has been generated. Please enter it below and try again.";
    } else {
      twoFactorError.value =
        err.message || "Verification failed. Please try again.";
      // Refresh CAPTCHA on error - session may be invalid
      await refreshCaptcha();
    }
    loading.value = false;
  }
};

const cancel2FA = () => {
  show2FAModal.value = false;
  twoFactorError.value = "";
  refreshCaptcha();
  captchaResponse.value = "";
};

const completeLogin = async (response) => {
  // Clear any existing master key and salt before initializing a new one
  // This ensures a clean state after logout/login
  await clearUserMasterKey();

  // Get salt from server response (base64-encoded)
  // The salt is persistent per user and ensures the same master key is derived each session
  const saltBase64 = response.user?.master_key_salt;
  let salt = null;

  if (saltBase64) {
    // Decode base64 salt to Uint8Array
    try {
      const saltStr = atob(saltBase64);
      salt = Uint8Array.from(saltStr, (c) => c.charCodeAt(0));
    } catch (e) {
      logger.error("Failed to decode salt from server:", e);
      // Fallback: generate new salt (but this will cause issues with existing VaultSpace keys)
      salt = null;
    }
  }

  // Initialize user master key from password using the salt from server
  // Pass JWT token so the key can be stored encrypted in IndexedDB
  // This ensures the same master key is derived each session and persists across page refreshes
  await initializeUserMasterKey(password.value, salt, response.token);

  // Clear password from memory
  password.value = "";

  // Redirect to dashboard after successful login
  router.push("/dashboard");
};

const handleSSOLogin = async (providerId) => {
  error.value = "";
  ssoLoading.value = true;

  try {
    const returnUrl = window.location.origin + "/dashboard";
    const redirectUrl = await sso.initiateLogin(providerId, returnUrl);
    // Redirect to SSO provider
    window.location.href = redirectUrl;
  } catch (err) {
    error.value =
      err.message || "Failed to initiate SSO login. Please try again.";
    ssoLoading.value = false;
  }
};

const handleMagicLinkLogin = async (providerId) => {
  error.value = "";
  magicLinkSuccess.value = false;
  magicLinkLoading.value = true;

  try {
    const returnUrl = window.location.origin + "/dashboard";
    const result = await sso.initiateMagicLinkLogin(
      providerId,
      magicLinkEmail.value,
      returnUrl,
    );

    if (result && result.message) {
      magicLinkSuccess.value = true;
      magicLinkEmail.value = ""; // Clear email after success
    } else {
      error.value = "Failed to send magic link. Please try again.";
    }
  } catch (err) {
    error.value = err.message || "Failed to send magic link. Please try again.";
  } finally {
    magicLinkLoading.value = false;
  }
};
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.login-content {
  max-width: 600px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
}

h1 {
  text-align: center;
  margin-bottom: 3rem;
  color: #e6eef6;
  font-size: 3rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  background: linear-gradient(135deg, #e6eef6 0%, #cbd5e1 50%, #94a3b8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: 0 4px 20px rgba(230, 238, 246, 0.3);
  margin-top: 0;
}

form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 100%;
}

input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  background: rgba(13, 17, 23, 0.5);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

input:focus {
  outline: none;
  border-color: #58a6ff;
}

input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button[type="submit"] {
  width: 100%;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  border: none;
  border-radius: 8px;
  color: white;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

button[type="submit"]:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.4);
}

button[type="submit"]:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.captcha-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.captcha-image-wrapper {
  position: relative;
  display: inline-block;
  cursor: pointer;
}

.captcha-image {
  height: auto;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.captcha-refresh {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: rgba(0, 0, 0, 0.6);
  color: #e6eef6;
  border: none;
  border-radius: 999px;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1.25rem;
  padding: 0;
}

.captcha-refresh:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.8);
}

.captcha-input {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: monospace;
}

p {
  text-align: center;
  margin-top: 1.5rem;
  color: #94a3b8;
  width: 100%;
}

p a {
  color: #58a6ff;
  text-decoration: none;
}

p a:hover {
  text-decoration: underline;
}

.error {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
  width: 100%;
  text-align: center;
}

.verification-link {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgba(239, 68, 68, 0.3);
}

.verification-link a {
  color: #58a6ff;
  text-decoration: none;
  font-size: 0.9rem;
}

.verification-link a:hover {
  text-decoration: underline;
}

.success-banner {
  color: #4ade80;
  padding: 0.75rem;
  margin-bottom: 1rem;
  width: 100%;
  text-align: center;
  background: rgba(74, 222, 128, 0.1);
  border: 1px solid rgba(74, 222, 128, 0.3);
  border-radius: 8px;
}

.sso-section {
  margin-bottom: 1.5rem;
  width: 100%;
}

.sso-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}

.sso-button {
  width: 100%;
  padding: 0.75rem 1rem;
  background: rgba(88, 166, 255, 0.1);
  border: 1px solid rgba(88, 166, 255, 0.3);
  border-radius: 8px;
  color: #58a6ff;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.sso-button:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.2);
  border-color: rgba(88, 166, 255, 0.5);
}

.sso-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.magic-link-form {
  margin-bottom: 1.5rem;
  width: 100%;
}

.magic-link-form h3 {
  margin-top: 0.5rem;
  margin-bottom: 1rem;
  font-size: 1.1rem;
  color: #e6eef6;
}

.magic-link-form form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.magic-link-input {
  padding: 0.75rem;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 6px;
  background: rgba(13, 17, 23, 0.5);
  color: #e6eef6;
  font-size: 0.95rem;
  transition: border-color 0.2s;
}

.magic-link-input:focus {
  outline: none;
  border-color: #58a6ff;
}

.magic-link-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.magic-link-button {
  width: 100%;
}

.magic-link-success {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 6px;
  color: #4ade80;
  font-size: 0.9rem;
  text-align: center;
}

.separator {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1.5rem 0;
  color: #94a3b8;
}

.separator::before,
.separator::after {
  content: "";
  flex: 1;
  border-bottom: 1px solid rgba(148, 163, 184, 0.3);
}

.separator span {
  padding: 0 1rem;
  font-size: 0.9rem;
}

/* Captcha overlay styles - matching orchestrator */
:global(.captcha-overlay) {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 1.25rem;
  opacity: 0;
  pointer-events: none;
  transition: opacity 500ms ease;
  z-index: 1050;
}

:global(.captcha-overlay--visible) {
  opacity: 1;
  pointer-events: auto;
}

:global(.captcha-overlay__image) {
  max-width: min(90vw, 480px);
  max-height: 80vh;
  width: auto;
  border-radius: 0.75rem;
  border: 2px solid rgba(56, 189, 248, 0.8);
  background: rgba(30, 41, 59, 0.4);
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.25);
  transform: scale(0.95);
  transition: transform 500ms ease;
}

:global(.captcha-overlay--visible .captcha-overlay__image) {
  transform: scale(1.5);
}

:global(body.captcha-overlay-open) {
  overflow: hidden;
}
</style>
