// Utilidades de formato y pequeños ayudantes de DOM.

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

let formatoMoneda = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
export function fijarMoneda(codigo) {
  try {
    formatoMoneda = new Intl.NumberFormat("es-CO", { style: "currency", currency: codigo, maximumFractionDigits: 0 });
  } catch {
    /* código inválido: se queda con COP */
  }
}
export const dinero = (v) => formatoMoneda.format(Number(v) || 0);

/* Modo incógnito: oculta los saldos (total y cuentas). Se recuerda en este dispositivo. */
const CLAVE_OCULTO = "mf.oculto";
const MASCARA = "$ ••••••";
let oculto = false;
try {
  oculto = localStorage.getItem(CLAVE_OCULTO) === "1";
} catch {
  /* sin almacenamiento: queda visible */
}
export const saldosOcultos = () => oculto;
export function alternarSaldos() {
  oculto = !oculto;
  try {
    localStorage.setItem(CLAVE_OCULTO, oculto ? "1" : "0");
  } catch {
    /* no pasa nada: vale para esta sesión */
  }
  return oculto;
}
/** Un saldo que respeta el modo incógnito; `pintarSaldos` lo actualiza sin volver a pintar la pantalla. */
export const htmlSaldo = (v) => `<span data-saldo="${Number(v) || 0}">${oculto ? MASCARA : dinero(v)}</span>`;
export function pintarSaldos(raiz = document) {
  raiz.querySelectorAll("[data-saldo]").forEach((el) => (el.textContent = oculto ? MASCARA : dinero(el.dataset.saldo)));
}

/** 1.250.000 -> "1,3 M"; 85.000 -> "85 mil" (para los ejes de las gráficas). */
export function dineroCorto(v) {
  const n = Math.abs(Number(v) || 0);
  const signo = Number(v) < 0 ? "-" : "";
  const f = (x) => x.toLocaleString("es-CO", { maximumFractionDigits: 1 });
  if (n >= 1e6) return `${signo}${f(n / 1e6)} M`;
  if (n >= 1e3) return `${signo}${f(n / 1e3)} mil`;
  return `${signo}${f(n)}`;
}

/** Fecha de hoy en Colombia, como YYYY-MM-DD. */
export const hoyISO = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Bogota" }).format(new Date());

export function periodoActual() {
  const [anio, mes] = hoyISO().split("-").map(Number);
  return { anio, mes };
}

export function sumarMes({ anio, mes }, n) {
  const i = anio * 12 + (mes - 1) + n;
  return { anio: Math.floor(i / 12), mes: (i % 12) + 1 };
}

export const mismoPeriodo = (a, b) => a.anio === b.anio && a.mes === b.mes;
export const nombreMes = ({ anio, mes }) =>
  new Date(anio, mes - 1, 1).toLocaleDateString("es-CO", { month: "long", year: "numeric" });
export const mesCorto = (anio, mes) =>
  new Date(anio, mes - 1, 1).toLocaleDateString("es-CO", { month: "short" }).replace(".", "");

const aFecha = (iso) => {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
};

/** "Hoy", "Ayer" o "martes 29 de septiembre". */
export function etiquetaDia(iso) {
  const hoy = hoyISO();
  if (iso === hoy) return "Hoy";
  const ayer = aFecha(hoy);
  ayer.setDate(ayer.getDate() - 1);
  if (aFecha(iso).getTime() === ayer.getTime()) return "Ayer";
  return aFecha(iso).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long" });
}

export const fechaLarga = (iso) =>
  aFecha(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }).replace(".", "");

export const fechaCorta = (iso) =>
  aFecha(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short" }).replace(".", "");

export const primerDiaMes = ({ anio, mes }) => `${anio}-${String(mes).padStart(2, "0")}-01`;
export function ultimoDiaMes({ anio, mes }) {
  const d = new Date(anio, mes, 0).getDate();
  return `${anio}-${String(mes).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** "12.500,50", "12500.5" o "12 500" -> "12500.5" (o null si no es un monto). */
export function leerMonto(texto) {
  let t = String(texto ?? "").trim().replace(/[^\d.,]/g, "");
  if (!t) return null;
  const ultimaComa = t.lastIndexOf(",");
  const ultimoPunto = t.lastIndexOf(".");
  const sep = Math.max(ultimaComa, ultimoPunto);
  if (sep >= 0 && t.length - sep - 1 <= 2 && t.length - sep - 1 > 0) {
    t = t.slice(0, sep).replace(/[.,]/g, "") + "." + t.slice(sep + 1);
  } else {
    t = t.replace(/[.,]/g, "");
  }
  const n = Number(t);
  return Number.isFinite(n) && n > 0 ? t : null;
}

export const $ = (sel, raiz = document) => raiz.querySelector(sel);
export const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

export const TIPOS_CUENTA = {
  EFECTIVO: "Efectivo",
  BANCARIA: "Cuenta bancaria",
  BILLETERA_DIGITAL: "Billetera digital (Nequi, Daviplata…)",
  TARJETA_CREDITO: "Tarjeta de crédito",
};
export const FRECUENCIAS = { SEMANAL: "Cada semana", QUINCENAL: "Cada quincena", MENSUAL: "Cada mes", ANUAL: "Cada año" };

/** Íconos de trazo (24x24). */
const trazo = (d) =>
  `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
export const ICONOS = {
  inicio: trazo('<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>'),
  movimientos: trazo('<path d="M7 4v14"/><path d="M3 14l4 4 4-4"/><path d="M17 20V6"/><path d="M21 10l-4-4-4 4"/>'),
  presupuestos: trazo('<circle cx="12" cy="12" r="9"/><path d="M12 12V3"/><path d="M12 12l6.4 6.4"/>'),
  mas: trazo('<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>'),
  mas_grande: trazo('<path d="M12 5v14M5 12h14"/>'),
  campana: trazo('<path d="M6 9a6 6 0 1 1 12 0c0 6 2 7 2 7H4s2-1 2-7"/><path d="M10 20a2 2 0 0 0 4 0"/>'),
  izquierda: trazo('<path d="M15 5l-7 7 7 7"/>'),
  derecha: trazo('<path d="M9 5l7 7-7 7"/>'),
  cerrar: trazo('<path d="M6 6l12 12M18 6L6 18"/>'),
  ojo: trazo('<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'),
  ojo_cerrado: trazo('<path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.6 6.7C3.9 8.5 2 12 2 12s3.6 7 10 7a9.7 9.7 0 0 0 4.4-1"/>'),
  chevron: trazo('<path d="M9 5l7 7-7 7"/>'),
};
export const emojiMenu = { gastos: "📊", ingresos: "💰", metas: "🎯", deudas: "🤝", cuentas: "👛", categorias: "🏷️", recurrentes: "🔁", notificaciones: "🔔", exportar: "📄", perfil: "👤", salir: "🚪" };
