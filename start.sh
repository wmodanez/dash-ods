#!/bin/bash

# Ativa o ambiente virtual (se estiver usando)
# source /caminho/para/seu/venv/bin/activate

# Define variáveis de ambiente
export DEBUG=False
export PORT=8050
export HOST=0.0.0.0

# Inicia o uWSGI
uwsgi --ini uwsgi.ini 