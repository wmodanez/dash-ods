from dash import html, Dash, callback_context
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from config import DEBUG, USE_RELOADER, PORT, HOST
import pandas as pd
from functools import lru_cache

# Adicione esta função após as importações
def capitalize_words(text):
    return ' '.join(word.capitalize() for word in text.split())

# Inicializa o aplicativo Dash com tema Bootstrap
app = Dash(
    __name__, 
    external_stylesheets=[dbc.themes.MATERIA],
    assets_folder='assets',
    assets_url_path='/assets/'
)

# Adicione o CSS personalizado
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Painel ODS</title>
        <link rel="icon" type="image/x-icon" href="/assets/favicon.ico">
        <style>
            .meta-button {
                background-color: #0d6efd !important;
                color: white !important;
                border: none !important;
                padding: 0.375rem 0.75rem !important;
                border-radius: 0.25rem !important;
                text-decoration: none !important;
                transition: all 0.2s ease-in-out !important;
                text-transform: capitalize !important;
            }
            .meta-button:hover {
                background-color: #0b5ed7 !important;
                color: white !important;
            }
        </style>
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
if not df.empty:
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
            ], className="mb-4", style={'margin-top': '15px', 'margin-left': '15px', 'margin-right': '15px'})
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
                                                    style={'width': '100%', 'margin-bottom': '10px', 'cursor': 'pointer'},
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
                                dbc.CardHeader(html.H2(id='card-header', children=initial_header)),
                                dbc.CardBody([
                                    html.P(id='card-content', children=initial_content),
                                    html.Hr(),
                                    dbc.Nav(id='metas-nav', pills=True, className="d-flex flex-wrap gap-2")
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
     Output('metas-nav', 'children')],  # Novo output para as metas
    [Input(f"objetivo{i}", "n_clicks") for i in range(len(df))],
    prevent_initial_call=True
)
def update_card_content(*args):
    ctx = callback_context
    if not ctx.triggered:
        return "Selecione um objetivo", "", []
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not button_id:
        return "Selecione um objetivo", "", []
    
    index = int(button_id.replace('objetivo', ''))
    row = df.iloc[index]
    
    # Define o cabeçalho baseado no índice
    if index == 0:
        header = row['RES_OBJETIVO']
        metas = []  # Lista vazia para o objetivo 0
    else:
        header = f"{row['ID_OBJETIVO']} - {row['RES_OBJETIVO']}"
        # Filtra as metas relacionadas ao objetivo selecionado
        metas = [
            dbc.NavItem(
            dbc.NavLink(
                meta['ID_META'],  # Retorna o texto original
                id=f"meta_{meta['ID_META']}",
                n_clicks=0,
                className="meta-button m-1",  # Usa a classe meta-button
                style={
                'width': 'auto',
                'background-color': '#0d6efd',
                'color': 'white',
                'border': 'none',
                'padding': '0.375rem 0.75rem',
                'border-radius': '0.25rem',
                'text-decoration': 'none',
                'transition': 'all 0.2s ease-in-out',
                ':hover': {
                    'background-color': '#0b5ed7',
                    'color': 'white'
                }
                }
            )
            ) for _, meta in df_metas[df_metas['ID_OBJETIVO'] == row['ID_OBJETIVO']].iterrows()
            if not df_indicadores[(df_indicadores['ID_META'] == meta['ID_META'])].empty
        ]
        
        if not metas:
            metas = [
            dbc.Card(
                dbc.CardBody(
                html.H3("Não existem indicadores que atendam os requisitos deste estudo.", className="text-center fw-bold")
                ),
                className="m-2",
                style={'width': '100%'}
            )
            ]
    
    return header, row['DESC_OBJETIVO'], metas

if __name__ == '__main__':
    app.run_server(
        debug=DEBUG,
        use_reloader=USE_RELOADER,
        port=PORT,
        host=HOST
    )