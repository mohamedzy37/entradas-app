#!/bin/sh
# Arranque del contenedor de la API:
#  1. Crea/actualiza el esquema (y carga datos demo si SEED_DEMO_DATA=true).
#  2. Arranca Uvicorn detras del proxy inverso (Nginx).
set -eu

python scripts/init_db.py

# --proxy-headers: toma la IP real del cliente de X-Forwarded-For (la pone
#   Nginx). Sin esto, el rate limiting veria siempre la IP del proxy.
# --forwarded-allow-ips="*": seguro porque el puerto 3000 NO se publica; solo
#   Nginx, dentro de la red de Docker, puede hablar con la API.
# --no-server-header: no anunciar "uvicorn" en las respuestas.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 3000 \
  --proxy-headers \
  --forwarded-allow-ips="*" \
  --no-server-header
