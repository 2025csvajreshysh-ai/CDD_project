/** Home page data loading and delegated interactions. */

document.addEventListener("DOMContentLoaded", () => {
  loadCategories();
  loadRestaurants();
  loadPersonalizedMenu();
  loadBestsellers();
});

function safeNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function safeId(value) {
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : 0;
}

function foodCard(item, badge = "") {
  const id = safeId(item.id);
  const name = UI.escapeHtml(item.name || "Menu item");
  const description = UI.escapeHtml(item.description || "Freshly prepared by our restaurant partner.");
  const price = safeNumber(item.price);
  const salePrice = safeNumber(item.discount_price, 0);
  const finalPrice = salePrice > 0 ? salePrice : price;
  const image = UI.imageUrl(item.image_url) || "/static/assets/food-placeholder.svg";
  return `
    <div class="col-lg-3 col-md-6">
      <article class="card food-card h-100">
        <div class="food-card-img-wrap">
          <img src="${image}" alt="${name}" class="food-card-img" loading="lazy">
          ${badge}
        </div>
        <div class="p-3 d-flex flex-column flex-grow-1">
          <div class="d-flex align-items-center gap-2 mb-1">
            <span class="${item.is_veg ? "veg-indicator" : "nonveg-indicator"}" aria-label="${item.is_veg ? "Vegetarian" : "Non-vegetarian"}"></span>
            <h3 class="h6 fw-bold mb-0 text-truncate">${name}</h3>
          </div>
          <p class="small text-muted mb-2 menu-item-description home-menu-description">${description}</p>
          <div class="d-flex justify-content-between align-items-center mt-auto pt-2">
            <div class="fw-bold brand-orange fs-5">
              ${UI.currency(finalPrice)}
              ${salePrice > 0 ? `<span class="text-muted text-decoration-line-through small fs-6 ms-1">${UI.currency(price)}</span>` : ""}
            </div>
            ${id ? `<button class="btn btn-primary-orange btn-sm" type="button" data-add-item="${id}">+ Add to Cart</button>` : ""}
          </div>
        </div>
      </article>
    </div>`;
}

async function loadCategories() {
  const container = document.getElementById("categoriesList");
  if (!container) return;
  UI.setLoading(container, "Loading food categories…");
  try {
    const categories = await API.getCategories();
    if (!Array.isArray(categories) || categories.length === 0) {
      UI.setEmpty(container, "No categories yet", "Restaurant categories will appear here.");
      return;
    }
    container.innerHTML = categories.map(category => {
      const name = UI.escapeHtml(category.name || "Other");
      const icon = UI.escapeHtml(category.icon_emoji || "🍽️");
      return `<a href="/pages/restaurants.html?category=${encodeURIComponent(category.name || "")}" class="category-pill text-decoration-none"><span class="fs-5" aria-hidden="true">${icon}</span><span>${name}</span></a>`;
    }).join("");
    UI.clearBusy(container);
  } catch (error) {
    UI.setError(container, error);
  }
}

async function loadRestaurants() {
  const container = document.getElementById("recommendedRestaurantsList");
  if (!container) return;
  UI.setLoading(container, "Finding restaurants near you…");
  try {
    const restaurants = await API.getRestaurants();
    if (!Array.isArray(restaurants) || restaurants.length === 0) {
      UI.setEmpty(container, "No restaurants available", "Please check back soon.");
      return;
    }
    container.innerHTML = restaurants.slice(0, 8).map(restaurant => {
      const id = safeId(restaurant.id);
      const name = UI.escapeHtml(restaurant.name || "Restaurant");
      const cuisine = UI.escapeHtml(restaurant.cuisine_type || "Mixed cuisine");
      const image = UI.imageUrl(restaurant.image_url) || "/static/assets/restaurant-placeholder.svg";
      const rating = safeNumber(restaurant.rating).toFixed(1);
      const deliveryTime = Math.max(0, safeNumber(restaurant.delivery_time_mins));
      return `
        <div class="col-lg-3 col-md-6">
          <article class="card food-card h-100">
            <div class="food-card-img-wrap">
              <img src="${image}" alt="${name}" class="food-card-img" loading="lazy">
              ${restaurant.is_pure_veg ? '<span class="badge bg-success position-absolute top-0 end-0 m-2 rounded-pill">100% Pure Veg</span>' : ""}
            </div>
            <div class="p-3 d-flex flex-column flex-grow-1">
              <div class="d-flex justify-content-between align-items-start mb-1">
                <h3 class="h5 fw-bold mb-0 text-truncate">${name}</h3>
                <span class="badge-rating"><i class="bi bi-star-fill text-warning me-1" aria-hidden="true"></i>${rating}</span>
              </div>
              <div class="small text-muted mb-2 text-truncate">${cuisine}</div>
              <div class="d-flex justify-content-between align-items-center small text-secondary mt-auto pt-2 border-top">
                <span><i class="bi bi-clock me-1" aria-hidden="true"></i>${deliveryTime} mins</span>
                <span>${UI.currency(restaurant.cost_for_two)} for two</span>
              </div>
              ${id ? `<a href="/pages/restaurant-details.html?id=${id}" class="btn btn-outline-orange btn-sm mt-3 w-100">View Menu</a>` : ""}
            </div>
          </article>
        </div>`;
    }).join("");
    UI.clearBusy(container);
  } catch (error) {
    UI.setError(container, error);
  }
}

async function loadPersonalizedMenu() {
  const container = document.getElementById("aiRecommendationsList");
  if (!container) return;
  UI.setLoading(container, "Personalizing your menu…");
  try {
    const items = await API.getRecommendations(null, null, 4);
    if (!Array.isArray(items) || items.length === 0) {
      UI.setEmpty(container, "No recommendations yet", "Explore a few dishes and we’ll have better suggestions for you.");
      return;
    }
    const badge = '<span class="badge bg-dark position-absolute top-0 start-0 m-2 rounded-pill"><i class="bi bi-magic me-1 text-warning" aria-hidden="true"></i>AI Match</span>';
    container.innerHTML = items.map(item => foodCard(item, badge)).join("");
    UI.clearBusy(container);
  } catch (error) {
    UI.setError(container, error);
  }
}

async function loadBestsellers() {
  const container = document.getElementById("bestsellersList");
  if (!container) return;
  UI.setLoading(container, "Loading popular dishes…");
  try {
    const items = await API.getMenuItems({ bestseller_only: true });
    const displayItems = Array.isArray(items) ? items.slice(0, 8) : [];
    if (displayItems.length === 0) {
      UI.setEmpty(container, "Popular dishes will appear here", "Our restaurant partners are adding their menus.");
      return;
    }
    const badge = '<span class="badge bg-danger position-absolute top-0 end-0 m-2 rounded-pill">Bestseller</span>';
    container.innerHTML = displayItems.map(item => foodCard(item, badge)).join("");
    UI.clearBusy(container);
  } catch (error) {
    UI.setError(container, error);
  }
}

function handleHeroSearch() {
  const input = document.getElementById("heroSearchInput");
  const term = input?.value.trim() || "";
  if (term) window.location.href = `/pages/restaurants.html?search=${encodeURIComponent(term)}`;
  else input?.focus();
}

async function copyCoupon(code) {
  try {
    await navigator.clipboard.writeText(code);
    Auth.showToast(`Coupon code ${code} copied!`, "success");
  } catch {
    Auth.showToast("Clipboard access is unavailable. Please copy the code manually.", "warning");
  }
}

document.addEventListener("click", event => {
  const cuisineChip = event.target.closest("[data-cuisine-search]");
  if (cuisineChip) {
    const cuisine = cuisineChip.dataset.cuisineSearch || "";
    window.location.href = `/pages/restaurants.html?cuisine=${encodeURIComponent(cuisine)}`;
    return;
  }
  if (event.target.closest("[data-pure-veg-search]")) {
    window.location.href = "/pages/restaurants.html?pure_veg=true";
    return;
  }

  const addButton = event.target.closest("[data-add-item]");
  if (addButton) {
    const itemId = safeId(addButton.dataset.addItem);
    if (itemId) Cart.addItem(itemId, 1);
    return;
  }

  const demoButton = event.target.closest("[data-demo-role]");
  if (demoButton) {
    Auth.executeDemoLogin(demoButton.dataset.demoRole);
    return;
  }

  const action = event.target.closest("[data-action]");
  if (!action) return;
  if (action.dataset.action === "hero-search") handleHeroSearch();
  if (action.dataset.action === "open-assistant") Chatbot.sendQuickMessage(action.dataset.prompt || "");
  if (action.dataset.action === "load-recommendations") loadPersonalizedMenu();
  if (action.dataset.action === "copy-coupon") copyCoupon(action.dataset.coupon || "");
});

document.addEventListener("keydown", event => {
  if (event.key === "Enter" && event.target.id === "heroSearchInput") handleHeroSearch();
});

document.addEventListener("submit", event => {
  if (event.target.matches('[data-form="newsletter"]')) {
    event.preventDefault();
    Auth.showToast("Thank you for subscribing! Check your email for special welcome offers.", "success");
    event.target.reset();
  }
});

document.addEventListener("click", event => {
  if (!event.target.closest("[data-ui-retry]")) return;
  const container = event.target.closest("[aria-busy]") || event.target.closest("#categoriesList, #recommendedRestaurantsList, #aiRecommendationsList, #bestsellersList");
  if (!container) return;
  ({
    categoriesList: loadCategories,
    recommendedRestaurantsList: loadRestaurants,
    aiRecommendationsList: loadPersonalizedMenu,
    bestsellersList: loadBestsellers
  })[container.id]?.();
});
