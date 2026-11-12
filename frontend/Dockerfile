# syntax=docker/dockerfile:1
# --- Etapa 1: compilar la SPA ---
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# --- Etapa 2: servir con Nginx SIN privilegios ---
# nginx-unprivileged corre como el usuario 101 y escucha en 8080/8443.
FROM nginxinc/nginx-unprivileged:stable-alpine

USER root
# openssl solo para generar un certificado autofirmado si no se aporta uno.
RUN apk add --no-cache openssl \
 && mkdir -p /etc/nginx/certs \
 && chown 101:101 /etc/nginx/certs \
 && rm -f /etc/nginx/conf.d/default.conf

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/security-headers.conf nginx/proxy.conf /etc/nginx/snippets/
COPY --chmod=755 nginx/05-tls-autofirmado.sh /docker-entrypoint.d/05-tls-autofirmado.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/05-tls-autofirmado.sh

# Solo los ficheros compilados: ni codigo fuente ni node_modules.
COPY --from=build /src/dist /usr/share/nginx/html

# Valores por defecto (los sobrescribe docker-compose).
ENV HTTPS_PORT=443 \
    TLS_CN=localhost

USER 101
EXPOSE 8080 8443
