# EntradasYa · Frontend web

Frontend de la API de entradas (`../backend`, FastAPI), con una interfaz inspirada en
**Booking.com**: cabecera azul, buscador con recuadro amarillo, filtros laterales y
tarjetas de resultados.

## Stack

- **React 19** + **TypeScript**
- **Vite 8**
- **Tailwind CSS 4** (vía `@tailwindcss/vite`)
- **React Router 7**
- **Autenticación:** JWT stateless: access token en memoria y refresh token en cookie `HttpOnly` (`src/auth/`)

## Requisitos

Tener el backend en marcha (`../backend`) en `http://localhost:3000`.
Consulta su README para crear la base de datos y arrancarlo con `uvicorn`.

## Arrancar el frontend

```bash
npm install
npm run dev
```

Abre **http://localhost:5173**.

> En desarrollo, Vite hace de **proxy** de `/api` y `/health` hacia
> `http://localhost:3000` (ver `vite.config.ts`). Así frontend y API comparten
> origen, igual que en producción detrás de un proxy inverso, y la cookie
> `SameSite=Strict` del refresh funciona sin CORS.

## Configuración

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `VITE_API_URL` | `/api` | URL base de la API. Lo recomendado es dejar `/api` y servir la API en el mismo dominio con un proxy inverso. |

Crea un `.env` si quieres sobreescribirla:

```env
VITE_API_URL=http://localhost:3000/api
```

## Scripts

| Script | Descripción |
| --- | --- |
| `npm run dev` | Servidor de desarrollo con recarga en caliente |
| `npm run build` | Comprueba tipos y genera `dist/` |
| `npm run preview` | Sirve el build de producción en el puerto 4173 |

## Estructura

```
src/
  api/         cliente HTTP (Bearer + refresco automático del JWT) y tipos de la API
  auth/        tokenStore (access en memoria, refresco single-flight) y AuthContext
  components/  Header, Footer, SearchBar, EventCard, Filters, CardFields, ProtectedRoute, Icons...
  hooks/       useAsync (fetch con estados de carga/error)
  lib/         formato (fechas, dinero), constantes (tipos de evento, estados)
  pages/       Home, Events, EventDetail, Checkout, Order, Validator, Login, Register, Account, NotFound
  App.tsx      rutas y layout
```

## Rutas

| Ruta | Página |
| --- | --- |
| `/` | Inicio con buscador, categorías y eventos destacados |
| `/eventos` | Resultados con filtros (tipo, ciudad, fecha) y ordenación |
| `/eventos/:slug` | Detalle del evento y selección de entradas |
| `/acceder` | Iniciar sesión |
| `/registro` | Crear una cuenta |
| `/cuenta` | 🔒 Mis entradas (pedidos del usuario) |
| `/checkout?event=…&items=…` | 🔒 Datos del comprador y pago simulado |
| `/pedido/:reference` | Estado del pedido, entradas y reintento de pago |
| `/validar` | Consultar/validar una entrada por código |

## Autenticación

- Para comprar hay que **crear una cuenta o iniciar sesión** (`/registro` y `/acceder`).
- La sesión es **stateless**: el backend no guarda nada.
  - El **access token** (JWT, 15 min) se guarda **solo en memoria** y se envía en
    `Authorization: Bearer`.
  - El **refresh token** (JWT, 7 días) lo pone el servidor en una cookie
    `HttpOnly; SameSite=Strict; Path=/api/auth`. El JavaScript **no puede leerlo**.
  - Al recargar o cuando caduca el access, `src/auth/tokenStore.ts` llama a
    `POST /api/auth/refresh` (una sola vez aunque haya varias peticiones a la vez).
    Si una petición recibe 401, se refresca y se reintenta una vez.
  - En `localStorage` solo hay una marca sin secretos (`entradas:has-session`).
- Las rutas `/checkout` y `/cuenta` están **protegidas**: sin sesión redirigen a
  `/acceder` y, tras entrar, vuelven al destino original.
- En la cabecera verás **Acceder / Crear cuenta** (anónimo) o **Mis entradas / Salir**
  (autenticado). El checkout precarga los datos del comprador desde tu cuenta.

### Cuenta de demostración

Tras `scripts/init_db.py` en el backend:

| Rol | Email | Contraseña |
| --- | --- | --- |
| CLIENT | `ana.garcia@ejemplo.com` | `demo1234` |
| MANAGER | `gestor@entradas.com` | `Gestor1234` |
| ADMIN | `admin@entradas.com` | `Admin1234` |

## Flujo de compra

1. Inicia sesión (o crea una cuenta) — es obligatorio para reservar.
2. En el detalle del evento eliges cantidades y pulsas **Reservar entradas**.
3. En el checkout rellenas los datos del comprador (precargados de tu cuenta) y la tarjeta.
4. Se crea el pedido (`POST /api/orders`) y se paga (`POST /api/orders/:ref/pay`).
5. Si el pago se aprueba, vas al pedido con tus entradas (códigos `XXXX-XXXX-XXXX`).

### Pago simulado

- **Tarjeta válida:** cualquier número terminado en algo distinto de `0002`
  (p. ej. `4242 4242 4242 4242`). El pago se **aprueba**.
- **Tarjeta rechazada:** cualquier número terminado en **`0002`**
  (p. ej. `4000 0000 0000 0002`). El pago se **rechaza** (HTTP 402) y el pedido
  queda pendiente para reintentar.

En el formulario hay dos botones para rellenar automáticamente estos casos de prueba.

## Notas

- Las imágenes de los eventos provienen de `imageUrl` (picsum). Si no hay conexión,
  la tarjeta muestra un fondo con el icono del tipo de evento.
- El backend admite varios tipos a la vez en el filtro: `GET /api/events?type=MUSEUM,CINEMA`.
- Tras `scripts/init_db.py` en el backend, el catálogo tiene 39 eventos y hay **pedidos de demo**
  que puedes abrir directamente:
  - `/pedido/ORD-DEMO0001` → pagado, con 2 entradas.
  - `/pedido/ORD-DEMO0002` → pendiente, con un pago rechazado.
