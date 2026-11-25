"""JWT: refresco con rotacion, revocacion y rechazo de tokens manipulados."""

import base64
import hashlib
import hmac
import json
import time

from ayudas_api import REFRESH_COOKIE, auth, con_refresh, cookies_set, login, refresh_de


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode()


def _b64_json(obj: dict) -> str:
    return _b64(json.dumps(obj, separators=(",", ":")).encode())


def _payload(token: str) -> dict:
    parte = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4)))


def _firmar(payload: dict, clave: bytes) -> str:
    cabecera = _b64_json({"alg": "HS256", "typ": "JWT"})
    cuerpo = _b64_json(payload)
    firma = hmac.new(clave, f"{cabecera}.{cuerpo}".encode(), hashlib.sha256).digest()
    return f"{cabecera}.{cuerpo}.{_b64(firma)}"


# --- Access token ---------------------------------------------------------


def test_el_access_token_contiene_los_claims_esperados(usuario_nuevo):
    claims = _payload(usuario_nuevo["token"])
    assert claims["type"] == "access"
    assert claims["sub"] == usuario_nuevo["id"]
    assert claims["role"] == "CLIENT"
    assert claims["exp"] - claims["iat"] == 15 * 60
    for claim in ("ver", "jti", "iss", "aud"):
        assert claim in claims


def test_token_con_payload_modificado_se_rechaza(api, usuario_nuevo):
    # Se cambia el rol a ADMIN sin volver a firmar: la firma deja de cuadrar.
    cabecera, _, firma = usuario_nuevo["token"].split(".")
    claims = _payload(usuario_nuevo["token"])
    claims["role"] = "ADMIN"
    falsificado = f"{cabecera}.{_b64_json(claims)}.{firma}"
    assert api.get("/api/auth/me", headers=auth(falsificado)).status_code == 401
    assert api.get("/api/admin/users", headers=auth(falsificado)).status_code == 401


def test_token_firmado_con_otra_clave_se_rechaza(api, usuario_nuevo):
    claims = _payload(usuario_nuevo["token"])
    falsificado = _firmar(claims, b"clave-que-no-es-la-del-servidor")
    assert api.get("/api/auth/me", headers=auth(falsificado)).status_code == 401


def test_token_sin_firma_alg_none_se_rechaza(api, usuario_nuevo):
    claims = _payload(usuario_nuevo["token"])
    sin_firma = f"{_b64_json({'alg': 'none', 'typ': 'JWT'})}.{_b64_json(claims)}."
    assert api.get("/api/auth/me", headers=auth(sin_firma)).status_code == 401


def test_token_caducado_se_rechaza(api, usuario_nuevo):
    claims = _payload(usuario_nuevo["token"])
    ahora = int(time.time())
    claims.update(iat=ahora - 3600, exp=ahora - 1800)
    # Aunque la firma no fuese valida, el servidor debe rechazarlo igualmente.
    caducado = _firmar(claims, b"x")
    assert api.get("/api/auth/me", headers=auth(caducado)).status_code == 401


def test_texto_basura_como_token_devuelve_401(api):
    for basura in ["abc", "a.b.c", "Bearer", "' OR 1=1 --"]:
        assert api.get("/api/auth/me", headers=auth(basura)).status_code == 401


def test_el_refresh_no_sirve_como_access_token(api, usuario_nuevo):
    respuesta = api.get("/api/auth/me", headers=auth(usuario_nuevo["refresh"]))
    assert respuesta.status_code == 401


# --- Refresh ----------------------------------------------------------------


def test_refresh_emite_un_access_nuevo_y_rota_la_cookie(api, usuario_nuevo):
    respuesta = api.post("/api/auth/refresh", headers=con_refresh(usuario_nuevo["refresh"]))
    assert respuesta.status_code == 200, respuesta.text
    datos = respuesta.json()["data"]
    assert datos["accessToken"] != usuario_nuevo["token"]
    assert "refreshToken" not in datos

    nuevo_refresh = refresh_de(respuesta)
    assert nuevo_refresh != usuario_nuevo["refresh"], "El refresh debe rotar"

    # El access nuevo funciona.
    assert api.get("/api/auth/me", headers=auth(datos["accessToken"])).status_code == 200


def test_la_rotacion_conserva_la_caducidad_absoluta_de_la_sesion(api, usuario_nuevo):
    respuesta = api.post("/api/auth/refresh", headers=con_refresh(usuario_nuevo["refresh"]))
    assert respuesta.status_code == 200
    original = _payload(usuario_nuevo["refresh"])
    rotado = _payload(refresh_de(respuesta))
    # La sesion no se alarga indefinidamente: auth_time y exp se mantienen.
    assert rotado["auth_time"] == original["auth_time"]
    assert rotado["exp"] == original["exp"]


def test_refresh_sin_cookie_devuelve_401_y_borra_la_cookie(api):
    respuesta = api.post("/api/auth/refresh")
    assert respuesta.status_code == 401
    cookie = cookies_set(respuesta).get(REFRESH_COOKIE)
    assert cookie is not None and cookie.get("max-age") == "0"


def test_refresh_con_cookie_falsa_devuelve_401(api):
    respuesta = api.post("/api/auth/refresh", headers=con_refresh("no.es.un-token"))
    assert respuesta.status_code == 401


def test_el_access_no_sirve_como_refresh(api, usuario_nuevo):
    respuesta = api.post("/api/auth/refresh", headers=con_refresh(usuario_nuevo["token"]))
    assert respuesta.status_code == 401


def test_refresh_desde_otro_origen_se_rechaza(api, usuario_nuevo):
    # Defensa anti-CSRF: solo se acepta el Origin del frontend.
    respuesta = api.post(
        "/api/auth/refresh",
        headers=con_refresh(usuario_nuevo["refresh"], origin="https://atacante.example"),
    )
    assert respuesta.status_code == 403


# --- Cierre de sesion ------------------------------------------------------


def test_logout_borra_la_cookie(api, usuario_nuevo):
    respuesta = api.post("/api/auth/logout", headers=con_refresh(usuario_nuevo["refresh"]))
    assert respuesta.status_code == 204
    assert cookies_set(respuesta)[REFRESH_COOKIE].get("max-age") == "0"


def test_logout_all_revoca_todos_los_tokens_del_usuario(api, usuario_nuevo):
    # Segunda sesion del mismo usuario ("otro dispositivo").
    otro = login(api, usuario_nuevo["email"], usuario_nuevo["password"])
    assert otro.status_code == 200
    token_otro = otro.json()["data"]["accessToken"]
    refresh_otro = refresh_de(otro)

    respuesta = api.post("/api/auth/logout-all", headers=auth(usuario_nuevo["token"]))
    assert respuesta.status_code == 204

    # Ningun token anterior sirve ya, en ningun dispositivo.
    assert api.get("/api/auth/me", headers=auth(usuario_nuevo["token"])).status_code == 401
    assert api.get("/api/auth/me", headers=auth(token_otro)).status_code == 401
    assert api.post("/api/auth/refresh", headers=con_refresh(usuario_nuevo["refresh"])).status_code == 401
    assert api.post("/api/auth/refresh", headers=con_refresh(refresh_otro)).status_code == 401

    # Puede volver a iniciar sesion con normalidad.
    assert login(api, usuario_nuevo["email"], usuario_nuevo["password"]).status_code == 200
