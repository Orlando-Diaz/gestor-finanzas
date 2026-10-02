// Gastos por categoría: cuánto llevas gastado en un periodo y, al elegir una categoría, sus movimientos por fecha.
import { api } from "../api.js";
import { categoriaPorId } from "../store.js";
import { $, $$, dinero, esc, etiquetaDia, hoyISO, nombreMes, periodoActual, primerDiaMes, sumarMes, ultimoDiaMes, fechaLarga } from "../util.js";
import { conectarFilas, htmlFilaMovimiento } from "./comun.js";

const POR_PAGINA = 30;
const RANGOS = [["mes", "Este mes"], ["3m", "3 meses"], ["anio", "Este año"], ["todo", "Todo"], ["fechas", "Fechas"]];
const est = { rango: "mes", desde: "", hasta: "", cat: null };

function limites() {
  const p = periodoActual();
  switch (est.rango) {
    case "mes": return { desde: primerDiaMes(p), hasta: ultimoDiaMes(p) };
    case "3m": return { desde: primerDiaMes(sumarMes(p, -2)), hasta: ultimoDiaMes(p) };
    case "anio": return { desde: `${p.anio}-01-01`, hasta: `${p.anio}-12-31` };
    case "todo": return { desde: "2000-01-01", hasta: "2999-12-31" };
    default: return { desde: est.desde || primerDiaMes(p), hasta: est.hasta || hoyISO() };
  }
}

function textoPeriodo() {
  const p = periodoActual();
  const { desde, hasta } = limites();
  switch (est.rango) {
    case "mes": return nombreMes(p);
    case "3m": return `${nombreMes(sumarMes(p, -2)).split(" ")[0]} – ${nombreMes(p).split(" ")[0]} de ${p.anio}`;
    case "anio": return `Año ${p.anio}`;
    case "todo": return "Todo el historial";
    default: return `${fechaLarga(desde)} – ${fechaLarga(hasta)}`;
  }
}

export default {
  titulo: () => "Gastos por categoría",
  atras: true,
  async render(main) {
    const { desde, hasta } = limites();
    const rangoInvalido = desde > hasta;
    main.innerHTML = `<div class="esqueleto" style="height:50px"></div><div class="esqueleto" style="height:120px"></div><div class="esqueleto"></div>`;
    const filas = rangoInvalido ? [] : await api.get("/resumen/por-categoria", { desde, hasta });
    const total = filas.reduce((s, c) => s + Number(c.total), 0);

    const cabecera = () => `<div class="fichas" role="group" aria-label="Periodo">${RANGOS.map(([v, n]) => `<button class="ficha" data-rango="${v}" aria-pressed="${v === est.rango}">${n}</button>`).join("")}</div>
      ${
        est.rango === "fechas"
          ? `<div class="dos" style="margin-bottom:12px"><div class="campo"><label for="g-desde">Desde</label><input id="g-desde" type="date" class="entrada" value="${esc(desde)}"></div>
              <div class="campo"><label for="g-hasta">Hasta</label><input id="g-hasta" type="date" class="entrada" value="${esc(hasta)}"></div></div>
              ${rangoInvalido ? `<p class="error" role="alert">La fecha inicial no puede ser posterior a la final.</p>` : ""}`
          : ""
      }`;

    const conectarCabecera = () => {
      $$("[data-rango]", main).forEach((b) => (b.onclick = () => {
        est.rango = b.dataset.rango;
        if (est.rango === "fechas" && !est.desde) Object.assign(est, { desde, hasta });
        this.render(main);
      }));
      $("#g-desde", main)?.addEventListener("change", (e) => { est.desde = e.target.value; this.render(main); });
      $("#g-hasta", main)?.addEventListener("change", (e) => { est.hasta = e.target.value; this.render(main); });
    };

    /* ----- Lista de categorías ----- */
    if (est.cat == null) {
      main.innerHTML = `${cabecera()}
        <section class="tarjeta resumen-gastos"><span class="suave pequeno">Total gastado · ${esc(textoPeriodo())}</span><span class="grande">${dinero(total)}</span></section>
        <section class="tarjeta"><h2>Por categoría</h2>${
          filas.length
            ? filas
                .map(
                  (c) => `<button class="cat-fila" data-cat="${c.categoria_id}" style="--c:${esc(c.color || "#6b7280")}"><span aria-hidden="true" style="font-size:1.25rem">${esc(c.icono || "•")}</span>
                    <span class="n">${esc(c.categoria)}</span><span class="v">${dinero(c.total)}<span class="pct">${Math.round(Number(c.porcentaje))}%</span></span>
                    <span class="barra" aria-hidden="true"><i style="width:${Math.max(2, Math.min(100, Number(c.porcentaje)))}%"></i></span></button>`,
                )
                .join("")
            : `<p class="vacio">No hay gastos en este periodo.</p>`
        }</section>
        ${filas.length ? `<p class="pequeno suave" style="text-align:center">Toca una categoría para ver sus movimientos.</p>` : ""}`;
      conectarCabecera();
      $$("[data-cat]", main).forEach((b) => (b.onclick = () => { est.cat = Number(b.dataset.cat); this.render(main); }));
      return;
    }

    /* ----- Movimientos de una categoría ----- */
    const info = filas.find((c) => c.categoria_id === est.cat);
    const cat = categoriaPorId(est.cat);
    let items = [];
    let pagina = 1;
    let cantidad = 0;

    const pintar = () => {
      const porDia = new Map();
      for (const t of items) porDia.set(t.fecha, [...(porDia.get(t.fecha) ?? []), t]);
      main.innerHTML = `${cabecera()}
        <div class="campo"><label for="g-cat">Categoría</label><select id="g-cat" class="entrada">
          ${filas.map((c) => `<option value="${c.categoria_id}" ${c.categoria_id === est.cat ? "selected" : ""}>${esc(c.icono || "")} ${esc(c.categoria)}</option>`).join("")}
          ${info ? "" : `<option value="${est.cat}" selected>${esc(cat?.nombre ?? "Categoría")}</option>`}</select></div>
        <section class="tarjeta resumen-gastos"><span class="suave pequeno">${esc(cat?.icono ?? "")} ${esc(info?.categoria ?? cat?.nombre ?? "")} · ${esc(textoPeriodo())}</span>
          <span class="grande">${dinero(info?.total ?? 0)}</span>
          <span class="suave pequeno">${cantidad} ${cantidad === 1 ? "movimiento" : "movimientos"}${info ? ` · ${Math.round(Number(info.porcentaje))}% de tus gastos` : ""}</span></section>
        ${
          items.length
            ? [...porDia].map(([dia, lista]) => `<h2 class="dia">${esc(etiquetaDia(dia))}</h2><section class="tarjeta" style="padding:4px 16px"><ul class="lista">${lista.map(htmlFilaMovimiento).join("")}</ul></section>`).join("")
            : `<section class="tarjeta"><div class="vacio"><strong>Sin gastos</strong>No hay movimientos de esta categoría en el periodo.</div></section>`
        }
        ${items.length < cantidad ? `<button class="btn secundario bloque" data-mas>Cargar más (${cantidad - items.length})</button>` : ""}
        <button class="btn secundario bloque" data-todas>Ver todas las categorías</button>`;
      conectarCabecera();
      $("#g-cat", main).onchange = (e) => { est.cat = Number(e.target.value); this.render(main); };
      $("[data-todas]", main).onclick = () => { est.cat = null; this.render(main); };
      conectarFilas(main, (id) => items.find((t) => t.id === id));
      $("[data-mas]", main)?.addEventListener("click", async (e) => { e.target.disabled = true; await cargar(pagina + 1); });
    };

    const cargar = async (n) => {
      const r = rangoInvalido ? { items: [], total: 0 } : await api.get("/transacciones", { desde, hasta, tipo: "GASTO", categoria_id: est.cat, pagina: n, por_pagina: POR_PAGINA });
      items = n === 1 ? r.items : [...items, ...r.items];
      pagina = n;
      cantidad = r.total;
      pintar();
    };
    await cargar(1);
  },
};
