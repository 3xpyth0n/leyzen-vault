<template>
  <teleport to="body">
    <div
      v-if="show"
      class="modal-overlay"
      role="dialog"
      aria-labelledby="reencryption-modal-title"
      aria-modal="true"
    >
      <div class="modal-container" @click.stop>
        <div class="modal-content">
          <!-- Animated gradient background -->
          <div class="gradient-background"></div>

          <!-- Main content -->
          <div class="modal-body">
            <!-- Spinner -->
            <div class="spinner-container" v-if="!error">
              <div class="spinner">
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
              </div>
            </div>

            <!-- Error icon -->
            <div class="error-icon" v-if="error">
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>

            <!-- Title -->
            <h2 id="reencryption-modal-title" class="modal-title">
              {{ error ? "Re-encryption Failed" : "Re-encrypting Keys" }}
            </h2>

            <!-- Current step -->
            <p class="current-step">{{ currentStep }}</p>

            <!-- VaultSpace name (if available) -->
            <p class="vaultspace-name" v-if="vaultspaceName && !error">
              {{ vaultspaceName }}
            </p>

            <!-- Progress percentage -->
            <div class="progress-info" v-if="!error">
              <span class="progress-percentage">{{ progress }}%</span>
              <span class="progress-count" v-if="totalCount > 0">
                ({{ currentIndex + 1 }} / {{ totalCount }})
              </span>
            </div>

            <!-- Error message -->
            <p class="error-message" v-if="error">{{ error }}</p>

            <!-- Cancel button (only show if not in error state and not complete) -->
            <div class="modal-actions" v-if="!error && progress < 100">
              <button
                class="cancel-btn"
                @click="handleCancel"
                :disabled="progress >= 100"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "ReEncryptionModal",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    progress: {
      type: Number,
      default: 0,
      validator: (value) => value >= 0 && value <= 100,
    },
    currentStep: {
      type: String,
      default: "Processing...",
    },
    vaultspaceName: {
      type: String,
      default: null,
    },
    currentIndex: {
      type: Number,
      default: 0,
    },
    totalCount: {
      type: Number,
      default: 0,
    },
    error: {
      type: String,
      default: null,
    },
  },
  emits: ["cancel"],
  watch: {
    show(newVal) {
      if (newVal) {
        document.body.style.overflow = "hidden";
      } else {
        document.body.style.overflow = "";
      }
    },
  },
  methods: {
    handleCancel() {
      this.$emit("cancel");
    },
  },
  beforeUnmount() {
    document.body.style.overflow = "";
  },
};
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100000 !important;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  padding-left: calc(1rem + 250px); /* Default: sidebar expanded (250px) */
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  animation: fadeIn 0.3s ease;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Remove sidebar padding in mobile mode */
.mobile-mode .modal-overlay {
  padding-left: 1rem !important;
  padding-right: 1rem !important;
}

/* Adjust modal overlay when sidebar is collapsed */
body.sidebar-collapsed .modal-overlay {
  padding-left: calc(1rem + 70px); /* Sidebar collapsed (70px) */
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-container {
  position: relative;
  width: 100%;
  max-width: 500px;
  animation: slideUp 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes slideUp {
  from {
    transform: scale(0.95) translateY(30px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-content {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);

  padding: 3rem 2.5rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
}

.modal-content::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(88, 166, 255, 0.4),
    transparent
  );
}

.gradient-background {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(
    circle,
    rgba(88, 166, 255, 0.1) 0%,
    transparent 70%
  );
  animation: rotate 20s linear infinite;
  pointer-events: none;
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.modal-body {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.spinner-container {
  margin-bottom: 2rem;
  position: relative;
  width: 80px;
  height: 80px;
}

.spinner {
  position: relative;
  width: 100%;
  height: 100%;
}

.spinner-ring {
  position: absolute;
  width: 100%;
  height: 100%;
  border: 3px solid var(--accent);
  border-top-color: var(--ash-grey);
  border-radius: 50%;
  animation: spin 1.5s linear infinite;
}

.spinner-ring:nth-child(1) {
  animation-delay: 0s;
  border: 3px solid var(--accent);
  border-top-color: var(--ash-grey);
}

.spinner-ring:nth-child(2) {
  animation-delay: 0.5s;
  border: 3px solid var(--accent);
  border-top-color: var(--ash-grey);
  width: 70%;
  height: 70%;
  top: 15%;
  left: 15%;
}

.spinner-ring:nth-child(3) {
  animation-delay: 1s;
  border: 3px solid var(--accent);
  border-top-color: var(--ash-grey);
  width: 40%;
  height: 40%;
  top: 30%;
  left: 30%;
  animation-direction: reverse;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.error-icon {
  margin-bottom: 1.5rem;
  color: #ef4444;
  filter: drop-shadow(0 4px 8px rgba(239, 68, 68, 0.3));
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.modal-title {
  margin: 0 0 1rem 0;
  color: #a9b7aa;
  font-size: 1.75rem;
  font-weight: 600;
  text-align: center;
  background: transparent;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.current-step {
  margin: 0 0 1rem 0;
  color: #a9b7aa;
  font-size: 1.1rem;
  font-weight: 500;
  text-align: center;
  line-height: 1.5;
  min-height: 1.5em;
}

.vaultspace-name {
  margin: 0 0 1.5rem 0;
  color: #a9b7aa;
  font-size: 0.95rem;
  font-style: italic;
  text-align: center;
}

.progress-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.progress-percentage {
  color: #58a6ff;
  font-size: 2rem;
  font-weight: 700;
  text-shadow: 0 0 20px rgba(88, 166, 255, 0.5);
  font-variant-numeric: tabular-nums;
}

.progress-count {
  color: #a9b7aa;
  font-size: 0.9rem;
  font-weight: 500;
}

.error-message {
  margin: 1rem 0 0 0;
  color: #fca5a5;
  font-size: 1rem;
  text-align: center;
  line-height: 1.5;
  padding: 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3) !important;

  width: 100%;
}

.modal-actions {
  margin-top: 2rem;
  display: flex;
  justify-content: center;
}

.cancel-btn {
  padding: 0.75rem 1.5rem;
  border: 1px solid #004225;

  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #004225;
  color: #a9b7aa;
}

.cancel-btn:hover:not(:disabled) {
  background: #004225;
  border-color: #004225;
  transform: translateY(-1px);
}

.cancel-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

/* Responsive design */
@media (max-width: 640px) {
  .modal-container {
    max-width: 100%;
  }

  .modal-content {
    padding: 2rem 1.5rem;
  }

  .modal-title {
    font-size: 1.5rem;
  }

  .current-step {
    font-size: 1rem;
  }

  .progress-percentage {
    font-size: 1.5rem;
  }
}
</style>
