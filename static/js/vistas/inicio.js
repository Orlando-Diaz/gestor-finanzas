import { api } from "../api.js";
import { barrasMensuales, lineaBalance } from "../graficas.js";
import { store } from "../store.js";
import { $, dinero, esc, nombreMes, primerDiaMes, ultimoDiaMes } from "../util.js";
import { abrirFormularioMovimiento, conectarFilas, conectarMes, estado, htmlFilaMovimiento, htmlSelectorMes } from "./comun.js";

const MAX_CATEGORIAS = 6;

function htmlCategorias(filas) {
  if (!filas.length) return `<p class="vacio">Sin gastos este mes.</p>`;
  const principales = filas.slice(0, MAX_CATEGORIAS);
  const resto = filas.slice(MAX_CATEGORIAS);
  const items = principales.map((c) => ({ nombre: c.categoria, icono: c.icono || "•", color: c.color || "#6b7280", total: c.total, pct: c.porcentaje }));
  if (resto.length) {
    items.push({
      nombre: `Otras (${resto.length})`, icono: "📦", color: "#6b7280",
      total: resto.reduce((s, c) => s + Number(c.total), 0), pct: resto.reduce((s, c) => s + Number(c.porcentaje), 0),
    });
  }
  return items
    .map(
      (c) => `<div class="cat-fila" style="--c:${esc(c.color)}"><span aria-hidden="true" style="font-size:1.25rem">${esc(c.icono)}</span>
        <span class="n">${esc(c.nombre)}</span><span class="v">${dinero(c.total)}<span class="pct">${Math.round(Number(c.pct))}%</span></span>
        <span class="barra" aria-hidden="true"><i style="width:${Math.max(2, Math.min(100, Number(c.pct)))}%"></i></span></div>`,
    )
    .join("");
}

export default {
  titulo: () => `Hola, ${store.usuario?.nombre?.split(" ")[0] ?? ""}`,
  async render(main) {
    const p = estado.periodo;
    const q = { anio: p.anio, mes: p.mes };
    main.innerHTML = `<div class="esqueleto" style="height:60px"></div><div class="esqueleto" style="height:190px"></div><div class="esqueleto"></div>`;
    const [resumen, porCat, serie, evol, movs] = await Promise.all([
      api.get("/resumen/mes", q),
      api.get("/resumen/por-categoria", q),
      api.get("/resumen/serie-mensual", { ...q, meses: 6 }),
      api.get("/resumen/evolucion-balance", { ...q, meses: 6 }),
      api.get("/transacciones", { desde: primerDiaMes(p), hasta: ultimoDiaMes(p), por_pagina: 5 }),
    ]);
    const total = store.cuentas.reduce((s, c) => s + Number(c.saldo_actual), 0);
    const balance = Number(resumen.balance);

    main.innerHTML = `${htmlSelectorMes(p)}
      <section class="billete" aria-label="Resumen de tu plata">
        <p class="rotulo">Tienes en total</p>
        <p class="total ${total < 0 ? "negativo" : ""}">${dinero(total)}</p>
        <div class="fila">
          <div><small>Ingresos de ${esc(nombreMes(p).split(" ")[0])}</small><b>${dinero(resumen.ingresos)}</b></div>
          <div><small>Gastos de ${esc(nombreMes(p).split(" ")[0])}</small><b>${dinero(resumen.gastos)}</b></div>
        </div>
      </section>
      <p class="pequeno suave" style="margin-top:-6px;text-align:center">${balance >= 0 ? "Este mes te sobran" : "Este mes gastaste de más"} <b style="color:var(--tinta)">${dinero(Math.abs(balance))}</b></p>
      ${
        store.cuentas.length
          ? `<div class="cuentas" role="list" aria-label="Tus cuentas">${store.cuentas
              .map((c) => `<a class="cuenta-chip" role="listitem" href="#/cuentas" style="text-decoration:none;color:inherit"><small>${esc(c.nombre)}</small><b>${dinero(c.saldo_actual)}</b></a>`)
              .join("")}</div>`
          : `<section class="tarjeta"><div class="vacio"><strong>Empieza creando una cuenta</strong>Registra dónde tienes tu plata: efectivo, Nequi, banco…<br><a class="btn" href="#/cuentas">Crear cuenta</a></div></section>`
      }
      <section class="tarjeta"><h2>En qué gastaste</h2>${htmlCategorias(porCat)}</section>
      <section class="tarjeta"><h2>Ingresos y gastos por mes</h2>
        <div class="leyenda"><span style="--c:var(--s1)">Ingresos</span><span style="--c:var(--s2)">Gastos</span></div><div class="grafica" id="g-barras"></div></section>
      <section class="tarjeta"><h2>Cómo crece tu plata</h2><div class="grafica" id="g-linea"></div></section>
      <section class="tarjeta"><div class="seccion-fila"><h2>Últimos movimientos</h2>${movs.items.length ? `<a class="enlace" href="#/movimientos" style="text-decoration:none">Ver todos</a>` : ""}</div>
        ${
          movs.items.length
            ? `<ul class="lista">${movs.items.map(htmlFilaMovimiento).join("")}</ul>`
            : `<div class="vacio"><strong>Nada registrado este mes</strong>Anota tu primer gasto o ingreso.<br><button class="btn" data-nuevo>Registrar movimiento</button></div>`
        }</section>`;

    barrasMensuales($("#g-barras", main), serie);
    lineaBalance($("#g-linea", main), evol);
    conectarMes(main, p, (nuevo) => {
      estado.periodo = nuevo;
      this.render(main);
    });
    conectarFilas(main, (id) => movs.items.find((t) => t.id === id));
    $("[data-nuevo]", main)?.addEventListener("click", () => abrirFormularioMovimiento());
  },
};
