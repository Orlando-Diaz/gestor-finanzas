// Gráficas en SVG a mano: sin librerías, funcionan sin conexión y heredan los colores del tema.
import { dinero, dineroCorto, esc, mesCorto } from "./util.js";

const W = 340;
const H = 190;
const M = { l: 46, r: 10, t: 10, b: 24 };
const PW = W - M.l - M.r;
const PH = H - M.t - M.b;

function pasoLimpio(x) {
  const e = 10 ** Math.floor(Math.log10(x));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * e >= x) return m * e;
  return 10 * e;
}

/** Escala con límites y marcas "redondas" (0, 500 mil, 1 M...). */
function escala(min, max) {
  if (max <= min) max = min + 1;
  const paso = pasoLimpio((max - min) / 3);
  const lo = Math.floor(min / paso) * paso;
  const hi = Math.ceil(max / paso) * paso;
  const marcas = [];
  for (let v = lo; v <= hi + paso / 2; v += paso) marcas.push(v);
  return { lo, hi, marcas };
}

const fila = (etiqueta, valor) => `<span>${esc(etiqueta)}: <b style="display:inline;text-transform:none">${esc(valor)}</b></span>`;

function eje(esc_, y) {
  return esc_.marcas
    .map((v) => {
      const py = y(v);
      return `<line class="rejilla" x1="${M.l}" x2="${W - M.r}" y1="${py}" y2="${py}"/>
        <text x="${M.l - 6}" y="${py + 4}" text-anchor="end">${dineroCorto(v)}</text>`;
    })
    .join("");
}

/** Hace que tocar o pasar el dedo por la gráfica muestre el detalle del punto más cercano. */
function interactiva(cont, zonas) {
  const svg = cont.querySelector("svg");
  const cursor = svg.querySelector(".cursor");
  let tip = null;
  let reloj;
  const ocultar = () => {
    tip?.remove();
    tip = null;
    if (cursor) cursor.setAttribute("opacity", "0");
  };
  const mover = (e) => {
    const r = svg.getBoundingClientRect();
    const x = ((e.clientX - r.left) * W) / r.width;
    const z = zonas.reduce((a, b) => (Math.abs(b.x - x) < Math.abs(a.x - x) ? b : a));
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "tip";
      tip.setAttribute("aria-hidden", "true");
      cont.append(tip);
    }
    tip.innerHTML = z.html;
    tip.style.left = `${Math.min(Math.max((z.x * r.width) / W, 70), r.width - 70)}px`;
    tip.style.top = `${(z.y * r.height) / H}px`;
    if (cursor) {
      cursor.setAttribute("x1", z.x);
      cursor.setAttribute("x2", z.x);
      cursor.setAttribute("opacity", "1");
    }
    clearTimeout(reloj);
    reloj = setTimeout(ocultar, 3500);
  };
  svg.addEventListener("pointerdown", mover);
  svg.addEventListener("pointermove", (e) => e.pointerType === "mouse" && mover(e));
  svg.addEventListener("pointerleave", (e) => e.pointerType === "mouse" && ocultar());
}

function tablaAccesible(titulo, columnas, filas) {
  return `<table class="solo-lectores"><caption>${esc(titulo)}</caption>
    <thead><tr>${columnas.map((c) => `<th scope="col">${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${filas.map((f) => `<tr>${f.map((c, i) => (i ? `<td>${esc(c)}</td>` : `<th scope="row">${esc(c)}</th>`)).join("")}</tr>`).join("")}</tbody></table>`;
}

/** Barras agrupadas: ingresos y gastos por mes. */
export function barrasMensuales(cont, serie) {
  const max = Math.max(0, ...serie.flatMap((p) => [Number(p.ingresos), Number(p.gastos)]));
  if (max === 0) {
    cont.innerHTML = `<p class="vacio">Aún no hay movimientos en estos meses.</p>`;
    return;
  }
  const esc_ = escala(0, max);
  const y = (v) => M.t + PH - ((v - esc_.lo) / (esc_.hi - esc_.lo)) * PH;
  const grupo = PW / serie.length;
  const ancho = Math.min(16, grupo * 0.3);
  const base = y(0);
  const barra = (x, v, color) => {
    const alto = base - y(v);
    if (alto <= 0) return "";
    const r = Math.min(4, ancho / 2, alto);
    return `<path d="M${x},${base} V${base - alto + r} Q${x},${base - alto} ${x + r},${base - alto} H${x + ancho - r} Q${x + ancho},${base - alto} ${x + ancho},${base - alto + r} V${base} Z" fill="var(${color})"/>`;
  };
  const zonas = [];
  const barras = serie
    .map((p, i) => {
      const cx = M.l + grupo * i + grupo / 2;
      const nombre = new Date(p.anio, p.mes - 1, 1).toLocaleDateString("es-CO", { month: "long", year: "numeric" });
      zonas.push({
        x: cx,
        y: y(Math.max(Number(p.ingresos), Number(p.gastos))),
        html: `<b>${esc(nombre)}</b>${fila("Ingresos", dinero(p.ingresos))}<br>${fila("Gastos", dinero(p.gastos))}`,
      });
      return `${barra(cx - ancho - 1, Number(p.ingresos), "--s1")}${barra(cx + 1, Number(p.gastos), "--s2")}
        <text x="${cx}" y="${H - 6}" text-anchor="middle">${esc(mesCorto(p.anio, p.mes))}</text>`;
    })
    .join("");
  cont.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Ingresos y gastos de los últimos ${serie.length} meses">
      ${eje(esc_, y)}<line class="cursor" y1="${M.t}" y2="${base}" stroke="var(--tinta-3)" stroke-dasharray="3 3" opacity="0"/>${barras}</svg>
    ${tablaAccesible("Ingresos y gastos por mes", ["Mes", "Ingresos", "Gastos"], serie.map((p) => [`${mesCorto(p.anio, p.mes)} ${p.anio}`, dinero(p.ingresos), dinero(p.gastos)]))}`;
  interactiva(cont, zonas);
}

/** Línea: plata total al cierre de cada mes. */
export function lineaBalance(cont, puntos) {
  const valores = puntos.map((p) => Number(p.balance));
  if (valores.every((v) => v === 0)) {
    cont.innerHTML = `<p class="vacio">Cuando registres movimientos verás aquí cómo crece tu plata.</p>`;
    return;
  }
  const esc_ = escala(Math.min(0, ...valores), Math.max(0, ...valores));
  const y = (v) => M.t + PH - ((v - esc_.lo) / (esc_.hi - esc_.lo)) * PH;
  const x = (i) => (puntos.length === 1 ? M.l + PW / 2 : M.l + (PW * i) / (puntos.length - 1));
  const d = valores.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const zonas = puntos.map((p, i) => ({
    x: x(i),
    y: y(valores[i]),
    html: `<b>${esc(new Date(p.anio, p.mes - 1, 1).toLocaleDateString("es-CO", { month: "long", year: "numeric" }))}</b>${fila("Total", dinero(p.balance))}`,
  }));
  const ult = valores.length - 1;
  const puntosSvg = valores
    .map((v, i) => `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="${i === ult ? 5 : 3.5}" fill="var(--billete)" stroke="var(--superficie)" stroke-width="2"/>`)
    .join("");
  const etiquetas = puntos
    .map((p, i) => `<text x="${x(i).toFixed(1)}" y="${H - 6}" text-anchor="${i === 0 && puntos.length > 1 ? "start" : i === ult && puntos.length > 1 ? "end" : "middle"}">${esc(mesCorto(p.anio, p.mes))}</text>`)
    .join("");
  cont.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Evolución de tu plata total en los últimos ${puntos.length} meses">
      ${eje(esc_, y)}<line class="cursor" y1="${M.t}" y2="${M.t + PH}" stroke="var(--tinta-3)" stroke-dasharray="3 3" opacity="0"/>
      <path d="${d}" fill="none" stroke="var(--billete)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>${puntosSvg}${etiquetas}</svg>
    ${tablaAccesible("Plata total al cierre de cada mes", ["Mes", "Total"], puntos.map((p) => [`${mesCorto(p.anio, p.mes)} ${p.anio}`, dinero(p.balance)]))}`;
  interactiva(cont, zonas);
}
