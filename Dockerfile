# Use uma imagem base Python oficial
FROM python:3.9-slim

# Define variáveis de ambiente para locale, timezone e build não interativo
ENV LANG=pt_BR.UTF-8 \
    LANGUAGE=pt_BR:pt:en \
    LC_ALL=pt_BR.UTF-8 \
    TZ=America/Sao_Paulo \
    DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Variáveis de ambiente da aplicação (mantidas)
ENV DEBUG=False \
    PORT=8050 \
    HOST=0.0.0.0

# Define um usuário não-root para OpenShift
ENV USER_UID=1001 \
    USER_NAME=python

# Instala as dependências do sistema, configura locale e timezone
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    tzdata \
    build-essential \
    nano \
    python3-dev \
    # Gera o locale pt_BR.UTF-8
    && echo "pt_BR.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen pt_BR.UTF-8 \
    # Limpa o cache do apt
    && rm -rf /var/lib/apt/lists/* \
    # Cria diretórios e ajusta permissões
    && mkdir -p /app/db /app/db-init \
    && chown -R ${USER_UID}:0 /app \
    && chmod -R g+w /app \
    && chmod g+w /etc/passwd

# Verifica a hora e o locale configurados
RUN echo "--- Verificando Hora e Locale --- " && \
    date && \
    echo "--- Locale Settings --- " && \
    locale && \
    echo "-------------------------------"

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

# Define usuário não-root
USER ${USER_UID}

# Comando para iniciar a aplicação
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "4", "--log-level", "debug", "app:server"]

# Expõe a porta da aplicação
EXPOSE 8050