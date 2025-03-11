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
├── Dockerfile             # Configuração do container
├── requirements.txt       # Dependências Python
├── openshift.yaml        # Configuração do OpenShift
└── openshift-entrypoint.sh # Script de inicialização
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

1. Criar novo projeto (se necessário):
```bash
oc new-project painel-ods
```

2. Criar build configuration:
```bash
oc new-build --binary --name=painel-ods --strategy=docker
```

### Deploy da Aplicação

1. Build da imagem:
```bash
oc start-build painel-ods --from-dir=. --follow
```

2. Deploy dos recursos:
```bash
oc apply -f openshift.yaml
```

3. Verificar status:
```bash
oc get pods
oc get services
oc get routes
```

### Configurações do OpenShift

O arquivo `openshift.yaml` contém as seguintes configurações:

- **Deployment**:
  - Replicas: 1 (ajustável conforme necessidade)
  - Recursos:
    - Memória: 512Mi (request) / 1Gi (limit)
    - CPU: 250m (request) / 500m (limit)
  - Health checks configurados

- **Service**:
  - Porta: 8050
  - Protocolo: TCP

- **Route**:
  - Expõe a aplicação externamente
  - Configurado para a porta 8050

### Monitoramento

1. Verificar logs:
```bash
oc logs -f dc/painel-ods
```

2. Verificar status dos pods:
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

1. Se o pod não iniciar:
```bash
oc describe pod <nome-do-pod>
oc logs <nome-do-pod>
```

2. Se a rota não estiver acessível:
```bash
oc get route painel-ods
oc describe route painel-ods
```

3. Problemas comuns:
   - Verificar se as portas estão corretas (8050)
   - Confirmar se os recursos (CPU/memória) são suficientes
   - Verificar permissões do usuário não-root (UID 1001)

### Segurança

A aplicação segue as melhores práticas de segurança do OpenShift:
- Executa como usuário não-root (UID 1001)
- Não requer privilégios especiais
- Utiliza volumes com permissões apropriadas

### Arquivos de Configuração

- `.dockerignore`: Otimiza o build da imagem
- `.openshiftignore`: Controla quais arquivos são enviados ao OpenShift
- `openshift.yaml`: Define os recursos do OpenShift
- `openshift-entrypoint.sh`: Script de inicialização

## Manutenção

### Atualizações

1. Atualizar código:
```bash
git pull origin main
```

2. Rebuild e redeploy:
```bash
oc start-build painel-ods --from-dir=. --follow
```

### Backup

Os dados importantes estão em:
- `/app/db/`: Arquivos CSV e Parquet
- Logs: Disponíveis através do OpenShift

## Suporte

Para problemas ou sugestões, abra uma issue no repositório.