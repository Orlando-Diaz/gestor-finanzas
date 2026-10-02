// Service worker: guarda la "carcasa" de la app para que abra sin conexión.
// Los datos (la API) NUNCA se guardan aquí: siempre vienen del servidor.
const CACHE = "mis-finanzas-v3";
const CARCASA = [
  "/",
  "/manifest.webmanifest",
  "/css/app.css",
  "/fonts/bricolage-grotesque-latin-wght-normal.woff2",
  "/fonts/figtree-latin-wght-normal.woff2",
  "/icons/icono.svg",
  "/icons/icono-192.png",
  "/js/main.js",
  "/js/api.js",
  "/js/graficas.js",
  "/js/store.js",
  "/js/ui.js",
  "/js/util.js",
  "/js/vistas/categorias.js",
  "/js/vistas/comun.js",
  "/js/vistas/cuentas.js",
  "/js/vistas/deudas.js",
  "/js/vistas/gastos.js",
  "/js/vistas/inicio.js",
  "/js/vistas/mas.js",
  "/js/vistas/metas.js",
  "/js/vistas/movimientos.js",
  "/js/vistas/notificaciones.js",
  "/js/vistas/presupuestos.js",
  "/js/vistas/recurrentes.js",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((c) => c.addAll(CARCASA)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nombres) => Promise.all(nombres.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

// Primero la red (así siempre ves la versión nueva); si no hay internet, lo guardado.
self.addEventListener("fetch", (evento) => {
  const { request } = evento;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  const esCarcasa = request.mode === "navigate" || CARCASA.includes(url.pathname);
  if (!esCarcasa) return; // API, /docs, etc.: directo a la red

  evento.respondWith(
    fetch(request)
      .then((respuesta) => {
        if (respuesta.ok && request.mode !== "navigate") {
          const copia = respuesta.clone();
          caches.open(CACHE).then((c) => c.put(request, copia));
        }
        return respuesta;
      })
      .catch(async () => (await caches.match(request)) || (request.mode === "navigate" ? caches.match("/") : Response.error())),
  );
});
