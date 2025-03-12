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
│   ├── buildconfig.yaml   # Configuração de build
│   ├── configmap.yaml     # ConfigMap com script de inicialização
│   ├── deployment.yaml    # Configuração do Deployment
│   ├── imagestream.yaml   # Configuração do ImageStream
│   ├── pvc.yaml          # Configuração do Volume Persistente
│   ├── route.yaml        # Configuração da Rota
│   └── service.yaml      # Configuração do Serviço
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
oc apply -f k8s/imagestream.yaml
oc apply -f k8s/buildconfig.yaml
```

### Deploy da Aplicação

1. Iniciar o build:
```bash
oc start-build painel-ods --follow
```

2. Deploy dos recursos:
```bash
oc apply -f k8s/pvc.yaml
oc apply -f k8s/configmap.yaml
oc apply -f k8s/deployment.yaml
oc apply -f k8s/service.yaml
oc apply -f k8s/route.yaml
```

Ou aplicar todos de uma vez:
```bash
oc apply -f k8s/
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

O arquivo `k8s/imagestream.yaml` contém:
- **ImageStream**:
  - Nome: painel-ods
  - Armazena as imagens construídas pelo BuildConfig
  - Usado como referência pelo Deployment

O arquivo `k8s/deployment.yaml` contém:
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
- `k8s/deployment.yaml`: Define os recursos do OpenShift

## Manutenção

### Atualizações

1. Atualizar a aplicação:
```bash
oc start-build painel-ods --follow
```

2. Deploy dos recursos (se necessário):
```bash
oc apply -f k8s/deployment.yaml
```

### Backup

Os dados importantes estão em:
- Volume persistente `painel-ods-data` montado em `/app/db/`: Arquivos CSV e Parquet
- Logs: Disponíveis através do OpenShift

## Suporte

Para problemas ou sugestões, abra uma issue no repositório.

## Gerenciamento dos Dados (ConfigMaps)

Os arquivos de dados da aplicação (CSVs e parquets) são gerenciados através de ConfigMaps no OpenShift. Existem dois ConfigMaps principais:

1. `painel-ods-db`: Contém os arquivos CSV principais
   - objetivos.csv
   - metas.csv
   - indicadores.csv
   - filtro.csv
   - unidade_medida.csv

2. `painel-ods-resultados`: Contém os arquivos parquet da pasta resultados

### Atualizando os Dados

Para atualizar os arquivos de dados, siga os passos:

1. Primeiro, remova os ConfigMaps existentes:
```bash
oc delete configmap painel-ods-db painel-ods-resultados
```

2. Crie novamente os ConfigMaps com os novos arquivos:
```bash
# Para os arquivos CSV
oc create configmap painel-ods-db \
  --from-file=objetivos.csv=db/objetivos.csv \
  --from-file=metas.csv=db/metas.csv \
  --from-file=indicadores.csv=db/indicadores.csv \
  --from-file=filtro.csv=db/filtro.csv \
  --from-file=unidade_medida.csv=db/unidade_medida.csv

# Para os arquivos parquet
oc create configmap painel-ods-resultados --from-file=db/resultados/
```

3. Reinicie o deployment para aplicar as alterações:
```bash
oc rollout restart deployment/painel-ods
```

### Verificando os Dados

Para verificar os dados atuais nos ConfigMaps:

1. Listar os ConfigMaps:
```bash
oc get configmaps
```

2. Ver detalhes de um ConfigMap específico:
```bash
oc describe configmap painel-ods-db
oc describe configmap painel-ods-resultados
```

3. Verificar os arquivos no pod:
```bash
# Listar arquivos CSV
oc exec <nome-do-pod> -- ls -la /app/db

# Listar arquivos parquet
oc exec <nome-do-pod> -- ls -la /app/db/resultados
```

### Observações Importantes

- Os ConfigMaps têm um limite de tamanho de 1MB por arquivo. Se seus arquivos forem maiores, considere usar um Volume Persistente ou dividir os dados em arquivos menores.
- A atualização dos ConfigMaps não afeta automaticamente os pods em execução. É necessário reiniciar o deployment para que as alterações sejam aplicadas.
- Mantenha um backup dos arquivos de dados antes de fazer qualquer atualização.
- É recomendado testar as atualizações em um ambiente de desenvolvimento antes de aplicar em produção.