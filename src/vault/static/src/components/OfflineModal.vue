<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="isOffline"
        class="offline-modal-overlay"
        @click.stop
        role="dialog"
        aria-labelledby="offline-modal-title"
        aria-modal="true"
      >
        <Transition name="slide-fade">
          <div class="offline-modal-container">
            <div class="offline-modal-content">
              <div class="offline-modal-icon">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="var(--error)"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    d="M2,14.5c0,1.6,0.9,3.1,2.2,3.9l-0.9,0.9c-0.4,0.4-0.4,1,0,1.4C3.5,20.9,3.7,21,4,21s0.5-0.1,0.7-0.3l14-14   c0.4-0.4,0.4-1,0-1.4s-1-0.4-1.4,0l-1.8,1.8C14.9,7,14.3,7,13.8,7c-0.1-0.2-0.3-0.3-0.4-0.4C12.4,5.6,11,5,9.5,5S6.6,5.6,5.6,6.6   C4.6,7.6,4,9,4,10.5c0,0.1,0,0.2,0,0.3c-0.2,0.2-0.5,0.3-0.7,0.6C2.5,12.2,2,13.3,2,14.5z M4.7,12.7c0.2-0.2,0.5-0.4,0.7-0.5   c0.4-0.2,0.7-0.6,0.6-1.1C6,10.9,6,10.7,6,10.5C6,9.6,6.4,8.7,7,8c1.3-1.3,3.6-1.3,4.9,0c0.2,0.2,0.4,0.4,0.5,0.7   c0.2,0.3,0.6,0.5,1,0.4l-7.7,7.7c-1-0.3-1.7-1.3-1.7-2.4C4,13.8,4.3,13.2,4.7,12.7z"
                  />
                  <path
                    d="M19.6,10.6c-0.2-0.4-0.4-0.8-0.6-1.2c-0.3-0.5-0.9-0.6-1.4-0.3c-0.5,0.3-0.6,0.9-0.3,1.4c0.2,0.3,0.4,0.7,0.5,1   c0.1,0.3,0.3,0.5,0.6,0.7c0.9,0.4,1.5,1.3,1.5,2.3c0,0.7-0.3,1.3-0.7,1.8c-0.5,0.5-1.1,0.7-1.8,0.7H10c-0.6,0-1,0.4-1,1s0.4,1,1,1   h7.5c1.2,0,2.3-0.5,3.2-1.3c0.9-0.8,1.3-2,1.3-3.2C22,12.8,21.1,11.3,19.6,10.6z"
                  />
                </svg>
              </div>
              <h2 id="offline-modal-title" class="offline-modal-title">
                Server Offline
              </h2>
              <p class="offline-modal-message">
                The server is currently unavailable. All actions are blocked
                until the server comes back online.
              </p>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script>
import { useServerStatus } from "../composables/useServerStatus";

export default {
  name: "OfflineModal",
  setup() {
    const { isOffline } = useServerStatus();

    return {
      isOffline,
    };
  },
};
</script>

<style scoped>
.offline-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--overlay-bg, rgba(0, 0, 0, 0.6));
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100000 !important;
  pointer-events: auto;
}

.offline-modal-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  width: 100%;
  max-width: 400px;
}

.offline-modal-content {
  background: var(--bg-modal);
  border: 1px solid var(--error);
  padding: 2rem;
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

.offline-modal-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1rem;
  width: 64px;
  height: 64px;
  background: rgba(239, 68, 68, 0.1);
}

.offline-modal-title {
  margin: 0 0 0.75rem 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--error);
}

.offline-modal-message {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-primary);
  line-height: 1.5;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .offline-modal-container {
    padding: 1rem;
    max-width: 90%;
  }

  .offline-modal-content {
    padding: 1.5rem;
  }

  .offline-modal-title {
    font-size: 1.25rem;
  }

  .offline-modal-message {
    font-size: 0.875rem;
  }
}
</style>
