// Service Worker de InTeks Display — caché offline para el player.
// SOLO funciona en contexto seguro (localhost o HTTPS). En http://IP no se registra.
// Diseño SEGURO: nunca intercepta /api/ (datos/SSE) ni vídeos (HTTP Range) para no romperlos.
// v2: cambiar el nombre borra la caché anterior al activarse, y con ella el
// admin.html viejo que se había quedado guardado (el panel no mostraba lo nuevo).
const CACHE = 'signalos-v2';

// El panel de administración y su login SE PIDEN SIEMPRE AL SERVIDOR. Solo el
// player necesita funcionar sin red; el panel sin servidor no sirve para nada, y
// servirlo de la caché hacía que tras actualizar se siguiera viendo la versión vieja.
const SIN_CACHE = new Set(['/admin', '/admin.html', '/login.html', '/login']);

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(
  caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim())
));

function cacheable(url, req) {
  if (req.method !== 'GET') return false;
  if (url.pathname.startsWith('/api/')) return false;                 // datos y SSE: pasar siempre
  if (SIN_CACHE.has(url.pathname)) return false;                      // panel: siempre fresco
  if (/\.(mp4|webm|mov|m4v|ogg|ogv)$/i.test(url.pathname)) return false; // vídeo: lo maneja el navegador (Range)
  return true;
}

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;   // solo mismo origen (flagcdn/cdn quedan al navegador)
  if (!cacheable(url, e.request)) return;             // passthrough: API, SSE, vídeo
  // Cache-first + revalidación en segundo plano: reproduce offline lo último cacheado
  e.respondWith(caches.open(CACHE).then(async (cache) => {
    const cached = await cache.match(e.request);
    const network = fetch(e.request).then((resp) => {
      if (resp && resp.status === 200) cache.put(e.request, resp.clone());
      return resp;
    }).catch(() => cached);
    return cached || network;
  }));
});
