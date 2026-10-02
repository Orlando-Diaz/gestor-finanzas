import { api } from "../api.js";
import { recargarConteo, recargarCuentas, store } from "../store.js";
import { $, $$, FRECUENCIAS, dinero, esc, fechaLarga, hoyISO, leerMonto } from "../util.js";
import { aviso, confirmar, enviando, hoja } from "../ui.js";
import { avisarCambio } from "./comun.js";

function formulario(rec, alGuardar) {
  let tipo = rec?.tipo ?? "GASTO";
  hoja(rec ? "Editar recurrente" : "Nuevo movimiento recurrente", (cuerpo, cerrar) => {
    const pintar = () => {
      const cats = store.categorias.filter((c) => c.tipo === tipo && (!c.archivada || c.id === rec?.categoria.id));
      cuerpo.innerHTML = `<form novalidate>
        ${rec ? "" : `<div class="segmentos" style="margin-bottom:14px">${[["GASTO", "Gasto"], ["INGRESO", "Ingreso"]].map(([v, n]) => `<button type="button" data-tipo="${v}" aria-pressed="${v === tipo}">${n}</button>`).join("")}</div>`}
        <div class="campo"><label for="r-nota">Nombre (ej: Arriendo, Salario)</label><input id="r-nota" class="entrada" maxlength="200" value="${esc(rec?.nota ?? "")}"></div>
        <div class="campo"><label for="r-monto">Monto</label><input id="r-monto" class="entrada" inputmode="decimal" value="${rec ? Number(rec.monto) : ""}"></div>
        <div class="campo"><label for="r-cat">Categoría</label><select id="r-cat" class="entrada">${cats.map((c) => `<option value="${c.id}" ${c.id === rec?.categoria.id ? "selected" : ""}>${esc(c.icono || "")} ${esc(c.nombre)}</option>`).join("")}</select></div>
        <div class="campo"><label for="r-cuenta">Cuenta</label><select id="r-cuenta" class="entrada">${store.cuentas.map((c) => `<option value="${c.id}" ${c.id === rec?.cuenta.id ? "selected" : ""}>${esc(c.nombre)}</option>`).join("")}</select></div>
        <div class="campo"><label for="r-frec">Se repite</label><select id="r-frec" class="entrada">${Object.entries(FRECUENCIAS).map(([v, n]) => `<option value="${v}" ${v === (rec?.frecuencia ?? "MENSUAL") ? "selected" : ""}>${n}</option>`).join("")}</select>
          <small class="suave">Quincenal cae los días 15 y último de cada mes.</small></div>
        <div class="dos">
          <div class="campo"><label for="r-fecha">${rec ? "Próxima fecha" : "Primera fecha"}</label><input id="r-fecha" type="date" class="entrada" value="${rec?.proxima_fecha ?? hoyISO()}"></div>
          <div class="campo"><label for="r-fin">Termina (opcional)</label><input id="r-fin" type="date" class="entrada" value="${rec?.fecha_fin ?? ""}"></div>
        </div>
        <button class="btn bloque" type="submit">Guardar</button>
        ${rec ? `<button class="btn secundario bloque" type="button" data-pausar style="margin-top:8px">${rec.activa ? "Pausar" : "Reactivar"}</button><button class="btn peligro bloque" type="button" data-borrar style="margin-top:8px">Eliminar</button>` : ""}</form>`;
      $$("[data-tipo]", cuerpo).forEach((b) => (b.onclick = () => { tipo = b.dataset.tipo; pintar(); }));
      const form = $("form", cuerpo);
      form.onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", form);
        const monto = leerMonto($("#r-monto", cuerpo).value);
        const falla = (m) => {
          $(".error", cuerpo)?.remove();
          boton.insertAdjacentHTML("beforebegin", `<p class="error" role="alert">${esc(m)}</p>`);
        };
        if (!monto) return falla("Escribe un monto mayor a cero.");
        if (!$("#r-cat", cuerpo).value || !$("#r-cuenta", cuerpo).value) return falla("Elige categoría y cuenta.");
        const datos = {
          monto, nota: $("#r-nota", cuerpo).value.trim() || null,
          categoria_id: Number($("#r-cat", cuerpo).value), cuenta_id: Number($("#r-cuenta", cuerpo).value),
          frecuencia: $("#r-frec", cuerpo).value, proxima_fecha: $("#r-fecha", cuerpo).value, fecha_fin: $("#r-fin", cuerpo).value || null,
        };
        enviando(boton, cuerpo, async () => {
          if (rec) await api.patch(`/recurrentes/${rec.id}`, datos);
          else await api.post("/recurrentes", { ...datos, tipo });
          cerrar();
          aviso("Recurrente guardado");
          alGuardar();
        });
      };
      $("[data-pausar]", cuerpo)?.addEventListener("click", (e) =>
        enviando(e.target, cuerpo, async () => {
          await api.patch(`/recurrentes/${rec.id}`, { activa: !rec.activa });
          cerrar();
          alGuardar();
        }),
      );
      $("[data-borrar]", cuerpo)?.addEventListener("click", () =>
        confirmar("¿Eliminar este recurrente?", "Los movimientos que ya registró se conservan.", "Eliminar", async () => {
          await api.borrar(`/recurrentes/${rec.id}`);
          cerrar();
          alGuardar();
        }),
      );
    };
    pintar();
  });
}

export default {
  titulo: () => "Recurrentes",
  atras: true,
  async render(main) {
    const lista = await api.get("/recurrentes");
    const recargar = async () => {
      await recargarCuentas();
      await recargarConteo();
      avisarCambio();
    };
    main.innerHTML = `<p class="suave pequeno">Arriendo, salario, suscripciones: se registran solos en su fecha.</p>
      ${
        lista.length
          ? `<section class="tarjeta" style="padding:4px 16px"><ul class="lista">${lista
              .map(
                (r) => `<li><button class="fila-mov" data-rec="${r.id}" style="--c:${esc(r.categoria.color || "#6b7280")};${r.activa ? "" : "opacity:.6"}">
              <span class="ico" aria-hidden="true">${esc(r.categoria.icono || "🔁")}</span>
              <span><span class="t" style="display:block">${esc(r.nota || r.categoria.nombre)}</span>
                <span class="s" style="display:block">${FRECUENCIAS[r.frecuencia]} · ${r.activa ? `próxima ${esc(fechaLarga(r.proxima_fecha))}` : "En pausa"}</span></span>
              <span class="monto ${r.tipo.toLowerCase()}">${r.tipo === "INGRESO" ? "+" : "−"}${dinero(r.monto)}</span></button></li>`,
              )
              .join("")}</ul></section>`
          : `<section class="tarjeta"><div class="vacio"><strong>Sin recurrentes</strong>Crea uno para tu arriendo, tu salario o una suscripción.</div></section>`
      }
      <button class="btn bloque" data-nuevo>Nuevo recurrente</button>
      ${lista.length ? `<button class="btn secundario bloque" data-procesar>Registrar los pendientes ahora</button>` : ""}`;
    const refrescar = () => recargar().then(() => this.render(main));
    $$("[data-rec]", main).forEach((b) => (b.onclick = () => formulario(lista.find((r) => r.id === Number(b.dataset.rec)), refrescar)));
    $("[data-nuevo]", main).onclick = () => formulario(null, refrescar);
    $("[data-procesar]", main)?.addEventListener("click", async (e) => {
      e.target.disabled = true;
      try {
        const { generadas } = await api.post("/recurrentes/procesar");
        aviso(generadas ? `Se registraron ${generadas} movimientos` : "No había nada pendiente");
        await refrescar();
      } catch (err) {
        aviso(err.message, "alerta");
        e.target.disabled = false;
      }
    });
  },
};
