const CACHE = "neura-ai-v6";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then(() => self.skipWaiting()));
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

  // NETWORK-FIRST: yangilanish har doim ko'rinsin, cache faqat offline uchun
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy)).catch(() => {});
        return res;
      })
      .catch(() =>
        caches.open(CACHE).then((c) => c.match(e.request).then((hit) => hit || Response.error()))
      )
  );
});