import os

# Configurações do servidor com valores padrão seguros para produção
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
USE_RELOADER = os.environ.get('USE_RELOADER', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 8050))
HOST = os.environ.get('HOST', '0.0.0.0')

# Senha para alternar o modo de manutenção (vem do secret)
MAINTENANCE_PASSWORD = os.environ.get('MAINTENANCE_PASSWORD')
MAINTENANCE_PASSWORD_HASH = os.environ.get('MAINTENANCE_PASSWORD_HASH')

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
    'SECRET_KEY': os.environ.get('SECRET_KEY')  # Vem do secret
}

# Configuração do modo de manutenção (vem do secret)
MAINTENANCE_MODE = os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true'
MAINTENANCE_ALLOWED_IPS = [
    '127.0.0.1',  # localhost
    # '10.209.59.96',  # IP do servidor
    # Adicione aqui os IPs que terão acesso durante a manutenção
]