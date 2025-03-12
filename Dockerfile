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
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/db_files/resultados \
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

# Copia os arquivos CSV e parquet para um diretório temporário
COPY --chown=${USER_UID}:0 db/*.csv /app/db_files/
COPY --chown=${USER_UID}:0 db/resultados/*.parquet /app/db_files/resultados/

# Cria um script de inicialização para copiar os arquivos para o volume persistente
RUN echo '#!/bin/bash\n\
echo "Verificando arquivos no volume persistente..."\n\
if [ ! -f /app/db/objetivos.csv ]; then\n\
    echo "Copiando arquivos CSV para o volume persistente..."\n\
    mkdir -p /app/db/resultados\n\
    cp -v /app/db_files/*.csv /app/db/\n\
    cp -v /app/db_files/resultados/*.parquet /app/db/resultados/\n\
    echo "Arquivos copiados com sucesso."\n\
else\n\
    echo "Arquivos já existem no volume persistente."\n\
fi\n\
\n\
# Inicia a aplicação\n\
exec gunicorn --bind 0.0.0.0:8050 --workers 4 --log-level debug app:server\n\
' > /app/start.sh && chmod +x /app/start.sh

# Copia o resto dos arquivos da aplicação
COPY --chown=${USER_UID}:0 . .

# Define usuário não-root
USER ${USER_UID}

# Comando para iniciar a aplicação
CMD ["/app/start.sh"]

# Expõe a porta da aplicação
EXPOSE 8050