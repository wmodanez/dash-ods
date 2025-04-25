# Use uma imagem base Python oficial
FROM python:3.9-slim

# Define timezone e frontend não interativo primeiro
ENV TZ=America/Sao_Paulo \
    DEBIAN_FRONTEND=noninteractive \
    # Mantém env vars do Python
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Instala tzdata, locales, GERA O LOCALE, e depois as dependências de build
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    locales \
    # Gera o locale pt_BR.UTF-8 ANTES de instalar outros pacotes
    && echo "pt_BR.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen pt_BR.UTF-8 \
    # Instala outras dependências de build
    && apt-get install -y --no-install-recommends \
       build-essential \
       nano \
       python3-dev \
    # Limpa o cache do apt
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # Cria diretórios e ajusta permissões (usando UID diretamente)
    && mkdir -p /app/db /app/db-init \
    && chown -R 1001:0 /app \
    && chmod -R g+w /app \
    && chmod g+w /etc/passwd

# Define as variáveis de ambiente do LOCALE *APÓS* a geração
ENV LANG=pt_BR.UTF-8 \
    LANGUAGE=pt_BR:pt:en \
    LC_ALL=pt_BR.UTF-8

# Variáveis de ambiente da aplicação
ENV DEBUG=False \
    PORT=8050 \
    HOST=0.0.0.0

# Define um usuário não-root para OpenShift
ENV USER_UID=1001 \
    USER_NAME=python

# Verifica a hora e o locale configurados (Mantido para verificação)
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