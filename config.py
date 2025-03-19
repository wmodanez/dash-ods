# Configurações do servidor
DEBUG = False
USE_RELOADER = False
PORT = 8050
HOST = '0.0.0.0'

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
    'SECRET_KEY': 'imb_ods_painel_secret_key_2024'  # Chave secreta para sessões
}