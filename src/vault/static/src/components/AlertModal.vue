<template>
  <teleport to="body">
    <div
      v-if="show"
      class="modal-overlay"
      @click="handleBackdropClick"
      role="dialog"
      aria-labelledby="alert-modal-title"
      aria-modal="true"
    >
      <div class="modal-container" @click.stop>
        <div class="modal-content-alert">
          <div class="modal-icon" :class="`modal-icon-${type}`">
            <span v-if="icon" v-html="icon"></span>
            <span v-else v-html="getDefaultIcon()"></span>
          </div>
          <h2 id="alert-modal-title" class="modal-title">{{ title }}</h2>
          <p id="alert-modal-message" class="modal-message">{{ message }}</p>
          <div class="modal-buttons">
            <button
              id="alert-modal-ok"
              class="modal-btn modal-btn-ok"
              :class="`modal-btn-${type}`"
              @click="handleOk"
              :disabled="disabled"
            >
              OK
            </button>
          </div>
        </div>
      </div>
    </div>
  </teleport>
</template>

<script>
export default {
  name: "AlertModal",
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    type: {
      type: String,
      default: "info",
      validator: (value) =>
        ["success", "error", "warning", "info"].includes(value),
    },
    title: {
      type: String,
      default: "Alert",
    },
    message: {
      type: String,
      default: "",
    },
    icon: {
      type: String,
      default: null,
    },
    closeOnBackdrop: {
      type: Boolean,
      default: true,
    },
    disabled: {
      type: Boolean,
      default: false,
    },
  },
  emits: ["close", "ok"],
  watch: {
    show(newVal) {
      if (newVal) {
        document.body.style.overflow = "hidden";
        // Focus on OK button for accessibility
        this.$nextTick(() => {
          const okBtn = document.getElementById("alert-modal-ok");
          if (okBtn) {
            okBtn.focus();
          }
        });
      } else {
        document.body.style.overflow = "";
      }
    },
  },
  methods: {
    getDefaultIcon() {
      if (!window.Icons) {
        return "";
      }
      const iconMap = {
        success: window.Icons.success,
        error: window.Icons.error,
        warning: window.Icons.warning,
        info: window.Icons.info,
      };
      const iconFn = iconMap[this.type] || iconMap.info;
      // Use .call() to preserve the correct 'this' context for window.Icons
      return iconFn && typeof iconFn === "function"
        ? iconFn.call(window.Icons, 48, "currentColor")
        : "";
    },
    handleOk() {
      this.$emit("ok");
      this.$emit("close");
    },
    handleBackdropClick(event) {
      if (this.closeOnBackdrop && event.target === event.currentTarget) {
        this.handleOk();
      }
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
  background: rgba(10, 10, 10, 0.8);
  animation: fadeIn 0.2s ease;
}

/* Remove sidebar padding in mobile mode */
body.mobile-mode .modal-overlay {
  padding: 1rem !important;
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
  max-width: 420px;
  animation: slideUp 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes slideUp {
  from {
    transform: scale(0.95) translateY(20px);
    opacity: 0;
  }
  to {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-content-alert {
  background: var(--bg-modal);
  border: 1px solid var(--border-color);
  padding: 2rem;
  position: relative;
  overflow: hidden;
}

.modal-icon {
  font-size: 3rem;
  text-align: center;
  margin-bottom: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-icon-success {
  color: var(--success);
}

.modal-icon-error {
  color: var(--error);
}

.modal-icon-warning {
  color: var(--warning);
}

.modal-icon-info {
  color: var(--text-primary);
}

.modal-title {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.modal-message {
  margin: 0 0 2rem 0;
  color: var(--text-primary);
  font-size: 1rem;
  text-align: center;
  line-height: 1.5;
}

.modal-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
}

.modal-btn {
  padding: 0.75rem 1.5rem;
  border: none;

  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 100px;
}

.modal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none !important;
}

.modal-btn-ok {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid #004225;
}

.modal-btn-ok:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.1);
}

.modal-btn-success {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid #004225;
}

.modal-btn-success:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-error {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid #004225;
}

.modal-btn-error:hover:not(:disabled) {
  background: rgba(0, 66, 37, 0.1);
}

.modal-btn-warning {
  background: transparent;
  color: #78350f;
}

.modal-btn-warning:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-info {
  background: transparent;
  color: var(--text-primary);
}

.modal-btn-info:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}
</style>
