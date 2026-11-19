/**
 * AI Foodie - Authentication & Role Redirection Logic
 */

const Auth = {
  // Role destination paths
  rolePaths: {
    customer: "/pages/customer-dashboard.html",
    restaurant_admin: "/pages/admin-dashboard.html",
    kitchen_staff: "/pages/kitchen-dashboard.html",
    delivery_partner: "/pages/delivery-dashboard.html",
    super_admin: "/pages/superadmin-dashboard.html"
  },

  // Perform demo login for a given role
  async executeDemoLogin(role) {
    try {
      this.showToast(`Authenticating demo ${role.replace('_', ' ')}...`, "info");
      const resp = await API.demoLogin(role);
      API.setToken(resp.access_token);
      API.setUser({
        id: resp.user_id,
        email: resp.email,
        full_name: resp.full_name,
        role: resp.role
      });
      this.showToast(`Welcome ${resp.full_name}!`, "success");
      
      setTimeout(() => {
        const dest = this.rolePaths[resp.role] || "/";
        window.location.href = dest;
      }, 700);
    } catch (err) {
      this.showToast(err.message || "Failed to demo login", "danger");
    }
  },

  // Standard login
  async executeLogin(email, password) {
    try {
      const resp = await API.login(email, password);
      API.setToken(resp.access_token);
      API.setUser({
        id: resp.user_id,
        email: resp.email,
        full_name: resp.full_name,
        role: resp.role
      });
      this.showToast(`Logged in successfully as ${resp.full_name}`, "success");
      
      setTimeout(() => {
        const dest = this.rolePaths[resp.role] || "/";
        window.location.href = dest;
      }, 600);
    } catch (err) {
      this.showToast(err.message || "Invalid credentials", "danger");
    }
  },

  // Ensure user is authenticated and authorized for dashboard
  checkAuthGuard(allowedRoles = []) {
    const user = API.getUser();
    const token = API.getToken();

    if (!user || !token) {
      window.location.href = "/pages/login.html?redirect=" + encodeURIComponent(window.location.pathname);
      return false;
    }

    if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
      alert(`Access Restricted: This dashboard requires role in ${allowedRoles.join(', ')}.`);
      window.location.href = this.rolePaths[user.role] || "/";
      return false;
    }
    return true;
  },

  // Update navbar based on login status
  updateNavbarAuth() {
    const user = API.getUser();
    const navAuthContainer = document.getElementById("navAuthContainer");
    if (!navAuthContainer) return;
    navAuthContainer.replaceChildren();

    if (user) {
      const dashboardHref = this.rolePaths[user.role] || "/pages/customer-dashboard.html";
      const dropdown = document.createElement("div");
      dropdown.className = "dropdown";
      const toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "btn btn-outline-dark dropdown-toggle d-flex align-items-center gap-2";
      toggle.dataset.bsToggle = "dropdown";
      toggle.setAttribute("aria-expanded", "false");
      const roleBadge = document.createElement("span");
      roleBadge.className = "badge bg-brand-orange text-white rounded-pill px-2 py-1 text-uppercase role-badge";
      roleBadge.textContent = String(user.role || "customer").replaceAll("_", " ");
      const name = document.createElement("span");
      name.className = "fw-semibold text-truncate nav-user-name";
      name.textContent = String(user.full_name || "Account").trim().split(/\s+/)[0];
      toggle.append(roleBadge, name);

      const menu = document.createElement("ul");
      menu.className = "dropdown-menu dropdown-menu-end shadow-sm";
      const emailRow = document.createElement("li");
      const email = document.createElement("h6");
      email.className = "dropdown-header";
      email.textContent = user.email || "";
      emailRow.appendChild(email);
      menu.appendChild(emailRow);
      menu.append(this.createMenuLink(dashboardHref, "bi-speedometer2", "My Dashboard"));
      menu.append(this.createMenuLink("/pages/cart.html", "bi-cart3", "Cart & Checkout"));
      const divider = document.createElement("li");
      divider.innerHTML = '<hr class="dropdown-divider">';
      menu.appendChild(divider);
      const logoutRow = document.createElement("li");
      const logoutButton = document.createElement("button");
      logoutButton.type = "button";
      logoutButton.className = "dropdown-item text-danger";
      logoutButton.innerHTML = '<i class="bi bi-box-arrow-right me-2" aria-hidden="true"></i>Logout';
      logoutButton.addEventListener("click", () => API.logout());
      logoutRow.appendChild(logoutButton);
      menu.appendChild(logoutRow);
      dropdown.append(toggle, menu);
      navAuthContainer.appendChild(dropdown);
    } else {
      const links = document.createElement("div");
      links.className = "d-flex align-items-center gap-2";
      const login = document.createElement("a");
      login.href = "/pages/login.html";
      login.className = "btn btn-outline-orange btn-sm";
      login.textContent = "Login";
      const signup = document.createElement("a");
      signup.href = "/pages/register.html";
      signup.className = "btn btn-primary-orange btn-sm";
      signup.textContent = "Sign up";
      links.append(login, signup);
      navAuthContainer.appendChild(links);
    }
  },

  createMenuLink(href, iconClass, label) {
    const row = document.createElement("li");
    const link = document.createElement("a");
    link.href = href;
    link.className = "dropdown-item";
    const icon = document.createElement("i");
    icon.className = `bi ${iconClass} me-2`;
    icon.setAttribute("aria-hidden", "true");
    link.append(icon, document.createTextNode(label));
    row.appendChild(link);
    return row;
  },

  // Toast notification helper
  showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container position-fixed top-0 end-0 p-3";
      document.body.appendChild(container);
    }

    const colorClass = {
      success: "bg-success text-white",
      danger: "bg-danger text-white",
      warning: "bg-warning text-dark",
      info: "bg-dark text-white",
    }[type] || "bg-dark text-white";
    const toastEl = document.createElement("div");
    toastEl.className = `toast align-items-center ${colorClass} border-0 shadow-lg`;
    toastEl.setAttribute("role", "status");
    toastEl.setAttribute("aria-live", "polite");
    toastEl.setAttribute("aria-atomic", "true");
    const row = document.createElement("div");
    row.className = "d-flex";
    const body = document.createElement("div");
    body.className = "toast-body fw-semibold";
    body.textContent = String(message ?? "");
    const close = document.createElement("button");
    close.type = "button";
    close.className = "btn-close btn-close-white me-2 m-auto";
    close.setAttribute("aria-label", "Close notification");
    close.dataset.bsDismiss = "toast";
    row.append(body, close);
    toastEl.appendChild(row);
    container.appendChild(toastEl);
    if (window.bootstrap) {
      const bsToast = new bootstrap.Toast(toastEl, { delay: 3500 });
      bsToast.show();
      toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove(), { once: true });
    }
  }
};

document.addEventListener("DOMContentLoaded", () => {
  Auth.updateNavbarAuth();
});
