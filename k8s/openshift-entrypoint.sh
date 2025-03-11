#!/bin/bash
set -e

# Adiciona o usuário atual ao /etc/passwd se necessário
if ! whoami &> /dev/null; then
  if [ -w /etc/passwd ]; then
    echo "${USER_NAME:-default}:x:$(id -u):0:${USER_NAME:-default} user:${HOME}:/sbin/nologin" >> /etc/passwd
  fi
fi

# Inicia o Gunicorn
exec gunicorn -w 4 -b 0.0.0.0:8050 app:server --timeout 120 