# EntradasYa: aplicación web distribuida de venta de entradas

Práctica de **Puesta en Producción Segura**. Venta de entradas para museos,
fútbol, cine y festivales, con backend y frontend separados.

```
entradas-app/
├── backend/             API REST con FastAPI + PostgreSQL (SQLAlchemy 2) + Dockerfile
├── frontend/            SPA con React 19 + TypeScript + Vite + Dockerfile (Nginx)
│   └── nginx/           proxy inverso HTTPS, cabeceras de seguridad, TLS
├── scripts/             utilidades (generar secretos)
└── docker-compose.yml   despliegue completo
```

## Requisitos del enunciado

| Requisito | Implementación |
| --- | --- |
| Backend y frontend separados | `backend/` (FastAPI, Python) y `frontend/` (React) son aplicaciones independientes que se comunican por HTTP. |
| Backend en framework Python | FastAPI 0.115+ con Pydantic v2 y SQLAlchemy 2. |
| Registro de usuarios | `POST /api/auth/register`. Contraseñas con Argon2id. Todo registro nuevo recibe el rol `CLIENT`. |
| La sesión no se almacena en el backend | Autenticación **100 % stateless**: no hay tabla de sesiones ni de tokens. |
| Mínimo 3 roles | `ADMIN`, `MANAGER` (gestor) y `CLIENT`, comprobados en cada endpoint (`require_roles`). |
| API REST con JWT | Access token JWT (15 min) en `Authorization: Bearer`. |
| Refresco del JWT | Refresh token JWT (7 días, secreto distinto) en cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/auth`, con rotación en cada uso y caducidad absoluta. |

Los detalles de diseño y seguridad están en [`backend/README.md`](backend/README.md).

## Roles

| Rol | Puede |
| --- | --- |
| `CLIENT` | Ver el catálogo, comprar entradas y consultar sus pedidos. |
| `MANAGER` | Lo anterior, además de gestionar eventos, recintos y tipos de entrada, ver pedidos y estadísticas y validar entradas en la puerta. |
| `ADMIN` | Todo lo anterior, además de gestionar usuarios (cambiar roles y activar o desactivar cuentas). |

## Despliegue con Docker (producción)

Requisitos: Docker Desktop.

```powershell
# 1. Generar el .env con secretos aleatorios (no se sube al repo)
powershell -ExecutionPolicy Bypass -File scripts\generar-env.ps1

# 2. Construir y arrancar
docker compose up -d --build

# 3. Comprobar el estado (los tres servicios deben estar "healthy" o "running")
docker compose ps
```

Abre **https://localhost**. El certificado es autofirmado, así que el navegador
mostrará un aviso: acéptalo para continuar. En un servidor real se monta un
certificado de una CA (por ejemplo, Let's Encrypt) en el volumen `tls-certs`.

### Arquitectura

```
Navegador ──HTTPS:443──▶ Nginx (frontend) ──┬── /            SPA (ficheros estáticos)
     └──HTTP:80 → 301 HTTPS                 └── /api/, /health ──▶ API FastAPI :3000 ──▶ PostgreSQL :5432
                         red "web"                               red "web" + "db"        red "db" (interna)
```

### Medidas de seguridad del despliegue

| Capa | Medida |
| --- | --- |
| Red | Solo Nginx publica puertos (80 y 443). La API y PostgreSQL no son accesibles desde fuera; la BD está en una red `internal` sin salida a Internet. |
| Transporte | HTTPS obligatorio (HTTP redirige con 301), TLS 1.2/1.3 con cifrados AEAD, HSTS y `http2`. |
| Secretos | En `.env` (excluido de git y de las imágenes por `.dockerignore`), generados con un RNG criptográfico. El compose no arranca si faltan. La API se niega a arrancar en producción con secretos débiles o iguales. |
| Contenedores | Ningún proceso corre como root (API como `app`, Nginx como `101`). `cap_drop: ALL`, `no-new-privileges` y sistema de ficheros de solo lectura en la API. Código de la API propiedad de root (no modificable por el proceso). |
| Imágenes | Base `slim`/`alpine`. Build multi-etapa: la imagen del frontend solo contiene los estáticos compilados, sin código fuente ni `node_modules`. |
| HTTP | CSP estricta (sin scripts inline ni `eval`), `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP, `server_tokens off` y API sin cabecera `Server`. |
| Fuerza bruta | Rate limit en Nginx (`/api/auth/`: 10 peticiones/min por IP, ráfaga 10) y en la API (20/min). Nginx pasa la IP real en `X-Forwarded-For` sobrescribiéndola, para que el cliente no pueda falsearla. |
| Superficie | `/docs` y `/openapi.json` desactivados en producción. Nginx nunca sirve ficheros ocultos (`.git`, `.env`). |
| Datos | PostgreSQL en un volumen persistente (`db-data`). `SEED_DEMO_DATA=false` evita crear los usuarios de demostración en un despliegue real. |

### Comandos útiles

```powershell
docker compose logs -f backend        # logs de la API
docker compose down                   # parar (conserva los datos)
docker compose down -v                # parar y BORRAR datos y certificado
```

## Puesta en marcha (desarrollo)

Requisitos: Python 3.12+, Node.js 20+ y PostgreSQL en `localhost:5432`.

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env          # y edita los valores
.venv\Scripts\python.exe scripts\init_db.py
.venv\Scripts\python.exe -m uvicorn app.main:app --port 3000 --reload

# Frontend (en otra terminal)
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

Usuarios de demostración (creados por `init_db.py`):

| Rol | Email | Contraseña |
| --- | --- | --- |
| CLIENT | `ana.garcia@ejemplo.com` | `demo1234` |
| MANAGER | `gestor@entradas.com` | `Gestor1234` |
| ADMIN | `admin@entradas.com` | `Admin1234` |

> Son credenciales de demostración para el entorno local. En producción se
> deben cambiar o eliminar.

## Pruebas

Con la API en marcha:

```powershell
cd backend
.venv\Scripts\python.exe scripts\smoke_test.py
```