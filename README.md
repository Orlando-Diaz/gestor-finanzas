# Mis Finanzas — API

Backend de una app de finanzas personales: registra ingresos, gastos y transferencias entre tus cuentas
(efectivo, Nequi, banco...), controla presupuestos por categoría y entrega los datos listos para graficar.

Se usa desde el teléfono con una **app web instalable (PWA)** que sirve la propia API, pero esta es independiente
y se puede probar completa desde la documentación interactiva (`/docs`).

> **Estado:** backend, app web y configuración de despliegue completos y probados (SQLite y PostgreSQL).

## Funcionalidades

- **App móvil (PWA)**: instalable en el celular, con modo claro/oscuro, inicio con el total de tu plata,
  gráficas, historial, presupuestos, cuentas, categorías, recurrentes, avisos y exportación. Sin librerías
  externas ni paso de compilación: HTML, CSS y JavaScript puros en `static/`.
- **Cuentas propias** por usuario (efectivo, bancaria, billetera digital, tarjeta de crédito). El saldo
  de cada una se **calcula** a partir del saldo inicial y los movimientos, nunca se guarda.
- **Movimientos**: ingresos, gastos y transferencias entre cuentas, con filtros (fechas, tipo, cuenta,
  categoría) y paginación.
- **Categorías**: 18 predeterminadas compartidas + las propias de cada usuario, con un nivel de subcategorías.
- **Presupuestos mensuales** por categoría con progreso (gastado, restante, estado `OK`/`ALERTA`/`EXCEDIDO`),
  alertas automáticas y copia del mes anterior.
- **Movimientos recurrentes** (arriendo, salario, suscripciones): semanal, quincenal (15 y fin de mes),
  mensual y anual. Se registran solos al arrancar, al iniciar sesión o bajo demanda.
- **Notificaciones** (alertas de presupuesto y recurrentes registradas) con contador de no leídas.
- **Resúmenes para gráficas**: balance del mes, gastos por categoría, gasto por día, ingresos vs gastos por mes
  (barras) y evolución del balance (línea). La app los muestra junto con una comparación contra el mes anterior.
- **Exportación a CSV** que abre bien en Excel (tildes, separador y decimales de Colombia).
- **Cuenta de usuario**: registro, login con JWT, cambio de nombre y de contraseña, eliminación de la cuenta
  con todos sus datos.

## Stack

Python 3.10+ · FastAPI · SQLAlchemy 2 · Pydantic 2 · Alembic · PyJWT · bcrypt · pytest.
SQLite para desarrollo y PostgreSQL para producción (misma base de código, probado en ambos).

## Cómo ejecutarlo (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

- **La app**: abre <http://127.0.0.1:8000/> y crea tu cuenta.
- **La documentación de la API**: <http://127.0.0.1:8000/docs> (pulsa **Authorize** para iniciar sesión y probar los endpoints).

Al arrancar, la app aplica las migraciones y crea las categorías predeterminadas.

### Probarla en tu celular (misma red Wi-Fi)

```powershell
uvicorn app.main:app --host 0.0.0.0 --reload
ipconfig          # busca la "Dirección IPv4" de tu PC, por ejemplo 192.168.1.20
```

En el celular abre `http://192.168.1.20:8000` (Windows puede pedir permiso en el firewall).
Para **instalarla** como app (botón "Agregar a pantalla de inicio") el navegador exige HTTPS, así que eso se hace
una vez desplegada (ver *Despliegue*); en el PC sí funciona con `localhost`.

> Si ya habías arrancado una versión anterior (sin migraciones), borra el archivo `mis_finanzas.db`
> —solo tenía datos de prueba— y vuelve a arrancar.

### Variables de entorno (`.env`)

| Variable | Para qué sirve | Por defecto |
|---|---|---|
| `DATABASE_URL` | Base de datos (`sqlite:///./mis_finanzas.db` o `postgresql+psycopg2://...`) | SQLite local |
| `SECRET_KEY` | Firma de los tokens. Genera uno: `python -c "import secrets; print(secrets.token_urlsafe(48))"` | valor de desarrollo |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de la sesión (en el celular conviene larga: `10080` = 7 días) | `60` |
| `MONEDA_POR_DEFECTO` | Moneda de los usuarios nuevos | `COP` |
| `ENTORNO` | Con `produccion` se exige un `SECRET_KEY` seguro y `BCRYPT_ROUNDS` ≥ 10 | `desarrollo` |
| `BCRYPT_ROUNDS` | Costo del hash de contraseñas | `12` |

**Nunca subas el archivo `.env` a GitHub** (ya está en `.gitignore`).

## Despliegue (Render + Neon)

La app es un solo servicio: la API y la PWA salen del mismo proceso. Se despliega gratis con
[Render](https://render.com) (la app) y [Neon](https://neon.com) (PostgreSQL).

> **¿Por qué no la base de Render?** Sus bases gratuitas [expiran a los 30 días](https://render.com/changelog/free-postgresql-instances-now-expire-after-30-days-previously-90)
> (y se borran tras 14 más). Para datos financieros eso no sirve; Neon no tiene esa caducidad.

1. **Base de datos**: crea un proyecto en Neon y copia la *connection string* (`postgresql://...?sslmode=require`).
2. **Código**: sube el repositorio a GitHub (el archivo `render.yaml` ya describe el servicio).
3. **App**: en Render, *New → Blueprint*, elige el repositorio y, cuando pida `DATABASE_URL`, pega la cadena de Neon.
   `SECRET_KEY` se genera sola.
4. Abre la URL `https://mis-finanzas-xxxx.onrender.com`, crea tu cuenta y, desde el celular, usa
   *Agregar a pantalla de inicio* para instalarla.

Las migraciones se aplican solas al arrancar. En el plan gratuito de Render el servicio se duerme tras unos
15 minutos sin uso: la primera visita después tarda alrededor de un minuto en despertar.

## Pruebas

```powershell
python -m pytest -q
```

Por defecto usan SQLite en memoria. Para correrlas también contra PostgreSQL:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg2://usuario:clave@localhost:5432/pruebas"
python -m pytest -q
```

La base indicada se **vacía** en cada prueba: usa una dedicada a pruebas. El flujo de GitHub Actions
(`.github/workflows/tests.yml`) ejecuta ambas variantes en cada push.

## Migraciones

```powershell
alembic upgrade head                                   # aplicar (la app ya lo hace al arrancar)
alembic revision --autogenerate -m "describe el cambio" # tras modificar un modelo
alembic downgrade -1                                   # deshacer la última
```

Hay una prueba que falla si cambias un modelo y olvidas crear su migración.

## Endpoints

| Grupo | Rutas |
|---|---|
| Autenticación | `POST /auth/registro` · `POST /auth/login` · `GET`/`PATCH /auth/me` · `POST /auth/cambiar-password` · `POST /auth/eliminar-cuenta` |
| Cuentas | `GET`/`POST /cuentas` · `GET`/`PATCH`/`DELETE /cuentas/{id}` |
| Categorías | `GET`/`POST /categorias` · `PATCH`/`DELETE /categorias/{id}` |
| Movimientos | `GET`/`POST /transacciones` · `GET`/`PATCH`/`DELETE /transacciones/{id}` |
| Presupuestos | `GET`/`POST /presupuestos` · `POST /presupuestos/copiar` · `GET`/`PATCH`/`DELETE /presupuestos/{id}` |
| Recurrentes | `GET`/`POST /recurrentes` · `POST /recurrentes/procesar` · `GET`/`PATCH`/`DELETE /recurrentes/{id}` |
| Notificaciones | `GET /notificaciones` · `GET /notificaciones/conteo` · `POST /notificaciones/leer-todas` · `PATCH /notificaciones/{id}/leer` · `DELETE /notificaciones/{id}` |
| Resumen | `GET /resumen/mes` · `/resumen/por-categoria` · `/resumen/por-dia` · `/resumen/serie-mensual` · `/resumen/evolucion-balance` |
| Exportar | `GET /exportar/transacciones` (CSV) |
| Salud | `GET /salud` |
| App web | `GET /` (PWA), `/manifest.webmanifest`, `/sw.js` |

## Decisiones de diseño

- **Dinero con `Numeric(14,2)`**, nunca `float`. Los montos son siempre positivos y el signo lo da el tipo.
- **El saldo se calcula**, no se guarda: no puede quedar desincronizado.
- **Una transferencia es una sola fila** (origen y destino) y no cuenta como ingreso ni gasto en los resúmenes.
- **Reglas en la base de datos, no solo en el código**: monto > 0, transferencia con destino distinto del origen,
  nombre de cuenta único por usuario, una recurrente no genera dos veces el mismo día.
- **Aislamiento por usuario**: todo se filtra por el usuario autenticado y los recursos ajenos responden `404`
  (no se revela que existen).
- **Historial protegido**: una cuenta o categoría con movimientos no se borra, se archiva.
- **Alertas sin ruido**: cada presupuesto avisa una sola vez al llegar al umbral y otra al excederse; al cambiar
  el límite se reinician.
- **Seguridad**: contraseñas con bcrypt, JWT con huella de la contraseña (cambiarla cierra las sesiones abiertas),
  login que no revela qué correos existen, exportación CSV protegida contra inyección de fórmulas.
- **App sin dependencias de compilación**: la PWA son módulos ES nativos; las gráficas son SVG propios y las
  fuentes viajan con la app, así que abre también con poca señal. El service worker solo guarda la "carcasa":
  los datos financieros nunca se almacenan en caché.
- **Zona horaria**: "hoy" se calcula en hora de Colombia (UTC-5, sin horario de verano).

## Estructura

```
app/
  api/         routers (un archivo por grupo de endpoints) y dependencias
  core/        configuración, base de datos, seguridad, fechas, migraciones
  models/      tablas (SQLAlchemy)
  schemas/     validación de entrada y salida (Pydantic)
  services/    lógica de negocio: saldos, presupuestos, recurrentes, arranque
static/        app web (PWA): index.html, manifest, service worker, css/, js/ (módulos por pantalla), fonts/, icons/
alembic/       migraciones
tests/         pruebas (SQLite y PostgreSQL)
```

## Pendiente

- Ideas: metas de ahorro, deudas ("me deben" / "debo"), importar el extracto del banco, etiquetas
