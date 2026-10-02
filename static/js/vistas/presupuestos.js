import { api } from "../api.js";
import { store } from "../store.js";
import { $, dinero, esc, leerMonto, nombreMes, sumarMes } from "../util.js";
import { aviso, confirmar, enviando, hoja } from "../ui.js";
import { avisarCambio, conectarMes, estado, htmlSelectorMes } from "./comun.js";

const ETIQUETA = { OK: "Vas bien", ALERTA: "Cuidado", EXCEDIDO: "Te pasaste" };

function htmlPresupuesto(b) {
  const pct = Math.min(100, Number(b.porcentaje));
  const restante = Number(b.restante);
  return `<button class="presu" data-presu="${b.id}">
    <span class="cab"><span aria-hidden="true" style="font-size:1.4rem">${esc(b.categoria.icono || "•")}</span><span class="nombre">${esc(b.categoria.nombre)}</span>
      <span class="estado ${b.estado}">${ETIQUETA[b.estado]}</span></span>
    <span class="progreso ${b.estado}" role="progressbar" aria-valuenow="${Math.round(Number(b.porcentaje))}" aria-valuemin="0" aria-valuemax="100" aria-label="Uso del presupuesto"><i style="width:${pct}%"></i></span>
    <span class="pie"><span>${dinero(b.gastado)} de ${dinero(b.monto_limite)}</span>
      <span>${restante >= 0 ? `Quedan ${dinero(restante)}` : `Te pasaste ${dinero(-restante)}`}</span></span></button>`;
}

function formulario(p, existente, lista) {
  const titulo = existente ? `Presupuesto: ${existente.categoria.nombre}` : "Nuevo presupuesto";
  hoja(titulo, (cuerpo, cerrar) => {
    const usadas = new Set(lista.map((b) => b.categoria.id));
    const libres = store.categorias.filter((c) => c.tipo === "GASTO" && !c.archivada && !usadas.has(c.id));
    if (!existente && !libres.length) {
      cuerpo.innerHTML = `<p class="suave">Ya tienes presupuesto en todas tus categorías de gasto.</p>`;
      return;
    }
    cuerpo.innerHTML = `<form novalidate>
      ${existente ? "" : `<div class="campo"><label for="p-cat">Categoría</label><select id="p-cat" class="entrada">${libres.map((c) => `<option value="${c.id}">${esc(c.icono || "")} ${esc(c.nombre)}</option>`).join("")}</select></div>`}
      <div class="campo"><label for="p-limite">Límite para ${esc(nombreMes(p))}</label>
        <input id="p-limite" class="entrada" inputmode="decimal" placeholder="Ej: 400000" value="${existente ? Number(existente.monto_limite) : ""}"></div>
      <div class="campo"><label for="p-umbral">Avisarme al llegar a (%)</label>
        <input id="p-umbral" class="entrada" type="number" min="1" max="100" value="${existente?.umbral_alerta ?? 80}"></div>
      <button class="btn bloque" type="submit">Guardar</button>
      ${existente ? `<button class="btn peligro bloque" type="button" data-borrar style="margin-top:8px">Eliminar presupuesto</button>` : ""}</form>`;
    const form = $("form", cuerpo);
    form.onsubmit = (e) => {
      e.preventDefault();
      const boton = $("button[type=submit]", form);
      const limite = leerMonto($("#p-limite", cuerpo).value);
      const umbral = Number($("#p-umbral", cuerpo).value);
      const falla = (m) => {
        $(".error", cuerpo)?.remove();
        boton.insertAdjacentHTML("beforebegin", `<p class="error" role="alert">${esc(m)}</p>`);
      };
      if (!limite) return falla("Escribe un límite mayor a cero.");
      if (!(umbral >= 1 && umbral <= 100)) return falla("El aviso va entre 1 y 100 %.");
      enviando(boton, cuerpo, async () => {
        if (existente) await api.patch(`/presupuestos/${existente.id}`, { monto_limite: limite, umbral_alerta: umbral });
        else await api.post("/presupuestos", { categoria_id: Number($("#p-cat", cuerpo).value), monto_limite: limite, umbral_alerta: umbral, anio: p.anio, mes: p.mes });
        cerrar();
        aviso("Presupuesto guardado");
        avisarCambio();
      });
    };
    $("[data-borrar]", cuerpo)?.addEventListener("click", () =>
      confirmar("¿Eliminar este presupuesto?", "Tus movimientos no se tocan; solo se quita el límite.", "Eliminar", async () => {
        await api.borrar(`/presupuestos/${existente.id}`);
        cerrar();
        aviso("Presupuesto eliminado");
        avisarCambio();
      }),
    );
  });
}

export default {
  titulo: () => "Presupuestos",
  async render(main) {
    const p = estado.periodo;
    main.innerHTML = `<div class="esqueleto" style="height:60px"></div><div class="esqueleto"></div>`;
    const lista = await api.get("/presupuestos", { anio: p.anio, mes: p.mes });
    main.innerHTML = `${htmlSelectorMes(p)}
      ${
        lista.length
          ? lista.map(htmlPresupuesto).join("")
          : `<section class="tarjeta"><div class="vacio"><strong>Sin presupuestos este mes</strong>Ponle un límite a lo que gastas en comida, transporte o lo que quieras, y te avisamos antes de pasarte.</div></section>`
      }
      <button class="btn bloque" data-nuevo>Nuevo presupuesto</button>
      <button class="btn secundario bloque" data-copiar>Copiar los de ${esc(nombreMes(sumarMes(p, -1)).split(" ")[0])}</button>`;
    conectarMes(main, p, (nuevo) => {
      estado.periodo = nuevo;
      this.render(main);
    });
    main.querySelectorAll("[data-presu]").forEach((b) => (b.onclick = () => formulario(p, lista.find((x) => x.id === Number(b.dataset.presu)), lista)));
    $("[data-nuevo]", main).onclick = () => formulario(p, null, lista);
    $("[data-copiar]", main).onclick = async (e) => {
      const o = sumarMes(p, -1);
      e.target.disabled = true;
      try {
        const copiados = await api.post("/presupuestos/copiar", { desde_anio: o.anio, desde_mes: o.mes, a_anio: p.anio, a_mes: p.mes });
        aviso(copiados.length ? `Se copiaron ${copiados.length} presupuestos` : "No había presupuestos nuevos para copiar");
        this.render(main);
      } catch (err) {
        aviso(err.message, "alerta");
        e.target.disabled = false;
      }
    };
  },
};
