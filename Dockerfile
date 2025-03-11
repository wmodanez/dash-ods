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
    build-essential \
    python3-dev \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app /var/log/nginx /var/log/supervisor \
    && chown -R ${USER_UID}:0 /app /var/log/nginx /var/log/supervisor /var/lib/nginx \
    && chmod -R g+w /app /var/log/nginx /var/log/supervisor /var/lib/nginx \
    && chmod g+w /etc/passwd

# Cria diretório da aplicação
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY --chown=${USER_UID}:0 requirements.txt .

# Atualiza o pip e instala as dependências
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copia os arquivos de configuração
COPY --chown=${USER_UID}:0 supervisord.conf /etc/supervisor/conf.d/
COPY --chown=${USER_UID}:0 nginx.conf /etc/nginx/sites-available/default

# Configura o Nginx
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default \
    && rm -f /etc/nginx/sites-enabled/default

# Copia o resto dos arquivos da aplicação
COPY --chown=${USER_UID}:0 . .

# Ajusta as permissões finais
RUN chmod -R g+w /app

# Adiciona script de inicialização
COPY --chown=${USER_UID}:0 openshift-entrypoint.sh /
RUN chmod g+x /openshift-entrypoint.sh

# Define usuário não-root
USER ${USER_UID}

# Expõe a porta da aplicação
EXPOSE 8050

# Define o entrypoint
ENTRYPOINT ["/openshift-entrypoint.sh"]