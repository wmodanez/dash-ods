#!/bin/bash

# Inicia o Nginx em background
nginx

# Inicia o Gunicorn
exec gunicorn --bind 0.0.0.0:8050 --workers 4 --log-level debug app:server 