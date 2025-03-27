import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configurações do servidor
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
USE_RELOADER = os.getenv('USE_RELOADER', 'True').lower() == 'true'
PORT = int(os.getenv('PORT', 8050))
HOST = os.getenv('HOST', '0.0.0.0')

# Senha para alternar o modo de manutenção
MAINTENANCE_PASSWORD = os.getenv('MAINTENANCE_PASSWORD', 'default_password')

# Configurações de performance do Dash
DASH_CONFIG = {}

# Configurações de cache do servidor
SERVER_CONFIG = {
    'SEND_FILE_MAX_AGE_DEFAULT': 31536000,  # Cache de 1 ano para arquivos estáticos
    'PERMANENT_SESSION_LIFETIME': 1800,  # 30 minutos para sessões
    'STATIC_FOLDER': 'db/resultados',  # Pasta onde estão os arquivos parquet
    'STATIC_URL_PATH': '/db/resultados',  # URL path para acessar os arquivos
    'STATIC_FOLDER_MIME_TYPES': {
        '.parquet': 'application/octet-stream'  # Define o tipo MIME para arquivos parquet
    },
    'SECRET_KEY': os.getenv('SECRET_KEY', 'imb_ods_painel_secret_key_2024')  # Chave secreta para sessões
}

# Configuração do modo de manutenção
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'
MAINTENANCE_ALLOWED_IPS = [
    '127.0.0.1',  # localhost
    # '10.209.59.96',  # IP do servidor
    # Adicione aqui os IPs que terão acesso durante a manutenção
]