// Piezas de interfaz reutilizables: hoja inferior, avisos y botón con "cargando".
import { $, ICONOS, esc } from "./util.js";

let temporizador;
export function aviso(texto, tipo = "") {
  $(".aviso")?.remove();
  const el = document.createElement("div");
  el.className = `aviso ${tipo}`;
  el.setAttribute("role", "status");
  el.textContent = texto;
  document.body.append(el);
  clearTimeout(temporizador);
  temporizador = setTimeout(() => el.remove(), tipo === "alerta" ? 6000 : 3200);
}

/** Abre una hoja inferior. `montar(cuerpo, cerrar)` arma el contenido y conecta eventos. */
export function hoja(titulo, montar) {
  const anterior = document.activeElement;
  const telon = document.createElement("div");
  telon.className = "telon";
  const panel = document.createElement("div");
  panel.className = "hoja";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", titulo);
  panel.innerHTML = `<div class="asa"></div><div class="cabeza"><h2>${esc(titulo)}</h2>
    <button class="btn-icono" data-cerrar aria-label="Cerrar">${ICONOS.cerrar}</button></div><div class="cuerpo"></div>`;
  document.body.append(telon, panel);
  document.body.style.overflow = "hidden";

  const cerrar = () => {
    telon.remove();
    panel.remove();
    document.body.style.overflow = "";
    document.removeEventListener("keydown", alTeclear);
    anterior?.focus?.();
  };
  const alTeclear = (e) => e.key === "Escape" && cerrar();
  document.addEventListener("keydown", alTeclear);
  telon.addEventListener("click", cerrar);
  panel.querySelector("[data-cerrar]").addEventListener("click", cerrar);
  montar(panel.querySelector(".cuerpo"), cerrar);
  return cerrar;
}

/** Ejecuta `tarea` con el botón bloqueado; si falla, muestra el error dentro de `cuerpo`. */
export async function enviando(boton, cuerpo, tarea) {
  const textoOriginal = boton.textContent;
  boton.disabled = true;
  boton.textContent = "Guardando…";
  cuerpo.querySelector(".error")?.remove();
  try {
    await tarea();
  } catch (e) {
    const p = document.createElement("p");
    p.className = "error";
    p.setAttribute("role", "alert");
    p.textContent = e.message || "No se pudo completar la acción";
    boton.before(p);
    boton.disabled = false;
    boton.textContent = textoOriginal;
  }
}

export function confirmar(titulo, mensaje, textoBoton, accion) {
  hoja(titulo, (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<p class="suave" style="margin-bottom:16px">${esc(mensaje)}</p>
      <button class="btn peligro bloque" data-ok>${esc(textoBoton)}</button>
      <button class="btn secundario bloque" data-no style="margin-top:8px">Cancelar</button>`;
    $("[data-no]", cuerpo).onclick = cerrar;
    const ok = $("[data-ok]", cuerpo);
    ok.onclick = () =>
      enviando(ok, cuerpo, async () => {
        await accion();
        cerrar();
      });
  });
}
