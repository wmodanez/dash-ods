# Painel ODS - IMB

Painel interativo para visualização de dados dos Objetivos de Desenvolvimento Sustentável (ODS) do Instituto Mauro Borges.

## Execução com Docker (Recomendado)

### Pré-requisitos
- Docker
- Docker Compose (opcional)

### Construindo e Executando com Docker

1. Construa a imagem:
```bash
docker build -t painel-ods .
```

2. Execute o container:
```bash
docker run -d -p 80:80 --name painel-ods painel-ods
```

3. Acesse a aplicação em:
```
http://localhost
```

### Gerenciamento do Container

- Para parar o container:
```bash
docker stop painel-ods
```

- Para iniciar o container:
```bash
docker start painel-ods
```

- Para ver os logs:
```bash
docker logs -f painel-ods
```

## Configuração do Ambiente de Produção com uWSGI (Instalação Manual)

### Pré-requisitos

- Python 3.x
- uWSGI
- Ambiente Linux

### Estrutura de Arquivos

O projeto deve conter os seguintes arquivos de configuração:

- `app.py`: Aplicação principal
- `uwsgi.ini`: Configurações do uWSGI
- `start.sh`: Script de inicialização

### Configuração do uWSGI

O arquivo `uwsgi.ini` contém as configurações necessárias para o servidor:

```ini
[uwsgi]
# Nome da aplicação
project = painel-ods

# Configurações do Python
plugin = python3
pythonpath = /caminho/para/seu/projeto
module = app:server

# Configurações do processo
master = true
processes = 4
threads = 2
enable-threads = true

# Socket
http = :8050

# Configurações de logging
logto = /var/log/uwsgi/%n.log
log-date = true

# Configurações de reinicialização
reload-mercy = 8
max-requests = 5000
reload-on-rss = 2048

# Configurações de buffer
buffer-size = 32768

# Configurações de timeout
harakiri = 60
socket-timeout = 60
http-timeout = 60
```

### Configuração do Diretório de Logs

Antes de iniciar a aplicação, configure o diretório de logs:

```bash
sudo mkdir -p /var/log/uwsgi
sudo chown -R $USER:$USER /var/log/uwsgi
```

### Script de Inicialização

O arquivo `start.sh` contém as configurações de ambiente e comando de inicialização:

```bash
#!/bin/bash

# Ativa o ambiente virtual (se estiver usando)
# source /caminho/para/seu/venv/bin/activate

# Define variáveis de ambiente
export DEBUG=False
export PORT=8050
export HOST=0.0.0.0

# Inicia o uWSGI
uwsgi --ini uwsgi.ini
```

### Execução

1. Dê permissão de execução ao script:
```bash
chmod +x start.sh
```

2. Execute o script:
```bash
./start.sh
```

### Monitoramento e Gerenciamento

#### Logs
Para monitorar os logs da aplicação:
```bash
tail -f /var/log/uwsgi/painel-ods.log
```

#### Gerenciamento do Processo
- Para parar o servidor:
```bash
uwsgi --stop /tmp/painel-ods.pid
```

- Para reiniciar:
```bash
uwsgi --reload /tmp/painel-ods.pid
```

### Configuração com Nginx (Recomendado)

Para usar o Nginx como proxy reverso, adicione a seguinte configuração:

```nginx
server {
    listen 80;
    server_name seu_dominio.com;

    location / {
        include uwsgi_params;
        uwsgi_pass 127.0.0.1:8050;
        uwsgi_read_timeout 60s;
        uwsgi_send_timeout 60s;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Considerações de Segurança

1. Certifique-se de que o arquivo `config.py` não expõe informações sensíveis
2. Configure corretamente as variáveis de ambiente em produção
3. Use HTTPS se a aplicação for acessível pela internet
4. Mantenha as dependências atualizadas
5. Faça backup regular dos dados

### Troubleshooting

Se encontrar problemas:

1. Verifique os logs em `/var/log/uwsgi/painel-ods.log`
2. Confirme se todas as dependências estão instaladas
3. Verifique as permissões dos diretórios
4. Certifique-se de que as portas necessárias estão liberadas
5. Verifique se o ambiente virtual (se usado) está ativado corretamente

### Contato

Para suporte ou dúvidas, entre em contato com a equipe do IMB.