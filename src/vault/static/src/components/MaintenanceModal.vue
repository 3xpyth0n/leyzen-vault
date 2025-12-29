<template>
  <Teleport v-if="isMaintenanceMode" to="body">
    <Transition name="fade">
      <div
        class="maintenance-modal-overlay"
        @click.stop
        role="dialog"
        aria-labelledby="maintenance-modal-title"
        aria-modal="true"
      >
        <Transition name="slide-fade">
          <div class="maintenance-modal-container">
            <div class="maintenance-modal-content">
              <div class="maintenance-modal-icon">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="#f59e0b"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M22.7 19l-9.1-9.1c.9-2.3.4-5-1.5-6.9-2-2-5-2.4-7.4-1.3L9 6 6 9 1.6 4.7C.4 7.1.9 10.1 2.9 12.1c1.9 1.9 4.6 2.4 6.9 1.5l9.1 9.1c.4.4 1 .4 1.4 0l2.3-2.3c.5-.4.5-1.1.1-1.4z"
                  />
                </svg>
              </div>
              <h2 id="maintenance-modal-title" class="maintenance-modal-title">
                Maintenance Mode
              </h2>
              <p class="maintenance-modal-message">
                The application is currently undergoing maintenance. All actions
                are blocked until maintenance is complete. Please do not close
                this page.
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
import { useMaintenanceMode } from "../composables/useMaintenanceMode";

export default {
  name: "MaintenanceModal",
  setup() {
    const { isMaintenanceMode } = useMaintenanceMode();

    return {
      isMaintenanceMode,
    };
  },
};
</script>

<style scoped>
.maintenance-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100000 !important;
  pointer-events: auto;
}

.maintenance-modal-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  width: 100%;
  max-width: 400px;
}

.maintenance-modal-content {
  background: linear-gradient(
    140deg,
    rgba(30, 41, 59, 0.95),
    rgba(15, 23, 42, 0.95)
  );
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(245, 158, 11, 0.3);

  padding: 2rem;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.5),
    0 0 0 1px rgba(245, 158, 11, 0.1);
  width: 100%;
  text-align: center;
}

/* Fade transition for overlay */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.4s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Slide and fade transition for modal content */
.slide-fade-enter-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-fade-enter-from {
  transform: translateY(30px);
  opacity: 0;
}

.slide-fade-leave-to {
  transform: translateY(-20px);
  opacity: 0;
}

.maintenance-modal-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1rem;
  width: 64px;
  height: 64px;
  background: rgba(245, 158, 11, 0.1);

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

.maintenance-modal-title {
  margin: 0 0 0.75rem 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #f59e0b;
  text-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
}

.maintenance-modal-message {
  margin: 0;
  font-size: 0.95rem;
  color: #a9b7aa;
  line-height: 1.5;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .maintenance-modal-container {
    padding: 1rem;
    max-width: 90%;
  }

  .maintenance-modal-content {
    padding: 1.5rem;
  }

  .maintenance-modal-title {
    font-size: 1.25rem;
  }

  .maintenance-modal-message {
    font-size: 0.875rem;
  }
}
</style>
