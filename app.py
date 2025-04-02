import dash
from dash import html, dcc, Input, Output, State, callback, dash_table
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime
import numpy as np
from dash.exceptions import PreventUpdate
from dash import callback_context
import plotly.io as pio
from config import *
import secrets
from dotenv import load_dotenv
from functools import lru_cache
from flask import session, redirect, send_from_directory, request, jsonify
import bcrypt
from generate_password import generate_password_hash, generate_secret_key, update_env_file, check_password
from flask_cors import CORS

# Carrega as variáveis de ambiente primeiro
load_dotenv()

# Configuração do tema do Plotly
pio.templates.default = "plotly_white"

import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import ALL, MATCH, Dash, callback_context, dcc, html, no_update
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from config import (
    DEBUG, USE_RELOADER, PORT, HOST, DASH_CONFIG, SERVER_CONFIG,
    MAINTENANCE_PASSWORD
)
from constants import COLUMN_NAMES, UF_NAMES

# Variável global para controle do modo de manutenção
MAINTENANCE_MODE = os.getenv('MAINTENANCE_MODE', 'false').lower() == 'true'

def maintenance_middleware():
    """Middleware para verificar se o sistema está em manutenção"""
    global MAINTENANCE_MODE
    if MAINTENANCE_MODE and request.remote_addr not in ['127.0.0.1']:
        # Se a requisição for para um arquivo estático ou arquivos do dash, serve normalmente
        if request.path.startswith('/assets/') or '_dash-component-suites' in request.path:
            return None
        # Se for a página principal, serve a página de manutenção
        return send_from_directory('assets', 'maintenance.html')
    return None


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
    serve_locally=True,
    **DASH_CONFIG  # Aplica as configurações de performance
)

# Registra o middleware de manutenção
app.server.before_request(maintenance_middleware)

# Configurações de cache
for key, value in SERVER_CONFIG.items():
    app.server.config[key] = value

# Configura a chave secreta do Flask
app.server.secret_key = SERVER_CONFIG['SECRET_KEY']

# Configura o Flask para servir arquivos estáticos
@app.server.route('/assets/<path:path>')
def serve_static(path):
    return send_from_directory('assets', path)

# Adicionando CORS para permitir as requisições de log
CORS(app.server)

# Endpoint para logging de erros do cliente
@app.server.route('/log', methods=['POST'])
def log_message():
    # Verifica se o servidor está em modo debug
    if not app.server.debug:
        return '', 204 # Retorna "No Content" se debug estiver desativado
    
    try:
        data = request.get_json(force=True)
        print("\n====================== ERRO DO NAVEGADOR ======================")
        print(f"Mensagem: {data.get('message', 'Sem mensagem')}")
        print(f"Stack: {data.get('stack', 'Sem stack')}")
        print("===============================================================\n")
        return jsonify({"status": "logged", "success": True})
    except Exception as e:
        print(f"Erro ao processar log do cliente: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Rota para servir arquivos do dash
@app.server.route('/_dash-component-suites/<path:path>')
def serve_dash_files(path):
    return send_from_directory('_dash-component-suites', path)


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
        <script>
        (function() {
            // Função para enviar log para o servidor
            function enviarLog(mensagem, stack) {
                console.log("Enviando log para o servidor:", mensagem);
                
                fetch('/log', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        message: typeof mensagem === 'object' ? JSON.stringify(mensagem) : String(mensagem),
                        stack: stack || new Error().stack
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Falha na requisição: ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("Log enviado com sucesso:", data);
                })
                .catch(err => {
                    console.log("Erro ao enviar log:", err);
                });
            }
            
            // Sobrescreve o console.error original
            const originalConsoleError = console.error;
            console.error = function() {
                // Captura os argumentos
                const args = Array.from(arguments);
                const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
                
                // Envia para o servidor
                enviarLog(message, new Error().stack);
                
                // Chama o console.error original
                originalConsoleError.apply(console, arguments);
            };
            
            // Captura erros não tratados
            window.addEventListener('error', function(event) {
                enviarLog(event.message, event.error ? event.error.stack : null);
                return false;
            });
            
            // Captura promessas rejeitadas não tratadas
            window.addEventListener('unhandledrejection', function(event) {
                enviarLog(
                    'Promessa rejeitada não tratada: ' + (event.reason ? event.reason.toString() : 'Razão desconhecida'),
                    event.reason && event.reason.stack ? event.reason.stack : null
                );
            });
            
        })();
        </script>
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
def load_variavel():
    try:
        # Tenta ler o arquivo com diferentes configurações
        try:
            df_variavel = pd.read_csv(
                'db/variavel.csv',
                low_memory=False,
                encoding='utf-8',
                dtype=str,
                sep=';'
            )
        except:
            # Se falhar, tenta ler com vírgula como separador
            df_variavel = pd.read_csv(
                'db/variavel.csv',
                low_memory=False,
                encoding='utf-8',
                dtype=str,
                sep=','
            )
        
        # Verifica se as colunas necessárias existem
        if len(df_variavel.columns) == 1 and ',' in df_variavel.columns[0]:
            # Se as colunas estiverem juntas, separa-as
            df_variavel = pd.DataFrame([x.split(',') for x in df_variavel[df_variavel.columns[0]]])
            # Pega apenas as colunas necessárias (CODG_VAR e DESC_VAR)
            if len(df_variavel.columns) >= 2:
                df_variavel = df_variavel.iloc[:, [0, 1]]
                df_variavel.columns = ['CODG_VAR', 'DESC_VAR']
        
        # Garante que as colunas estejam presentes e com os nomes corretos
        if 'CODG_VAR' not in df_variavel.columns or 'DESC_VAR' not in df_variavel.columns:
            return pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])
        
        # Remove espaços extras e aspas das colunas
        df_variavel['CODG_VAR'] = df_variavel['CODG_VAR'].str.strip().str.strip('"')
        df_variavel['DESC_VAR'] = df_variavel['DESC_VAR'].str.strip().str.strip('"')
        
        return df_variavel
    except Exception as e:
        return pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])


# Carrega os dados
df = load_objetivos()
df_metas = load_metas()
df_indicadores = load_indicadores()
df_unidade_medida = load_unidade_medida()
df_variavel = load_variavel()

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
            tab_content = []

            if df_dados is not None and not df_dados.empty:
                try:
                    # Verifica se o indicador tem VARIAVEIS = 1
                    indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row['ID_INDICADOR']]
                    if not indicador_info.empty and indicador_info['VARIAVEIS'].iloc[0] == '1':
                        # Inicializa tab_content vazio para indicadores com variáveis
                        tab_content = []
                        
                        # Carrega as variáveis do arquivo variavel.csv
                        df_variavel_loaded = load_variavel()
                        
                        # Obtém as variáveis únicas do indicador
                        variaveis_indicador = df_dados['CODG_VAR'].unique() if 'CODG_VAR' in df_dados.columns else []
                        
                        # Filtra apenas as variáveis que existem no indicador
                        df_variavel_loaded = df_variavel_loaded[df_variavel_loaded['CODG_VAR'].isin(variaveis_indicador)]
                        
                        # Obtém o valor inicial do dropdown
                        valor_inicial = df_variavel_loaded['CODG_VAR'].iloc[0] if not df_variavel_loaded.empty else None

                        if not df_variavel_loaded.empty:
                            tab_content.append(
                                html.Div([
                                    html.Label("Selecione uma Variável:", 
                                        style={
                                            'fontWeight': 'bold',
                                            'display': 'block',
                                            'marginBottom': '5px'
                                        },
                                        id={'type': 'var-label', 'index': row['ID_INDICADOR']}
                                    ),
                                    dcc.Dropdown(
                                        id={'type': 'var-dropdown', 'index': row['ID_INDICADOR']},
                                        options=[
                                            {'label': desc, 'value': cod} 
                                            for cod, desc in zip(df_variavel_loaded['CODG_VAR'], df_variavel_loaded['DESC_VAR'])
                                        ],
                                        value=valor_inicial,
                                        style={'width': '70%'}
                                    )
                                ], style={'paddingBottom': '20px', 'paddingTop': '20px'}, id={'type': 'var-dropdown-container', 'index': row['ID_INDICADOR']})
                            )

                        # Cria a visualização com o valor inicial do dropdown
                        grid = create_visualization(df_dados, row['ID_INDICADOR'], valor_inicial)
                        tab_content.append(grid)
                    else:
                        # Se não tiver variáveis, mostra a descrição do indicador
                        tab_content = [
                            html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                        ]
                    
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
    ),
    'xaxis_automargin': False, # Desativa auto-margin para eixo X
    'yaxis_automargin': False  # Desativa auto-margin para eixo Y
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
                                'Instituto Mauro Borges - ODS - Agenda ',
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
                                    html.Div(id='card-content', children=initial_content),
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
                                    html.Div(
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


def create_visualization(df, indicador_id=None, selected_var=None):
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

        # Cria uma cópia do DataFrame para evitar modificações no original
        df = df.copy()
        
        # Se o indicador tem variáveis, filtra pelo valor selecionado ou primeiro valor disponível
        if 'CODG_VAR' in df.columns:
            if selected_var:
                df['CODG_VAR'] = df['CODG_VAR'].astype(str).str.strip()
                selected_var = str(selected_var).strip()
                df = df[df['CODG_VAR'] == selected_var]
            else:
                # Pega o primeiro valor disponível
                primeiro_valor = df['CODG_VAR'].iloc[0]
                df = df[df['CODG_VAR'] == primeiro_valor]

        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df.columns:
            df['DESC_UND_FED'] = df['CODG_UND_FED'].astype(str).map(UF_NAMES)
            df = df.dropna(subset=['DESC_UND_FED'])
        
        # Adiciona as descrições da variável e unidade de medida antes do agrupamento
        if 'CODG_VAR' in df.columns and not df_variavel.empty:
            df['CODG_VAR'] = df['CODG_VAR'].astype(str)
            df_variavel['CODG_VAR'] = df_variavel['CODG_VAR'].astype(str)
            df = df.merge(df_variavel[['CODG_VAR', 'DESC_VAR']], on='CODG_VAR', how='left')
            df['DESC_VAR'] = df['DESC_VAR'].fillna('Descrição não disponível')
        else:
            df['DESC_VAR'] = 'Descrição não disponível'
        
        if 'CODG_UND_MED' in df.columns and not df_unidade_medida.empty:
            df['CODG_UND_MED'] = df['CODG_UND_MED'].astype(str)
            df_unidade_medida['CODG_UND_MED'] = df_unidade_medida['CODG_UND_MED'].astype(str)
            df = df.merge(df_unidade_medida[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
            df['DESC_UND_MED'] = df['DESC_UND_MED'].fillna('Unidade não disponível')
        else:
            df['DESC_UND_MED'] = 'Unidade não disponível'
        
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
                    "maxWidth": None,
                    "resizable": True,
                    "wrapText": True,
                    "autoHeight": True,
                    "suppressSizeToFit": False,
                    "cellStyle": {"whiteSpace": "normal"},
                    "cellClass": "wrap-text"
                })
        
        defaultColDef = {
            "flex": 1,
            "minWidth": 100,
            "maxWidth": None,
            "resizable": True,
            "wrapText": True,
            "autoHeight": True,
            "suppressSizeToFit": False,
            "cellStyle": {"whiteSpace": "normal"},
            "cellClass": "wrap-text"
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
                                    "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                                    "domLayout": "autoHeight",  # Alterado de "normal"
                                    "suppressMovableColumns": True,
                                    "animateRows": True,
                                    "suppressColumnVirtualisation": True
                                    # Remova autoSizeAllColumns
                                },
                                style={"width": "calc(100% - 40px)", "marginLeft": "20px"}, # Removido height: 100%
                            )
                        ])
                    
                    # ==============================================
                    # GRÁFICO DE LINHA - Evolução temporal dos valores
                    # ==============================================
                    # Configura o gráfico de linha
                    config = {
                        'x': 'CODG_ANO',  # Voltando para CODG_ANO no eixo X
                        'y': 'VLR_VAR',
                        'color': 'DESC_UND_FED'  # Voltando para DESC_UND_FED para colorir por estado
                    }
                    
                    # Tratamento para dados anuais
                    if 'DESC_UND_FED' in df.columns:
                        df = df.groupby(['CODG_ANO', 'DESC_UND_FED'], as_index=False).agg({
                            'VLR_VAR': 'first',
                            'DESC_UND_MED': 'first',
                            'DESC_VAR': 'first'
                        })
                    else:
                        df = df.groupby('CODG_ANO', as_index=False).agg({
                            'VLR_VAR': 'first',
                            'DESC_UND_MED': 'first',
                            'DESC_VAR': 'first'
                        })
                    
                    # Atualiza os labels dos eixos
                    config['labels'] = {
                        'x': "",  # Removendo o label do eixo X
                        'y': "",
                        'color': f"<b>{COLUMN_NAMES.get('DESC_UND_FED', 'Unidade Federativa')}</b>"  # Voltando para UF
                    }
                    
                    # Cria os gráficos
                    fig_line = px.line(df, **config)
                    
                    # Cria um dicionário para mapear cada estado com sua unidade de medida
                    estado_unidade = df.groupby('DESC_UND_FED')['DESC_UND_MED'].first().to_dict()
                    
                    # Atualiza cada traço individualmente para garantir que o customdata corresponda ao estado correto
                    for trace in fig_line.data:
                        estado = trace.name
                        trace.update(
                            line_shape='spline',
                            mode='lines+markers',
                            marker=dict(
                                size=14,
                                symbol='circle',
                                line=dict(width=2, color='white')
                            ),
                            hovertemplate="<b>" + estado + "</b><br>" +
                                        "Ano: %{x}<br>" +
                                        "Valor: %{y}<br>" +
                                        "Unidade de Medida: " + estado_unidade[estado] + "<extra></extra>"
                        )
                        if estado == 'Goiás':
                            trace.line = dict(color='#229846', width=6)
                            trace.name = '<b>Goiás</b>'
                    
                    # Atualiza o layout do gráfico de linha
                    fig_line.update_layout(
                        xaxis=dict(
                            tickangle=45,  # Rotaciona os rótulos para melhor visualização
                            tickfont=dict(size=12)
                        )
                    )
                    
                    # ==============================================
                    # GRÁFICO DE BARRAS - Comparação entre UFs
                    # ==============================================
                    # Cria o gráfico de barras
                    fig_bar = px.bar(
                        df,
                        x='CODG_ANO',
                        y='VLR_VAR',
                        color='DESC_UND_FED',
                        labels={
                            'DESC_UND_FED': 'Unidade Federativa',
                            'VLR_VAR': 'Valor',
                            'CODG_ANO': ""  # Removendo o label do eixo X
                        }
                    )
                    
                    # Atualiza o layout do gráfico de barras
                    fig_bar.update_layout(
                        showlegend=True,
                        xaxis=dict(
                            tickfont=dict(size=12, color='black'),
                            tickangle=45,
                            ticktext=[f"<b>{x}</b>" for x in sorted(df['CODG_ANO'].unique())],
                            tickvals=sorted(df['CODG_ANO'].unique())
                        ),
                        yaxis=dict(
                            tickfont=dict(size=12, color='black'),
                            showticklabels=False  # Remove os valores do eixo Y
                        ),
                        margin=dict(b=100)  # Margem inferior para os rótulos rotacionados
                    )
                    
                    # Atualiza o hover do gráfico de barras
                    for trace in fig_bar.data:
                        estado = trace.name
                        trace.update(
                            hovertemplate="<b>" + estado + "</b><br>" +
                                        "Ano: %{x}<br>" +
                                        "Valor: %{y}<br>" +
                                        "Unidade de Medida: " + estado_unidade[estado] + "<extra></extra>"
                        )
                        if estado == 'Goiás':
                            trace.marker.color = '#229846'
                            trace.marker.line.width = 6
                            trace.name = '<b>Goiás</b>'
                    
                    # ==============================================
                    # MAPA COROPLÉTICO - Visualização geográfica
                    # ==============================================
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
                        coastlinecolor="White",
                        showland=True,
                        landcolor="white",
                        showframe=False,
                        center=dict(lat=-12.9598, lon=-53.2729),
                        projection=dict(
                            type='mercator',
                            scale=2.6
                        )
                    )
                    
                    # Atualiza o layout do mapa e adiciona linhas de divisão brancas e mais grossas
                    fig_map.update_traces(
                        marker_line_color='white',
                        marker_line_width=1,
                        hovertemplate="<b>%{location}</b><br>" +
                                    "Valor: %{z}<br>" +
                                    "Unidade de Medida: " + df['DESC_UND_MED'].iloc[0] + "<extra></extra>"
                    )
                    
                    # Atualiza o layout do mapa
                    fig_map.update_layout(
                        margin=dict(r=0, l=0, t=0, b=0),
                        coloraxis_colorbar=dict(
                            title=None,
                            tickfont=dict(size=12, color='black')
                        )
                    )
                    
                    # ==============================================
                    # TABELA DE DADOS - Visualização detalhada
                    # ==============================================
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
                    fig_bar.update_xaxes(showgrid=False, zeroline=False)
                    
                    # Destaca Goiás
                    if 'DESC_UND_FED' in df.columns:
                        for trace in fig_line.data:
                            if hasattr(trace, 'name') and trace.name == 'Goiás':
                                trace.line = dict(color='#229846', width=6)
                                trace.name = '<b>Goiás</b>'
                        for trace in fig_bar.data:
                            if hasattr(trace, 'name') and trace.name == 'Goiás':
                                trace.marker.color = '#229846'
                                trace.marker.line.width = 6
                                trace.name = '<b>Goiás</b>'
                    
                    # ==============================================
                    # GRÁFICO DE PIZZA - Distribuição percentual
                    # ==============================================
                    # Verifica se há menos de 5 anos de dados
                    anos_unicos = sorted(df['CODG_ANO'].unique())
                    mostrar_pizza = len(anos_unicos) < 5
                    
                    # Cria o gráfico de pizza apenas se houver menos de 5 anos
                    if mostrar_pizza:
                        # Cria o gráfico de pizza
                        fig_pie = px.pie(
                            df,
                            values='VLR_VAR',
                            names='DESC_UND_FED',
                            labels={
                                'DESC_UND_FED': 'Unidade Federativa',
                                'VLR_VAR': 'Valor'
                            }
                        )
                        
                        # Atualiza o layout do gráfico de pizza
                        fig_pie.update_layout(
                            showlegend=True,
                            legend=dict(
                                title="Unidade Federativa",
                                yanchor="top",
                                y=0.99,
                                xanchor="left",
                                x=1.05,
                                orientation="v"
                            ),
                            margin=dict(r=150)  # Margem à direita para acomodar a legenda
                        )
                        
                        # Atualiza o hover do gráfico de pizza
                        fig_pie.update_traces(
                            hovertemplate="<b>%{label}</b><br>" +
                                        "Valor: %{value}<br>" +
                                        "Percentual: %{percent:.1%}<br>" +
                                        "Unidade de Medida: " + df['DESC_UND_MED'].iloc[0] + "<extra></extra>",
                            textinfo="label+value+percent",
                            texttemplate="<b>%{label}</b><br>%{value}<br>%{percent:.1%}",
                            textposition="outside",
                            showlegend=False,
                            hoverinfo="skip"
                        )
                        
                        # Destaca Goiás no gráfico de pizza
                        for trace in fig_pie.data:
                            if trace.name == 'Goiás':
                                trace.marker = dict(color='#229846')
                                trace.name = '<b>Goiás</b>'
                    
                    # Adiciona o gráfico de pizza à estrutura, mas mantém oculto se não houver menos de 5 anos
                    return html.Div([
                        html.Div(
                            id={'type': 'graph-container', 'index': indicador_id},
                            children=[
                                dbc.Row([
                                    # Coluna da esquerda com os gráficos
                                    dbc.Col([
                                        # Primeira linha com os gráficos (linha/barra ou pizza)
                                        dbc.Row([
                                            dbc.Col([
                                                # Container para gráficos de linha e barra
                                                html.Div([
                                                    dcc.Graph(figure=fig_line, style={'height': '370px'}),
                                                    dcc.Graph(figure=fig_bar, style={'height': '370px'})
                                                ], style={
                                                    'display': 'none' if mostrar_pizza else 'block',
                                                    'border': '1px solid #dee2e6',
                                                    'borderRadius': '4px',
                                                    'padding': '15px',
                                                    'height': '800px',
                                                    'marginBottom': '0px'
                                                }),
                                                # Container para gráfico de pizza
                                                html.Div([
                                                    html.Label("Ano", 
                                                        style={
                                                            'fontWeight': 'bold',
                                                            'marginBottom': '5px',
                                                            'display': 'block'
                                                        }
                                                    ),
                                                    dcc.Dropdown(
                                                        id={'type': 'pie-year-dropdown', 'index': indicador_id},
                                                        options=[{'label': ano, 'value': ano} for ano in anos_unicos],
                                                        value=anos_unicos[-1] if anos_unicos else None,
                                                        style={'width': '200px', 'marginBottom': '10px'}
                                                    ),
                                                    dcc.Graph(
                                                        figure=fig_pie if mostrar_pizza else go.Figure(), # Passa figura vazia em vez de None
                                                        id={'type': 'pie-chart', 'index': indicador_id},
                                                        style={'height': '700px'}
                                                    )
                                                ], style={
                                                    'display': 'block' if mostrar_pizza else 'none',
                                                    'border': '1px solid #dee2e6',
                                                    'borderRadius': '4px',
                                                    'padding': '15px',
                                                    'height': '800px'
                                                })
                                            ], width=12)
                                        ], className="mb-4")
                                    ], width=7),
                                    # Coluna da direita com o mapa e dropdown
                                    dbc.Col([
                                        # Container do mapa com dropdown
                                        html.Div([
                                            html.Label("Ano:", 
                                                style={
                                                    'fontWeight': 'bold',
                                                    'marginBottom': '5px',
                                                    'display': 'block'
                                                }
                                            ),
                                            dcc.Dropdown(
                                                id={'type': 'year-dropdown', 'index': indicador_id},
                                                options=[{'label': ano, 'value': ano} for ano in sorted(df['CODG_ANO'].unique())],
                                                value=sorted(df['CODG_ANO'].unique())[-1],
                                                style={'width': '200px', 'marginBottom': '10px'}
                                            ),
                                            dcc.Graph(
                                                id={'type': 'choropleth-map', 'index': indicador_id},
                                                figure=fig_map,
                                                style={
                                                    'height': '700px'
                                                }
                                            )
                                        ], style={
                                            'border': '1px solid #dee2e6',
                                            'borderRadius': '4px',
                                            'padding': '15px',
                                            'height': '800px',
                                            'marginBottom': '0px'
                                        })
                                    ], width=5)
                                ])
                            ]
                        ),
                        html.Div([
                            html.H5("Dados Detalhados", className="mt-4 mb-3", style={'marginLeft': '20px'}),
                            dag.AgGrid(
                                rowData=df.sort_values(['DESC_UND_FED', 'CODG_ANO', 'DESC_VAR']).to_dict('records'),
                                columnDefs=columnDefs,
                                defaultColDef=defaultColDef,
                                dashGridOptions={
                                    "pagination": True,
                                    "paginationPageSize": 10,
                                    "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                                    "domLayout": "autoHeight",  # Alterado de "normal"
                                    "suppressMovableColumns": True,
                                    "animateRows": True,
                                    "suppressColumnVirtualisation": True
                                    # Remova autoSizeAllColumns
                                },
                                style={"width": "calc(100% - 40px)", "marginLeft": "20px"}, # Removido height: 100%
                            )
                        ], style={
                            'width': '100%', 
                            'marginTop': '20px',
                            'border': '1px solid #dee2e6',
                            'borderRadius': '4px',
                            'padding': '15px'
                        })
                    ])
                except Exception as e:
                    print(f"Erro ao atualizar gráficos: {e}")
                    raise PreventUpdate
        
        # Se não encontrar sugestão ou não tiver indicador, mostra apenas a tabela
        return dag.AgGrid(
            rowData=df.to_dict('records'),
            columnDefs=columnDefs,
            defaultColDef=defaultColDef,
            dashGridOptions={
                "pagination": True,
                "paginationPageSize": 10,
                "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                "domLayout": "autoHeight",  # Alterado de "normal"
                "suppressMovableColumns": True,
                "animateRows": True,
                "suppressColumnVirtualisation": True
                # Remova autoSizeAllColumns
            },
            style={"width": "100%"}, # Removido height: 100%
        )
    except Exception as e:
        print(f"Erro ao atualizar gráficos: {e}")
        raise PreventUpdate


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
                            tab_content = []

                            if df_dados is not None and not df_dados.empty:
                                try:
                                    # Verifica se o indicador tem VARIAVEIS = 1
                                    indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row['ID_INDICADOR']]
                                    if not indicador_info.empty and indicador_info['VARIAVEIS'].iloc[0] == '1':
                                        # Inicializa tab_content vazio para indicadores com variáveis
                                        tab_content = []
                                        
                                        # Carrega as variáveis do arquivo variavel.csv
                                        df_variavel_loaded = load_variavel()
                                        
                                        # Obtém as variáveis únicas do indicador
                                        variaveis_indicador = df_dados['CODG_VAR'].unique() if 'CODG_VAR' in df_dados.columns else []
                                        
                                        # Filtra apenas as variáveis que existem no indicador
                                        df_variavel_loaded = df_variavel_loaded[df_variavel_loaded['CODG_VAR'].isin(variaveis_indicador)]
                                        
                                        # Obtém o valor inicial do dropdown
                                        valor_inicial = df_variavel_loaded['CODG_VAR'].iloc[0] if not df_variavel_loaded.empty else None

                                        if not df_variavel_loaded.empty:
                                            tab_content.append(
                                                html.Div([
                                                    html.Label("Selecione uma Variável:", 
                                                        style={
                                                            'fontWeight': 'bold',
                                                            'display': 'block',
                                                            'marginBottom': '5px'
                                                        },
                                                        id={'type': 'var-label', 'index': row['ID_INDICADOR']}
                                                    ),
                                                    dcc.Dropdown(
                                                        id={'type': 'var-dropdown', 'index': row['ID_INDICADOR']},
                                                        options=[
                                                            {'label': desc, 'value': cod} 
                                                            for cod, desc in zip(df_variavel_loaded['CODG_VAR'], df_variavel_loaded['DESC_VAR'])
                                                        ],
                                                        value=valor_inicial,
                                                        style={'width': '70%'}
                                                    )
                                                ], style={'paddingBottom': '20px', 'paddingTop': '20px'}, id={'type': 'var-dropdown-container', 'index': row['ID_INDICADOR']})
                                            )

                                        # Cria a visualização com o valor inicial do dropdown
                                        grid = create_visualization(df_dados, row['ID_INDICADOR'], valor_inicial)
                                        tab_content.append(grid)
                                    else:
                                        # Se não tiver variáveis, mostra a descrição do indicador
                                        tab_content = [
                                            html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                                        ]
                                    
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
                    f"Erro ao processar meta: {str(e)}",
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
                    tab_content = []

                    if df_dados is not None and not df_dados.empty:
                        try:
                            # Verifica se o indicador tem VARIAVEIS = 1
                            indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row['ID_INDICADOR']]
                            if not indicador_info.empty and indicador_info['VARIAVEIS'].iloc[0] == '1':
                                # Inicializa tab_content vazio para indicadores com variáveis
                                tab_content = []
                                
                                # Carrega as variáveis do arquivo variavel.csv
                                df_variavel_loaded = load_variavel()
                                
                                # Obtém as variáveis únicas do indicador
                                variaveis_indicador = df_dados['CODG_VAR'].unique() if 'CODG_VAR' in df_dados.columns else []
                                
                                # Filtra apenas as variáveis que existem no indicador
                                df_variavel_loaded = df_variavel_loaded[df_variavel_loaded['CODG_VAR'].isin(variaveis_indicador)]
                                
                                # Obtém o valor inicial do dropdown
                                valor_inicial = df_variavel_loaded['CODG_VAR'].iloc[0] if not df_variavel_loaded.empty else None

                                if not df_variavel_loaded.empty:
                                    tab_content.append(
                                        html.Div([
                                            html.Label("Selecione uma Variável:", 
                                                style={
                                                    'fontWeight': 'bold',
                                                    'display': 'block',
                                                    'marginBottom': '5px'
                                                },
                                                id={'type': 'var-label', 'index': row['ID_INDICADOR']}
                                            ),
                                            dcc.Dropdown(
                                                id={'type': 'var-dropdown', 'index': row['ID_INDICADOR']},
                                                options=[
                                                    {'label': desc, 'value': cod} 
                                                    for cod, desc in zip(df_variavel_loaded['CODG_VAR'], df_variavel_loaded['DESC_VAR'])
                                                ],
                                                value=valor_inicial,
                                                style={'width': '70%'}
                                            )
                                        ], style={'paddingBottom': '20px', 'paddingTop': '20px'}, id={'type': 'var-dropdown-container', 'index': row['ID_INDICADOR']})
                                    )

                                # Cria a visualização com o valor inicial do dropdown
                                grid = create_visualization(df_dados, row['ID_INDICADOR'], valor_inicial)
                                tab_content.append(grid)
                            else:
                                # Se não tiver variáveis, mostra a descrição do indicador
                                tab_content = [
                                    html.P(row['DESC_INDICADOR'], className="text-justify p-3")
                                ]
                                
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
                f"Erro ao processar objetivo: {str(e)}",
                color="danger",
                className="text-center p-3"
            ), [], "", []

    except Exception as e:
        return initial_header, dbc.Alert(
            f"Erro ao processar solicitação: {str(e)}",
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
    if not ctx.triggered or not ctx.outputs_list:
        raise PreventUpdate
    
    triggered_id_str = ctx.triggered[0]['prop_id']
    if not triggered_id_str:
        raise PreventUpdate
    
    indicador_id = "Desconhecido" # Inicializa com valor padrão
    try:
        # Parse o ID do dropdown que acionou o callback
        # Usar rsplit para remover apenas o sufixo .value
        triggered_prop_id = json.loads(triggered_id_str.rsplit('.', 1)[0])
        indicador_id = triggered_prop_id['index']
        selected_year = ctx.triggered[0]['value']
        
        # Carrega os dados do indicador
        df = load_dados_indicador_cache(indicador_id)
        if df is None or df.empty:
            raise PreventUpdate
        
        # Filtra os dados para o ano selecionado e cria uma cópia explícita
        df_ano = df[df['CODG_ANO'] == selected_year].copy()
        
        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df_ano.columns:
            df_ano['DESC_UND_FED'] = df_ano['CODG_UND_FED'].astype(str).map(UF_NAMES)
            df_ano = df_ano.dropna(subset=['DESC_UND_FED'])
        
        if df_ano.empty:
             # Se não houver dados para o ano/UF, retorna um mapa vazio ou uma mensagem
             # (Opcional: criar uma figura vazia ou com aviso)
             # Por agora, vamos prevenir a atualização para este mapa específico
             # Encontra o índice do mapa correspondente
             target_output_index = -1
             for i, output_spec in enumerate(ctx.outputs_list):
                 if isinstance(output_spec['id'], dict) and output_spec['id'].get('index') == indicador_id:
                     target_output_index = i
                     break
             
             output_list = [no_update] * len(ctx.outputs_list)
             if target_output_index != -1:
                 # Poderia retornar um go.Figure() vazio aqui se quisesse limpar o mapa
                 output_list[target_output_index] = no_update 
             return output_list

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
            color_continuous_scale='Greens_r',
            scope="south america"
        )
        
        # Ajusta o layout do mapa
        fig_map.update_geos(
            visible=False,
            showcoastlines=True,
            coastlinecolor="White",
            showland=True,
            landcolor="white",
            showframe=False,
            center=dict(lat=-12.9598, lon=-53.2729),
            projection=dict(
                type='mercator',
                scale=2.6
            )
        )
        
        # Adiciona a unidade de medida ao hover do mapa
        if 'DESC_UND_MED' in df_ano.columns:
            unidade_medida = df_ano['DESC_UND_MED'].dropna().iloc[0] if not df_ano['DESC_UND_MED'].dropna().empty else ''
            fig_map.update_traces(
                marker_line_color='white',
                marker_line_width=1,
                hovertemplate="<b>%{location}</b><br>" +
                            f"Valor: %{{z}}" + (f" {unidade_medida}" if unidade_medida else "") + "<extra></extra>"
            )
        else:
            fig_map.update_traces(
                marker_line_color='white',
                marker_line_width=1,
                hovertemplate="<b>%{location}</b><br>" +
                            "Valor: %{z}<extra></extra>"
            )
        
        # Atualiza o layout do mapa
        fig_map.update_layout(
            margin=dict(r=0, l=0, t=0, b=0),
            coloraxis_colorbar=dict(
                title=None,
                tickfont=dict(size=12, color='black')
            )
        )
        
        # Prepara a lista de saída
        output_list = [no_update] * len(ctx.outputs_list)
        
        # Encontra o índice do output correspondente ao dropdown acionado
        target_output_index = -1
        for i, output_spec in enumerate(ctx.outputs_list):
            # Verifica se 'id' é um dict e contém 'index'
            if isinstance(output_spec['id'], dict) and output_spec['id'].get('index') == indicador_id:
                target_output_index = i
                break
                
        # Se encontrou o índice correspondente, atualiza a figura
        if target_output_index != -1:
            output_list[target_output_index] = fig_map
            
        return output_list
        
    except Exception as e:
        print(f"Erro ao atualizar mapa para indicador {indicador_id}: {e}") # Mensagem mais específica
        # Retorna no_update para todas as saídas em caso de erro
        return [no_update] * len(ctx.outputs_list)


# Callback para atualizar os gráficos quando a variável é alterada
@app.callback(
    Output({'type': 'graph-container', 'index': MATCH}, 'children'),
    [Input({'type': 'var-dropdown', 'index': MATCH}, 'value')],
    [State({'type': 'var-dropdown', 'index': MATCH}, 'id')],
    prevent_initial_call=True
)
def update_graphs(selected_var, dropdown_id):
    if not selected_var:
        raise PreventUpdate
    
    try:
        # Extrai o ID do indicador
        indicador_id = dropdown_id['index']
        
        # Carrega os dados do indicador
        df = load_dados_indicador_cache(indicador_id)
        if df is None or df.empty:
            print("DataFrame vazio ou None após carregamento")
            raise PreventUpdate
        
        # Cria uma cópia do DataFrame para evitar modificações no original
        df = df.copy()
        
        # Filtra por variável
        if 'CODG_VAR' in df.columns:
            df['CODG_VAR'] = df['CODG_VAR'].astype(str).str.strip()
            selected_var = str(selected_var).strip()
            df = df[df['CODG_VAR'] == selected_var]
            
            if df.empty:
                return html.Div([
                    dbc.Alert(
                        "Nenhum dado disponível para a variável selecionada.",
                        color="warning",
                        className="text-center p-3"
                    )
                ])
        
        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df.columns:
            df['DESC_UND_FED'] = df['CODG_UND_FED'].astype(str).map(UF_NAMES)
            df = df.dropna(subset=['DESC_UND_FED'])
        
        # Adiciona as descrições da variável e unidade de medida antes do agrupamento
        if 'CODG_VAR' in df.columns and not df_variavel.empty:
            df['CODG_VAR'] = df['CODG_VAR'].astype(str)
            df_variavel['CODG_VAR'] = df_variavel['CODG_VAR'].astype(str)
            df = df.merge(df_variavel[['CODG_VAR', 'DESC_VAR']], on='CODG_VAR', how='left')
            df['DESC_VAR'] = df['DESC_VAR'].fillna('Descrição não disponível')
        else:
            df['DESC_VAR'] = 'Descrição não disponível'
        
        if 'CODG_UND_MED' in df.columns and not df_unidade_medida.empty:
            df['CODG_UND_MED'] = df['CODG_UND_MED'].astype(str)
            df_unidade_medida['CODG_UND_MED'] = df_unidade_medida['CODG_UND_MED'].astype(str)
            df = df.merge(df_unidade_medida[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
            df['DESC_UND_MED'] = df['DESC_UND_MED'].fillna('Unidade não disponível')
        else:
            df['DESC_UND_MED'] = 'Unidade não disponível'
        
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
                    "maxWidth": None,
                    "resizable": True,
                    "wrapText": True,
                    "autoHeight": True,
                    "suppressSizeToFit": False,
                    "cellStyle": {"whiteSpace": "normal"},
                    "cellClass": "wrap-text"
                })
        
        defaultColDef = {
            "flex": 1,
            "minWidth": 100,
            "maxWidth": None,
            "resizable": True,
            "wrapText": True,
            "autoHeight": True,
            "suppressSizeToFit": False,
            "cellStyle": {"whiteSpace": "normal"},
            "cellClass": "wrap-text"
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
                                    "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                                    "domLayout": "autoHeight",  # Alterado de "normal"
                                    "suppressMovableColumns": True,
                                    "animateRows": True,
                                    "suppressColumnVirtualisation": True
                                    # Remova autoSizeAllColumns
                                },
                                style={"width": "calc(100% - 40px)", "marginLeft": "20px"}, # Removido height: 100%
                            )
                        ])
                    
                    # ==============================================
                    # GRÁFICO DE LINHA - Evolução temporal dos valores
                    # ==============================================
                    # Configura o gráfico de linha
                    config = {
                        'x': 'CODG_ANO',  # Voltando para CODG_ANO no eixo X
                        'y': 'VLR_VAR',
                        'color': 'DESC_UND_FED'  # Voltando para DESC_UND_FED para colorir por estado
                    }
                    
                    # Tratamento para dados anuais
                    if 'DESC_UND_FED' in df.columns:
                        df = df.groupby(['CODG_ANO', 'DESC_UND_FED'], as_index=False).agg({
                            'VLR_VAR': 'first',
                            'DESC_UND_MED': 'first',
                            'DESC_VAR': 'first'
                        })
                    else:
                        df = df.groupby('CODG_ANO', as_index=False).agg({
                            'VLR_VAR': 'first',
                            'DESC_UND_MED': 'first',
                            'DESC_VAR': 'first'
                        })
                    
                    # Atualiza os labels dos eixos
                    config['labels'] = {
                        'x': "",  # Removendo o label do eixo X
                        'y': "",
                        'color': f"<b>{COLUMN_NAMES.get('DESC_UND_FED', 'Unidade Federativa')}</b>"  # Voltando para UF
                    }
                    
                    # Cria os gráficos
                    fig_line = px.line(df, **config)
                    
                    # Cria um dicionário para mapear cada estado com sua unidade de medida
                    estado_unidade = df.groupby('DESC_UND_FED')['DESC_UND_MED'].first().to_dict()
                    
                    # Atualiza cada traço individualmente para garantir que o customdata corresponda ao estado correto
                    for trace in fig_line.data:
                        estado = trace.name
                        trace.update(
                            line_shape='spline',
                            mode='lines+markers',
                            marker=dict(
                                size=14,
                                symbol='circle',
                                line=dict(width=2, color='white')
                            ),
                            hovertemplate="<b>" + estado + "</b><br>" +
                                        "Ano: %{x}<br>" +
                                        "Valor: %{y}<br>" +
                                        "Unidade de Medida: " + estado_unidade[estado] + "<extra></extra>"
                        )
                        if estado == 'Goiás':
                            trace.line = dict(color='#229846', width=6)
                            trace.name = '<b>Goiás</b>'
                    
                    # Atualiza o layout do gráfico de linha
                    fig_line.update_layout(
                        xaxis=dict(
                            tickangle=45,  # Rotaciona os rótulos para melhor visualização
                            tickfont=dict(size=12)
                        )
                    )
                    
                    # ==============================================
                    # GRÁFICO DE BARRAS - Comparação entre UFs
                    # ==============================================
                    # Cria o gráfico de barras
                    fig_bar = px.bar(
                        df,
                        x='CODG_ANO',
                        y='VLR_VAR',
                        color='DESC_UND_FED',
                        labels={
                            'DESC_UND_FED': 'Unidade Federativa',
                            'VLR_VAR': 'Valor',
                            'CODG_ANO': ""  # Removendo o label do eixo X
                        }
                    )
                    
                    # Atualiza o layout do gráfico de barras
                    fig_bar.update_layout(
                        showlegend=True,
                        xaxis=dict(
                            tickfont=dict(size=12, color='black'),
                            tickangle=45,
                            ticktext=[f"<b>{x}</b>" for x in sorted(df['CODG_ANO'].unique())],
                            tickvals=sorted(df['CODG_ANO'].unique())
                        ),
                        yaxis=dict(
                            tickfont=dict(size=12, color='black'),
                            showticklabels=False  # Remove os valores do eixo Y
                        ),
                        margin=dict(b=100)  # Margem inferior para os rótulos rotacionados
                    )
                    
                    # Atualiza o hover do gráfico de barras
                    for trace in fig_bar.data:
                        estado = trace.name
                        trace.update(
                            hovertemplate="<b>" + estado + "</b><br>" +
                                        "Ano: %{x}<br>" +
                                        "Valor: %{y}<br>" +
                                        "Unidade de Medida: " + estado_unidade[estado] + "<extra></extra>"
                        )
                        if estado == 'Goiás':
                            trace.marker.color = '#229846'
                            trace.marker.line.width = 6
                            trace.name = '<b>Goiás</b>'
                    
                    # ==============================================
                    # MAPA COROPLÉTICO - Visualização geográfica
                    # ==============================================
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
                        coastlinecolor="White",
                        showland=True,
                        landcolor="white",
                        showframe=False,
                        center=dict(lat=-12.9598, lon=-53.2729),
                        projection=dict(
                            type='mercator',
                            scale=2.6
                        )
                    )
                    
                    # Atualiza o layout do mapa e adiciona linhas de divisão brancas e mais grossas
                    fig_map.update_traces(
                        marker_line_color='white',
                        marker_line_width=1,
                        hovertemplate="<b>%{location}</b><br>" +
                                    "Valor: %{z}<br>" +
                                    "Unidade de Medida: " + df['DESC_UND_MED'].iloc[0] + "<extra></extra>"
                    )
                    
                    # Atualiza o layout do mapa
                    fig_map.update_layout(
                        margin=dict(r=0, l=0, t=0, b=0),
                        coloraxis_colorbar=dict(
                            title=None,
                            tickfont=dict(size=12, color='black')
                        )
                    )
                    
                    # ==============================================
                    # TABELA DE DADOS - Visualização detalhada
                    # ==============================================
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
                    fig_bar.update_xaxes(showgrid=False, zeroline=False)
                    
                    # Destaca Goiás
                    if 'DESC_UND_FED' in df.columns:
                        for trace in fig_line.data:
                            if hasattr(trace, 'name') and trace.name == 'Goiás':
                                trace.line = dict(color='#229846', width=6)
                                trace.name = '<b>Goiás</b>'
                        for trace in fig_bar.data:
                            if hasattr(trace, 'name') and trace.name == 'Goiás':
                                trace.marker.color = '#229846'
                                trace.marker.line.width = 6
                                trace.name = '<b>Goiás</b>'
                    
                    # ==============================================
                    # GRÁFICO DE PIZZA - Distribuição percentual
                    # ==============================================
                    # Verifica se há menos de 5 anos de dados
                    anos_unicos = sorted(df['CODG_ANO'].unique())
                    mostrar_pizza = len(anos_unicos) < 5
                    
                    # Cria o gráfico de pizza apenas se houver menos de 5 anos
                    if mostrar_pizza:
                        # Cria o gráfico de pizza
                        fig_pie = px.pie(
                            df,
                            values='VLR_VAR',
                            names='DESC_UND_FED',
                            labels={
                                'DESC_UND_FED': 'Unidade Federativa',
                                'VLR_VAR': 'Valor'
                            }
                        )
                        
                        # Atualiza o layout do gráfico de pizza
                        fig_pie.update_layout(
                            showlegend=True,
                            legend=dict(
                                title="Unidade Federativa",
                                yanchor="top",
                                y=0.99,
                                xanchor="left",
                                x=1.05,
                                orientation="v"
                            ),
                            margin=dict(r=150)  # Margem à direita para acomodar a legenda
                        )
                        
                        # Atualiza o hover do gráfico de pizza
                        fig_pie.update_traces(
                            hovertemplate="<b>%{label}</b><br>" +
                                        "Valor: %{value}<br>" +
                                        "Percentual: %{percent:.1%}<br>" +
                                        "Unidade de Medida: " + df['DESC_UND_MED'].iloc[0] + "<extra></extra>",
                            textinfo="label+value+percent",
                            texttemplate="<b>%{label}</b><br>%{value}<br>%{percent:.1%}",
                            textposition="outside",
                            showlegend=False,
                            hoverinfo="skip"
                        )
                        
                        # Destaca Goiás no gráfico de pizza
                        for trace in fig_pie.data:
                            if trace.name == 'Goiás':
                                trace.marker = dict(color='#229846')
                                trace.name = '<b>Goiás</b>'
                    
                    # Adiciona o gráfico de pizza à estrutura, mas mantém oculto se não houver menos de 5 anos
                    return html.Div([
                        html.Div(
                            id={'type': 'graph-container', 'index': indicador_id},
                            children=[
                                dbc.Row([
                                    # Coluna da esquerda com os gráficos
                                    dbc.Col([
                                        # Primeira linha com os gráficos (linha/barra ou pizza)
                                        dbc.Row([
                                            dbc.Col([
                                                # Container para gráficos de linha e barra
                                                html.Div([
                                                    dcc.Graph(figure=fig_line, style={'height': '370px'}),
                                                    dcc.Graph(figure=fig_bar, style={'height': '370px'})
                                                ], style={
                                                    'display': 'none' if mostrar_pizza else 'block',
                                                    'border': '1px solid #dee2e6',
                                                    'borderRadius': '4px',
                                                    'padding': '15px',
                                                    'height': '800px',
                                                    'marginBottom': '0px'
                                                }),
                                                # Container para gráfico de pizza
                                                html.Div([
                                                    html.Label("Ano", 
                                                        style={
                                                            'fontWeight': 'bold',
                                                            'marginBottom': '5px',
                                                            'display': 'block'
                                                        }
                                                    ),
                                                    dcc.Dropdown(
                                                        id={'type': 'pie-year-dropdown', 'index': indicador_id},
                                                        options=[{'label': ano, 'value': ano} for ano in anos_unicos],
                                                        value=anos_unicos[-1] if anos_unicos else None,
                                                        style={'width': '200px', 'marginBottom': '10px'}
                                                    ),
                                                    dcc.Graph(
                                                        figure=fig_pie if mostrar_pizza else go.Figure(), # Passa figura vazia em vez de None
                                                        id={'type': 'pie-chart', 'index': indicador_id},
                                                        style={'height': '700px'}
                                                    )
                                                ], style={
                                                    'display': 'block' if mostrar_pizza else 'none',
                                                    'border': '1px solid #dee2e6',
                                                    'borderRadius': '4px',
                                                    'padding': '15px',
                                                    'height': '800px'
                                                })
                                            ], width=12)
                                        ], className="mb-4")
                                    ], width=7),
                                    # Coluna da direita com o mapa e dropdown
                                    dbc.Col([
                                        # Container do mapa com dropdown
                                        html.Div([
                                            html.Label("Ano:", 
                                                style={
                                                    'fontWeight': 'bold',
                                                    'marginBottom': '5px',
                                                    'display': 'block'
                                                }
                                            ),
                                            dcc.Dropdown(
                                                id={'type': 'year-dropdown', 'index': indicador_id},
                                                options=[{'label': ano, 'value': ano} for ano in sorted(df['CODG_ANO'].unique())],
                                                value=sorted(df['CODG_ANO'].unique())[-1],
                                                style={'width': '200px', 'marginBottom': '10px'}
                                            ),
                                            dcc.Graph(
                                                id={'type': 'choropleth-map', 'index': indicador_id},
                                                figure=fig_map,
                                                style={
                                                    'height': '700px'
                                                }
                                            )
                                        ], style={
                                            'border': '1px solid #dee2e6',
                                            'borderRadius': '4px',
                                            'padding': '15px',
                                            'height': '800px',
                                            'marginBottom': '0px'
                                        })
                                    ], width=5)
                                ])
                            ]
                        ),
                        html.Div([
                            html.H5("Dados Detalhados", className="mt-4 mb-3", style={'marginLeft': '20px'}),
                            dag.AgGrid(
                                rowData=df.sort_values(['DESC_UND_FED', 'CODG_ANO', 'DESC_VAR']).to_dict('records'),
                                columnDefs=columnDefs,
                                defaultColDef=defaultColDef,
                                dashGridOptions={
                                    "pagination": True,
                                    "paginationPageSize": 10,
                                    "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                                    "domLayout": "autoHeight",  # Alterado de "normal"
                                    "suppressMovableColumns": True,
                                    "animateRows": True,
                                    "suppressColumnVirtualisation": True
                                    # Remova autoSizeAllColumns
                                },
                                style={"width": "calc(100% - 40px)", "marginLeft": "20px"}, # Removido height: 100%
                            )
                        ], style={
                            'width': '100%', 
                            'marginTop': '20px',
                            'border': '1px solid #dee2e6',
                            'borderRadius': '4px',
                            'padding': '15px'
                        })
                    ])
                except Exception as e:
                    print(f"Erro ao atualizar gráficos: {e}")
                    raise PreventUpdate
        
        # Se não encontrar sugestão ou não tiver indicador, mostra apenas a tabela
        return dag.AgGrid(
            rowData=df.to_dict('records'),
            columnDefs=columnDefs,
            defaultColDef=defaultColDef,
            dashGridOptions={
                "pagination": True,
                "paginationPageSize": 10,
                "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                "domLayout": "autoHeight",  # Alterado de "normal"
                "suppressMovableColumns": True,
                "animateRows": True,
                "suppressColumnVirtualisation": True
                # Remova autoSizeAllColumns
            },
            style={"width": "100%"}, # Removido height: 100%
        )
    except Exception as e:
        print(f"Erro ao atualizar gráficos: {e}")
        raise PreventUpdate


# Callback para controlar a visibilidade do label baseado na existência de variáveis
@app.callback(
    Output({'type': 'var-label', 'index': MATCH}, 'style'),
    Input({'type': 'var-dropdown', 'index': MATCH}, 'options'),
    prevent_initial_call=True
)
def update_label_visibility(options):
    if not options:
        return {'display': 'none'}
    return {
        'fontWeight': 'bold',
        'display': 'block',
        'marginBottom': '5px'
    }


# Callback para atualizar o gráfico de pizza quando o ano é alterado
@app.callback(
    Output({'type': 'pie-chart', 'index': MATCH}, 'figure'),
    [Input({'type': 'pie-year-dropdown', 'index': MATCH}, 'value')],
    [State({'type': 'pie-year-dropdown', 'index': MATCH}, 'id')],
    prevent_initial_call=True
)
def update_pie_chart(selected_year, dropdown_id):
    if not selected_year:
        raise PreventUpdate
    
    try:
        # Extrai o ID do indicador
        indicador_id = dropdown_id['index']
        
        # Carrega os dados do indicador
        df = load_dados_indicador_cache(indicador_id)
        if df is None or df.empty:
            raise PreventUpdate
        
        # Adiciona as descrições da unidade de medida antes do filtro
        if 'CODG_UND_MED' in df.columns and not df_unidade_medida.empty:
            df['CODG_UND_MED'] = df['CODG_UND_MED'].astype(str)
            df_unidade_medida['CODG_UND_MED'] = df_unidade_medida['CODG_UND_MED'].astype(str)
            df = df.merge(df_unidade_medida[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
            df['DESC_UND_MED'] = df['DESC_UND_MED'].fillna('Unidade não disponível')
        else:
            df['DESC_UND_MED'] = 'Unidade não disponível'
        
        # Filtra os dados para o ano selecionado
        df_ano = df[df['CODG_ANO'] == selected_year]
        
        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df_ano.columns:
            df_ano['DESC_UND_FED'] = df_ano['CODG_UND_FED'].astype(str).map(UF_NAMES)
            df_ano = df_ano.dropna(subset=['DESC_UND_FED'])
        
        # Converte o campo VLR_VAR para numérico
        df_ano['VLR_VAR'] = pd.to_numeric(df_ano['VLR_VAR'], errors='coerce')
        df_ano = df_ano.dropna(subset=['VLR_VAR'])
        
        if df_ano.empty:
            raise PreventUpdate
        
        # Obtém a unidade de medida
        unidade_medida = df_ano['DESC_UND_MED'].iloc[0] if 'DESC_UND_MED' in df_ano.columns else 'Unidade não disponível'
        
        # Cria o gráfico de pizza
        fig_pie = px.pie(
            df_ano,
            values='VLR_VAR',
            names='DESC_UND_FED',
            labels={
                'DESC_UND_FED': 'Unidade Federativa',
                'VLR_VAR': 'Valor'
            }
        )
        
        # Atualiza o layout do gráfico de pizza
        fig_pie.update_layout(
            showlegend=True,
            legend=dict(
                title="Unidade Federativa",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.05,
                orientation="v"
            ),
            margin=dict(r=150)  # Margem à direita para acomodar a legenda
        )
        
        # Atualiza o hover do gráfico de pizza
        fig_pie.update_traces(
            hovertemplate="<b>%{label}</b><br>" +
                        "Valor: %{value}<br>" +
                        "Percentual: %{percent:.1%}<br>" +
                        f"Unidade de Medida: {unidade_medida}<extra></extra>",
            textinfo="label+value+percent",
            texttemplate="<b>%{label}</b><br>%{value}<br>%{percent:.1%}",
            textposition="outside",
            showlegend=False,
            hoverinfo="skip"
        )
        
        # Destaca Goiás no gráfico de pizza
        for trace in fig_pie.data:
            if trace.name == 'Goiás':
                trace.marker = dict(color='#229846')
                trace.name = '<b>Goiás</b>'
        
        return fig_pie
    except Exception as e:
        print(f"Erro ao atualizar gráfico de pizza: {e}")
        raise PreventUpdate


# Obtém a instância do servidor Flask
server = app.server

def update_maintenance_mode(new_state: bool):
    """Atualiza o estado do modo de manutenção no arquivo .env"""
    env_vars = {}
    
    # Se o arquivo .env existe, lê as variáveis existentes
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
    else:
        # Se o arquivo não existe, define valores padrão
        env_vars = {
            'DEBUG': 'false',
            'USE_RELOADER': 'false',
            'PORT': '8050',
            'HOST': '0.0.0.0',
            'MAINTENANCE_MODE': 'false',
            'SECRET_KEY': generate_secret_key(),
            'MAINTENANCE_PASSWORD_HASH': generate_password_hash(MAINTENANCE_PASSWORD)
        }

    # Atualiza o estado do modo de manutenção
    env_vars['MAINTENANCE_MODE'] = str(new_state).lower()

    # Escreve o arquivo .env atualizado
    with open('.env', 'w', encoding='utf-8') as f:
        for key, value in env_vars.items():
            f.write(f'{key}={value}\n')

@server.route('/toggle-maintenance', methods=['POST'])
def toggle_maintenance():
    """Alterna o modo de manutenção do sistema"""
    global MAINTENANCE_MODE
    try:
        data = request.get_json()
        if not data or 'password' not in data:
            return jsonify({
                'success': False,
                'message': 'Por favor, forneça a senha de manutenção para continuar.',
                'maintenance_mode': MAINTENANCE_MODE
            }), 400

        stored_hash = get_maintenance_password_hash()
        if not stored_hash:
            return jsonify({
                'success': False,
                'message': 'Configuração de senha não encontrada. Por favor, entre em contato com o administrador do sistema.',
                'maintenance_mode': MAINTENANCE_MODE
            }), 500

        if not check_password(data['password'], stored_hash):
            return jsonify({
                'success': False,
                'message': 'A senha fornecida está incorreta. Por favor, verifique e tente novamente.',
                'maintenance_mode': MAINTENANCE_MODE
            }), 401

        MAINTENANCE_MODE = not MAINTENANCE_MODE
        # Persiste o novo estado no arquivo .env
        update_maintenance_mode(MAINTENANCE_MODE)
        
        return jsonify({
            'success': True,
            'message': f'Modo de manutenção {"ativado" if MAINTENANCE_MODE else "desativado"} com sucesso!',
            'maintenance_mode': MAINTENANCE_MODE
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Ocorreu um erro ao processar sua solicitação. Por favor, tente novamente mais tarde.',
            'maintenance_mode': MAINTENANCE_MODE,
            'error': str(e)
        }), 500

def get_maintenance_password_hash():
    """Obtém o hash da senha de manutenção do arquivo .env"""
    return os.getenv('MAINTENANCE_PASSWORD_HASH')

if __name__ == '__main__':
    # Verifica se o arquivo .env existe
    if not os.path.exists('.env'):
        print("Arquivo .env não encontrado. Criando com as configurações padrão...")
        
        # Gera uma nova SECRET_KEY e atualiza o arquivo .env
        new_secret_key = generate_secret_key()
        update_env_file(generate_password_hash(MAINTENANCE_PASSWORD))
        
        print("Arquivo .env criado com sucesso!")
        # Recarrega as variáveis de ambiente
        load_dotenv()

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
