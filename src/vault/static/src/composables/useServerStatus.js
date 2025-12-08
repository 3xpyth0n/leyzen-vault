/**
 * Composable for accessing server online/offline status
 * Provides reactive access to server status from global state
 */

import { ref, computed, onMounted, onUnmounted } from "vue";

export function useServerStatus() {
  // Use a reactive ref that watches the global status
  const isOnline = ref(
    typeof window !== "undefined" && window.getServerStatus
      ? window.getServerStatus()
      : true,
  );

  // Function to update the reactive ref from global state
  const updateStatus = () => {
    if (typeof window !== "undefined" && window.getServerStatus) {
      isOnline.value = window.getServerStatus();
    }
  };

  // Watch for status changes via polling (since window._serverStatus might change)
  let statusCheckInterval = null;

  onMounted(() => {
    // Initial check
    updateStatus();

    // Poll for status changes every 500ms to keep reactivity
    statusCheckInterval = setInterval(() => {
      updateStatus();
    }, 500);
  });

  onUnmounted(() => {
    if (statusCheckInterval) {
      clearInterval(statusCheckInterval);
    }
  });

  const isOffline = computed(() => !isOnline.value);

  return {
    isOnline,
    isOffline,
  };
}
