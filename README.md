# Painel ODS - Instituto Mauro Borges 🌍

Este é um painel interativo desenvolvido com Dash para visualização dos Objetivos de Desenvolvimento Sustentável (ODS) do Instituto Mauro Borges.

## 📑 Índice

- [Análise do Projeto](#análise-do-projeto)
- [Tecnologias](#tecnologias)
- [Arquitetura](#arquitetura)
- [Documentação](#documentação)
- [Instalação](#instalação)
- [Banco de Dados](#banco-de-dados)
- [Autenticação](#autenticação)
- [API Endpoints](#api-endpoints)
- [Desenvolvimento](#desenvolvimento)
- [Testes](#testes)
- [Contribuição](#contribuição)

## 📊 Análise do Projeto

### Estrutura Geral

O projeto é um painel de visualização de dados relacionado aos Objetivos de Desenvolvimento Sustentável (ODS), desenvolvido com Dash, um framework Python baseado em Flask para criação de aplicações web analíticas.

### Componentes Principais

#### 1. Configuração e Inicialização

- O aplicativo é configurado com temas Bootstrap e serviços de arquivos estáticos
- Implementa uma configuração flexível baseada em variáveis de ambiente através de um arquivo `.env`
- Possui um modo de manutenção que pode ser ativado/desativado remotamente

#### 2. Estrutura de Dados

- Os dados são organizados hierarquicamente:
  - **Objetivos**: representam os Objetivos de Desenvolvimento Sustentável
  - **Metas**: subdivisões dos objetivos
  - **Indicadores**: métricas para avaliar o progresso das metas
  - **Variáveis**: diferentes aspectos mensuráveis dos indicadores

#### 3. Sistema de Cache Avançado

- Implementa um sistema de cache de dois níveis (memória e disco) para otimização máxima
- Utiliza cache em memória para acesso ultra-rápido aos dados mais recentes
- Mantém cache persistente em disco para dados que não mudam com frequência
- Implementa pré-carregamento preditivo de indicadores relacionados em segundo plano
- Inclui monitoramento de estatísticas de desempenho do cache
- Oferece uma rota para limpar o cache quando necessário

#### 4. Visualizações de Dados

- Oferece diferentes tipos de visualizações:
  - Gráficos de linha para evolução temporal
  - Mapas coropléticos para visualização geográfica
  - Gráficos de pizza para distribuição percentual
  - Tabelas de dados detalhados

#### 5. Interatividade

- Implementa callbacks para:
  - Navegação entre objetivos, metas e indicadores
  - Seleção de anos e variáveis nos filtros
  - Atualização dinâmica dos gráficos baseada nas seleções do usuário

#### 6. Segurança

- Proteção por senha para o modo de manutenção
- Geração segura de chaves secretas para o Flask
- Armazenamento seguro de senhas com hash bcrypt

#### 7. Gerenciamento de Recursos

- Carrega dados de arquivos CSV e Parquet
- Oferece tratamento de erros para lidar com dados ausentes ou incorretos
- Implementa convertibilidade de formatos para garantir compatibilidade

### Funcionalidades Destacadas

1. **Visualização Interativa**: O usuário pode navegar pelos diferentes objetivos, metas e indicadores, visualizando os dados de forma dinâmica.

2. **Exploração Multidimensional**: Permite a análise por diferentes variáveis, anos e unidades federativas.

3. **Modo de Manutenção**: Possibilita que administradores coloquem o sistema em manutenção sem interromper completamente o serviço.

4. **Sistema de Cache Eficiente**: Otimiza o desempenho ao armazenar em cache dados frequentemente acessados.

5. **Responsividade**: Interface adaptável com componentes do Bootstrap e AG Grid para uma melhor experiência do usuário.

### Otimizações Implementadas

- **Cache de Dois Níveis**: Combina cache em memória (rápido) e em disco (persistente) para performance máxima
- **Pré-carregamento Preditivo**: Antecipa as necessidades do usuário carregando dados relacionados em segundo plano
- **Lazy Loading**: Carrega apenas os dados necessários quando solicitados, com carregamento sob demanda
- **Monitoramento de Performance**: Acompanha estatísticas detalhadas de uso do cache através de um relatório de desempenho para otimização contínua
- **Configuração Flexível**: Permite ajustar parâmetros via variáveis de ambiente
- **Tratamento de Erros Robusto**: Garante que o sistema continue funcionando mesmo com dados parciais ou ausentes

## 🛠️ Tecnologias

- Python 3.8+
- Dash
- Plotly
- Pandas
- Dash Bootstrap Components
- Dash AG Grid
- GeoJSON
- Docker
- OpenShift

## 🏗️ Arquitetura

### Estrutura do Projeto

``` None
painel-ods/
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
├── assets/                # Recursos estáticos
│   ├── css/
│   ├── js/
│   └── img/
├── Dockerfile             # Configuração do container
├── .openshiftignore       # Arquivos a serem ignorados no build do OpenShift
└── requirements.txt       # Dependências Python
```

## 📚 Documentação

### Funcionalidades

- Visualização interativa dos ODS
- Gráficos dinâmicos e interativos
- Mapa coroplético do Brasil
- Tabelas de dados detalhadas
- Filtros por ano e variáveis
- Interface responsiva e moderna
- Sistema de login e autenticação
- Página de manutenção
- Sistema de cache avançado de dois níveis com pré-carregamento preditivo
- Sugestões automáticas de visualização

### Visualizações

O painel oferece quatro tipos diferentes de visualizações para cada indicador:

#### 1. Gráfico de Linhas

- Evolução temporal dos valores
- Linhas suavizadas para tendências
- Destaque para Goiás
- Hover com informações detalhadas
- Legenda interativa

#### 2. Gráfico de Barras

- Comparação entre estados
- Destaque para Goiás
- Hover com informações detalhadas
- Visualização de valores absolutos

#### 3. Gráfico de Pizza

- Distribuição percentual
- Seletor de ano
- Hover com estado, valor e percentual
- Unidade de medida no título
- Cores consistentes
- Legenda interativa

#### 4. Mapa Coroplético

- Visualização geográfica
- Seletor de ano
- Escala de cores Viridis
- Hover com informações detalhadas
- Ajuste automático do território

### Layout

- Gráficos de linha e barra: 60% da largura à esquerda
- Gráfico de pizza e mapa: 40% da largura à direita
- Dropdown de ano acima do pizza e mapa
- Altura dos containers: 800px
- Padding e bordas consistentes

### Sistema de Cache Avançado

#### Arquitetura de Dois Níveis

- **Nível 1 (Memória)**: Armazena dados recentemente acessados na RAM para acesso ultra-rápido
- **Nível 2 (Disco)**: Mantém dados persistentes em arquivos serializados para acesso entre sessões

#### Pré-carregamento Preditivo

- Quando um usuário seleciona uma meta, o sistema automaticamente inicia o carregamento de todos os indicadores relacionados em segundo plano
- Este processo ocorre em uma thread separada, sem bloquear a interface do usuário
- Os dados pré-carregados são armazenados no cache para acesso instantâneo quando necessário

#### Benefícios

- **Navegação mais rápida**: Redução significativa no tempo de carregamento dos indicadores
- **Menor carga no servidor**: Evita reprocessamento desnecessário dos mesmos dados
- **Melhor experiência do usuário**: Transições mais suaves entre indicadores
- **Persistência entre sessões**: Mantém dados em cache mesmo após reinicialização do servidor

#### Monitoramento de Desempenho

O sistema inclui um relatório de desempenho do cache que fornece as seguintes métricas:

- **Taxa de acesso (Hit Rate)**: Percentual de solicitações atendidas pelo cache
- **Acessos em memória**: Número de solicitações atendidas pelo cache em memória (nível 1)
- **Acessos em disco**: Número de solicitações atendidas pelo cache em disco (nível 2)
- **Erros (Misses)**: Número de solicitações que não encontraram dados no cache
- **Pré-carregamentos**: Número de indicadores carregados proativamente pelo sistema
- **Tamanho do cache em memória**: Quantidade atual e máxima de itens no cache em memória

Este relatório permite monitorar a eficiência do sistema de cache e identificar oportunidades de otimização.

## 📦 Instalação

### Requisitos

- Python 3.8+
- Docker (opcional, para desenvolvimento local)
- OpenShift CLI (oc) para deploy no OpenShift

### Passos de Instalação

1.Clone o repositório:

```bash
git clone https://github.com/seu-usuario/painel-ods.git
cd painel-ods
```

2.Crie um ambiente virtual:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3.Instale as dependências:

```bash
pip install -r requirements.txt
```

4.Configure as variáveis de ambiente:

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Gere o hash da senha de manutenção
python generate_password.py
```

5.Inicie o servidor:

```bash
python app.py
```

A aplicação estará disponível em `http://localhost:8050`

## 💾 Banco de Dados

### Estrutura Básica

Todos os arquivos parquet seguem uma estrutura básica comum:

| Coluna | Descrição | Tipo |
|--------|-----------|------|
| ID_INDICADOR | Identificador único do indicador | Categoria |
| CODG_UND_MED | Código da unidade de medida | Categoria |
| VLR_VAR | Valor da variável | Numérico |
| CODG_UND_FED | Código da unidade federativa | Categoria |
| CODG_VAR | Código da variável | Categoria |
| CODG_ANO | Código do ano | Inteiro |

### Campos Adicionais

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

## 🔐 Autenticação

O sistema utiliza autenticação básica para acesso restrito e página de manutenção.

### Modo de Manutenção

Para ativar/desativar o modo de manutenção, faça uma requisição POST para `/toggle-maintenance` com a senha:

```bash
curl -X POST -H "Content-Type: application/json" -d '{"password":"sua_senha"}' http://localhost:8050/toggle-maintenance
```

## 💻 Desenvolvimento

### Desenvolvimento Local com Docker

1.Criar ambiente virtual:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2.Instalar dependências:

```bash
pip install -r requirements.txt
```

3.Executar com Docker:

```bash
docker compose up --build
```

### Deploy no OpenShift

#### Pré-requisitos

1.OpenShift CLI (oc) instalado
2.Acesso a um cluster OpenShift
3.Login no cluster:

```bash
oc login <cluster-url>
```

#### Configuração Inicial

1.Usar o projeto colocation-imb:

```bash
oc project colocation-imb
```

2.Criar recursos de build:

```bash
oc apply -f k8s/imagestream.yaml
oc apply -f k8s/buildconfig.yaml
```

#### Deploy da Aplicação

1.Iniciar o build:

```bash
oc start-build painel-ods --follow
```

2.Deploy dos recursos:

```bash
oc apply -f k8s/
```

## 🧪 Testes

### Executando Testes

```bash
python -m pytest tests/
```

## 🤝 Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 👥 Autores

- Instituto Mauro Borges
- Desenvolvido pela Gerência de Dados e Estatísticas do IMB

## 🙏 Agradecimentos

- Todos os colaboradores que contribuíram com o projeto
- Equipe de dados do IMB
- Comunidade Dash e Plotly
