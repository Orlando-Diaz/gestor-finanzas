// Gastos por categoría.
import { crearVistaPorCategoria } from "./porCategoria.js";

export default crearVistaPorCategoria({
  tipo: "GASTO",
  titulo: "Gastos por categoría",
  totalEtiqueta: "Total gastado",
  vacio: "No hay gastos en este periodo.",
  sinMovimientos: "Sin gastos",
  deTus: "de tus gastos",
});
