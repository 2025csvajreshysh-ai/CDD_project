/** Restaurant menu filters, suitability cues, and add-to-cart actions. */
const RestaurantMenu = {
  restaurantId: null,
  restaurant: null,
  items: [],
  selectedCategory: "",

  init() {
    const value = Number(new URLSearchParams(window.location.search).get("id"));
    this.restaurantId = Number.isInteger(value) && value > 0 ? value : 1;
    document.getElementById("menuItemSearch").addEventListener("input", () => this.render());
    document.getElementById("dietaryFilter").addEventListener("change", () => this.render());
    document.getElementById("allergenFilter").addEventListener("input", () => this.render());
    document.getElementById("safetyFilter").addEventListener("change", () => this.render());
    document.getElementById("vegFilterSwitch").addEventListener("change", () => this.render());
    document.getElementById("categoryTabs").addEventListener("click", event => {
      const button = event.target.closest("[data-category]");
      if (!button) return;
      this.selectedCategory = button.dataset.category;
      document.querySelectorAll("#categoryTabs [data-category]").forEach(tab => {
        tab.setAttribute("aria-pressed", String(tab === button));
        tab.classList.toggle("active", tab === button);
        tab.classList.toggle("btn-dark", tab === button);
      });
      this.render();
    });
    document.getElementById("menuItemsGrid").addEventListener("click", event => {
      const button = event.target.closest("[data-add-item]");
      if (button) Cart.addItem(Number(button.dataset.addItem), 1);
    });
    this.load();
  },

  async load() {
    const hero = document.getElementById("restaurantHero");
    const grid = document.getElementById("menuItemsGrid");
    try {
      const data = await API.getRestaurantDetails(this.restaurantId);
      this.restaurant = data.restaurant;
      this.items = Array.isArray(data.menu_items) ? data.menu_items : [];
      this.renderHero();
      this.renderCategories();
      this.render();
    } catch (error) {
      UI.setError(hero, error, "");
      UI.setError(grid, error, "");
    }
  },

  renderHero() {
    const restaurant = this.restaurant;
    const image = UI.imageUrl(restaurant.image_url);
    document.getElementById("restaurantHero").innerHTML = `
      <div class="container py-4 py-lg-5">
        <nav aria-label="Breadcrumb"><ol class="breadcrumb mb-4">
          <li class="breadcrumb-item"><a href="/">Home</a></li>
          <li class="breadcrumb-item"><a href="/pages/restaurants.html">Restaurants</a></li>
          <li class="breadcrumb-item active" aria-current="page">${UI.escapeHtml(restaurant.name)}</li>
        </ol></nav>
        <div class="row align-items-center gy-4">
          <div class="col-md-8">
            <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
              <h1 class="display-6 fw-bold mb-0" id="restaurantName">${UI.escapeHtml(restaurant.name)}</h1>
              ${restaurant.is_pure_veg ? '<span class="badge bg-success rounded-pill">Pure vegetarian kitchen</span>' : ""}
            </div>
            <p class="text-secondary mb-2">${UI.escapeHtml(restaurant.cuisine_type)} · ${UI.escapeHtml(restaurant.address)}, ${UI.escapeHtml(restaurant.city)}</p>
            <p class="small text-light opacity-75 restaurant-description">${UI.escapeHtml(restaurant.description)}</p>
            <div class="d-flex flex-wrap gap-3 align-items-center">
              <span class="badge-rating"><i class="bi bi-star-fill text-warning me-1" aria-hidden="true"></i>${Number(restaurant.rating || 0).toFixed(1)} (${Number(restaurant.total_reviews || 0)} ratings)</span>
              <span class="small"><i class="bi bi-clock me-1 text-warning" aria-hidden="true"></i>${Number(restaurant.delivery_time_mins || 0)} min delivery</span>
              <span class="small">${UI.currency(restaurant.cost_for_two)} for two</span>
            </div>
          </div>
          <div class="col-md-4 text-md-end">${image ? `<img src="${UI.escapeHtml(image)}" alt="${UI.escapeHtml(restaurant.name)}" class="restaurant-hero-image">` : ""}</div>
        </div>
      </div>`;
  },

  renderCategories() {
    const categories = [...new Set(this.items.map(item => item.category?.name).filter(Boolean))].sort((a, b) => a.localeCompare(b));
    const tabs = [{ name: "All dishes", value: "" }, ...categories.map(name => ({ name, value: name }))];
    document.getElementById("categoryTabs").innerHTML = tabs.map((tab, index) => `
      <button class="btn btn-sm btn-light text-start fw-semibold ${index === 0 ? "active btn-dark" : ""}" type="button" data-category="${UI.escapeHtml(tab.value)}" aria-pressed="${index === 0}">${UI.escapeHtml(tab.name)}</button>
    `).join("");
  },

  suitability(item, dietaryChoice, allergyTerms) {
    const details = `${item.allergens || ""} ${item.ingredients || ""}`.toLocaleLowerCase();
    const tags = String(item.dietary_tags || "").toLocaleLowerCase().replaceAll("-", " ");
    const hasDeclaredAllergenInfo = Boolean(String(item.allergens || "").trim());
    const hasDietaryTag = preference => new RegExp(`(^|[^a-z])${preference}([^a-z]|$)`, "i").test(tags);
    const matchedAllergens = allergyTerms.filter(term => {
      const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`, "i").test(details);
    });

    let unsuitableReason = "";
    let needsConfirmation = false;
    if (dietaryChoice === "vegetarian" && !item.is_veg) unsuitableReason = "Contains non-vegetarian ingredients";
    if (["vegan", "jain"].includes(dietaryChoice)) {
      if (!item.is_veg) unsuitableReason = "Does not match the selected dietary preference";
      else if (!hasDietaryTag(dietaryChoice)) needsConfirmation = true;
    }
    if (matchedAllergens.length) unsuitableReason = `Menu lists ${matchedAllergens.join(", ")}`;
    if (allergyTerms.length && !hasDeclaredAllergenInfo) needsConfirmation = true;

    if (unsuitableReason) return { state: "unsuitable", label: "Unsuitable", detail: unsuitableReason };
    if (needsConfirmation) return { state: "some-options", label: "Some options", detail: "Confirm ingredients with the restaurant" };
    if (!dietaryChoice && allergyTerms.length === 0) return { state: "some-options", label: "Some options", detail: "Set dietary and allergy preferences to assess this item" };
    return { state: "suitable", label: "Suitable", detail: "No conflict found in the listed menu information" };
  },

  render() {
    const search = document.getElementById("menuItemSearch").value.trim().toLocaleLowerCase();
    const selectedDietaryChoice = document.getElementById("dietaryFilter").value;
    const dietaryChoice = selectedDietaryChoice === "any" ? "" : selectedDietaryChoice;
    const allergyTerms = document.getElementById("allergenFilter").value
      .split(/[,;|]/).map(term => term.trim().toLocaleLowerCase()).filter(Boolean);
    const safetyFilter = document.getElementById("safetyFilter").value;
    const vegetarianOnly = document.getElementById("vegFilterSwitch").checked;

    const filtered = this.items.filter(item => {
      const matchSearch = !search || [item.name, item.description, item.ingredients, item.category?.name]
        .some(value => String(value || "").toLocaleLowerCase().includes(search));
      const matchCategory = !this.selectedCategory || item.category?.name === this.selectedCategory;
      const suitability = this.suitability(item, dietaryChoice, allergyTerms);
      const matchSafety = safetyFilter === "all"
        || (safetyFilter === "hide-unsuitable" && suitability.state !== "unsuitable")
        || suitability.state === safetyFilter;
      return matchSearch && matchCategory && matchSafety && (!vegetarianOnly || item.is_veg);
    });

    document.getElementById("menuCount").textContent = `${filtered.length} of ${this.items.length} dishes`;
    const grid = document.getElementById("menuItemsGrid");
    UI.clearBusy(grid);
    if (!filtered.length) {
      UI.setEmpty(grid, "No dishes match these filters", "Try changing your search or dietary settings.");
      return;
    }

    grid.innerHTML = filtered.map(item => {
      const status = this.suitability(item, dietaryChoice, allergyTerms);
      const image = UI.imageUrl(item.image_url);
      const price = Number(item.discount_price || item.price || 0);
      const description = item.description || "Freshly prepared by the restaurant kitchen.";
      return `
        <div class="col-md-6">
          <article class="card menu-item-card h-100 border-0 shadow-sm rounded-4 p-3 bg-white">
            <div class="d-flex gap-3">
              <div class="menu-item-detail flex-grow-1">
                <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
                  <span class="${item.is_veg ? "veg-indicator" : "nonveg-indicator"}" aria-label="${item.is_veg ? "Vegetarian" : "Non-vegetarian"}"></span>
                  ${item.is_bestseller ? '<span class="badge bg-danger rounded-pill">Bestseller</span>' : ""}
                  <span class="small text-muted"><i class="bi bi-clock me-1" aria-hidden="true"></i>${Number(item.prep_time_minutes || 0)} min</span>
                </div>
                <div class="d-flex flex-wrap align-items-center gap-2 mb-2">
                  <h2 class="h6 fw-bold mb-0">${UI.escapeHtml(item.name)}</h2>
                  <span class="food-safety-pill is-${status.state}" title="${UI.escapeHtml(status.detail)}">${UI.escapeHtml(status.label)}</span>
                </div>
                <p class="small text-muted mb-2 menu-item-description">${UI.escapeHtml(description)}</p>
                <div class="menu-item-meta text-secondary"><strong>Ingredients:</strong> ${UI.escapeHtml(item.ingredients || "Not listed")}</div>
                <div class="menu-item-meta text-danger mt-1"><strong>Declared allergens:</strong> ${UI.escapeHtml(item.allergens || "Not listed")}</div>
                <div class="d-flex justify-content-between align-items-center mt-3">
                  <span class="brand-orange fw-bold">${UI.currency(price)}${item.discount_price ? `<span class="text-muted text-decoration-line-through small ms-1">${UI.currency(item.price)}</span>` : ""}</span>
                  <button class="btn btn-sm btn-primary-orange" type="button" data-add-item="${Number(item.id)}" aria-label="Add ${UI.escapeHtml(item.name)} to cart">Add to cart</button>
                </div>
              </div>
              ${image ? `<img src="${UI.escapeHtml(image)}" alt="${UI.escapeHtml(item.name)}" class="menu-item-image rounded-3" loading="lazy">` : ""}
            </div>
          </article>
        </div>`;
    }).join("");
  }
};

document.addEventListener("DOMContentLoaded", () => RestaurantMenu.init());
