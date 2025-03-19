# Painel ODS - Instituto Mauro Borges

Este é um painel interativo desenvolvido com Dash para visualização dos Objetivos de Desenvolvimento Sustentável (ODS) do Instituto Mauro Borges.

## 🚀 Funcionalidades

- Visualização interativa dos ODS
- Gráficos dinâmicos e interativos
- Mapa coroplético do Brasil
- Tabelas de dados detalhadas
- Filtros por ano e variáveis
- Interface responsiva e moderna

## 🛠️ Tecnologias Utilizadas

- Python 3.8+
- Dash
- Plotly
- Pandas
- Dash Bootstrap Components
- Dash AG Grid
- GeoJSON

## 📦 Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/painel-ods.git
cd painel-ods
```

2. Crie um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute o aplicativo:
```bash
python app.py
```

## 📁 Estrutura do Projeto

```
painel-ods/
├── app.py              # Aplicativo principal
├── config.py           # Configurações
├── constants.py        # Constantes
├── requirements.txt    # Dependências
├── assets/            # Recursos estáticos
│   ├── css/
│   ├── js/
│   └── img/
└── db/                 # Banco de dados
    ├── resultados/     # Dados dos indicadores
    ├── br_geojson.json # Mapa do Brasil
    └── *.csv          # Arquivos de dados
```

## 🔄 Releases

### v1.0.0 (2024-03-21)
- **Novo**: Implementação inicial do painel
- **Novo**: Visualização dos ODS com gráficos e mapas
- **Novo**: Sistema de navegação entre objetivos e metas
- **Novo**: Tabelas de dados detalhadas

### v1.1.0 (2024-03-22)
- **Melhoria**: Adição de bordas nos containers dos gráficos
- **Melhoria**: Ajuste na altura dos containers para melhor visualização
- **Melhoria**: Reposicionamento do dropdown de ano dentro do container do mapa
- **Correção**: Ajuste no layout dos gráficos para evitar sobreposição

### v1.2.0 (2024-03-22)
- **Melhoria**: Remoção do título da barra de cores do mapa
- **Melhoria**: Ajuste no layout do mapa para melhor visualização
- **Correção**: Correção do comportamento do mapa ao alterar o ano
- **Correção**: Ajuste no hover do mapa para exibir a unidade de medida

## 📝 Notas de Desenvolvimento

- O aplicativo utiliza cache para melhorar a performance
- Os dados são carregados de arquivos CSV e Parquet
- O mapa utiliza GeoJSON para visualização dos estados
- A interface é responsiva e se adapta a diferentes tamanhos de tela

## 🤝 Contribuindo

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👥 Autores

- Instituto Mauro Borges
- Desenvolvido pela equipe de TI do IMB

## 🙏 Agradecimentos

- Todos os colaboradores que contribuíram com o projeto
- Equipe de dados do IMB
- Comunidade Dash e Plotly

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

## Scripts de Análise

### analyze_indicators.py

Este script analisa os arquivos parquet dos indicadores e gera sugestões de visualização. Suas principais funcionalidades são:

1. **Análise de Estrutura**:
   - Verifica a estrutura padrão dos arquivos parquet
   - Identifica colunas adicionais
   - Detecta colunas temporais e categóricas

2. **Geração de Sugestões**:
   - Cria sugestões de visualização baseadas na estrutura dos dados
   - Inclui configurações detalhadas para cada tipo de gráfico
   - Gera sugestões específicas para:
     - Dados temporais
     - Dados categóricos
     - Análise de distribuição
     - Análise de correlação

3. **Arquivos de Saída**:
   - `db/sugestoes_visualizacao.csv`: Contém todas as sugestões geradas
   - `db/sugestoes_visualizacao_aleatorias.csv`: Contém até 3 sugestões aleatórias por indicador

4. **Tipos de Visualizações Sugeridas**:
   - Gráficos de Barras
   - Gráficos de Linha
   - Gráficos de Área Temporal
   - Heatmaps
   - Gráficos de Pizza
   - Treemaps
   - Histogramas
   - Box Plots
   - Gráficos de Dispersão
   - Gráficos de Bolhas

Para executar o script:
```bash
python analyze_indicators.py
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

### Limpeza de Recursos

#### Removendo Pods Não Utilizados

Para manter o cluster limpo e otimizado, você pode remover pods que não estão mais em uso. Siga os passos:

1. Visualizar pods que serão removidos:
```bash
oc get pods -n colocation-imb | grep -E 'Completed|Failed|Error|CrashLoopBackOff'
```

2. Remover todos os pods não utilizados:
```bash
oc get pods -n colocation-imb | grep -E 'Completed|Failed|Error|CrashLoopBackOff' | awk '{print $1}' | xargs oc delete pod -n colocation-imb
```

Este comando remove automaticamente pods nos seguintes estados:
- Completed (Concluídos)
- Failed (Falhos)
- Error (Erro)
- CrashLoopBackOff (Reiniciando repetidamente)

### Backup

Os dados importantes estão em:
- Volume persistente `painel-ods-data` montado em `/app/db/`: Arquivos CSV e Parquet
- Logs: Disponíveis através do OpenShift

## Suporte

Para problemas ou sugestões, abra uma issue no repositório.

## Gerenciamento dos Dados (ConfigMaps)

Os arquivos de dados da aplicação (CSVs, parquets e JSON) são gerenciados através de ConfigMaps no OpenShift. Existem dois ConfigMaps principais:

1. `painel-ods-db`: Contém os arquivos CSV principais e JSON
   - objetivos.csv
   - metas.csv
   - indicadores.csv
   - filtro.csv
   - unidade_medida.csv
   - sugestoes_visualizacao.json

2. `painel-ods-resultados`: Contém os arquivos parquet da pasta resultados

### Atualizando os Dados

Para atualizar os arquivos de dados, siga os passos:

1. Primeiro, remova os ConfigMaps existentes:
#### Deletando Múltiplos ConfigMaps do projeto
Para deletar vários ConfigMaps de uma vez, você pode usar um dos seguintes comandos:

```bash
# Para visualizar primeiro quais serão deletados
oc get configmap | grep ^painel

# Deletar todos os ConfigMaps que começam com "painel"
oc delete configmap $(oc get configmap | grep ^painel | awk '{print $1}')
```

2. Crie novamente os ConfigMaps com os novos arquivos:
```bash
# Para os arquivos CSV e JSON
oc create configmap painel-ods-db \
  --from-file=objetivos.csv=db/objetivos.csv \
  --from-file=metas.csv=db/metas.csv \
  --from-file=indicadores.csv=db/indicadores.csv \
  --from-file=filtro.csv=db/filtro.csv \
  --from-file=unidade_medida.csv=db/unidade_medida.csv \
  --from-file=sugestoes_visualizacao.json=db/sugestoes_visualizacao.json

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

# Dicionário de Dados

## Estrutura Básica

Todos os arquivos parquet seguem uma estrutura básica comum com as seguintes colunas:

| Coluna | Descrição | Tipo |
|--------|-----------|------|
| ID_INDICADOR | Identificador único do indicador | Categoria |
| CODG_UND_MED | Código da unidade de medida | Categoria |
| VLR_VAR | Valor da variável | Numérico |
| CODG_UND_FED | Código da unidade federativa | Categoria |
| CODG_VAR | Código da variável | Categoria |
| CODG_ANO | Código do ano | Inteiro |

## Campos Adicionais

Além da estrutura básica, os indicadores podem conter campos adicionais para desagregação dos dados:

| Campo | Descrição | Tipo |
|-------|-----------|------|
| CODG_ATV_TRAB | Código da atividade de trabalho | Categoria |
| CODG_DEF | Código do tipo de deficiência | Categoria |
| CODG_ECO_REL_AGUA | Código do ecossistema relacionado à água | Categoria |
| CODG_ETAPA_ENS | Código da etapa de ensino | Categoria |
| CODG_GRUP_OCUP_TRAB_PNAD | Campo de desagregação específico do indicador | Categoria |
| CODG_IDADE | Código da faixa etária | Categoria |
| CODG_INF_ESC | Código da infraestrutura escolar | Categoria |
| CODG_NIV_INSTR | Código do nível de instrução | Categoria |
| CODG_RACA | Código da raça/cor | Categoria |
| CODG_REND_MENSAL_DOM_PER_CAP | Código da renda mensal domiciliar per capita | Categoria |
| CODG_SET_ATIV | Código do setor de atividade | Categoria |
| CODG_SEXO | Código do sexo | Categoria |
| CODG_SIT_DOM | Código da situação do domicílio (urbano/rural) | Categoria |
| CODG_TIPO_DOENCA | Código do tipo de doença | Categoria |
| CODG_TIP_DIN_ECO_REL_AGUA | Código do tipo de dinâmica do ecossistema relacionado à água | Categoria |
| COD_GRU_IDADE_NIV_ENS | Código do grupo de idade por nível de ensino | Categoria |

## Estatísticas dos Indicadores

### ODS 1 - Erradicação da Pobreza
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 1.1.1 | 35 | - | Básico |
| 1.2.1 | 35 | - | Básico |
| 1.5.1 | 35 | - | Básico |
| 1.5.4 | 21 | - | Básico |

### ODS 3 - Saúde e Bem-estar
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 3.1.1 | 105 | - | Médio |
| 3.1.2 | 105 | - | Médio |
| 3.2.1 | 105 | - | Médio |
| 3.2.2 | 105 | - | Médio |
| 3.3.2 | 4,410 | CODG_SEXO, CODG_IDADE | Alto |
| 3.3.3 | 304 | - | Médio |
| 3.3.4 | 2,940 | CODG_IDADE, CODG_SEXO | Alto |
| 3.3.5 | 7,056 | CODG_SEXO, CODG_IDADE, CODG_TIPO_DOENCA | Muito Alto |
| 3.4.1 | 1,890 | CODG_SEXO, CODG_IDADE | Alto |
| 3.4.2 | 2,730 | CODG_SEXO, CODG_IDADE | Alto |
| 3.6.1 | 2,940 | CODG_SEXO, CODG_IDADE | Alto |
| 3.7.2 | 966 | CODG_IDADE | Médio |
| 3.9.2 | 2,940 | CODG_SEXO, CODG_IDADE | Alto |
| 3.9.3 | 2,940 | CODG_SEXO, CODG_IDADE | Alto |
| 3.a.1 | 63 | CODG_SEXO | Básico |

### ODS 4 - Educação de Qualidade
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 4.1.2 | 126 | COD_GRU_IDADE_NIV_ENS | Médio |
| 4.2.2 | 252 | CODG_SEXO | Médio |
| 4.5.1 | 168 | - | Médio |
| 4.a.1 | 1,470 | CODG_INF_ESC | Alto |
| 4.c.1 | 448 | CODG_ETAPA_ENS | Médio |

### ODS 5 - Igualdade de Gênero
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 5.4.1.2 | 315 | CODG_SEXO, CODG_RACA | Médio |
| 5.4.1.3 | 315 | CODG_SEXO, CODG_SIT_DOM | Médio |
| 5.4.1 | 525 | CODG_SEXO, CODG_IDADE | Médio |
| 5.5.1.1 | 42 | - | Básico |
| 5.5.1 | 42 | - | Básico |

### ODS 6 - Água Potável e Saneamento
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 6.1.1 | 42 | - | Básico |
| 6.2.1 | 14 | - | Básico |
| 6.4.1 | 504 | CODG_SET_ATIV | Médio |
| 6.6.1 | 112 | CODG_ECO_REL_AGUA, CODG_TIP_DIN_ECO_REL_AGUA | Médio |

### ODS 7 - Energia Acessível e Limpa
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 7.1.1 | 42 | - | Básico |
| 7.1.2 | 14 | - | Básico |

### ODS 8 - Trabalho Decente e Crescimento Econômico
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 8.3.1.2 | 189 | CODG_ATV_TRAB | Médio |
| 8.3.1.3 | 21 | CODG_DEF | Básico |
| 8.3.1 | 189 | CODG_SEXO | Médio |
| 8.5.1.2 | 728 | CODG_IDADE | Médio |
| 8.5.1.3 | 1,001 | CODG_GRUP_OCUP_TRAB_PNAD | Alto |
| 8.5.1.4 | 21 | CODG_DEF | Básico |
| 8.5.1 | 273 | CODG_SEXO | Médio |
| 8.5.2.2 | 273 | CODG_SEXO | Médio |
| 8.5.2.3 | 728 | CODG_IDADE | Médio |
| 8.5.2 | 21 | CODG_DEF | Básico |
| 8.6.1 | 42 | - | Básico |

### ODS 9 - Indústria, Inovação e Infraestrutura
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 9.2.1 | 168 | - | Médio |
| 9.2.2 | 84 | - | Básico |
| 9.b.1 | 84 | - | Básico |

### ODS 11 - Cidades e Comunidades Sustentáveis
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 11.3.2 | 175 | - | Médio |
| 11.5.1 | 63 | - | Básico |
| 11.b.2 | 21 | - | Básico |

### ODS 13 - Ação Contra a Mudança Global do Clima
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 13.1.1 | 63 | - | Básico |
| 13.1.3 | 21 | - | Básico |

### ODS 16 - Paz, Justiça e Instituições Eficazes
| Indicador | Total de Registros | Desagregações | Nível de Desagregação |
|-----------|-------------------|---------------|----------------------|
| 16.1.1.2 | 455 | CODG_IDADE | Médio |
| 16.1.1.3 | 910 | CODG_SEXO, CODG_IDADE | Médio |
| 16.1.1.4 | 70 | CODG_SEXO | Básico |
| 16.1.1 | 35 | - | Básico |
| 16.1.3.1 | 630 | CODG_IDADE, CODG_SIT_DOM | Médio |
| 16.1.3.2 | 630 | CODG_NIV_INSTR, CODG_SIT_DOM | Médio |
| 16.1.3.3 | 504 | CODG_RACA, CODG_SIT_DOM | Médio |
| 16.1.3.4 | 1,008 | CODG_REND_MENSAL_DOM_PER_CAP, CODG_SIT_DOM | Alto |
| 16.1.3 | 441 | CODG_SEXO, CODG_SIT_DOM | Médio |
| 16.9.1 | 28 | - | Básico |

## Legenda do Nível de Desagregação

- **Básico**: Apenas com as colunas padrão (até 100 registros)
- **Médio**: Com uma desagregação adicional (100-1.000 registros)
- **Alto**: Com duas desagregações adicionais (1.000-5.000 registros)
- **Muito Alto**: Com três ou mais desagregações (mais de 5.000 registros)

## Observações

1. Os campos são armazenados em tipos de dados apropriados:
   - Valores numéricos (VLR_VAR): float64
   - Anos (CODG_ANO): Int64
   - Códigos e identificadores: category
2. A estrutura básica é comum a todos os indicadores
3. As colunas adicionais variam de acordo com a especificidade de cada indicador
4. O número de registros varia significativamente entre os indicadores
5. A desagregação dos dados permite análises mais detalhadas por diferentes dimensões

## Visualizações Implementadas

O painel oferece quatro tipos diferentes de visualizações para cada indicador:

### 1. Gráfico de Linhas
- Exibe a evolução temporal dos valores do indicador
- Linhas suavizadas para melhor visualização das tendências
- Destaque especial para Goiás (linha verde mais grossa)
- Hover com informações detalhadas incluindo unidade de medida
- Legenda interativa para filtrar estados específicos

### 2. Gráfico de Barras
- Permite comparação direta entre os estados
- Destaque para Goiás (barras em verde)
- Mesmas informações no hover que o gráfico de linhas
- Facilita a visualização de valores absolutos

### 3. Gráfico de Pizza
- Visualização da distribuição percentual dos dados
- Seletor de ano para visualizar diferentes períodos
- Hover mostrando estado, valor e percentual
- Unidade de medida exibida no título do gráfico
- Cores consistentes com as outras visualizações
- Legenda interativa para destacar estados específicos

### 4. Mapa Coroplético
- Visualização geográfica dos dados por estado
- Seletor de ano para visualizar diferentes períodos
- Escala de cores Viridis para representar os valores
- Hover mostrando nome do estado e valor com unidade de medida
- Ajuste automático para mostrar todo o território brasileiro

### Características Comuns
- Todas as visualizações compartilham:
  - Mesmo esquema de cores
  - Mesmo formato de apresentação dos dados
  - Unidades de medida consistentes
  - Destaque especial para Goiás
  - Interatividade ao passar o mouse

### Layout
- Gráficos de linha e barra ocupam 60% da largura à esquerda
- Gráfico de pizza e mapa coroplético ocupam 40% da largura à direita
- Dropdown para seleção do ano acima do gráfico de pizza e do mapa
- Altura dos containers ajustada para 800px para melhor visualização
- Padding e bordas consistentes em todos os containers
