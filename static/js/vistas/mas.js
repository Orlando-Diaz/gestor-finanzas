import { api, sesion } from "../api.js";
import { store } from "../store.js";
import { $, ICONOS, emojiMenu, esc, hoyISO, periodoActual, primerDiaMes, ultimoDiaMes } from "../util.js";
import { aviso, enviando, hoja } from "../ui.js";

function descargar(blob, nombre) {
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

function exportar() {
  hoja("Exportar a Excel (CSV)", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<p class="suave" style="margin-bottom:14px">Se descarga un archivo que abre directo en Excel, con tildes y formato de Colombia.</p>
      <button class="btn bloque" data-mes>Solo este mes</button>
      <button class="btn secundario bloque" data-todo style="margin-top:8px">Todo el historial</button>`;
    const bajar = (boton, filtros, nombre) =>
      enviando(boton, cuerpo, async () => {
        const blob = await api.archivo("/exportar/transacciones", filtros);
        descargar(blob, nombre);
        cerrar();
        aviso("Archivo descargado");
      });
    $("[data-mes]", cuerpo).onclick = (e) => {
      const p = periodoActual();
      bajar(e.target, { desde: primerDiaMes(p), hasta: ultimoDiaMes(p) }, `movimientos-${p.anio}-${String(p.mes).padStart(2, "0")}.csv`);
    };
    $("[data-todo]", cuerpo).onclick = (e) => bajar(e.target, {}, `movimientos-${hoyISO()}.csv`);
  });
}

export function cerrarSesion() {
  sesion.limpiar();
  window.dispatchEvent(new Event("mf:sesion-vencida"));
}

function perfil() {
  hoja("Mi perfil", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<form novalidate>
      <div class="campo"><label for="u-nombre">Nombre</label><input id="u-nombre" class="entrada" maxlength="100" value="${esc(store.usuario.nombre)}"></div>
      <div class="campo"><span class="etiqueta">Correo</span><p>${esc(store.usuario.email)}</p></div>
      <button class="btn bloque" type="submit">Guardar nombre</button></form>
      <hr style="border:0;border-top:1px solid var(--linea);margin:18px 0">
      <button class="btn secundario bloque" data-clave>Cambiar contraseña</button>
      <button class="btn peligro bloque" data-eliminar style="margin-top:8px">Eliminar mi cuenta</button>`;
    const form = $("form", cuerpo);
    form.onsubmit = (e) => {
      e.preventDefault();
      const nombre = $("#u-nombre", cuerpo).value.trim();
      enviando($("button[type=submit]", form), cuerpo, async () => {
        store.usuario = await api.patch("/auth/me", { nombre });
        cerrar();
        aviso("Nombre actualizado");
        window.dispatchEvent(new Event("mf:cambio"));
      });
    };
    $("[data-clave]", cuerpo).onclick = () => {
      cerrar();
      cambiarClave();
    };
    $("[data-eliminar]", cuerpo).onclick = () => {
      cerrar();
      eliminarCuenta();
    };
  });
}

function cambiarClave() {
  hoja("Cambiar contraseña", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<form novalidate>
      <div class="campo"><label for="k-actual">Contraseña actual</label><input id="k-actual" type="password" autocomplete="current-password" class="entrada"></div>
      <div class="campo"><label for="k-nueva">Contraseña nueva (mínimo 8 caracteres)</label><input id="k-nueva" type="password" autocomplete="new-password" class="entrada"></div>
      <p class="pequeno suave" style="margin-bottom:12px">Al cambiarla se cierra la sesión en todos tus dispositivos.</p>
      <button class="btn bloque" type="submit">Cambiar contraseña</button></form>`;
    $("form", cuerpo).onsubmit = (e) => {
      e.preventDefault();
      enviando($("button[type=submit]", cuerpo), cuerpo, async () => {
        await api.post("/auth/cambiar-password", { password_actual: $("#k-actual", cuerpo).value, password_nueva: $("#k-nueva", cuerpo).value });
        cerrar();
        cerrarSesion();
        aviso("Contraseña cambiada. Inicia sesión con la nueva.");
      });
    };
  });
}

function eliminarCuenta() {
  hoja("Eliminar mi cuenta", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<p style="margin-bottom:14px">Se borran tu usuario y <b>todos</b> tus datos: cuentas, movimientos, presupuestos y recurrentes. No se puede deshacer.</p>
      <form novalidate><div class="campo"><label for="e-clave">Escribe tu contraseña para confirmar</label><input id="e-clave" type="password" autocomplete="current-password" class="entrada"></div>
      <button class="btn peligro bloque" type="submit">Eliminar todo</button></form>`;
    $("form", cuerpo).onsubmit = (e) => {
      e.preventDefault();
      enviando($("button[type=submit]", cuerpo), cuerpo, async () => {
        await api.post("/auth/eliminar-cuenta", { password: $("#e-clave", cuerpo).value });
        cerrar();
        cerrarSesion();
        aviso("Tu cuenta fue eliminada");
      });
    };
  });
}

const fila = (icono, texto, extra = "", cls = "") =>
  `<span aria-hidden="true" style="font-size:1.3rem">${icono}</span><span>${texto}</span>${extra || ICONOS.chevron}`;

export default {
  titulo: () => "Más",
  render(main) {
    main.innerHTML = `<section class="tarjeta" style="display:grid;gap:2px"><p style="font-family:var(--f-titulo);font-size:1.25rem;font-weight:700">${esc(store.usuario.nombre)}</p><p class="suave pequeno">${esc(store.usuario.email)}</p></section>
      <nav class="menu" aria-label="Más opciones">
        <a href="#/gastos">${fila(emojiMenu.gastos, "Gastos por categoría")}</a>
        <a href="#/metas">${fila(emojiMenu.metas, "Metas de ahorro")}</a>
        <a href="#/deudas">${fila(emojiMenu.deudas, "Deudas: me deben / debo")}</a>
        <a href="#/cuentas">${fila(emojiMenu.cuentas, "Mis cuentas")}</a>
        <a href="#/categorias">${fila(emojiMenu.categorias, "Categorías")}</a>
        <a href="#/recurrentes">${fila(emojiMenu.recurrentes, "Movimientos recurrentes")}</a>
        <a href="#/avisos">${fila(emojiMenu.notificaciones, "Avisos", store.noLeidas ? `<span class="insignia" style="position:static">${store.noLeidas}</span>` : "")}</a>
      </nav>
      <nav class="menu" aria-label="Cuenta">
        <button data-exportar>${fila(emojiMenu.exportar, "Exportar a Excel (CSV)")}</button>
        <button data-perfil>${fila(emojiMenu.perfil, "Mi perfil y contraseña")}</button>
        <button data-salir class="peligro">${fila(emojiMenu.salir, "Cerrar sesión", "<span></span>")}</button>
      </nav>
      <p class="pequeno suave" style="text-align:center">Mis Finanzas · tus datos viven en tu propio servidor</p>`;
    $("[data-exportar]", main).onclick = exportar;
    $("[data-perfil]", main).onclick = perfil;
    $("[data-salir]", main).onclick = cerrarSesion;
  },
};
