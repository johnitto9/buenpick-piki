const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const messages = document.querySelector("#messages");
const sendButton = form.querySelector("button[type='submit']");
const newChatButton = document.querySelector("#new-chat");
const runtime = document.querySelector("#runtime");
const runtimeLabel = document.querySelector("#runtime-label");

const conversationKey = "piki-local-conversation";
let conversationId = localStorage.getItem(conversationKey) || crypto.randomUUID();
localStorage.setItem(conversationKey, conversationId);

function addMessage(role, text, pending = false) {
  const article = document.createElement("article");
  article.className = `message ${role}${pending ? " pending" : ""}`;
  if (role === "assistant") {
    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "P";
    article.append(avatar);
  }
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  article.append(bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/chat/status");
    const status = await response.json();
    runtime.className = status.enabled ? "runtime ready" : "runtime error";
    runtimeLabel.textContent = status.enabled ? status.llm_model : "Chat no configurado";
  } catch {
    runtime.className = "runtime error";
    runtimeLabel.textContent = "Sin conexión";
  }
}

async function loadHistory() {
  try {
    const response = await fetch(`/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`);
    if (!response.ok) return;
    const history = await response.json();
    if (!history.length) return;
    messages.replaceChildren();
    history.forEach((item) => addMessage(item.role, item.text));
  } catch {
    return;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  input.style.height = "auto";
  addMessage("user", message);
  const pending = addMessage("assistant", "Pensando…", true);
  sendButton.disabled = true;
  try {
    const response = await fetch("/api/chat/messages", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({conversation_id: conversationId, message}),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "No pude procesar el mensaje.");
    pending.querySelector(".bubble").textContent = payload.text;
    pending.classList.remove("pending");
  } catch (error) {
    pending.querySelector(".bubble").textContent = error.message;
    pending.classList.remove("pending");
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 132)}px`;
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

newChatButton.addEventListener("click", () => {
  conversationId = crypto.randomUUID();
  localStorage.setItem(conversationKey, conversationId);
  messages.replaceChildren();
  addMessage("assistant", "Hola, soy Piki. ¿Qué alimento te gustaría rescatar hoy?");
  input.focus();
});

Promise.all([refreshStatus(), loadHistory()]);
