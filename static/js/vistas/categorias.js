import { api } from "../api.js";
import { recargarCategorias } from "../store.js";
import { $, $$, esc } from "../util.js";
import { aviso, confirmar, enviando, hoja } from "../ui.js";
import { avisarCambio } from "./comun.js";

let tipoActual = "GASTO";

function formulario(cat, alGuardar) {
  hoja(cat ? "Editar categoría" : "Nueva categoría", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<form novalidate>
      <div class="campo"><label for="k-nombre">Nombre</label><input id="k-nombre" class="entrada" maxlength="60" placeholder="Ej: Gimnasio" value="${esc(cat?.nombre ?? "")}"></div>
      <div class="dos">
        <div class="campo"><label for="k-icono">Emoji</label><input id="k-icono" class="entrada" maxlength="8" placeholder="🏋️" value="${esc(cat?.icono ?? "")}"></div>
        <div class="campo"><label for="k-color">Color</label><input id="k-color" class="entrada" type="color" style="padding:4px" value="${esc(cat?.color ?? "#0e5a47")}"></div>
      </div>
      <button class="btn bloque" type="submit">Guardar</button>
      ${cat ? `<button class="btn secundario bloque" type="button" data-archivar style="margin-top:8px">Archivar</button><button class="btn peligro bloque" type="button" data-borrar style="margin-top:8px">Eliminar</button>` : ""}</form>`;
    const form = $("form", cuerpo);
    form.onsubmit = (e) => {
      e.preventDefault();
      const boton = $("button[type=submit]", form);
      const nombre = $("#k-nombre", cuerpo).value.trim();
      if (!nombre) {
        $(".error", cuerpo)?.remove();
        boton.insertAdjacentHTML("beforebegin", `<p class="error" role="alert">Escribe un nombre.</p>`);
        return;
      }
      const datos = { nombre, icono: $("#k-icono", cuerpo).value.trim() || null, color: $("#k-color", cuerpo).value };
      enviando(boton, cuerpo, async () => {
        if (cat) await api.patch(`/categorias/${cat.id}`, datos);
        else await api.post("/categorias", { ...datos, tipo: tipoActual });
        cerrar();
        aviso("Categoría guardada");
        alGuardar();
      });
    };
    $("[data-archivar]", cuerpo)?.addEventListener("click", (e) =>
      enviando(e.target, cuerpo, async () => {
        await api.patch(`/categorias/${cat.id}`, { archivada: true });
        cerrar();
        alGuardar();
      }),
    );
    $("[data-borrar]", cuerpo)?.addEventListener("click", () =>
      confirmar("¿Eliminar la categoría?", "Solo se puede si nunca la has usado. Si ya tiene historial, archívala.", "Eliminar", async () => {
        await api.borrar(`/categorias/${cat.id}`);
        cerrar();
        alGuardar();
      }),
    );
  });
}

export default {
  titulo: () => "Categorías",
  atras: true,
  async render(main) {
    const todas = await api.get("/categorias");
    const lista = todas.filter((c) => c.tipo === tipoActual);
    const recargar = async () => {
      await recargarCategorias();
      avisarCambio();
    };
    main.innerHTML = `<div class="segmentos" role="group" aria-label="Tipo de categoría">
        ${[["GASTO", "Gastos"], ["INGRESO", "Ingresos"]].map(([v, n]) => `<button data-tipo="${v}" aria-pressed="${v === tipoActual}">${n}</button>`).join("")}</div>
      <section class="tarjeta" style="padding:4px 16px"><ul class="lista">${lista
        .map(
          (c) => `<li><button class="fila-mov" ${c.predeterminada ? "disabled" : `data-cat="${c.id}"`} style="--c:${esc(c.color || "#6b7280")}">
            <span class="ico" aria-hidden="true">${esc(c.icono || "•")}</span>
            <span class="t">${esc(c.nombre)}</span><span class="s">${c.predeterminada ? "Predeterminada" : "Editar"}</span></button></li>`,
        )
        .join("")}</ul></section>
      <button class="btn bloque" data-nueva>Nueva categoría de ${tipoActual === "GASTO" ? "gasto" : "ingreso"}</button>`;
    $$("[data-tipo]", main).forEach((b) => (b.onclick = () => { tipoActual = b.dataset.tipo; this.render(main); }));
    $$("[data-cat]", main).forEach((b) => (b.onclick = () => formulario(todas.find((c) => c.id === Number(b.dataset.cat)), () => recargar().then(() => this.render(main)))));
    $("[data-nueva]", main).onclick = () => formulario(null, () => recargar().then(() => this.render(main)));
  },
};
