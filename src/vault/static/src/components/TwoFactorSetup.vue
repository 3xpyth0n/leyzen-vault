<template>
  <div class="two-factor-setup">
    <!-- Step 1: Scan QR Code -->
    <div v-if="step === 'scan'" class="setup-step">
      <h3>Set Up Two-Factor Authentication</h3>
      <p class="description">
        Scan this QR code with your authenticator app (Google Authenticator,
        Authy, 1Password, etc.)
      </p>

      <div v-if="qrCode" class="qr-code-container">
        <img :src="qrCode" alt="2FA QR Code" class="qr-code" />
      </div>

      <div v-if="secret" class="manual-entry">
        <p class="manual-entry-label">Can't scan? Enter this code manually:</p>
        <div class="secret-code">
          <code>{{ secret }}</code>
          <button
            @click="copySecret"
            class="copy-button"
            :title="secretCopied ? 'Copied!' : 'Copy to clipboard'"
          >
            <svg
              v-if="!secretCopied"
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
              <path
                d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
              ></path>
            </svg>
            <svg
              v-else
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </button>
        </div>
      </div>

      <div class="verify-section">
        <p>Enter the 6-digit code from your authenticator app to verify:</p>
        <input
          v-model="verificationCode"
          type="text"
          inputmode="numeric"
          pattern="[0-9]*"
          maxlength="6"
          placeholder="000000"
          class="verification-input"
          @input="formatVerificationCode"
          @keyup.enter="verifySetup"
        />
        <p v-if="errorMessage" class="error-message">{{ errorMessage }}</p>
      </div>

      <div class="button-group">
        <button @click="$emit('cancel')" class="btn btn-secondary">
          Cancel
        </button>
        <button
          @click="verifySetup"
          class="btn btn-primary"
          :disabled="verificationCode.length !== 6 || isLoading"
        >
          {{ isLoading ? "Verifying..." : "Verify & Enable 2FA" }}
        </button>
      </div>
    </div>

    <!-- Step 2: Show Backup Codes -->
    <div v-else-if="step === 'backup'" class="setup-step">
      <h3>Save Your Backup Codes</h3>
      <p class="description warning">
        <strong>Important:</strong> Save these backup codes in a secure place.
        You can use them to access your account if you lose your authenticator
        device.
      </p>

      <div class="backup-codes-container">
        <div
          v-for="(code, index) in backupCodes"
          :key="index"
          class="backup-code"
        >
          <code>{{ code }}</code>
        </div>
      </div>

      <div class="button-group">
        <button @click="downloadBackupCodes" class="btn btn-secondary">
          Download as Text
        </button>
        <button
          @click="copyBackupCodes"
          class="btn btn-secondary"
          :disabled="backupCodesCopied"
        >
          {{ backupCodesCopied ? "Copied!" : "Copy to Clipboard" }}
        </button>
        <button @click="finishSetup" class="btn btn-primary">
          I've Saved My Codes
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-else-if="step === 'loading'" class="loading-container">
      <div class="spinner"></div>
      <p>Generating QR code...</p>
    </div>
  </div>
</template>

<script>
import { twoFactor } from "../services/api";

export default {
  name: "TwoFactorSetup",
  emits: ["success", "cancel"],
  data() {
    return {
      step: "loading", // 'loading', 'scan', 'backup'
      secret: null,
      qrCode: null,
      verificationCode: "",
      backupCodes: [],
      errorMessage: "",
      isLoading: false,
      secretCopied: false,
      backupCodesCopied: false,
    };
  },
  async mounted() {
    await this.initializeSetup();
  },
  methods: {
    async initializeSetup() {
      try {
        const data = await twoFactor.setup();
        this.secret = data.secret;
        this.qrCode = data.qr_code;
        this.step = "scan";
      } catch (error) {
        this.errorMessage = error.message || "Failed to generate QR code";
        this.$emit("cancel");
      }
    },
    formatVerificationCode(event) {
      // Only allow digits
      this.verificationCode = event.target.value.replace(/\D/g, "");
    },
    async verifySetup() {
      if (this.verificationCode.length !== 6) {
        return;
      }

      this.isLoading = true;
      this.errorMessage = "";

      try {
        const result = await twoFactor.verifySetup(this.verificationCode);
        this.backupCodes = result.backup_codes;
        this.step = "backup";
      } catch (error) {
        this.errorMessage = error.message || "Invalid code. Please try again.";
      } finally {
        this.isLoading = false;
      }
    },
    copySecret() {
      navigator.clipboard.writeText(this.secret);
      this.secretCopied = true;
      setTimeout(() => {
        this.secretCopied = false;
      }, 2000);
    },
    copyBackupCodes() {
      const codesText = this.backupCodes.join("\n");
      navigator.clipboard.writeText(codesText);
      this.backupCodesCopied = true;
    },
    downloadBackupCodes() {
      const codesText = this.backupCodes.join("\n");
      const blob = new Blob([codesText], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "leyzen-vault-backup-codes.txt";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    },
    finishSetup() {
      this.$emit("success");
    },
  },
};
</script>

<style scoped>
.two-factor-setup {
  max-width: 500px;
  margin: 0 auto;
  padding: 0;
  overflow-x: hidden;
}

.setup-step {
  text-align: center;
  padding: 0 1rem 1rem 1rem;
}

h3 {
  margin: 0 0 1.5rem 0;
  padding: 1.5rem 1rem 0 1rem;
  font-size: 1.5rem;
  color: #e6eef6;
  font-weight: 600;
}

.description {
  margin-bottom: 1.5rem;
  color: #b8c5d6;
  line-height: 1.5;
  font-size: 0.95rem;
}

.description.warning {
  background: rgba(255, 193, 7, 0.1);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: 8px;
  padding: 1rem;
  color: #ffc107;
}

.qr-code-container {
  margin: 2rem 0;
  display: flex;
  justify-content: center;
}

.qr-code {
  max-width: 250px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  background: white;
}

.manual-entry {
  margin: 2rem 0;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}

.manual-entry-label {
  margin-bottom: 0.75rem;
  font-size: 0.9rem;
  color: #b8c5d6;
}

.secret-code {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.secret-code code {
  font-family: "Courier New", monospace;
  font-size: 0.9rem;
  padding: 0.75rem 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  letter-spacing: 0.05em;
  color: #e6eef6;
  word-break: break-all;
  max-width: 100%;
  overflow-wrap: break-word;
}

.copy-button {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  cursor: pointer;
  padding: 0.5rem;
  transition: all 0.2s;
  color: #b8c5d6;
  display: flex;
  align-items: center;
  justify-content: center;
}

.copy-button:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
  color: #e6eef6;
}

.verify-section {
  margin: 2rem 0;
}

.verification-input {
  max-width: 200px;
  width: 100%;
  padding: 0.75rem;
  font-size: 1.5rem;
  text-align: center;
  letter-spacing: 0.3em;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  font-family: "Courier New", monospace;
  background: rgba(0, 0, 0, 0.3);
  color: #e6eef6;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.verification-input:focus {
  outline: none;
  border-color: #007bff;
  background: rgba(0, 0, 0, 0.4);
}

.error-message {
  color: #ff6b6b;
  margin-top: 1rem;
  font-size: 0.9rem;
  background: rgba(255, 107, 107, 0.1);
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid rgba(255, 107, 107, 0.3);
}

.backup-codes-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  margin: 2rem 0;
}

.backup-code {
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
}

.backup-code code {
  font-family: "Courier New", monospace;
  font-size: 1rem;
  letter-spacing: 0.1em;
  color: #e6eef6;
}

.button-group {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 2rem;
  flex-wrap: wrap;
}

.loading-container {
  text-align: center;
  padding: 3rem;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
