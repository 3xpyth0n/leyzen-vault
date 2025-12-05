/**
 * Composable for server health check
 * Uses Server-Sent Events (SSE) for real-time health status monitoring
 */

import { ref, watch, onMounted, onUnmounted } from "vue";

export function useHealthCheck() {
  const isOnline = ref(true);
  const isChecking = ref(false);
  let eventSource = null;
  let reconnectTimer = null;
  let reconnectInterval = null;
  let healthCheckInterval = null; // Fast polling when offline
  let offlineTimer = null; // Timer before marking as offline (to ignore rotations)
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const reconnectIntervalMs = 500; // Check every 500ms when offline for fast detection
  const healthCheckPollInterval = 500; // Poll /healthz every 500ms when offline
  const rotationGracePeriod = 5000; // Wait 5 seconds before marking offline (ignore rotations)

  const connectSSE = () => {
    // Don't start if already running
    if (eventSource) {
      return;
    }

    isChecking.value = true;

    try {
      eventSource = new EventSource("/healthz/stream", {
        withCredentials: true,
      });

      eventSource.onopen = () => {
        // Connection opened successfully
        isChecking.value = false;
        reconnectAttempts = 0;

        // Cancel offline timer - this was likely just a rotation
        clearOfflineTimer();

        // Stop reconnection interval and polling since we're connected
        if (reconnectInterval) {
          clearInterval(reconnectInterval);
          reconnectInterval = null;
        }
        stopHealthCheckPolling();

        // If we were offline, we're now online
        if (!isOnline.value) {
          isOnline.value = true;
          // Update global status immediately when marked online
          if (typeof window !== "undefined" && window.updateServerStatus) {
            window.updateServerStatus(true);
          }
        }
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.status === "ok") {
            // Server is online
            if (!isOnline.value) {
              isOnline.value = true;
            }
          }
        } catch (error) {
          // Invalid JSON, but connection is still alive
          console.warn("Invalid health check data:", error);
        }
      };

      eventSource.onerror = (error) => {
        // Connection error or closed - could be rotation or real downtime
        isChecking.value = false;

        // Close the connection
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }

        // Don't mark as offline immediately - wait grace period to distinguish
        // rotations (quick reconnection) from real downtime
        clearOfflineTimer();
        offlineTimer = setTimeout(() => {
          // Only mark as offline if we still don't have a connection after grace period
          if (!eventSource && isOnline.value) {
            isOnline.value = false;
            // Update global status immediately when marked offline
            if (typeof window !== "undefined" && window.updateServerStatus) {
              window.updateServerStatus(false);
            }
          }
          offlineTimer = null;
        }, rotationGracePeriod);

        // Start aggressive reconnection interval for fast detection
        startReconnectInterval();
      };
    } catch (error) {
      // Failed to create EventSource
      isChecking.value = false;
      isOnline.value = false;
      // Update global status immediately when marked offline
      if (typeof window !== "undefined" && window.updateServerStatus) {
        window.updateServerStatus(false);
      }

      // Start aggressive reconnection interval for fast detection
      startReconnectInterval();
    }
  };

  const checkHealthWithFetch = async () => {
    try {
      // Use a short timeout to avoid long waits during rotations
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout

      try {
        const response = await fetch("/healthz", {
          method: "GET",
          credentials: "same-origin",
          cache: "no-cache",
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (response.ok) {
          const data = await response.json();
          if (data && data.status === "ok") {
            // Server is back online! Cancel offline timer (was likely rotation)
            clearOfflineTimer();

            // Server is back online! Reconnect SSE immediately
            if (!isOnline.value) {
              isOnline.value = true;
              // Update global status immediately when marked online
              if (typeof window !== "undefined" && window.updateServerStatus) {
                window.updateServerStatus(true);
              }
            }

            // Stop polling and reconnect SSE
            stopHealthCheckPolling();
            reconnectAttempts = 0; // Reset attempts since server is back
            connectSSE();
            return true;
          }
        }
        return false;
      } catch (fetchError) {
        clearTimeout(timeoutId);
        // Network errors or timeouts - server might be temporarily unavailable
        // Don't mark as offline immediately, keep trying
        if (fetchError.name === "AbortError") {
          // Timeout - server might be slow during rotation, keep trying
          return false;
        }
        // Other network errors - keep trying
        return false;
      }
    } catch (error) {
      // Unexpected error - keep trying
      return false;
    }
  };

  const clearOfflineTimer = () => {
    if (offlineTimer) {
      clearTimeout(offlineTimer);
      offlineTimer = null;
    }
  };

  const startHealthCheckPolling = () => {
    // Clear any existing polling
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval);
      healthCheckInterval = null;
    }

    // Start fast polling with fetch to detect server coming back online
    healthCheckInterval = setInterval(async () => {
      const isBack = await checkHealthWithFetch();
      if (isBack) {
        // Server is back, polling will be stopped by checkHealthWithFetch
        stopHealthCheckPolling();
      }
    }, healthCheckPollInterval);
  };

  const stopHealthCheckPolling = () => {
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval);
      healthCheckInterval = null;
    }
  };

  const startReconnectInterval = () => {
    // Clear any existing reconnect timers/intervals
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }

    // Don't start if already at max attempts
    if (reconnectAttempts >= maxReconnectAttempts) {
      return;
    }

    // Start fast polling to detect server coming back online
    startHealthCheckPolling();

    // Also try to reconnect SSE periodically as backup
    reconnectInterval = setInterval(() => {
      if (reconnectAttempts >= maxReconnectAttempts) {
        clearInterval(reconnectInterval);
        reconnectInterval = null;
        return;
      }

      // Only try to connect if we don't already have a connection
      if (!eventSource) {
        reconnectAttempts++;
        connectSSE();
      } else {
        // Connection exists, stop the interval
        clearInterval(reconnectInterval);
        reconnectInterval = null;
      }
    }, reconnectIntervalMs);
  };

  const disconnectSSE = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }

    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }

    clearOfflineTimer();
    stopHealthCheckPolling();

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    reconnectAttempts = 0;
    isChecking.value = false;
  };

  // Watch isOnline and update global status immediately
  // This ensures the global status is always in sync with the composable
  watch(
    isOnline,
    (newStatus) => {
      if (typeof window !== "undefined" && window.updateServerStatus) {
        window.updateServerStatus(newStatus);
      }
    },
    { immediate: true },
  );

  // Also update global status on mount to ensure it's initialized
  onMounted(() => {
    if (typeof window !== "undefined" && window.updateServerStatus) {
      window.updateServerStatus(isOnline.value);
    }
  });

  // Start health check when composable is used
  onMounted(() => {
    connectSSE();
  });

  // Stop health check when component is unmounted
  onUnmounted(() => {
    disconnectSSE();
  });

  return {
    isOnline,
    isChecking,
    connectSSE,
    disconnectSSE,
  };
}

// Export a global function to check server status
// This allows api.js to check if server is online before making requests
// Initialize global status tracking
if (typeof window !== "undefined") {
  // Initialize global status (default to true)
  if (!window._serverStatus) {
    window._serverStatus = { isOnline: true };
  }

  // This will be updated by components using useHealthCheck
  window.getServerStatus = () => {
    return window._serverStatus ? window._serverStatus.isOnline : true;
  };

  // Function to update global status (called by components)
  window.updateServerStatus = (status) => {
    if (!window._serverStatus) {
      window._serverStatus = { isOnline: true };
    }
    window._serverStatus.isOnline = status;
  };
}
