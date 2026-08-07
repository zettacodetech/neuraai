const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("sendBtn");
const chipsBox = document.getElementById("chips");
const fileInput = document.getElementById("fileInput");

const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("overlay");
const menuBtn = document.getElementById("menuBtn");
const convList = document.getElementById("convList");
const convEmpty = document.getElementById("convEmpty");
const newChatBtn = document.getElementById("newChatBtn");
const sideUser = document.getElementById("sideUser");

const authBackdrop = document.getElementById("authBackdrop");
const modalClose = document.getElementById("modalClose");
const modalTitle = document.getElementById("modalTitle");
const modalSub = document.getElementById("modalSub");
const authForm = document.getElementById("authForm");
const authError = document.getElementById("authError");
const authSubmit = document.getElementById("authSubmit");
const nameField = document.getElementById("nameField");
const fName = document.getElementById("fName");
const fUsername = document.getElementById("fUsername");
const fPassword = document.getElementById("fPassword");

const termsBackdrop = document.getElementById("termsBackdrop");
const termsAccept = document.getElementById("termsAccept");
const aboutBackdrop = document.getElementById("aboutBackdrop");
const aboutClose = document.getElementById("aboutClose");
const aboutBtn = document.getElementById("aboutBtn");
const keyBackdrop = document.getElementById("keyBackdrop");
const keyClose = document.getElementById("keyClose");
const keyBtn = document.getElementById("apiKeyBtn");
const keyCreateBtn = document.getElementById("keyCreateBtn");
const keyCopyBtn = document.getElementById("keyCopyBtn");
const keyRevokeBtn = document.getElementById("keyRevokeBtn");
const keyError = document.getElementById("keyError");
const apiKeyBox = document.getElementById("apiKeyBox");
const loginTopBtn = document.getElementById("loginTopBtn");

/* ================= holat ================= */

let me = null;            // {token, username, name} | null
let currentConv = null;   // ochiq suhbat id (null = yangi)
let sending = false;

function uid() {
  let id = localStorage.getItem("neura_uid");
  if (!id) {
    id = "u" + Date.now() + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("neura_uid", id);
  }
  return id;
}
const CLIENT_ID = uid();

function esc(t) {
  const d = document.createElement("div");
  d.textContent = t;
  return d.innerHTML;
}

function fmtDate(iso) {
  try {
    const d = new Date(iso.replace(" ", "T") + "Z");
    return d.toLocaleDateString("uz-UZ", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return iso.slice(0, 10);
  }
}

/* ================= API ================= */

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    throw Object.assign(
      new Error("Server javob bera olmadi (" + res.status + "). Qayta urinib ko'ring."),
      { status: res.status }
    );
  }
  if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
  return data;
}

/* ================= xabarlar ================= */

function renderText(text) {
  const parts = text.split(/```/);
  let html = "";
  parts.forEach((p, i) => {
    if (i % 2 === 1) html += "<pre>" + esc(p) + "</pre>";
    else html += esc(p).replace(/\n/g, "<br>");
  });
  return html;
}

function qImage(row, role, url, caption) {
  const b = document.createElement("div");
  b.className = "bubble " + role;
  const img = document.createElement("img");
  img.src = url;
  img.alt = "rasm";
  b.appendChild(img);
  if (caption) {
    const c = document.createElement("div");
    c.className = "img-cap";
    c.textContent = caption;
    b.appendChild(c);
  }
  row.appendChild(b);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
}

function qMedia(url, isVideo, caption) {
  const row = document.createElement("div");
  row.className = "row ai";
  const av = document.createElement("div");
  av.className = "avatar";
  av.textContent = "✦";
  row.appendChild(av);
  const b = document.createElement("div");
  b.className = "bubble";
  if (isVideo) {
    const v = document.createElement("video");
    v.src = url;
    v.controls = true;
    v.loop = true;
    v.muted = true;
    v.autoplay = false;
    v.style.maxWidth = "100%";
    v.style.maxHeight = "300px";
    v.style.borderRadius = "10px";
    b.appendChild(v);
  } else {
    const img = document.createElement("img");
    img.src = url;
    img.alt = "generated";
    b.appendChild(img);
  }
  const cap = document.createElement("div");
  cap.className = "img-cap";
  cap.textContent = caption;
  b.appendChild(cap);
  const dl = document.createElement("a");
  dl.className = "gen-dl";
  dl.href = url;
  dl.download = "";
  dl.textContent = "⬇ Yuklab olish";
  b.appendChild(dl);
  row.appendChild(b);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
}

function qMessage(role, text) {
  const row = document.createElement("div");
  row.className = "row " + role;
  if (role === "ai") {
    const av = document.createElement("div");
    av.className = "avatar";
    av.textContent = "✦";
    row.appendChild(av);
  }
  const b = document.createElement("div");
  b.className = "bubble";
  b.innerHTML = renderText(text);
  row.appendChild(b);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
}

function typingRow() {
  const row = document.createElement("div");
  row.className = "row ai";
  const av = document.createElement("div");
  av.className = "avatar";
  av.textContent = "✦";
  row.appendChild(av);
  const b = document.createElement("div");
  b.className = "bubble";
  b.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  row.appendChild(b);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
}

function addFeedback(row, messageId) {
  const fb = document.createElement("div");
  fb.className = "feedback";
  const up = document.createElement("button");
  up.className = "fb-btn";
  up.textContent = "👍 Foydali";
  const down = document.createElement("button");
  down.className = "fb-btn";
  down.textContent = "👎";
  fb.append(up, down);
  row.appendChild(fb);
  up.onclick = () => {
    api("/api/feedback", { method: "POST", body: JSON.stringify({ message_id: messageId, rating: 1 }) }).catch(() => {});
    up.classList.add("active"); down.classList.remove("active");
  };
  down.onclick = () => {
    api("/api/feedback", { method: "POST", body: JSON.stringify({ message_id: messageId, rating: -1 }) }).catch(() => {});
    down.classList.add("active"); up.classList.remove("active");
  };
}

function showWelcome() {
  const name = me ? me.name : "";
  chat.innerHTML = "";
  const w = document.createElement("div");
  w.className = "welcome";
  w.innerHTML =
    "<div class='welcome-logo'>✦</div>" +
    "<h2>" + (name ? "Assalomu alaykum, <span class='accent'>" + esc(name) + "</span>!" : "Sizning aqlli<br><span class='accent'>yordamchingiz</span>") + "</h2>" +
    "<p>Men suhbatlashib o'rganadigan sun'iy intellektman. Savol bering, kod yozang, rasm tahlil qiling yoki yangi rasm/video yarating.</p>";
  const grid = w.appendChild(document.createElement("div"));
  grid.className = "welcome-grid";
  const items = [
    { e: "💬", t: "Suhbat", d: "Har qanday savolga tabiiy javob" },
    { e: "💻", t: "Kod", d: "Dasturlash kodlari yozadi" },
    { e: "📷", t: "Rasm tahlili", d: "Rasmni o'qiydi va izohlaydi" },
    { e: "🌍", t: "Qidiruv", d: "Internetdan yangi ma'lumot" },
    { e: "🎨", t: "Rasm yaratish", d: "Prompt bo'yicha rasm chizadi" },
    { e: "🎬", t: "Video yaratish", d: "Matnni videoga aylantiradi" },
  ];
  items.forEach((it) => {
    const card = document.createElement("button");
    card.className = "welcome-card";
    card.innerHTML = "<span class='card-emoji'>" + it.e + "</span><b>" + it.t + "</b><small>" + it.d + "</small>";
    card.onclick = () => send(it.t === "Rasm tahlili" ? "Rasmni tahlil qil" : it.t === "Rasm yaratish" ? "Rasm yarat" : it.t === "Video yaratish" ? "Video yarat" : "Neura AI nima qila oladi?");
    grid.appendChild(card);
  });
  w.appendChild(grid);
  chat.appendChild(w);
}

/* ================= yuborish ================= */

async function send(text) {
  text = (text || "").trim();
  if (!text || sending) return;
  input.value = "";
  autoResize();
  sending = true;
  sendBtn.disabled = true;
  hideChips();

  qMessage("user", text);
  const typing = typingRow();

  try {
    const body = { message: text, user_id: CLIENT_ID };
    if (me) body.token = me.token;
    if (currentConv !== null) body.conversation_id = currentConv;

    const data = await api("/api/chat", { method: "POST", body: JSON.stringify(body) });
    typing.remove();
    const row = qMessage("ai", data.reply);
    addFeedback(row, data.message_id);

    if (currentConv === null && data.conversation_id) {
      currentConv = data.conversation_id;
      refreshConversations();
    }
    if (data.user_name && !me) {
      me = { token: localStorage.getItem("neura_token"), username: "", name: data.user_name };
    }
  } catch (e) {
    typing.remove();
    if (e.status === 401) {
      qMessage("ai", "Kirish muddati tugagan. Qaytadan kiring.");
    } else {
      qMessage("ai", "⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.");
    }
  }
  sending = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ================= rasm tahlili ================= */

function formatAnalysis(d) {
  const lines = [
    "📷 <b>Rasm tahlili:</b>",
    "• Format: " + d.format + ", " + d.width + "×" + d.height,
    "• Yorug'lik: " + d.brightness,
    "• Asosiy ranglar: " + d.colors.map((c) => c.name + " (" + c.percent + "%)").join(", "),
    "• " + d.unique_colors + " xil rang",
    "• " + (d.photo_like ? "Bu fotografiya" : "Bu kompyuter grafikasi"),
  ];
  if (d.exif && d.exif.DateTimeOriginal) lines.push("• Sana: " + d.exif.DateTimeOriginal);
  return lines.join("\n");
}

async function sendImage(file) {
  if (!file || sending) return;
  sending = true;
  sendBtn.disabled = true;
  hideChips();

  const row = document.createElement("div");
  row.className = "row user";
  qImage(row, "user", URL.createObjectURL(file), file.name);
  const typing = typingRow();

  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/analyze-image", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
    typing.remove();
    qMessage("ai", formatAnalysis(data));
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Rasm tahlili xatosi: " + (e.message || "qayta urinib ko'ring"));
  }
  sending = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ================= generatsiya (rasm/video) ================= */

async function genArt(kind) {
  if (sending) return;
  const q = prompt(kind === "image" ? "Rasm uchun tasvif yozing:" : "Video uchun tasvif yozing:", "tog'lar va quyosh botishi");
  if (!q || !q.trim()) return;
  sending = true;
  sendBtn.disabled = true;
  hideChips();

  const label = (kind === "image" ? "🎨 Rasm: " : "🎬 Video: ");
  qMessage("user", label + q.trim());
  const typing = typingRow();

  try {
    const res = await fetch("/api/gen/" + kind, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: q.trim() }),
    });
    const data = await res.json();
    if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
    typing.remove();
    qMedia(data.url, kind === "video", q.trim());
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Generatsiya xatosi: " + (e.message || "qayta urinib ko'ring"));
  }
  sending = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ================= suhbatlar (tarix) ================= */

async function refreshConversations() {
  if (!me) return;
  try {
    const data = await api("/api/conversations?token=" + encodeURIComponent(me.token));
    renderConvList(data.items);
  } catch (e) { /* indamaslik */ }
}

function renderConvList(items) {
  convList.innerHTML = "";
  convEmpty.style.display = items.length ? "none" : "block";
  items.forEach((c) => {
    const btn = document.createElement("button");
    btn.className = "conv-item" + (currentConv === c.id ? " active" : "");
    btn.innerHTML =
      '<span class="conv-ico"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>' +
      '<span class="conv-info"><span class="conv-title">' + esc(c.title) + "</span>" +
      '<span class="conv-meta">' + c.msg_count + " xabar · " + fmtDate(c.created_at) + "</span></span>";
    btn.onclick = () => openConversation(c.id);
    convList.appendChild(btn);
  });
}

async function openConversation(id) {
  if (!me) return;
  closeSidebar();
  try {
    const data = await api("/api/conversations/" + id + "?token=" + encodeURIComponent(me.token));
    currentConv = id;
    chat.innerHTML = "";
    data.items.forEach((m) => qMessage(m.role === "assistant" ? "ai" : "user", m.text));
    if (!data.items.length) showWelcome();
    refreshConversations();
  } catch (e) {
    if (e.status === 401) openAuth();
  }
}

function newChat() {
  currentConv = null;
  showWelcome();
  refreshConversations();
  closeSidebar();
  hideChips();
  input.focus();
}

/* ================= hisob ================= */

function openAuth() {
  authBackdrop.hidden = false;
  fUsername.focus();
}
function closeAuth() { authBackdrop.hidden = true; }

function setMode(mode) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
  nameField.hidden = mode !== "register";
  authSubmit.textContent = mode === "register" ? "Ro'yxatdan o'tish" : "Kirish";
  modalTitle.textContent = mode === "register" ? "Hisob yarating" : "Xush kelibsiz!";
  modalSub.textContent = mode === "register" ? "Suhbatlaringiz bir joyda saqlansin" : "Hisobingizga kiring";
}

authForm.onsubmit = async (e) => {
  e.preventDefault();
  const mode = document.querySelector(".tab.active").dataset.mode;
  const username = fUsername.value.trim();
  const password = fPassword.value;
  const name = fName.value.trim();
  authError.textContent = "";
  authSubmit.disabled = true;

  try {
    const data = await api("/api/" + (mode === "register" ? "register" : "login"), {
      method: "POST",
      body: JSON.stringify({
        username, password,
        name: mode === "register" ? name : undefined,
        client_id: CLIENT_ID,
      }),
    });
    me = { token: data.token, username: data.username, name: data.name };
    localStorage.setItem("neura_token", data.token);
    closeAuth();
    newChat();
    renderUser();
  } catch (err) {
    authError.textContent = err.message;
  }
  authSubmit.disabled = false;
};

function renderUser() {
  if (!me) {
    if (loginTopBtn) loginTopBtn.style.display = "";
    sideUser.innerHTML =
      '<button class="logout-btn" style="width:100%;padding:11px" id="loginPromptBtn">🔑 Hisobga kirish / Ro\'yxatdan o\'tish</button>';
    const b = document.getElementById("loginPromptBtn");
    if (b) b.onclick = openAuth;
    return;
  }
  if (loginTopBtn) loginTopBtn.style.display = "none";
  const initial = (me.name || me.username || "?").charAt(0).toUpperCase();
  sideUser.innerHTML =
    '<div class="user-ava">' + esc(initial) + "</div>" +
    '<div class="user-info"><div class="user-name">' + esc(me.name || me.username || "Mehmon") + '</div><div class="user-login">' + (me.guest ? "mehmon" : "@" + esc(me.username)) + "</div></div>" +
    '<button class="logout-btn" id="logoutBtn" title="Chiqish">' + (me.guest ? "Chiqish" : "Chiqish") + "</button>";
  document.getElementById("logoutBtn").onclick = async () => {
    await api("/api/logout?token=" + encodeURIComponent(me.token)).catch(() => {});
    me = null;
    currentConv = null;
    localStorage.removeItem("neura_token");
    chat.innerHTML = "";
    renderUser();
    showWelcome();
    refreshConversations();
    if (loginTopBtn) loginTopBtn.style.display = "";
  };
}

/* ================= API kaliti / Haqida / Qoidalar ================= */

function openAbout() {
  if (aboutBtn) aboutBackdrop.hidden = false;
}

async function openKeyModal() {
  if (!me) {
    authError.textContent = "";
    openAuth();
    return;
  }
  keyBackdrop.hidden = false;
  keyError.textContent = "";
  try {
    const data = await api("/api/key?token=" + encodeURIComponent(me.token));
    keyCreateBtn.hidden = !!data.key;
    keyCopyBtn.hidden = !data.key;
    keyRevokeBtn.hidden = !data.key;
    apiKeyBox.innerHTML = data.key
      ? '<code id="apiKeyVal">' + esc(data.key) + "</code>"
      : '<span class="muted">Sizda hozircha kalit yo\'q. Yaratib oling.</span>';
  } catch (e) {
    keyError.textContent = e.message;
  }
}

keyCreateBtn.onclick = async () => {
  keyCreateBtn.disabled = true;
  keyError.textContent = "";
  try {
    const data = await api("/api/key/create", {
      method: "POST",
      body: JSON.stringify({ token: me.token }),
    });
    apiKeyBox.innerHTML = '<span id="apiKeyVal" class="key-val">' + esc(data.key) + "</span>";
    keyCreateBtn.hidden = true;
    keyCopyBtn.hidden = false;
    keyRevokeBtn.hidden = false;
    navigator.clipboard && navigator.clipboard.writeText(data.key).catch(() => {});
  } catch (e) {
    keyError.textContent = e.message;
  }
  keyCreateBtn.disabled = false;
};

keyCopyBtn.onclick = () => {
  const val = document.getElementById("apiKeyVal");
  if (val && navigator.clipboard) navigator.clipboard.writeText(val.textContent);
};

keyRevokeBtn.onclick = async () => {
  try {
    await api("/api/key?token=" + encodeURIComponent(me.token), { method: "DELETE" });
    apiKeyBox.innerHTML = '<span class="muted">Kalit bekor qilindi.</span>';
    keyCreateBtn.hidden = false;
    keyCopyBtn.hidden = true;
    keyRevokeBtn.hidden = true;
  } catch (e) {
    keyError.textContent = e.message;
  }
};

/* ================= boshqa ================= */

function hideChips() { chipsBox.style.display = "none"; }
function autoResize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 150) + "px";
}
function closeSidebar() {
  sidebar.classList.remove("open");
  overlay.classList.remove("show");
}

sendBtn.onclick = () => send(input.value);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send(input.value);
  }
});
input.addEventListener("input", autoResize);

chipsBox.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  if (chip.dataset.action === "image") fileInput.click();
  else if (chip.dataset.gen) genArt(chip.dataset.gen);
  else send(chip.dataset.q);
});

fileInput.addEventListener("change", () => {
  const f = fileInput.files[0];
  if (f) sendImage(f);
  fileInput.value = "";
});

newChatBtn.onclick = newChat;
menuBtn.onclick = () => {
  sidebar.classList.toggle("open");
  overlay.classList.toggle("show");
};
overlay.onclick = closeSidebar;
modalClose.onclick = closeAuth;
authBackdrop.addEventListener("click", (e) => { if (e.target === authBackdrop) closeAuth(); });
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.mode)));

loginTopBtn.onclick = openAuth;
aboutBtn.onclick = openAbout;
aboutClose.onclick = () => { aboutBackdrop.hidden = true; };
aboutBackdrop.addEventListener("click", (e) => { if (e.target === aboutBackdrop) aboutBackdrop.hidden = true; });
keyBtn.onclick = openKeyModal;
keyClose.onclick = () => { keyBackdrop.hidden = true; };
keyBackdrop.addEventListener("click", (e) => { if (e.target === keyBackdrop) keyBackdrop.hidden = true; });
termsBackdrop.addEventListener("click", (e) => { if (e.target === termsBackdrop) termsBackdrop.hidden = true; });

/* ================= boshlash ================= */

async function boot() {
  if (!localStorage.getItem("neura_terms")) {
    termsBackdrop.hidden = false;
  }
  termsAccept.onclick = () => {
    localStorage.setItem("neura_terms", "1");
    termsBackdrop.hidden = true;
  };

  const token = localStorage.getItem("neura_token");
  if (token) {
    try {
      const u = await api("/api/me?token=" + encodeURIComponent(token));
      me = { token, username: u.username, name: u.name };
      currentConv = null;
      renderUser();
      await refreshConversations();
    } catch (e) {
      localStorage.removeItem("neura_token");
      me = null;
    }
  }
  if (!me) {
    try {
      const s = await api("/api/session?client_id=" + encodeURIComponent(CLIENT_ID));
      me = { token: s.token, username: "", name: "", guest: true };
      localStorage.setItem("neura_token", s.token);
      renderUser();
      await refreshConversations();
    } catch (e) {
      renderUser();
    }
  } else {
    renderUser();
  }
  if (!currentConv) showWelcome();
}

/* ================= PWA ================= */

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

let deferredPrompt = null;
const installBtn = document.getElementById("installBtn");
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
  installBtn.hidden = false;
});
installBtn.addEventListener("click", async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  installBtn.hidden = true;
});
window.addEventListener("appinstalled", () => { installBtn.hidden = true; });

boot();