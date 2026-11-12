# Entradas API (FastAPI)

Backend de venta de entradas para museos, futbol, cine y festivales.

- **Framework:** FastAPI (Python 3.12)
- **Base de datos:** PostgreSQL + SQLAlchemy 2.0
- **Autenticacion:** JWT **100 % stateless**: la sesion no se guarda en el
  backend (requisito del enunciado). Access token (JWT, 15 min) en
  `Authorization: Bearer`; refresh token (JWT, 7 dias) en cookie `HttpOnly`.
- **Roles:** `ADMIN`, `MANAGER`, `CLIENT`.

## Requisitos

- Python 3.12+
- PostgreSQL en `localhost:5432`.

## Puesta en marcha

```powershell
cd backend

# 1. Entorno virtual e instalacion
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Configuracion
copy .env.example .env
# edita .env si tu PostgreSQL usa otras credenciales

# 3. Crear base de datos, esquema y datos iniciales
#    (en una BD de la version anterior, tambien elimina la tabla refresh_tokens
#    y anade users.token_version)
.venv\Scripts\python.exe scripts\init_db.py

# 4. Arrancar
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload
```

- API: <http://localhost:3000/api>
- Documentacion interactiva: <http://localhost:3000/docs>
- Salud: <http://localhost:3000/health>

## Usuarios de demostracion

| Rol | Email | Contrasena |
| --- | --- | --- |
| CLIENT | `ana.garcia@ejemplo.com` | `demo1234` |
| MANAGER | `gestor@entradas.com` | `Gestor1234` |
| ADMIN | `admin@entradas.com` | `Admin1234` |

## Autenticacion stateless y refresco del JWT

El enunciado exige que **la sesion no se almacene en el backend**. No hay tabla
de sesiones ni de tokens: todo lo necesario viaja firmado dentro de los JWT.

| | Access token | Refresh token |
| --- | --- | --- |
| Formato | JWT HS256 (`type=access`) | JWT HS256 (`type=refresh`) |
| Secreto | `JWT_SECRET` | `JWT_REFRESH_SECRET` (distinto) |
| Vida | 15 min | 7 dias **absolutos** desde el login |
| Transporte | Cabecera `Authorization: Bearer` | Cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/auth` |
| En el navegador | Solo en memoria (variable JS) | Cookie inaccesible para JavaScript |
| En el servidor | Nada | Nada |

### Flujo

1. `POST /api/auth/login` (o `/register`) devuelve el `accessToken` en el cuerpo
   y pone el refresh en la cookie con `Set-Cookie`.
2. Cada peticion protegida envia `Authorization: Bearer <accessToken>`.
3. Al recargar la pagina o al caducar el access, el frontend llama a
   `POST /api/auth/refresh` **sin cuerpo**: el navegador adjunta la cookie.
   El servidor verifica la firma, la caducidad y la version, y devuelve un
   access nuevo y **rota** la cookie (refresh nuevo con la misma caducidad
   absoluta: la sesion no se alarga indefinidamente).
4. Si varias peticiones necesitan refrescar a la vez, el frontend hace **una
   sola** llamada (*single flight*). Si una peticion recibe 401, refresca y la
   reintenta una vez; si el refresh falla, cierra la sesion.
5. `POST /api/auth/logout` borra la cookie. `POST /api/auth/logout-all`
   invalida los tokens en **todos** los dispositivos.

### Revocacion sin guardar sesiones: `token_version`

Un JWT stateless no se puede "borrar" del servidor. Para poder invalidarlo,
cada usuario tiene un entero `token_version` que viaja en el claim `ver` de
ambos tokens. Si no coincide con el valor actual, el token se rechaza. Se
incrementa en:

- `logout-all` (cerrar todas las sesiones);
- cambio de rol por un administrador (el JWT ya no reflejaria el rol real);
- desactivacion o reactivacion de la cuenta.

No es una sesion: es **un unico entero por usuario**, no un registro por login.

### Decisiones de seguridad

- **Refresh en cookie `HttpOnly`**: aunque un XSS ejecute codigo en la pagina,
  no puede leer el refresh token ni enviarlo a otro sitio. El access, en
  memoria, caduca en 15 minutos.
- **Anti-CSRF**: la cookie es `SameSite=Strict` (no viaja en peticiones
  iniciadas desde otros sitios), su `Path` es `/api/auth` (no se envia al
  resto de la API) y `/refresh`, `/logout` y `/logout-all` rechazan un
  `Origin` que no este en `CORS_ORIGINS`. Ademas, el resto de rutas se
  autentican con la cabecera `Authorization`, que un sitio ajeno no puede
  poner.
- **Secretos distintos y claim `type`**: un refresh no sirve como access ni al
  reves.
- **Caducidad absoluta**: la rotacion conserva `auth_time`; a los 7 dias del
  login hay que volver a entrar.
- **Limitacion conocida**: al ser stateless no hay deteccion de reutilizacion
  de un refresh ya rotado (eso exigiria guardarlos). Se mitiga con la cookie
  `HttpOnly` (el token no es accesible para robarlo), `token_version` y la
  vida absoluta de 7 dias.

## Login con Google

Implementado en `app/google_oauth.py` y `app/routers/google_auth.py` con
OpenID Connect (Authorization Code + PKCE + `state` + `nonce`). La
configuración, el diagrama del flujo y el análisis de amenazas están en el
[README de la raíz](../README.md#login-con-google).

## Endpoints principales

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| POST | `/api/auth/register` | publico |
| POST | `/api/auth/login` | publico |
| POST | `/api/auth/refresh` | cookie de refresh valida |
| POST | `/api/auth/logout` | publico (borra la cookie) |
| POST | `/api/auth/logout-all` | autenticado |
| GET | `/api/auth/me` | autenticado |
| GET | `/api/auth/providers` | publico |
| GET | `/api/auth/google/login` | publico (redirige a Google) |
| GET | `/api/auth/google/callback` | publico (vuelta de Google) |
| GET | `/api/categories` | publico |
| GET | `/api/venues` | publico |
| GET | `/api/events` | publico |
| GET | `/api/events/{idOrSlug}` | publico |
| POST | `/api/orders` | autenticado |
| GET | `/api/orders` | autenticado (propias) |
| GET | `/api/orders/{reference}` | publico (capacidad) |
| POST | `/api/orders/{reference}/pay` | autenticado (propietario) |
| POST | `/api/orders/{reference}/cancel` | autenticado (propietario) |
| GET | `/api/tickets/{code}` | publico (capacidad) |
| POST | `/api/tickets/{code}/check-in` | MANAGER/ADMIN |
| GET | `/api/admin/users` | ADMIN |
| PATCH | `/api/admin/users/{id}/role` | ADMIN |
| PATCH | `/api/admin/users/{id}/active` | ADMIN |
| GET | `/api/admin/orders` | MANAGER/ADMIN |
| GET | `/api/admin/stats` | MANAGER/ADMIN |
| POST/PATCH/DELETE | `/api/admin/events` | MANAGER/ADMIN |
| POST/PATCH/DELETE | `/api/admin/ticket-types` | MANAGER/ADMIN |
| POST/PATCH/DELETE | `/api/admin/venues` | MANAGER/ADMIN |

## Seguridad implementada

- Contrasenas con **Argon2id** (64 MiB, 3 iteraciones).
- JWT firmados HS256 con `iss`, `aud`, `exp`, `iat`, `jti`, `type` y `ver`; se
  valida todo. Secretos distintos para access y refresh.
- Sesion **stateless**: ningun token ni sesion se guarda en el servidor.
- Refresh en cookie `HttpOnly` + `Secure` (produccion) + `SameSite=Strict` +
  `Path=/api/auth`, con comprobacion de `Origin`.
- Autorizacion por rol **contra la base de datos** y `token_version`: un cambio
  de rol o una desactivacion invalidan los tokens al instante.
- CORS restringido a una lista explicita de origenes.
- La API se niega a arrancar en produccion con secretos de desarrollo,
  secretos iguales o cookie sin `Secure`.
- Cabeceras `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, CSP y HSTS en produccion.
- Rate limiting en login/registro/refresh (20/min por IP).
- Mensajes de error uniformes; los detalles internos solo se registran.
- `--reset` en `init_db.py` es explicito para evitar borrados accidentales.

## Pruebas rapidas

```powershell
# Login
curl.exe -s -X POST http://localhost:3000/api/auth/login `
  -H "Content-Type: application/json" `
  -c cookies.txt `
  -d '{\"email\":\"admin@entradas.com\",\"password\":\"Admin1234\"}'

# Con el accessToken devuelto:
curl.exe -s http://localhost:3000/api/auth/me -H "Authorization: Bearer <TOKEN>"

# Refrescar usando la cookie guardada (rota la cookie)
curl.exe -s -X POST http://localhost:3000/api/auth/refresh -b cookies.txt -c cookies.txt

# Prueba completa (requiere la API en marcha)
.venv\Scripts\python.exe scripts\smoke_test.py
```
