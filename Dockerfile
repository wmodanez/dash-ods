# Use uma imagem base Python oficial
FROM python:3.9-slim

# Define variáveis de ambiente
ENV DEBUG=False \
    PORT=8050 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Instala as dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório da aplicação
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install uwsgi

# Copia o resto dos arquivos da aplicação
COPY . .

# Cria diretório para logs do uWSGI
RUN mkdir -p /var/log/uwsgi \
    && chown -R www-data:www-data /var/log/uwsgi

# Configura o Nginx
COPY nginx.conf /etc/nginx/sites-available/default
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Configura o Supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Dá permissão de execução ao script de inicialização
RUN chmod +x start.sh

# Expõe a porta 80 para o Nginx
EXPOSE 80

# Comando para iniciar o Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]