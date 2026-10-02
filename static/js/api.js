// Cliente de la API. El token vive en localStorage (con respaldo en memoria si el navegador lo bloquea).

const CLAVE = "mf.token";
let enMemoria = null;

export const sesion = {
  get token() {
    try {
      return localStorage.getItem(CLAVE) ?? enMemoria;
    } catch {
      return enMemoria;
    }
  },
  guardar(t) {
    enMemoria = t;
    try {
      localStorage.setItem(CLAVE, t);
    } catch {
      /* sin almacenamiento: la sesión dura mientras la pestaña esté abierta */
    }
  },
  limpiar() {
    enMemoria = null;
    try {
      localStorage.removeItem(CLAVE);
    } catch {
      /* nada */
    }
  },
};

export class ApiError extends Error {
  constructor(status, mensaje) {
    super(mensaje);
    this.status = status;
  }
}

function mensajeDeError(status, cuerpo) {
  const d = cuerpo?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) {
    return d
      .map((e) => {
        const campo = Array.isArray(e.loc) ? e.loc.filter((x) => x !== "body" && x !== "query").join(".") : "";
        const msg = String(e.msg || "").replace(/^Value error, /, "");
        return campo ? `${campo}: ${msg}` : msg;
      })
      .join(". ");
  }
  if (status >= 500) return "Algo falló en el servidor. Inténtalo de nuevo en un momento.";
  return `Error ${status}`;
}

async function pedir(metodo, ruta, { query, json, form, archivo } = {}) {
  const url = new URL(ruta, location.origin);
  for (const [k, v] of Object.entries(query || {})) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  const cabeceras = {};
  if (sesion.token) cabeceras.Authorization = `Bearer ${sesion.token}`;
  let cuerpo;
  if (json !== undefined) {
    cabeceras["Content-Type"] = "application/json";
    cuerpo = JSON.stringify(json);
  } else if (form) {
    cuerpo = new URLSearchParams(form);
  }
  let r;
  try {
    r = await fetch(url, { method: metodo, headers: cabeceras, body: cuerpo });
  } catch {
    throw new ApiError(0, "No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.");
  }
  if (r.status === 204) return null;
  if (archivo && r.ok) return r.blob();
  let datos = null;
  try {
    datos = await r.json();
  } catch {
    /* sin cuerpo JSON */
  }
  if (!r.ok) {
    // 401 con sesión abierta = token vencido. En el login, un 401 es "clave incorrecta".
    if (r.status === 401 && sesion.token && ruta !== "/auth/login") {
      sesion.limpiar();
      window.dispatchEvent(new CustomEvent("mf:sesion-vencida", { detail: { vencida: true } }));
    }
    throw new ApiError(r.status, mensajeDeError(r.status, datos));
  }
  return datos;
}

export const api = {
  get: (ruta, query) => pedir("GET", ruta, { query }),
  archivo: (ruta, query) => pedir("GET", ruta, { query, archivo: true }),
  post: (ruta, json) => pedir("POST", ruta, { json }),
  patch: (ruta, json) => pedir("PATCH", ruta, { json }),
  borrar: (ruta) => pedir("DELETE", ruta),
  async login(email, password) {
    const t = await pedir("POST", "/auth/login", { form: { username: email, password } });
    sesion.guardar(t.access_token);
  },
  registro: (nombre, email, password) => pedir("POST", "/auth/registro", { json: { nombre, email, password } }),
};
