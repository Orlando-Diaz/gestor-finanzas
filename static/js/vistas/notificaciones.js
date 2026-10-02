import { api } from "../api.js";
import { recargarConteo } from "../store.js";
import { $, $$, esc } from "../util.js";

const ICONO = { PRESUPUESTO_UMBRAL: "⚠️", PRESUPUESTO_EXCEDIDO: "🚨", RECURRENTE_REGISTRADA: "🔁", INFO: "ℹ️" };
const cuando = (iso) => {
  const f = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return f.toLocaleString("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: "America/Bogota" });
};

export default {
  titulo: () => "Avisos",
  atras: true,
  async render(main) {
    const lista = await api.get("/notificaciones");
    main.innerHTML = lista.length
      ? `${lista.some((n) => !n.leida) ? `<button class="btn secundario bloque" data-todas>Marcar todo como leído</button>` : ""}
        <section class="tarjeta" style="padding:4px 16px"><ul class="lista">${lista
          .map(
            (n) => `<li><div class="fila-mov" style="grid-template-columns:44px minmax(0,1fr) auto">
              <span class="ico" aria-hidden="true" style="--c:#e8b33d">${ICONO[n.tipo] ?? "ℹ️"}</span>
              <button data-leer="${n.id}" style="border:0;background:none;text-align:left;padding:0">
                <span class="t" style="display:block;${n.leida ? "font-weight:500" : ""}">${n.leida ? "" : '<span class="solo-lectores">Sin leer: </span>'}${esc(n.mensaje)}</span>
                <span class="s" style="display:block">${esc(cuando(n.creada_en))}</span></button>
              <button class="btn-icono" data-borrar="${n.id}" aria-label="Quitar aviso" style="width:36px;height:36px">✕</button></div></li>`,
          )
          .join("")}</ul></section>`
      : `<section class="tarjeta"><div class="vacio"><strong>Sin avisos</strong>Te avisamos cuando un presupuesto llegue a su límite o se registre un recurrente.</div></section>`;
    const refrescar = async () => {
      await recargarConteo();
      this.render(main);
    };
    $("[data-todas]", main)?.addEventListener("click", async () => {
      await api.post("/notificaciones/leer-todas");
      refrescar();
    });
    $$("[data-leer]", main).forEach((b) => (b.onclick = async () => {
      const n = lista.find((x) => x.id === Number(b.dataset.leer));
      if (!n.leida) {
        await api.patch(`/notificaciones/${n.id}/leer`);
        refrescar();
      }
    }));
    $$("[data-borrar]", main).forEach((b) => (b.onclick = async () => {
      await api.borrar(`/notificaciones/${b.dataset.borrar}`);
      refrescar();
    }));
  },
};
