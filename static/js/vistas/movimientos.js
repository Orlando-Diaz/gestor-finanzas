import { api } from "../api.js";
import { $, $$, esc, etiquetaDia, primerDiaMes, ultimoDiaMes } from "../util.js";
import { abrirFormularioMovimiento, conectarFilas, conectarMes, estado, htmlFilaMovimiento, htmlSelectorMes } from "./comun.js";

const POR_PAGINA = 20;
const FILTROS = [["", "Todos"], ["GASTO", "Gastos"], ["INGRESO", "Ingresos"], ["TRANSFERENCIA", "Transferencias"]];
let tipoFiltro = "";

export default {
  titulo: () => "Movimientos",
  async render(main) {
    const p = estado.periodo;
    let items = [];
    let pagina = 1;
    let total = 0;

    const pintar = () => {
      const porDia = new Map();
      for (const t of items) porDia.set(t.fecha, [...(porDia.get(t.fecha) ?? []), t]);
      main.innerHTML = `${htmlSelectorMes(p)}
        <div class="fichas" role="group" aria-label="Filtrar por tipo">${FILTROS.map(([v, n]) => `<button class="ficha" data-tipo="${v}" aria-pressed="${v === tipoFiltro}">${n}</button>`).join("")}</div>
        ${
          items.length
            ? [...porDia]
                .map(([dia, lista]) => `<h2 class="dia">${esc(etiquetaDia(dia))}</h2><section class="tarjeta" style="padding:4px 16px"><ul class="lista">${lista.map(htmlFilaMovimiento).join("")}</ul></section>`)
                .join("")
            : `<section class="tarjeta"><div class="vacio"><strong>Sin movimientos</strong>No hay registros con este filtro en el mes.<br><button class="btn" data-nuevo>Registrar movimiento</button></div></section>`
        }
        ${items.length < total ? `<button class="btn secundario bloque" data-mas>Cargar más (${total - items.length})</button>` : ""}`;
      conectarMes(main, p, (nuevo) => {
        estado.periodo = nuevo;
        this.render(main);
      });
      $$("[data-tipo]", main).forEach((b) => (b.onclick = () => { tipoFiltro = b.dataset.tipo; this.render(main); }));
      conectarFilas(main, (id) => items.find((t) => t.id === id));
      $("[data-nuevo]", main)?.addEventListener("click", () => abrirFormularioMovimiento());
      $("[data-mas]", main)?.addEventListener("click", async (e) => {
        e.target.disabled = true;
        await cargar(pagina + 1);
      });
    };

    const cargar = async (n) => {
      const r = await api.get("/transacciones", { desde: primerDiaMes(p), hasta: ultimoDiaMes(p), tipo: tipoFiltro, pagina: n, por_pagina: POR_PAGINA });
      items = n === 1 ? r.items : [...items, ...r.items];
      pagina = n;
      total = r.total;
      pintar();
    };

    main.innerHTML = `<div class="esqueleto" style="height:60px"></div><div class="esqueleto"></div>`;
    await cargar(1);
  },
};
