/**
 * File events service for real-time file synchronization via SSE.
 *
 * Handles Server-Sent Events (SSE) connection to receive file change notifications
 * with automatic reconnection and fallback to polling.
 */

const DEFAULT_RETRY_DELAY = 1000; // 1 second
const MAX_RETRY_DELAY = 30000; // 30 seconds
const POLLING_INTERVAL = 5000; // 5 seconds
const SSE_TIMEOUT = 60000; // 60 seconds

class FileEventsClient {
  constructor() {
    this.eventSource = null;
    this.vaultspaceId = null;
    this.lastEventTimestamp = null;
    this.listeners = new Map();
    this.reconnectTimer = null;
    this.retryDelay = DEFAULT_RETRY_DELAY;
    this.isPolling = false;
    this.pollingInterval = null;
    this.isConnected = false;
    this.connectionTimeout = null;
  }

  /**
   * Connect to file events stream for a VaultSpace.
   *
   * @param {string} vaultspaceId - VaultSpace ID to subscribe to
   * @param {string} lastEventTimestamp - Optional ISO timestamp of last received event
   */
  connect(vaultspaceId, lastEventTimestamp = null) {
    if (this.vaultspaceId === vaultspaceId && this.isConnected) {
      // Already connected to this VaultSpace
      return;
    }

    this.disconnect();
    this.vaultspaceId = vaultspaceId;
    this.lastEventTimestamp = lastEventTimestamp;
    this.retryDelay = DEFAULT_RETRY_DELAY;

    this._connectSSE();
  }

  /**
   * Disconnect from file events stream.
   */
  disconnect() {
    this._clearReconnectTimer();
    this._clearPolling();
    this._closeSSE();
    this.vaultspaceId = null;
    this.lastEventTimestamp = null;
    this.isConnected = false;
  }

  /**
   * Subscribe to file events.
   *
   * @param {Function} callback - Function to call when an event is received
   * @returns {Function} Unsubscribe function
   */
  subscribe(callback) {
    const id = Symbol();
    this.listeners.set(id, callback);

    return () => {
      this.listeners.delete(id);
    };
  }

  /**
   * Get recent events from server (for catch-up or polling fallback).
   *
   * @returns {Promise<Array>} Array of recent events
   */
  async getRecentEvents(limit = 50) {
    if (!this.vaultspaceId) {
      return [];
    }

    try {
      const token = localStorage.getItem("jwt_token");
      if (!token) {
        throw new Error("Authentication required");
      }

      const params = new URLSearchParams({
        vaultspace_id: this.vaultspaceId,
        limit: limit.toString(),
      });

      const response = await fetch(`/api/v2/files/events/recent?${params}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        credentials: "same-origin",
      });

      if (!response.ok) {
        throw new Error(
          `Failed to fetch recent events: ${response.statusText}`,
        );
      }

      const data = await response.json();
      return data.events || [];
    } catch (error) {
      return [];
    }
  }

  /**
   * Connect to SSE stream.
   *
   * @private
   */
  async _connectSSE() {
    if (!this.vaultspaceId) {
      return;
    }

    try {
      const token = localStorage.getItem("jwt_token");
      if (!token) {
        this._startPolling();
        return;
      }

      // Establish SSE session with secure cookie before connecting
      try {
        const sessionResponse = await fetch("/api/v2/files/events/session", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          credentials: "same-origin",
        });

        if (!sessionResponse.ok) {
          logger.warn(
            "Failed to establish SSE session, falling back to polling",
          );
          this._startPolling();
          return;
        }
      } catch (error) {
        logger.warn(
          "Error establishing SSE session, falling back to polling:",
          error,
        );
        this._startPolling();
        return;
      }

      const params = new URLSearchParams({
        vaultspace_id: this.vaultspaceId,
      });

      if (this.lastEventTimestamp) {
        params.append("last_event_timestamp", this.lastEventTimestamp);
      }

      const url = `/api/v2/files/events?${params}`;
      this.eventSource = new EventSource(url, {
        withCredentials: true,
      });

      // Set connection timeout
      this.connectionTimeout = setTimeout(() => {
        if (!this.isConnected) {
          this._closeSSE();
          this._startPolling();
        }
      }, SSE_TIMEOUT);

      this.eventSource.onopen = () => {
        this._clearConnectionTimeout();
        this.isConnected = true;
        this.retryDelay = DEFAULT_RETRY_DELAY;
        this._stopPolling();
        this._notifyListeners("connected", { vaultspaceId: this.vaultspaceId });
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this._handleMessage(data);
        } catch (error) {}
      };

      this.eventSource.addEventListener("file_event", (event) => {
        try {
          const data = JSON.parse(event.data);
          this._handleFileEvent(data);
        } catch (error) {}
      });

      this.eventSource.onerror = (error) => {
        this._clearConnectionTimeout();
        this.isConnected = false;
        this._closeSSE();

        // Fallback to polling if SSE fails
        if (!this.isPolling) {
          this._startPolling();
        }

        // Schedule reconnection attempt
        this._scheduleReconnect();
      };
    } catch (error) {
      this._startPolling();
    }
  }

  /**
   * Handle SSE message.
   *
   * @private
   */
  _handleMessage(data) {
    if (data.type === "connected") {
      this._notifyListeners("connected", data);
    } else if (data.type === "file_event") {
      this._handleFileEvent(data.event);
    } else if (data.type === "error") {
      this._notifyListeners("error", data);
    }
  }

  /**
   * Handle file event.
   *
   * @private
   */
  _handleFileEvent(event) {
    if (event && event.timestamp) {
      this.lastEventTimestamp = event.timestamp;
    }
    this._notifyListeners("file_event", event);
  }

  /**
   * Notify all listeners of an event.
   *
   * @private
   */
  _notifyListeners(type, data) {
    this.listeners.forEach((callback) => {
      try {
        callback({ type, data });
      } catch (error) {}
    });
  }

  /**
   * Close SSE connection.
   *
   * @private
   */
  _closeSSE() {
    if (this.eventSource) {
      try {
        this.eventSource.close();
      } catch (error) {
        // Ignore errors when closing
      }
      this.eventSource = null;
    }
    this._clearConnectionTimeout();
  }

  /**
   * Clear connection timeout.
   *
   * @private
   */
  _clearConnectionTimeout() {
    if (this.connectionTimeout) {
      clearTimeout(this.connectionTimeout);
      this.connectionTimeout = null;
    }
  }

  /**
   * Schedule SSE reconnection attempt.
   *
   * @private
   */
  _scheduleReconnect() {
    this._clearReconnectTimer();

    this.reconnectTimer = setTimeout(() => {
      if (this.vaultspaceId && !this.isConnected) {
        this._connectSSE();
      }
    }, this.retryDelay);

    // Exponential backoff
    this.retryDelay = Math.min(this.retryDelay * 2, MAX_RETRY_DELAY);
  }

  /**
   * Clear reconnect timer.
   *
   * @private
   */
  _clearReconnectTimer() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Start polling fallback.
   *
   * @private
   */
  _startPolling() {
    if (this.isPolling) {
      return;
    }

    this.isPolling = true;

    // Poll immediately
    this._poll();

    // Then poll at intervals
    this.pollingInterval = setInterval(() => {
      this._poll();
    }, POLLING_INTERVAL);
  }

  /**
   * Stop polling fallback.
   *
   * @private
   */
  _stopPolling() {
    if (!this.isPolling) {
      return;
    }

    this.isPolling = false;
    this._clearPolling();
  }

  /**
   * Clear polling interval.
   *
   * @private
   */
  _clearPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  /**
   * Poll for recent events.
   *
   * @private
   */
  async _poll() {
    try {
      const events = await this.getRecentEvents(50);
      if (events && events.length > 0) {
        // Filter events newer than last known timestamp
        const newEvents = this.lastEventTimestamp
          ? events.filter(
              (e) => new Date(e.timestamp) > new Date(this.lastEventTimestamp),
            )
          : events;

        // Process new events
        for (const event of newEvents) {
          this._handleFileEvent(event);
        }
      }
    } catch (error) {}
  }
}

// Export singleton instance
export const fileEventsClient = new FileEventsClient();
