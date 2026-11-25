"""Disponibilidad de la API y del catalogo publico."""


def test_health_responde_y_la_bd_esta_disponible(api):
    respuesta = api.get("/health")
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["database"] == "ok"


def test_respuestas_de_la_api_llevan_csp_restrictiva(api):
    respuesta = api.get("/api/events")
    csp = respuesta.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_documentacion_interactiva_desactivada_en_produccion(api):
    # En produccion (ENVIRONMENT=production) /docs y /openapi.json no se publican.
    assert api.get("/docs").status_code == 404
    assert api.get("/openapi.json").status_code == 404


def test_listado_de_eventos_paginado(api):
    respuesta = api.get("/api/events", params={"page": 1, "limit": 5})
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["data"]) <= 5
    paginacion = cuerpo["pagination"]
    assert paginacion["page"] == 1
    assert paginacion["limit"] == 5
    assert paginacion["total"] >= len(cuerpo["data"])


def test_listado_solo_muestra_eventos_visibles(api):
    respuesta = api.get("/api/events", params={"limit": 50})
    assert respuesta.status_code == 200
    for evento in respuesta.json()["data"]:
        assert evento["status"] in {"PUBLISHED", "SOLD_OUT"}


def test_detalle_de_evento_por_slug_incluye_tipos_de_entrada(api):
    eventos = api.get("/api/events", params={"limit": 1}).json()["data"]
    assert eventos, "No hay eventos en el catalogo (¿se cargaron los datos de demo?)"
    respuesta = api.get(f"/api/events/{eventos[0]['slug']}")
    assert respuesta.status_code == 200
    detalle = respuesta.json()["data"]
    assert detalle["id"] == eventos[0]["id"]
    assert isinstance(detalle["ticketTypes"], list)


def test_evento_inexistente_devuelve_404(api):
    respuesta = api.get("/api/events/no-existe-este-evento")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "NOT_FOUND"


def test_categorias_y_recintos(api):
    assert api.get("/api/categories").status_code == 200
    assert api.get("/api/venues").status_code == 200


def test_parametros_invalidos_devuelven_400_y_no_500(api):
    respuesta = api.get("/api/events", params={"limit": 1000})
    assert respuesta.status_code == 400
    assert respuesta.json()["error"]["code"] == "VALIDATION_ERROR"


def test_busqueda_con_inyeccion_sql_no_rompe_la_api(api):
    # SQLAlchemy usa consultas parametrizadas: el texto se trata como dato.
    for q in ["' OR '1'='1", "'; DROP TABLE users; --", "%' UNION SELECT * FROM users --"]:
        respuesta = api.get("/api/events", params={"q": q})
        assert respuesta.status_code == 200
        assert respuesta.json()["data"] == []
