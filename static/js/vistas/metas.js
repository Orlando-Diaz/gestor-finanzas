import { api } from "../api.js";
import { recargarConteo } from "../store.js";
import { $, $$, dinero, esc, fechaCorta, fechaLarga, hoyISO, leerMonto } from "../util.js";
import { aviso, confirmar, enviando, errorEn, hoja } from "../ui.js";
import { avisarCambio } from "./comun.js";

const ICONO_POR_DEFECTO = "🎯";

/** Tarjeta de una meta (se usa aquí y, en versión corta, en Inicio). */
export function htmlMeta(m, corta = false, etiqueta = "button") {
  const pct = Math.min(100, Number(m.porcentaje));
  const color = m.color ? `background:${esc(m.color)}` : "";
  const barra = `<span class="progreso ${m.cumplida ? "OK" : ""}" role="progressbar" aria-valuenow="${Math.round(pct)}" aria-valuemin="0" aria-valuemax="100" aria-label="Progreso de la meta"><i style="width:${pct}%;${color}"></i></span>`;
  const pie = m.cumplida
    ? `<span>${dinero(m.ahorrado)} ahorrados</span><span>¡Cumplida!</span>`
    : `<span>${dinero(m.ahorrado)} de ${dinero(m.monto_objetivo)}</span><span>Faltan ${dinero(m.faltante)}</span>`;
  const extra = !corta && !m.cumplida && m.cuota_mensual_sugerida
    ? `<span class="pequeno suave">Ahorra ${dinero(m.cuota_mensual_sugerida)} al mes para llegar el ${esc(fechaCorta(m.fecha_objetivo))}</span>`
    : !corta && m.fecha_objetivo && !m.cumplida
      ? `<span class="pequeno suave">Fecha objetivo: ${esc(fechaLarga(m.fecha_objetivo))}</span>`
      : "";
  return `<${etiqueta} class="presu" ${etiqueta === "button" ? `data-meta="${m.id}"` : ""}>
    <span class="cab"><span aria-hidden="true" style="font-size:1.4rem">${esc(m.icono || ICONO_POR_DEFECTO)}</span><span class="nombre">${esc(m.nombre)}</span>
      <span class="estado ${m.cumplida ? "OK" : "ALERTA"}" ${m.cumplida ? "" : 'style="background:var(--superficie-2);color:var(--tinta-2)"'}>${m.cumplida ? "Cumplida" : `${Math.round(Number(m.porcentaje))}%`}</span></span>
    ${barra}<span class="pie">${pie}</span>${extra}</${etiqueta}>`;
}

function campoFecha(id, etiqueta, valor = "") {
  return `<div class="campo"><label for="${id}">${etiqueta}</label><input id="${id}" type="date" class="entrada" value="${esc(valor)}"></div>`;
}

/** Hoja con el detalle de una meta: aportar, retirar, editar, archivar, eliminar. */
export function abrirMeta(inicial, alCambiar) {
  let m = inicial;
  hoja(`${m.icono || ICONO_POR_DEFECTO} ${m.nombre}`, (cuerpo, cerrar) => {
    const titulo = () => ($(".cabeza h2", cuerpo.parentElement).textContent = `${m.icono || ICONO_POR_DEFECTO} ${m.nombre}`);

    const detalle = () => {
      titulo();
      cuerpo.innerHTML = `<div class="tarjeta" style="margin-bottom:14px">${htmlMeta(m, false, "div")}</div>
        <div class="dos" style="margin-bottom:6px">
          <button class="btn" data-aportar>Aportar</button><button class="btn secundario" data-retirar ${Number(m.ahorrado) > 0 ? "" : "disabled"}>Retirar</button></div>
        <div class="seccion-fila" style="margin-top:18px"><h2>Movimientos</h2></div>
        ${
          m.aportes.length
            ? `<ul class="lista">${m.aportes
                .map(
                  (a) => `<li><div class="fila-mov" style="grid-template-columns:minmax(0,1fr) auto 36px;padding:8px 0">
                <span><span class="t" style="display:block">${a.tipo === "APORTE" ? "Aporte" : "Retiro"}</span><span class="s" style="display:block">${esc(fechaLarga(a.fecha))}${a.nota ? ` · ${esc(a.nota)}` : ""}</span></span>
                <span class="monto ${a.tipo === "APORTE" ? "ingreso" : "gasto"}">${a.tipo === "APORTE" ? "+" : "−"}${dinero(a.monto)}</span>
                <button class="btn-icono" data-quitar="${a.id}" aria-label="Borrar este movimiento" style="width:36px;height:36px">✕</button></div></li>`,
                )
                .join("")}</ul>`
            : `<p class="vacio">Aún no has apartado nada. Toca <b>Aportar</b> para empezar.</p>`
        }
        <button class="btn secundario bloque" data-editar style="margin-top:14px">Editar meta</button>
        <button class="btn secundario bloque" data-archivar style="margin-top:8px">Archivar</button>
        <button class="btn peligro bloque" data-borrar style="margin-top:8px">Eliminar meta</button>`;
      $("[data-aportar]", cuerpo).onclick = () => formAporte("APORTE");
      $("[data-retirar]", cuerpo).onclick = () => formAporte("RETIRO");
      $("[data-editar]", cuerpo).onclick = formEditar;
      $$("[data-quitar]", cuerpo).forEach(
        (b) =>
          (b.onclick = async () => {
            b.disabled = true;
            try {
              await api.borrar(`/metas/${m.id}/aportes/${b.dataset.quitar}`);
              m = await api.get(`/metas/${m.id}`);
              alCambiar();
              detalle();
            } catch (e) {
              aviso(e.message, "alerta");
              b.disabled = false;
            }
          }),
      );
      $("[data-archivar]", cuerpo).onclick = (e) =>
        enviando(e.target, cuerpo, async () => {
          await api.patch(`/metas/${m.id}`, { archivada: true });
          cerrar();
          aviso("Meta archivada");
          alCambiar();
        });
      $("[data-borrar]", cuerpo).onclick = () =>
        confirmar("¿Eliminar esta meta?", "Se borra también su historial de aportes. Si solo quieres dejar de verla, archívala.", "Eliminar", async () => {
          await api.borrar(`/metas/${m.id}`);
          cerrar();
          alCambiar();
        });
    };

    const formAporte = (tipo) => {
      const aporte = tipo === "APORTE";
      cuerpo.innerHTML = `<form novalidate>
        <div class="campo"><label for="a-monto">${aporte ? "¿Cuánto apartas?" : "¿Cuánto sacas?"}</label>
          <input id="a-monto" class="entrada" inputmode="decimal" placeholder="Ej: 50.000" autocomplete="off"></div>
        ${campoFecha("a-fecha", "Fecha", hoyISO())}
        <div class="campo"><label for="a-nota">Nota (opcional)</label><input id="a-nota" class="entrada" maxlength="255"></div>
        <button class="btn bloque" type="submit">${aporte ? "Guardar aporte" : "Guardar retiro"}</button>
        <button class="btn secundario bloque" type="button" data-volver style="margin-top:8px">Volver</button></form>`;
      $("[data-volver]", cuerpo).onclick = detalle;
      setTimeout(() => $("#a-monto", cuerpo)?.focus(), 50);
      $("form", cuerpo).onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", cuerpo);
        const monto = leerMonto($("#a-monto", cuerpo).value);
        if (!monto) return errorEn(cuerpo, boton, "Escribe un monto mayor a cero.");
        enviando(boton, cuerpo, async () => {
          const estabaCumplida = m.cumplida;
          m = await api.post(`/metas/${m.id}/aportes`, {
            tipo, monto, fecha: $("#a-fecha", cuerpo).value || undefined, nota: $("#a-nota", cuerpo).value.trim() || undefined,
          });
          alCambiar();
          recargarConteo();
          if (m.cumplida && !estabaCumplida) aviso("¡Meta cumplida! 🎉");
          detalle();
        });
      };
    };

    const formEditar = () => {
      cuerpo.innerHTML = `<form novalidate>
        <div class="campo"><label for="e-nombre">Nombre</label><input id="e-nombre" class="entrada" maxlength="80" value="${esc(m.nombre)}"></div>
        <div class="campo"><label for="e-objetivo">Monto objetivo</label><input id="e-objetivo" class="entrada" inputmode="decimal" value="${Number(m.monto_objetivo)}"></div>
        ${campoFecha("e-fecha", "Fecha objetivo (opcional)", m.fecha_objetivo ?? "")}
        <div class="dos">
          <div class="campo"><label for="e-icono">Emoji</label><input id="e-icono" class="entrada" maxlength="8" value="${esc(m.icono ?? "")}" placeholder="✈️"></div>
          <div class="campo"><label for="e-color">Color</label><input id="e-color" class="entrada" type="color" style="padding:4px" value="${esc(m.color ?? "#0e5a47")}"></div>
        </div>
        <button class="btn bloque" type="submit">Guardar cambios</button>
        <button class="btn secundario bloque" type="button" data-volver style="margin-top:8px">Volver</button></form>`;
      $("[data-volver]", cuerpo).onclick = detalle;
      $("form", cuerpo).onsubmit = (e) => {
        e.preventDefault();
        const boton = $("button[type=submit]", cuerpo);
        const nombre = $("#e-nombre", cuerpo).value.trim();
        const objetivo = leerMonto($("#e-objetivo", cuerpo).value);
        if (!nombre) return errorEn(cuerpo, boton, "Escribe un nombre.");
        if (!objetivo) return errorEn(cuerpo, boton, "El objetivo debe ser mayor a cero.");
        enviando(boton, cuerpo, async () => {
          m = await api.patch(`/metas/${m.id}`, {
            nombre, monto_objetivo: objetivo, fecha_objetivo: $("#e-fecha", cuerpo).value || null,
            icono: $("#e-icono", cuerpo).value.trim() || null, color: $("#e-color", cuerpo).value,
          });
          alCambiar();
          recargarConteo();
          detalle();
        });
      };
    };

    detalle();
  });
}

function formularioNueva(alGuardar) {
  hoja("Nueva meta de ahorro", (cuerpo, cerrar) => {
    cuerpo.innerHTML = `<form novalidate>
      <div class="campo"><label for="n-nombre">¿Para qué ahorras?</label><input id="n-nombre" class="entrada" maxlength="80" placeholder="Ej: Viaje a Cartagena"></div>
      <div class="campo"><label for="n-objetivo">¿Cuánto necesitas?</label><input id="n-objetivo" class="entrada" inputmode="decimal" placeholder="Ej: 1.500.000"></div>
      ${campoFecha("n-fecha", "¿Para cuándo? (opcional)")}
      <div class="dos">
        <div class="campo"><label for="n-icono">Emoji</label><input id="n-icono" class="entrada" maxlength="8" placeholder="✈️"></div>
        <div class="campo"><label for="n-color">Color</label><input id="n-color" class="entrada" type="color" style="padding:4px" value="#0e5a47"></div>
      </div>
      <button class="btn bloque" type="submit">Crear meta</button></form>`;
    $("form", cuerpo).onsubmit = (e) => {
      e.preventDefault();
      const boton = $("button[type=submit]", cuerpo);
      const nombre = $("#n-nombre", cuerpo).value.trim();
      const objetivo = leerMonto($("#n-objetivo", cuerpo).value);
      if (!nombre) return errorEn(cuerpo, boton, "Ponle un nombre a tu meta.");
      if (!objetivo) return errorEn(cuerpo, boton, "Escribe cuánto necesitas (mayor a cero).");
      enviando(boton, cuerpo, async () => {
        await api.post("/metas", {
          nombre, monto_objetivo: objetivo, fecha_objetivo: $("#n-fecha", cuerpo).value || null,
          icono: $("#n-icono", cuerpo).value.trim() || null, color: $("#n-color", cuerpo).value,
        });
        cerrar();
        aviso("Meta creada");
        alGuardar();
      });
    };
  });
}

export default {
  titulo: () => "Metas de ahorro",
  atras: true,
  async render(main) {
    const metas = await api.get("/metas");
    main.innerHTML = `${
      metas.length
        ? metas.map((m) => htmlMeta(m)).join("")
        : `<section class="tarjeta"><div class="vacio"><strong>Aún no tienes metas</strong>Un viaje, una moto, un fondo de emergencia: ponle nombre y monto, y ve cuánto llevas.</div></section>`
    }
      <button class="btn bloque" data-nueva>Nueva meta</button>
      <p class="pequeno suave" style="text-align:center">Lo que apartas aquí no mueve el saldo de tus cuentas: es plata que ya tienes y reservas para tu meta.</p>`;
    const refrescar = () => this.render(main);
    $$("[data-meta]", main).forEach((b) => (b.onclick = async () => abrirMeta(await api.get(`/metas/${b.dataset.meta}`), refrescar)));
    $("[data-nueva]", main).onclick = () => formularioNueva(refrescar);
  },
};
