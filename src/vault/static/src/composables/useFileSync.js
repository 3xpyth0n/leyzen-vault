/**
 * Composable for real-time file synchronization via SSE.
 *
 * Provides:
 * - Automatic file list updates when files are created, updated, deleted, renamed, or moved
 * - SSE connection management with automatic reconnection
 * - Polling fallback when SSE is unavailable
 * - Event handling for file operations
 */

import { ref, onMounted, onUnmounted, watch } from "vue";
import { fileEventsClient } from "../services/fileEvents.js";
import { logger } from "../utils/logger.js";

/**
 * Composable for file synchronization
 *
 * @param {Object} options - Configuration options
 * @param {string} options.vaultspaceId - VaultSpace ID to sync
 * @param {Function} options.onFileCreate - Callback when a file is created
 * @param {Function} options.onFileUpdate - Callback when a file is updated
 * @param {Function} options.onFileDelete - Callback when a file is deleted
 * @param {Function} options.onFileRename - Callback when a file is renamed
 * @param {Function} options.onFileMove - Callback when a file is moved
 * @param {Function} options.onFileRestore - Callback when a file is restored
 * @param {Function} options.onRefresh - Callback to refresh the file list
 * @returns {Object} Composable API
 */
export function useFileSync(options = {}) {
  const {
    vaultspaceId = null,
    onFileCreate = null,
    onFileUpdate = null,
    onFileDelete = null,
    onFileRename = null,
    onFileMove = null,
    onFileRestore = null,
    onRefresh = null,
  } = options;

  const isConnected = ref(false);
  const isPolling = ref(false);
  const lastEventTimestamp = ref(null);
  const unsubscribe = ref(null);

  /**
   * Handle file event
   */
  const handleFileEvent = (event) => {
    if (!event || !event.event_type) {
      return;
    }

    const { event_type, file_id, data } = event;

    // Update last event timestamp
    if (event.timestamp) {
      lastEventTimestamp.value = event.timestamp;
    }

    // Call appropriate handler
    switch (event_type) {
      case "create":
        if (onFileCreate) {
          onFileCreate({ fileId: file_id, data });
        } else if (onRefresh) {
          onRefresh();
        }
        break;

      case "update":
        if (onFileUpdate) {
          onFileUpdate({ fileId: file_id, data });
        } else if (onRefresh) {
          onRefresh();
        }
        break;

      case "delete":
        if (onFileDelete) {
          onFileDelete({ fileId: file_id, data });
        } else if (onRefresh) {
          onRefresh();
        }
        break;

      case "rename":
        if (onFileRename) {
          onFileRename({ fileId: file_id, data });
        } else if (onRefresh) {
          onRefresh();
        }
        break;

      case "move":
        if (onFileMove) {
          onFileMove({ fileId: file_id, data });
        } else if (onRefresh) {
          onRefresh();
        }
        break;

      case "restore":
        if (onFileRestore) {
          onFileRestore({ fileId: file_id, data });
        } else if (onRefresh) {
          onRefresh();
        }
        break;

      default:
        logger.warn(`Unknown file event type: ${event_type}`);
    }
  };

  /**
   * Handle connection status change
   */
  const handleConnectionStatus = (type, data) => {
    if (type === "connected") {
      isConnected.value = true;
      isPolling.value = false;
      logger.debug("File sync connected via SSE");
    } else if (type === "error") {
      isConnected.value = false;
      logger.warn("File sync error:", data);
    }
  };

  /**
   * Connect to file events stream
   */
  const connect = () => {
    if (!vaultspaceId) {
      logger.warn("Cannot connect to file events: vaultspaceId is required");
      return;
    }

    // Unsubscribe from previous connection
    if (unsubscribe.value) {
      unsubscribe.value();
      unsubscribe.value = null;
    }

    // Subscribe to file events
    unsubscribe.value = fileEventsClient.subscribe(({ type, data }) => {
      if (type === "file_event") {
        handleFileEvent(data);
      } else if (type === "connected") {
        handleConnectionStatus("connected", data);
      } else if (type === "error") {
        handleConnectionStatus("error", data);
      }
    });

    // Connect to SSE stream
    fileEventsClient.connect(vaultspaceId, lastEventTimestamp.value);

    // Check if polling is active (indicates SSE fallback)
    const checkPollingStatus = () => {
      // Access internal state via a workaround
      // In a real implementation, we might expose this via the client
      setTimeout(() => {
        // This is a workaround - in production, the client should expose polling status
        // For now, we'll assume polling if not connected after a delay
        if (!isConnected.value) {
          isPolling.value = true;
        }
      }, 2000);
    };

    checkPollingStatus();
  };

  /**
   * Disconnect from file events stream
   */
  const disconnect = () => {
    if (unsubscribe.value) {
      unsubscribe.value();
      unsubscribe.value = null;
    }
    fileEventsClient.disconnect();
    isConnected.value = false;
    isPolling.value = false;
  };

  /**
   * Manually refresh file list
   */
  const refresh = () => {
    if (onRefresh) {
      onRefresh();
    }
  };

  // Watch for vaultspaceId changes
  watch(
    () => vaultspaceId,
    (newId, oldId) => {
      if (newId !== oldId) {
        disconnect();
        if (newId) {
          connect();
        }
      }
    },
  );

  // Connect on mount
  onMounted(() => {
    if (vaultspaceId) {
      connect();
    }
  });

  // Disconnect on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    isPolling,
    connect,
    disconnect,
    refresh,
  };
}
