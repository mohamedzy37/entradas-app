"""Autorizacion por roles: ADMIN, MANAGER y CLIENT."""

import pytest

from ayudas_api import auth, con_refresh, login

# (metodo, ruta, roles que DEBEN tener acceso)
RUTAS_PROTEGIDAS = [
    ("GET", "/api/admin/users", {"ADMIN"}),
    ("GET", "/api/admin/orders", {"ADMIN", "MANAGER"}),
    ("GET", "/api/admin/stats", {"ADMIN", "MANAGER"}),
]


@pytest.fixture
def tokens(token_admin, token_manager, token_cliente):
    return {"ADMIN": token_admin, "MANAGER": token_manager, "CLIENT": token_cliente}


@pytest.mark.parametrize("metodo, ruta, permitidos", RUTAS_PROTEGIDAS)
@pytest.mark.parametrize("rol", ["ADMIN", "MANAGER", "CLIENT"])
def test_matriz_de_permisos(api, tokens, metodo, ruta, permitidos, rol):
    respuesta = api.request(metodo, ruta, headers=auth(tokens[rol]))
    esperado = 200 if rol in permitidos else 403
    assert respuesta.status_code == esperado, f"{rol} {metodo} {ruta}: {respuesta.text}"


@pytest.mark.parametrize("metodo, ruta, _", RUTAS_PROTEGIDAS)
def test_rutas_protegidas_sin_token_devuelven_401(api, metodo, ruta, _):
    assert api.request(metodo, ruta).status_code == 401


def test_un_cliente_no_puede_crear_eventos(api, token_cliente):
    respuesta = api.post(
        "/api/admin/events",
        headers=auth(token_cliente),
        json={"title": "Hack", "type": "OTHER", "startAt": "2030-01-01T20:00:00Z", "venueId": "x"},
    )
    assert respuesta.status_code == 403


def test_un_gestor_no_puede_cambiar_roles(api, token_manager, usuario_nuevo):
    respuesta = api.patch(
        f"/api/admin/users/{usuario_nuevo['id']}/role",
        headers=auth(token_manager),
        json={"role": "ADMIN"},
    )
    assert respuesta.status_code == 403


def test_un_cliente_no_puede_ascenderse_a_si_mismo(api, usuario_nuevo):
    respuesta = api.patch(
        f"/api/admin/users/{usuario_nuevo['id']}/role",
        headers=auth(usuario_nuevo["token"]),
        json={"role": "ADMIN"},
    )
    assert respuesta.status_code == 403


def test_cambio_de_rol_revoca_los_tokens_y_se_aplica_al_volver_a_entrar(
    api, token_admin, usuario_nuevo
):
    respuesta = api.patch(
        f"/api/admin/users/{usuario_nuevo['id']}/role",
        headers=auth(token_admin),
        json={"role": "MANAGER"},
    )
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["data"]["role"] == "MANAGER"

    # Los tokens emitidos con el rol anterior dejan de valer.
    assert api.get("/api/auth/me", headers=auth(usuario_nuevo["token"])).status_code == 401
    assert (
        api.post("/api/auth/refresh", headers=con_refresh(usuario_nuevo["refresh"])).status_code
        == 401
    )

    # Con una sesion nueva ya tiene permisos de gestor.
    nuevo = login(api, usuario_nuevo["email"], usuario_nuevo["password"])
    assert nuevo.status_code == 200
    token = nuevo.json()["data"]["accessToken"]
    assert nuevo.json()["data"]["user"]["role"] == "MANAGER"
    assert api.get("/api/admin/stats", headers=auth(token)).status_code == 200
    assert api.get("/api/admin/users", headers=auth(token)).status_code == 403


def test_rol_inexistente_se_rechaza(api, token_admin, usuario_nuevo):
    respuesta = api.patch(
        f"/api/admin/users/{usuario_nuevo['id']}/role",
        headers=auth(token_admin),
        json={"role": "SUPERADMIN"},
    )
    assert respuesta.status_code == 400


def test_usuario_desactivado_no_puede_entrar(api, token_admin, usuario_nuevo):
    respuesta = api.patch(
        f"/api/admin/users/{usuario_nuevo['id']}/active",
        headers=auth(token_admin),
        json={"isActive": False},
    )
    assert respuesta.status_code == 200, respuesta.text

    assert api.get("/api/auth/me", headers=auth(usuario_nuevo["token"])).status_code in {401, 403}
    assert login(api, usuario_nuevo["email"], usuario_nuevo["password"]).status_code == 403
    assert (
        api.post("/api/auth/refresh", headers=con_refresh(usuario_nuevo["refresh"])).status_code
        == 401
    )


def test_el_admin_no_puede_desactivarse_a_si_mismo(api, token_admin):
    yo = api.get("/api/auth/me", headers=auth(token_admin)).json()["data"]["user"]
    respuesta = api.patch(
        f"/api/admin/users/{yo['id']}/active",
        headers=auth(token_admin),
        json={"isActive": False},
    )
    assert respuesta.status_code == 409
