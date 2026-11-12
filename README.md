# EntradasYa: aplicación web distribuida de venta de entradas

Práctica de **Puesta en Producción Segura**. Venta de entradas para museos,
fútbol, cine y festivales, con backend y frontend separados.

```
entradas-app/
├── backend/    API REST con FastAPI + PostgreSQL (SQLAlchemy 2)
└── frontend/   SPA con React 19 + TypeScript + Vite + Tailwind
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