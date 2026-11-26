"""Aplicacion para lanzar las pruebas funcionales de EntradasYa.

Uso:
    python ejecutar_pruebas.py                     -> abre la ventana
    python ejecutar_pruebas.py --sin-ventana e2e   (api, e2e, todas, carga,
                                                    pico, estres, ddos, produccion)

Pruebas funcionales (pytest):
    api   Pruebas de la API REST y del despliegue, incluidas las anti-DDoS.
    e2e   Pruebas de extremo a extremo en el navegador (Selenium).

Pruebas de estres (Locust):
    carga       420 usuarios simultaneos (despliegue local).
    pico        420 usuarios de golpe (despliegue local).
    estres      Escalones hasta 1200 usuarios (despliegue local).
    ddos        Simulacion de ataque contra Nginx (despliegue local).
    produccion  Carga moderada contra Render (produccion).

Cada ejecucion genera un informe HTML en resultados/ y, en las pruebas con
Selenium, capturas de pantalla en resultados/capturas/.
"""

from __future__ import annotations

import argparse
import os
import queue
import re
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
RESULTADOS = CARPETA / "resultados"

SUITES = {
    "api": ("Pruebas de la API", "funcionales"),
    "e2e": ("Pruebas en el navegador (Selenium)", "e2e"),
}
NAVEGADORES = ["firefox", "chrome", "edge"]
RESULTADO_PRUEBA = re.compile(r"::\S+ (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b")
RENDER_API = "https://entradas-api-mohamedzy37.onrender.com"
MAX_LINEAS = 3000

# perfil: (descripcion, locustfile, url destino, argumentos extra)
ESTRES = {
    "carga": ("Carga: 420 usuarios (local)", "estres/locustfile.py", "API_URL", []),
    "pico": ("Pico: 420 usuarios de golpe (local)", "estres/locustfile.py", "API_URL", []),
    "estres": ("Estrés hasta 1200 usuarios (local)", "estres/locustfile.py", "API_URL", []),
    "ddos": ("Simulación DDoS contra Nginx (local)", "estres/ddos_locustfile.py", "WEB_URL",
             ["-u", "301", "-r", "100", "-t", "2m"]),
    "produccion": ("Producción: hasta 50 usuarios (Render)", "estres/locustfile.py", "RENDER_URL", []),
}


def comando_pytest(suite: str) -> tuple[list[str], Path]:
    RESULTADOS.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    informe = RESULTADOS / f"informe-{suite}-{marca}.html"
    carpetas = [SUITES[s][1] for s in (SUITES if suite == "todas" else [suite])]
    comando = [
        sys.executable, "-m", "pytest", *carpetas,
        "-v", "-p", "no:cacheprovider",
        f"--html={informe}", "--self-contained-html",
    ]
    return comando, informe


def comando_locust(perfil: str, config: dict[str, str]) -> tuple[list[str], Path]:
    RESULTADOS.mkdir(exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = RESULTADOS / f"{perfil}-{marca}"
    _, fichero, destino, extra = ESTRES[perfil]
    host = config.get(destino) or {
        "API_URL": "http://127.0.0.1:3000",
        "WEB_URL": "https://localhost",
        "RENDER_URL": RENDER_API,
    }[destino]
    comando = [
        sys.executable, "-m", "locust", "-f", fichero, "-H", host,
        "--headless", "--only-summary", "--html", f"{base}.html", "--csv", str(base), *extra,
    ]
    return comando, Path(f"{base}.html")


def comando_para(tipo: str, config: dict[str, str]) -> tuple[list[str], Path]:
    if tipo in ESTRES:
        return comando_locust(tipo, config)
    return comando_pytest(tipo)


def entorno(config: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update({k: v for k, v in config.items() if v != ""})
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    # Certificado autofirmado de localhost: sin un aviso por cada peticion.
    env["PYTHONWARNINGS"] = "ignore:Unverified HTTPS request"
    return env


# --- Modo consola --------------------------------------------------------------


def ejecutar_sin_ventana(tipo: str) -> int:
    config = {"PERFIL": tipo if tipo in ESTRES and tipo != "ddos" else ""}
    comando, informe = comando_para(tipo, config)
    print("Ejecutando:", " ".join(comando))
    codigo = subprocess.call(comando, cwd=CARPETA, env=entorno(config))
    print(f"\nInforme: {informe}")
    return codigo


# --- Ventana ---------------------------------------------------------------------


def abrir_ventana() -> None:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText

    raiz = tk.Tk()
    raiz.title("EntradasYa · Pruebas funcionales")
    raiz.geometry("1280x760")
    raiz.minsize(1000, 550)

    estado = {"proceso": None, "informe": None, "ok": 0, "fallos": 0}
    lineas: queue.Queue[str | None] = queue.Queue()

    # Configuracion -------------------------------------------------------------
    marco = ttk.LabelFrame(raiz, text="Configuración", padding=10)
    marco.pack(fill="x", padx=10, pady=(10, 5))

    variables = {
        "WEB_URL": tk.StringVar(value=os.environ.get("WEB_URL", "https://localhost")),
        "API_URL": tk.StringVar(value=os.environ.get("API_URL", "http://127.0.0.1:3000")),
        "NAVEGADOR": tk.StringVar(value=os.environ.get("NAVEGADOR", "firefox")),
        "RENDER_URL": tk.StringVar(value=os.environ.get("RENDER_URL", RENDER_API)),
    }
    headless = tk.BooleanVar(value=False)
    lento = tk.BooleanVar(value=False)

    ttk.Label(marco, text="Web (Selenium):").grid(row=0, column=0, sticky="w")
    ttk.Entry(marco, textvariable=variables["WEB_URL"], width=45).grid(row=0, column=1, sticky="we", padx=5)
    ttk.Label(marco, text="API:").grid(row=0, column=2, sticky="w", padx=(15, 0))
    ttk.Entry(marco, textvariable=variables["API_URL"], width=35).grid(row=0, column=3, sticky="we", padx=5)

    ttk.Label(marco, text="Navegador:").grid(row=1, column=0, sticky="w", pady=(8, 0))
    ttk.Combobox(
        marco, textvariable=variables["NAVEGADOR"], values=NAVEGADORES, state="readonly", width=12
    ).grid(row=1, column=1, sticky="w", padx=5, pady=(8, 0))
    opciones = ttk.Frame(marco)
    opciones.grid(row=1, column=2, columnspan=2, sticky="w", pady=(8, 0), padx=(15, 0))
    ttk.Checkbutton(opciones, text="Sin ventana del navegador (headless)", variable=headless).pack(side="left")
    ttk.Checkbutton(opciones, text="Modo lento (para verlo)", variable=lento).pack(side="left", padx=10)
    ttk.Label(marco, text="API producción:").grid(row=2, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(marco, textvariable=variables["RENDER_URL"], width=45).grid(
        row=2, column=1, sticky="we", padx=5, pady=(8, 0)
    )
    marco.columnconfigure(1, weight=1)
    marco.columnconfigure(3, weight=1)

    # Botones ---------------------------------------------------------------------
    barra = ttk.Frame(raiz, padding=(10, 5))
    barra.pack(fill="x")
    botones: list[ttk.Button] = []

    def boton(texto: str, accion) -> ttk.Button:
        b = ttk.Button(barra, text=texto, command=accion)
        b.pack(side="left", padx=(0, 8))
        botones.append(b)
        return b

    boton("▶ Pruebas de la API", lambda: lanzar("api"))
    boton("▶ Pruebas en el navegador (Selenium)", lambda: lanzar("e2e"))
    boton("▶ Todas", lambda: lanzar("todas"))

    barra_estres = ttk.Frame(raiz, padding=(10, 0, 10, 5))
    barra_estres.pack(fill="x")
    ttk.Label(barra_estres, text="Estrés (Locust):").pack(side="left", padx=(0, 8))
    for perfil, (descripcion, *_resto) in ESTRES.items():
        b = ttk.Button(barra_estres, text=descripcion, command=lambda p=perfil: lanzar(p))
        b.pack(side="left", padx=(0, 6))
        botones.append(b)
    detener = ttk.Button(barra, text="■ Detener", state="disabled", command=lambda: parar())
    detener.pack(side="left", padx=(0, 8))
    abrir_informe = ttk.Button(barra, text="Abrir informe", state="disabled", command=lambda: ver_informe())
    abrir_informe.pack(side="right")
    ttk.Button(barra, text="Capturas", command=lambda: ver_capturas()).pack(side="right", padx=8)

    resumen = ttk.Label(raiz, text="Elige qué pruebas ejecutar.", padding=(10, 0), font=("Segoe UI", 11, "bold"))
    resumen.pack(fill="x")
    progreso = ttk.Progressbar(raiz, mode="indeterminate")
    progreso.pack(fill="x", padx=10, pady=5)

    # Salida -------------------------------------------------------------------------
    salida = ScrolledText(raiz, font=("Consolas", 10), wrap="none", state="disabled")
    salida.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    salida.tag_config("ok", foreground="#15803d")
    salida.tag_config("fallo", foreground="#b91c1c", font=("Consolas", 10, "bold"))
    salida.tag_config("omitida", foreground="#a16207")
    salida.tag_config("titulo", foreground="#1d4ed8", font=("Consolas", 10, "bold"))

    def escribir(texto: str) -> None:
        etiqueta = None
        resultado = RESULTADO_PRUEBA.search(texto)
        if resultado:
            # Solo cuentan las lineas "ruta::prueba RESULTADO" de pytest -v.
            if resultado.group(1) == "PASSED":
                etiqueta = "ok"
                estado["ok"] += 1
            elif resultado.group(1) in {"FAILED", "ERROR"}:
                etiqueta = "fallo"
                estado["fallos"] += 1
            else:
                etiqueta = "omitida"
        elif texto.startswith(("FAILED ", "ERROR ", "E ")):
            etiqueta = "fallo"
        elif texto.startswith("=") or texto.startswith("_"):
            etiqueta = "titulo"
        salida.configure(state="normal")
        salida.insert("end", texto, etiqueta)
        salida.see("end")
        salida.configure(state="disabled")
        resumen.configure(text=f"En curso...  ✔ {estado['ok']} correctas   ✘ {estado['fallos']} fallidas")

    def lanzar(tipo: str) -> None:
        config = {k: v.get().strip() for k, v in variables.items()}
        config["HEADLESS"] = "1" if headless.get() else "0"
        config["LENTO"] = "0.6" if lento.get() else "0"
        config["PERFIL"] = tipo if tipo in ESTRES and tipo != "ddos" else ""
        comando, informe = comando_para(tipo, config)
        estado.update(informe=informe, ok=0, fallos=0)

        salida.configure(state="normal")
        salida.delete("1.0", "end")
        salida.configure(state="disabled")
        escribir(f"$ {' '.join(comando[2:])}\n\n")
        for b in botones:
            b.configure(state="disabled")
        detener.configure(state="normal")
        abrir_informe.configure(state="disabled")
        progreso.start(12)

        creacion = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proceso = subprocess.Popen(
            comando,
            cwd=CARPETA,
            env=entorno(config),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creacion,
        )
        estado["proceso"] = proceso

        def leer() -> None:
            assert proceso.stdout is not None
            for linea in proceso.stdout:
                lineas.put(linea)
            proceso.wait()
            lineas.put(None)

        threading.Thread(target=leer, daemon=True).start()

    def revisar_cola() -> None:
        # Como mucho 500 lineas por ciclo, para que la ventana siga respondiendo.
        try:
            for _ in range(500):
                linea = lineas.get_nowait()
                if linea is None:
                    terminar()
                    break
                escribir(linea)
        except queue.Empty:
            pass
        # Se conservan solo las ultimas lineas de la salida.
        sobrantes = int(salida.index("end-1c").split(".")[0]) - MAX_LINEAS
        if sobrantes > 0:
            salida.configure(state="normal")
            salida.delete("1.0", f"{sobrantes + 1}.0")
            salida.configure(state="disabled")
        raiz.after(100, revisar_cola)

    def terminar() -> None:
        proceso = estado["proceso"]
        codigo = proceso.returncode if proceso else -1
        progreso.stop()
        for b in botones:
            b.configure(state="normal")
        detener.configure(state="disabled")
        if estado["informe"] and Path(estado["informe"]).exists():
            abrir_informe.configure(state="normal")
        if estado["ok"] == 0 and estado["fallos"] == 0 and codigo in (0, 1):
            # Locust: no hay pruebas que contar; devuelve 1 si hubo algun error.
            texto = "✔ Prueba de estrés terminada. Abre el informe para ver tiempos y errores."
        elif codigo == 0 and estado["ok"] == 0:
            texto = "✔ Prueba terminada. Abre el informe para ver los resultados."
        elif codigo == 0:
            texto = f"✔ Todas las pruebas han pasado ({estado['ok']})."
        elif codigo == 5:
            texto = "No se ha encontrado ninguna prueba."
        else:
            texto = f"✘ {estado['fallos']} prueba(s) fallida(s), {estado['ok']} correcta(s). Revisa el informe."
        resumen.configure(text=texto)
        estado["proceso"] = None

    def parar() -> None:
        if estado["proceso"] is not None:
            estado["proceso"].terminate()

    def ver_informe() -> None:
        if estado["informe"]:
            webbrowser.open(Path(estado["informe"]).as_uri())

    def ver_capturas() -> None:
        carpeta = RESULTADOS / "capturas"
        carpeta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(carpeta)  # noqa: S606 - abre la carpeta en el Explorador
        else:
            webbrowser.open(carpeta.as_uri())

    def al_cerrar() -> None:
        parar()
        raiz.destroy()

    raiz.protocol("WM_DELETE_WINDOW", al_cerrar)
    revisar_cola()
    raiz.mainloop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--sin-ventana", choices=["api", "e2e", "todas", *ESTRES], help="ejecutar sin interfaz gráfica"
    )
    argumentos = parser.parse_args()
    if argumentos.sin_ventana:
        return ejecutar_sin_ventana(argumentos.sin_ventana)
    abrir_ventana()
    return 0


if __name__ == "__main__":
    sys.exit(main())
