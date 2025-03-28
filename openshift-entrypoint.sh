#!/bin/bash

# Cria diretórios necessários se não existirem
mkdir -p /var/lib/nginx/body \
    /var/lib/nginx/proxy \
    /var/lib/nginx/fastcgi \
    /var/lib/nginx/uwsgi \
    /var/lib/nginx/scgi \
    /var/log/nginx

# Ajusta permissões
chown -R ${USER_UID}:0 /var/lib/nginx /var/log/nginx
chmod -R g+w /var/lib/nginx /var/log/nginx

# Inicia o Nginx em background
nginx

# Inicia o Gunicorn
exec gunicorn --bind 0.0.0.0:8050 --workers 4 --log-level debug app:server 