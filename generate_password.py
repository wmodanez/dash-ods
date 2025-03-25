import bcrypt
import os
import secrets
from dotenv import load_dotenv

def generate_password_hash(password: str) -> str:
    """Gera um hash bcrypt para a senha fornecida"""
    if isinstance(password, str):
        password = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password, salt).decode('utf-8')

def generate_secret_key() -> str:
    """Gera uma chave secreta forte e aleatória"""
    return secrets.token_hex(32)  # 32 bytes = 64 caracteres hexadecimais

def update_env_file(password_hash: str):
    """Atualiza o arquivo .env com o novo hash da senha"""
    # Carrega as variáveis de ambiente existentes
    load_dotenv()
    env_vars = {}
    
    # Se o arquivo .env existe, lê as variáveis existentes
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
    else:
        # Se o arquivo não existe, define valores padrão
        env_vars = {
            'DEBUG': 'false',
            'USE_RELOADER': 'false',
            'PORT': '8050',
            'HOST': '0.0.0.0',
            'MAINTENANCE_MODE': 'false',
            'SECRET_KEY': generate_secret_key()  # Gera uma nova chave secreta
        }

    # Atualiza ou adiciona o hash da senha
    env_vars['MAINTENANCE_PASSWORD_HASH'] = password_hash
    
    # Se não existir SECRET_KEY, gera uma nova
    if 'SECRET_KEY' not in env_vars:
        env_vars['SECRET_KEY'] = generate_secret_key()

    # Escreve o arquivo .env atualizado
    with open('.env', 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f'{key}={value}\n')

def check_password(password: str, stored_hash: str) -> bool:
    """Verifica se a senha fornecida corresponde ao hash armazenado"""
    try:
        if isinstance(password, str):
            password = password.encode('utf-8')
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        return bcrypt.checkpw(password, stored_hash)
    except Exception as e:
        print(f"Erro ao verificar senha: {str(e)}")
        return False

def test_password(password: str):
    """Testa se a senha está funcionando corretamente"""
    # Gera um novo hash
    new_hash = generate_password_hash(password)
    print(f"Hash gerado: {new_hash}")
    
    # Testa a verificação
    is_valid = check_password(password, new_hash)
    print(f"Senha válida: {is_valid}")
    
    # Testa com senha errada
    wrong_password = "senha_errada"
    is_valid = check_password(wrong_password, new_hash)
    print(f"Senha errada válida: {is_valid}")

def main():
    # Senha atual do arquivo .env
    current_password = 'imb_maintenance_2024'
    
    # Testa a senha primeiro
    print("Testando a senha...")
    test_password(current_password)
    
    # Gera o hash da senha
    password_hash = generate_password_hash(current_password)
    
    # Atualiza o arquivo .env
    update_env_file(password_hash)
    print('\nHash da senha e chave secreta gerados e salvos no arquivo .env com sucesso!')
    
    # Verifica se a senha funciona com o hash salvo
    print("\nVerificando se a senha funciona com o hash salvo...")
    load_dotenv()
    stored_hash = os.getenv('MAINTENANCE_PASSWORD_HASH')
    if stored_hash:
        is_valid = check_password(current_password, stored_hash)
        print(f"Senha válida com hash salvo: {is_valid}")
    else:
        print("Hash não encontrado no arquivo .env")

if __name__ == '__main__':
    main() 