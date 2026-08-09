const CACHE = "neura-ai-v7";
const PRECACHE = ["/", "/static/app.js", "/static/style.css", "/static/icons/logo.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(PRECACHE).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (
    e.request.method !== "GET" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/static/icons/")
  ) {
    return;
  }

  // NETWORK-FIRST: yangilanish har doim ko'rinsin, cache offline uchun
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        }
        return res;
      })
      .catch(() =>
        caches
          .open(CACHE)
          .then((c) =>
            c
              .match(e.request)
              .then((hit) => hit || c.match("/") || c.match("/static/app.js") || Response.error())
          )
      )
  );
});

// Offline rejimda foydalanuvchiga bildirish
self.addEventListener("message", (e) => {
  if (e.data && e.data.type === "SKIP_WAITING") self.skipWaiting();
});