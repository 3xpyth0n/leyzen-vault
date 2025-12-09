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
  let healthCheckInterval = null;
  let offlineTimer = null;
  if (typeof window !== "undefined") {
    if (!window._serverStatus) {
      window._serverStatus = { isOnline: true, consecutiveErrors: 0 };
    }
    if (window._serverStatus.consecutiveErrors === undefined) {
      window._serverStatus.consecutiveErrors = 0;
    }
  }
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 10;
  const reconnectIntervalMs = 500;
  const healthCheckPollInterval = 100;
  const fetchTimeout = 1000;
  const maxConsecutiveErrors = 5;

  const connectSSE = () => {
    if (eventSource) {
      return;
    }

    isChecking.value = true;

    try {
      eventSource = new EventSource("/healthz/stream", {
        withCredentials: true,
      });

      eventSource.onopen = () => {
        isChecking.value = false;
        reconnectAttempts = 0;
        clearOfflineTimer();

        const wasOffline = !isOnline.value;
        const globalWasOffline =
          typeof window !== "undefined" &&
          window._serverStatus &&
          !window._serverStatus.isOnline;
        if (wasOffline && globalWasOffline) {
          if (typeof window !== "undefined" && window._serverStatus) {
            window._serverStatus.consecutiveErrors = 0;
          }
        }

        if (reconnectInterval) {
          clearInterval(reconnectInterval);
          reconnectInterval = null;
        }
        stopHealthCheckPolling();

        if (!isOnline.value) {
          isOnline.value = true;
          if (typeof window !== "undefined" && window.updateServerStatus) {
            window.updateServerStatus(true);
          }
        }
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.status === "ok") {
            const wasOffline = !isOnline.value;
            const globalWasOffline =
              typeof window !== "undefined" &&
              window._serverStatus &&
              !window._serverStatus.isOnline;
            if (wasOffline && globalWasOffline) {
              if (typeof window !== "undefined" && window._serverStatus) {
                window._serverStatus.consecutiveErrors = 0;
              }
              isOnline.value = true;
              if (typeof window !== "undefined" && window.updateServerStatus) {
                window.updateServerStatus(true);
              }
            }
          }
        } catch (error) {
          console.warn("Invalid health check data:", error);
        }
      };

      eventSource.onerror = (error) => {
        isChecking.value = false;

        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }

        clearOfflineTimer();
        const wasOffline = !isOnline.value;
        const globalWasOffline =
          typeof window !== "undefined" &&
          window._serverStatus &&
          !window._serverStatus.isOnline;
        if (wasOffline && globalWasOffline) {
          if (typeof window !== "undefined" && window._serverStatus) {
            window._serverStatus.consecutiveErrors = 0;
          }
        }

        offlineTimer = setTimeout(() => {
          if (!eventSource && isOnline.value) {
            isOnline.value = false;
            if (typeof window !== "undefined" && window.updateServerStatus) {
              window.updateServerStatus(false);
            }
            startReconnectInterval();
          }
          offlineTimer = null;
        }, 1000);

        startReconnectInterval();
      };
    } catch (error) {
      isChecking.value = false;
      isOnline.value = false;
      if (typeof window !== "undefined" && window.updateServerStatus) {
        window.updateServerStatus(false);
      }
      startReconnectInterval();
    }
  };

  const checkHealthWithFetch = async () => {
    try {
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

        const networkErrorStatusCodes = [500, 502, 503, 504];
        if (networkErrorStatusCodes.includes(response.status)) {
          if (typeof window !== "undefined" && window.notifyServerError) {
            window.notifyServerError();
          }
          return false;
        }

        if (response.ok) {
          const data = await response.json();
          if (data && data.status === "ok") {
            clearOfflineTimer();
            const wasOffline = !isOnline.value;
            const globalWasOffline =
              typeof window !== "undefined" &&
              window._serverStatus &&
              !window._serverStatus.isOnline;
            if (wasOffline && globalWasOffline) {
              if (typeof window !== "undefined" && window._serverStatus) {
                window._serverStatus.consecutiveErrors = 0;
              }
              isOnline.value = true;
              if (typeof window !== "undefined" && window.updateServerStatus) {
                window.updateServerStatus(true);
              }
              stopHealthCheckPolling();
              reconnectAttempts = 0;
              connectSSE();
            }
            return true;
          }
        }
        return false;
      } catch (fetchError) {
        clearTimeout(timeoutId);
        if (typeof window !== "undefined" && window.notifyServerError) {
          window.notifyServerError();
        }
        return false;
      }
    } catch (error) {
      return false;
    }
  };

  const clearOfflineTimer = () => {
    if (offlineTimer) {
      clearTimeout(offlineTimer);
      offlineTimer = null;
    }
  };

  const notifyServerError = () => {
    if (typeof window !== "undefined") {
      if (!window._serverStatus) {
        window._serverStatus = { isOnline: true, consecutiveErrors: 0 };
      }
      if (
        window._serverStatus.consecutiveErrors === undefined ||
        window._serverStatus.consecutiveErrors === null ||
        typeof window._serverStatus.consecutiveErrors !== "number"
      ) {
        const existing = window._serverStatus.consecutiveErrors;
        window._serverStatus.consecutiveErrors =
          typeof existing === "number" ? existing : 0;
      }

      if (isOnline.value) {
        window._serverStatus.consecutiveErrors =
          window._serverStatus.consecutiveErrors + 1;
      } else {
        return;
      }
    } else {
      return;
    }

    const consecutiveErrors = window._serverStatus.consecutiveErrors;

    if (consecutiveErrors >= maxConsecutiveErrors) {
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      isOnline.value = false;
      if (typeof window !== "undefined" && window.updateServerStatus) {
        window.updateServerStatus(false);
      }
      startReconnectInterval();
    }
  };

  const startHealthCheckPolling = () => {
    if (healthCheckInterval) {
      clearInterval(healthCheckInterval);
      healthCheckInterval = null;
    }

    healthCheckInterval = setInterval(async () => {
      const isBack = await checkHealthWithFetch();
      if (isBack) {
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
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (reconnectInterval) {
      clearInterval(reconnectInterval);
      reconnectInterval = null;
    }

    if (reconnectAttempts >= maxReconnectAttempts) {
      return;
    }

    startHealthCheckPolling();

    reconnectInterval = setInterval(() => {
      if (reconnectAttempts >= maxReconnectAttempts) {
        clearInterval(reconnectInterval);
        reconnectInterval = null;
        return;
      }

      if (!eventSource) {
        reconnectAttempts++;
        connectSSE();
      } else {
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

  watch(
    isOnline,
    (newStatus) => {
      if (typeof window !== "undefined" && window.updateServerStatus) {
        window.updateServerStatus(newStatus);
      }
    },
    { immediate: true },
  );

  onMounted(() => {
    if (typeof window !== "undefined" && window.updateServerStatus) {
      window.updateServerStatus(isOnline.value);
    }
  });

  onMounted(() => {
    connectSSE();
  });

  onUnmounted(() => {
    disconnectSSE();
  });

  const resetErrorCounter = () => {};

  if (typeof window !== "undefined") {
    window._notifyServerError = notifyServerError;
    window._resetErrorCounter = resetErrorCounter;
  }

  return {
    isOnline,
    isChecking,
    connectSSE,
    disconnectSSE,
  };
}

if (typeof window !== "undefined") {
  if (!window._serverStatus) {
    window._serverStatus = { isOnline: true, consecutiveErrors: 0 };
  }
  if (
    window._serverStatus.consecutiveErrors === undefined ||
    window._serverStatus.consecutiveErrors === null
  ) {
    window._serverStatus.consecutiveErrors = 0;
  }

  window.getServerStatus = () => {
    return window._serverStatus ? window._serverStatus.isOnline : true;
  };

  window.updateServerStatus = (status) => {
    if (!window._serverStatus) {
      window._serverStatus = { isOnline: true, consecutiveErrors: 0 };
    }
    const currentErrors = window._serverStatus.consecutiveErrors || 0;
    const wasOffline = !window._serverStatus.isOnline;
    const isComingOnline = wasOffline && status === true;

    window._serverStatus.isOnline = status;

    if (isComingOnline) {
      window._serverStatus.consecutiveErrors = 0;
    } else {
      window._serverStatus.consecutiveErrors = currentErrors;
    }
  };

  window.notifyServerError = () => {
    if (window._notifyServerError) {
      window._notifyServerError();
    }
  };

  window.resetErrorCounter = () => {
    if (window._resetErrorCounter) {
      window._resetErrorCounter();
    }
  };
}
