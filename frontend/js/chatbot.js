/** Accessible, database-grounded conversational ordering assistant. */
const Chatbot = {
  isOpen: false,
  isSending: false,
  history: [],

  escape(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
  },

  safeImageUrl(value) {
    try {
      const url = new URL(String(value || ""), window.location.origin);
      return ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
      return "";
    }
  },

  init() {
    if (document.getElementById("aiChatbotBubble")) return;
    const bubble = document.createElement("button");
    bubble.id = "aiChatbotBubble";
    bubble.type = "button";
    bubble.className = "chatbot-bubble";
    bubble.setAttribute("aria-label", "Open AI food assistant");
    bubble.setAttribute("aria-expanded", "false");
    bubble.innerHTML = '<i class="bi bi-robot" aria-hidden="true"></i>';

    const panel = document.createElement("section");
    panel.id = "aiChatbotWindow";
    panel.className = "chatbot-window";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "AI food assistant");
    panel.setAttribute("aria-hidden", "true");
    panel.innerHTML = `
      <header class="chatbot-header">
        <div class="d-flex align-items-center gap-2">
          <span class="chatbot-avatar"><i class="bi bi-robot" aria-hidden="true"></i></span>
          <span><strong class="d-block">AI Food Assistant</strong><small class="chatbot-subtitle">Live menu connected</small></span>
        </div>
        <button id="closeChatbotBtn" class="btn btn-sm btn-link text-white" type="button" aria-label="Close assistant"><i class="bi bi-x-lg" aria-hidden="true"></i></button>
      </header>
      <div id="chatbotMessages" class="chatbot-body" aria-live="polite" aria-relevant="additions">
        <div class="chat-msg bot">Hi! I can search the live menu, filter by dietary preference or budget, check listed ingredients, and look up your own order status.</div>
      </div>
      <div id="chatbotChips" class="chatbot-chips">
        <button class="chatbot-chip" type="button" data-chat-prompt="Suggest vegetarian food under 200 rupees">Vegetarian under ₹200</button>
        <button class="chatbot-chip" type="button" data-chat-prompt="What is popular today?">Popular today</button>
        <button class="chatbot-chip" type="button" data-chat-prompt="Show food under 150 rupees">Under ₹150</button>
        <button class="chatbot-chip" type="button" data-chat-prompt="What ingredients are in Paneer Butter Masala?">Ingredients</button>
        <button class="chatbot-chip" type="button" data-chat-prompt="What is my current order status?">My order</button>
      </div>
      <form id="chatbotForm" class="chatbot-footer">
        <label class="visually-hidden" for="chatbotInput">Ask the food assistant</label>
        <input type="text" id="chatbotInput" class="form-control rounded-pill px-3" placeholder="Ask about dishes or ingredients…" autocomplete="off" maxlength="1000">
        <button type="submit" class="chatbot-send btn btn-primary-orange rounded-circle" aria-label="Send message"><i class="bi bi-send-fill" aria-hidden="true"></i></button>
      </form>`;
    document.body.append(bubble, panel);

    bubble.addEventListener("click", () => this.toggle());
    panel.querySelector("#closeChatbotBtn").addEventListener("click", () => this.toggle(false));
    panel.addEventListener("click", event => {
      const promptButton = event.target.closest("[data-chat-prompt]");
      if (promptButton) this.sendQuickMessage(promptButton.dataset.chatPrompt);
      const addButton = event.target.closest("[data-chat-add]");
      if (addButton) Cart.addItem(Number(addButton.dataset.chatAdd), 1);
    });
    panel.querySelector("#chatbotForm").addEventListener("submit", event => {
      event.preventDefault();
      const input = panel.querySelector("#chatbotInput");
      const message = input.value.trim();
      if (!message || this.isSending) return;
      input.value = "";
      this.sendMessage(message);
    });
  },

  toggle(forceState = null) {
    const panel = document.getElementById("aiChatbotWindow");
    const bubble = document.getElementById("aiChatbotBubble");
    if (!panel || !bubble) return;
    this.isOpen = forceState === null ? !this.isOpen : Boolean(forceState);
    panel.classList.toggle("is-open", this.isOpen);
    panel.setAttribute("aria-hidden", String(!this.isOpen));
    bubble.setAttribute("aria-expanded", String(this.isOpen));
    if (this.isOpen) panel.querySelector("#chatbotInput").focus();
    else bubble.focus();
  },

  sendQuickMessage(message) {
    if (!this.isOpen) this.toggle(true);
    this.sendMessage(message);
  },

  appendMessage(className, text) {
    const container = document.getElementById("chatbotMessages");
    const element = document.createElement("div");
    element.className = className;
    element.textContent = text;
    container.appendChild(element);
    container.scrollTop = container.scrollHeight;
    return element;
  },

  renderAssistantResponse(response) {
    const message = document.createElement("div");
    message.className = "chat-msg bot";
    const reply = document.createElement("p");
    reply.className = "chat-message-reply";
    reply.textContent = response.reply || "I could not find an answer in the live menu.";
    message.appendChild(reply);

    const mode = document.createElement("small");
    mode.className = "chatbot-response-mode";
    mode.textContent = response.llm_used ? "AI response grounded in menu data" : "Live menu assistant";
    message.appendChild(mode);

    const items = Array.isArray(response.recommended_items) ? response.recommended_items : [];
    if (items.length) {
      const list = document.createElement("div");
      list.className = "chatbot-recommendations";
      items.forEach(item => {
        const image = this.safeImageUrl(item.image_url);
        const card = document.createElement("article");
        card.className = "chat-item-card";
        card.innerHTML = `
          ${image ? `<img src="${this.escape(image)}" class="chat-item-img" alt="" loading="lazy">` : ""}
          <div class="chat-item-copy">
            <strong class="chat-item-name">${this.escape(item.name)}</strong>
            <span class="small text-muted">${this.escape(item.restaurant_name)}</span>
            <span class="small brand-orange fw-bold">₹${Number(item.price || 0).toFixed(2)}</span>
          </div>
          <button class="chat-item-add btn btn-sm btn-primary-orange" type="button" data-chat-add="${Number(item.food_id)}">Add</button>`;
        list.appendChild(card);
      });
      message.appendChild(list);
    }

    const container = document.getElementById("chatbotMessages");
    container.appendChild(message);
    container.scrollTop = container.scrollHeight;

    if (Array.isArray(response.suggestions) && response.suggestions.length) {
      const chips = document.getElementById("chatbotChips");
      chips.replaceChildren(...response.suggestions.map(suggestion => {
        const button = document.createElement("button");
        button.className = "chatbot-chip";
        button.type = "button";
        button.textContent = suggestion;
        button.dataset.chatPrompt = suggestion;
        return button;
      }));
    }
  },

  async sendMessage(message) {
    if (this.isSending) return;
    this.isSending = true;
    const form = document.getElementById("chatbotForm");
    const sendButton = form.querySelector("button[type='submit']");
    sendButton.disabled = true;
    this.appendMessage("chat-msg user", message);
    const previousHistory = this.history.slice(-8);
    this.history.push({ role: "user", content: message });
    const loading = this.appendMessage("chat-msg bot chatbot-loading", "Searching the live menu…");

    try {
      const response = await API.chatWithAssistant(message, null, null, previousHistory);
      loading.remove();
      this.renderAssistantResponse(response);
      this.history.push({ role: "assistant", content: response.reply || "" });
      this.history = this.history.slice(-8);
    } catch (error) {
      loading.remove();
      this.appendMessage("chat-msg bot chatbot-error", `I could not reach the assistant. ${error.message || "Please try again."}`);
    } finally {
      this.isSending = false;
      sendButton.disabled = false;
      document.getElementById("chatbotInput").focus();
    }
  }
};

document.addEventListener("DOMContentLoaded", () => Chatbot.init());
