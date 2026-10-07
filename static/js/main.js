// Arranque de la app: acceso (login/registro), encabezado, navegación por hash y barra inferior.
import { ApiError, api, sesion } from "./api.js";
import { cargarBase, recargarConteo, store, vaciarStore } from "./store.js";
import { $, $$, ICONOS, esc } from "./util.js";
import { aviso } from "./ui.js";
import { abrirFormularioMovimiento } from "./vistas/comun.js";
import cuentas from "./vistas/cuentas.js";
import categorias from "./vistas/categorias.js";
import gastos from "./vistas/gastos.js";
import ingresos from "./vistas/ingresos.js";
import deudas from "./vistas/deudas.js";
import inicio from "./vistas/inicio.js";
import mas from "./vistas/mas.js";
import metas from "./vistas/metas.js";
import movimientos from "./vistas/movimientos.js";
import notificaciones from "./vistas/notificaciones.js";
import presupuestos from "./vistas/presupuestos.js";
import recurrentes from "./vistas/recurrentes.js";

const RUTAS = { inicio, movimientos, presupuestos, mas, cuentas, categorias, recurrentes, gastos, ingresos, metas, deudas, avisos: notificaciones };
const PESTANAS = [["inicio", "Inicio"], ["movimientos", "Movimientos"], null, ["presupuestos", "Presupuestos"], ["mas", "Más"]];
const raiz = $("#app");
let rutaActual = "inicio";
let versionPintado = 0;

/* ---------- Acceso ---------- */
function pantallaAcceso(modo = "entrar", mensaje = "") {
  document.title = "Mis Finanzas";
  const registro = modo === "registro";
  raiz.innerHTML = `<div class="acceso"><div class="marca"><h1>Mis Finanzas</h1><p>Lo que entra, lo que sale y cuánto te queda. Todo en tu bolsillo.</p></div>
    <form novalidate>
      ${mensaje ? `<p class="error" role="status" style="margin:0 0 12px">${esc(mensaje)}</p>` : ""}
      ${registro ? `<div class="campo"><label for="a-nombre">Nombre</label><input id="a-nombre" class="entrada" autocomplete="name" maxlength="100"></div>` : ""}
      <div class="campo"><label for="a-email">Correo</label><input id="a-email" class="entrada" type="email" inputmode="email" autocomplete="email" autocapitalize="none"></div>
      <div class="campo"><label for="a-clave">Contraseña${registro ? " (mínimo 8 caracteres)" : ""}</label><input id="a-clave" class="entrada" type="password" autocomplete="${registro ? "new-password" : "current-password"}"></div>
      <button class="btn bloque" type="submit" style="margin-bottom:14px">${registro ? "Crear mi cuenta" : "Entrar"}</button></form>
    <p class="cambiar">${registro ? "¿Ya tienes cuenta?" : "¿Primera vez aquí?"}
      <button data-modo>${registro ? "Inicia sesión" : "Crea tu cuenta"}</button></p></div>`;
  $("[data-modo]", raiz).onclick = () => pantallaAcceso(registro ? "entrar" : "registro");
  $("form", raiz).onsubmit = async (e) => {
    e.preventDefault();
    const boton = $("button[type=submit]", raiz);
    const email = $("#a-email", raiz).value.trim();
    const clave = $("#a-clave", raiz).value;
    $(".error", raiz)?.remove();
    boton.disabled = true;
    try {
      if (registro) await api.registro($("#a-nombre", raiz).value.trim(), email, clave);
      await api.login(email, clave);
      await arrancar();
    } catch (err) {
      boton.disabled = false;
      const texto = err instanceof ApiError && err.status === 401 ? "Correo o contraseña incorrectos." : err.message;
      boton.insertAdjacentHTML("beforebegin", `<p class="error" role="alert">${esc(texto)}</p>`);
    }
  };
}

/* ---------- Estructura principal ---------- */
function armarEstructura() {
  raiz.innerHTML = `<div class="banner-offline" id="offline" hidden>Sin conexión: verás los datos al volver a conectarte.</div>
    <header class="encabezado"><button class="btn-icono" id="atras" aria-label="Volver" hidden>${ICONOS.izquierda}</button><h1 id="titulo"></h1>
      <a class="btn-icono" href="#/avisos" aria-label="Avisos" id="campana">${ICONOS.campana}<span class="insignia" id="insignia" hidden></span></a></header>
    <main id="contenido" tabindex="-1"></main>
    <nav class="barra-inferior" aria-label="Principal">${PESTANAS.map((p) =>
      p ? `<a class="pestana" href="#/${p[0]}" data-ruta="${p[0]}">${ICONOS[p[0]]}${p[1]}</a>` : `<button class="fab" id="fab" aria-label="Registrar movimiento">${ICONOS.mas_grande}</button>`).join("")}</nav>`;
  $("#fab").onclick = () => abrirFormularioMovimiento();
  $("#atras").onclick = () => (history.length > 1 ? history.back() : (location.hash = "#/mas"));
  pintarInsignia();
}

function pintarInsignia() {
  const el = $("#insignia");
  if (!el) return;
  el.hidden = !store.noLeidas;
  el.textContent = store.noLeidas > 9 ? "9+" : store.noLeidas;
}

async function pintarRuta() {
  const nombre = (location.hash.replace(/^#\//, "") || "inicio").split("?")[0];
  rutaActual = RUTAS[nombre] ? nombre : "inicio";
  const vista = RUTAS[rutaActual];
  const main = $("#contenido");
  if (!main) return;
  const miVersion = ++versionPintado;
  // Cada pantalla se dibuja en su propio contenedor. Si el usuario cambia de pantalla mientras otra
  // sigue cargando, esa carga lenta escribe en un contenedor ya descartado y no pisa la pantalla nueva.
  // "display: contents" hace que los hijos sigan siendo, para el diseño de <main>, hijos directos.
  const pantalla = document.createElement("div");
  pantalla.style.display = "contents";
  main.replaceChildren(pantalla);
  $("#titulo").textContent = vista.titulo();
  document.title = `${vista.titulo()} · Mis Finanzas`;
  $("#atras").hidden = !vista.atras;
  $$(".pestana").forEach((p) => {
    const activa = p.dataset.ruta === rutaActual || (vista.atras && p.dataset.ruta === "mas");
    activa ? p.setAttribute("aria-current", "page") : p.removeAttribute("aria-current");
  });
  try {
    await vista.render(pantalla);
  } catch (e) {
    if (miVersion !== versionPintado) return;
    pantalla.innerHTML = `<section class="tarjeta"><div class="vacio"><strong>No se pudo cargar</strong>${esc(e.message)}<br><button class="btn" id="reintentar">Reintentar</button></div></section>`;
    $("#reintentar", pantalla).onclick = pintarRuta;
  }
}

async function arrancar() {
  try {
    await cargarBase();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return pantallaAcceso("entrar", "Tu sesión venció. Entra de nuevo.");
    raiz.innerHTML = `<div class="acceso"><div class="marca"><h1>Mis Finanzas</h1></div><p class="error">${esc(e.message)}</p><button class="btn" id="otra-vez">Reintentar</button></div>`;
    $("#otra-vez").onclick = arrancar;
    return;
  }
  armarEstructura();
  if (!location.hash) location.hash = "#/inicio";
  pintarRuta();
}

window.addEventListener("hashchange", () => $("#contenido") && pintarRuta());
window.addEventListener("mf:cambio", () => $("#contenido") && pintarRuta());
window.addEventListener("mf:conteo", pintarInsignia);
window.addEventListener("mf:sesion-vencida", (e) => {
  vaciarStore();
  location.hash = "";
  pantallaAcceso("entrar", e.detail?.vencida ? "Tu sesión venció. Entra de nuevo." : "");
});
window.addEventListener("online", () => ($("#offline") && ($("#offline").hidden = true), $("#contenido") && pintarRuta()));
window.addEventListener("offline", () => $("#offline") && ($("#offline").hidden = false));
document.addEventListener("visibilitychange", () => document.visibilityState === "visible" && store.usuario && recargarConteo());

if (sesion.token) arrancar();
else pantallaAcceso();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
