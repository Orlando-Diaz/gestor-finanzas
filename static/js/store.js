// Datos compartidos entre pantallas (cuentas, categorías, usuario, notificaciones sin leer).
import { api } from "./api.js";
import { fijarMoneda } from "./util.js";

export const store = { usuario: null, cuentas: [], categorias: [], noLeidas: 0 };

export async function recargarCuentas() {
  store.cuentas = await api.get("/cuentas");
}
export async function recargarCategorias() {
  store.categorias = await api.get("/categorias");
}
export async function recargarConteo() {
  try {
    store.noLeidas = (await api.get("/notificaciones/conteo")).no_leidas;
  } catch {
    /* el contador es decorativo: si falla no estorba */
  }
  window.dispatchEvent(new Event("mf:conteo"));
}
export async function cargarBase() {
  const [usuario, cuentas, categorias] = await Promise.all([api.get("/auth/me"), api.get("/cuentas"), api.get("/categorias")]);
  Object.assign(store, { usuario, cuentas, categorias });
  fijarMoneda(usuario.moneda_por_defecto);
  await recargarConteo();
}
export function vaciarStore() {
  Object.assign(store, { usuario: null, cuentas: [], categorias: [], noLeidas: 0 });
}

export const categoriaPorId = (id) => store.categorias.find((c) => c.id === id);
