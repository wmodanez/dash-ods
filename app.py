from dash import html, Dash, callback_context, ALL, no_update, dash, State
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from config import DEBUG, USE_RELOADER, PORT, HOST
import pandas as pd
from functools import lru_cache
import json
import time
from dash.exceptions import PreventUpdate

def capitalize_words(text):
    return ' '.join(word.capitalize() for word in text.split())

# Inicializa o aplicativo Dash com tema Bootstrap
app = Dash(
    __name__, 
    external_stylesheets=[dbc.themes.MATERIA],
    assets_folder='assets',
    assets_url_path='/assets/'
)

# Template HTML básico
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Painel ODS</title>
        <link rel="icon" type="image/x-icon" href="/assets/favicon.ico">
        {%favicon%}
        {%css%}
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
        df = pd.read_csv('db/objetivos.csv', 
                         low_memory=False, 
                         encoding='utf-8',
                         dtype=str,
                         sep=';',  # Usa ponto e vírgula como separador
                         on_bad_lines='skip')   
    except Exception as e:
        print(f"Erro ao ler o arquivo de objetivos: {e}")
        df = pd.DataFrame()  # DataFrame vazio em caso de erro
    return df

@lru_cache(maxsize=1)
def load_metas():
    try:
        df_metas = pd.read_csv('db/metas.csv', 
                               low_memory=False, 
                               encoding='utf-8',
                               dtype=str,
                               sep=';',  # Usa ponto e vírgula como separador
                               on_bad_lines='skip')
    except Exception as e:
        print(f"Erro ao ler o arquivo de metas: {e}")
        df_metas = pd.DataFrame()  # DataFrame vazio em caso de erro
    return df_metas

@lru_cache(maxsize=1)
def load_indicadores():
    try:
        df_indicadores = pd.read_csv('db/indicadores.csv', 
                                     low_memory=False, 
                                     encoding='utf-8',
                                     dtype=str,
                                     sep=';',  # Usa ponto e vírgula como separador
                                     on_bad_lines='skip')
        df_indicadores['RBC'] = pd.to_numeric(df_indicadores['RBC'], errors='coerce')
        df_indicadores = df_indicadores.loc[df_indicadores['RBC'] == 1]  # Filtra os indicadores RBC
        return df_indicadores
    except Exception as e:
        print(f"Erro ao ler o arquivo de indicadores: {e}")
        df_indicadores = pd.DataFrame()  # DataFrame vazio em caso de erro
        return df_indicadores

# Lê os arquivos CSV
df = load_objetivos()
df_metas = load_metas()
df_indicadores = load_indicadores()

# Lê o arquivo CSV de metas
try:
    df_metas = pd.read_csv('db/metas.csv', 
                          low_memory=False, 
                          encoding='utf-8',
                          dtype=str,
                          sep=';',  # Usa ponto e vírgula como separador
                          on_bad_lines='skip')
except Exception as e:
    print(f"Erro ao ler o arquivo de metas: {e}")
    df_metas = pd.DataFrame()  # DataFrame vazio em caso de erro

# Lê o arquivo CSV de indicadores
try:
    df_indicadores = pd.read_csv('db/indicadores.csv', 
                                 low_memory=False, 
                                 encoding='utf-8',
                                 dtype=str,
                                 sep=';',  # Usa ponto e vírgula como separador
                                 on_bad_lines='skip')
    df_indicadores['RBC'] = pd.to_numeric(df_indicadores['RBC'], errors='coerce')
    df_indicadores = df_indicadores.loc[df_indicadores['RBC'] == 1]  # Filtra os indicadores RBC
except Exception as e:
    print(f"Erro ao ler o arquivo de indicadores: {e}")
    df_indicadores = pd.DataFrame()  # DataFrame vazio em caso de erro

# Define o conteúdo inicial do card
initial_header = "Selecione um objetivo"
initial_content = ""
initial_meta_description = ""
if not df.empty and 'DESC_OBJETIVO' in df.columns:
    row = df.iloc[0]
    initial_header = row['RES_OBJETIVO']
    initial_content = row['DESC_OBJETIVO']

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
                                    html.Img(src='/assets/img/sgg.png', 
                                            style={'width': '40%', 'height': '100%'}, 
                                            className="img-fluid")
                                ], width=6),
                                # Imagem do IMB
                                dbc.Col([
                                    html.Img(src='/assets/img/imb720.png', 
                                            style={'width': '30%', 'height': '100%'}, 
                                            className="img-fluid")
                                ], width=6)
                            ], className="align-items-center")
                        ], width=6),
                        # Coluna do título
                        dbc.Col([
                            html.H1('Instituto Mauro Borges - ODS - Agenda 2030', 
                                   className="text-center align-middle",
                                   style={'margin': '0', 'padding': '0'})
                        ], width=6, className="d-flex align-items-center")
                    ], className="align-items-center")
                ])
            ], className="mb-4", style={'marginTop': '15px', 'marginLeft': '15px', 'marginRight': '15px'})
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
                                                    style={'width': '100%', 'marginBottom': '10px', 'cursor': 'pointer'},
                                                    className="img-fluid",
                                                    id=f"objetivo{idx}",
                                                    n_clicks=0
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
                                dbc.CardHeader(html.H3(id='card-header', children=initial_header)),
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
                                        }
                                    ),
                                    html.P(id='meta-description', className="text-justify mt-4"),
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

# Callback para atualizar o conteúdo do card
@app.callback(
    [Output('card-header', 'children'),
     Output('card-content', 'children'),
     Output('metas-nav', 'children'),
     Output('meta-description', 'children')],
    [Input(f"objetivo{i}", "n_clicks") for i in range(len(df))] +
    [Input({'type': 'meta-button', 'index': ALL}, 'n_clicks')],
    [State({'type': 'meta-button', 'index': ALL}, 'active')],
    prevent_initial_call=False
)
def update_card_content(*args):
    ctx = callback_context
    if not ctx.triggered:
        return initial_header, initial_content, [], initial_meta_description
    
    triggered_id = ctx.triggered[0]['prop_id']
    
    # Se for um clique em uma meta
    if 'meta-button' in triggered_id:
        try:
            # Extrair o ID da meta do triggered_id de forma mais robusta
            meta_id = triggered_id.split('"index":"')[1].split('"')[0]
            # Buscar a descrição da meta
            meta_filtrada = df_metas[df_metas['ID_META'] == meta_id]
            if not meta_filtrada.empty:
                meta_desc = meta_filtrada['DESC_META'].iloc[0]
                
                # Atualizar todas as metas com a nova meta ativa
                objetivo_id = meta_filtrada['ID_OBJETIVO'].iloc[0]
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
                
                return no_update, no_update, metas_atualizadas, meta_desc
            else:
                return no_update, no_update, no_update, "Não foi possível encontrar a descrição desta meta."
        except Exception as e:
            print(f"Erro ao processar meta: {e}")
            return no_update, no_update, no_update, "Ocorreu um erro ao carregar a descrição da meta."
    
    # Se for um clique em um objetivo
    button_id = triggered_id.split('.')[0]
    if not button_id.startswith('objetivo'):
        return initial_header, initial_content, [], initial_meta_description
    
    index = int(button_id.replace('objetivo', ''))
    row = df.iloc[index]
    
    # Define o cabeçalho baseado no índice
    if index == 0:
        header = row['RES_OBJETIVO']
        metas = []  # Lista vazia para o objetivo 0
        meta_description = ""
    else:
        header = f"{row['ID_OBJETIVO']} - {row['RES_OBJETIVO']}"
        # Filtra as metas relacionadas ao objetivo selecionado
        metas_filtradas = df_metas[df_metas['ID_OBJETIVO'] == row['ID_OBJETIVO']]
        metas_com_indicadores = [
            meta for _, meta in metas_filtradas.iterrows()
            if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
        ]
        
        if metas_com_indicadores:
            # Seleciona a primeira meta como ativa
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
            
            # Define a descrição da meta selecionada
            meta_description = meta_selecionada['DESC_META']
        else:
            metas = [
                dbc.Card(
                    dbc.CardBody(
                        html.H3("Não existem indicadores que atendam os requisitos deste estudo.", 
                               className="text-center fw-bold")
                    ),
                    className="m-2",
                    style={'width': '100%'}
                )
            ]
            meta_description = ""
    
    return header, row['DESC_OBJETIVO'] if 'DESC_OBJETIVO' in row else "", metas, meta_description

# Função com cache para carregar dados do indicador
@lru_cache(maxsize=100)
def load_dados_indicador_cache(indicador_id):
    try:
        df_dados = pd.read_parquet(f'db/resultados/indicador{indicador_id.replace("Indicador ", "")}.parquet')
        return df_dados
    except Exception as e:
        print(f"Erro ao carregar dados do indicador: {e}")
        return None

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
        # Extrair o ID do indicador do triggered_id
        indicador_id = triggered_id.split('"index":"')[1].split('"')[0]
        
        # Buscar o indicador
        indicador = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
        if not indicador.empty:
            # Carregar dados do indicador usando o cache
            df_dados = load_dados_indicador_cache(indicador_id)
            if df_dados is not None:
                # Criar a tabela com os dados
                tabela = dbc.Table.from_dataframe(
                    df_dados,
                    striped=True,
                    bordered=True,
                    hover=True,
                    responsive=True,
                    className="table-sm"
                )
                # Retornar uma lista com um único elemento contendo a tabela
                return [[tabela]]
            else:
                return [[html.P("Erro ao carregar os dados do indicador.", className="text-danger")]]
        else:
            return [[]]
    except Exception as e:
        print(f"Erro ao carregar dados do indicador: {e}")
        return [[]]

# Callback para carregar os indicadores de forma assíncrona
@app.callback(
    Output('indicadores-section', 'children'),
    [Input({'type': 'meta-button', 'index': ALL}, 'n_clicks')],
    [State({'type': 'meta-button', 'index': ALL}, 'active')],
    prevent_initial_call=True
)
def load_indicadores_async(*args):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    triggered_id = ctx.triggered[0]['prop_id']
    if 'meta-button' not in triggered_id:
        raise PreventUpdate
    
    try:
        # Extrair o ID da meta do triggered_id
        meta_id = triggered_id.split('"index":"')[1].split('"')[0]
        
        # Buscar os indicadores da meta
        indicadores_meta = df_indicadores[df_indicadores['ID_META'] == meta_id]
        if not indicadores_meta.empty:
            # Iniciar carregamento assíncrono
            tabs_indicadores = []
            for idx, row in indicadores_meta.iterrows():
                # Carregar dados do indicador
                df_dados = load_dados_indicador_cache(row['ID_INDICADOR'])
                
                # Criar conteúdo da tab
                tab_content = [
                    html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                ]
                
                # Adicionar tabela se houver dados
                if df_dados is not None:
                    tabela = dbc.Table.from_dataframe(
                        df_dados,
                        striped=True,
                        bordered=True,
                        hover=True,
                        responsive=True,
                        className="table-sm"
                    )
                    tab_content.append(tabela)
                else:
                    tab_content.append(html.P("Erro ao carregar os dados do indicador.", className="text-danger"))
                
                tabs_indicadores.append(
                    dbc.Tab(
                        tab_content,
                        label=row['ID_INDICADOR'],
                        tab_id=f"tab-{row['ID_INDICADOR']}",
                        id={'type': 'tab-indicador', 'index': row['ID_INDICADOR']}
                    )
                )
            
            # Retornar o conteúdo final com as tabs
            return [
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
            return []
    except Exception as e:
        print(f"Erro ao carregar indicadores: {e}")
        return []

if __name__ == '__main__':
    app.run_server(
        debug=DEBUG,
        use_reloader=USE_RELOADER,
        port=PORT,
        host=HOST
    )