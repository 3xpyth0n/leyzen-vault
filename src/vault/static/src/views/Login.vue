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
          <div class="captcha-image-wrapper" @click="handleCaptchaClick">
            <img
              v-if="captchaImageUrl && captchaNonce"
              :key="captchaNonce"
              :src="captchaImageUrl"
              alt=""
              class="captcha-image"
            />
            <div v-else class="captcha-loading">Loading Captcha</div>
            <div
              :class="{ 'captcha-refresh-toast': true, show: showRefreshToast }"
            >
              Tap again to refresh ({{ toastCountdown }}s)
            </div>
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
const show2FAModal = ref(false);
const twoFactorError = ref("");
const showRefreshToast = ref(false);
const pendingRefresh = ref(false);
const toastCountdown = ref(3);
let toastTimeout = null;
let countdownInterval = null;

/**
 * Refresh CAPTCHA by calling the refresh endpoint.
 * Simple and straightforward - just get new nonce and update state.
 */

/**
 * Refresh CAPTCHA by calling the refresh endpoint.
 * Simple and straightforward - just get new nonce and update state.
 */
const refreshCaptcha = async () => {
  try {
    const response = await fetch("/api/auth/captcha-refresh", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      logger.error("Failed to refresh CAPTCHA:", response.status);
      // Clear URL to prevent 404 errors
      captchaImageUrl.value = "";
      captchaNonce.value = "";
      return;
    }

    const data = await response.json();

    if (data.nonce) {
      // Update nonce and image URL - simple and direct
      // Always update on refresh to ensure image loads (especially after logout)
      captchaNonce.value = data.nonce;
      captchaImageUrl.value = `/api/auth/captcha-image?nonce=${data.nonce}`;
      captchaResponse.value = "";
    } else {
      logger.error("CAPTCHA refresh returned no nonce");
      // Clear URL to prevent 404 errors
      captchaImageUrl.value = "";
      captchaNonce.value = "";
    }
  } catch (error) {
    logger.error("Failed to refresh CAPTCHA:", error);
    // Clear URL to prevent 404 errors
    captchaImageUrl.value = "";
    captchaNonce.value = "";
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

  // Always refresh CAPTCHA on mount to ensure we have a valid one
  // This handles cases where user returns to login page after logout
  if (passwordAuthEnabled.value) {
    await refreshCaptcha();
  }
  // Load SSO providers
  try {
    ssoProviders.value = await sso.listProviders();
  } catch (err) {
    logger.error("Failed to load SSO providers:", err);
    // Don't show error to user, just log it
  }
});

onUnmounted(() => {
  // Component cleanup
  if (toastTimeout) {
    clearTimeout(toastTimeout);
    toastTimeout = null;
  }
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
});

const hideToast = () => {
  showRefreshToast.value = false;
  pendingRefresh.value = false;
  toastCountdown.value = 3;
  if (toastTimeout) {
    clearTimeout(toastTimeout);
    toastTimeout = null;
  }
  if (countdownInterval) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
};

const startCountdown = () => {
  toastCountdown.value = 3;
  if (countdownInterval) {
    clearInterval(countdownInterval);
  }
  countdownInterval = setInterval(() => {
    toastCountdown.value--;
    if (toastCountdown.value <= 0) {
      hideToast();
    }
  }, 1000);
};

const handleCaptchaClick = () => {
  if (loading.value) return;

  // Uniform behavior: double tap/click for everyone
  if (pendingRefresh.value) {
    // Second tap/click: confirm refresh
    hideToast();
    refreshCaptcha();
  } else {
    // First tap/click: show toast with countdown
    pendingRefresh.value = true;
    showRefreshToast.value = true;
    startCountdown();
    // Auto-hide after 3 seconds
    toastTimeout = setTimeout(() => {
      hideToast();
    }, 3000);
  }
};

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

    // Check if error is about CAPTCHA expiration or too many attempts
    const isCaptchaExpired =
      err.message &&
      (err.message.includes("CAPTCHA expired") ||
        err.message.includes("CAPTCHA invalid") ||
        err.message.includes("CAPTCHA not found") ||
        err.message.includes("Please refresh the CAPTCHA"));

    const isTooManyAttempts =
      err.message && err.message.includes("Too many failed attempts");

    // Check if error is about unverified email
    if (err.message && err.message.includes("not verified")) {
      showVerificationLink.value = true;
      emailForVerification.value = username.value;
    } else {
      showVerificationLink.value = false;
    }

    // Only refresh CAPTCHA if expired or too many attempts, NOT on invalid response
    if (isCaptchaExpired || isTooManyAttempts) {
      logger.info("CAPTCHA expired or too many attempts, refreshing");
      await refreshCaptcha();
      if (isCaptchaExpired) {
        error.value =
          "The security code has expired. A new code has been generated. Please enter it below.";
      } else if (isTooManyAttempts) {
        error.value =
          "Too many failed attempts. A new security code has been generated. Please enter it below.";
      }
    }
    // For "Incorrect captcha response" errors, keep the same CAPTCHA (allow retry)
    // Only clear the input field
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
    // Check if error is about CAPTCHA expiration or too many attempts
    const isCaptchaExpired =
      err.message &&
      (err.message.includes("CAPTCHA expired") ||
        err.message.includes("CAPTCHA invalid") ||
        err.message.includes("CAPTCHA not found") ||
        err.message.includes("Please refresh the CAPTCHA"));

    const isTooManyAttempts =
      err.message && err.message.includes("Too many failed attempts");

    if (isCaptchaExpired || isTooManyAttempts) {
      logger.info(
        "CAPTCHA expired or too many attempts during 2FA, refreshing",
      );
      await refreshCaptcha();
      if (isCaptchaExpired) {
        twoFactorError.value =
          "The security code has expired. A new code has been generated. Please enter it below and try again.";
      } else if (isTooManyAttempts) {
        twoFactorError.value =
          "Too many failed attempts. A new security code has been generated. Please enter it below and try again.";
      }
    } else {
      twoFactorError.value =
        err.message || "Verification failed. Please try again.";
      // Don't refresh CAPTCHA on other errors - keep it for retry
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
  background: var(--bg-primary);
}

.login-content {
  max-width: 600px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 3rem;
}

h1 {
  font-family: var(--font-family-branding);
  text-align: center;
  margin-bottom: 3rem;
  color: var(--text-primary);
  font-size: 3rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin-top: 0;
  opacity: 1;
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
  border: 1px solid #004225;
  background: rgba(10, 10, 10, 0.6);
  color: #a9b7aa;
  font-size: 0.95rem;
  font-weight: 500;
  transition:
    border-color 0.2s,
    background 0.2s;
}

input::placeholder {
  color: rgba(169, 183, 170, 0.6);
  opacity: 1;
}

input:focus {
  outline: none;
  border-color: #004225;
}

input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button[type="submit"] {
  width: 100%;
  padding: 0.75rem 1rem;
  background: transparent;
  border: 1px solid #004225;
  color: var(--text-primary);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.2s,
    color 0.2s,
    background 0.2s;
}

button[type="submit"]:hover:not(:disabled) {
  border-color: #004225;
  color: var(--text-primary);
  background: rgba(0, 66, 37, 0.1);
}

button[type="submit"]:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.captcha-section {
  display: flex !important;
  flex-direction: row !important;
  align-items: flex-start;
  gap: 0.75rem;
  width: 100%;
  position: relative;
  overflow: visible;
}

.captcha-image-wrapper {
  position: relative;
  display: inline-block;
  flex-shrink: 0;
  width: 230px;
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 10, 10, 0.6);
  cursor: pointer;
  overflow: visible;
}

.captcha-image {
  height: 70px;
  width: 230px;
  object-fit: contain;
  display: block;
}

.captcha-refresh-toast {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 66, 37, 0.9);
  color: #a9b7aa;
  padding: 0.6rem 1.2rem;
  font-size: 0.9rem;
  font-weight: 600;
  white-space: nowrap;
  z-index: 1000;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  text-align: center;
  box-sizing: border-box;
  opacity: 0;
  visibility: hidden;
  transition:
    opacity 0.5s ease,
    visibility 0.5s ease;
}

.captcha-refresh-toast.show {
  opacity: 1;
  visibility: visible;
}

.captcha-loading {
  color: #a9b7aa;
  font-size: 0.9rem;
  text-align: center;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.captcha-section .captcha-input {
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: monospace;
  flex: 1;
  min-width: 0;
  width: auto !important;
  max-width: 100%;
}

.captcha-section .captcha-input::placeholder {
  color: rgba(169, 183, 170, 0.6);
  opacity: 1;
}

p {
  text-align: center;
  margin-top: 1.5rem;
  color: #a9b7aa;
  width: 100%;
  font-weight: 500;
}

p a {
  color: var(--slate-grey);
  text-decoration: none;
  font-weight: 600;
}

p a:hover {
  text-decoration: underline;
}

.error {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;

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
  color: #004225;
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
  background: transparent;
  border: 1px solid #004225;
  color: var(--text-primary);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    border-color 0.2s,
    color 0.2s,
    background 0.2s;
}

.sso-button:hover:not(:disabled) {
  border-color: #004225;
  color: var(--text-primary);
  background: rgba(0, 66, 37, 0.1);
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
  color: #a9b7aa;
  font-weight: 600;
}

.magic-link-form form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.magic-link-input {
  padding: 0.75rem;
  border: 1px solid #004225;
  background: rgba(10, 10, 10, 0.6);
  color: #a9b7aa;
  font-size: 0.95rem;
  font-weight: 500;
  transition:
    border-color 0.2s,
    background 0.2s;
}

.magic-link-input::placeholder {
  color: rgba(169, 183, 170, 0.6);
  opacity: 1;
}

.magic-link-input:focus {
  outline: none;
  border-color: #004225;
  background: rgba(10, 10, 10, 0.8);
  color: #a9b7aa;
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

  color: #4ade80;
  font-size: 0.9rem;
  text-align: center;
}

.separator {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 1.5rem 0;
  color: #a9b7aa;
  font-weight: 500;
}

.separator::before,
.separator::after {
  content: "";
  flex: 1;
  border-bottom: 1px solid #004225;
  opacity: 0.5;
}

.separator span {
  padding: 0 1rem;
  font-size: 0.9rem;
  font-weight: 500;
}

@media (max-width: 600px) {
  .captcha-section {
    flex-direction: column !important;
  }

  .captcha-image-wrapper {
    width: 100%;
    margin-bottom: 0.75rem;
  }

  .captcha-image-wrapper .captcha-image {
    width: 100%;
    height: auto;
  }

  .captcha-section .captcha-input {
    width: 100% !important;
  }
}
</style>
