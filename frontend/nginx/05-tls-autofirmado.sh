#!/bin/sh
# Si no se ha montado un certificado real en /etc/nginx/certs, genera uno
# autofirmado (valido 1 ano) para poder servir HTTPS desde el primer arranque.
# En un despliegue real se monta el certificado de una CA (p. ej. Let's Encrypt).
set -eu

CERT_DIR=/etc/nginx/certs
CN="${TLS_CN:-localhost}"

if [ -s "$CERT_DIR/tls.crt" ] && [ -s "$CERT_DIR/tls.key" ]; then
  echo "TLS: usando el certificado existente en $CERT_DIR"
  exit 0
fi

echo "TLS: no hay certificado; generando uno AUTOFIRMADO para '$CN'"
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout "$CERT_DIR/tls.key" \
  -out "$CERT_DIR/tls.crt" \
  -subj "/CN=$CN" \
  -addext "subjectAltName=DNS:$CN,DNS:localhost,IP:127.0.0.1" 2>/dev/null
chmod 600 "$CERT_DIR/tls.key"
