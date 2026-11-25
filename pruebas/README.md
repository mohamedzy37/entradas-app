# Pruebas funcionales y de estrés de EntradasYa

| Tipo | Herramienta | Carpeta | Qué comprueba |
| --- | --- | --- | --- |
| Funcionales de la API | pytest + httpx | `funcionales/` | Que cada endpoint hace lo que debe y que la seguridad (JWT, roles, cookies, validación, despliegue) se cumple |
| Funcionales en el navegador (E2E) | pytest + **Selenium** | `e2e/` | Que un usuario real puede registrarse, comprar, pagar y validar entradas en la web, y lo que ve cada rol |
| Carga y estrés | Locust | `estres/` | Que la aplicación aguanta **420 usuarios simultáneos** (local) y cómo responde producción (Render) |
| Protección DDoS | pytest + Locust | `funcionales/test_7_ddos.py`, `estres/ddos_locustfile.py` | Que Nginx frena inundaciones, conexiones lentas (Slowloris) y peticiones enormes sin que caiga el servicio |

Las pruebas son de **caja negra**: no importan código de la aplicación, así
que sirven tanto para el despliegue con Docker como para Render.

Para lanzarlas hay una **aplicación con ventana** (`ejecutar_pruebas.py`): ver
el apartado 3.

## 1. Pruebas funcionales de la API

| Fichero | Casos |
| --- | --- |
| `test_1_salud.py` | `/health`, catálogo paginado, eventos visibles, 404, validación de parámetros, inyección SQL en la búsqueda, `/docs` desactivado en producción |
| `test_2_registro_login.py` | Registro, cookie del refresh (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/api/auth`), no se puede elegir rol al registrarse, email duplicado, validación de contraseña, login de los 3 roles, anti-enumeración de usuarios |
| `test_3_tokens_jwt.py` | Claims del access token, tokens manipulados / firmados con otra clave / `alg: none` / caducados, refresh con rotación y caducidad absoluta, refresh desde otro origen (CSRF), logout y logout global |
| `test_4_roles.py` | Matriz de permisos ADMIN / MANAGER / CLIENT, escalada de privilegios, cambio de rol que revoca tokens, usuario desactivado, el admin no puede desactivarse |
| `test_5_pedidos.py` | Compra completa (reserva → pago rechazado → pago aprobado → entradas → check-in), cancelación con devolución de stock, pedidos ajenos, máximo por pedido, sobreventa y **15 compras simultáneas sobre 5 entradas** |
| `test_6_despliegue.py` | Redirección HTTP→HTTPS, cabeceras de seguridad, cabecera `Server` sin versión, ficheros ocultos, API en el mismo origen y **rate limit del login** (429) |
| `test_7_ddos.py` | **Anti-DDoS**: 300 peticiones simultáneas desde una IP se cortan con 429 sin errores 5xx, la web sigue disponible tras el ataque, los estáticos no se ven afectados, **Slowloris** (la conexión lenta se cierra a los 10 s), cuerpo de 2 MB → 413, cabeceras enormes → 400 |

Las pruebas crean sus propios usuarios y eventos (no gastan las entradas de
los eventos de demostración) y cancelan los eventos al terminar.

## 2. Pruebas funcionales en el navegador (Selenium)

Abren Firefox (o Chrome/Edge), hacen clic y escriben en la web como un usuario y
comprueban lo que aparece en pantalla. Guardan capturas de pantalla de los
pasos importantes en `resultados/capturas/` (y una captura automática si una
prueba falla).

| Fichero | Casos |
| --- | --- |
| `test_e2e_1_navegacion.py` | Portada por HTTPS, listado de eventos, filtro por tipo, búsqueda, detalle de un evento, página 404, el validador sin sesión solo permite consultar |
| `test_e2e_2_cuentas.py` | Registro, validación de la contraseña en el formulario, email ya registrado, login incorrecto, login y logout, **la sesión sobrevive a recargar la página** (refresh con la cookie HttpOnly), tras cerrar sesión no se recupera, ruta protegida → login → vuelta a la ruta |
| `test_e2e_3_compra.py` | **Compra completa**: registro → elegir 2 entradas → checkout → tarjeta rechazada → pedido pendiente → reintento con tarjeta válida → entradas emitidas → aparecen en "Mis entradas"; validación de la tarjeta; máximo por pedido; reservar sin sesión pide login |
| `test_e2e_4_roles_y_validacion.py` | Un CLIENT no entra en Gestión ni escribiendo la URL, el MANAGER ve el panel sin la gestión de usuarios, el ADMIN gestiona usuarios, **check-in de una entrada en la puerta** (y no puede entrar dos veces), un CLIENT solo consulta entradas |
| `test_e2e_5_seguridad_navegador.py` | Los tokens no son accesibles desde JavaScript (ni en `document.cookie` ni en `localStorage`), atributos de la cookie del refresh, un nombre con HTML no ejecuta código (XSS), la CSP bloquea scripts en línea |

## 3. Pruebas de carga y estrés

`estres/locustfile.py` simula dos tipos de usuario, con 5–15 s de espera entre
acciones (~10 s de media, el mismo supuesto que el estudio de costes):

- **Visitante (70 %)**: portada, filtros, búsqueda, detalle de eventos y categorías.
- **Comprador (30 %)**: se registra, navega, reserva y paga entradas (10 %
  cancela), consulta sus pedidos, refresca el token e inicia sesión de nuevo
  (Argon2id: la operación más costosa).

| Perfil (`PERFIL`) | Tipo de prueba | Usuarios | Duración |
| --- | --- | --- | --- |
| `carga` | Carga | Rampa de 2 min hasta **420** y 5 min estable | 7 min |
| `pico` | Pico | **420** usuarios en ~10 s (apertura de una venta) | ~3 min |
| `estres` | Estrés | +100 usuarios cada minuto hasta 1200 | 12 min |
| `produccion` | Carga en producción (Render) | 10 → 25 → 50 usuarios | 3 min |

Las pruebas se reparten entre los dos despliegues:

| Despliegue | Pruebas | Por qué |
| --- | --- | --- |
| Local (Docker, `localhost`) | `carga`, `pico`, `estres` y simulación DDoS | Se puede llevar al límite sin afectar a nadie y medir el consumo con `docker stats` |
| Producción (Render) | `produccion` y pruebas funcionales | Comprueba el despliegue real con una carga moderada; el plan gratuito (0,1 CPU, 512 MB) no está pensado para 420 usuarios, como concluye el estudio de costes |

### Criterios de aceptación (420 usuarios)

| Métrica | Objetivo |
| --- | --- |
| Errores | < 1 % de las peticiones |
| Percentil 95 del catálogo (`/api/events`) | < 500 ms |
| Percentil 95 de login / registro | < 2 s |
| Percentil 95 de reservar y pagar | < 1 s |
| Sobreventa | 0 entradas vendidas de más |

## 4. Protección frente a DoS / DDoS

Medidas configuradas en Nginx (`frontend/nginx/default.conf.template`):

| Ataque | Medida | Valor |
| --- | --- | --- |
| Inundación de la API desde una IP | `limit_req` zona `api` | 20 peticiones/s por IP, ráfaga de 40 (`API_RATE_LIMIT`) |
| Fuerza bruta contra el login | `limit_req` zona `auth` | 10 por minuto por IP, ráfaga de 10 (`AUTH_RATE_LIMIT`) |
| Muchas conexiones desde una IP | `limit_conn` | 50 conexiones/peticiones simultáneas por IP |
| Slowloris (peticiones enviadas muy despacio) | `client_header_timeout`, `client_body_timeout`, `send_timeout`, `reset_timedout_connection` | 10 s |
| Conexiones ociosas | `keepalive_timeout` | 15 s |
| Cuerpos o cabeceras enormes | `client_max_body_size`, buffers de cabeceras | 1 MB / 8 KB |

Además, la API ya limitaba el trabajo por petición (paginación con máximo de
50 elementos, validación de tamaños con Pydantic).

Se comprueban de dos formas:

- **`funcionales/test_7_ddos.py`** (con las pruebas de la API): verifica cada
  medida y que el servicio sigue disponible después.
- **`estres/ddos_locustfile.py`**: 300 bots atacan la API a través de Nginx
  durante 2 minutos mientras un monitor consulta el backend directamente.
  Al terminar muestra el porcentaje de peticiones bloqueadas y el tiempo de
  respuesta del backend durante el ataque.

Limitación: un DDoS *distribuido* real (miles de IP) o volumétrico (saturar la
red) no se puede frenar solo con Nginx en el propio servidor; en producción se
pone delante una CDN o servicio anti-DDoS (Cloudflare, AWS Shield, Azure DDoS
Protection, Google Cloud Armor). Render ya incluye protección DDoS de su red,
por lo que **la simulación de ataque solo se lanza contra el despliegue local**:
atacar la infraestructura de un tercero no es aceptable (la simulación se niega
a ejecutarse si el destino no es `localhost`).

## 5. Cómo ejecutarlas (Windows, PowerShell)

### 5.1 Preparar Python (una sola vez)

```powershell
cd $env:USERPROFILE\entradas-app\pruebas
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 5.2 Levantar la aplicación con la API accesible para las pruebas

Desde la raíz del repositorio:

```powershell
cd $env:USERPROFILE\entradas-app
docker compose -f docker-compose.yml -f docker-compose.pruebas.yml up -d --build
```

Esto publica la API en `http://127.0.0.1:3000` (solo en el propio equipo) y
sube el límite de logins de Nginx de 10 a 120 por minuto, porque las pruebas
inician sesión muchas veces seguidas desde la misma IP. La ráfaga máxima no
cambia, así que la prueba de fuerza bruta sigue recibiendo 429.

### 5.3 Pruebas funcionales con la aplicación

```powershell
cd $env:USERPROFILE\entradas-app\pruebas
.venv\Scripts\python.exe ejecutar_pruebas.py
```

Se abre una ventana donde eliges:

- **Pruebas de la API**, **Pruebas en el navegador (Selenium)** o **Todas**.
- El navegador (Firefox, Chrome o Edge). La primera vez Selenium descarga solo
  el driver del navegador.
- *Modo lento*, para ver los pasos a ritmo humano (útil para enseñarlo), o
  *headless*, para que no se abra la ventana del navegador.
- En la fila **Estrés (Locust)**: carga, pico y estrés locales, la
  **simulación DDoS** y la prueba de **producción** (usa la URL de la API de
  Render del campo *API producción*).

La ventana muestra cada prueba en verde o rojo y, al terminar, el botón
**Abrir informe** abre el informe HTML (`resultados\informe-*.html`). El botón
**Capturas** abre la carpeta con las capturas de pantalla.

Sin ventana, desde la consola:

```powershell
.venv\Scripts\python.exe ejecutar_pruebas.py --sin-ventana todas   # o api, o e2e
```

O directamente con pytest:

```powershell
.venv\Scripts\python.exe -m pytest funcionales -v
.venv\Scripts\python.exe -m pytest e2e -v
```

### 5.4 Pruebas de carga y estrés

Cierra los programas pesados: Locust y Docker comparten el mismo equipo.

```powershell
cd $env:USERPROFILE\entradas-app\pruebas

# Carga: 420 usuarios simultáneos
$env:PERFIL = "carga"
.venv\Scripts\locust.exe -f estres\locustfile.py -H http://localhost:3000 --headless --html resultados\carga.html --csv resultados\carga

# Pico: llegan 420 usuarios de golpe
$env:PERFIL = "pico"
.venv\Scripts\locust.exe -f estres\locustfile.py -H http://localhost:3000 --headless --html resultados\pico.html --csv resultados\pico

# Estrés: subir hasta encontrar el límite
$env:PERFIL = "estres"
.venv\Scripts\locust.exe -f estres\locustfile.py -H http://localhost:3000 --headless --html resultados\estres.html --csv resultados\estres

# Simulación DDoS contra Nginx (solo local)
Remove-Item Env:PERFIL
.venv\Scripts\locust.exe -f estres\ddos_locustfile.py -H https://localhost --headless -u 301 -r 100 -t 2m --html resultados\ddos.html
```

O con la aplicación: `.venv\Scripts\python.exe ejecutar_pruebas.py --sin-ventana carga`
(o `pico`, `estres`, `ddos`, `produccion`).

Cada prueba genera un informe HTML con gráficas (`resultados\*.html`) y los
datos en CSV. Mientras se ejecutan puedes ver el consumo de los contenedores
con `docker stats` en otra ventana.

Para verlo en directo con gráficas, quita `--headless` y abre
<http://localhost:8089>.

### 5.5 Volver al despliegue normal

```powershell
cd $env:USERPROFILE\entradas-app
docker compose up -d
```

## 6. Contra Render (producción)

```powershell
$env:API_URL = "https://entradas-api-mohamedzy37.onrender.com"
$env:WEB_URL = "https://entradas-mohamedzy37.onrender.com"
.venv\Scripts\python.exe -m pytest -v
```

`API_URL` es la URL del servicio de la API (no la de la web), porque `/health`
solo existe en la API. En la aplicación basta con cambiar las dos URL de la
ventana. La prueba del rate limit se omite porque Render no usa
el Nginx del proyecto.

Prueba de carga en producción (perfil `produccion`, hasta 50 usuarios):

```powershell
$env:PERFIL = "produccion"
.venv\Scripts\locust.exe -f estres\locustfile.py -H https://entradas-api-mohamedzy37.onrender.com --headless --html resultados\produccion.html --csv resultados\produccion
```

Si la API estaba dormida, la primera petición tarda alrededor de un minuto.

## 7. Variables de entorno

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `API_URL` | `http://localhost:3000` | API a probar |
| `WEB_URL` | `https://localhost` | Web pública (pruebas de despliegue) |
| `VERIFY_TLS` | `false` en localhost | Verificar el certificado TLS |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | usuario de demo | Admin para crear los eventos de prueba |
| `MANAGER_EMAIL`, `MANAGER_PASSWORD`, `CLIENT_EMAIL`, `CLIENT_PASSWORD` | usuarios de demo | Resto de roles |
| `PERFIL` | (vacío) | `carga`, `pico`, `estres` o `produccion` en Locust |
| `API_RATE_LIMIT` / `AUTH_RATE_LIMIT` | `20r/s` / `10r/m` | Límites de Nginx (variables del `docker compose`) |
| `NAVEGADOR` | `firefox` | Navegador de Selenium: `firefox`, `chrome` o `edge` |
| `HEADLESS` | `0` | `1` para no mostrar el navegador |
| `LENTO` | `0` | Segundos de pausa entre acciones de Selenium |
