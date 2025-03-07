import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
from config import DEBUG, USE_RELOADER, PORT, HOST

# Inicializa o aplicativo Dash com tema Bootstrap
app = dash.Dash(
    __name__, 
    external_stylesheets=[dbc.themes.MATERIA],
    assets_folder='assets',
    assets_url_path='/assets/'
)

# Define o layout do aplicativo
app.layout = dbc.Container([
    # Title
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
                                ], width=7),
                                # Imagem do IMB
                                dbc.Col([
                                    html.Img(src='/assets/img/imb720.png', 
                                            style={'width': '30%', 'height': '100%'}, 
                                            className="img-fluid")
                                ], width=5)
                            ], className="align-items-center")
                        ], width=5),
                        # Coluna do título
                        dbc.Col([
                            html.H1('Instituto Mauro Borges - ODS - Agenda 2030', 
                                   className="text-center align-middle",
                                   style={'margin': '0', 'padding': '0'})
                        ], width=7, className="d-flex align-items-center")
                    ], className="align-items-center")
                ])
            ], className="mb-4", style={'margin-top': '15px', 'margin-left': '15px', 'margin-right': '15px'})
        ])
    ]),
    
    # Card Principal
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        # Card do Menu
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Menu"),
                                dbc.CardBody([
                                    dbc.ListGroup([
                                        dbc.ListGroupItem("Item 1", href="#"),
                                        dbc.ListGroupItem("Item 2", href="#"),
                                        dbc.ListGroupItem("Item 3", href="#"),
                                    ])
                                ])
                            ])
                        ], lg=2),
                        
                        # Card do Conteúdo
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader("Conteúdo"),
                                dbc.CardBody([
                                    html.Div(id='conteudo')
                                ])
                            ])
                        ], lg=10)
                    ])
                ])
            ], className="border-0 shadow-none")
        ])
    ])
], fluid=True)

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