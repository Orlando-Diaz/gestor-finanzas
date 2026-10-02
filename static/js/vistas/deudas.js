import { api } from "../api.js";
import { recargarConteo } from "../store.js";
import { $, $$, dinero, esc, fechaCorta, fechaLarga, hoyISO, leerMonto } from "../util.js";
import { aviso, confirmar, enviando, errorEn, hoja } from "../ui.js";

const TEXTO = {
  ME_DEBEN: { titulo: "Me deben", persona: "¿Quién te debe?", abono: "Registrar abono", abonoTitulo: "¿Cuánto te pagó?", todo: "Me pagó todo lo que falta", pie: "te falta recibir" },
  DEBO: { titulo: "Debo", persona: "¿A quién le debes?", abono: "Registrar pago", abonoTitulo: "¿Cuánto pagaste?", todo: "Pagué todo lo que falta", pie: "te falta pagar" },
};
const estado = { tipo: "ME_DEBEN", saldadas: false };

function campoFecha(id, etiqueta, valor = "") {
  return `<div class="campo"><label for="${id}">${etiqueta}</label><input id="${id}" type="date" class="entrada" value="${esc(valor)}"></div>`;
}

/** Tarjeta de una deuda (lista). */
function htmlDeuda(d, etiqueta = "button") {
  const pct = Math.min(100, Number(d.porcentaje));
  const t = TEXTO[d.tipo];
  const insignia = d.saldada
    ? `<span class="estado OK">Saldada</span>`
    : d.vencida
      ? `<span class="estado EXCEDIDO">Vencida</span>`
      : `<span class="estado" style="background:var(--superficie-2);color:var(--tinta-2)">${Math.round(Number(d.porcentaje))}%</span>`;
  const pie = d.saldada
    ? `<span>${dinero(d.monto_total)} en total</span><span>Todo pagado</span>`
    : `<span>${dinero(d.pendiente)} ${t.pie}</span><span>de ${dinero(d.monto_total)}</span>`;
  const venc = d.fecha_vencimiento && !d.saldada
    ? `<span class="pequeno suave">${d.vencida ? "Venció" : "Vence"} el ${esc(fechaCorta(d.fecha_vencimiento))}</span>`
    : "";
  return `<${etiqueta} class="presu" ${etiqueta === "button" ? `data-deuda="${d.id}"` : ""}>
    <span class="cab"><span class="nombre">${esc(d.persona)}</span>${insignia}</span>
    ${d.descripcion ? `<span class="pequeno suave">${esc(d.descripcion)}</span>` : ""}
    <span class="progreso ${d.saldada ? "OK" : d.vencida ? "EXCEDIDO" : ""}" role="progressbar" aria-valuenow="${Math.round(pct)}" aria-valuemin="0" aria-valuemax="100" aria-label="Progreso del pago"><i style="width:${pct}%"></i></span>
    <span class="pie">${pie}</span>${venc}</${etiqueta}>`;
}

function abrirDeuda(inicial, alCambiar) {
  let d = inicial;
  hoja(d.persona, (cuerpo, cerrar) => {
    const t = () => TEXTO[d.tipo];
    const titulo = () => ($(".cabeza h2", cuerpo.parentElement).textContent = d.persona);

    const detalle = () => {
      titulo();
      cuerpo.innerHTML = `<div class="tarjeta" style="margin-bottom:14px">${htmlDeuda(d, "div")}</div>
        ${
          d.saldada
            ? ""
            : `<button class="btn bloque" data-abonar>${t().abono}</button>
               <button class="btn secundario bloque" data-todo style="margin-top:8px">${t().todo}</button>`
        }
        <div class="seccion-fila" style="margin-top:18px"><h2>Pagos</h2></div>
        ${
          d.pagos.length
            ? `<ul class="lista">${d.pagos
                .map(
                  (a) => `<li><div class="fila-mov" style="grid-template-columns:minmax(0,1fr) auto 36px;padding:8px 0">
                <span><span class="t" style="display:block">${esc(fechaLarga(a.fecha))}</span>${a.nota ? `<span class="s" style="display:block">${esc(a.nota)}</span>` : ""}</span>
                <span class="monto ${d.tipo === "ME_DEBEN" ? "ingreso" : "gasto"}">${dinero(a.monto)}</span>
                <button class="btn-icono" data-quitar="${a.id}" aria-label="Borrar este pago" style="width:36px;height:36px">✕</button></div></li>`,
                )
                .join("")}</ul>`
            : `<p class="vacio">Todavía no hay pagos registrados.</p>`
        }
        <button class="btn secundario bloque" data-editar style="margin-top:14px">Editar</button>
        <button class="btn peligro bloque" data-borrar style="margin-top:8px">Eliminar</button>`;
      $("[data-abonar]", cuerpo) && ($("[data-abonar]", cuerpo).onclick = formPago);
      const todo = $("[data-todo]", cuerpo);
      if (todo)
        todo.onclick = () =>
          enviando(todo, cuerpo, async () => {
            d = await api.post(`/deudas/${d.id}/pagos`, { monto: d.pendiente });
            alCambiar();
            aviso("¡Deuda saldada!");
            detalle();
          });
      $("[data-editar]", cuerpo).onclick = formEditar;
      $$("[data-quitar]", cuerpo).forEach(
        (b) =>
          (b.onclick = async () => {
            b.disabled = true;
            try {
              await api.borrar(`/deudas/${d.id}/pagos/${b.dataset.quitar}`);
              d = await api.get(`/deudas/${d.id}`);
              alCambiar();
              detalle();
            } catch (e) {
              aviso(e.message, "alerta");
              b.disabled = false;
            }
          }),
      );
      $("[data-borrar]", cuerpo).onclick = () =>
        confirmar("¿Eliminar esta deuda?", "Se borra también su historial de pagos.", "Eliminar", async () => {
          await api.borrar(`/deudas/${d.id}`);
          cerrar();
          alCambiar();
        });
    };

    const formPago = () => {
      cuerpo.innerHTML = `<form novalidate>
        <div class="campo"><label for="p-monto">${t().abonoTitulo}</label>
          <input id="p-monto" class="entrada" inputmode="decimal" placeholder="Máximo ${dinero(d.pendiente)}" autocomplete="off"></div>
        ${campoFecha("p-fecha", "Fecha", hoyISO())}
        <div class="campo"><label for="p-nota">Nota (opcional)</label><input id="p-nota" class="entrada" maxlength="255"></div>
        <button class="btn bloque" type="submit">Guardar</button>
        <button class="btn secundario bloque" type="button" data-volver style="margin-top:8px">Volver</button></form>`;
      $("[data-volver]", cuerpo).onclick = detalle;
      setTimeout(() => $("#p-monto", cuerpo)?.focus(), 50);
      $("form", cuerpo).onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", cuerpo);
        const monto = leerMonto($("#p-monto", cuerpo).value);
        if (!monto) return errorEn(cuerpo, boton, "Escribe un monto mayor a cero.");
        enviando(boton, cuerpo, async () => {
          const estabaSaldada = d.saldada;
          d = await api.post(`/deudas/${d.id}/pagos`, {
            monto, fecha: $("#p-fecha", cuerpo).value || undefined, nota: $("#p-nota", cuerpo).value.trim() || undefined,
          });
          alCambiar();
          if (d.saldada && !estabaSaldada) aviso("¡Deuda saldada!");
          detalle();
        });
      };
    };

    const formEditar = () => {
      cuerpo.innerHTML = `<form novalidate>
        <div class="campo"><label for="e-persona">Persona</label><input id="e-persona" class="entrada" maxlength="100" value="${esc(d.persona)}"></div>
        <div class="campo"><label for="e-desc">Descripción (opcional)</label><input id="e-desc" class="entrada" maxlength="255" value="${esc(d.descripcion ?? "")}"></div>
        <div class="campo"><label for="e-total">Monto total</label><input id="e-total" class="entrada" inputmode="decimal" value="${Number(d.monto_total)}"></div>
        ${campoFecha("e-venc", "Fecha de vencimiento (opcional)", d.fecha_vencimiento ?? "")}
        <button class="btn bloque" type="submit">Guardar cambios</button>
        <button class="btn secundario bloque" type="button" data-volver style="margin-top:8px">Volver</button></form>`;
      $("[data-volver]", cuerpo).onclick = detalle;
      $("form", cuerpo).onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", cuerpo);
        const persona = $("#e-persona", cuerpo).value.trim();
        const total = leerMonto($("#e-total", cuerpo).value);
        if (!persona) return errorEn(cuerpo, boton, "Escribe un nombre.");
        if (!total) return errorEn(cuerpo, boton, "El monto debe ser mayor a cero.");
        enviando(boton, cuerpo, async () => {
          d = await api.patch(`/deudas/${d.id}`, {
            persona, monto_total: total, descripcion: $("#e-desc", cuerpo).value.trim() || null,
            fecha_vencimiento: $("#e-venc", cuerpo).value || null,
          });
          alCambiar();
          detalle();
        });
      };
    };

    detalle();
  });
}

function formularioNueva(alGuardar) {
  hoja("Nueva deuda", (cuerpo, cerrar) => {
    let tipo = estado.tipo;
    const pintar = () => {
      const t = TEXTO[tipo];
      cuerpo.innerHTML = `<form novalidate>
        <div class="segmentos" role="group" aria-label="Tipo de deuda" style="margin-bottom:14px">
          <button type="button" data-t="ME_DEBEN" aria-pressed="${tipo === "ME_DEBEN"}">Me deben</button>
          <button type="button" data-t="DEBO" aria-pressed="${tipo === "DEBO"}">Debo</button></div>
        <div class="campo"><label for="n-persona">${t.persona}</label><input id="n-persona" class="entrada" maxlength="100" autocomplete="off"></div>
        <div class="campo"><label for="n-monto">Monto</label><input id="n-monto" class="entrada" inputmode="decimal" placeholder="Ej: 200.000" autocomplete="off"></div>
        <div class="campo"><label for="n-desc">Descripción (opcional)</label><input id="n-desc" class="entrada" maxlength="255" placeholder="Ej: Préstamo para el arriendo"></div>
        ${campoFecha("n-venc", "¿Para cuándo? (opcional)")}
        <button class="btn bloque" type="submit">Guardar</button></form>`;
      $$("[data-t]", cuerpo).forEach(
        (b) =>
          (b.onclick = () => {
            // conserva lo ya escrito al cambiar de pestaña
            const guardado = ["#n-persona", "#n-monto", "#n-desc", "#n-venc"].map((s) => $(s, cuerpo).value);
            tipo = b.dataset.t;
            pintar();
            ["#n-persona", "#n-monto", "#n-desc", "#n-venc"].forEach((s, i) => ($(s, cuerpo).value = guardado[i]));
          }),
      );
      $("form", cuerpo).onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", cuerpo);
        const persona = $("#n-persona", cuerpo).value.trim();
        const monto = leerMonto($("#n-monto", cuerpo).value);
        if (!persona) return errorEn(cuerpo, boton, "Escribe el nombre de la persona.");
        if (!monto) return errorEn(cuerpo, boton, "Escribe un monto mayor a cero.");
        enviando(boton, cuerpo, async () => {
          const venc = $("#n-venc", cuerpo).value || undefined;
          await api.post("/deudas", {
            tipo, persona, monto_total: monto, descripcion: $("#n-desc", cuerpo).value.trim() || undefined,
            fecha_vencimiento: venc,
            // una deuda que ya venció se anota con su fecha de vencimiento como fecha de origen
            fecha: venc && venc < hoyISO() ? venc : undefined,
          });
          estado.tipo = tipo;
          cerrar();
          aviso("Deuda guardada");
          alGuardar();
        });
      };
    };
    pintar();
  });
}

export default {
  titulo: () => "Deudas",
  atras: true,
  async render(main) {
    const [resumen, lista] = await Promise.all([
      api.get("/deudas/resumen"),
      api.get("/deudas", { tipo: estado.tipo, estado: estado.saldadas ? "todas" : "pendientes" }),
    ]);
    const t = TEXTO[estado.tipo];
    const total = estado.tipo === "ME_DEBEN" ? resumen.me_deben : resumen.debo;
    const cantidad = estado.tipo === "ME_DEBEN" ? resumen.cantidad_me_deben : resumen.cantidad_debo;
    main.innerHTML = `<section class="billete" aria-label="Resumen de deudas">
        <p class="rotulo">${estado.tipo === "ME_DEBEN" ? "Te deben en total" : "Debes en total"}</p>
        <p class="total">${dinero(total)}</p>
        <div class="fila">
          <div><small>${estado.tipo === "ME_DEBEN" ? "Pendientes" : "Deudas pendientes"}</small><b>${cantidad}</b></div>
          <div><small>${estado.tipo === "ME_DEBEN" ? "Tú debes" : "Te deben"}</small><b>${dinero(estado.tipo === "ME_DEBEN" ? resumen.debo : resumen.me_deben)}</b></div>
        </div></section>
      ${resumen.vencidas ? `<p class="pequeno" role="status" style="margin:-4px 0 0;text-align:center;color:var(--gasto)">Tienes ${resumen.vencidas} ${resumen.vencidas === 1 ? "deuda vencida" : "deudas vencidas"}</p>` : ""}
      <div class="segmentos" role="group" aria-label="Tipo de deuda">
        <button data-t="ME_DEBEN" aria-pressed="${estado.tipo === "ME_DEBEN"}">Me deben</button>
        <button data-t="DEBO" aria-pressed="${estado.tipo === "DEBO"}">Debo</button></div>
      ${
        lista.length
          ? lista.map((d) => htmlDeuda(d)).join("")
          : `<section class="tarjeta"><div class="vacio"><strong>${estado.saldadas ? "Nada por aquí" : "Sin deudas pendientes"}</strong>${
              estado.tipo === "ME_DEBEN" ? "Anota a quién le prestaste plata y cuánto te falta por recibir." : "Anota lo que debes para no olvidarlo."
            }</div></section>`
      }
      <button class="btn bloque" data-nueva>Nueva deuda</button>
      <button class="btn secundario bloque" data-saldadas>${estado.saldadas ? "Ocultar saldadas" : "Ver también las saldadas"}</button>`;
    const refrescar = () => {
      recargarConteo();
      return this.render(main);
    };
    $$("[data-t]", main).forEach(
      (b) =>
        (b.onclick = () => {
          estado.tipo = b.dataset.t;
          this.render(main);
        }),
    );
    $$("[data-deuda]", main).forEach((b) => (b.onclick = async () => abrirDeuda(await api.get(`/deudas/${b.dataset.deuda}`), refrescar)));
    $("[data-nueva]", main).onclick = () => formularioNueva(refrescar);
    $("[data-saldadas]", main).onclick = () => {
      estado.saldadas = !estado.saldadas;
      this.render(main);
    };
  },
};
