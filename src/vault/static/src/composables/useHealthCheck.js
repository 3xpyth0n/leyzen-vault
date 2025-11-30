/**
 * Composable for server health check
 * Polls /healthz endpoint every 5 seconds to determine server status
 */

import { ref, onMounted, onUnmounted } from "vue";

export function useHealthCheck() {
  const isOnline = ref(true);
  const isChecking = ref(false);
  let healthCheckInterval = null;
  let abortController = null;

  const checkHealth = async () => {
    // Cancel any pending request
    if (abortController) {
      abortController.abort();
    }

    abortController = new AbortController();
    isChecking.value = true;

    try {
      const response = await fetch("/healthz", {
        method: "GET",
        signal: abortController.signal,
        credentials: "same-origin",
        // Add a timeout by using a race condition
      });

      // Check if response is ok (status 200-299)
      if (response.ok) {
        const data = await response.json();
        // Verify the response contains the expected status
        if (data && data.status === "ok") {
          isOnline.value = true;
        } else {
          isOnline.value = false;
        }
      } else {
        isOnline.value = false;
      }
    } catch (error) {
      // Network errors, timeouts, or aborted requests
      if (error.name !== "AbortError") {
        isOnline.value = false;
      }
    } finally {
      isChecking.value = false;
      abortController = null;
    }
  };

  const startHealthCheck = () => {
    // Don't start if already running
    if (healthCheckInterval) {
      return;
    }

    // Initial check
    checkHealth();

    // Set up interval for periodic checks (every 5 seconds)
    healthCheckInterval = setInterval(() => {
      checkHealth();
    }, 5000);
  };

  const stopHealthCheck = () => {
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval);
      healthCheckInterval = null;
    }

    // Cancel any pending request
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  };

  // Start health check when composable is used
  onMounted(() => {
    startHealthCheck();
  });

  // Stop health check when component is unmounted
  onUnmounted(() => {
    stopHealthCheck();
  });

  return {
    isOnline,
    isChecking,
    checkHealth,
    startHealthCheck,
    stopHealthCheck,
  };
}
