# syntax=docker/dockerfile:1
# Imagen de produccion de la API (FastAPI + Uvicorn).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Usuario sin privilegios: la API nunca se ejecuta como root.
RUN groupadd --system app \
 && useradd --system --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app

# Dependencias primero para aprovechar la cache de capas.
COPY requirements.txt .
RUN pip install -r requirements.txt

# El codigo pertenece a root y es de solo lectura para el usuario "app":
# si alguien compromete el proceso, no puede modificar la aplicacion.
COPY app ./app
COPY scripts ./scripts
COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Por si el fichero llega con finales de linea de Windows (CRLF).
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh

USER app
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:3000/health', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["docker-entrypoint.sh"]
