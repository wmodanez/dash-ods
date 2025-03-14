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
            
        # Define os caminhos dos arquivos
        arquivo_parquet = f'db/resultados/indicador{indicador_id.replace("Indicador ", "")}.parquet'
        arquivo_metadados = f'db/resultados/indicador{indicador_id.replace("Indicador ", "")}_metadata.json'
        
        # Carrega os metadados primeiro
        try:
            with open(arquivo_metadados, 'r', encoding='utf-8') as f:
                metadados = json.load(f)
        except Exception as e:
            print(f"Erro ao carregar metadados do indicador {indicador_id}: {e}")
            metadados = None
        
        # Carrega o arquivo parquet
        df_dados = pd.read_parquet(arquivo_parquet)
        
        # Se tiver metadados, aplica as configurações
        if metadados:
            # Configura os tipos das colunas conforme os metadados
            for coluna, tipo in metadados['colunas'].items():
                if coluna in df_dados.columns:
                    try:
                        if coluna == 'CODG_ANO':
                            df_dados[coluna] = df_dados[coluna].astype(str)
                        elif 'Int64' in tipo:
                            df_dados[coluna] = pd.to_numeric(df_dados[coluna], errors='coerce').astype('Int64')
                        elif 'float' in tipo:
                            df_dados[coluna] = pd.to_numeric(df_dados[coluna], errors='coerce')
                        elif 'category' in tipo:
                            df_dados[coluna] = df_dados[coluna].astype('category')
                    except Exception as e:
                        print(f"Erro ao converter coluna {coluna} para tipo {tipo}: {e}")
        
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
                grid = create_visualization(df_dados, row['ID_INDICADOR'])
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
        return html.Div("Nenhum dado disponível")
 
    # Garante que os dados estão ordenados por ano se existir
    if 'CODG_ANO' in df.columns:
        df = df.sort_values('CODG_ANO')
    
    # Substitui os códigos das UFs pelos nomes completos
    if 'CODG_UND_FED' in df.columns:
        df['DESC_UND_FED'] = df['CODG_UND_FED'].astype(str).map(UF_NAMES)
        # Remove a coluna CODG_UND_FED para evitar confusão
        if 'DESC_UND_FED' in df.columns:
            df = df.drop('CODG_UND_FED', axis=1)
    
    # Carrega as sugestões de visualização
    df_sugestoes = load_sugestoes_visualizacao()
    
    # Se tiver um indicador específico, tenta encontrar suas sugestões
    if indicador_id and not df_sugestoes.empty:
        sugestoes_indicador = df_sugestoes[df_sugestoes['ID_INDICADOR'] == indicador_id]
        if not sugestoes_indicador.empty:
            # Usa a primeira sugestão disponível
            sugestao = sugestoes_indicador.iloc[0]
            
            # Configura o gráfico de linha
            config = {
                'x': 'CODG_ANO',
                'y': 'VLR_VAR',
                'color': 'DESC_UND_FED' if 'DESC_UND_FED' in df.columns else None
            }
            
            # Converte apenas o campo VLR_VAR para numérico (os outros já foram convertidos)
            if 'VLR_VAR' in df.columns:
                df['VLR_VAR'] = pd.to_numeric(df['VLR_VAR'], errors='coerce')
            
            # Tratamento genérico para dados anuais
            if 'CODG_ANO' in df.columns and 'VLR_VAR' in df.columns:
                # Se tiver dados por unidade federativa, mantém essa informação
                if 'DESC_UND_FED' in df.columns:
                    # Usa DESC_UND_FED para o agrupamento sem agregação
                    df = df.groupby(['CODG_ANO', 'DESC_UND_FED'], as_index=False).first()
                else:
                    # Mantém todas as colunas durante o agrupamento sem agregação
                    df = df.groupby('CODG_ANO', as_index=False).first()
            
            # Atualiza os labels dos eixos com as descrições do COLUMN_NAMES
            config['labels'] = {
                'x': COLUMN_NAMES.get('CODG_ANO', 'Ano'),
                'y': COLUMN_NAMES.get('VLR_VAR', 'Valor'),
                'color': COLUMN_NAMES.get('DESC_UND_FED', 'Unidade Federativa') if 'DESC_UND_FED' in df.columns else None
            }
            
            # Sempre usa gráfico de linha primeiro
            fig_line = px.line(df, **config)
            
            # Aplica suavização nas linhas
            fig_line.update_traces(line_shape='spline')
            
            # Cria o gráfico de barras com a mesma configuração
            fig_bar = px.bar(df, **config)
            
            # Carrega o GeoJSON do Brasil
            with open('db/br_geojson.json', 'r', encoding='utf-8') as f:
                geojson = json.load(f)
            
            # Cria o dropdown de anos
            anos = sorted(df['CODG_ANO'].unique())
            dropdown = dcc.Dropdown(
                id={'type': 'year-dropdown', 'index': indicador_id},
                options=[{'label': ano, 'value': ano} for ano in anos],
                value=anos[-1],  # Seleciona o último ano por padrão
                style={'width': '200px', 'margin': '10px'}
            )
            
            # Cria o mapa coroplético inicial com o último ano
            df_ultimo_ano = df[df['CODG_ANO'] == anos[-1]]
            fig_map = px.choropleth(
                df_ultimo_ano,
                geojson=geojson,
                locations='DESC_UND_FED',
                featureidkey='properties.name',
                color='VLR_VAR',
                color_continuous_scale='Viridis',
                scope="south america"
            )
            
            # Adiciona a unidade de medida ao hover do mapa
            if 'DESC_UND_MED' in df_ultimo_ano.columns:
                unidade_medida = df_ultimo_ano['DESC_UND_MED'].dropna().iloc[0] if not df_ultimo_ano['DESC_UND_MED'].dropna().empty else ''
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
                fitbounds="locations",
                visible=False,
                showcoastlines=True,
                coastlinecolor="Black",
                showland=True,
                landcolor="white",
                showframe=False
            )
            
            # Aplica o layout padrão e adiciona títulos específicos
            layout = DEFAULT_LAYOUT.copy()
            layout.update({
                'xaxis_title': config['labels']['x'],
                'yaxis_title': config['labels']['y'],
                'legend': dict(
                    title="<b>Unidade Federativa</b>",
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=1.05,
                    orientation="v"
                )
            })
            
            # Atualiza os nomes das colunas no hover template
            hovertemplate = []
            x_label = config['labels']['x']
            hovertemplate.append(f"{x_label}: %{{x}}")
            y_label = config['labels']['y']
            
            # Verifica se as colunas de unidade de medida existem
            if 'DESC_UND_MED' in df.columns:
                # Pega o primeiro valor não nulo da coluna DESC_UND_MED
                unidade_medida = df['DESC_UND_MED'].dropna().iloc[0] if not df['DESC_UND_MED'].dropna().empty else ''
                if unidade_medida:
                    hovertemplate.append(f"{y_label}: %{{y}} {unidade_medida}")
                else:
                    hovertemplate.append(f"{y_label}: %{{y}}")
            else:
                hovertemplate.append(f"{y_label}: %{{y}}")
            
            if hovertemplate:
                fig_line.update_traces(
                    hovertemplate="<br>".join(hovertemplate) + "<extra></extra>"
                )
                fig_bar.update_traces(
                    hovertemplate="<br>".join(hovertemplate) + "<extra></extra>"
                )
            
            fig_line.update_layout(layout)
            fig_bar.update_layout(layout)
            
            # Remove linhas de grade e linhas do zero para todos os tipos de gráficos
            fig_line.update_xaxes(showgrid=False, zeroline=False)
            fig_line.update_yaxes(showgrid=False, zeroline=False)
            fig_bar.update_xaxes(showgrid=False, zeroline=False)
            fig_bar.update_yaxes(showgrid=False, zeroline=False)
            
            # Destaca Goiás com cor específica
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
                        dropdown,
                        dcc.Graph(
                            id={'type': 'choropleth-map', 'index': indicador_id},
                            figure=fig_map,
                            style={'height': '600px'}  # Ajusta a altura do mapa
                        )
                    ], style={'width': '40%', 'display': 'inline-block', 'vertical-align': 'top', 'paddingLeft': '20px'})
                ])
            ])
    
    # Se não encontrar sugestão ou não tiver indicador, mostra a tabela
    columnDefs = []
    for col in df.columns:
        if col == 'CODG_UND_FED':
            # Adiciona a coluna DESC_UND_FED em vez de CODG_UND_FED
            columnDefs.append({
                "field": "DESC_UND_FED",
                "headerName": "Unidade Federativa",
                "sortable": True,
                "filter": True
            })
        else:
            columnDefs.append({
                "field": col,
                "headerName": COLUMN_NAMES.get(col, capitalize_words(col)),
                "sortable": True,
                "filter": True
            })
    
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
                                grid = create_visualization(df_dados, row['ID_INDICADOR'])
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
                        grid = create_visualization(df_dados, row['ID_INDICADOR'])
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
        
        # Carrega o GeoJSON
        with open('db/br_geojson.json', 'r', encoding='utf-8') as f:
            geojson = json.load(f)
        
        # Cria o novo mapa
        fig_map = px.choropleth(
            df_ano,
            geojson=geojson,
            locations='DESC_UND_FED',
            featureidkey='properties.name',
            color='VLR_VAR',
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
            fitbounds="locations",
            visible=False,
            showcoastlines=True,
            coastlinecolor="Black",
            showland=True,
            landcolor="white",
            showframe=False
        )
        
        return [fig_map]
    except Exception as e:
        print(f"Erro ao atualizar o mapa: {e}")
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
