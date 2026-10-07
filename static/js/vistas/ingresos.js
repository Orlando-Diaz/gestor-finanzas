// Ingresos por categoría.
import { crearVistaPorCategoria } from "./porCategoria.js";

export default crearVistaPorCategoria({
  tipo: "INGRESO",
  titulo: "Ingresos por categoría",
  totalEtiqueta: "Total recibido",
  vacio: "No hay ingresos en este periodo.",
  sinMovimientos: "Sin ingresos",
  deTus: "de tus ingresos",
});
