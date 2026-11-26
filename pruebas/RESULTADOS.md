# Resultados de las pruebas · EntradasYa

**Asignatura:** Puesta en Producción Segura · 2026-27
**Alumno:** Mohammed Ghayat Zayoun
**Fecha de ejecución:** 25 y 26 de noviembre de 2026
**Entorno:** despliegue local con Docker Compose (`docker-compose.yml` + `docker-compose.pruebas.yml`),
Windows 11, Python 3.12, Firefox.

Las pruebas y las instrucciones para repetirlas están en [`README.md`](README.md). Todas se
lanzan desde la aplicación `ejecutar_pruebas.py`, que genera un informe HTML por ejecución
en `resultados/`.

## 1. Resumen

| Prueba | Herramienta | Resultado |
| --- | --- | --- |
| Funcionales de la API y del despliegue | pytest + httpx | **91 / 91 superadas** |
| Funcionales en el navegador (E2E) | pytest + Selenium (Firefox) | **29 / 29 superadas** |
| Carga: 420 usuarios simultáneos | Locust | **0,01 % de errores**, p95 global de 78 ms |
| Simulación de ataque DoS de capa 7 | Locust | **98 % del ataque bloqueado**, backend sin fallos |

## 2. Pruebas funcionales de la API (91 casos)

| Bloque | Casos | Resultado |
| --- | --- | --- |
| Salud y catálogo (`test_1`) | 10 | ✔ |
| Registro e inicio de sesión (`test_2`) | 17 | ✔ |
| JWT: tokens manipulados, `alg: none`, caducados, rotación del refresh, revocación (`test_3`) | 15 | ✔ |
| Roles y autorización (`test_4`) | 19 | ✔ |
| Compras, pagos, check-in y concurrencia (`test_5`) | 10 | ✔ |
| Configuración segura del despliegue (`test_6`) | 14 | ✔ |
| Protección frente a DoS (`test_7`) | 6 | ✔ |

Datos destacados:

- **Compras simultáneas:** 15 compras a la vez sobre 5 entradas → exactamente 5 aceptadas y
  10 rechazadas (409). No hay sobreventa.
- **Inundación de la API:** 300 peticiones en 0,5 s desde una IP → 49 atendidas y
  **251 bloqueadas (429)**, sin errores 5xx; la web sigue respondiendo tras el ataque.
- **Slowloris:** Nginx cierra la conexión incompleta a los **10,0 s** (`client_header_timeout`).
- **Fuerza bruta en el login:** 40 intentos simultáneos → la mayoría reciben 429.
- Cuerpo de 2 MB → 413; cabeceras de 64 KB → 400.

## 3. Pruebas funcionales en el navegador con Selenium (29 casos)

| Bloque | Casos | Resultado |
| --- | --- | --- |
| Navegación sin sesión: portada HTTPS, listado, filtros, búsqueda, detalle, 404 | 7 | ✔ |
| Cuentas: registro y sus validaciones, login, logout, **la sesión sobrevive a recargar** | 10 | ✔ |
| Compra completa: pago rechazado → reintento → entradas → "Mis entradas" | 4 | ✔ |
| Roles y validación de entradas: panel de gestión por rol, **check-in en puerta** | 7 | ✔ |
| Seguridad en el navegador: tokens inaccesibles desde JavaScript, cookie `HttpOnly`/`Secure`/`Strict`, XSS, CSP | 4 | ✔ |

Las capturas de pantalla de cada paso están en `resultados/capturas/`.

## 4. Prueba de carga: 420 usuarios simultáneos (despliegue local)

Perfil `carga`: rampa de 2 minutos hasta 420 usuarios y 5 minutos estables. El 70 % de los
usuarios navega por el catálogo y el 30 % se registra, compra, paga, consulta sus pedidos y
refresca el token. Cada usuario espera entre 5 y 15 s entre acciones.

| Métrica | Resultado | Objetivo | |
| --- | --- | --- | --- |
| Peticiones totales | 16.263 (≈ 39 por segundo) | — | |
| Errores | 1 (0,01 %) | < 1 % | ✔ |
| p95 del catálogo (`/api/events`) | 28–39 ms | < 500 ms | ✔ |
| p95 de login / registro (Argon2id) | 180 / 170 ms | < 2 s | ✔ |
| p95 de reservar / pagar | 66 / 67 ms | < 1 s | ✔ |
| Mediana / p95 / p99 / máximo global | 14 / 78 / 140 / 390 ms | — | |

Tiempos por operación (ms):

| Operación | Peticiones | Mediana | p95 | p99 |
| --- | ---: | ---: | ---: | ---: |
| `POST /api/auth/login` | 437 | 99 | 180 | 270 |
| `POST /api/auth/register` | 126 | 110 | 170 | 210 |
| `POST /api/auth/refresh` | 488 | 10 | 27 | 53 |
| `GET /api/events` (portada) | 5.767 | 14 | 39 | 100 |
| `GET /api/events` (filtros) | 2.132 | 13 | 37 | 89 |
| `GET /api/events/[slug]` | 4.076 | 12 | 34 | 81 |
| `GET /api/categories` | 1.064 | 10 | 26 | 65 |
| `GET /api/orders` | 453 | 19 | 59 | 140 |
| `POST /api/orders` (reservar) | 860 | 26 | 66 | 170 |
| `POST /api/orders/[ref]/pay` | 769 | 22 | 67 | 130 |
| `POST /api/orders/[ref]/cancel` | 91 | 17 | 42 | 120 |

El único error fue una conexión cerrada por el servidor justo cuando el cliente iba a
reutilizarla (`RemoteDisconnected`), un error de red y no de la aplicación.

**Conclusión:** con una sola instancia de la API, la aplicación atiende a 420 usuarios
simultáneos con holgura. La operación más costosa es el login/registro, por el hash Argon2id
(diseñado para ser lento frente a ataques de fuerza bruta), y aun así su p95 es de 180 ms.

## 5. Simulación de ataque DoS de capa 7 (despliegue local)

300 bots piden la API sin pausa a través de Nginx durante 2 minutos, mientras un monitor
consulta `/health` directamente en el backend cada segundo.

| Métrica | Resultado |
| --- | --- |
| Peticiones de ataque | 119.048 (≈ 1.000 por segundo) |
| Bloqueadas por Nginx (429) | **116.630 (98,0 %)** |
| Atendidas (200) | 2.418 (2,0 %) |
| Otros errores | 0 |
| Backend durante el ataque (`/health`) | 83 comprobaciones, **0 fallos**, mediana 300 ms, p95 440 ms |

Las 2.418 peticiones atendidas coinciden con el límite configurado
(`API_RATE_LIMIT` = 20 peticiones/s durante 120 s, más la ráfaga de 40): Nginx descarta el
resto sin que lleguen al backend. El aumento de latencia de `/health` se debe a que Locust
genera las 1.000 peticiones por segundo en el mismo equipo que los contenedores y compite con
ellos por la CPU; el backend solo recibe 20 peticiones por segundo.

**Conclusión:** las medidas de Nginx (`limit_req`, `limit_conn`, tiempos de espera cortos y
límites de tamaño) frenan una inundación desde un origen y mantienen el servicio disponible.
Un DDoS distribuido o volumétrico real necesita además una protección de red delante
(CDN o servicio anti-DDoS), como se explica en el `README.md`.
