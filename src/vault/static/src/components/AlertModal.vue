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
  padding-left: calc(1rem + 250px); /* Default: sidebar expanded (250px) */
  background: rgba(7, 14, 28, 0.4);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  animation: fadeIn 0.2s ease;
  transition: padding-left 0.4s cubic-bezier(0.4, 0, 0.2, 1);
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
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.1),
    rgba(15, 23, 42, 0.08)
  );
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 2rem;
  padding: 2rem;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
}

.modal-content-alert::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
  );
}

.modal-icon {
  font-size: 3rem;
  text-align: center;
  margin-bottom: 1rem;
  filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-icon-success {
  color: #86efac;
}

.modal-icon-error {
  color: #ef4444;
}

.modal-icon-warning {
  color: #fbbf24;
}

.modal-icon-info {
  color: #38bdf8;
}

.modal-title {
  margin: 0 0 1rem 0;
  color: #e6eef6;
  font-size: 1.5rem;
  font-weight: 600;
  text-align: center;
}

.modal-message {
  margin: 0 0 2rem 0;
  color: #cbd5e1;
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
  border-radius: 0.5rem;
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
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  color: white;
}

.modal-btn-ok:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-success {
  background: linear-gradient(135deg, #86efac 0%, #4ade80 100%);
  color: #065f46;
}

.modal-btn-success:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-error {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  color: white;
}

.modal-btn-error:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-warning {
  background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
  color: #78350f;
}

.modal-btn-warning:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}

.modal-btn-info {
  background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
  color: white;
}

.modal-btn-info:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-1px);
}
</style>
