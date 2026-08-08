/* ==================== InomjonAI frontend ==================== */

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

const landing = document.getElementById("landing");
const chatApp = document.getElementById("chatApp");
const modelSwitch = document.getElementById("modelSwitch");
const modelStatus = document.getElementById("modelStatus");

const authBackdrop = document.getElementById("authBackdrop");
const modalClose = document.getElementById("modalClose");
const modalTitle = document.getElementById("modalTitle");
const modalSub = document.getElementById("modalSub");
const authForm = document.getElementById("authForm");
const authError = document.getElementById("authError");
const authSubmit = document.getElementById("authSubmit");
const regFields = document.getElementById("regFields");
const fName = document.getElementById("fName");
const fEmail = document.getElementById("fEmail");
const fPassword = document.getElementById("fPassword");

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

const profileBackdrop = document.getElementById("profileBackdrop");
const profileClose = document.getElementById("profileClose");
const profileAvatar = document.getElementById("profileAvatar");
const profileSub = document.getElementById("profileSub");
const profileForm = document.getElementById("profileForm");
const profileError = document.getElementById("profileError");
const profileSave = document.getElementById("profileSave");
const pName = document.getElementById("pName");
const pSurname = document.getElementById("pSurname");
const pEmail = document.getElementById("pEmail");
const pPhone = document.getElementById("pPhone");
const passForm = document.getElementById("passForm");
const passError = document.getElementById("passError");
const passSave = document.getElementById("passSave");
const pOldPass = document.getElementById("pOldPass");
const pNewPass = document.getElementById("pNewPass");
const profileLogout = document.getElementById("profileLogout");

/* ================= holat ================= */

let me = null;          // {token, username, name, surname, email, phone} | null
let currentConv = null; // ochiq suhbat id (null = yangi)
let sending = false;
let currentModel = localStorage.getItem("neura_model") || "fast";

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

function cacheUser(u) {
  if (!u || !u.username) return;
  localStorage.setItem(
    "neura_user",
    JSON.stringify({ username: u.username, name: u.name, surname: u.surname || "", email: u.email || "", phone: u.phone || "" })
  );
}
function loadCachedUser() {
  try { return JSON.parse(localStorage.getItem("neura_user") || "null"); } catch (e) { return null; }
}
function removeCachedUser() {
  localStorage.removeItem("neura_user");
}

function fmtDate(iso) {
  try {
    const d = new Date(iso.replace(" ", "T") + "Z");
    return d.toLocaleDateString("uz-UZ", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch (e) {
    return iso.slice(0, 10);
  }
}

const MODEL_LABELS = {
  fast: "⚡ Tez model · gemini-flash-latest",
  think: "🧠 Aqlli model · command-a-plus-05-2026",
};

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

/* ================= sahifa ko'rinishi ================= */

function showLanding() {
  landing.hidden = false;
  chatApp.hidden = true;
}
function showChat() {
  landing.hidden = true;
  chatApp.hidden = false;
  input.focus();
}

/* ================= model tanlash ================= */

function applyModelUI() {
  document.querySelectorAll(".ms-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.model === currentModel)
  );
  if (modelStatus) modelStatus.textContent = MODEL_LABELS[currentModel] || "";
  localStorage.setItem("neura_model", currentModel);
}

modelSwitch.addEventListener("click", (e) => {
  const btn = e.target.closest(".ms-btn");
  if (!btn || !btn.dataset.model) return;
  currentModel = btn.dataset.model;
  applyModelUI();
});

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

function qMessage(role, text) {
  const row = document.createElement("div");
  row.className = "row " + role + " msg-in";
  if (role === "ai") {
    const av = document.createElement("div");
    av.className = "avatar";
    av.textContent = "✦";
    row.appendChild(av);
  }
  const b = document.createElement("div");
  b.className = "bubble";
  b.innerHTML = renderText(text);
  if (role === "ai") {
    const copy = document.createElement("button");
    copy.className = "copy-btn";
    copy.title = "Javobni nusxalash";
    copy.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
    copy.onclick = () => {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(text).then(() => {
        copy.classList.add("done");
        copy.textContent = "✓";
        setTimeout(() => { copy.classList.remove("ok"); copy.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'; }, 1200);
      });
    };
    b.appendChild(copy);
  }
  row.appendChild(b);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
  return row;
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
    v.style.maxWidth = "100%";
    v.style.maxHeight = "300px";
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

function greeting() {
  const h = new Date().getHours();
  if (h >= 5 && h < 11) return "Xayrli tong";
  if (h >= 11 && h < 17) return "Xayrli kun";
  if (h >= 17 && h < 23) return "Xayrli kech";
  return "Xayrli tun";
}

function showWelcome() {
  const name = me ? (me.name || me.username) : "";
  chat.innerHTML = "";
  const w = document.createElement("div");
  w.className = "welcome";
  w.innerHTML =
    "<div class='welcome-logo'><img src='/static/icons/logo.png' alt='InomjonAI' /></div>" +
    "<h2>" + greeting() + (name ? ", <span class='grad-text'>" + esc(name) + "</span>!" : "!") + "</h2>" +
    "<p>Men suhbatlashib o'rganadigan sun'iy intellektman. Savol bering, kod yozing, rasm tahlil qiling yoki yangi rasm/video yarating.</p>";
  const grid = w.appendChild(document.createElement("div"));
  grid.className = "welcome-grid";
  const items = [
    { e: "💬", t: "Suhbat", d: "Har qanday savolga tabiiy javob", q: "Nima qila olasan?" },
    { e: "💻", t: "Kod", d: "Dasturlash kodlari yozadi", q: "Python dastur yozib ber: foydalanuvchi ismini so'rab, salomlashadigan" },
    { e: "📷", t: "Rasm tahlili", d: "Rasmni o'qiydi va izohlaydi", q: "" },
    { e: "🌍", t: "Qidiruv", d: "Internetdan yangi ma'lumot", q: "O'zbekiston bo'yicha so'nggi kunlardagi muhim yangiliklarni topib ber" },
    { e: "🎨", t: "Rasm yaratish", d: "Prompt bo'yicha rasm chizadi", art: "image" },
    { e: "🎬", t: "Video yaratish", d: "Matnni videoga aylantiradi", art: "video" },
  ];
  items.forEach((it) => {
    const card = document.createElement("button");
    card.className = "welcome-card tilt3d";
    card.innerHTML = "<span data-z='28'>" + it.e + "</span><b>" + it.t + "</b><small>" + it.d + "</small>";
    card.onclick = () => { if (it.art) genArt(it.art); else if (it.file) fileInput.click(); else send(it.q); };
    grid.appendChild(card);
  });
  w.appendChild(grid);
  chat.appendChild(w);
}

/* ================= yuborish ================= */

async function send(text) {
  text = (text || "").trim();
  if (!text || sending) return;
  if (!me) {
    openAuth();
    return;
  }
  input.value = "";
  autoResize();
  sending = true;
  sendBtn.disabled = true;
  hideChips();

  qMessage("user", text);
  const typing = typingRow();

  try {
    const body = { message: text, user_id: CLIENT_ID, model: currentModel };
    if (me) body.token = me.token;
    if (currentConv !== null) body.conversation_id = currentConv;

    const data = await api("/api/chat", { method: "POST", body: JSON.stringify(body) });
    typing.remove();
    if (data.media_url) {
      qMedia(data.media_url, data.media_type === "video", text);
    } else {
      const row = qMessage("ai", data.reply);
      addFeedback(row, data.message_id);
    }

    if (currentConv === null && data.conversation_id) {
      currentConv = data.conversation_id;
      refreshConversations();
    }
  } catch (e) {
    typing.remove();
    if (e.status === 401) {
      qMessage("ai", "Kirish muddati tugagan. Qaytadan kiring.");
      setTimeout(() => { logout(); openAuth(); }, 600);
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
  if (!me) { openAuth(); return; }
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
  if (!me) { openAuth(); return; }
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
  if (!me || !me.token) return;
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

function openAuth(mode = "") {
  if (mode) setMode(mode);
  authBackdrop.hidden = false;
  setTimeout(() => fUsername.focus(), 60);
}
function closeAuth() { authBackdrop.hidden = true; }

function setMode(mode) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
  regFields.hidden = mode !== "register";
  authSubmit.textContent = mode === "register" ? "Ro'yxatdan o'tish" : "Kirish";
  modalTitle.textContent = mode === "register" ? "Hisob yarating" : "Xush kelibsiz!";
  modalSub.textContent = mode === "register" ? "AI ishlatish uchun 1 daqiqada ro'yxatdan o'ting" : "AI ishlatish uchun hisobingizga kiring";
}

authForm.onsubmit = async (e) => {
  e.preventDefault();
  const mode = document.querySelector(".tab.active").dataset.mode;
  const email = fEmail.value.trim().toLowerCase();
  const password = fPassword.value;
  authError.textContent = "";
  authSubmit.disabled = true;

  try {
    let data;
    if (mode === "register") {
      if (!email || !email.includes("@") || !email.includes(".")) {
        authError.textContent = "To'g'ri email kiriting (masalan: ism@mail.com)";
        authSubmit.disabled = false;
        return;
      }
      if (!fName.value.trim()) {
        authError.textContent = "Ismingizni kiriting";
        authSubmit.disabled = false;
        return;
      }
      data = await api("/api/register", {
        method: "POST",
        body: JSON.stringify({
          email, password,
          name: fName.value.trim(),
          client_id: CLIENT_ID,
        }),
      });
    } else {
      data = await api("/api/login", {
        method: "POST",
        body: JSON.stringify({ email, password, client_id: CLIENT_ID }),
      });
    }
    me = {
      token: data.token,
      username: data.username,
      name: data.name,
      surname: (data.surname || ""),
      email: data.email || "",
    };
    localStorage.setItem("neura_token", data.token);
    try {
      const u = await api("/api/me?token=" + encodeURIComponent(data.token));
      me.name = u.name || me.name;
      me.surname = u.surname || "";
      me.email = u.email || "";
      me.phone = u.phone || "";
    } catch (e) {}
    cacheUser(me);
    closeAuth();
    renderUser();
    showChat();
    newChat();
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
    if (b) b.onclick = () => openAuth();
    return;
  }
  if (loginTopBtn) loginTopBtn.style.display = "none";
  const initial = (me.name || me.username || "?").charAt(0).toUpperCase();
  sideUser.innerHTML =
    '<button class="user-card" id="userCard" title="Profil">' +
    '<div class="user-ava">' + esc(initial) + "</div>" +
    '<div class="user-info"><div class="user-name">' + esc(me.name || me.username || "") + '</div><div class="user-login">' + "@" + esc(me.username.toLowerCase()) + "</div></div>" +
    "</button>" +
    '<button class="logout-btn" id="logoutBtn" title="Chiqish">Chiqish</button>';
  document.getElementById("userCard").onclick = () => openProfile();
  document.getElementById("logoutBtn").onclick = async () => {
    await api("/api/logout?token=" + encodeURIComponent(me.token)).catch(() => {});
    logout();
  };
}

function logout() {
  try { closeProfile(); } catch (e) {}
  me = null;
  currentConv = null;
  localStorage.removeItem("neura_token");
  removeCachedUser();
  renderUser();
  showLanding();
  if (loginTopBtn) loginTopBtn.style.display = "";
}

/* ================= API kaliti / Haqida ================= */

function openAbout() {
  if (aboutBtn) aboutBackdrop.hidden = false;
}

async function openKeyModal() {
  if (!me) {
    openAuth();
    return;
  }
  keyBackdrop.hidden = false;
  keyError.textContent = "";
  const keyMake = document.getElementById("keyMake");
  const keyView = document.getElementById("keyView");
  document.getElementById("keyName").value = "";
  document.querySelectorAll(".key-model input[data-m]").forEach((c) => {
    c.checked = c.dataset.m === "fast";
  });
  try {
    const data = await api("/api/key?token=" + encodeURIComponent(me.token));
    if (data.key) {
      keyMake.hidden = true;
      keyView.hidden = false;
      apiKeyBox.innerHTML = '<code id="apiKeyVal">' + esc(data.key) + "</code>";
      const meta = document.getElementById("keyMeta");
      const models = (data.models && data.models.length)
        ? data.models.map((m) => m === "think" ? "🧠 Aqlli" : "⚡ Tez").join(" · ")
        : "⚡ Tez";
      meta.innerHTML = "Nomi: <b>" + esc(data.name || "Bosh kalit") + "</b> &nbsp;·&nbsp; Modellar: <b>" + models + "</b>";
    } else {
      keyMake.hidden = false;
      keyView.hidden = true;
    }
  } catch (e) {
    keyError.textContent = e.message;
  }
}

keyCreateBtn.onclick = async () => {
  if (!me) { closeAuth(); openAuth(); return; }
  const name = document.getElementById("keyName").value.trim();
  const models = Array.from(document.querySelectorAll(".key-model input[data-m]:checked"))
    .map((c) => c.dataset.m);
  if (!models.length) {
    keyError.textContent = "Kamida bitta modelni tanlang.";
    return;
  }
  keyCreateBtn.disabled = true;
  keyError.textContent = "";
  try {
    const data = await api("/api/key/create", {
      method: "POST",
      body: JSON.stringify({ token: me.token, name: name || "Bosh kalit", models }),
    });
    document.getElementById("keyMake").hidden = true;
    document.getElementById("keyView").hidden = false;
    apiKeyBox.innerHTML = '<code id="apiKeyVal">' + esc(data.key) + "</code>";
    const meta = document.getElementById("keyMeta");
    const modelsTxt = (data.models || []).map((m) => m === "think" ? "🧠 Aqlli" : "⚡ Tez").join(" · ");
    meta.innerHTML = "Nomi: <b>" + esc(data.name) + "</b> &nbsp;·&nbsp; Modellar: <b>" + modelsTxt + "</b>";
    navigator.clipboard && navigator.clipboard.writeText(data.key).catch(() => {});
  } catch (e) {
    keyError.textContent = e.message;
  }
  keyCreateBtn.disabled = false;
};

keyCopyBtn.onclick = () => {
  if (!me) return;
  const val = document.getElementById("apiKeyVal");
  if (val && navigator.clipboard) navigator.clipboard.writeText(val.textContent);
};

keyRevokeBtn.onclick = async () => {
  if (!me) return;
  try {
    await api("/api/key?token=" + encodeURIComponent(me.token), { method: "DELETE" });
    document.getElementById("keyView").hidden = true;
    document.getElementById("keyMake").hidden = false;
    document.getElementById("keyName").value = "";
    keyError.textContent = "Kalit bekor qilindi.";
  } catch (e) {
    keyError.textContent = e.message;
  }
};

/* ================= profil ================= */

function openProfile() {
  if (!me) { openAuth(); return; }
  profileError.textContent = "";
  passError.textContent = "";
  pOldPass.value = "";
  pNewPass.value = "";
  pName.value = me.name || me.username || "";
  pSurname.value = me.surname || "";
  pEmail.value = me.email || "";
  pPhone.value = me.phone || "";
  const initial = (me.name || me.username || "?").charAt(0).toUpperCase();
  profileAvatar.textContent = initial;
  profileSub.textContent = "@" + (me.username || "").toLowerCase() + (me.offline ? " · oflayn rejimda" : "");
  profileBackdrop.hidden = false;
}

function closeProfile() { profileBackdrop.hidden = true; }

profileForm.onsubmit = async (e) => {
  e.preventDefault();
  profileError.textContent = "";
  if (!me) { openAuth(); return; }
  profileSave.disabled = true;
  try {
    const data = await api("/api/profile", {
      method: "POST",
      body: JSON.stringify({
        token: me.token,
        name: pName.value.trim(),
        surname: pSurname.value.trim(),
        phone: pPhone.value.trim(),
      }),
    });
    me.name = data.name;
    me.surname = data.surname || "";
    me.phone = data.phone || "";
    me.email = data.email || "";
    cacheUser(me);
    renderUser();
    profileError.textContent = "✅ Ma'lumotlar saqlandi";
  } catch (err) {
    profileError.textContent = err.message;
  }
  profileSave.disabled = false;
};

passForm.onsubmit = async (e) => {
  e.preventDefault();
  passError.textContent = "";
  if (!me) { openAuth(); return; }
  passSave.disabled = true;
  try {
    await api("/api/change-password", {
      method: "POST",
      body: JSON.stringify({ token: me.token, old_password: pOldPass.value, new_password: pNewPass.value }),
    });
    pOldPass.value = "";
    pNewPass.value = "";
    passError.textContent = "✅ Parol o'zgartirildi";
  } catch (err) {
    passError.textContent = err.message;
  }
  passSave.disabled = false;
};

profileLogout.onclick = async () => {
  if (!me) { closeProfile(); return; }
  await api("/api/logout?token=" + encodeURIComponent(me.token)).catch(() => {});
  logout();
};

profileClose.onclick = closeProfile;
profileBackdrop.addEventListener("click", (e) => {
  if (e.target === profileBackdrop) closeProfile();
});

/* ================= landing interaktiv ================= */

document.getElementById("landingLoginBtn").onclick = () => openAuth();
document.getElementById("heroStartBtn").onclick = () => openAuth("register");
document.getElementById("heroHowBtn").onclick = () => {
  document.getElementById("features").scrollIntoView({ behavior: "smooth" });
};
document.getElementById("supportChatBtn").onclick = () => openAuth();
document.getElementById("cliHowBtn").onclick = () => {
  document.getElementById("cliBox").hidden = !document.getElementById("cliBox").hidden;
};
document.querySelectorAll("[data-open-chat]").forEach((el) => {
  el.onclick = () => openAuth();
});

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

loginTopBtn.onclick = () => openAuth();
aboutBtn.onclick = openAbout;
aboutClose.onclick = () => { aboutBackdrop.hidden = true; };
aboutBackdrop.addEventListener("click", (e) => { if (e.target === aboutBackdrop) aboutBackdrop.hidden = true; });
keyBtn.onclick = openKeyModal;
keyClose.onclick = () => { keyBackdrop.hidden = true; };
keyBackdrop.addEventListener("click", (e) => { if (e.target === keyBackdrop) keyBackdrop.hidden = true; });

/* ================= boshlash ================= */

async function boot() {
  const token = localStorage.getItem("neura_token");
  const cachedUser = loadCachedUser();

  if (token) {
    try {
      const u = await api("/api/me?token=" + encodeURIComponent(token));
      me = {
        token,
        username: u.username,
        name: u.name,
        surname: u.surname || "",
        email: u.email || "",
        phone: u.phone || "",
      };
      cacheUser(me);
      renderUser();
      showChat();
      currentConv = null;
      await refreshConversations();
    } catch (e) {
      if (e.status === 401) {
        // Token haqiqatan ham o'lik — tozalaymiz
        localStorage.removeItem("neura_token");
        removeCachedUser();
        me = null;
      } else if (cachedUser) {
        // Server xatosi / tarmoq uzilishi — foydalanuvchini o'chiramaymiz!
        me = { token, username: cachedUser.username, name: cachedUser.name, offline: true };
        renderUser();
        showChat();
      } else {
        me = null;
      }
    }
  }

  if (!me) {
    // Ro'yxatdan o'tmagan — landing, AI faqat ro'yxatdan o'tganlarga
    renderUser();
    showLanding();
    return;
  }
  renderUser();
  if (!currentConv) showWelcome();
}

/* ================= PWA ================= */

if ("serviceWorker" in navigator) {
  let refreshing = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (refreshing) return;
    refreshing = true;
    location.reload();
  });
  navigator.serviceWorker.register("/sw.js").catch(() => {});

  // Yangilanishni MAKSIMAL tezlikda tekshirish — F5 shartsiz
  let swTimer = null;
  function swCheck() {
    if (document.visibilityState !== "visible") return;
    navigator.serviceWorker
      .getRegistration()
      .then((r) => r && r.update().catch(() => {}))
      .catch(() => {});
  }
  function startSwTimer() {
    if (swTimer) clearInterval(swTimer);
    swTimer = setInterval(swCheck, 30 * 1000);
  }
  startSwTimer();
  document.addEventListener("visibilitychange", swCheck);
  window.addEventListener("focus", swCheck);
  window.addEventListener("pageshow", swCheck);
}

/* ================= mobil klaviatura ================= */

(function mobileKeyboard() {
  const composer = document.querySelector(".composer");
  if (!composer || !window.visualViewport) return;
  const apply = () => {
    const vh = window.visualViewport;
    document.documentElement.style.setProperty("--kb", vh.height + "px");
    const offset = window.innerHeight - (vh.height + vh.offsetTop);
    if (offset > 80) {
      document.documentElement.classList.add("kb-open");
      composer.style.paddingBottom = "calc(14px + " + offset + "px)";
      setTimeout(() => composer.scrollIntoView({ block: "nearest" }), 80);
      const chatEl = document.querySelector(".chat");
      if (chatEl) setTimeout(() => chatEl.scrollTo({ top: chatEl.scrollHeight }), 120);
    } else {
      document.documentElement.classList.remove("kb-open");
      composer.style.paddingBottom = "";
    }
  };
  window.visualViewport.addEventListener("resize", apply);
  window.visualViewport.addEventListener("scroll", apply);
  document.addEventListener("focusin", () => setTimeout(apply, 120));
  document.addEventListener("focusout", apply);
})();

let deferredPrompt = null;
const installBtn = document.getElementById("installBtn");
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;
  if (installBtn) installBtn.hidden = false;
});
if (installBtn) {
  installBtn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    installBtn.hidden = true;
  });
}
window.addEventListener("appinstalled", () => { if (installBtn) installBtn.hidden = true; });

applyModelUI();
boot();

/* ================= 3D effektlar (slechki joylar) ================= */

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

function bindTilt(el) {
  if (reduceMotion || !finePointer) return;
  el.addEventListener("pointermove", (e) => {
    const r = el.getBoundingClientRect();
    if (!r.width) return;
    const px = (e.clientX - r.left) / r.width;
    const py = (e.clientY - r.top) / r.height;
    el.style.transform =
      "perspective(900px) rotateX(" + ((0.5 - py) * 10).toFixed(2) + "deg) rotateY(" + ((px - 0.5) * 12).toFixed(2) + "deg) translateZ(10px)";
    el.style.setProperty("--mx", px.toFixed(3));
    el.style.setProperty("--my", py.toFixed(3));
    el.querySelectorAll("[data-z]").forEach((c) => {
      c.style.transform = "translateZ(" + c.dataset.z + "px)";
    });
  });
  el.addEventListener("pointerleave", () => {
    el.style = "";
    el.querySelectorAll("[data-z]").forEach((c) => { c.style.transform = ""; });
  });
}

function bindAllTilt() {
  document.querySelectorAll(".tilt3d").forEach((el) => {
    if (!el.dataset.tilted) { el.dataset.tilted = "1"; bindTilt(el); }
  });
}
bindAllTilt();

// kuzatuvchi — dinamik yaratilgan 3D elementlar uchun
if (typeof MutationObserver !== "undefined") {
  new MutationObserver(() => bindAllTilt()).observe(document.body, { childList: true, subtree: true });
}

// aurora orblari — sichqoncha bilan 3D parallaks (landing)
if (!reduceMotion) {
  const orbs = document.querySelectorAll(".orb");
  let raf = null;
  window.addEventListener("pointermove", (e) => {
    if (raf) return;
    const x = e.clientX / window.innerWidth - 0.5;
    const y = e.clientY / window.innerHeight - 0.5;
    raf = requestAnimationFrame(() => {
      orbs.forEach((o, i) => {
        const d = (i + 1) * 16;
        o.style.translate = (-x * d).toFixed(1) + "px " + (-y * d).toFixed(1) + "px";
      });
      raf = null;
    });
  });
}
