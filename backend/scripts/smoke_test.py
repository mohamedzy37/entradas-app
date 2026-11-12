"""Prueba de humo de la API FastAPI.

Uso:
    .venv\\Scripts\\python.exe scripts\\smoke_test.py

Requiere la API escuchando en http://localhost:3000 y los datos sembrados.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid

BASE = "http://localhost:3000"
COOKIE_NAME = "refresh_token"

ok = 0
fail = 0
failures: list[str] = []


def check(name: str, condition: bool, extra: str = "") -> None:
    global ok, fail
    if condition:
        ok += 1
        print(f"OK   {name}")
    else:
        fail += 1
        failures.append(name)
        print(f"FAIL {name} {extra}")


def request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    refresh: str | None = None,
    origin: str | None = None,
):
    headers: dict[str, str] = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if refresh:
        headers["Cookie"] = f"{COOKIE_NAME}={refresh}"
    if origin:
        headers["Origin"] = origin
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else None
            return response.status, payload, response.headers
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            payload = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            payload = raw
        return error.code, payload, error.headers
    except urllib.error.URLError as error:
        raise SystemExit(f"No se pudo conectar con la API: {error}") from error


def refresh_cookie(headers) -> dict[str, str] | None:
    """Devuelve los atributos de la cookie del refresh (o None si no hay)."""
    for raw in headers.get_all("Set-Cookie") or []:
        parts = [p.strip() for p in raw.split(";")]
        name, _, value = parts[0].partition("=")
        if name != COOKIE_NAME:
            continue
        attrs = {"value": value.strip('"')}
        for part in parts[1:]:
            key, _, val = part.partition("=")
            attrs[key.lower()] = val or "true"
        return attrs
    return None


def login(email: str, password: str):
    return request("POST", "/api/auth/login", {"email": email, "password": password})


print("== Salud y catalogo ==")
status, body, _ = request("GET", "/health")
check("health 200", status == 200 and body.get("status") == "ok", str(body))

status, body, _ = request("GET", "/api/categories")
check("categorias", status == 200 and len(body["data"]) == 8, str(status))

status, body, _ = request("GET", "/api/venues?limit=100")
check("recintos", status == 200 and body["pagination"]["total"] >= 29, str(status))

status, body, _ = request("GET", "/api/events?limit=50")
check("eventos", status == 200 and body["pagination"]["total"] > 0, str(status))
first_event = body["data"][0]
status, body, _ = request("GET", f"/api/events/{first_event['slug']}")
check(
    "detalle evento con tipos de entrada",
    status == 200 and len(body["data"]["ticketTypes"]) > 0,
    str(status),
)

status, _, _ = request("GET", "/api/auth/me")
check("me sin token -> 401", status == 401, str(status))

print("\n== Login de los 3 roles ==")
status, admin_login, headers = login("admin@entradas.com", "Admin1234")
check("login admin", status == 200 and "accessToken" in admin_login["data"], str(status))
cookie = refresh_cookie(headers)
check(
    "refresh en cookie HttpOnly + SameSite=Strict + Path=/api/auth",
    cookie is not None
    and "httponly" in cookie
    and cookie.get("samesite", "").lower() == "strict"
    and cookie.get("path") == "/api/auth",
    str(headers.get_all("Set-Cookie")),
)
check(
    "el refresh NO va en el cuerpo de la respuesta",
    "refreshToken" not in admin_login["data"],
    str(admin_login["data"].keys()),
)
admin_access = admin_login["data"]["accessToken"]
admin_refresh = cookie["value"] if cookie else ""

status, body, _ = request("GET", "/api/auth/me", token=admin_access)
check(
    "me admin con rol",
    status == 200 and body["data"]["user"]["role"] == "ADMIN",
    str(body),
)

status, manager_login, _ = login("gestor@entradas.com", "Gestor1234")
check(
    "login manager",
    status == 200 and manager_login["data"]["user"]["role"] == "MANAGER",
    str(status),
)
manager_access = manager_login["data"]["accessToken"]

status, client_login, _ = login("ana.garcia@ejemplo.com", "demo1234")
check(
    "login client demo",
    status == 200 and client_login["data"]["user"]["role"] == "CLIENT",
    str(status),
)
client_access = client_login["data"]["accessToken"]

print("\n== Registro y validaciones ==")
email = f"smoke-{int(time.time())}-{uuid.uuid4().hex[:6]}@ejemplo.com"
password = "Prueba1234"
status, registered, headers = request(
    "POST",
    "/api/auth/register",
    {"name": "Usuario Prueba", "email": email, "password": password},
)
check("registro 201", status == 201 and registered["data"]["user"]["role"] == "CLIENT")
new_access = registered["data"]["accessToken"]
new_refresh = (refresh_cookie(headers) or {}).get("value", "")

status, _, _ = request(
    "POST",
    "/api/auth/register",
    {"name": "Usuario Prueba", "email": email, "password": password},
)
check("registro duplicado 409", status == 409, str(status))

status, _, _ = request(
    "POST",
    "/api/auth/register",
    {"name": "X", "email": "mal", "password": "corta"},
)
check("validacion 400", status == 400, str(status))

status, _, _ = request(
    "POST", "/api/auth/login", {"email": email, "password": "Incorrecta1"}
)
check("login incorrecto 401", status == 401, str(status))

print("\n== Refresco stateless del JWT ==")
status, _, _ = request("POST", "/api/auth/refresh")
check("refresh sin cookie -> 401", status == 401, str(status))

status, _, _ = request("POST", "/api/auth/refresh", refresh="no.es.un-jwt")
check("refresh manipulado -> 401", status == 401, str(status))

status, _, _ = request("POST", "/api/auth/refresh", refresh=new_access)
check("access token usado como refresh -> 401", status == 401, str(status))

status, _, _ = request("GET", "/api/auth/me", token=new_refresh)
check("refresh token usado como access -> 401", status == 401, str(status))

status, _, _ = request(
    "POST", "/api/auth/refresh", refresh=new_refresh, origin="https://atacante.example"
)
check("refresh desde origen no permitido -> 403", status == 403, str(status))

time.sleep(1.1)  # para que el iat del token nuevo sea distinto
status, rotated, headers = request("POST", "/api/auth/refresh", refresh=new_refresh)
rotated_cookie = refresh_cookie(headers) or {}
check(
    "refresh devuelve access nuevo y rota la cookie",
    status == 200
    and rotated["data"]["accessToken"] != new_access
    and rotated_cookie.get("value") not in (None, "", new_refresh),
    str(status),
)
rotated_access = rotated["data"]["accessToken"]
rotated_refresh = rotated_cookie.get("value", "")

status, _, _ = request("GET", "/api/auth/me", token=rotated_access)
check("el access refrescado funciona", status == 200, str(status))

print("\n== Compra (nuevo usuario) ==")
event = next(e for e in request("GET", "/api/events?limit=50")[1]["data"] if e["status"] == "PUBLISHED")
detail = request("GET", f"/api/events/{event['slug']}")[1]["data"]
ticket_type = detail["ticketTypes"][0]

status, created, _ = request(
    "POST",
    "/api/orders",
    {
        "buyer": {"name": "Usuario Prueba", "email": email, "phone": "+34600111222"},
        "items": [{"ticketTypeId": ticket_type["id"], "quantity": 2}],
    },
    token=new_access,
)
check("crear pedido 201", status == 201, str(status))
reference = created["data"]["reference"]
check(
    "total correcto",
    created["data"]["totalCents"] == ticket_type["priceCents"] * 2,
    str(created["data"]["totalCents"]),
)

status, body, _ = request(
    "POST",
    f"/api/orders/{reference}/pay",
    {
        "cardNumber": "4242 4242 4242 4242",
        "cardHolder": "Usuario Prueba",
        "expiryMonth": 12,
        "expiryYear": 2030,
        "cvv": "123",
    },
    token=new_access,
)
check("pago aprobado 200", status == 200 and body["approved"] is True, str(status))
codes = [t["code"] for t in body["data"]["order"]["tickets"]]
check("2 entradas emitidas", len(codes) == 2, str(codes))

status, mine, _ = request("GET", "/api/orders", token=new_access)
check(
    "mis pedidos incluye el pagado",
    status == 200 and any(o["reference"] == reference for o in mine["data"]),
    str(status),
)

print("\n== Pago rechazado ==")
status, created2, _ = request(
    "POST",
    "/api/orders",
    {
        "buyer": {"name": "Usuario Prueba", "email": email},
        "items": [{"ticketTypeId": ticket_type["id"], "quantity": 1}],
    },
    token=new_access,
)
reference2 = created2["data"]["reference"]
status, body, _ = request(
    "POST",
    f"/api/orders/{reference2}/pay",
    {
        "cardNumber": "4000 0000 0000 0002",
        "cardHolder": "Usuario Prueba",
        "expiryMonth": 12,
        "expiryYear": 2030,
        "cvv": "123",
    },
    token=new_access,
)
check(
    "pago rechazado 402",
    status == 402 and body["approved"] is False,
    str(status),
)

status, body, _ = request("POST", f"/api/orders/{reference2}/cancel", token=new_access)
check("cancelar reserva 200", status == 200 and body["data"]["status"] == "CANCELLED")

print("\n== Autorizacion por roles ==")
status, _, _ = request("GET", "/api/admin/users", token=client_access)
check("client no puede listar usuarios -> 403", status == 403, str(status))

status, _, _ = request("GET", "/api/admin/users", token=manager_access)
check("manager no puede listar usuarios -> 403", status == 403, str(status))

status, users, _ = request("GET", "/api/admin/users", token=admin_access)
check("admin lista usuarios", status == 200 and users["pagination"]["total"] >= 3)

status, _, _ = request("GET", "/api/admin/stats", token=manager_access)
check("manager ve estadisticas", status == 200)

status, _, _ = request("GET", "/api/admin/orders", token=manager_access)
check("manager lista pedidos", status == 200)

status, _, _ = request("GET", "/api/admin/stats", token=client_access)
check("client no ve estadisticas -> 403", status == 403, str(status))

print("\n== Check-in de entradas ==")
ticket_code = codes[0]
status, _, _ = request(
    "POST", f"/api/tickets/{ticket_code}/check-in", token=new_access
)
check("client no puede hacer check-in -> 403", status == 403, str(status))

status, body, _ = request(
    "POST", f"/api/tickets/{ticket_code}/check-in", token=manager_access
)
check(
    "manager hace check-in",
    status == 200 and body["data"]["status"] == "USED",
    str(status),
)

status, _, _ = request(
    "POST", f"/api/tickets/{ticket_code}/check-in", token=manager_access
)
check("segundo check-in -> 409", status == 409, str(status))

status, body, _ = request("GET", f"/api/tickets/{ticket_code}")
check("consulta publica de entrada", status == 200 and body["data"]["status"] == "USED")

print("\n== Gestion de catalogo (manager) ==")
venues = request("GET", "/api/venues?limit=100")[1]["data"]
venue = venues[0]
status, event_body, _ = request(
    "POST",
    "/api/admin/events",
    {
        "title": "Evento de prueba " + uuid.uuid4().hex[:6],
        "description": "Creado por la prueba de humo",
        "type": "OTHER",
        "status": "DRAFT",
        "startAt": "2030-01-01T20:00:00Z",
        "venueId": venue["id"],
    },
    token=manager_access,
)
check("manager crea evento 201", status == 201, str(status))
new_event = event_body["data"]
check("evento tiene slug unico", bool(new_event["slug"]), str(new_event))

status, tt_body, _ = request(
    "POST",
    f"/api/admin/events/{new_event['id']}/ticket-types",
    {
        "name": "General",
        "priceCents": 1234,
        "quantityTotal": 50,
        "maxPerOrder": 4,
    },
    token=manager_access,
)
check(
    "manager crea tipo de entrada",
    status == 201 and tt_body["data"]["minPriceCents"] == 1234,
    str(status),
)

status, _, _ = request("DELETE", f"/api/admin/events/{new_event['id']}", token=manager_access)
check("manager elimina evento sin ventas -> 204", status == 204, str(status))

status, _, _ = request("GET", "/api/admin/users", token=new_access)
check("usuario nuevo no es admin -> 403", status == 403, str(status))

print("\n== Cambio de rol por admin ==")
user_id = registered["data"]["user"]["id"]
status, changed, _ = request(
    "PATCH", f"/api/admin/users/{user_id}/role", {"role": "MANAGER"}, token=admin_access
)
check(
    "admin cambia rol a MANAGER",
    status == 200 and changed["data"]["role"] == "MANAGER",
    str(status),
)
status, _, _ = request("GET", "/api/auth/me", token=rotated_access)
check("cambio de rol invalida el access anterior -> 401", status == 401, str(status))
status, _, _ = request("POST", "/api/auth/refresh", refresh=rotated_refresh)
check("cambio de rol invalida el refresh anterior -> 401", status == 401, str(status))

status, relogin, _ = login(email, password)
status, _, _ = request("GET", "/api/admin/stats", token=relogin["data"]["accessToken"])
check("tras volver a entrar, el nuevo rol MANAGER funciona", status == 200, str(status))
request(
    "PATCH", f"/api/admin/users/{user_id}/role", {"role": "CLIENT"}, token=admin_access
)

print("\n== Logout ==")
status, _, headers = request("POST", "/api/auth/logout", refresh=admin_refresh)
cleared = refresh_cookie(headers) or {}
check(
    "logout 204 y borra la cookie",
    status == 204 and cleared.get("max-age") == "0",
    str(headers.get_all("Set-Cookie")),
)

status, _, _ = request("POST", "/api/auth/logout-all", token=admin_access)
check("logout-all 204", status == 204, str(status))
status, _, _ = request("GET", "/api/auth/me", token=admin_access)
check("logout-all invalida el access -> 401", status == 401, str(status))
status, _, _ = request("POST", "/api/auth/refresh", refresh=admin_refresh)
check("logout-all invalida el refresh -> 401", status == 401, str(status))

print("\n" + "=" * 50)
print(f"RESULTADO: {ok} OK, {fail} FAIL")
if failures:
    print("Fallos: " + ", ".join(failures))
raise SystemExit(0 if fail == 0 else 1)
