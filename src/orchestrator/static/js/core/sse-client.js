const DEFAULT_RETRY = 5000;
const DEFAULT_THROTTLE = 500;

export class SSEClient extends EventTarget {
  constructor(streams, options = {}) {
    super();
    this.streams = (streams || []).map((stream, index) => ({
      id: index,
      name: stream.name || `stream-${index}`,
      url: stream.url,
      event: stream.event || "message",
      eventType: stream.eventType || "message",
      withCredentials: stream.withCredentials ?? true,
      transform:
        typeof stream.transform === "function" ? stream.transform : null,
      source: null,
      retryTimer: null,
      backoff: options.retryDelay || DEFAULT_RETRY,
    }));
    this.throttleMs = options.throttleMs || DEFAULT_THROTTLE;
    this.buffer = [];
    this.flushTimer = null;
  }

  start() {
    this.streams.forEach((stream) => this._connect(stream));
  }

  stop() {
    this.streams.forEach((stream) => this._close(stream));
    if (this.flushTimer) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
    this.buffer = [];
  }

  subscribe(type, handler, options) {
    this.addEventListener(type, handler, options);
    return () => this.removeEventListener(type, handler, options);
  }

  _connect(stream) {
    this._close(stream);
    if (!stream.url) return;

    try {
      const source = new EventSource(stream.url, {
        withCredentials: stream.withCredentials,
      });
      stream.source = source;

      source.addEventListener(stream.eventType, (event) =>
        this._handleMessage(stream, event),
      );

      source.onopen = () => {
        this.dispatchEvent(
          new CustomEvent("connection-open", {
            detail: { stream: stream.name },
          }),
        );
      };

      source.onerror = (error) => {
        this.dispatchEvent(
          new CustomEvent("connection-error", {
            detail: { stream: stream.name, error },
          }),
        );
        this._scheduleReconnect(stream);
      };
    } catch (error) {
      this.dispatchEvent(
        new CustomEvent("connection-error", {
          detail: { stream: stream.name, error },
        }),
      );
      this._scheduleReconnect(stream);
    }
  }

  _close(stream) {
    if (stream.retryTimer) {
      clearTimeout(stream.retryTimer);
      stream.retryTimer = null;
    }
    if (stream.source) {
      try {
        stream.source.close();
      } catch (error) {
        console.warn("Failed to close SSE source", error);
      }
      stream.source = null;
    }
  }

  _scheduleReconnect(stream) {
    if (stream.retryTimer) return;
    this.dispatchEvent(
      new CustomEvent("connection-reconnecting", {
        detail: { stream: stream.name },
      }),
    );
    stream.retryTimer = setTimeout(() => {
      stream.retryTimer = null;
      this._connect(stream);
    }, stream.backoff || DEFAULT_RETRY);
  }

  _handleMessage(stream, event) {
    let payload = null;
    try {
      payload = JSON.parse(event.data);
    } catch (error) {
      console.warn("Invalid SSE payload", error);
      return;
    }

    if (stream.transform) {
      try {
        payload = stream.transform(payload);
      } catch (error) {
        console.warn("SSE transform failed", error);
      }
    }

    this.buffer.push({ stream, payload });
    this._scheduleFlush();
  }

  _scheduleFlush() {
    if (this.flushTimer) return;
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      this._flush();
    }, this.throttleMs);
  }

  _flush() {
    if (!this.buffer.length) return;
    const batch = this.buffer.splice(0, this.buffer.length);
    const latestByEvent = new Map();

    for (const item of batch) {
      latestByEvent.set(item.stream.event, {
        stream: item.stream.name,
        data: item.payload,
      });
    }

    latestByEvent.forEach((value, eventName) => {
      this.dispatchEvent(new CustomEvent(eventName, { detail: value }));
    });

    this.dispatchEvent(
      new CustomEvent("batch", {
        detail: {
          updates: batch.map((item) => ({
            stream: item.stream.name,
            event: item.stream.event,
            data: item.payload,
          })),
        },
      }),
    );
  }
}
