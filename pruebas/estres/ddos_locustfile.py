"""Simulacion de un ataque DoS de capa 7 contra el despliegue propio (Nginx).

    locust -f estres/ddos_locustfile.py -H https://localhost --headless -u 301 -r 100 -t 2m

* Atacante: bots que piden la API sin pausa, a traves de Nginx (-H). Las
  respuestas 429 se cuentan como "bloqueadas": es lo esperado.
* Monitor (1 usuario): consulta /health directamente en la API
  (API_URL, http://127.0.0.1:3000 con docker-compose.pruebas.yml) cada segundo,
  para medir si el backend sigue respondiendo con normalidad mientras Nginx
  frena el ataque.

Al terminar se imprime el porcentaje de peticiones bloqueadas.

SOLO contra el despliegue local: no lances esto contra Render ni contra
ninguna infraestructura que no sea tuya.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

import urllib3
from locust import HttpUser, between, constant, events, task

API_URL = os.environ.get("API_URL", "http://127.0.0.1:3000").rstrip("/")
CONTADOR = {"total": 0, "bloqueadas": 0, "atendidas": 0, "errores": 0}
# El certificado de localhost es autofirmado: no avisar en cada peticion.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
log = logging.getLogger("entradas-ddos")


@events.test_start.add_listener
def comprobar_destino(environment, **_):
    host = urlparse(environment.host or "").hostname or ""
    if host not in {"localhost", "127.0.0.1"}:
        log.error("La simulacion de DDoS solo se permite contra el despliegue local (localhost).")
        if environment.runner is not None:
            environment.runner.quit()


class Atacante(HttpUser):
    wait_time = constant(0)  # sin pausa entre peticiones

    def on_start(self):
        self.client.verify = False  # certificado autofirmado de localhost

    @task
    def inundar_api(self):
        with self.client.get("/api/events?limit=12", name="ATAQUE /api/events", catch_response=True) as r:
            CONTADOR["total"] += 1
            if r.status_code == 429:
                CONTADOR["bloqueadas"] += 1
                r.success()  # bloqueada por Nginx: comportamiento correcto
            elif r.status_code == 200:
                CONTADOR["atendidas"] += 1
            else:
                CONTADOR["errores"] += 1
                r.failure(f"Respuesta inesperada {r.status_code}")


class Monitor(HttpUser):
    fixed_count = 1
    wait_time = between(1, 1)

    @task
    def salud_del_backend(self):
        # URL absoluta: va directa a la API, sin pasar por Nginx.
        self.client.get(f"{API_URL}/health", name="MONITOR backend /health")


@events.test_stop.add_listener
def resumen(environment, **_):
    total = CONTADOR["total"] or 1
    texto = (
        f"\n=== Simulacion DDoS ===\n"
        f"Peticiones de ataque: {CONTADOR['total']}\n"
        f"  Bloqueadas por Nginx (429): {CONTADOR['bloqueadas']} ({100 * CONTADOR['bloqueadas'] / total:.1f} %)\n"
        f"  Atendidas (200):            {CONTADOR['atendidas']} ({100 * CONTADOR['atendidas'] / total:.1f} %)\n"
        f"  Otros errores:              {CONTADOR['errores']}\n"
    )
    monitor = environment.stats.get("MONITOR backend /health", "GET")
    if monitor.num_requests:
        texto += (
            f"Backend durante el ataque (/health): mediana {monitor.median_response_time:.0f} ms, "
            f"p95 {monitor.get_response_time_percentile(0.95):.0f} ms, fallos {monitor.num_failures}\n"
        )
    print(texto)
    log.info(texto)
