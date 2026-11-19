(() => {
  const token = API.getToken();
  const user = API.getUser();
  const connectForm = document.getElementById("connectForm");
  const orderInput = document.getElementById("orderId");
  const status = document.getElementById("status");
  const gpsButton = document.getElementById("gps");
  const simulateButton = document.getElementById("simulate");
  const stopButton = document.getElementById("stop");
  let socket = null;
  let watchId = null;
  let simulationTimer = null;
  let map = null;
  let marker = null;

  function setStatus(message, state = "") {
    status.textContent = message;
    status.dataset.state = state;
  }

  function setSharingControls(enabled) {
    gpsButton.disabled = !enabled;
    simulateButton.disabled = !enabled;
    stopButton.disabled = !enabled && watchId === null && simulationTimer === null;
  }

  function stopLocationSources() {
    if (watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(watchId);
    watchId = null;
    if (simulationTimer !== null) window.clearInterval(simulationTimer);
    simulationTimer = null;
  }

  function publish(latitude, longitude) {
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setStatus("The location coordinates were invalid.", "error");
      return;
    }
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setStatus("Connect to an assigned order before sharing location.", "error");
      return;
    }
    socket.send(JSON.stringify({ lat, lon }));
    if (map) {
      if (marker) marker.setLatLng([lat, lon]);
      else marker = L.circleMarker([lat, lon], { radius: 9, color: "#c2410c", fillColor: "#f97316", fillOpacity: 1 }).addTo(map);
      map.panTo([lat, lon]);
    }
    setStatus(`Sharing location: ${lat.toFixed(5)}, ${lon.toFixed(5)}`, "live");
  }

  function buildSocketUrl(orderId) {
    const url = new URL(API_BASE_URL);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `/ws/delivery/${orderId}`;
    url.search = new URLSearchParams({ token }).toString();
    return url.href;
  }

  if (!token || user?.role !== "delivery_partner") {
    setStatus("Sign in with a delivery partner account to share location.", "error");
    connectForm.querySelector("button[type='submit']").disabled = true;
    window.setTimeout(() => { window.location.href = "/pages/login.html"; }, 900);
    return;
  }

  if (window.L) {
    map = L.map("partnerMap", { scrollWheelZoom: false }).setView([12.9716, 77.5946], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors"
    }).addTo(map);
  } else {
    setStatus("Map tiles did not load. You can still share your location.", "warning");
  }

  connectForm.addEventListener("submit", event => {
    event.preventDefault();
    const orderId = Number(orderInput.value);
    if (!Number.isSafeInteger(orderId) || orderId < 1) {
      setStatus("Enter a valid assigned order ID.", "error");
      orderInput.focus();
      return;
    }
    stopLocationSources();
    socket?.close();
    setStatus("Connecting to the assigned order…");
    socket = new WebSocket(buildSocketUrl(orderId));
    socket.addEventListener("open", () => {
      setStatus(`Connected to order ${orderId}. Location sharing is off.`, "connected");
      setSharingControls(true);
    });
    socket.addEventListener("message", event => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "error") setStatus(message.detail || "The server rejected this location update.", "error");
      } catch {
        setStatus("Received an unreadable update from the server.", "warning");
      }
    });
    socket.addEventListener("close", event => {
      stopLocationSources();
      setSharingControls(false);
      setStatus(event.code === 4403 ? "This order is not assigned to your account." : "Connection closed.", "warning");
    });
    socket.addEventListener("error", () => setStatus("Connection failed. Check the order assignment and try again.", "error"));
  });

  gpsButton.addEventListener("click", () => {
    if (!navigator.geolocation) {
      setStatus("This browser does not provide geolocation.", "error");
      return;
    }
    if (watchId !== null) navigator.geolocation.clearWatch(watchId);
    watchId = navigator.geolocation.watchPosition(
      position => publish(position.coords.latitude, position.coords.longitude),
      error => setStatus(error.message || "Could not read the device location.", "error"),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
    setSharingControls(true);
    setStatus("Waiting for GPS location…", "connected");
  });

  simulateButton.addEventListener("click", () => {
    stopLocationSources();
    const route = [[12.9716, 77.5946], [12.968, 77.600], [12.962, 77.606], [12.955, 77.612], [12.948, 77.618]];
    let index = 0;
    simulationTimer = window.setInterval(() => {
      if (!socket || socket.readyState !== WebSocket.OPEN) {
        stopLocationSources();
        setSharingControls(false);
        return;
      }
      publish(...route[index++ % route.length]);
    }, 1800);
    setSharingControls(true);
    setStatus("Demo route is sharing location.", "live");
  });

  stopButton.addEventListener("click", () => {
    stopLocationSources();
    socket?.close();
    socket = null;
    setSharingControls(false);
    setStatus("Location sharing stopped.");
  });

  window.addEventListener("beforeunload", () => {
    stopLocationSources();
    socket?.close();
  });
})();
