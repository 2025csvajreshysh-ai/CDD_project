/** Restaurant discovery filters, rendering, and navigation state. */
const RestaurantDiscovery = {
  state: { search: "", cuisine: "", pureVeg: false, requestId: 0 },

  init() {
    const params = new URLSearchParams(window.location.search);
    this.state.search = params.get("search") || "";
    this.state.cuisine = params.get("category") || params.get("cuisine") || "";
    this.state.pureVeg = params.get("pure_veg") === "true";

    const searchInput = document.getElementById("restaurantSearchInput");
    const vegSwitch = document.getElementById("pureVegSwitch");
    searchInput.value = this.state.search;
    vegSwitch.checked = this.state.pureVeg;

    searchInput.addEventListener("input", this.debounce(() => {
      this.state.search = searchInput.value.trim();
      this.syncUrl();
      this.fetchRestaurants();
    }, 250));
    vegSwitch.addEventListener("change", () => {
      this.state.pureVeg = vegSwitch.checked;
      this.syncUrl();
      this.fetchRestaurants();
    });
    document.getElementById("cuisineFilters").addEventListener("click", event => {
      const button = event.target.closest("[data-cuisine]");
      if (!button) return;
      this.state.cuisine = button.dataset.cuisine || "";
      this.updateCuisineButtons();
      this.syncUrl();
      this.fetchRestaurants();
    });
    document.getElementById("clearRestaurantFilters").addEventListener("click", () => this.clearFilters());
    document.getElementById("restaurantsContainer").addEventListener("click", event => {
      if (event.target.closest("[data-ui-retry]")) this.fetchRestaurants();
      if (event.target.closest("[data-clear-filters]")) this.clearFilters();
    });

    this.updateCuisineButtons();
    this.syncClearButton();
    this.fetchRestaurants();
  },

  debounce(callback, delay) {
    let timeoutId;
    return (...args) => {
      window.clearTimeout(timeoutId);
      timeoutId = window.setTimeout(() => callback(...args), delay);
    };
  },

  updateCuisineButtons() {
    document.querySelectorAll("#cuisineFilters [data-cuisine]").forEach(button => {
      const selected = button.dataset.cuisine === this.state.cuisine;
      button.classList.toggle("active", selected);
      button.classList.toggle("btn-dark", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  },

  syncClearButton() {
    const hasFilters = Boolean(this.state.search || this.state.cuisine || this.state.pureVeg);
    document.getElementById("clearRestaurantFilters").hidden = !hasFilters;
  },

  syncUrl() {
    const params = new URLSearchParams();
    if (this.state.search) params.set("search", this.state.search);
    if (this.state.cuisine) params.set("cuisine", this.state.cuisine);
    if (this.state.pureVeg) params.set("pure_veg", "true");
    const query = params.toString();
    window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    this.syncClearButton();
  },

  clearFilters() {
    this.state.search = "";
    this.state.cuisine = "";
    this.state.pureVeg = false;
    document.getElementById("restaurantSearchInput").value = "";
    document.getElementById("pureVegSwitch").checked = false;
    this.updateCuisineButtons();
    this.syncUrl();
    this.fetchRestaurants();
  },

  async fetchRestaurants() {
    const container = document.getElementById("restaurantsContainer");
    const meta = document.getElementById("restaurantResultsMeta");
    const requestId = ++this.state.requestId;
    const params = {};
    if (this.state.search) params.search = this.state.search;
    if (this.state.cuisine) params.cuisine = this.state.cuisine;
    if (this.state.pureVeg) params.pure_veg = true;

    meta.textContent = "Finding restaurants…";
    UI.setLoading(container, "Finding restaurants that match your filters…");
    try {
      const restaurants = await API.getRestaurants(params);
      if (requestId !== this.state.requestId) return;
      if (!Array.isArray(restaurants) || restaurants.length === 0) {
        meta.textContent = "No matches found";
        container.removeAttribute("aria-busy");
        container.innerHTML = `
          <div class="col-12">
            <div class="restaurant-empty-state">
              <span class="restaurant-empty-icon" aria-hidden="true"><i class="bi bi-search"></i></span>
              <h2 class="h5 fw-bold mb-2">No restaurants match those filters</h2>
              <p class="text-muted mb-3">Try another search or clear the filters to see all available kitchens.</p>
              <button class="btn btn-primary-orange btn-sm" type="button" data-clear-filters>Show all restaurants</button>
            </div>
          </div>`;
        return;
      }

      meta.textContent = `${restaurants.length} ${restaurants.length === 1 ? "restaurant" : "restaurants"} found`;
      container.innerHTML = restaurants.map(restaurant => this.renderCard(restaurant)).join("");
      UI.clearBusy(container);
    } catch (error) {
      if (requestId !== this.state.requestId) return;
      meta.textContent = "Could not load restaurants";
      UI.setError(container, error, "Retry");
    }
  },

  renderCard(restaurant) {
    const id = Number(restaurant.id);
    const safeId = Number.isSafeInteger(id) && id > 0 ? id : 0;
    const name = UI.escapeHtml(restaurant.name || "Restaurant");
    const cuisine = UI.escapeHtml(restaurant.cuisine_type || "Multi-cuisine");
    const description = UI.escapeHtml(restaurant.description || "Fresh meals, prepared by a local restaurant partner.");
    const image = UI.imageUrl(restaurant.image_url) || "/static/assets/restaurant-placeholder.svg";
    const rating = Number.isFinite(Number(restaurant.rating)) ? Number(restaurant.rating).toFixed(1) : "New";
    const deliveryTime = Math.max(0, Number(restaurant.delivery_time_mins) || 0);
    return `
      <div class="col-lg-3 col-md-6">
        <article class="card food-card h-100 restaurant-result-card">
          <div class="food-card-img-wrap">
            <img src="${image}" alt="${name}" class="food-card-img" loading="lazy">
            ${restaurant.is_pure_veg ? '<span class="badge bg-success position-absolute top-0 end-0 m-2 rounded-pill">Pure vegetarian</span>' : ""}
          </div>
          <div class="p-3 d-flex flex-column flex-grow-1">
            <div class="d-flex justify-content-between align-items-start gap-2 mb-1">
              <h2 class="h5 fw-bold mb-0 text-truncate">${name}</h2>
              <span class="badge-rating" aria-label="Rating ${rating}"><i class="bi bi-star-fill text-warning me-1" aria-hidden="true"></i>${rating}</span>
            </div>
            <div class="small text-muted mb-2 text-truncate">${cuisine}</div>
            <p class="small text-muted mb-3 restaurant-card-description">${description}</p>
            <div class="d-flex justify-content-between align-items-center small text-secondary mt-auto pt-2 border-top">
              <span><i class="bi bi-clock me-1" aria-hidden="true"></i>${deliveryTime} min</span>
              <span>${UI.currency(restaurant.cost_for_two)} for two</span>
            </div>
            ${safeId ? `<a href="/pages/restaurant-details.html?id=${safeId}" class="btn btn-outline-orange btn-sm mt-3 w-100">Browse menu</a>` : ""}
          </div>
        </article>
      </div>`;
  }
};

document.addEventListener("DOMContentLoaded", () => RestaurantDiscovery.init());
