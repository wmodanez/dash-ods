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
            
        # Se não estiver no cache, carrega do arquivo
        df_dados = pd.read_parquet(
            f'db/resultados/indicador{indicador_id.replace("Indicador ", "")}.parquet'
        )
        
        # Armazena no cache
        indicadores_cache[indicador_id] = df_dados
        return df_dados
    except Exception as e:
        print(f"Erro ao carregar dados do indicador: {e}")
        return None

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
        print(f"Erro ao limpar cache: {e}")
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
                print(f"Coluna {col} não encontrada no arquivo objetivos.csv")
                return pd.DataFrame(columns=required_columns)
        return df
    except Exception as e:
        import traceback
        print(f"Erro ao ler o arquivo de objetivos: {e}")
        print(f"Traceback completo: {traceback.format_exc()}")
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
        print(f"Erro ao ler o arquivo de metas: {e}")
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
        print(f"Erro ao ler o arquivo de indicadores: {e}")
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
        print(f"Erro ao ler o arquivo de sugestões: {e}")
        return pd.DataFrame()


# Carrega os dados
df = load_objetivos()

df_metas = load_metas()
df_indicadores = load_indicadores()

# Define o conteúdo inicial do card
if not df.empty:
    row_objetivo_0 = df.iloc[(0,)]
    initial_header = row_objetivo_0['RES_OBJETIVO']
    initial_content = row_objetivo_0['DESC_OBJETIVO']
else:
    print("DataFrame de objetivos está vazio, usando mensagem de erro...")
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
        print(f"Erro ao preparar metas iniciais: {e}")
        meta_inicial = None
        initial_meta_description = ""
else:
    print("DataFrames vazios, não é possível preparar metas iniciais")
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

            if df_dados is not None:
                grid = create_ag_grid(df_dados)
                tab_content.append(grid)
            else:
                tab_content.append(
                    html.P(
                        "Erro ao carregar os dados do indicador.",
                        className="text-danger"
                    )
                )

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


def create_ag_grid(df, indicador_id=None):
    """Cria um grid AG Grid com os dados do DataFrame"""
    if df is None or df.empty:
        return html.Div("Nenhum dado disponível")
    
    # Carrega as sugestões de visualização
    df_sugestoes = load_sugestoes_visualizacao()
    
    # Se tiver um indicador específico, tenta encontrar sua primeira sugestão
    if indicador_id and not df_sugestoes.empty:
        sugestao = df_sugestoes[df_sugestoes['ID_INDICADOR'] == indicador_id].iloc[(0,)]
        if sugestao is not None:
            # Cria o gráfico baseado na sugestão
            config = json.loads(sugestao['config'].replace("'", '"'))
            
            # Converte todas as colunas numéricas
            for col in df.columns:
                if col.startswith(('ID', 'CODG')) or col == 'VLR_VAR':
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Tratamento genérico para dados anuais
            if 'CODG_ANO' in df.columns and 'VLR_VAR' in df.columns:
                # Garante que o DataFrame está ordenado por ano
                df = df.sort_values('CODG_ANO')
                
                # Se tiver dados por unidade federativa, mantém essa informação
                if 'CODG_UND_FED' in df.columns:
                    # Mantém todas as colunas numéricas durante o agrupamento
                    colunas_agregacao = {col: 'mean' for col in df.columns if col.startswith(('ID', 'CODG')) or col == 'VLR_VAR'}
                    df = df.groupby(['CODG_ANO', 'CODG_UND_FED'], as_index=False).agg(colunas_agregacao)
                else:
                    # Mantém todas as colunas numéricas durante o agrupamento
                    colunas_agregacao = {col: 'mean' for col in df.columns if col.startswith(('ID', 'CODG')) or col == 'VLR_VAR'}
                    df = df.groupby('CODG_ANO', as_index=False).agg(colunas_agregacao)
            
            if sugestao['tipo'] == 'bar':
                fig = px.bar(df, **config)
            elif sugestao['tipo'] == 'line':
                fig = px.line(df, **config)
            elif sugestao['tipo'] == 'histogram':
                # Remove nbinsx do config se existir e usa nbins
                if 'nbinsx' in config:
                    nbins = config.pop('nbinsx')
                    fig = px.histogram(df, **config, nbins=nbins)
                else:
                    fig = px.histogram(df, **config)
            elif sugestao['tipo'] == 'box':
                fig = px.box(df, **config)
            elif sugestao['tipo'] == 'scatter':
                fig = px.scatter(df, **config)
            elif sugestao['tipo'] == 'bubble':
                fig = px.scatter(df, **config)
            else:
                fig = px.bar(df, **config)  # Fallback para gráfico de barras
            
            fig.update_layout(
                title=sugestao['titulo'],
                xaxis_title=config.get('x', ''),
                yaxis_title=config.get('y', ''),
                showlegend=True
            )
            
            return html.Div([
                html.H5(sugestao['descricao'], className="mb-3"),
                dcc.Graph(figure=fig)
            ])
    
    # Se não encontrar sugestão ou não tiver indicador, mostra a tabela
    columnDefs = [
        {"field": col, "headerName": capitalize_words(col), "sortable": True, "filter": True}
        for col in df.columns
    ]
    
    defaultColDef = {
        "flex": 1,
        "minWidth": 100,
        "resizable": True,
    }
    
    grid = dag.AgGrid(
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
    
    return grid


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
                    meta_desc = meta_filtrada['DESC_META'].iloc[(0,)]
                    objetivo_id = meta_filtrada['ID_OBJETIVO'].iloc[(0,)]
                    metas_filtradas = df_metas[df_metas['ID_OBJETIVO'] == objetivo_id]
                    metas_com_indicadores = [
                        meta for _, meta in metas_filtradas.iterrows()
                        if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
                    ]

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
                                html.P(
                                    row['DESC_INDICADOR'],
                                    className="text-justify p-3"
                                )
                            ]

                            if df_dados is not None:
                                grid = create_ag_grid(df_dados, row['ID_INDICADOR'])
                                tab_content.append(grid)
                            else:
                                tab_content.append(
                                    html.P(
                                        "Erro ao carregar os dados do indicador.",
                                        className="text-danger"
                                    )
                                )

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
                    return no_update, no_update, no_update, "Não foi possível encontrar a descrição desta meta.", []
            except Exception as e:
                print(f"Erro ao processar meta: {e}")
                return no_update, no_update, no_update, "Ocorreu um erro ao carregar a descrição da meta.", []

        # Se for um clique em um objetivo
        button_id = triggered_id.split('.')[0]
        if not button_id.startswith('objetivo'):
            return initial_header, initial_content, [], initial_meta_description, []

        try:
            index = int(button_id.replace('objetivo', ''))
            if index >= len(df):
                return initial_header, "Objetivo não encontrado.", [], "", []
            
            row = df.iloc[index]
            if 'DESC_OBJETIVO' not in row or 'RES_OBJETIVO' not in row or 'ID_OBJETIVO' not in row:
                return initial_header, "Dados do objetivo estão incompletos.", [], "", []

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

            if not metas_com_indicadores and index != 0:
                metas = [
                    dbc.Card(
                        dbc.CardBody(
                            html.P(
                                "Não existem indicadores que atendam os requisitos deste estudo.",
                                className="text-center fw-bold"
                            )
                        ),
                        className="m-2",
                        style={'width': '100%'}
                    )
                ]
                return header, content, metas, "", []

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

                    if df_dados is not None:
                        grid = create_ag_grid(df_dados, row['ID_INDICADOR'])
                        tab_content.append(grid)
                    else:
                        tab_content.append(
                            html.P(
                                "Erro ao carregar os dados do indicador.",
                                className="text-danger"
                            )
                        )

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
            print(f"Erro ao processar objetivo: {e}")
            return initial_header, "Erro ao processar o objetivo selecionado.", [], "", []

    except Exception as e:
        print(f"Erro geral no callback: {e}")
        return initial_header, "Ocorreu um erro ao processar a solicitação.", [], "", []


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
                grid = create_ag_grid(df_dados)
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
