# Use uma imagem base Python oficial
FROM python:3.9-slim

# Define variáveis de ambiente
ENV DEBUG=False \
    PORT=8050 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Define um usuário não-root para OpenShift
ENV USER_UID=1001 \
    USER_NAME=python

# Instala as dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential nano \
    python3-dev \
    nginx \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/db /app/db-init \
    && chown -R ${USER_UID}:0 /app \
    && chmod -R g+w /app \
    && chmod g+w /etc/passwd

# Cria diretório da aplicação
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY --chown=${USER_UID}:0 requirements.txt .

# Atualiza o pip e instala as dependências
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copia o resto dos arquivos da aplicação
COPY --chown=${USER_UID}:0 . .

# Copia os arquivos da pasta db para db-init
RUN cp -r db/* db-init/ || true

# Garante que as pastas têm as permissões corretas
RUN chown -R ${USER_UID}:0 /app/db /app/db-init && \
    chmod -R g+w /app/db /app/db-init

# Cria e configura diretórios do Nginx
RUN mkdir -p /var/lib/nginx/body \
    /var/lib/nginx/proxy \
    /var/lib/nginx/fastcgi \
    /var/lib/nginx/uwsgi \
    /var/lib/nginx/scgi \
    /var/log/nginx \
    && chown -R ${USER_UID}:0 /var/lib/nginx \
    && chown -R ${USER_UID}:0 /var/log/nginx \
    && chmod -R g+w /var/lib/nginx \
    && chmod -R g+w /var/log/nginx

# Define usuário não-root
USER ${USER_UID}

# Script de inicialização
COPY --chown=${USER_UID}:0 openshift-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/openshift-entrypoint.sh

# Comando para iniciar a aplicação
ENTRYPOINT ["/usr/local/bin/openshift-entrypoint.sh"]

# Expõe as portas da aplicação
EXPOSE 80 8050