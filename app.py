import dash
from dash import html, dcc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
from config import DEBUG, USE_RELOADER, PORT, HOST
import pandas as pd
import base64

# Inicializa o aplicativo Dash com tema Bootstrap
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.MATERIA],
    assets_folder='assets',
    assets_url_path='/assets/'
)

# Lê o arquivo CSV
try:
    df = pd.read_csv('db/objetivos.csv', 
                     low_memory=False, 
                     encoding='utf-8',
                     dtype=str,
                     sep=';',  # Usa ponto e vírgula como separador
                     on_bad_lines='skip')   
except Exception as e:
    print(f"Erro ao ler o arquivo CSV: {e}")
    df = pd.DataFrame()  # DataFrame vazio em caso de erro

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
                                dbc.CardHeader(html.H3(id='card-header', children=initial_header)),
                                dbc.CardBody([
                                    html.P(id='card-content', children=initial_content)
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
     Output('card-content', 'children')],
    [Input(f"objetivo{i}", "n_clicks") for i in range(len(df))],
    prevent_initial_call=True
)
def update_card_content(*args):
    ctx = dash.callback_context
    if not ctx.triggered:
        return "Selecione um objetivo", ""
    
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    if not button_id:
        return "Selecione um objetivo", ""
    
    index = int(button_id.replace('objetivo', ''))
    row = df.iloc[index]
    
    # Define o cabeçalho baseado no índice
    if index == 0:
        header = row['RES_OBJETIVO']
    else:
        header = f"{row['ID_OBJETIVO']} - {row['RES_OBJETIVO']}"
    
    return header, row['DESC_OBJETIVO']

# Configura o favicon
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

if __name__ == '__main__':
    app.run_server(
        debug=DEBUG,
        use_reloader=USE_RELOADER,
        port=PORT,
        host=HOST
    )