/* JARVIS PWA service worker (Faz 2).
   - Statik kabuk (/, /assets/*): cache-first + arka planda güncelleme.
   - /api ve /ws: asla önbelleklenmez (canlı veri); çevrimdışında başarısız olur,
     UI zaten offline durumuna düşer.
*/
const CACHE = "jarvis-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.pathname.startsWith("/api") || url.pathname.startsWith("/ws")) return;

  // Statik varlıklar: cache-first, miss ise ağa düş ve önbelleğe yaz.
  event.respondWith(
    caches.match(event.request).then((hit) => {
      if (hit) return hit;
      return fetch(event.request)
        .then((resp) => {
          if (resp.ok && url.origin === self.location.origin) {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(event.request, copy));
          }
          return resp;
        })
        .catch(() =>
          url.pathname === "/" ? caches.match("/") : Response.error()
        );
    })
  );
});