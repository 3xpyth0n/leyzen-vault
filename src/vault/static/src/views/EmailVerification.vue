<template>
  <div class="verification-wrapper">
    <div class="verification-container">
      <h1>Email Verification</h1>
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="success" class="success">{{ success }}</div>

      <div v-if="!verified && !tokenInUrl">
        <p class="info-text">
          A verification email has been sent to <strong>{{ email }}</strong
          >. Please check your inbox and click on the verification link in the
          email.
        </p>

        <div class="resend-section">
          <p>Didn't receive the email?</p>
          <button
            @click="handleResendEmail"
            :disabled="resendLoading || resendCooldown > 0"
            class="btn btn-secondary"
          >
            {{
              resendCooldown > 0
                ? `Resend (${resendCooldown}s)`
                : resendLoading
                  ? "Sending..."
                  : "Resend email"
            }}
          </button>
        </div>

        <div class="back-section">
          <router-link v-if="!isLoggedIn" to="/login" class="link"
            >Back to login</router-link
          >
          <router-link v-else to="/dashboard" class="link"
            >Back to dashboard</router-link
          >
        </div>
      </div>

      <div v-else-if="verified && !isLoggedIn" class="verified-section">
        <div class="success-icon">✓</div>
        <h2>Email verified successfully!</h2>
        <p>Your account has been verified. You can now log in.</p>
        <router-link to="/login" class="btn btn-primary"
          >Go to login</router-link
        >
      </div>

      <div
        v-else-if="tokenInUrl && !verified && !error"
        class="verifying-section"
      >
        <p class="info-text">Verifying your email address...</p>
      </div>
    </div>

    <!-- Modal for logged-in users -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>Email Verified</h2>
          <button class="modal-close" @click="closeModal" aria-label="Close">
            ×
          </button>
        </div>
        <div class="modal-body">
          <div class="success-icon">✓</div>
          <p>Your email address has been successfully verified.</p>
        </div>
        <div class="modal-footer">
          <button @click="goToDashboard" class="btn btn-primary">
            Return to dashboard
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useAuthStore } from "../store/auth";

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const email = ref(route.query.email || "");
const userId = ref(route.query.user_id || "");
const loading = ref(false);
const resendLoading = ref(false);
const error = ref("");
const success = ref("");
const verified = ref(false);
const resendCooldown = ref(0);
const tokenInUrl = ref(false);
const showModal = ref(false);
let cooldownInterval = null;

// Check if user is logged in
const isLoggedIn = computed(() => {
  return localStorage.getItem("jwt_token") !== null;
});

// Check if we came from a verification link (token in query)
onMounted(() => {
  const token = route.query.token;
  if (token) {
    tokenInUrl.value = true;
    handleVerifyToken(token);
  }
});

onUnmounted(() => {
  if (cooldownInterval) {
    clearInterval(cooldownInterval);
  }
});

const startCooldown = () => {
  resendCooldown.value = 60; // 60 seconds cooldown
  cooldownInterval = setInterval(() => {
    resendCooldown.value--;
    if (resendCooldown.value <= 0) {
      clearInterval(cooldownInterval);
      cooldownInterval = null;
    }
  }, 1000);
};

const handleVerifyToken = async (token) => {
  loading.value = true;
  error.value = "";
  success.value = "";

  try {
    const response = await authStore.verifyEmailToken(token);
    // CRITICAL: Do NOT store any token - user must log in after email verification
    // This ensures master key initialization happens during login
    // Even if response contains a token, ignore it
    if (response.token) {
      // Explicitly remove any token that might exist
      localStorage.removeItem("jwt_token");
    }
    verified.value = true;
    tokenInUrl.value = false;

    // If user was logged in, show modal instead of redirecting
    if (response.user_was_logged_in) {
      showModal.value = true;
    } else {
      // User not logged in - show success message and allow redirect to login
      success.value = "Email verified successfully!";
    }
  } catch (err) {
    error.value =
      err.message || "Verification failed. The link may be expired or invalid.";
    tokenInUrl.value = false;
  } finally {
    loading.value = false;
  }
};

const closeModal = () => {
  showModal.value = false;
};

const goToDashboard = () => {
  router.push("/dashboard");
};

const handleResendEmail = async () => {
  // If user_id is not available, use email instead
  if (!userId.value && !email.value) {
    error.value = "User ID or email missing";
    return;
  }

  resendLoading.value = true;
  error.value = "";
  success.value = "";

  try {
    const response = await authStore.resendVerificationEmail(
      userId.value || null,
      email.value || null,
    );
    // If user_id was missing but email was used, update user_id from response
    if (!userId.value && response.user_id) {
      userId.value = response.user_id;
    }
    success.value = "Verification email resent!";
    startCooldown();
  } catch (err) {
    error.value = err.message || "Failed to send email. Please try again.";
  } finally {
    resendLoading.value = false;
  }
};
</script>

<style scoped>
.verification-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
  position: relative;
  z-index: 1;
}

.verification-container {
  max-width: 500px;
  width: 100%;
  padding: 2.5rem;
}

h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: #a9b7aa;
  font-size: 1.75rem;
  font-weight: 600;
}

h2 {
  text-align: center;
  margin-bottom: 1rem;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
}

.info-text {
  text-align: center;
  margin-bottom: 2rem;
  color: #a9b7aa;
  line-height: 1.6;
}

.info-text strong {
  color: #a9b7aa;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #a9b7aa;
  font-weight: 500;
}

.verifying-section {
  text-align: center;
  padding: 2rem 0;
}

.verifying-section .info-text {
  color: #a9b7aa;
  font-size: 1rem;
}

.btn {
  width: 100%;
  padding: 0.75rem 1.5rem;
  border: none;

  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 1rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: rgba(88, 166, 255, 0.2);
  color: #a9b7aa;
  border: 1px solid rgba(88, 166, 255, 0.3);
}

.btn-primary:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.3);
  border-color: rgba(88, 166, 255, 0.5);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #a9b7aa;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}

.resend-section {
  text-align: center;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.resend-section p {
  margin-bottom: 1rem;
  color: #a9b7aa;
}

.back-section {
  text-align: center;
  margin-top: 1.5rem;
}

.link {
  color: #58a6ff;
  text-decoration: none;
  font-size: 0.9rem;
}

.link:hover {
  text-decoration: underline;
}

.verified-section {
  text-align: center;
  padding: 2rem 0;
}

.success-icon {
  font-size: 4rem;
  color: #86efac;
  margin-bottom: 1rem;
}

.error {
  color: #fca5a5;
  padding: 0.75rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;

  margin-bottom: 1rem;
}

.success {
  color: #86efac;
  padding: 0.75rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);

  margin-bottom: 1rem;
}

.verified-section p {
  color: #a9b7aa;
  margin-bottom: 2rem;
  line-height: 1.6;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
  padding: 2rem;
  box-sizing: border-box;
}

.modal-content {
  max-width: 500px;
  width: 100%;
  padding: 2.5rem;
  position: relative;
  margin: auto;
  animation: modalFadeIn 0.3s ease-out;
}

@keyframes modalFadeIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.modal-header h2 {
  margin: 0;
  color: #a9b7aa;
  font-size: 1.5rem;
  font-weight: 600;
}

.modal-close {
  background: none;
  border: none;
  color: #a9b7aa;
  font-size: 2rem;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;

  transition: all 0.2s ease;
}

.modal-close:hover {
  color: #a9b7aa;
  background: rgba(255, 255, 255, 0.1);
}

.modal-body {
  text-align: center;
  padding: 1rem 0;
}

.modal-body .success-icon {
  font-size: 4rem;
  color: #86efac;
  margin-bottom: 1rem;
}

.modal-body p {
  color: #a9b7aa;
  font-size: 1rem;
  line-height: 1.6;
  margin: 0;
}

.modal-footer {
  margin-top: 2rem;
  display: flex;
  justify-content: center;
}
</style>
