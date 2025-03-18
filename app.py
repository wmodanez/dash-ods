from dash import html, Dash, callback_context, ALL, no_update, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from config import DEBUG, USE_RELOADER, PORT, HOST, DASH_CONFIG, SERVER_CONFIG
import pandas as pd
from functools import lru_cache
from flask import session, redirect
from dash.exceptions import PreventUpdate
import os
import plotly.express as px
import json
from constants import COLUMN_NAMES, UF_NAMES
import numpy as np
from shapely.geometry import shape, MultiPolygon


def capitalize_words(text):
    return ' '.join(word.capitalize() for word in text.split())


# Inicializa o aplicativo Dash com tema Bootstrap
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.MATERIA,
        "https://cdn.jsdelivr.net/npm/ag-grid-community@30.2.1/styles/ag-grid.min.css",
        "https://cdn.jsdelivr.net/npm/ag-grid-community@30.2.1/styles/ag-theme-alpine.min.css",
    ],
    assets_folder='assets',
    assets_url_path='/assets/',
    **DASH_CONFIG  # Aplica as configurações de performance
)

# Configurações de cache
for key, value in SERVER_CONFIG.items():
    app.server.config[key] = value

# Configura a chave secreta do Flask
app.server.secret_key = SERVER_CONFIG['SECRET_KEY']


# Cache em memória para os dados dos indicadores
indicadores_cache = {}

# Função com cache para carregar dados do indicador
@lru_cache(maxsize=10000)
def load_dados_indicador_cache(indicador_id):
    try:
        # Verifica se os dados já estão no cache
        if indicador_id in indicadores_cache:
            return indicadores_cache[indicador_id]
        
        # Remove apenas "Indicador " do início e mantém os pontos
        nome_arquivo = indicador_id.lower().replace("indicador ", "")
        
        # Define os caminhos dos arquivos
        arquivo_parquet = f'db/resultados/indicador{nome_arquivo}.parquet'
        arquivo_metadados = f'db/resultados/indicador{nome_arquivo}_metadata.json'
        
        # Verifica se o arquivo existe
        if not os.path.exists(arquivo_parquet):
            return pd.DataFrame()  # Retorna um DataFrame vazio em vez de None
        
        # Carrega os metadados primeiro
        try:
            with open(arquivo_metadados, 'r', encoding='utf-8') as f:
                metadados = json.load(f)
        except Exception as e:
            metadados = None
        
        # Carrega o arquivo parquet
        try:
            df = pd.read_parquet(arquivo_parquet)
            if df.empty:
                return pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()
        
        # Se tiver metadados, aplica as configurações
        if metadados:
            # Configura os tipos das colunas conforme os metadados
            for coluna, tipo in metadados['colunas'].items():
                if coluna in df.columns:
                    try:
                        if coluna == 'CODG_ANO':
                            df[coluna] = df[coluna].astype(str)
                        elif 'Int64' in tipo:
                            df[coluna] = pd.to_numeric(df[coluna], errors='coerce').astype('Int64')
                        elif 'float' in tipo:
                            df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
                        elif 'category' in tipo:
                            df[coluna] = df[coluna].astype('category')
                    except Exception as e:
                        pass
        
        # Armazena no cache
        indicadores_cache[indicador_id] = df
        return df
    except Exception as e:
        return pd.DataFrame()  # Retorna um DataFrame vazio em vez de None

# Função para limpar o cache dos indicadores
def limpar_cache_indicadores():
    global indicadores_cache
    indicadores_cache.clear()
    load_dados_indicador_cache.cache_clear()

# Modifica a rota de limpar cache para também limpar o cache dos indicadores
@app.server.route('/limpar-cache')
def limpar_cache():
    try:
        session.clear()
        limpar_cache_indicadores()
        return redirect('/')  # Redireciona para a página inicial
    except Exception as e:
        return redirect('/')  # Redireciona para a página inicial mesmo em caso de erro


# Template HTML básico com otimizações
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>IMB - Painel ODS</title>
        <link rel="icon" type="image/x-icon" href="/assets/favicon.ico">
        {%favicon%}
        {%css%}
        <meta http-equiv="Cache-Control" content="max-age=31536000">
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''


# Lê o arquivo CSV de objetivos
@lru_cache(maxsize=1)
def load_objetivos():
    try:
        df = pd.read_csv(
            'db/objetivos.csv',
            low_memory=False,
            encoding='utf-8',
            dtype=str,
            sep=';',
            on_bad_lines='skip'
        )
        
        # Remover a primeira linha se ela contiver #
        if df.iloc[(0,)].name == '#':
            df = df.iloc[1:]
        # Garantir que as colunas necessárias existam
        required_columns = ['ID_OBJETIVO', 'RES_OBJETIVO', 'DESC_OBJETIVO', 'BASE64']
        for col in required_columns:
            if col not in df.columns:
                return pd.DataFrame(columns=required_columns)
        return df
    except Exception as e:
        return pd.DataFrame(columns=['ID_OBJETIVO', 'RES_OBJETIVO', 'DESC_OBJETIVO', 'BASE64'])


@lru_cache(maxsize=1)
def load_metas():
    try:
        df_metas = pd.read_csv(
            'db/metas.csv',
            low_memory=False,
            encoding='utf-8',
            dtype=str,
            sep=';',
            on_bad_lines='skip'
        )
    except Exception as e:
        df_metas = pd.DataFrame()
    return df_metas


@lru_cache(maxsize=1)
def load_indicadores():
    try:
        df_indicadores = pd.read_csv(
            'db/indicadores.csv',
            low_memory=False,
            encoding='utf-8',
            dtype=str,
            sep=';',
            on_bad_lines='skip'
        )
        df_indicadores['RBC'] = pd.to_numeric(df_indicadores['RBC'], errors='coerce')
        df_indicadores = df_indicadores.loc[df_indicadores['RBC'] == 1]
        return df_indicadores
    except Exception as e:
        return pd.DataFrame()


@lru_cache(maxsize=1)
def load_sugestoes_visualizacao():
    try:
        df_sugestoes = pd.read_csv(
            'db/sugestoes_visualizacao.csv',
            low_memory=False,
            encoding='utf-8',
            dtype=str,
            sep=';',
            on_bad_lines='skip'
        )
        return df_sugestoes
    except Exception as e:
        return pd.DataFrame()


@lru_cache(maxsize=1)
def load_unidade_medida():
    try:
        # Tenta ler o arquivo com diferentes configurações
        try:
            df_unidade_medida = pd.read_csv(
                'db/unidade_medida.csv',
                low_memory=False,
                encoding='utf-8',
                dtype=str,
                sep=';'
            )
        except:
            # Se falhar, tenta ler com vírgula como separador
            df_unidade_medida = pd.read_csv(
                'db/unidade_medida.csv',
                low_memory=False,
                encoding='utf-8',
                dtype=str,
                sep=','
            )
        
        # Verifica se as colunas necessárias existem
        if len(df_unidade_medida.columns) == 1 and ',' in df_unidade_medida.columns[0]:
            # Se as colunas estiverem juntas, separa-as
            df_unidade_medida = pd.DataFrame([x.split(',') for x in df_unidade_medida[df_unidade_medida.columns[0]]])
            # Pega apenas as colunas necessárias (CODG_UND_MED e DESC_UND_MED)
            if len(df_unidade_medida.columns) >= 2:
                df_unidade_medida = df_unidade_medida.iloc[:, [0, 1]]
                df_unidade_medida.columns = ['CODG_UND_MED', 'DESC_UND_MED']
        
        # Garante que as colunas estejam presentes e com os nomes corretos
        if 'CODG_UND_MED' not in df_unidade_medida.columns or 'DESC_UND_MED' not in df_unidade_medida.columns:
            return pd.DataFrame(columns=['CODG_UND_MED', 'DESC_UND_MED'])
        
        # Remove espaços extras e aspas das colunas
        df_unidade_medida['CODG_UND_MED'] = df_unidade_medida['CODG_UND_MED'].str.strip().str.strip('"')
        df_unidade_medida['DESC_UND_MED'] = df_unidade_medida['DESC_UND_MED'].str.strip().str.strip('"')
        
        return df_unidade_medida
    except Exception as e:
        return pd.DataFrame(columns=['CODG_UND_MED', 'DESC_UND_MED'])


@lru_cache(maxsize=1)
def load_filtro():
    try:
        # Tenta ler o arquivo com diferentes configurações
        try:
            df_filtro = pd.read_csv(
                'db/filtro.csv',
                low_memory=False,
                encoding='utf-8',
                dtype=str,
                sep=';'
            )
        except:
            # Se falhar, tenta ler com vírgula como separador
            df_filtro = pd.read_csv(
                'db/filtro.csv',
                low_memory=False,
                encoding='utf-8',
                dtype=str,
                sep=','
            )
        
        # Verifica se as colunas necessárias existem
        if len(df_filtro.columns) == 1 and ',' in df_filtro.columns[0]:
            # Se as colunas estiverem juntas, separa-as
            df_filtro = pd.DataFrame([x.split(',') for x in df_filtro[df_filtro.columns[0]]])
            # Pega apenas as colunas necessárias (CODG_VAR e DESC_VAR)
            if len(df_filtro.columns) >= 2:
                df_filtro = df_filtro.iloc[:, [0, 1]]
                df_filtro.columns = ['CODG_VAR', 'DESC_VAR']
        
        # Garante que as colunas estejam presentes e com os nomes corretos
        if 'CODG_VAR' not in df_filtro.columns or 'DESC_VAR' not in df_filtro.columns:
            return pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])
        
        # Remove espaços extras e aspas das colunas
        df_filtro['CODG_VAR'] = df_filtro['CODG_VAR'].str.strip().str.strip('"')
        df_filtro['DESC_VAR'] = df_filtro['DESC_VAR'].str.strip().str.strip('"')
        
        return df_filtro
    except Exception as e:
        return pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])


# Carrega os dados
df = load_objetivos()
df_metas = load_metas()
df_indicadores = load_indicadores()
df_unidade_medida = load_unidade_medida()
df_filtro = load_filtro()

# Define o conteúdo inicial do card
if not df.empty:
    row_objetivo_0 = df.iloc[(0,)]
    initial_header = row_objetivo_0['RES_OBJETIVO']
    initial_content = row_objetivo_0['DESC_OBJETIVO']
else:
    initial_header = "Erro ao carregar dados"
    initial_content = "Não foi possível carregar os dados dos objetivos. Por favor, verifique se os arquivos CSV estão presentes na pasta db."

initial_meta_description = ""

# Prepara as metas iniciais do objetivo 0
if not df.empty and not df_metas.empty:
    try:
        metas_filtradas_inicial = df_metas[df_metas['ID_OBJETIVO'] == df.iloc[(0,)]['ID_OBJETIVO']]
        metas_com_indicadores_inicial = [
            meta for _, meta in metas_filtradas_inicial.iterrows()
            if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
        ]
        
        # Define a meta inicial e sua descrição
        meta_inicial = metas_com_indicadores_inicial[0] if metas_com_indicadores_inicial else None
        initial_meta_description = meta_inicial['DESC_META'] if meta_inicial else ""
    except Exception as e:
        meta_inicial = None
        initial_meta_description = ""
else:
    meta_inicial = None
    initial_meta_description = ""

# Prepara os indicadores iniciais
initial_indicadores_section = []
if meta_inicial:
    indicadores_meta_inicial = df_indicadores[df_indicadores['ID_META'] == meta_inicial['ID_META']]
    if not indicadores_meta_inicial.empty:
        tabs_indicadores = []
        for _, row in indicadores_meta_inicial.iterrows():
            df_dados = load_dados_indicador_cache(row['ID_INDICADOR'])
            tab_content = [
                html.P(row['DESC_INDICADOR'], className="text-justify p-3")
            ]

            if df_dados is not None and not df_dados.empty:
                try:
                    # Adiciona o dropdown de variáveis se o indicador tiver VARIAVEIS = 1
                    tab_content = [
                        html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                    ]
                    
                    # Verifica se o indicador tem VARIAVEIS = 1
                    indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row['ID_INDICADOR']]
                    if not indicador_info.empty and indicador_info['VARIAVEIS'].iloc[0] == '1':
                        # Carrega as variáveis do arquivo filtro.csv
                        df_filtro_loaded = load_filtro()
                        
                        # Obtém as variáveis únicas do indicador
                        variaveis_indicador = df_dados['CODG_VAR'].unique() if 'CODG_VAR' in df_dados.columns else []
                        
                        # Filtra apenas as variáveis que existem no indicador
                        df_filtro_loaded = df_filtro_loaded[df_filtro_loaded['CODG_VAR'].isin(variaveis_indicador)]
                        
                        if not df_filtro_loaded.empty:
                            tab_content.append(
                                dbc.Row([
                                    dbc.Col([
                                        html.Label("Selecione a Variável:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                                        dcc.Dropdown(
                                            id={'type': 'var-dropdown', 'index': row['ID_INDICADOR']},
                                            options=[
                                                {'label': desc, 'value': cod} 
                                                for cod, desc in zip(df_filtro_loaded['CODG_VAR'], df_filtro_loaded['DESC_VAR'])
                                            ],
                                            value=df_filtro_loaded['CODG_VAR'].iloc[0] if not df_filtro_loaded.empty else None,
                                            style={'width': '70%', 'marginBottom': '20px'}
                                        )
                                    ], width=12)
                                ])
                            )
                        
                        grid = create_visualization(df_dados, row['ID_INDICADOR'])
                        tab_content.append(grid)
                except Exception as e:
                    print(f"Erro ao processar dropdown de variáveis: {e}")
                    tab_content = [
                        html.P(row['DESC_INDICADOR'], className="text-justify p-3"),
                        grid
                    ]

            tabs_indicadores.append(
                dbc.Tab(
                    tab_content,
                    label=row['ID_INDICADOR'],
                    tab_id=f"tab-{row['ID_INDICADOR']}",
                    id={'type': 'tab-indicador', 'index': row['ID_INDICADOR']}
                )
            )

        initial_indicadores_section = [
            html.H5("Indicadores", className="mt-4 mb-3"),
            dbc.Card(
                dbc.CardBody(
                    dbc.Tabs(
                        children=tabs_indicadores,
                        active_tab=tabs_indicadores[0].tab_id if tabs_indicadores else None
                    )
                ),
                className="mt-3"
            )
        ]

# Layout padrão para todos os gráficos
DEFAULT_LAYOUT = {
    'showlegend': True,
    'legend': dict(
        title="Unidade Federativa",
        yanchor="top",
        y=0.99,
        xanchor="left",
        x=1.05,
        orientation="v"
    ),
    'margin': dict(r=150),  # Margem à direita para acomodar a legenda
    'xaxis': dict(
        showgrid=False,  # Remove as linhas de grade do eixo X
        zeroline=False   # Remove a linha do zero do eixo X
    ),
    'yaxis': dict(
        showgrid=False,  # Remove as linhas de grade do eixo Y
        zeroline=False   # Remove a linha do zero do eixo Y
    )
}

# Define o layout do aplicativo
app.layout = dbc.Container([
    # Header com imagens e título
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Coluna das imagens
                        dbc.Col([
                            dbc.Row([
                                # Imagem da SGG
                                dbc.Col([
                                    html.Img(
                                        src='/assets/img/sgg.png',
                                        style={'width': '40%', 'height': '100%'},
                                        className="img-fluid"
                                    )
                                ], width=6),
                                # Imagem do IMB
                                dbc.Col([
                                    html.Img(
                                        src='/assets/img/imb720.png',
                                        style={'width': '30%', 'height': '100%'},
                                        className="img-fluid"
                                    )
                                ], width=6)
                            ], className="align-items-center")
                        ], width=6),
                        # Coluna do título
                        dbc.Col([
                            html.H1(
                                'Instituto Mauro Borges - ODS - Agenda 2030',
                                className="text-center align-middle",
                                style={'margin': '0', 'padding': '0'}
                            )
                        ], width=6, className="d-flex align-items-center")
                    ], className="align-items-center")
                ])
            ], className="mb-4", style={
                'marginTop': '15px',
                'marginLeft': '15px',
                'marginRight': '15px'
            })
        ])
    ]),

    # Card Principal
    dbc.Row([
        # Menu Lateral
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Menu
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Div([
                                                html.Img(
                                                    src=row['BASE64'],
                                                    style={
                                                        'width': '100%',
                                                        'marginBottom': '10px',
                                                        'cursor': 'pointer'
                                                    },
                                                    className="img-fluid",
                                                    id=f"objetivo{idx}",
                                                    n_clicks=1 if idx == 0 else 0
                                                )
                                            ])
                                        ], width=4) for idx, row in df.iterrows()
                                    ], className="g-2")
                                ])
                            ])
                        ], lg=2),

                        # Main
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(
                                    html.H3(id='card-header', children=initial_header)
                                ),
                                dbc.CardBody([
                                    html.P(id='card-content', children=initial_content),
                                    dbc.Nav(
                                        id='metas-nav',
                                        pills=True,
                                        className="nav nav-pills gap-2",
                                        style={
                                            'display': 'flex',
                                            'flexWrap': 'wrap',
                                            'marginBottom': '1rem'
                                        },
                                        children=[]
                                    ),
                                    html.P(
                                        id='meta-description',
                                        children=initial_meta_description,
                                        className="text-justify mt-4"
                                    ),
                                    html.Div(id='loading-indicator', children=[]),
                                    html.Div(id='indicadores-section', children=[])
                                ])
                            ])
                        ], lg=10)
                    ])
                ])
            ], className="border-0 shadow-none")
        ])
    ])
], fluid=True)


def create_visualization(df, indicador_id=None):
    """Cria uma visualização (gráfico ou tabela) com os dados do DataFrame"""
    if df is None or df.empty:
        return html.Div([
            dbc.Alert(
                "Nenhum dado disponível para este indicador.",
                color="warning",
                className="text-center p-3"
            )
        ])
 
    try:
        # Verifica se as colunas necessárias existem
        colunas_necessarias = ['CODG_ANO', 'VLR_VAR']
        if not all(col in df.columns for col in colunas_necessarias):
            return html.Div([
                dbc.Alert(
                    f"Dados incompletos para criar a visualização. Colunas necessárias: {', '.join(colunas_necessarias)}",
                    color="warning",
                    className="text-center p-3"
                )
            ])

        # Garante que os dados estão ordenados por ano
        df = df.sort_values('CODG_ANO')
        
        # Converte o campo VLR_VAR para numérico e remove valores inválidos
        df['VLR_VAR'] = pd.to_numeric(df['VLR_VAR'], errors='coerce')
        df = df.dropna(subset=['VLR_VAR'])
        
        if df.empty:
            return html.Div([
                dbc.Alert(
                    "Não há dados numéricos válidos para criar a visualização.",
                    color="warning",
                    className="text-center p-3"
                )
            ])
        
        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df.columns:
            df['DESC_UND_FED'] = df['CODG_UND_FED'].astype(str).map(UF_NAMES)
            df = df.dropna(subset=['DESC_UND_FED'])
        
        # Adiciona as descrições da variável e unidade de medida
        if 'CODG_VAR' in df.columns and not df_filtro.empty:
            df['CODG_VAR'] = df['CODG_VAR'].astype(str)
            df_filtro['CODG_VAR'] = df_filtro['CODG_VAR'].astype(str)
            df = df.merge(df_filtro[['CODG_VAR', 'DESC_VAR']], on='CODG_VAR', how='left')
            df['DESC_VAR'] = df['DESC_VAR'].fillna('Descrição não disponível')
        
        if 'CODG_UND_MED' in df.columns and not df_unidade_medida.empty:
            df['CODG_UND_MED'] = df['CODG_UND_MED'].astype(str)
            df_unidade_medida['CODG_UND_MED'] = df_unidade_medida['CODG_UND_MED'].astype(str)
            df = df.merge(df_unidade_medida[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
            df['DESC_UND_MED'] = df['DESC_UND_MED'].fillna('Unidade não disponível')
        
        # Carrega as sugestões de visualização
        df_sugestoes = load_sugestoes_visualizacao()
        
        # Define as configurações da tabela
        columnDefs = []
        
        # Define a ordem das colunas
        column_order = [
            ('DESC_UND_FED', 'Unidade Federativa'),
            ('CODG_ANO', 'Ano'),
            ('DESC_VAR', 'Descrição da Variável'),
            ('VLR_VAR', 'Valor'),
            ('DESC_UND_MED', 'Unidade de Medida')
        ]
        
        # Adiciona as colunas na ordem especificada
        for col, header in column_order:
            if col in df.columns:
                columnDefs.append({
                    "field": col,
                    "headerName": header,
                    "sortable": True,
                    "filter": True,
                    "flex": 1,
                    "minWidth": 100,
                    "resizable": True,
                    "wrapText": True,
                    "autoHeight": True
                })
        
        defaultColDef = {
            "flex": 1,
            "minWidth": 100,
            "resizable": True,
            "wrapText": True,
            "autoHeight": True
        }
        
        # Se tiver um indicador específico e sugestões disponíveis
        if indicador_id and not df_sugestoes.empty:
            sugestoes_indicador = df_sugestoes[df_sugestoes['ID_INDICADOR'] == indicador_id]
            if not sugestoes_indicador.empty:
                try:
                    # Verifica se há dados suficientes para criar os gráficos
                    if len(df) < 2:
                        return html.Div([
                            dbc.Alert(
                                "Não há dados suficientes para criar os gráficos. Mostrando apenas a tabela de dados.",
                                color="warning",
                                className="text-center p-3"
                            ),
                            dag.AgGrid(
                                rowData=df.to_dict('records'),
                                columnDefs=columnDefs,
                                defaultColDef=defaultColDef,
                                dashGridOptions={
                                    "pagination": True,
                                    "paginationPageSize": 10,
                                    "rowHeight": 48,
                                    "domLayout": "autoHeight",
                                    "suppressMovableColumns": True,
                                    "animateRows": True,
                                },
                                style={"height": "100%", "width": "100%"},
                            )
                        ])
                    
                    # Configura o gráfico de linha
                    config = {
                        'x': 'CODG_ANO',
                        'y': 'VLR_VAR',
                        'color': 'DESC_UND_FED' if 'DESC_UND_FED' in df.columns else None
                    }
                    
                    # Tratamento para dados anuais
                    if 'DESC_UND_FED' in df.columns:
                        df = df.groupby(['CODG_ANO', 'DESC_UND_FED'], as_index=False).first()
                    else:
                        df = df.groupby('CODG_ANO', as_index=False).first()
                    
                    # Atualiza os labels dos eixos
                    config['labels'] = {
                        'x': f"<b>{COLUMN_NAMES.get('CODG_ANO', 'Ano')}</b>",
                        'y': "",
                        'color': f"<b>{COLUMN_NAMES.get('DESC_UND_FED', 'Unidade Federativa')}</b>" if 'DESC_UND_FED' in df.columns else None
                    }
                    
                    # Cria os gráficos
                    fig_line = px.line(df, **config)
                    fig_line.update_traces(line_shape='spline')
                    fig_bar = px.bar(df, **config)
                    
                    # Carrega o GeoJSON do Brasil
                    with open('db/br_geojson.json', 'r', encoding='utf-8') as f:
                        geojson = json.load(f)
                    
                    # Cria o mapa coroplético
                    fig_map = px.choropleth(
                        df,
                        geojson=geojson,
                        locations='DESC_UND_FED',
                        featureidkey='properties.name',
                        color='VLR_VAR',
                        color_continuous_scale='Greens_r',
                        scope="south america"
                    )
                    
                    # Ajusta o layout do mapa
                    fig_map.update_geos(
                        visible=False,
                        showcoastlines=True,
                        coastlinecolor="Black",
                        showland=True,
                        landcolor="white",
                        showframe=False,
                        center=dict(lat=-12.9598, lon=-53.2729),
                        projection=dict(
                            type='mercator',
                            scale=2.6
                        )
                    )
                    
                    # Aplica o layout padrão
                    layout = DEFAULT_LAYOUT.copy()
                    layout.update({
                        'xaxis_title': config['labels']['x'],
                        'yaxis_title': config['labels']['y'],
                        'xaxis': dict(
                            showgrid=False,
                            zeroline=False,
                            tickfont=dict(size=12, color='black'),
                            ticktext=[f"<b>{x}</b>" for x in sorted(df['CODG_ANO'].unique())],
                            tickvals=sorted(df['CODG_ANO'].unique())
                        ),
                        'yaxis': dict(
                            showgrid=False,
                            zeroline=False,
                            tickfont=dict(size=12, color='black')
                        )
                    })
                    
                    # Aplica os layouts
                    fig_line.update_layout(layout)
                    fig_bar.update_layout(layout)
                    
                    # Remove linhas de grade
                    fig_line.update_xaxes(showgrid=False, zeroline=False)
                    fig_line.update_yaxes(showgrid=False, zeroline=False)
                    fig_bar.update_xaxes(showgrid=False, zeroline=False)
                    fig_bar.update_yaxes(showgrid=False, zeroline=False)
                    
                    # Destaca Goiás
                    if 'DESC_UND_FED' in df.columns:
                        for trace in fig_line.data:
                            if hasattr(trace, 'name') and trace.name == 'Goiás':
                                trace.line = dict(color='#229846', width=6)
                                trace.name = '<b>Goiás</b>'
                        for trace in fig_bar.data:
                            if hasattr(trace, 'name') and trace.name == 'Goiás':
                                trace.marker.color = '#229846'
                                trace.name = '<b>Goiás</b>'
                    
                    return html.Div([
                        html.Div([
                            html.Div([
                                dcc.Graph(figure=fig_line),
                                dcc.Graph(figure=fig_bar)
                            ], style={'width': '60%', 'display': 'inline-block', 'vertical-align': 'top'}),
                            html.Div([
                                html.Label("Selecione o Ano:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                                dcc.Dropdown(
                                    id={'type': 'year-dropdown', 'index': indicador_id},
                                    options=[{'label': ano, 'value': ano} for ano in sorted(df['CODG_ANO'].unique())],
                                    value=sorted(df['CODG_ANO'].unique())[-1],
                                    style={'width': '200px', 'margin': '10px'}
                                ),
                                dcc.Graph(
                                    id={'type': 'choropleth-map', 'index': indicador_id},
                                    figure=fig_map,
                                    style={'height': '600px'}
                                )
                            ], style={'width': '40%', 'display': 'inline-block', 'vertical-align': 'top', 'paddingLeft': '20px'})
                        ]),
                        html.Div([
                            html.H5("Dados Detalhados", className="mt-4 mb-3"),
                            dag.AgGrid(
                                rowData=df.to_dict('records'),
                                columnDefs=columnDefs,
                                defaultColDef=defaultColDef,
                                dashGridOptions={
                                    "pagination": True,
                                    "paginationPageSize": 10,
                                    "rowHeight": 48,
                                    "domLayout": "autoHeight",
                                    "suppressMovableColumns": True,
                                    "animateRows": True,
                                },
                                style={"height": "100%", "width": "100%"},
                            )
                        ], style={'width': '100%', 'marginTop': '20px'})
                    ])
                except Exception as e:
                    return html.Div([
                        dbc.Alert(
                            [
                                html.H4("Erro ao criar os gráficos", className="alert-heading"),
                                html.P("Ocorreu um erro ao tentar criar as visualizações. Mostrando apenas a tabela de dados."),
                                html.Hr(),
                                html.P(f"Detalhes do erro: {str(e)}", className="mb-0")
                            ],
                            color="warning",
                            className="text-center p-3"
                        ),
                        dag.AgGrid(
                            rowData=df.to_dict('records'),
                            columnDefs=columnDefs,
                            defaultColDef=defaultColDef,
                            dashGridOptions={
                                "pagination": True,
                                "paginationPageSize": 10,
                                "rowHeight": 48,
                                "domLayout": "autoHeight",
                                "suppressMovableColumns": True,
                                "animateRows": True,
                            },
                            style={"height": "100%", "width": "100%"},
                        )
                    ])
        
        # Se não encontrar sugestão ou não tiver indicador, mostra apenas a tabela
        return dag.AgGrid(
            rowData=df.to_dict('records'),
            columnDefs=columnDefs,
            defaultColDef=defaultColDef,
            dashGridOptions={
                "pagination": True,
                "paginationPageSize": 10,
                "rowHeight": 48,
                "domLayout": "autoHeight",
                "suppressMovableColumns": True,
                "animateRows": True,
            },
            style={"height": "100%", "width": "100%"},
        )
    except Exception as e:
        return html.Div([
            dbc.Alert(
                [
                    html.H4("Erro ao criar a visualização", className="alert-heading"),
                    html.P("Ocorreu um erro ao tentar processar os dados."),
                    html.Hr(),
                    html.P(f"Detalhes do erro: {str(e)}", className="mb-0")
                ],
                color="danger",
                className="text-center p-3"
            )
        ])


# Modifica o callback de atualização do card para usar AG Grid
@app.callback(
    [
        Output('card-header', 'children'),
        Output('card-content', 'children'),
        Output('metas-nav', 'children'),
        Output('meta-description', 'children'),
        Output('indicadores-section', 'children')
    ],
    [Input(f"objetivo{i}", "n_clicks") for i in range(len(df))] +
    [Input({'type': 'meta-button', 'index': ALL}, 'n_clicks')],
    [State({'type': 'meta-button', 'index': ALL}, 'active')],
    prevent_initial_call=False
)
def update_card_content(*args):
    ctx = callback_context
    if not ctx.triggered:
        return initial_header, initial_content, [], initial_meta_description, []

    try:
        triggered_id = ctx.triggered[0]['prop_id']

        # Se for um clique em uma meta
        if 'meta-button' in triggered_id:
            try:
                meta_id = triggered_id.split('"index":"')[1].split('"')[0]
                meta_filtrada = df_metas[df_metas['ID_META'] == meta_id]

                if not meta_filtrada.empty:
                    meta_desc = meta_filtrada['DESC_META'].iloc[0]
                    objetivo_id = meta_filtrada['ID_OBJETIVO'].iloc[0]
                    metas_filtradas = df_metas[df_metas['ID_OBJETIVO'] == objetivo_id]
                    metas_com_indicadores = [
                        meta for _, meta in metas_filtradas.iterrows()
                        if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
                    ]

                    if not metas_com_indicadores:
                        return no_update, no_update, [], dbc.Alert(
                            "Não existem indicadores disponíveis para esta meta.",
                            color="warning",
                            className="text-center p-3"
                        ), []

                    metas_atualizadas = [
                        dbc.NavLink(
                            meta['ID_META'],
                            id={'type': 'meta-button', 'index': meta['ID_META']},
                            href="#",
                            active=meta['ID_META'] == meta_id,
                            className="nav-link"
                        ) for meta in metas_com_indicadores
                    ]

                    indicadores_meta = df_indicadores[df_indicadores['ID_META'] == meta_id]
                    if not indicadores_meta.empty:
                        tabs_indicadores = []
                        for _, row in indicadores_meta.iterrows():
                            df_dados = load_dados_indicador_cache(row['ID_INDICADOR'])
                            tab_content = [
                                html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                            ]

                            if df_dados is not None and not df_dados.empty:
                                try:
                                    # Adiciona o dropdown de variáveis se o indicador tiver VARIAVEIS = 1
                                    tab_content = [
                                        html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                                    ]
                                    
                                    # Verifica se o indicador tem VARIAVEIS = 1
                                    indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row['ID_INDICADOR']]
                                    if not indicador_info.empty and indicador_info['VARIAVEIS'].iloc[0] == '1':
                                        # Carrega as variáveis do arquivo filtro.csv
                                        df_filtro_loaded = load_filtro()
                                        
                                        # Obtém as variáveis únicas do indicador
                                        variaveis_indicador = df_dados['CODG_VAR'].unique() if 'CODG_VAR' in df_dados.columns else []
                                        
                                        # Filtra apenas as variáveis que existem no indicador
                                        df_filtro_loaded = df_filtro_loaded[df_filtro_loaded['CODG_VAR'].isin(variaveis_indicador)]
                                        
                                        if not df_filtro_loaded.empty:
                                            tab_content.append(
                                                dbc.Row([
                                                    dbc.Col([
                                                        html.Label("Selecione a Variável:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                                                        dcc.Dropdown(
                                                            id={'type': 'var-dropdown', 'index': row['ID_INDICADOR']},
                                                            options=[
                                                                {'label': desc, 'value': cod} 
                                                                for cod, desc in zip(df_filtro_loaded['CODG_VAR'], df_filtro_loaded['DESC_VAR'])
                                                            ],
                                                            value=df_filtro_loaded['CODG_VAR'].iloc[0] if not df_filtro_loaded.empty else None,
                                                            style={'width': '70%', 'marginBottom': '20px'}
                                                        )
                                                    ], width=12)
                                                ])
                                            )
                                    
                                    grid = create_visualization(df_dados, row['ID_INDICADOR'])
                                    tab_content.append(grid)
                                except Exception as e:
                                    print(f"Erro ao processar dropdown de variáveis: {e}")
                                    tab_content = [
                                        html.P(row['DESC_INDICADOR'], className="text-justify p-3"),
                                        grid
                                    ]

                            tabs_indicadores.append(
                                dbc.Tab(
                                    tab_content,
                                    label=row['ID_INDICADOR'],
                                    tab_id=f"tab-{row['ID_INDICADOR']}",
                                    id={'type': 'tab-indicador', 'index': row['ID_INDICADOR']}
                                )
                            )

                        indicadores_section = [
                            html.H5("Indicadores", className="mt-4 mb-3"),
                            dbc.Card(
                                dbc.CardBody(
                                    dbc.Tabs(
                                        children=tabs_indicadores,
                                        active_tab=tabs_indicadores[0].tab_id if tabs_indicadores else None
                                    )
                                ),
                                className="mt-3"
                            )
                        ]
                    else:
                        indicadores_section = []

                    return no_update, no_update, metas_atualizadas, meta_desc, indicadores_section
                else:
                    return no_update, no_update, [], dbc.Alert(
                        "Meta não encontrada.",
                        color="warning",
                        className="text-center p-3"
                    ), []
            except Exception as e:
                return no_update, no_update, [], dbc.Alert(
                    [
                        html.H4("Erro ao carregar os dados da meta", className="alert-heading"),
                        html.P("Ocorreu um erro ao tentar carregar os dados da meta selecionada."),
                        html.Hr(),
                        html.P(f"Detalhes do erro: {str(e)}", className="mb-0")
                    ],
                    color="danger",
                    className="text-center p-3"
                ), []

        # Se for um clique em um objetivo
        button_id = triggered_id.split('.')[0]
        if not button_id.startswith('objetivo'):
            return initial_header, initial_content, [], initial_meta_description, []

        try:
            index = int(button_id.replace('objetivo', ''))
            if index >= len(df):
                return initial_header, dbc.Alert(
                    "Objetivo não encontrado.",
                    color="warning",
                    className="text-center p-3"
                ), [], "", []
            
            row = df.iloc[index]
            if not all(key in row for key in ['DESC_OBJETIVO', 'RES_OBJETIVO', 'ID_OBJETIVO']):
                return initial_header, dbc.Alert(
                    "Dados do objetivo estão incompletos.",
                    color="warning",
                    className="text-center p-3"
                ), [], "", []

            header = f"{row['ID_OBJETIVO']} - {row['RES_OBJETIVO']}" if index > 0 else row['RES_OBJETIVO']
            content = row['DESC_OBJETIVO']

            # Se for o objetivo 0, retorna apenas o header e content
            if index == 0:
                return header, content, [], "", []

            metas_filtradas = df_metas[df_metas['ID_OBJETIVO'] == row['ID_OBJETIVO']]
            metas_com_indicadores = [
                meta for _, meta in metas_filtradas.iterrows()
                if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
            ]

            if not metas_com_indicadores:
                return header, content, [], dbc.Alert(
                    "Não existem indicadores disponíveis para este objetivo.",
                    color="warning",
                    className="text-center p-3"
                ), []

            meta_selecionada = metas_com_indicadores[0]
            metas = [
                dbc.NavLink(
                    meta['ID_META'],
                    id={'type': 'meta-button', 'index': meta['ID_META']},
                    href="#",
                    active=meta['ID_META'] == meta_selecionada['ID_META'],
                    className="nav-link"
                ) for meta in metas_com_indicadores
            ]

            meta_description = meta_selecionada['DESC_META']
            indicadores_meta = df_indicadores[df_indicadores['ID_META'] == meta_selecionada['ID_META']]

            if not indicadores_meta.empty:
                tabs_indicadores = []
                for _, row in indicadores_meta.iterrows():
                    df_dados = load_dados_indicador_cache(row['ID_INDICADOR'])
                    tab_content = [
                        html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                    ]

                    if df_dados is not None and not df_dados.empty:
                        try:
                            # Adiciona o dropdown de variáveis se o indicador tiver VARIAVEIS = 1
                            tab_content = [
                                html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                            ]
                            
                            # Verifica se o indicador tem VARIAVEIS = 1
                            indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row['ID_INDICADOR']]
                            if not indicador_info.empty and indicador_info['VARIAVEIS'].iloc[0] == '1':
                                # Carrega as variáveis do arquivo filtro.csv
                                df_filtro_loaded = load_filtro()
                                
                                # Obtém as variáveis únicas do indicador
                                variaveis_indicador = df_dados['CODG_VAR'].unique() if 'CODG_VAR' in df_dados.columns else []
                                
                                # Filtra apenas as variáveis que existem no indicador
                                df_filtro_loaded = df_filtro_loaded[df_filtro_loaded['CODG_VAR'].isin(variaveis_indicador)]
                                
                                if not df_filtro_loaded.empty:
                                    tab_content.append(
                                        dbc.Row([
                                            dbc.Col([
                                                html.Label("Selecione a Variável:", style={'fontWeight': 'bold', 'marginBottom': '5px'}),
                                                dcc.Dropdown(
                                                    id={'type': 'var-dropdown', 'index': row['ID_INDICADOR']},
                                                    options=[
                                                        {'label': desc, 'value': cod} 
                                                        for cod, desc in zip(df_filtro_loaded['CODG_VAR'], df_filtro_loaded['DESC_VAR'])
                                                    ],
                                                    value=df_filtro_loaded['CODG_VAR'].iloc[0] if not df_filtro_loaded.empty else None,
                                                    style={'width': '70%', 'marginBottom': '20px'}
                                                )
                                            ], width=12)
                                        ])
                                    )
                            
                            grid = create_visualization(df_dados, row['ID_INDICADOR'])
                            tab_content.append(grid)
                        except Exception as e:
                            print(f"Erro ao processar dropdown de variáveis: {e}")
                            tab_content = [
                                html.P(row['DESC_INDICADOR'], className="text-justify p-3"),
                                grid
                            ]

                    tabs_indicadores.append(
                        dbc.Tab(
                            tab_content,
                            label=row['ID_INDICADOR'],
                            tab_id=f"tab-{row['ID_INDICADOR']}",
                            id={'type': 'tab-indicador', 'index': row['ID_INDICADOR']}
                        )
                    )

                indicadores_section = [
                    html.H5("Indicadores", className="mt-4 mb-3"),
                    dbc.Card(
                        dbc.CardBody(
                            dbc.Tabs(
                                children=tabs_indicadores,
                                active_tab=tabs_indicadores[0].tab_id if tabs_indicadores else None
                            )
                        ),
                        className="mt-3"
                    )
                ]
            else:
                indicadores_section = []

            return header, content, metas, meta_description, indicadores_section

        except Exception as e:
            return initial_header, dbc.Alert(
                [
                    html.H4("Erro ao processar o objetivo selecionado", className="alert-heading"),
                    html.P("Ocorreu um erro ao tentar processar o objetivo selecionado."),
                    html.Hr(),
                    html.P(f"Detalhes do erro: {str(e)}", className="mb-0")
                ],
                color="danger",
                className="text-center p-3"
            ), [], "", []

    except Exception as e:
        return initial_header, dbc.Alert(
            [
                html.H4("Erro ao processar a solicitação", className="alert-heading"),
                html.P("Ocorreu um erro ao tentar processar sua solicitação."),
                html.Hr(),
                html.P(f"Detalhes do erro: {str(e)}", className="mb-0")
            ],
            color="danger",
            className="text-center p-3"
        ), [], "", []


# Callback para carregar os dados de cada indicador
@app.callback(
    Output({'type': 'dados-indicador', 'index': ALL}, 'children'),
    [Input({'type': 'tab-indicador', 'index': ALL}, 'active')],
    prevent_initial_call=True
)
def load_dados_indicador(*args):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    triggered_id = ctx.triggered[0]['prop_id']
    if 'tab-indicador' not in triggered_id:
        raise PreventUpdate

    try:
        indicador_id = triggered_id.split('"index":"')[1].split('"')[0]
        indicador = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]

        if not indicador.empty:
            df_dados = load_dados_indicador_cache(indicador_id)
            if df_dados is not None:
                grid = create_visualization(df_dados, indicador_id)
                return [[grid]]
            else:
                return [[
                    html.P(
                        "Erro ao carregar os dados do indicador.",
                        className="text-danger"
                    )
                ]]
        else:
            return [[]]

    except Exception as e:
        print(f"Erro ao carregar dados do indicador: {e}")
        return [[]]


# Callback para atualizar o mapa coroplético quando o ano é alterado
@app.callback(
    Output({'type': 'choropleth-map', 'index': ALL}, 'figure'),
    [Input({'type': 'year-dropdown', 'index': ALL}, 'value')],
    [State({'type': 'choropleth-map', 'index': ALL}, 'figure')]
)
def update_map(selected_years, current_figures):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    triggered_id = ctx.triggered[0]['prop_id']
    if not triggered_id:
        raise PreventUpdate
    
    try:
        # Extrai o ID do indicador do triggered_id
        indicador_id = triggered_id.split('"index":"')[1].split('"')[0]
        selected_year = ctx.triggered[0]['value']
        
        # Carrega os dados do indicador
        df = load_dados_indicador_cache(indicador_id)
        if df is None:
            raise PreventUpdate
        
        # Filtra os dados para o ano selecionado
        df_ano = df[df['CODG_ANO'] == selected_year]
        
        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df_ano.columns:
            df_ano['DESC_UND_FED'] = df_ano['CODG_UND_FED'].astype(str).map(UF_NAMES)
        
        # Renomeia a coluna VLR_VAR para Valor
        df_ano = df_ano.rename(columns={'VLR_VAR': 'Valor'})
        
        # Carrega o GeoJSON
        with open('db/br_geojson.json', 'r', encoding='utf-8') as f:
            geojson = json.load(f)
        
        # Cria o novo mapa
        fig_map = px.choropleth(
            df_ano,
            geojson=geojson,
            locations='DESC_UND_FED',
            featureidkey='properties.name',
            color='Valor',
            color_continuous_scale='Viridis',
            scope="south america"
        )
        
        # Adiciona a unidade de medida ao hover do mapa
        if 'DESC_UND_MED' in df_ano.columns:
            unidade_medida = df_ano['DESC_UND_MED'].dropna().iloc[0] if not df_ano['DESC_UND_MED'].dropna().empty else ''
            if unidade_medida:
                fig_map.update_traces(
                    hovertemplate="<b>%{location}</b><br>" +
                    f"Valor: %{{z}} {unidade_medida}<extra></extra>"
                )
            else:
                fig_map.update_traces(
                    hovertemplate="<b>%{location}</b><br>" +
                    "Valor: %{z}<extra></extra>"
                )
        else:
            fig_map.update_traces(
                hovertemplate="<b>%{location}</b><br>" +
                "Valor: %{z}<extra></extra>"
            )
        
        # Ajusta o layout do mapa
        fig_map.update_geos(
            visible=False,
            showcoastlines=True,
            coastlinecolor="Black",
            showland=True,
            landcolor="white",
            showframe=False,
            center=dict(lat=-12.9598, lon=-53.2729),
            projection=dict(
                type='mercator',
                scale=2.6
            )
        )
        
        # Atualiza o layout do mapa
        fig_map.update_layout(
            xaxis=dict(
                tickfont=dict(size=12, color='black'),
                ticktext=[f"<b>{x}</b>" for x in sorted(df_ano['DESC_UND_FED'].unique())],
                tickvals=sorted(df_ano['DESC_UND_FED'].unique())
            ),
            yaxis=dict(
                tickfont=dict(size=12, color='black'),
                ticktext=[f"<b>{x}</b>" for x in sorted(df_ano['DESC_UND_FED'].unique())],
                tickvals=sorted(df_ano['DESC_UND_FED'].unique())
            ),
            coloraxis_colorbar=dict(
                title="",
                tickfont=dict(size=12, color='black')
            )
        )
        
        return [fig_map]
    except Exception as e:
        raise PreventUpdate


# Obtém a instância do servidor Flask
server = app.server

if __name__ == '__main__':
    if DEBUG:
        app.run_server(
            debug=DEBUG,
            use_reloader=USE_RELOADER,
            port=PORT,
            host=HOST,
            **DASH_CONFIG
        )
    else:
        # Em produção, o uWSGI irá usar a variável 'server'
        app.run_server(
            debug=False,
            use_reloader=False,
            port=PORT,
            host=HOST
        )
