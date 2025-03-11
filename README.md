# Painel ODS

Painel de visualização de indicadores dos Objetivos de Desenvolvimento Sustentável (ODS).

## Requisitos

- Python 3.9+
- Docker (para desenvolvimento local)
- OpenShift CLI (oc) para deploy no OpenShift

## Estrutura do Projeto

```
.
├── app/                    # Código fonte da aplicação
├── db/                     # Arquivos de dados
├── k8s/                    # Arquivos de configuração do OpenShift
│   ├── openshift.yaml     # Manifesto do OpenShift
│   └── buildconfig.yaml   # Configuração de build
├── Dockerfile             # Configuração do container
├── .openshiftignore       # Arquivos a serem ignorados no build do OpenShift
└── requirements.txt       # Dependências Python
```

## Desenvolvimento Local

1. Criar ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Instalar dependências:
```bash
pip install -r requirements.txt
```

3. Executar com Docker:
```bash
docker compose up --build
```

A aplicação estará disponível em `http://localhost:8050`

## Deploy no OpenShift

### Pré-requisitos

1. OpenShift CLI (oc) instalado
2. Acesso a um cluster OpenShift
3. Login no cluster:
```bash
oc login <cluster-url>
```

### Configuração Inicial

1. Usar o projeto colocation-imb:
```bash
oc project colocation-imb
```

2. Criar recursos de build:
```bash
oc apply -f k8s/buildconfig.yaml
```

### Deploy da Aplicação

1. Iniciar o build:
```bash
oc start-build painel-ods --follow
```

2. Deploy dos recursos:
```bash
oc apply -f k8s/openshift.yaml
```

3. Verificar status:
```bash
oc get pods
oc get services
oc get routes
oc get builds
oc get imagestreams
```

### Configurações do OpenShift

O arquivo `k8s/buildconfig.yaml` contém:
- **BuildConfig**:
  - Estratégia: Docker
  - Fonte: Git (https://github.com/wmodanez/dash-ods.git, branch: openshift)
  - Recursos:
    - Memória: 512Mi (request) / 2Gi (limit)
    - CPU: 250m (request) / 1000m (limit)
  - Variáveis de ambiente configuradas
  - Output: ImageStream painel-ods:latest

O arquivo `k8s/openshift.yaml` contém:
- **Deployment**:
  - Replicas: 1 (ajustável conforme necessidade)
  - Recursos:
    - Memória: 512Mi (request) / 2Gi (limit)
    - CPU: 250m (request) / 1000m (limit)
  - Health checks configurados
  - Volume persistente montado em `/app/db`

- **PersistentVolumeClaim**:
  - Nome: painel-ods-data
  - Tamanho: 20Gi
  - Modo de acesso: ReadWriteOnce
  - Montado no Deployment em `/app/db`

- **ConfigMap**:
  - Contém o script de inicialização
  - Montado no container em `/k8s`

- **Service**:
  - Porta: 8050
  - Protocolo: TCP

- **Route**:
  - Expõe a aplicação externamente
  - Configurado para a porta 8050

### Monitoramento

1. Verificar logs do build:
```bash
oc logs -f bc/painel-ods
```

2. Verificar logs da aplicação:
```bash
oc logs -f dc/painel-ods
```

3. Verificar status dos pods:
```bash
oc get pods
oc describe pod <nome-do-pod>
```

### Escalonamento

Para ajustar o número de réplicas:
```bash
oc scale deployment painel-ods --replicas=3
```

### Troubleshooting

1. Se o build falhar:
```bash
oc logs -f bc/painel-ods
oc describe build <nome-do-build>
```

2. Se o pod não iniciar:
```bash
oc describe pod <nome-do-pod>
oc logs <nome-do-pod>
```

3. Se a rota não estiver acessível:
```bash
oc get route painel-ods
oc describe route painel-ods
```

4. Problemas comuns:
   - Verificar se as portas estão corretas (8050)
   - Confirmar se os recursos (CPU/memória) são suficientes
   - Verificar permissões do usuário não-root (UID 1001)
   - Verificar se o ConfigMap foi criado corretamente
   - Verificar se o ImageStream foi criado e está atualizado
   - Verificar se o PVC foi provisionado corretamente:
     ```bash
     oc get pvc painel-ods-data
     oc describe pvc painel-ods-data
     ```

### Segurança

A aplicação segue as melhores práticas de segurança do OpenShift:
- Executa como usuário não-root (UID 1001)
- Não requer privilégios especiais
- Utiliza volumes com permissões apropriadas

### Arquivos de Configuração

- `.dockerignore`: Otimiza o build da imagem
- `.openshiftignore`: Controla quais arquivos são enviados ao OpenShift
  - Ignora arquivos de desenvolvimento (venv, __pycache__, etc.)
  - Ignora arquivos de IDE e temporários
  - Ignora arquivos de teste e documentação
  - Ignora arquivos de configuração local
  - Ignora o diretório k8s (não necessário no build)
  - Melhora a performance do build e reduz o tamanho do contexto
- `k8s/buildconfig.yaml`: Define a configuração do build
- `k8s/openshift.yaml`: Define os recursos do OpenShift

## Manutenção

### Atualizações

1. Atualizar a aplicação:
```bash
oc start-build painel-ods --follow
```

2. Deploy dos recursos (se necessário):
```bash
oc apply -f k8s/openshift.yaml
```

### Backup

Os dados importantes estão em:
- Volume persistente `painel-ods-data` montado em `/app/db/`: Arquivos CSV e Parquet
- Logs: Disponíveis através do OpenShift

## Suporte

Para problemas ou sugestões, abra uma issue no repositório.