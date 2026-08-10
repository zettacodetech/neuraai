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

const aboutBtn = document.getElementById("aboutBtn");
const keyBtn = document.getElementById("apiKeyBtn");
const themeBtn = document.getElementById("themeBtn");
const micBtn = document.getElementById("micBtn");
const loginTopBtn = document.getElementById("loginTopBtn");
const docInput = document.getElementById("docInput");
const searchBtn = document.getElementById("searchBtn");
const galleryBtn = document.getElementById("galleryBtn");
const shareBtn = document.getElementById("shareBtn");

/* ================= holat ================= */

let me = null;          // {token, username, name, surname, email, phone} | null

function updateLimitBadge() {
  const badge = document.getElementById("limitBadge");
  if (!badge) return;
  if (!me || !me.daily_limit) { badge.hidden = true; return; }
  badge.hidden = false;
  document.getElementById("limitNum").textContent = Math.max(0, me.daily_limit - (me.daily_used || 0));
  document.getElementById("limitMax").textContent = me.daily_limit;
  const left = me.daily_limit - (me.daily_used || 0);
  badge.title = left <= 3 ? "Limit tugayapti — /premium oshiring!" : "Bugungi so'rovlar limiti";
  badge.classList.toggle("limit-low", left <= 3);
}
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
  local: "🖥️ Lokal model · Ollama",
};

let localAI = null; // {available, model, models} | null
async function loadLocalAI() {
  try {
    const res = await fetch("/api/local-ai");
    if (!res.ok) return;
    localAI = await res.json();
    const btn = document.getElementById("localModelBtn");
    if (btn) {
      if (localAI.ok) {
        btn.classList.add("ok");
        btn.title = "Lokal AI ishlayapti: " + (localAI.configured_model || "");
      } else {
        btn.classList.add("off");
        btn.title = localAI.hint || "Lokal AI mavjud emas";
      }
    }
  } catch (e) {
    /* ign */
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
  const parts = String(text).split(/```/);
  let html = "";
  parts.forEach((p, i) => {
    if (i % 2 === 1) html += "<pre>" + esc(p) + "</pre>";
    else html += mdRender(p);
  });
  return html;
}

function mdRender(raw) {
  const lines = raw.split("\n");
  let html = "";
  let listTag = null;
  let table = null;
  const flushList = () => {
    if (listTag) { html += "</" + listTag + ">"; listTag = null; }
  };
  const flushTable = () => {
    if (table) { html += "</table>"; table = null; }
  };
  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, "");
    if (!line.trim()) { flushList(); flushTable(); continue; }
    if (line.trim() !== "|" && /^\s*\|.*\|\s*$/.test(line)) {
      flushList();
      if (!table) table = "<table>";
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (cells.every((c) => /^:?-{2,}:?$/.test(c))) continue;
      table += "<tr>" + cells.map((c) => "<td>" + mdInline(c) + "</td>").join("") + "</tr>";
      continue;
    }
    flushTable();
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) { flushList(); html += "<h" + h[1].length + ">" + mdInline(h[2]) + "</h" + h[1].length + ">"; continue; }
    const ul = line.match(/^\s*[-*]\s+(.*)$/);
    const ol = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const li = (ul || ol || [])[1];
    const tag = ul ? "ul" : ol ? "ol" : null;
    if (tag) {
      if (listTag !== tag) { flushList(); html += "<" + tag + ">"; listTag = tag; }
      html += "<li>" + mdInline(li) + "</li>";
      continue;
    }
    flushList();
    html += "<p>" + mdInline(line) + "</p>";
  }
  flushList();
  flushTable();
  return html;
}

function mdInline(t) {
  let s = esc(t);
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  s = s.replace(/__([^_]+)__/g, "<b>$1</b>");
  s = s.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");
  s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
  return s;
}

/* ============ jonli effektlar (99999D) ============ */

function speak(text, btn) {
  const clean = text.replace(/```[\s\S]*?```/g, " kod ").replace(/<[^>]+>/g, " ").slice(0, 1200);
  const stop = () => { btn.dataset.on = "0"; btn.classList.remove("playing"); };
  if (btn.dataset.on === "1" && window.__nAudio) {
    try { window.__nAudio.pause(); window.__nAudio = null; } catch (e) {}
    stop();
    return;
  }
  if ("speechSynthesis" in window && speechSynthesis.getVoices().length > 0) {
    if (speechSynthesis.speaking && btn.dataset.on === "1") {
      speechSynthesis.cancel();
      stop();
      return;
    }
    const u = new SpeechSynthesisUtterance(clean);
    const voices = speechSynthesis.getVoices();
    u.voice = voices.find((v) => /^uz/i.test(v.lang)) || voices.find((v) => /^(ru|az|kk|ky)/i.test(v.lang)) || null;
    u.lang = u.voice ? u.voice.lang : "ru-RU";
    u.rate = 1;
    u.pitch = 1;
    btn.dataset.on = "1";
    btn.classList.add("playing");
    u.onend = u.onerror = stop;
    speechSynthesis.speak(u);
    return;
  }
  // API TTS fallback (ElevenLabs / Pollinations) — WebApp / WebView uchun
  btn.dataset.on = "1";
  btn.classList.add("playing");
  fetch("/api/generate-voice", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: clean, token: (me && me.token) || "" }),
  }).then(async (r) => {
    const d = await r.json().catch(() => ({}));
    if (!d.audio_url) throw new Error("audio yo'q");
    if (window.__nAudio) { try { window.__nAudio.pause(); } catch (e) {} }
    const audio = new Audio(d.audio_url);
    window.__nAudio = audio;
    audio.onended = audio.onerror = stop;
    audio.play().catch(stop);
  }).catch(stop);
}

function voiceButton(text) {
  const btn = document.createElement("button");
  btn.className = "voice-btn";
  btn.title = "Ovozli o'qish";
  btn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>';
  btn.onclick = () => speak(text, btn);
  return btn;
}

function confettiBurst() {
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const colors = ["#22d3ee", "#8f7bff", "#ec4899", "#fbbf24", "#34d399", "#f472b6"];
  const n = 42;
  for (let i = 0; i < n; i++) {
    const c = document.createElement("span");
    c.className = "conf";
    const s = 5 + Math.random() * 8;
    c.style.left = Math.random() * 100 + "vw";
    c.style.width = s + "px";
    c.style.height = s * 0.55 + "px";
    c.style.background = colors[i % colors.length];
    c.style.setProperty("--dx", (Math.random() * 200 - 100) + "px");
    c.style.setProperty("--t", (1.6 + Math.random() * 1.6) + "s");
    c.style.setProperty("--rot", (Math.random() * 720 - 360) + "deg");
    c.style.animationDelay = Math.random() * 0.5 + "s";
    document.body.appendChild(c);
    c.addEventListener("animationend", () => c.remove());
  }
}

function flashRow(row) {
  if (!row) return;
  if (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  row.classList.add("flash-ai");
  setTimeout(() => row.classList.remove("flash-ai"), 1500);
}

function aiRowBubble() {
  const row = document.createElement("div");
  row.className = "row ai msg-in";
  const av = document.createElement("div");
  av.className = "avatar";
  av.textContent = "✦";
  row.appendChild(av);
  const b = document.createElement("div");
  b.className = "bubble";
  row.appendChild(b);
  return { row, bubble: b };
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
        copy.classList.add("ok");
        copy.textContent = "✓";
        setTimeout(() => { copy.classList.remove("ok"); copy.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'; }, 1200);
      });
    };
    b.appendChild(copy);
    b.appendChild(voiceButton(text));
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
    { e: "📷", t: "Rasm tahlili", d: "Rasmni o'qiydi va izohlaydi", file: true },
    { e: "🌍", t: "Qidiruv", d: "Internetdan yangi ma'lumot", q: "O'zbekiston bo'yicha so'nggi kunlardagi muhim yangiliklarni topib ber" },
    { e: "🏖", t: "Sayohat reja", d: "3 kunlik sayohat rejasini tuzadi", q: "Toshkentdan Samarqandga 2 kunga beg: mehmonxona, restoran va joylar bilan reja tuzib ber" },
    { e: "💪", t: "Mashq dasturi", d: "Haftalik jismoniy mashqlar", q: "Yangi boshlovchi uchun haftalik 30 daqiqalik jismoniy mashq dasturi tuzib ber" },
    { e: "🍳", t: "Retsept", d: "Taom tayyorlash bo'yicha ko'rsatma", q: "Osh tayyorlashning oddiy retsepti bo'ylama ko'rsatma bilan yozib ber" },
    { e: "🎓", t: "O'qish", d: "Mavzuni oddiy tilda tushuntiradi", q: "Gravitatsiya nima ekanligini 5 yoshli bolaga tushuntiradigan qilib aytib ber" },
    { e: "🎨", t: "Rasm yaratish", d: "Prompt bo'yicha rasm chizadi", art: "image" },
    { e: "🎬", t: "Video yaratish", d: "Matnni videoga aylantiradi", art: "video" },
    { e: "🎵", t: "Musiqa yaratish", d: "Tavsif bo'yicha musiqa yaratadi", genType: "music" },
    { e: "🎙️", t: "Ovoz yaratish", d: "Matnni ovozga aylantiradi", genType: "voice" },
  ];
  items.forEach((it) => {
    const card = document.createElement("button");
    card.className = "welcome-card tilt3d";
    card.innerHTML = "<span data-z='28'>" + it.e + "</span><b>" + it.t + "</b><small>" + it.d + "</small>";
    card.onclick = () => { if (it.art) genArt(it.art); else if (it.genType) genAudio(it.genType); else if (it.file) fileInput.click(); else send(it.q); };
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
  // ============ Slash buyruqlar ============
  if (text.startsWith("/note ")) {
    const content = text.slice(6).trim();
    if (content) {
      const title = content.split("\n")[0].slice(0, 60) || "Nota";
      try {
        await api("/api/notes/create", { method: "POST", body: JSON.stringify({ token: me.token, title, content, category: "chat" }) });
        toast(t("saved"));
      } catch (e) { toast(e.message); }
    }
    input.value = "";
    return;
  }
  if (text === "/notes") { loadNotes(); openModal("notesModal"); input.value = ""; return; }
  if (text === "/sum") {
    input.value = "";
    if (!currentConv) { toast("Avval suhbatni oching"); return; }
    const typing = typingRow();
    try {
      const res = await fetch("/api/chat/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: me.token, conversation_id: currentConv }),
      });
      const data = await res.json();
      if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
      typing.remove();
      qMessage("ai", "📋 Suhbat xulosasi:\n\n" + data.summary);
      flashRow(document.querySelector(".row.ai.msg-in:last-of-type"));
    } catch (e) {
      typing.remove();
      qMessage("ai", "⚠️ Xulosa xatosi: " + (e.message || "qayta urinib ko'ring"));
    }
    return;
  }
  if (text === "/translate") {
    input.value = "";
    if (!currentConv) { toast("Avval suhbatni oching"); return; }
    const typing = typingRow();
    try {
      const res = await fetch("/api/chat/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: me.token, conversation_id: currentConv }),
      });
      const data = await res.json();
      if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
      typing.remove();
      qMessage("ai", "🌐 Suhbat tarjimasi:\n\n" + data.translation);
      flashRow(document.querySelector(".row.ai.msg-in:last-of-type"));
    } catch (e) {
      typing.remove();
      qMessage("ai", "⚠️ Tarjima xatosi: " + (e.message || "qayta urinib ko'ring"));
    }
    return;
  }
  if (text === "/export") {
    if (currentConv) {
      try {
        const d = await api(`/api/export?token=${encodeURIComponent(me.token)}&conversation_id=${currentConv}`);
        exportText.value = d.text || "";
        openModal("exportModal");
      } catch (e) { toast(e.message); }
    }
    input.value = "";
    return;
  }
  input.value = "";
  autoResize();
  sending = true;
  sendBtn.disabled = true;
  hideChips();

  qMessage("user", text);
  const typing = typingRow();
  let finished = false;

  let sseConv = currentConv;
  try {
    const body = { message: text, user_id: CLIENT_ID, model: currentModel };
    if (me) body.token = me.token;
    if (currentConv !== null) body.conversation_id = currentConv;

    // ============ SSE jonli javob ============
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let emsg = "xato";
      try { emsg = (await res.json()).error || emsg; } catch (e) {}
      throw Object.assign(new Error(emsg), { status: res.status });
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let ai = null;      // {row, bubble}
    let acc = "";
    let gotChunk = false;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const ln of block.split("\n")) {
          if (!ln.startsWith("data:")) continue;
          let evt;
          try { evt = JSON.parse(ln.slice(5).trim()); } catch (e) { continue; }
          if (evt.type === "start") {
            if (sseConv === null && evt.conversation_id) sseConv = evt.conversation_id;
          } else if (evt.type === "text") {
            if (!ai) {
              typing.remove();
              ai = aiRowBubble();
              chat.appendChild(ai.row);
            }
            acc += evt.text;
            ai.bubble.innerHTML = renderText(acc);
            if (!gotChunk) { flashRow(ai.row); gotChunk = true; }
            chat.scrollTop = chat.scrollHeight;
          } else if (evt.type === "media") {
            typing.remove();
            qMedia(evt.media_url, evt.media_type === "video", text);
            confettiBurst();
            hideScrollDown();
          } else if (evt.type === "error") {
            typing.remove();
            qMessage("ai", evt.reply || "⚠️ Xatolik yuz berdi.");
          } else if (evt.type === "done") {
            typing.remove();
            if (!ai && evt.reply) {
              ai = aiRowBubble();
              chat.appendChild(ai.row);
            }
            if (evt.reply) {
              acc = evt.reply;
              ai.bubble.innerHTML = renderText(acc);
            }
            if (ai) {
              ai.bubble.appendChild(voiceButton(acc));
              const copy = document.createElement("button");
              copy.className = "copy-btn";
              copy.title = "Javobni nusxalash";
              copy.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
              copy.onclick = () => {
                if (!navigator.clipboard) return;
                navigator.clipboard.writeText(acc).then(() => {
                  copy.classList.add("ok");
                  copy.textContent = "✓";
                  setTimeout(() => { copy.classList.remove("ok"); copy.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>'; }, 1200);
                });
              };
              ai.bubble.appendChild(copy);
              flashRow(ai.row);
              if (document.hidden) ding();
              if (evt.message_id) addFeedback(ai.row, evt.message_id);
            }
            if (sseConv !== null) {
              currentConv = sseConv;
              lastConvId = sseConv;
            }
            finished = true;
          }
        }
      }
    }
    if (!finished) throw new Error("Stream uzildi");

    refreshConversations();
    updateStats();
  } catch (e) {
    // ============ zaxira: oddiy /api/chat ============
    try {
      const body = { message: text, user_id: CLIENT_ID, model: currentModel };
      if (me) body.token = me.token;
      if (currentConv !== null) body.conversation_id = currentConv;
      const data = await api("/api/chat", { method: "POST", body: JSON.stringify(body) });
      typing.remove();
      if (data.media_url) {
        qMedia(data.media_url, data.media_type === "video", text);
        confettiBurst();
      } else {
        const row = qMessage("ai", data.reply);
        flashRow(row);
        addFeedback(row, data.message_id);
      }
      if (currentConv === null && data.conversation_id) {
        currentConv = data.conversation_id;
        lastConvId = data.conversation_id;
      }
      refreshConversations();
      updateStats();
    } catch (e2) {
      typing.remove();
      if (e2.status === 401) {
        qMessage("ai", "Kirish muddati tugagan. Qaytadan kiring.");
        setTimeout(() => { logout(); openAuth(); }, 600);
      } else {
        qMessage("ai", "⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.");
      }
    }
  }
  sending = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ================= rasm tahlili ================= */

async function editImage(file, action, label) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("action", action);
  const typing = typingRow();
  try {
    const res = await fetch("/api/edit-image", { method: "POST", body: fd });
    const d = await res.json();
    typing.remove();
    if (!res.ok) throw new Error(d.error || "xato");
    const row = document.createElement("div");
    row.className = "row ai msg-in";
    const av = document.createElement("div");
    av.className = "avatar";
    av.textContent = "✦";
    row.appendChild(av);
    const b = document.createElement("div");
    b.className = "bubble";
    b.innerHTML = '<b>🖼️ ' + label + ':</b> <a class="dl-link" href="' + d.image_url + '" target="_blank" rel="noopener">Ochish</a>';
    row.appendChild(b);
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Tahrirlash xatosi: " + (e.message || "qayta urinib ko'ring"));
  }
}

function attachImageEditActions(file) {
  const last = document.querySelector(".row.ai.msg-in:last-of-type .bubble");
  if (!last) return;
  const wrap = document.createElement("div");
  wrap.className = "img-edit-bar";
  const acts = [
    ["retro", "🕰 Retro"],
    ["upscale", "🔍 2x kat"],
    ["bg-remove", "✂️ BG olib tashlash"],
  ];
  acts.forEach(([a, lbl]) => {
    const btn = document.createElement("button");
    btn.className = "mini-btn";
    btn.textContent = lbl;
    btn.onclick = () => editImage(file, a, lbl);
    wrap.appendChild(btn);
  });
  last.appendChild(wrap);
}

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

  // Rasmni base64 ga aylantiramiz (local vision model uchun)
  const toBase64 = (f) => new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(",")[1]);
    r.onerror = reject;
    r.readAsDataURL(f);
  });

  try {
    const b64 = await toBase64(file);
    // 1) Local AI vision (qwen2.5-vl) — birinchi urinish
    const res = await fetch("/api/vision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image: b64,
        prompt: "Ushbu rasmni tahlil qilib, undagi narsalarni, matnni va holatni o'zbekcha batafsil tushuntir.",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
    typing.remove();
    qMessage("ai", data.analysis || "Tahlil topilmadi");
    attachImageEditActions(file);
    flashRow(document.querySelector(".row.ai.msg-in:last-of-type"));
    confettiBurst();
  } catch (e) {
    // 2) Fallback: heuristics tahlil
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res2 = await fetch("/api/analyze-image", { method: "POST", body: fd });
      const data2 = await res2.json();
      if (!res2.ok) throw Object.assign(new Error(data2.error || "xato"), { status: res2.status });
      typing.remove();
      qMessage("ai", formatAnalysis(data2));
      flashRow(document.querySelector(".row.ai.msg-in:last-of-type"));
      confettiBurst();
    } catch (e2) {
      typing.remove();
      qMessage("ai", "⚠️ Rasm tahlili xatosi: " + (e2.message || "qayta urinib ko'ring"));
    }
  }
  sending = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ================= hujjat yuklash (PDF/DOCX/TXT) ================= */

async function sendDoc(file) {
  if (!file || sending) return;
  if (!me) { openAuth(); return; }
  sending = true;
  sendBtn.disabled = true;
  hideChips();
  qMessage("user", "📄 " + file.name);
  const typing = typingRow();

  let text = "";
  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/upload-doc", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
    text = "📄 Hujjat: " + data.filename + "\n\n" + data.text;
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Hujjatni o'qib bo'lmadi: " + (e.message || "qayta urinib ko'ring"));
sending = false;
  sendBtn.disabled = false;
  input.focus();
  if (me && (me.daily_used !== undefined)) { me.daily_used++; updateLimitBadge(); }
}
  typing.remove();
  send(text);
  sending = false;
  sendBtn.disabled = false;
}

docInput.addEventListener("change", () => {
  const f = docInput.files[0];
  if (f) sendDoc(f);
  docInput.value = "";
});

/* ================= ovozli xabar (MediaRecorder → /api/stt) ================= */

let recorder = null;
let recChunks = [];

async function sttSend(blob) {
  const typing = typingRow();
  qMessage("user", "🎤 (ovozli xabar)");
  try {
    const fd = new FormData();
    fd.append("file", new File([blob], "voice.webm", { type: "audio/webm" }));
    const res = await fetch("/api/stt", { method: "POST", body: fd });
    const data = await res.json();
    typing.remove();
    if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
    send(data.text);
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Ovozni tanib bo'lmadi: " + (e.message || "qayta urinib ko'ring"));
  }
}

async function startRecorder() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";
    recorder = new MediaRecorder(stream, { mimeType: mime });
    recChunks = [];
    recorder.ondataavailable = (e) => { if (e.data.size) recChunks.push(e.data); };
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(recChunks, { type: mime });
      if (blob.size > 200) sttSend(blob);
      else { micBtn.classList.remove("rec"); input.placeholder = "InomjonAI ga so'rovingizni yozing..."; }
    };
    recorder.start();
    recognizing = true;
    micBtn.classList.add("rec");
    input.placeholder = "Gapiring...";
    input.value = "🔴 Yozilmoqda...";
  } catch (e) {
    alert("Mikrofon ruxsati berilmagan yoki qo'llab-quvvatlanmaydi.");
  }
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
    confettiBurst();
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Generatsiya xatosi: " + (e.message || "qayta urinib ko'ring"));
  }
  sending = false;
  sendBtn.disabled = false;
  input.focus();
}

/* ================= suhbatlar (tarix) ================= */

async function refreshConversations(archived = 0) {
  if (!me || !me.token) return;
  try {
    const data = await api("/api/conversations?token=" + encodeURIComponent(me.token) + "&archived=" + (archived ? 1 : 0));
    renderConvList(data.items);
  } catch (e) { /* indamaslik */ }
}

let showArchived = false;
const archBtn = document.getElementById("archBtn");
if (archBtn) archBtn.onclick = () => {
  showArchived = !showArchived;
  archBtn.classList.toggle("on", showArchived);
  refreshConversations(showArchived ? 1 : 0);
};

function renderConvList(items) {
  convItems = items;
  convList.innerHTML = "";
  convEmpty.style.display = items.length ? "none" : "block";
  items.forEach((c) => {
    const btn = document.createElement("div");
    btn.className = "conv-item" + (currentConv === c.id ? " active" : "");
    btn.dataset.id = c.id;
    const folderTag = c.folder ? '<span class="conv-fold">' + esc(c.folder) + '</span>' : "";
    btn.innerHTML =
      '<span class="conv-ico"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg></span>' +
      '<span class="conv-info"><span class="conv-title">' + esc(c.title) + "</span>" +
      '<span class="conv-meta">' + c.msg_count + " xabar · " + fmtDate(c.created_at) + folderTag + "</span></span>" +
      '<span class="conv-actions">' +
      '<button class="conv-act" title="Papka" data-act="folder"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></button>' +
      '<button class="conv-act" title="Arxivlash" data-act="archive"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8v13H3V8M1 3h22v5H1zM10 12h4"/></svg></button>' +
      '<button class="conv-act" title="Nomlash" data-act="rename"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5z"/></svg></button>' +
      '<button class="conv-act" title="TXT yuklab olish" data-act="export"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></button>' +
      '<button class="conv-act danger" title="O\'chirish" data-act="del"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg></button>' +
      "</span>";
    btn.querySelector(".conv-info").onclick = () => openConversation(c.id);
    btn.querySelector('[data-act="folder"]').onclick = (e) => { e.stopPropagation(); askFolder(c); };
    btn.querySelector('[data-act="archive"]').onclick = (e) => { e.stopPropagation(); archiveConv(c); };
    btn.querySelector('[data-act="rename"]').onclick = (e) => { e.stopPropagation(); renameConversation(c.id); };
    btn.querySelector('[data-act="export"]').onclick = (e) => { e.stopPropagation(); exportConversation(c.id); };
    btn.querySelector('[data-act="del"]').onclick = (e) => { e.stopPropagation(); deleteConversation(c.id); };
    convList.appendChild(btn);
  });
  updateStats(items);
}

function askFolder(c) {
  const cur = c.folder || "";
  const val = prompt(cur ? "Papkani o'zgartirish (bo'sh qoldirsangiz — o'chiriladi):" : "Papka nomini kiriting:", cur);
  if (val === null) return;
  api("/api/conversations/folder", {
    method: "POST",
    body: JSON.stringify({ token: me.token, conversation_id: c.id, folder: val.trim() }),
  }).then((d) => {
    toast(d.folders ? "Papka saqlandi" : "Saqlandi");
    refreshConversations();
  }).catch((e) => toast(e.message));
}

function archiveConv(c) {
  const arch = c.archived ? 0 : 1;
  api("/api/conversations/archive", {
    method: "POST",
    body: JSON.stringify({ token: me.token, conversation_id: c.id, archived: arch }),
  }).then(() => {
    toast(arch ? "Arxivlandi" : "Qayta tiklandi");
    refreshConversations();
  }).catch((e) => toast(e.message));
}

/* ================= jonli statistika ================= */

function updateStats(items) {
  const ids = { conv: document.getElementById("statsConv"), msg: document.getElementById("statsMsg") };
  if (!ids.conv || !ids.msg) return;
  const list = Array.isArray(items) ? items : convItems;
  ids.conv.textContent = list ? list.length : 0;
  ids.msg.textContent = list ? list.reduce((s, c) => s + (c.msg_count || 0), 0) : 0;
  const st = document.querySelector(".st-pulse");
  if (st) {
    st.classList.remove("st-live");
    void st.offsetWidth;
    st.classList.add("st-live");
  }
}

let convItems = [];

/* ================= pastga tushish ================= */

const scrollDownBtn = document.getElementById("scrollDownBtn");

function hideScrollDown() {
  if (scrollDownBtn) scrollDownBtn.hidden = true;
}

function chatOnScroll() {
  if (!scrollDownBtn) return;
  const atBottom = chat.scrollHeight - chat.scrollTop - chat.clientHeight < 260;
  scrollDownBtn.hidden = atBottom;
}

if (scrollDownBtn) {
  scrollDownBtn.onclick = () => chat.scrollTo({ top: chat.scrollHeight, behavior: "smooth" });
  chat.addEventListener("scroll", chatOnScroll, { passive: true });
}

document.querySelectorAll("#slashChips .chip.slash").forEach((b) => {
  b.onclick = () => {
    const s = b.dataset.slash;
    if (s === "/note ") { input.focus(); input.value = "/note "; input.setSelectionRange(input.value.length, input.value.length); autoResize(); }
    else send(s);
  };
});

async function openConversation(id) {
  if (!me) return;
  closeSidebar();
  try {
    const data = await api("/api/conversations/" + id + "?token=" + encodeURIComponent(me.token));
    currentConv = id;
    lastConvId = id;
    chat.innerHTML = "";
    data.items.forEach((m) => qMessage(m.role === "assistant" ? "ai" : "user", m.text));
    if (!data.items.length) showWelcome();
    refreshConversations();
  } catch (e) {
    if (e.status === 401) openAuth();
  }
}

/* ================= ommaviy ulashilgan suhbat (share havolasi) ================= */

async function loadPublicShare(code) {
  const composer = document.querySelector(".composer");
  try {
    const data = await api("/api/share/" + code);
    renderUser();
    showChat();
    const bar = document.createElement("div");
    bar.className = "share-note";
    bar.innerHTML =
      '<span>🔗 <b>' + esc(data.title || "Suhbat") + "</b> — <b>InomjonAI</b> da ulashilgan suhbat</span>" +
      '<button id="shareJoinBtn">Chatga kirish →</button>';
    document.querySelector(".main").insertBefore(bar, chat);
    document.getElementById("shareJoinBtn").onclick = () => { location.href = "/login"; };
    data.messages.forEach((m) => qMessage(m.role === "assistant" ? "ai" : "user", m.text));
    if (composer) composer.style.display = "none";
    if (modelSwitch) modelSwitch.style.display = "none";
    if (scrollDownBtn) scrollDownBtn.hidden = true;
    if (shareBtn) shareBtn.style.display = "none";
  } catch (e) {
    document.body.innerHTML = '<div style="min-height:100dvh;display:grid;place-items:center;text-align:center;padding:20px"><div><h2 style="margin:0 0 10px">Havola topilmadi yoki o\'chirilgan</h2><a href="/" style="color:var(--violet2)">← Bosh sahifaga qaytish</a></div></div>';
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
  location.href = mode === "register" ? "/register" : "/login";
}
function closeAuth() {}

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
  const avaHtml = me.avatar
    ? '<div class="user-ava"><img src="' + esc(me.avatar) + '" alt="avatar" /></div>'
    : '<div class="user-ava">' + esc(initial) + "</div>";
  sideUser.innerHTML =
    '<button class="user-card" id="userCard" title="Profil">' +
    avaHtml +
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

function openProfile() {
  if (!me) { openAuth(); return; }
  location.href = "/profile";
}
function closeProfile() {}

/* ================= API kaliti / Haqida ================= */

function openAbout() {
  location.href = "/about";
}

function openKeyModal() {
  if (!me) {
    openAuth();
    return;
  }
  location.href = "/api-key";
}

/* ================= landing interaktiv ================= */

document.getElementById("landingLoginBtn").onclick = () => openAuth("login");
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
  else if (chip.dataset.genType) genAudio(chip.dataset.genType);
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

if (loginTopBtn) loginTopBtn.onclick = () => openAuth("login");
aboutBtn.onclick = openAbout;
keyBtn.onclick = openKeyModal;
if (themeBtn) themeBtn.onclick = toggleTheme;

/* ================= mavzu (dark/light) ================= */

const THEME_KEY = "neura_theme";
const themeIcon = document.getElementById("themeIcon");

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem(THEME_KEY, t);
  if (themeIcon) themeIcon.setAttribute("d", t === "light"
    ? "M12 3v2m0 14v2M3 12h2m14 0h2M5.6 5.6l1.4 1.4m10 10l1.4 1.4M18.4 5.6L17 7m-10 10l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0z"
    : "M12 3a9 9 0 1 0 9 9c0-.46-.04-.92-.1-1.36a5.39 5.39 0 0 1-4.4 2.26 5.4 5.4 0 0 1-3.14-9.8c-.44-.06-.9-.1-1.36-.1z");
}

function toggleTheme() {
  const cur = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  applyTheme(cur);
  saveSettings();
}

function saveSettings() {
  const token = localStorage.getItem("neura_token");
  if (!token) return;
  const theme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  api("/api/settings", { method: "POST", body: JSON.stringify({ token, lang: currentLang || "uz", theme }) }).catch(() => {});
}

applyTheme(localStorage.getItem(THEME_KEY) || (window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));

/* ================= ovozli kiritish ================= */

let recognizing = false;
const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
if (micBtn && SpeechRec) {
  const rec = new SpeechRec();
  rec.lang = "uz-UZ";
  rec.interimResults = false;
  micBtn.onclick = () => {
    if (recognizing) { recognizing = false; rec.stop(); micBtn.classList.remove("rec"); return; }
    recognizing = true;
    micBtn.classList.add("rec");
    input.placeholder = "Gapiring...";
    try { rec.start(); } catch (e) {}
  };
  rec.onresult = (ev) => {
    const t = ev.results[0][0].transcript.trim();
    if (t) { input.value = t; autoResize(); send(t); }
  };
  rec.onend = () => {
    recognizing = false;
    micBtn.classList.remove("rec");
    input.placeholder = "InomjonAI ga so'rovingizni yozing...";
  };
  rec.onerror = () => {
    recognizing = false;
    micBtn.classList.remove("rec");
    input.placeholder = "InomjonAI ga so'rovingizni yozing...";
  };
} else if (micBtn && window.MediaRecorder && navigator.mediaDevices) {
  micBtn.onclick = () => {
    if (recognizing) {
      recognizing = false;
      micBtn.classList.remove("rec");
      input.value = "";
      autoResize();
      if (recorder && recorder.state !== "inactive") recorder.stop();
      input.placeholder = "InomjonAI ga so'rovingizni yozing...";
      return;
    }
    startRecorder();
  };
} else if (micBtn) {
  micBtn.hidden = true;
}

/* ================= audio generatsiya (musiqa / ovoz) ================= */

async function genAudio(kind) {
  if (!me) { openAuth(); return; }
  const label = kind === "music" ? "🎵 Musiqa uchun tavsif kiriting (masalan: \"sekin lirik pianino\")" : "🎙️ Ovoz uchun matn kiriting";
  const q = prompt(label);
  if (!q || !q.trim()) return;
  if (sending) return;
  sending = true;
  sendBtn.disabled = true;
  hideChips();
  qMessage("user", (kind === "music" ? "🎵 Musiqa: " : "🎙️ Ovoz: ") + q.trim());
  const typing = typingRow();
  try {
    const res = await fetch("/api/generate-" + kind, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(kind === "music"
        ? { token: me.token, prompt: q.trim(), title: q.trim().slice(0, 60) }
        : { token: me.token, prompt: q.trim() }),
    });
    const data = await res.json();
    if (!res.ok) throw Object.assign(new Error(data.error || "xato"), { status: res.status });
    typing.remove();
    qAudio(data.audio_url);
    confettiBurst();
  } catch (e) {
    typing.remove();
    qMessage("ai", "⚠️ Generatsiya xatosi: " + (e.message || "qayta urinib ko'ring"));
  }
  sending = false;
  sendBtn.disabled = false;
}

function qAudio(url) {
  if (!url) return;
  const row = document.createElement("div");
  row.className = "msg-row ai";
  row.innerHTML =
    '<div class="msg-bubble ai"><div class="msg-text">🔊 Tayyor:</div>' +
    '<audio controls preload="none" class="audio-player" src="' + esc(url) + '"></audio></div>';
  chat.appendChild(row);
  chat.scrollTo({ top: chat.scrollHeight, behavior: "smooth" });
  return row;
}

/* ================= suhbat amallari (nomlash / o'chirish / eksport) ================= */

async function renameConversation(id) {
  if (!me) return;
  const c = convItems.find((x) => x.id === id);
  const name = prompt("Suhbat nomini kiriting:", c ? c.title : "");
  if (!name || !name.trim()) return;
  try {
    await api("/api/rename", {
      method: "POST",
      body: JSON.stringify({ token: me.token, conversation_id: id, name: name.trim() }),
    });
    refreshConversations();
  } catch (e) { alert(e.message); }
}

async function deleteConversation(id) {
  if (!me) return;
  if (!confirm("Bu suhbatni o'chirishni xohlaysizmi?")) return;
  try {
    await api("/api/conversations/" + id + "?token=" + encodeURIComponent(me.token), { method: "DELETE" });
    if (currentConv === id) newChat();
    else refreshConversations();
  } catch (e) { alert(e.message); }
}

function exportConversation(id) {
  if (!me) return;
  const c = convItems.find((x) => x.id === id);
  api("/api/conversations/" + id + "?token=" + encodeURIComponent(me.token)).then((data) => {
    const txt = (c ? c.title + "\n" : "") + data.items
      .map((m) => (m.role === "assistant" ? "AI: " : "Siz: ") + m.text)
      .join("\n\n");
    const blob = new Blob([txt], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (c ? c.title : "suhbat") + ".txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }).catch(() => {});
}

/* ================= ulashish / qidiruv / galereya ================= */

function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.hidden = false;
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.hidden = true;
}
document.querySelectorAll("[data-close]").forEach((b) => {
  b.onclick = () => closeModal(b.dataset.close);
});

async function createShare() {
  if (!me) { openAuth(); return; }
  const convId = currentConv || lastConvId;
  if (!convId) {
    alert("Avval suhbatni boshlang — ulashish uchun kamida bitta xabar kerak.");
    return;
  }
  try {
    const data = await api("/api/share/create", {
      method: "POST",
      body: JSON.stringify({ token: me.token, conversation_id: convId }),
    });
    const full = (data.public_url && data.public_url.startsWith("http"))
      ? data.public_url
      : location.origin + data.url;
    const urlEl = document.getElementById("shareUrl");
    const delBtn = document.getElementById("shareDelBtn");
    const qrEl = document.getElementById("shareQr");
    urlEl.value = full;
    if (qrEl) {
      qrEl.src = "https://api.qrserver.com/v1/create-qr-code/?size=280x280&margin=8&qzone=1&color=8f7bff&bgcolor=ffffff&data=" + encodeURIComponent(full);
      qrEl.style.display = "block";
      qrEl.title = "Havolani skanerlang";
    }
    urlEl.value = full;
    delBtn.style.display = "block";
    delBtn.onclick = async () => {
      try {
        await api("/api/share/delete", {
          method: "POST",
          body: JSON.stringify({ token: me.token, conversation_id: convId }),
        });
        closeModal("shareModal");
        alert("Ulashish o'chirildi.");
      } catch (e) { alert(e.message); }
    };
    openModal("shareModal");
  } catch (e) {
    alert(e.message);
  }
}

const shareCopyBtn = document.getElementById("shareCopyBtn");
if (shareCopyBtn) {
  shareCopyBtn.onclick = async () => {
    const url = document.getElementById("shareUrl").value;
    if (!url || !navigator.clipboard) return;
    await navigator.clipboard.writeText(url);
    shareCopyBtn.textContent = "✓ Nusxalandi";
    setTimeout(() => { shareCopyBtn.textContent = "Nusxalash"; }, 1500);
  };
}
const shareTgBtn = document.getElementById("shareTgBtn");
if (shareTgBtn) {
  shareTgBtn.onclick = () => {
    const url = document.getElementById("shareUrl").value;
    if (!url) return;
    const msg = "🎉 InomjonAI da qiziqarli suhbat! Bu yerdan ko'ring: " + url;
    window.open("https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(msg), "_blank", "noopener");
  };
}
if (shareBtn) shareBtn.onclick = createShare;

/* ---------- qidiruv ---------- */

let searchTimer = null;
const searchInput = document.getElementById("searchInput");

async function runSearch(q) {
  const box = document.getElementById("searchResults");
  q = (q || "").trim();
  if (q.length < 2) {
    box.innerHTML = '<div class="search-empty">Kamida 2 ta belgi yozing</div>';
    return;
  }
  if (!me) { openAuth(); return; }
  try {
    const data = await api("/api/search?q=" + encodeURIComponent(q) + "&token=" + encodeURIComponent(me.token));
    if (!data.results.length) {
      box.innerHTML = '<div class="search-empty">Natija topilmadi</div>';
      return;
    }
    box.innerHTML = "";
    data.results.forEach((m) => {
      const row = document.createElement("button");
      row.className = "search-item";
      row.innerHTML =
        '<span class="search-ico">' + (m.role === "assistant" ? "✦" : "👤") + "</span>" +
        '<span class="search-body"><span class="search-title">' + esc(m.conversation_title || "Suhbat") + "</span>" +
        '<span class="search-text">' + esc(String(m.text).slice(0, 120)) + "</span></span>" +
        '<span class="search-date">' + fmtDate(m.created_at) + "</span>";
      row.onclick = () => {
        closeModal("searchModal");
        openConversation(m.conversation_id);
      };
      box.appendChild(row);
    });
  } catch (e) {
    box.innerHTML = '<div class="search-empty">' + esc(e.message) + "</div>";
  }
}

if (searchInput) {
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => runSearch(searchInput.value), 350);
  });
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runSearch(searchInput.value);
  });
}
if (searchBtn) {
  searchBtn.onclick = () => {
    if (!me) { openAuth(); return; }
    openModal("searchModal");
    setTimeout(() => { searchInput && searchInput.focus(); }, 100);
    runSearch(searchInput && searchInput.value);
  };
}

/* ---------- rejalashtirilgan xabarlar ---------- */

const schedBtn = document.getElementById("schedBtn");
if (schedBtn) {
  schedBtn.onclick = () => {
    if (!me) { openAuth(); return; }
    openModal("schedModal");
    loadScheduled();
  };
}

async function loadScheduled() {
  const list = document.getElementById("schedList");
  if (!me) return;
  try {
    const d = await api("/api/schedule/list?token=" + encodeURIComponent(me.token));
    const items = d.items || [];
    if (!items.length) { list.innerHTML = '<div class="search-empty">Hali reja yo\'q.</div>'; return; }
    list.innerHTML = "";
    items.forEach((it) => {
      const div = document.createElement("div");
      div.className = "sched-item";
      div.innerHTML =
        '<div style="flex:1;overflow:hidden">' +
        '<div class="sched-text">' + esc(String(it.text || "").slice(0, 90)) + '</div>' +
        '<small style="color:var(--muted)">🕒 ' + esc(it.send_at || "") + (it.status === "sent" ? " · ✅ yuborildi" : "") + '</small>' +
        '</div>';
      if (it.status !== "sent") {
        const del = document.createElement("button");
        del.className = "mini-btn";
        del.textContent = "✕";
        del.style.marginLeft = "8px";
        del.onclick = async () => {
          try {
            await api("/api/schedule/delete", { method: "POST", body: JSON.stringify({ token: me.token, sched_id: it.id }) });
            loadScheduled();
          } catch (e) { toast(e.message); }
        };
        div.appendChild(del);
      }
      list.appendChild(div);
    });
  } catch (e) {
    list.innerHTML = '<div class="search-empty">Xato: ' + esc(e.message) + '</div>';
  }
}

const schedAddBtn = document.getElementById("schedAddBtn");
if (schedAddBtn) {
  schedAddBtn.onclick = async () => {
    const text = document.getElementById("schedText").value.trim();
    const at = document.getElementById("schedAt").value;
    if (text.length < 2) { toast("Xabar matnini yozing"); return; }
    if (!at) { toast("Vaqtni tanlang"); return; }
    try {
      const d = await api("/api/schedule/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: me.token, text, send_at: at }),
      });
      document.getElementById("schedText").value = "";
      document.getElementById("schedAt").value = "";
      toast("✅ Reja qo'shildi (" + d.send_at + ")");
      loadScheduled();
    } catch (e) { toast(e.message); }
  };
}

/* ---------- galereya ---------- */

let galleryKind = "";

async function loadGallery(kind) {
  const grid = document.getElementById("galleryGrid");
  if (!me) return;
  galleryKind = kind || "";
  grid.innerHTML = '<div class="search-empty">Yuklanmoqda...</div>';
  try {
    const data = await api("/api/gallery?kind=" + encodeURIComponent(galleryKind) + "&token=" + encodeURIComponent(me.token));
    if (!data.items.length) {
      grid.innerHTML = '<div class="search-empty">Hali media yo\'q. Chatda 🎨 Rasm yoki 🎬 Video yaratib ko\'ring!</div>';
      return;
    }
    grid.innerHTML = "";
    data.items.forEach((it) => {
      const card = document.createElement("div");
      card.className = "g-item";
      const cap = esc(it.prompt ? String(it.prompt).slice(0, 60) : it.kind);
      if (it.kind === "video") {
        card.innerHTML = '<video src="' + esc(it.url) + '" muted loop preload="metadata"></video><span class="g-cap">' + cap + "</span>";
        card.onclick = () => { card.querySelector("video").paused ? card.querySelector("video").play() : card.querySelector("video").pause(); };
      } else if (it.kind === "image") {
        card.innerHTML = '<img src="' + esc(it.url) + '" alt="' + cap + '" loading="lazy" /><span class="g-cap">' + cap + "</span>";
        card.onclick = () => window.open(it.url, "_blank", "noopener");
      } else {
        card.innerHTML = '<audio controls preload="none" src="' + esc(it.url) + '"></audio><span class="g-cap">' + cap + "</span>";
      }
      grid.appendChild(card);
    });
  } catch (e) {
    grid.innerHTML = '<div class="search-empty">' + esc(e.message) + "</div>";
  }
}

if (galleryBtn) {
  galleryBtn.onclick = () => {
    if (!me) { openAuth(); return; }
    openModal("galleryModal");
    loadGallery("");
  };
}
const galleryTabs = document.getElementById("galleryTabs");
if (galleryTabs) {
  galleryTabs.onclick = (e) => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    galleryTabs.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    loadGallery(tab.dataset.kind);
  };
}

let lastConvId = null;

/* ================= bildirishnoma ovozi ================= */

let audioCtx = null;
function ding() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sine";
    o.frequency.value = 880;
    g.gain.setValueAtTime(0.0001, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.12, audioCtx.currentTime + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.35);
    o.connect(g).connect(audioCtx.destination);
    o.start();
    o.stop(audioCtx.currentTime + 0.4);
  } catch (e) {}
}

/* ================= boshlash ================= */

if ("speechSynthesis" in window) {
  speechSynthesis.getVoices();
  speechSynthesis.addEventListener("voiceschanged", () => speechSynthesis.getVoices());
}

async function boot() {
  loadLocalAI();
  const shareMatch = location.pathname.match(/^\/share\/([A-Za-z0-9_-]+)/);
  if (shareMatch) {
    loadPublicShare(shareMatch[1]);
    return;
  }

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
        avatar: u.avatar || "",
        daily_limit: u.daily_limit || 0,
        daily_used: u.daily_used || 0,
        premium_plan: u.premium_plan || "free",
      };
      cacheUser(me);
      renderUser();
      showChat();
      updateLimitBadge();
      currentConv = null;
      api("/api/settings?token=" + encodeURIComponent(token)).then((s) => {
        if (s && s.lang) { currentLang = s.lang; applyLang(); }
        if (s && s.theme) applyTheme(s.theme);
      }).catch(() => {});
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
      "perspective(1100px) rotateX(" + ((0.5 - py) * 16).toFixed(2) + "deg) rotateY(" + ((px - 0.5) * 18).toFixed(2) + "deg) translateZ(14px)";
    el.style.setProperty("--mx", px.toFixed(3));
    el.style.setProperty("--my", py.toFixed(3));
    el.querySelectorAll("[data-z]").forEach((c) => {
      c.style.transform = "translateZ(" + c.dataset.z + "px)";
    });
  });
  el.addEventListener("pointerleave", () => {
    el.style.removeProperty("transform");
    el.style.removeProperty("--mx");
    el.style.removeProperty("--my");
    el.querySelectorAll("[data-z]").forEach((c) => { c.style.removeProperty("transform"); });
  });
}

function bindAllTilt() {
  document.querySelectorAll(".tilt3d").forEach((el, i) => {
    if (!el.dataset.tilted) {
      el.dataset.tilted = "1";
      bindTilt(el);
      if (!reduceMotion) {
        el.style.setProperty("--fd", (7 + (i % 5)) + "s");
        el.style.animationDelay = "-" + (i % 9) + "s";
      }
    }
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

/* ================= 99D — jonli sayt effektlari ================= */

// 1) aylanuvchi so'z (hero sarlavhada)
const rotWord = document.getElementById("rotWord");
const ROT_WORDS = ["suhbat", "chat", "kod yozish", "rasm yaratish", "tarjima", "video", "savollarga javob"];
if (rotWord && !reduceMotion) {
  let ri = 0;
  setInterval(() => {
    ri = (ri + 1) % ROT_WORDS.length;
    rotWord.classList.add("out");
    setTimeout(() => {
      rotWord.textContent = ROT_WORDS[ri];
      rotWord.classList.remove("out");
    }, 380);
  }, 2400);
}

// 2) yuguruvchi lenta (ticker) — imkoniyatlar
const tickerTrack = document.getElementById("tickerTrack");
if (tickerTrack) {
  const tkItems = ["⚡ Tez javob", "🧠 Aqlli fikrlash", "🎨 Rasm yaratish", "🎬 Video", "🎵 Musiqa / Ovoz", "🌍 Internet qidiruvi", "💻 Kod yozish", "📷 Rasm tahlili", "🔑 Bepul API"];
  const mk = () => tkItems.map((t) => "<span>" + t + "</span><i class='tk-star'>✦</i>").join("");
  tickerTrack.innerHTML = mk() + mk();
}

// 3) skroll-reveal — bo'limlar jonlanadi
if ("IntersectionObserver" in window) {
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        en.target.classList.add("rv-in");
        en.target.querySelectorAll("[data-st]").forEach((c, i) => {
          c.style.transitionDelay = ((i % 4) * 90 + 40) + "ms";
        });
        io.unobserve(en.target);
      });
    },
    { threshold: 0.12 }
  );
  document.querySelectorAll(".rv").forEach((el) => io.observe(el));
  // xavfsizlik to'rigi: 3.5s ichida ko'rinmay qolgan bo'limlarni ochish
  setTimeout(() => {
    document.querySelectorAll(".rv:not(.rv-in)").forEach((el) => {
      if (el.getBoundingClientRect().top < window.innerHeight) el.classList.add("rv-in");
    });
  }, 3500);
} else {
  document.querySelectorAll(".rv").forEach((el) => el.classList.add("rv-in"));
}

// 4) hisoblagichlar (hero-stats: 2 model / 4 platforma / 24)
function animateCount(el, target) {
  const t0 = performance.now();
  const dur = 1100;
  const tick = (t) => {
    const p = Math.min((t - t0) / dur, 1);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
function countUp(el, target) {
  if (reduceMotion) { el.textContent = target; return; }
  animateCount(el, target);
}
(function counters() {
  const stats = document.querySelector(".hero-stats");
  const els = document.querySelectorAll("[data-count]");
  if (!els.length || !stats) return;
  const run = () => els.forEach((el) => countUp(el, +el.dataset.count));
  if (!reduceMotion && "IntersectionObserver" in window) {
    const io2 = new IntersectionObserver((en) => {
      en.forEach((e) => {
        if (e.isIntersecting) { run(); io2.disconnect(); }
      });
    }, { threshold: 0.4 });
    io2.observe(stats);
  } else {
    run();
  }
})();

// 5) tugmalar bosilganda suv tomchisi (ripple)
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-primary, .l-cta, .auth-submit, .send-btn, .chip");
  if (!btn || reduceMotion) return;
  const r = btn.getBoundingClientRect();
  const d = Math.max(r.width, r.height);
  const sp = document.createElement("span");
  sp.className = "ripple";
  sp.style.width = d + "px";
  sp.style.height = d + "px";
  sp.style.left = (e.clientX - r.left - d / 2) + "px";
  sp.style.top = (e.clientY - r.top - d / 2) + "px";
  btn.appendChild(sp);
  setTimeout(() => sp.remove(), 600);
});

/* ================= 99999D — jonli AI tarmog'i ================= */

// 6) neural-network canvas — butun sayt fonida tirik tarmoq
(function neuralNet() {
  const cv = document.getElementById("neuralNet");
  if (!cv || reduceMotion || !window.matchMedia("(pointer: fine)").matches) return;
  const ctx = cv.getContext("2d");
  const DPR = Math.min(window.devicePixelRatio || 1, 1.5);
  let W = 0, H = 0, nodes = [];
  function resz() {
    W = cv.width = Math.floor(window.innerWidth * DPR);
    H = cv.height = Math.floor(window.innerHeight * DPR);
    const n = Math.min(90, Math.floor((window.innerWidth * window.innerHeight) / 24000));
    nodes = Array.from({ length: n }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.24 * DPR,
      vy: (Math.random() - 0.5) * 0.24 * DPR,
      r: (Math.random() * 1.6 + 0.8) * DPR,
    }));
  }
  resz();
  window.addEventListener("resize", resz);
  const mouse = { x: -99999, y: -99999 };
  window.addEventListener("pointermove", (e) => {
    mouse.x = e.clientX * DPR; mouse.y = e.clientY * DPR;
  }, { passive: true });
  let running = true;
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) requestAnimationFrame(loop);
  });
  const LINK = 130 * DPR, MJ = 240 * DPR;
  function loop() {
    if (!running) return;
    ctx.clearRect(0, 0, W, H);
    for (const n of nodes) {
      n.x += n.vx; n.y += n.vy;
      if (n.x < -20) n.x = W + 20; else if (n.x > W + 20) n.x = -20;
      if (n.y < -20) n.y = H + 20; else if (n.y > H + 20) n.y = -20;
      const dx = mouse.x - n.x, dy = mouse.y - n.y, d2 = dx * dx + dy * dy;
      if (d2 < MJ * MJ) {
        const dd = Math.sqrt(d2) || 1;
        const f = (1 - Math.sqrt(d2) / MJ) * 0.022;
        n.vx += (dx / dd) * f; n.vy += (dy / dd) * f;
      }
      n.vx *= 0.996; n.vy *= 0.996;
    }
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < LINK) {
          ctx.strokeStyle = "rgba(120,140,255," + (0.15 * (1 - d / LINK)).toFixed(3) + ")";
          ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
    }
    for (const n of nodes) {
      ctx.fillStyle = "rgba(34,211,238,0.75)";
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 6.2832); ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,0.95)";
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r * 0.35, 0, 6.2832); ctx.fill();
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();

// 7) skroll progress-bari (yuqorida holo chiziq)
(function scrollProgress() {
  const pb = document.getElementById("progressBar");
  if (!pb) return;
  let busy = false;
  window.addEventListener(
    "scroll",
    () => {
      if (busy) return;
      busy = true;
      requestAnimationFrame(() => {
        const st = document.documentElement.scrollTop || document.body.scrollTop || 0;
        const max = document.documentElement.scrollHeight - window.innerHeight;
        pb.style.transform = "scaleX(" + (max > 0 ? Math.min(st / max, 1) : 0) + ")";
        busy = false;
      });
    },
    { passive: true }
  );
})();

// 8) kursor yorug'ligi (silliq suzib boruvchi holo nur)
(function cursorGlow() {
  const g = document.getElementById("cursorGlow");
  if (!g || reduceMotion || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
  let tx = window.innerWidth / 2, ty = window.innerHeight / 2, cx = tx, cy = ty;
  window.addEventListener("pointermove", (e) => {
    tx = e.clientX; ty = e.clientY;
    g.style.opacity = 1;
  }, { passive: true });
  document.documentElement.addEventListener("mouseleave", () => { g.style.opacity = 0; });
  (function step() {
    cx += (tx - cx) * 0.12;
    cy += (ty - cy) * 0.12;
    g.style.transform = "translate(" + cx.toFixed(1) + "px," + cy.toFixed(1) + "px)";
    requestAnimationFrame(step);
  })();
})();

// 9) o'zgaruvchan placeholder (chat kiritish maydoni)
(function placeholders() {
  const inp = document.getElementById("input");
  if (!inp) return;
  const list = [
    "InomjonAI ga savol yozing...",
    "Masalan: 'Python dastur yozib ber'",
    "Masalan: 'kosmos rasmini yarat'",
    "Masalan: 'video: quyosh botishi'",
    "Tarjima qil: 'salom dunyo'",
  ];
  let i = 0;
  if (reduceMotion) return;
  setInterval(() => {
    if (document.hidden || inp.value) return;
    i = (i + 1) % list.length;
    inp.placeholder = list[i];
  }, 3200);
})();

/* ================= Yangi: Til tanlash / i18n ================= */

// Offlayn/onlayn indikator
(function netWatch() {
  const st = document.querySelector(".status");
  if (!st) return;
  const set = (on) => {
    st.classList.toggle("off", !on);
    st.innerHTML = on ? '<span class="dot"></span> Onlayn' : '<span class="dot"></span> Offlayn';
  };
  window.addEventListener("online", () => set(true));
  window.addEventListener("offline", () => set(false));
})();

function toast(msg) {
  let el = document.getElementById("toastBox");
  if (!el) {
    el = document.createElement("div");
    el.id = "toastBox";
    el.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:99999;max-width:86vw;padding:10px 16px;border-radius:12px;background:var(--accent,#7c5dfa);color:#fff;font-size:14px;box-shadow:0 6px 20px rgba(0,0,0,.25);opacity:0;transition:opacity .25s,transform .25s;pointer-events:none";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.opacity = "1";
  el.style.transform = "translateX(-50%) translateY(0)";
  clearTimeout(el._t);
  el._t = setTimeout(() => {
    el.style.opacity = "0";
    el.style.transform = "translateX(-50%) translateY(8px)";
  }, 2400);
}


const I18N = {
  uz: {
    newChat: "Yangi suhbat", convs: "Suhbatlarim", empty: "Hali suhbatlar yo'q.",
    empty2: "Birinchi savolingizni yozing!", search: "Qidiruv", gallery: "Galereya",
    share: "Ulashish", export: "Eksport", notes: "Notalar", lang: "Til",
    theme: "Tema", about: "InomjonAI haqida", login: "Kirish", online: "Onlayn",
    apk: "APK", exportModal: "Suhbatni eksport qilish", copy: "Nusxalash",
    download: "Yuklab olish (.txt)", saved: "Saqlangan", del: "O'chirish",
    save: "Saqlash", noNotes: "Notalar yo'q", noteTitle: "Nota sarlavhasi...",
    noteContent: "Nota matni...", cat: "Kategoriya (ixtiyoriy)",
  },
  ru: {
    new_yangi: "Новый чат", convs: "Мои чаты", empty: "Чатов пока нет.",
    q2: "Напишите первый вопрос!", search: "Поиск", export: "Экспорт",
    notes: "Заметки", lang: "Язык", theme: "Тема", about: "О InomjonAI",
    login: "Вход", online: "Онлайн", apk: "APK", exportModal: "Экспорт чата",
    copy: "Копировать", download: "Скачать (.txt)", saved: "Сохранено",
    del: "Удалить", save: "Сохранить", noNotes: "Нет заметок",
    noteTitle: "Заголовок заметки...", noteText: "Текст заметки...",
    cat: "Категория (необязательно)", share: "Поделиться",
  },
  en: {
    newChat: "New chat", convs: "My chats", empty: "No chats yet.",
    search: "Search", export: "Export", notes: "Notes", lang: "Language",
    theme: "Theme", about: "About InomjonAI", login: "Log in", online: "Online",
    apk: "APK", exportModal: "Export conversation", copy: "Copy",
    download: "Download (.txt)", saved: "Saved", del: "Delete",
    save: "Save", noNotes: "No notes", share: "Share",
  },
};

let currentLang = localStorage.getItem("neura_lang") || "uz";
function t(key) {
  const d = I18N[currentLang] || I18N.uz;
  return d[key] !== undefined ? d[key] : (I18N.uz[key] !== undefined ? I18N.uz[key] : key);
}
function applyLang() {
  localStorage.setItem("neura_lang", currentLang);
  const label = document.getElementById("langLabel");
  if (label) label.textContent = currentLang.toUpperCase();
  const map = { searchBtn: "search", exportBtn: "export", notesBtn: "notes", shareBtn: "share" };
  for (const [id, key] of Object.entries(map)) {
    const btn = document.getElementById(id);
    if (!btn) continue;
    const span = btn.querySelector("span:last-child");
    if (span) span.textContent = t(key);
  }
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-lang]");
  if (b) { currentLang = b.dataset.lang; applyLang(); saveSettings(); closeModal("langModal"); }
});
const langBtn = document.getElementById("langBtn");
if (langBtn) langBtn.addEventListener("click", () => openModal("langModal"));

/* ================= Yangi: Eksport ================= */

const exportBtn = document.getElementById("exportBtn");
const exportText = document.getElementById("exportText");
if (exportBtn) exportBtn.addEventListener("click", async () => {
  if (!localStorage.getItem("neura_token")) return;
  const convId = currentConv || 0;
  if (!convId) { toast("Avval suhbat oching"); return; }
  try {
    const d = await api(`/api/export?token=${encodeURIComponent(localStorage.getItem("neura_token"))}&conversation_id=${convId}`);
    exportText.value = d.text || "";
    openModal("exportModal");
  } catch (err) { toast(err.message); }
});
const exportCopyBtn = document.getElementById("exportCopyBtn");
if (exportCopyBtn) exportCopyBtn.addEventListener("click", () => {
  navigator.clipboard.writeText(exportText.value || "").then(() => toast(t("saved"))).catch(() => {});
});
const exportDownloadBtn = document.getElementById("exportDownloadBtn");
if (exportDownloadBtn) exportDownloadBtn.addEventListener("click", () => {
  const blob = new Blob([exportText.value || ""], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "neura-suhbat.txt"; a.click();
  URL.revokeObjectURL(a.href);
});
const exportPdfBtn = document.getElementById("exportPdfBtn");
if (exportPdfBtn) exportPdfBtn.addEventListener("click", async () => {
  const convId = getActiveConvId() || currentConv;
  if (!convId) { toast("Suhbat topilmadi"); return; }
  try {
    const res = await fetch(`/api/export?token=${encodeURIComponent(localStorage.getItem("neura_token") || "")}&conversation_id=${convId}&format=pdf`);
    if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.error || "PDF xatolik"); }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "neura-suhbat.pdf"; a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) { toast(e.message); }
});

function getActiveConvId() {
  const active = document.querySelector(".conv-item.active");
  return active ? (active.dataset.id || active.dataset.conv || "") : "";
}

/* ================= Notalar ================= */

const notesBtn = document.getElementById("notesBtn");
if (notesBtn) notesBtn.addEventListener("click", () => { loadNotes(); openModal("notesModal"); });
async function loadNotes() {
  const list = document.getElementById("notesList");
  if (!list) return;
  try {
    const d = await api(`/api/notes?token=${encodeURIComponent(localStorage.getItem("neura_token") || "")}`);
    list.innerHTML = "";
    if (!d.notes || d.notes.length === 0) {
      list.innerHTML = '<div class="search-empty">' + t("noNotes") + '</div>';
      return;
    }
    d.notes.forEach(n => {
      const el = document.createElement("div");
      el.className = "note-item";
      el.style.cssText = "padding:8px 10px;border-radius:10px;background:var(--accent-soft,rgba(124,93,250,.12));margin-bottom:6px;cursor:pointer";
      el.innerHTML = `<b>${esc(n.title)}</b><small style="display:block;color:#90a">${esc(n.category || "")} · ${fmtDate(n.created_at || n.updated_at || "")}</small>`;
      el.onclick = () => {
        loadNote(n.id);
      };
      list.appendChild(el);
    });
  } catch (e) { if (list) list.innerHTML = '<div class="search-empty">' + esc(e.message) + '</div>'; }
}
async function loadNote(id) {
  try {
    const d = await api(`/api/notes/detail?token=${encodeURIComponent(localStorage.getItem("neura_token") || "")}&id=${id}`);
    notHelper.prefill(d);
  } catch (e) { toast(e.message); }
}
const noteTitle = document.getElementById("noteTitle"), noteContent = document.getElementById("noteContent"),
      noteCat = document.getElementById("noteCategory"), noteId = document.getElementById("noteId");
const notHelper = {
  prefill(d) { noteId.value = d.id; noteTitle.value = d.title; noteContent.value = d.content; noteCat.value = d.category || ""; },
};
const noteSaveBtn = document.getElementById("noteSaveBtn");
if (noteSaveBtn) noteSaveBtn.addEventListener("click", async () => {
  const body = { token: localStorage.getItem("neura_token") || "", title: noteTitle.value, content: noteContent.value, category: noteCat.value, note_id: parseInt(noteId.value || 0) };
  try {
    const d = parseInt(noteId.value || 0) ? await api("/api/notes/update", { method: "POST", body: JSON.stringify(body) }) : await api("/api/notes/create", { method: "POST", body: JSON.stringify(body) });
    toast(t("saved")); if (d) { noteId.value = "0"; noteTitle.value = ""; noteContent.value = ""; noteCat.value = ""; loadNotes(); }
  } catch (e) { toast(e.message); }
});
const noteDelBtn = document.getElementById("noteDelBtn");
if (noteDelBtn) noteDelBtn.addEventListener("click", async () => {
  if (!noteId.value || noteId.value === "0") return;
  try {
    await api("/api/notes/delete", { method: "POST", body: JSON.stringify({ token: localStorage.getItem("neura_token") || "", note_id: parseInt(noteId.value) }) });
    noteId.value = "0"; noteTitle.value = ""; noteContent.value = ""; noteCat.value = "";
    loadNotes(); toast(t("del"));
  } catch (e) { toast(e.message); }
});

/* ================= Soz hammasi: til+chap localStorage'dan ================= */
(function initExtras() {
  applyLang();
})();

/* ================= Referal ================= */

const referalBtn = document.getElementById("referalBtn");
const referalModal = document.getElementById("referalModal");
if (referalBtn) referalBtn.addEventListener("click", async () => {
  if (!me) { openAuth(); return; }
  openModal("referalModal");
  const codeInput = document.getElementById("referalCode");
  const listBox = document.getElementById("referalList");
  try {
    const d = await api("/api/referral?token=" + encodeURIComponent(me.token));
    if (codeInput) codeInput.value = d.code || "";
    if (listBox) {
      if (!d.referrals || d.referrals.length === 0) {
        listBox.innerHTML = '<div class="search-empty">Hali referallar yo\'q. Kodni ulashing!</div>';
      } else {
        listBox.innerHTML = "";
        d.referrals.forEach((r) => {
          const el = document.createElement("div");
          el.style.cssText = "padding:8px 10px;border-radius:10px;background:var(--accent-soft,rgba(124,93,250,.12));margin-bottom:6px;font-size:13px";
          el.textContent = (r.username || r.telegram_id || r.id) + " · " + (r.created_at || "");
          listBox.appendChild(el);
        });
      }
    }
  } catch (e) { if (codeInput) codeInput.value = ""; if (listBox) listBox.innerHTML = '<div class="search-empty">' + esc(e.message) + '</div>'; }
});
const referalCopyBtn = document.getElementById("referalCopyBtn");
if (referalCopyBtn) referalCopyBtn.addEventListener("click", () => {
  const c = document.getElementById("referalCode");
  if (c && c.value) navigator.clipboard.writeText(c.value).then(() => toast(t("saved"))).catch(() => {});
});
const referalApplyBtn = document.getElementById("referalApplyBtn");
if (referalApplyBtn) referalApplyBtn.addEventListener("click", async () => {
  const code = (document.getElementById("referalApplyInput") || {}).value || "";
  if (!code.trim()) return;
  try {
    await api("/api/referral/apply", { method: "POST", body: JSON.stringify({ token: me.token, code: code.trim() }) });
    toast(t("saved"));
    document.getElementById("referalApplyInput").value = "";
  } catch (e) { toast(e.message); }
});

/* ================= Yangiliklar bloki ================= */

async function loadNews() {
  const sec = document.getElementById("news");
  if (!sec) return;
  try {
    const d = await fetch("/api/news").then((r) => r.json());
    const list = document.getElementById("newsList");
    const empty = document.getElementById("newsEmpty");
    if (!d || !d.ok || !d.items || d.items.length === 0) {
      if (empty) empty.hidden = false;
      return;
    }
    sec.style.display = "";
    list.innerHTML = "";
    const emojis = ["🌍", "🇺🇿", "💼", "⚽", "📈", "🏛", "🎯", "🌐"];
    d.items.forEach((it, i) => {
      if (!it.text || it.text.length < 20) return;
      const el = document.createElement("div");
      el.className = "news-item";
      const link = it.link
        ? ' <a href="' + esc(it.link) + '" target="_blank" rel="noopener">manba →</a>'
        : "";
      el.innerHTML = '<span class="n-emoji">' + (emojis[i % emojis.length]) + "</span><p>" + esc(it.text) + link + "</p>";
      list.appendChild(el);
    });
    if (list.children.length === 0 && empty) empty.hidden = false;
  } catch (e) {
    const empty = document.getElementById("newsEmpty");
    if (empty) empty.hidden = false;
  }
}
document.addEventListener("DOMContentLoaded", () => { setTimeout(loadNews, 1200); });
