// Piezas compartidas por varias pantallas: selector de mes, filas de movimientos y formulario de movimiento.
import { api } from "../api.js";
import { store, recargarConteo, recargarCuentas } from "../store.js";
import { $, $$, ICONOS, dinero, esc, hoyISO, leerMonto, mismoPeriodo, nombreMes, periodoActual, sumarMes } from "../util.js";
import { aviso, confirmar, enviando, hoja } from "../ui.js";

export const avisarCambio = () => window.dispatchEvent(new Event("mf:cambio"));

/* ---------- Selector de mes ---------- */
export function htmlSelectorMes(p) {
  const esActual = mismoPeriodo(p, periodoActual());
  return `<div class="mes"><button data-mes="-1" aria-label="Mes anterior">${ICONOS.izquierda}</button>
    <strong aria-live="polite">${esc(nombreMes(p))}</strong>
    <button data-mes="1" aria-label="Mes siguiente" ${esActual ? "disabled" : ""}>${ICONOS.derecha}</button></div>`;
}
export function conectarMes(raiz, p, alCambiar) {
  $$("[data-mes]", raiz).forEach((b) => (b.onclick = () => alCambiar(sumarMes(p, Number(b.dataset.mes)))));
}

/* ---------- Filas de movimientos ---------- */
export function htmlFilaMovimiento(t) {
  const transf = t.tipo === "TRANSFERENCIA";
  const icono = transf ? "↔️" : t.categoria?.icono || "•";
  const titulo = transf ? "Transferencia" : t.categoria?.nombre || "Sin categoría";
  const detalle = transf ? `${t.cuenta.nombre} → ${t.cuenta_destino?.nombre ?? "?"}` : t.cuenta.nombre;
  const signo = t.tipo === "INGRESO" ? "+" : t.tipo === "GASTO" ? "−" : "";
  const clase = t.tipo.toLowerCase();
  return `<li><button class="fila-mov" data-mov="${t.id}" style="--c:${esc(t.categoria?.color || "#6b7280")}">
    <span class="ico" aria-hidden="true">${esc(icono)}</span>
    <span><span class="t" style="display:block">${esc(titulo)}</span>
      <span class="s" style="display:block">${esc(t.nota ? `${t.nota} · ${detalle}` : detalle)}</span></span>
    <span class="monto ${clase}"><span class="solo-lectores">${t.tipo.toLowerCase()} </span>${signo}${dinero(t.monto)}</span></button></li>`;
}

/* ---------- Formulario de movimiento (crear y editar) ---------- */
const TEXTOS = {
  GASTO: { cuenta: "Pagado desde", titulo: "Nuevo gasto" },
  INGRESO: { cuenta: "Entra a", titulo: "Nuevo ingreso" },
  TRANSFERENCIA: { cuenta: "Sale de", titulo: "Nueva transferencia" },
};

// Mes que se está mirando: se comparte entre Inicio, Movimientos y Presupuestos.
export const estado = { periodo: periodoActual() };

const opcionesCuenta = (sel, extra = []) =>
  [...store.cuentas, ...extra.filter((e) => e && !store.cuentas.some((c) => c.id === e.id))]
    .map((c) => `<option value="${c.id}" ${c.id === sel ? "selected" : ""}>${esc(c.nombre)}</option>`)
    .join("");

/** `mov` = movimiento existente para editarlo; sin él se crea uno nuevo. */
export function abrirFormularioMovimiento(mov = null) {
  const editando = Boolean(mov);
  let tipo = mov?.tipo ?? "GASTO";
  let categoriaId = mov?.categoria?.id ?? null;

  if (!store.cuentas.length) {
    hoja("Falta una cuenta", (cuerpo, cerrar) => {
      cuerpo.innerHTML = `<p class="suave">Para registrar movimientos necesitas al menos una cuenta (efectivo, Nequi, banco…).</p>
        <a class="btn bloque" href="#/cuentas" style="margin-top:14px">Crear una cuenta</a>`;
      $("a", cuerpo).onclick = cerrar;
    });
    return;
  }

  hoja(editando ? "Editar movimiento" : TEXTOS[tipo].titulo, (cuerpo, cerrar) => {
    const pintar = () => {
      const transf = tipo === "TRANSFERENCIA";
      const cats = store.categorias.filter((c) => c.tipo === tipo && (!c.archivada || c.id === categoriaId));
      const cuentaSel = mov?.cuenta.id ?? store.cuentas[0].id;
      const destinoSel = mov?.cuenta_destino?.id ?? store.cuentas.find((c) => c.id !== cuentaSel)?.id;
      cuerpo.innerHTML = `<form novalidate>
        ${
          editando
            ? ""
            : `<div class="segmentos" role="group" aria-label="Tipo de movimiento" style="margin-bottom:12px">
          ${["GASTO", "INGRESO", "TRANSFERENCIA"].map((t) => `<button type="button" data-tipo="${t}" aria-pressed="${t === tipo}">${{ GASTO: "Gasto", INGRESO: "Ingreso", TRANSFERENCIA: "Transferencia" }[t]}</button>`).join("")}</div>`
        }
        <div class="monto-grande"><label for="f-monto" class="solo-lectores">Monto</label>
          <input id="f-monto" inputmode="decimal" autocomplete="off" placeholder="$ 0" value="${mov ? esc(String(Number(mov.monto))) : ""}"><small>Pesos</small></div>
        ${
          transf
            ? ""
            : `<div class="campo"><span class="etiqueta">Categoría</span><div class="cuadricula-cat" role="group" aria-label="Categoría">
          ${cats.map((c) => `<button type="button" class="cat-op" data-cat="${c.id}" aria-pressed="${c.id === categoriaId}"><span aria-hidden="true">${esc(c.icono || "•")}</span>${esc(c.nombre)}</button>`).join("")}</div></div>`
        }
        <div class="${transf ? "dos" : ""}">
          <div class="campo"><label for="f-cuenta">${TEXTOS[tipo].cuenta}</label>
            <select id="f-cuenta" class="entrada">${opcionesCuenta(cuentaSel, [mov?.cuenta])}</select></div>
          ${transf ? `<div class="campo"><label for="f-destino">Entra a</label><select id="f-destino" class="entrada">${opcionesCuenta(destinoSel, [mov?.cuenta_destino])}</select></div>` : ""}
        </div>
        <div class="campo"><label for="f-fecha">Fecha</label><input id="f-fecha" type="date" class="entrada" value="${mov?.fecha ?? hoyISO()}" max="2100-12-31"></div>
        <div class="campo"><label for="f-nota">Nota (opcional)</label><input id="f-nota" class="entrada" maxlength="255" value="${esc(mov?.nota ?? "")}" placeholder="Ej: almuerzo con Valeria"></div>
        <button class="btn bloque" type="submit">${editando ? "Guardar cambios" : "Guardar"}</button>
        ${editando ? `<button class="btn peligro bloque" type="button" data-borrar style="margin-top:8px">Eliminar movimiento</button>` : ""}
      </form>`;

      $$("[data-tipo]", cuerpo).forEach(
        (b) =>
          (b.onclick = () => {
            const guardado = { monto: $("#f-monto", cuerpo).value, nota: $("#f-nota", cuerpo).value, fecha: $("#f-fecha", cuerpo).value };
            tipo = b.dataset.tipo;
            categoriaId = null;
            $(".cabeza h2", cuerpo.parentElement).textContent = TEXTOS[tipo].titulo;
            pintar();
            $("#f-monto", cuerpo).value = guardado.monto;
            $("#f-nota", cuerpo).value = guardado.nota;
            $("#f-fecha", cuerpo).value = guardado.fecha;
          }),
      );
      $$("[data-cat]", cuerpo).forEach(
        (b) =>
          (b.onclick = () => {
            categoriaId = Number(b.dataset.cat);
            $$("[data-cat]", cuerpo).forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
          }),
      );
      if (editando) {
        $("[data-borrar]", cuerpo).onclick = () =>
          confirmar("¿Eliminar este movimiento?", "El saldo de tu cuenta se ajustará. No se puede deshacer.", "Eliminar", async () => {
            await api.borrar(`/transacciones/${mov.id}`);
            await recargarCuentas();
            cerrar();
            aviso("Movimiento eliminado");
            avisarCambio();
          });
      }
      const form = $("form", cuerpo);
      form.onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", form);
        const monto = leerMonto($("#f-monto", cuerpo).value);
        const fecha = $("#f-fecha", cuerpo).value;
        const cuentaId = Number($("#f-cuenta", cuerpo).value);
        const destinoId = transf ? Number($("#f-destino", cuerpo).value) : null;
        const nota = $("#f-nota", cuerpo).value.trim();
        const falla = (m) => {
          $(".error", cuerpo)?.remove();
          boton.insertAdjacentHTML("beforebegin", `<p class="error" role="alert">${esc(m)}</p>`);
        };
        if (!monto) return falla("Escribe un monto mayor a cero.");
        if (!fecha) return falla("Elige la fecha.");
        if (!transf && !categoriaId) return falla("Elige una categoría.");
        if (transf && cuentaId === destinoId) return falla("Elige dos cuentas distintas.");
        enviando(boton, cuerpo, async () => {
          let creado;
          const antes = store.noLeidas;
          if (editando) {
            const cambios = {};
            if (Number(monto) !== Number(mov.monto)) cambios.monto = monto;
            if (fecha !== mov.fecha) cambios.fecha = fecha;
            if (cuentaId !== mov.cuenta.id) cambios.cuenta_id = cuentaId;
            if (transf && destinoId !== mov.cuenta_destino?.id) cambios.cuenta_destino_id = destinoId;
            if (!transf && categoriaId !== mov.categoria?.id) cambios.categoria_id = categoriaId;
            if (nota !== (mov.nota ?? "")) cambios.nota = nota || null;
            if (Object.keys(cambios).length) creado = await api.patch(`/transacciones/${mov.id}`, cambios);
          } else {
            creado = await api.post("/transacciones", {
              tipo, monto, fecha, cuenta_id: cuentaId,
              ...(transf ? { cuenta_destino_id: destinoId } : { categoria_id: categoriaId }),
              ...(nota ? { nota } : {}),
            });
          }
          await recargarCuentas();
          cerrar();
          avisarCambio();
          await recargarConteo();
          if (creado && tipo === "GASTO" && store.noLeidas > antes) {
            const [ultima] = await api.get("/notificaciones", { solo_no_leidas: true, limite: 1 });
            if (ultima) return aviso(ultima.mensaje, "alerta");
          }
          aviso(editando ? "Cambios guardados" : "Movimiento guardado");
        });
      };
    };
    pintar();
    if (!editando) setTimeout(() => $("#f-monto", cuerpo)?.focus(), 50);
  });
}

/** Conecta los clics en filas de movimientos para abrir su edición. */
export function conectarFilas(raiz, porId) {
  $$("[data-mov]", raiz).forEach((b) => (b.onclick = () => abrirFormularioMovimiento(porId(Number(b.dataset.mov)))));
}
