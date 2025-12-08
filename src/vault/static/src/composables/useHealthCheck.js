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
  let proactiveCheckInterval = null; // Continuous polling to detect offline quickly
  let offlineTimer = null; // Timer before marking as offline (to ignore rotations)
  let reconnectAttempts = 0;
  let consecutiveFailures = 0; // Track consecutive fetch failures for fast offline detection
  const maxReconnectAttempts = 10;
  const reconnectIntervalMs = 500; // Check every 500ms when offline for fast detection
  const healthCheckPollInterval = 500; // Poll /healthz every 500ms when offline
  const proactiveCheckIntervalMs = 2000; // Check every 2 seconds when online (proactive detection)
  const fetchTimeout = 1000; // 1 second timeout for fetch requests
  const maxConsecutiveFailures = 2; // Mark offline after 2 consecutive failures
  const rotationGracePeriod = 1000; // Wait 1 second before marking offline (ignore rotations)

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
        consecutiveFailures = 0; // Reset failure counter

        // Cancel offline timer - this was likely just a rotation
        clearOfflineTimer();

        // Stop reconnection interval and polling since we're connected
        if (reconnectInterval) {
          clearInterval(reconnectInterval);
          reconnectInterval = null;
        }
        stopHealthCheckPolling();

        // Start proactive checking when online
        startProactiveChecking();

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
            // Server is online - reset failure counter
            consecutiveFailures = 0;
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

  const checkHealthWithFetch = async (isProactive = false) => {
    try {
      // Use a short timeout to avoid long waits during rotations
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), fetchTimeout);

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
            // Server is online - reset failure counter
            consecutiveFailures = 0;

            // Cancel offline timer (was likely rotation)
            clearOfflineTimer();

            // Server is back online! Reconnect SSE if we were offline
            if (!isOnline.value) {
              isOnline.value = true;
              // Update global status immediately when marked online
              if (typeof window !== "undefined" && window.updateServerStatus) {
                window.updateServerStatus(true);
              }

              // Stop polling and reconnect SSE
              stopHealthCheckPolling();
              reconnectAttempts = 0; // Reset attempts since server is back
              connectSSE();
            }
            return true;
          }
        }
        // Non-OK response - count as failure
        if (isProactive) {
          consecutiveFailures++;
          checkForOffline();
        }
        return false;
      } catch (fetchError) {
        clearTimeout(timeoutId);
        // Network errors or timeouts
        if (isProactive) {
          consecutiveFailures++;
          checkForOffline();
        }
        return false;
      }
    } catch (error) {
      // Unexpected error - count as failure if proactive
      if (isProactive) {
        consecutiveFailures++;
        checkForOffline();
      }
      return false;
    }
  };

  const clearOfflineTimer = () => {
    if (offlineTimer) {
      clearTimeout(offlineTimer);
      offlineTimer = null;
    }
  };

  const checkForOffline = () => {
    // If we have multiple consecutive failures, mark as offline quickly
    if (consecutiveFailures >= maxConsecutiveFailures && isOnline.value) {
      // Clear any existing offline timer
      clearOfflineTimer();

      // Mark as offline immediately or after a very short grace period
      offlineTimer = setTimeout(() => {
        if (!eventSource || consecutiveFailures >= maxConsecutiveFailures) {
          if (isOnline.value) {
            isOnline.value = false;
            // Update global status immediately when marked offline
            if (typeof window !== "undefined" && window.updateServerStatus) {
              window.updateServerStatus(false);
            }
            // Close EventSource if it exists (it's not working anyway)
            if (eventSource) {
              eventSource.close();
              eventSource = null;
            }
            // Start reconnection attempts
            startReconnectInterval();
          }
        }
        offlineTimer = null;
      }, rotationGracePeriod);
    }
  };

  const startProactiveChecking = () => {
    // Clear any existing proactive check interval
    stopProactiveChecking();

    // Start periodic health checks to detect offline quickly
    proactiveCheckInterval = setInterval(async () => {
      // Only check if we think we're online
      if (isOnline.value && eventSource) {
        await checkHealthWithFetch(true);
      }
    }, proactiveCheckIntervalMs);
  };

  const stopProactiveChecking = () => {
    if (proactiveCheckInterval) {
      clearInterval(proactiveCheckInterval);
      proactiveCheckInterval = null;
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
    stopProactiveChecking();

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    reconnectAttempts = 0;
    consecutiveFailures = 0;
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
    // Also start proactive checking after a short delay to allow SSE to connect first
    setTimeout(() => {
      if (isOnline.value) {
        startProactiveChecking();
      }
    }, 1000);
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
