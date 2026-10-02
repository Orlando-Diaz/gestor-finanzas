import { api } from "../api.js";
import { barrasDiarias, barrasMensuales, lineaBalance } from "../graficas.js";
import { store } from "../store.js";
import { $, dinero, esc, hoyISO, mismoPeriodo, nombreMes, periodoActual, primerDiaMes, sumarMes, ultimoDiaMes } from "../util.js";
import { htmlMeta, abrirMeta } from "./metas.js";
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

const mesSolo = (p) => {
  const m = nombreMes(p).split(" ")[0];
  return m.charAt(0).toUpperCase() + m.slice(1);
};

/** Este mes contra el anterior, categoría por categoría (las 6 con más gasto entre los dos meses). */
function htmlComparativo(actual, anterior, p) {
  const previo = new Map(anterior.map((c) => [c.categoria_id, c]));
  const filas = new Map();
  for (const c of actual) filas.set(c.categoria_id, { ...c, ahora: Number(c.total), antes: 0 });
  for (const c of anterior) {
    const f = filas.get(c.categoria_id) ?? { ...c, ahora: 0, antes: 0 };
    f.antes = Number(previo.get(c.categoria_id).total);
    filas.set(c.categoria_id, f);
  }
  const lista = [...filas.values()].sort((a, b) => b.ahora + b.antes - (a.ahora + a.antes)).slice(0, 6);
  if (!lista.length) return `<p class="vacio">Sin gastos en estos dos meses.</p>`;
  const max = Math.max(...lista.map((f) => Math.max(f.ahora, f.antes)));
  const delta = (f) => {
    if (f.antes === 0) return `<span class="delta">Nuevo</span>`;
    if (f.ahora === 0) return `<span class="delta">Sin gastos</span>`;
    const pct = Math.round(((f.ahora - f.antes) / f.antes) * 100);
    if (pct === 0) return `<span class="delta">Igual</span>`;
    return `<span class="delta">${pct > 0 ? "▲ +" : "▼ −"}${Math.abs(pct)}%</span>`;
  };
  const barra = (v, clase) =>
    `<span class="dupla"><span class="barra"><i class="${clase}" style="width:${v ? Math.max(2, (v / max) * 100) : 0}%"></i></span><span class="v">${dinero(v)}</span></span>`;
  return `<div class="leyenda"><span style="--c:var(--s2)">${esc(mesSolo(p))}</span><span style="--c:var(--tinta-3)">${esc(mesSolo(sumarMes(p, -1)))}</span></div>` +
    lista
      .map(
        (f) => `<div class="comp-fila"><div class="comp-cab"><span aria-hidden="true">${esc(f.icono || "•")}</span><span class="n">${esc(f.categoria)}</span>${delta(f)}</div>
          ${barra(f.ahora, "ahora")}${barra(f.antes, "antes")}</div>`,
      )
      .join("");
}

function resumenDias(dias, p) {
  const gastos = dias.map((d) => Number(d.gastos));
  const total = gastos.reduce((a, b) => a + b, 0);
  if (!total) return "";
  const transcurridos = mismoPeriodo(p, periodoActual()) ? Number(hoyISO().slice(8)) : dias.length;
  const mayor = gastos.indexOf(Math.max(...gastos));
  return `<p class="pequeno suave" style="margin:-4px 0 8px">Promedio: <b style="color:var(--tinta)">${dinero(total / transcurridos)}</b> por día · Día más alto: el ${mayor + 1} (${dinero(gastos[mayor])})</p>`;
}

export default {
  titulo: () => `Hola, ${store.usuario?.nombre?.split(" ")[0] ?? ""}`,
  async render(main) {
    const p = estado.periodo;
    const q = { anio: p.anio, mes: p.mes };
    main.innerHTML = `<div class="esqueleto" style="height:60px"></div><div class="esqueleto" style="height:190px"></div><div class="esqueleto"></div>`;
    const prev = sumarMes(p, -1);
    const [resumen, porCat, porCatPrev, dias, serie, evol, movs, metas, deudas] = await Promise.all([
      api.get("/resumen/mes", q),
      api.get("/resumen/por-categoria", q),
      api.get("/resumen/por-categoria", { anio: prev.anio, mes: prev.mes }),
      api.get("/resumen/por-dia", q),
      api.get("/resumen/serie-mensual", { ...q, meses: 6 }),
      api.get("/resumen/evolucion-balance", { ...q, meses: 6 }),
      api.get("/transacciones", { desde: primerDiaMes(p), hasta: ultimoDiaMes(p), por_pagina: 5 }),
      api.get("/metas").catch(() => []),
      api.get("/deudas/resumen").catch(() => null),
    ]);
    const metasActivas = metas.filter((m) => !m.cumplida).slice(0, 2);
    const hayDeudas = deudas && (Number(deudas.me_deben) > 0 || Number(deudas.debo) > 0);
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
      ${
        metasActivas.length
          ? `<section class="tarjeta"><div class="seccion-fila"><h2>Tus metas</h2><a class="enlace" href="#/metas" style="text-decoration:none">Ver todas</a></div>
              <div style="display:grid;gap:10px">${metasActivas.map((m) => htmlMeta(m, true)).join("")}</div></section>`
          : ""
      }
      ${
        hayDeudas
          ? `<a class="tarjeta" href="#/deudas" style="display:grid;grid-template-columns:1fr 1fr;gap:12px;text-decoration:none;color:inherit">
              <span><small class="suave">Te deben</small><b style="display:block;font-size:1.1rem">${dinero(deudas.me_deben)}</b></span>
              <span><small class="suave">Debes</small><b style="display:block;font-size:1.1rem">${dinero(deudas.debo)}</b></span>
              ${deudas.vencidas ? `<span class="pequeno" style="grid-column:1/-1;color:var(--gasto)">${deudas.vencidas} ${deudas.vencidas === 1 ? "deuda vencida" : "deudas vencidas"}</span>` : ""}
            </a>`
          : ""
      }
      <section class="tarjeta"><h2>En qué gastaste</h2>${htmlCategorias(porCat)}</section>
      <section class="tarjeta"><h2>Comparado con el mes pasado</h2>${htmlComparativo(porCat, porCatPrev, p)}</section>
      <section class="tarjeta"><h2>Gasto por día</h2>${resumenDias(dias, p)}<div class="grafica" id="g-dias"></div></section>
      <section class="tarjeta"><h2>Ingresos y gastos por mes</h2>
        <div class="leyenda"><span style="--c:var(--s1)">Ingresos</span><span style="--c:var(--s2)">Gastos</span></div><div class="grafica" id="g-barras"></div></section>
      <section class="tarjeta"><h2>Cómo crece tu plata</h2><div class="grafica" id="g-linea"></div></section>
      <section class="tarjeta"><div class="seccion-fila"><h2>Últimos movimientos</h2>${movs.items.length ? `<a class="enlace" href="#/movimientos" style="text-decoration:none">Ver todos</a>` : ""}</div>
        ${
          movs.items.length
            ? `<ul class="lista">${movs.items.map(htmlFilaMovimiento).join("")}</ul>`
            : `<div class="vacio"><strong>Nada registrado este mes</strong>Anota tu primer gasto o ingreso.<br><button class="btn" data-nuevo>Registrar movimiento</button></div>`
        }</section>`;

    barrasDiarias($("#g-dias", main), dias);
    barrasMensuales($("#g-barras", main), serie);
    lineaBalance($("#g-linea", main), evol);
    conectarMes(main, p, (nuevo) => {
      estado.periodo = nuevo;
      this.render(main);
    });
    conectarFilas(main, (id) => movs.items.find((t) => t.id === id));
    main.querySelectorAll("[data-meta]").forEach((b) => (b.onclick = async () => abrirMeta(await api.get(`/metas/${b.dataset.meta}`), () => this.render(main))));
    $("[data-nuevo]", main)?.addEventListener("click", () => abrirFormularioMovimiento());
  },
};
