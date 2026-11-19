/* Leaflet live order tracking. Load Leaflet 1.9.x before this script. */
(() => {
  const qs = new URLSearchParams(location.search);
  const orderId = Number(qs.get("order_id"));
  const token = localStorage.getItem("aifoodie_token");
  const mapNode = document.getElementById("trackingMap");
  if (!mapNode || !orderId || !token || !window.L) return;
  const map = L.map(mapNode).setView([12.9716, 77.5946], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap contributors" }).addTo(map);
  const restaurantIcon = L.divIcon({ className: "tracking-pin restaurant-pin", html: "🍽️", iconSize: [32, 32] });
  const customerIcon = L.divIcon({ className: "tracking-pin customer-pin", html: "🏠", iconSize: [32, 32] });
  const riderIcon = L.divIcon({ className: "tracking-pin rider-pin", html: "🛵", iconSize: [36, 36] });
  let rider, route;
  const setMarker = (marker, coords, icon, title) => marker ? marker.setLatLng(coords) : L.marker(coords, { icon, title }).addTo(map);
  async function routeToCustomer(start, end) {
    if (route) map.removeLayer(route);
    try {
      const url = `https://router.project-osrm.org/route/v1/driving/${start[1]},${start[0]};${end[1]},${end[0]}?overview=full&geometries=geojson`;
      const response = await fetch(url);
      if (!response.ok) throw new Error("OSRM unavailable");
      const data = await response.json();
      if (!data.routes?.length) throw new Error("No route found");
      route = L.geoJSON(data.routes[0].geometry, { style: { color: "#f97316", weight: 5, opacity: .8 } }).addTo(map);
      map.fitBounds(route.getBounds(), { padding: [32, 32] });
    } catch (error) { console.warn("Route could not be loaded", error); }
  }
  async function initialize() {
    const res = await fetch(`/api/delivery/orders/${orderId}/location`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error("Could not load order locations");
    const data = await res.json();
    const rest = [data.restaurant.lat, data.restaurant.lon], customer = [data.customer.lat, data.customer.lon];
    L.marker(rest, { icon: restaurantIcon }).addTo(map).bindPopup("Restaurant");
    L.marker(customer, { icon: customerIcon }).addTo(map).bindPopup("Delivery address");
    if (data.partner) { rider = setMarker(rider, [data.partner.lat, data.partner.lon], riderIcon, "Delivery partner"); await routeToCustomer([data.partner.lat, data.partner.lon], customer); }
    else await routeToCustomer(rest, customer);
  }
  initialize().catch(error => { const status = document.getElementById("trackingStatus"); if (status) status.textContent = error.message; });
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${location.host}/ws/delivery/${orderId}?token=${encodeURIComponent(token)}`);
  socket.addEventListener("open", () => { const status = document.getElementById("trackingStatus"); if (status) status.textContent = "Live location connected"; });
  socket.addEventListener("message", async event => {
    const data = JSON.parse(event.data);
    if (data.type !== "location") return;
    const point = [data.lat, data.lon];
    rider = setMarker(rider, point, riderIcon, "Delivery partner");
    const customer = await fetch(`/api/delivery/orders/${orderId}/location`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json());
    await routeToCustomer(point, [customer.customer.lat, customer.customer.lon]);
  });
})();
