import { api } from "../api.js";
import { recargarCuentas, store } from "../store.js";
import { $, $$, TIPOS_CUENTA, dinero, esc } from "../util.js";
import { aviso, confirmar, enviando, hoja } from "../ui.js";
import { avisarCambio } from "./comun.js";

const ICONO = { EFECTIVO: "💵", BANCARIA: "🏦", BILLETERA_DIGITAL: "📱", TARJETA_CREDITO: "💳" };

function formulario(cuenta, alGuardar) {
  hoja(cuenta ? "Editar cuenta" : "Nueva cuenta", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<form novalidate>
      <div class="campo"><label for="c-nombre">Nombre</label><input id="c-nombre" class="entrada" maxlength="60" placeholder="Ej: Nequi" value="${esc(cuenta?.nombre ?? "")}"></div>
      <div class="campo"><label for="c-tipo">Tipo</label><select id="c-tipo" class="entrada">${Object.entries(TIPOS_CUENTA)
        .map(([v, n]) => `<option value="${v}" ${v === (cuenta?.tipo ?? "EFECTIVO") ? "selected" : ""}>${esc(n)}</option>`)
        .join("")}</select></div>
      <div class="campo"><label for="c-saldo">Saldo inicial (lo que tenías al empezar)</label>
        <input id="c-saldo" class="entrada" inputmode="decimal" placeholder="0" value="${cuenta ? Number(cuenta.saldo_inicial) : ""}"></div>
      <button class="btn bloque" type="submit">Guardar</button>
      ${
        cuenta
          ? `<button class="btn secundario bloque" type="button" data-archivar style="margin-top:8px">${cuenta.archivada ? "Volver a activarla" : "Archivar (dejar de usarla)"}</button>
             <button class="btn peligro bloque" type="button" data-borrar style="margin-top:8px">Eliminar</button>`
          : ""
      }</form>`;
    const form = $("form", cuerpo);
    form.onsubmit = (e) => {
      e.preventDefault();
      const boton = $("button[type=submit]", form);
      const nombre = $("#c-nombre", cuerpo).value.trim();
      const bruto = $("#c-saldo", cuerpo).value.trim();
      const saldo = bruto === "" ? "0" : bruto.replace(/\./g, "").replace(",", ".");
      const falla = (m) => {
        $(".error", cuerpo)?.remove();
        boton.insertAdjacentHTML("beforebegin", `<p class="error" role="alert">${esc(m)}</p>`);
      };
      if (!nombre) return falla("Ponle un nombre a la cuenta.");
      if (Number.isNaN(Number(saldo))) return falla("El saldo inicial no es un número válido.");
      const datos = { nombre, tipo: $("#c-tipo", cuerpo).value, saldo_inicial: saldo };
      enviando(boton, cuerpo, async () => {
        if (cuenta) await api.patch(`/cuentas/${cuenta.id}`, datos);
        else await api.post("/cuentas", datos);
        cerrar();
        aviso("Cuenta guardada");
        alGuardar();
      });
    };
    $("[data-archivar]", cuerpo)?.addEventListener("click", (e) =>
      enviando(e.target, cuerpo, async () => {
        await api.patch(`/cuentas/${cuenta.id}`, { archivada: !cuenta.archivada });
        cerrar();
        alGuardar();
      }),
    );
    $("[data-borrar]", cuerpo)?.addEventListener("click", () =>
      confirmar("¿Eliminar la cuenta?", "Solo se puede si no tiene movimientos. Si ya tiene historial, mejor archívala.", "Eliminar", async () => {
        await api.borrar(`/cuentas/${cuenta.id}`);
        cerrar();
        aviso("Cuenta eliminada");
        alGuardar();
      }),
    );
  });
}

export default {
  titulo: () => "Mis cuentas",
  atras: true,
  async render(main) {
    const cuentas = await api.get("/cuentas", { incluir_archivadas: true });
    const recargar = async () => {
      await recargarCuentas();
      avisarCambio();
    };
    main.innerHTML = `${
      cuentas.length
        ? `<section class="tarjeta" style="padding:4px 16px"><ul class="lista">${cuentas
            .map(
              (c) => `<li><button class="fila-mov" data-cuenta="${c.id}" ${c.archivada ? 'style="opacity:.6"' : ""}>
              <span class="ico" aria-hidden="true">${ICONO[c.tipo]}</span>
              <span><span class="t" style="display:block">${esc(c.nombre)}</span><span class="s" style="display:block">${esc(TIPOS_CUENTA[c.tipo].split(" (")[0])}${c.archivada ? " · Archivada" : ""}</span></span>
              <span class="monto">${dinero(c.saldo_actual)}</span></button></li>`,
            )
            .join("")}</ul></section>`
        : `<section class="tarjeta"><div class="vacio"><strong>Aún no tienes cuentas</strong>Crea una por cada lugar donde guardas plata: efectivo, Nequi, tu banco…</div></section>`
    }
      <button class="btn bloque" data-nueva>Nueva cuenta</button>
      <p class="pequeno suave" style="text-align:center">El saldo se calcula solo: saldo inicial + ingresos − gastos ± transferencias.</p>`;
    $$("[data-cuenta]", main).forEach((b) => (b.onclick = () => formulario(cuentas.find((c) => c.id === Number(b.dataset.cuenta)), recargar)));
    $("[data-nueva]", main).onclick = () => formulario(null, recargar);
  },
};
