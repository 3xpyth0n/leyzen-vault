/**
 * Composable for accessing maintenance mode status
 * Provides reactive access to maintenance mode from global state
 * Uses the healthz/stream SSE connection for real-time updates
 */

import { ref, onMounted, onUnmounted } from "vue";

export function useMaintenanceMode() {
  // Use a reactive ref that syncs with global restore status
  const isMaintenanceMode = ref(false);

  // Function to update from global restore status
  const updateFromGlobal = () => {
    if (typeof window !== "undefined" && window._restoreStatus) {
      isMaintenanceMode.value = window._restoreStatus.maintenance_mode || false;
    } else {
      isMaintenanceMode.value = false;
    }
  };

  // Update interval to sync with global status (lightweight, only reads from memory)
  let syncInterval = null;

  onMounted(() => {
    // Initial sync
    updateFromGlobal();

    // Sync periodically from global state (lightweight check, no HTTP request)
    // The actual data comes from the SSE stream via useHealthCheck
    syncInterval = setInterval(() => {
      updateFromGlobal();
    }, 500);
  });

  onUnmounted(() => {
    if (syncInterval) {
      clearInterval(syncInterval);
    }
  });

  return {
    isMaintenanceMode,
  };
}
