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

# Cria diretórios necessários
RUN mkdir -p /var/log/nginx /var/log/supervisor \
    && chown -R www-data:www-data /var/log/nginx \
    && chown -R www-data:www-data /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Atualiza o pip e instala as dependências
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install gunicorn

# Copia os arquivos de configuração
COPY supervisord.conf /etc/supervisor/conf.d/
COPY nginx.conf /etc/nginx/sites-available/default

# Configura o Nginx
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default \
    && rm -f /etc/nginx/sites-enabled/default

# Copia o resto dos arquivos da aplicação
COPY . .

# Ajusta as permissões
RUN chown -R www-data:www-data /app \
    && chmod -R 755 /app

# Expõe as portas
EXPOSE 80 8050

# Comando para iniciar o Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]