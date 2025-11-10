<template>
  <div class="verification-wrapper">
    <div class="verification-container glass glass-card">
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
          <router-link to="/login" class="link">Back to login</router-link>
        </div>
      </div>

      <div v-else-if="verified" class="verified-section">
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
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { auth } from "../services/api";

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
let cooldownInterval = null;

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
    const response = await auth.verifyEmailToken(token);
    if (response.token) {
      // Store token
      localStorage.setItem("jwt_token", response.token);
      verified.value = true;
      success.value = "Email verified successfully!";
      tokenInUrl.value = false;
      // Don't auto-redirect, let user click "Go to login" button
    }
  } catch (err) {
    error.value =
      err.message || "Verification failed. The link may be expired or invalid.";
    tokenInUrl.value = false;
  } finally {
    loading.value = false;
  }
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
    const response = await auth.resendVerificationEmail(
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
  color: #e6eef6;
  font-size: 1.75rem;
  font-weight: 600;
}

h2 {
  text-align: center;
  margin-bottom: 1rem;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
}

.info-text {
  text-align: center;
  margin-bottom: 2rem;
  color: #94a3b8;
  line-height: 1.6;
}

.info-text strong {
  color: #e6eef6;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #e6eef6;
  font-weight: 500;
}

.verifying-section {
  text-align: center;
  padding: 2rem 0;
}

.verifying-section .info-text {
  color: #94a3b8;
  font-size: 1rem;
}

.btn {
  width: 100%;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
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
  color: #e6eef6;
  border: 1px solid rgba(88, 166, 255, 0.3);
}

.btn-primary:hover:not(:disabled) {
  background: rgba(88, 166, 255, 0.3);
  border-color: rgba(88, 166, 255, 0.5);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #e6eef6;
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
  color: #94a3b8;
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
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
}

.success {
  color: #86efac;
  padding: 0.75rem;
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  margin-bottom: 1rem;
}

.verified-section p {
  color: #94a3b8;
  margin-bottom: 2rem;
  line-height: 1.6;
}
</style>
