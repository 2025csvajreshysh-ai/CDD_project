/* Rider-side Leaflet map and location publisher for assigned deliveries. */
window.PartnerTracking = (() => {
  const state = { map: null, orders: [], order: null, socket: null, watchId: null, simulation: null, markers: {}, route: null };
  const token = () => localStorage.getItem("aifoodie_token");
  const status = message => { const el = document.getElementById("partnerGpsStatus"); if (el) el.textContent = message; };
  const selected = () => state.orders.find(order => String(order.order_id) === document.getElementById("trackingOrderSelect")?.value);
  function point(lat, lon) { return [Number(lat), Number(lon)]; }
  function marker(name, coords, emoji, label) {
    if (state.markers[name]) state.markers[name].setLatLng(coords);
    else state.markers[name] = L.marker(coords, { icon: L.divIcon({ className: "partner-map-icon", html: `<span aria-label="${label}">${emoji}</span>`, iconSize: [34, 34] }) }).addTo(state.map).bindPopup(label);
    return state.markers[name];
  }
  async function showRoute(from, to) {
    if (state.route) state.map.removeLayer(state.route);
    try {
      const response = await fetch(`https://router.project-osrm.org/route/v1/driving/${from[1]},${from[0]};${to[1]},${to[0]}?overview=full&geometries=geojson`);
      if (!response.ok) throw new Error("Routing service unavailable");
      const result = await response.json();
      if (!result.routes?.length) throw new Error("No route found");
      state.route = L.geoJSON(result.routes[0].geometry, { style: { color: "#f97316", weight: 5, opacity: .8 } }).addTo(state.map);
      state.map.fitBounds(state.route.getBounds(), { padding: [24, 24] });
    } catch (error) { status(`Map is ready; route could not be loaded: ${error.message}`); }
  }
  function closeConnection() {
    if (state.watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(state.watchId);
    state.watchId = null;
    if (state.simulation) clearInterval(state.simulation);
    state.simulation = null;
    if (state.socket) state.socket.close();
    state.socket = null;
    ["startPartnerGps", "simulatePartnerGps", "stopPartnerGps"].forEach(id => { const button = document.getElementById(id); if (button) button.disabled = true; });
  }
  function sendLocation(lat, lon) {
    if (!state.socket || state.socket.readyState !== WebSocket.OPEN) { status("Connect to an assigned order before sharing location."); return; }
    const coords = point(lat, lon);
    state.socket.send(JSON.stringify({ lat: coords[0], lon: coords[1] }));
    marker("rider", coords, "🛵", "Your location");
    const drop = point(state.order.delivery_lat, state.order.delivery_lon);
    showRoute(coords, drop);
    status(`Sharing live location: ${coords[0].toFixed(5)}, ${coords[1].toFixed(5)}`);
  }
  function connect(order) {
    closeConnection();
    state.order = order;
    const pickup = point(order.restaurant_lat, order.restaurant_lon), drop = point(order.delivery_lat, order.delivery_lon);
    marker("restaurant", pickup, "🍽️", "Restaurant pickup");
    marker("customer", drop, "🏠", "Customer delivery address");
    state.map.fitBounds([pickup, drop], { padding: [24, 24] });
    showRoute(pickup, drop);
    if (!token()) { status("Please sign in again to share delivery location."); return; }
    const scheme = location.protocol === "https:" ? "wss:" : "ws:";
    state.socket = new WebSocket(`${scheme}//${location.host}/ws/delivery/${order.order_id}?token=${encodeURIComponent(token())}`);
    state.socket.onopen = () => {
      status(`Connected to order #${order.order_number}. Choose GPS or simulation.`);
      ["startPartnerGps", "simulatePartnerGps", "stopPartnerGps"].forEach(id => { document.getElementById(id).disabled = false; });
    };
    state.socket.onclose = () => status("Tracking connection closed.");
    state.socket.onerror = () => status("Could not connect to tracking. Check that this order is assigned to your account.");
  }
  function setOrders(orders) {
    state.orders = orders || [];
    if (!state.map) { status("The map library could not load. Check your internet connection and reload."); return; }
    const select = document.getElementById("trackingOrderSelect");
    if (!select) return;
    const previous = select.value;
    select.innerHTML = state.orders.length ? state.orders.map(order => `<option value="${order.order_id}">#${order.order_number} · ${order.status.replaceAll("_", " ")}</option>`).join("") : '<option value="">No assigned orders</option>';
    if (!state.orders.length) { closeConnection(); state.order = null; status("No assigned orders are available to track."); return; }
    select.value = state.orders.some(order => String(order.order_id) === previous) ? previous : String(state.orders[0].order_id);
    connect(selected());
  }
  function initialize() {
    const node = document.getElementById("partnerMap");
    if (!node || state.map) return;
    if (!window.L) { status("The map library could not load. Check your internet connection and reload."); return; }
    state.map = L.map(node).setView([12.9716, 77.5946], 13);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(state.map);
    document.getElementById("trackingOrderSelect").addEventListener("change", () => { const order = selected(); if (order) connect(order); });
    document.getElementById("startPartnerGps").addEventListener("click", () => {
      if (!navigator.geolocation) { status("This browser does not provide geolocation."); return; }
      if (state.simulation) clearInterval(state.simulation);
      state.simulation = null;
      state.watchId = navigator.geolocation.watchPosition(position => sendLocation(position.coords.latitude, position.coords.longitude), error => status(`Location error: ${error.message}`), { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 });
      status("Waiting for a GPS location. Allow location access when your browser asks.");
    });
    document.getElementById("simulatePartnerGps").addEventListener("click", () => {
      if (!state.order) return;
      if (state.watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(state.watchId);
      state.watchId = null;
      if (state.simulation) clearInterval(state.simulation);
      const start = point(state.order.restaurant_lat, state.order.restaurant_lon), end = point(state.order.delivery_lat, state.order.delivery_lon);
      let step = 0;
      state.simulation = setInterval(() => {
        step = (step + 1) % 21;
        const fraction = step / 20;
        sendLocation(start[0] + (end[0] - start[0]) * fraction, start[1] + (end[1] - start[1]) * fraction);
      }, 1500);
    });
    document.getElementById("stopPartnerGps").addEventListener("click", () => {
      if (state.watchId !== null && navigator.geolocation) navigator.geolocation.clearWatch(state.watchId);
      state.watchId = null;
      if (state.simulation) clearInterval(state.simulation);
      state.simulation = null;
      status("Location sharing stopped. You can start it again while connected.");
    });
    window.addEventListener("beforeunload", closeConnection);
  }
  return { initialize, setOrders };
})();
