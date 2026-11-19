/** Authenticated, same-origin WebSocket client for live order events. */
const WSClient = {
  socket: null,
  reconnectAttempts: 0,
  maxReconnectAttempts: 10,
  listeners: [],
  stopped: false,

  connect() {
    const token = API.getToken();
    if (!token) {
      this.updateLiveIndicator(false, "Sign in for live updates");
      return;
    }
    this.stopped = false;

    const socketBase = window.location.protocol === "file:"
      ? "http://127.0.0.1:8000"
      : window.location.origin;
    const socketUrl = new URL("/ws/orders", socketBase);
    socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";
    socketUrl.searchParams.set("token", token);

    try {
      this.socket = new WebSocket(socketUrl.toString());
      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.updateLiveIndicator(true);
      };
      this.socket.onmessage = event => {
        try {
          this.handleIncomingEvent(JSON.parse(event.data));
        } catch (error) {
          console.error("[WebSocket] Could not parse event:", error);
        }
      };
      this.socket.onclose = event => {
        const rejected = event.code === 4401 || event.code === 4403;
        this.updateLiveIndicator(false, rejected ? "Sign in again for live updates" : "Reconnecting to live updates…");
        if (!this.stopped && API.getToken() && !rejected && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts += 1;
          const delay = Math.min(1000 * (1.5 ** this.reconnectAttempts), 10000);
          window.setTimeout(() => this.connect(), delay);
        }
      };
      this.socket.onerror = error => console.warn("[WebSocket] Connection error:", error);
    } catch (error) {
      console.error("[WebSocket] Failed to initiate connection:", error);
      this.updateLiveIndicator(false, "Live updates unavailable");
    }
  },

  disconnect() {
    this.stopped = true;
    this.socket?.close(1000, "Client disconnected");
    this.socket = null;
  },

  handleIncomingEvent(data) {
    if (["NEW_ORDER", "ORDER_STATUS_CHANGED", "DELIVERY_STATUS_UPDATED", "KITCHEN_ORDER_UPDATED"].includes(data.event)) {
      this.playChime();
    }

    if (data.event === "NEW_ORDER") {
      Auth.showToast(`New order #${data.order_number} received (₹${Number(data.total_amount || 0).toFixed(2)})`, "info");
    } else if (data.event === "ORDER_STATUS_CHANGED") {
      Auth.showToast(`Order #${data.order_number} is now ${String(data.new_status || "updated").replaceAll("_", " ").toUpperCase()}`, "info");
    }

    this.listeners.forEach(listener => {
      try {
        listener(data);
      } catch (error) {
        console.error("[WebSocket] Listener failed:", error);
      }
    });
  },

  addListener(callback) {
    if (typeof callback === "function") this.listeners.push(callback);
  },

  updateLiveIndicator(isConnected, message = "") {
    const element = document.getElementById("wsLiveIndicator");
    if (!element) return;
    element.className = isConnected
      ? "badge bg-success-subtle text-success border border-success d-inline-flex align-items-center gap-1"
      : "badge bg-secondary-subtle text-secondary border d-inline-flex align-items-center gap-1";
    if (isConnected) {
      element.innerHTML = '<span class="live-indicator-dot" aria-hidden="true"></span> Live updates';
    } else {
      element.textContent = message || "Live updates offline";
    }
  },

  playChime() {
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      const audioContext = new AudioContextClass();
      const startAt = audioContext.currentTime;
      [[659.25, 0, 0.35], [987.77, 0.15, 0.55]].forEach(([frequency, offset, duration]) => {
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(frequency, startAt + offset);
        gain.gain.setValueAtTime(0.15, startAt + offset);
        gain.gain.exponentialRampToValueAtTime(0.001, startAt + offset + duration);
        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        oscillator.start(startAt + offset);
        oscillator.stop(startAt + offset + duration);
      });
      window.setTimeout(() => audioContext.close(), 1000);
    } catch {
      // Audio may be unavailable until a user gesture or on an unsupported browser.
    }
  }
};

document.addEventListener("DOMContentLoaded", () => WSClient.connect());
