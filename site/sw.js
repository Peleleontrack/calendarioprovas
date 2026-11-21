// Service worker: a app abre sem rede com a última versão das provas que viu.
// Mudar VERSION sempre que se quiser forçar a limpeza da cache antiga.
const VERSION = "provas-v1";
const SHELL = ["/", "/config.js", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/favicon-64.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// O Cache API não guarda respostas parciais (206); as listas do Supabase podem vir assim.
async function storable(res) {
  if (res.status !== 206) return res;
  const body = await res.clone().blob();
  return new Response(body, { status: 200, statusText: "OK", headers: res.headers });
}

async function networkFirst(req, key) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(key || req, await storable(res.clone()));
    return res;
  } catch (err) {
    const hit = await cache.match(key || req);
    if (hit) return hit;
    throw err;
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok || res.type === "opaque") cache.put(req, res.clone());
  return res;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;               // gravar provas, login: sempre direto à rede
  const url = new URL(req.url);

  // Supabase: só as provas e o estado da recolha (públicos). Nunca login nem o calendário pessoal.
  if (url.hostname.endsWith(".supabase.co")) {
    if (url.pathname === "/rest/v1/races" || url.pathname === "/rest/v1/meta") {
      event.respondWith(networkFirst(req));
    }
    return;
  }

  // Bibliotecas e tipos de letra de CDNs: mudam pouco
  if (url.hostname === "cdn.jsdelivr.net" || url.hostname.endsWith("fonts.googleapis.com") || url.hostname.endsWith("fonts.gstatic.com")) {
    event.respondWith(cacheFirst(req));
    return;
  }

  if (url.origin !== self.location.origin) return;

  // Páginas: rede primeiro (para apanhar versões novas), cache se estiver sem rede
  if (req.mode === "navigate") {
    event.respondWith(networkFirst(req, "/"));
    return;
  }
  event.respondWith(networkFirst(req));
});
