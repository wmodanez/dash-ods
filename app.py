import dash
from dash import (
    html, dcc, Input, Output, State, callback, dash_table,
    callback_context, ALL, MATCH, no_update # Adiciona ALL e MATCH aqui
)
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import time
import warnings
from datetime import datetime
import numpy as np
from dash.exceptions import PreventUpdate # Mantém import específico
# Removido o import plotly.io as pio (já importado abaixo)
# Removido import do warning_counter
from config import *
import secrets
from dotenv import load_dotenv
from functools import lru_cache
from cache_manager import cache_manager, load_dados_indicador_cached, preload_related_indicators
from flask import session, redirect, send_from_directory, request, jsonify
import bcrypt
from generate_password import generate_password_hash, generate_secret_key, update_env_file, check_password
from flask_cors import CORS
import constants  # Importar constantes

# Carrega as variáveis de ambiente primeiro
load_dotenv()

# Configuração do tema do Plotly
import plotly.io as pio # Movido para cá para evitar re-import
pio.templates.default = "plotly_white"

# Remove imports redundantes que estavam abaixo

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
        if request.path.startswith('/assets/') or '_dash-component-suites' in request.path:
            return None
        return send_from_directory('assets', 'maintenance.html')
    return None

def capitalize_words(text):
    return ' '.join(word.capitalize() for word in text.split())

# Inicializa o aplicativo Dash com tema Bootstrap
app = dash.Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.MATERIA,
        "https://cdn.jsdelivr.net/npm/ag-grid-community@30.2.1/styles/ag-grid.min.css",
        "https://cdn.jsdelivr.net/npm/ag-grid-community@30.2.1/styles/ag-theme-alpine.min.css",
    ],
    assets_folder='assets',
    assets_url_path='/assets/',
    serve_locally=True,
    suppress_callback_exceptions=True,  # Suprimir exceções de callbacks para componentes dinâmicos
    **DASH_CONFIG
)

# Registra o middleware de manutenção
app.server.before_request(maintenance_middleware)

# Configurações de cache
for key, value in SERVER_CONFIG.items():
    app.server.config[key] = value

# Configura a chave secreta do Flask
app.server.secret_key = SERVER_CONFIG['SECRET_KEY']

@app.server.route('/assets/<path:path>')
def serve_static(path):
    return send_from_directory('assets', path)





CORS(app.server)

@app.server.route('/log', methods=['POST'])
def log_message():
    if not app.server.debug:
        return '', 204
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

@app.server.route('/_dash-component-suites/<path:path>')
def serve_dash_files(path):
    return send_from_directory('_dash-component-suites', path)

# Função original para carregar dados do indicador (sem cache)
def _load_dados_indicador_original(indicador_id):
    """Função original para carregar dados do indicador (sem cache)."""
    try:
        nome_arquivo = indicador_id.lower().replace("indicador ", "")
        arquivo_parquet = f'db/resultados/indicador{nome_arquivo}.parquet'
        arquivo_metadados = f'db/resultados/indicador{nome_arquivo}_metadata.json'
        if not os.path.exists(arquivo_parquet):
            return pd.DataFrame()
        try:
            with open(arquivo_metadados, 'r', encoding='utf-8') as f:
                metadados = json.load(f)
        except Exception as e:
            metadados = None
        try:
            df_load = pd.read_parquet(arquivo_parquet)
            if df_load.empty:
                return pd.DataFrame()
        except Exception as e:
            return pd.DataFrame()
        if metadados:
            for coluna, tipo in metadados['colunas'].items():
                if coluna in df_load.columns:
                    try:
                        if coluna == 'CODG_ANO':
                            df_load[coluna] = df_load[coluna].astype(str)
                        elif 'Int64' in tipo:
                            df_load[coluna] = pd.to_numeric(df_load[coluna], errors='coerce').astype('Int64')
                        elif 'float' in tipo:
                            df_load[coluna] = pd.to_numeric(df_load[coluna], errors='coerce')
                        elif 'category' in tipo:
                            df_load[coluna] = df_load[coluna].astype('category')
                    except Exception as e:
                        pass
        return df_load
    except Exception as e:
        return pd.DataFrame()

# Função com cache de dois níveis
def load_dados_indicador_cache(indicador_id):
    """Carrega dados do indicador usando cache de dois níveis (memória e disco)."""
    return load_dados_indicador_cached(indicador_id, _load_dados_indicador_original)

def limpar_cache_indicadores():
    """Limpa o cache de indicadores."""
    # Limpa o cache de dois níveis
    cache_manager.clear()
    # Limpa o cache LRU da função original (se ainda estiver sendo usado em algum lugar)
    if hasattr(load_dados_indicador_cache, 'cache_clear'):
        load_dados_indicador_cache.cache_clear()

@app.server.route('/limpar-cache')
def limpar_cache():
    try:
        session.clear()
        limpar_cache_indicadores()
        return redirect('/')
    except Exception as e:
        return redirect('/')

@app.server.route('/cache-stats')
def view_cache_stats():
    """Exibe estatísticas do cache."""
    stats = cache_manager.get_stats()
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Estatísticas do Cache</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2c3e50; }}
            .stats {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .stat-item {{ margin-bottom: 10px; }}
            .stat-label {{ font-weight: bold; }}
            .hit-rate {{ font-size: 1.2em; color: #27ae60; }}
            .actions {{ margin-top: 20px; }}
            .btn {{ display: inline-block; padding: 10px 15px; background-color: #3498db; color: white;
                   text-decoration: none; border-radius: 4px; margin-right: 10px; }}
            .btn:hover {{ background-color: #2980b9; }}
            .btn-danger {{ background-color: #e74c3c; }}
            .btn-danger:hover {{ background-color: #c0392b; }}
            .timestamp {{ color: #7f8c8d; font-size: 0.9em; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>Estatísticas do Cache</h1>
        <div class="timestamp">Dados atualizados em: {time.strftime('%d/%m/%Y %H:%M:%S')}</div>

        <div class="stats">
            <div class="stat-item hit-rate">
                <span class="stat-label">Taxa de acerto:</span> {stats['hit_rate']:.2%}
            </div>
            <div class="stat-item">
                <span class="stat-label">Acertos em memória:</span> {stats['memory_hits']}
            </div>
            <div class="stat-item">
                <span class="stat-label">Acertos em disco:</span> {stats['disk_hits']}
            </div>
            <div class="stat-item">
                <span class="stat-label">Erros:</span> {stats['misses']}
            </div>
            <div class="stat-item">
                <span class="stat-label">Pré-carregamentos:</span> {stats['preloads']}
            </div>
            <div class="stat-item">
                <span class="stat-label">Tamanho do cache em memória:</span> {stats['memory_cache_size']}/{stats['memory_cache_maxsize']}
            </div>
        </div>

        <div class="actions">
            <a href="/limpar-cache" class="btn btn-danger">Limpar Cache</a>
            <a href="/" class="btn">Voltar para o Painel</a>
        </div>
    </body>
    </html>
    """
    return html

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
            function enviarLog(mensagem, stack) {
                fetch('/log', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        message: typeof mensagem === 'object' ? JSON.stringify(mensagem) : String(mensagem),
                        stack: stack || new Error().stack
                    })
                })
                .then(response => response.ok ? response.json() : Promise.reject('Falha na requisição: ' + response.status))
                .then(data => console.log("Log enviado:", data))
                .catch(err => console.log("Erro ao enviar log:", err));
            }
            const originalConsoleError = console.error;
            console.error = function() {
                const args = Array.from(arguments);
                const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
                enviarLog(message, new Error().stack);
                originalConsoleError.apply(console, arguments);
            };
            window.addEventListener('error', function(event) {
                enviarLog(event.message, event.error ? event.error.stack : null);
                return false;
            });
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

@lru_cache(maxsize=1)
def load_objetivos():
    try:
        df_obj = pd.read_csv('db/objetivos.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
        if df_obj.iloc[(0,)].name == '#':
            df_obj = df_obj.iloc[1:]
        required_columns = ['ID_OBJETIVO', 'RES_OBJETIVO', 'DESC_OBJETIVO', 'BASE64']
        if not all(col in df_obj.columns for col in required_columns):
             return pd.DataFrame(columns=required_columns)
        return df_obj
    except Exception as e:
        return pd.DataFrame(columns=['ID_OBJETIVO', 'RES_OBJETIVO', 'DESC_OBJETIVO', 'BASE64'])

@lru_cache(maxsize=1)
def load_metas():
    try:
        return pd.read_csv('db/metas.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
    except Exception as e:
        return pd.DataFrame()

@lru_cache(maxsize=1)
def load_indicadores():
    try:
        df_ind = pd.read_csv('db/indicadores.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
        df_ind['RBC'] = pd.to_numeric(df_ind['RBC'], errors='coerce')
        return df_ind.loc[df_ind['RBC'] == 1]
    except Exception as e:
        return pd.DataFrame()

@lru_cache(maxsize=1)
def load_sugestoes_visualizacao():
    try:
        return pd.read_csv('db/sugestoes_visualizacao.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
    except Exception as e:
        return pd.DataFrame()

@lru_cache(maxsize=1)
def load_unidade_medida():
    cols = ['CODG_UND_MED', 'DESC_UND_MED']
    try:
        try:
            df_um = pd.read_csv('db/unidade_medida.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';')
        except:
            df_um = pd.read_csv('db/unidade_medida.csv', low_memory=False, encoding='utf-8', dtype=str, sep=',')
        if len(df_um.columns) == 1 and ',' in df_um.columns[0]:
            df_um = pd.DataFrame([x.split(',') for x in df_um[df_um.columns[0]]])
            if len(df_um.columns) >= 2:
                df_um = df_um.iloc[:, [0, 1]]
                df_um.columns = cols
        if not all(col in df_um.columns for col in cols):
            return pd.DataFrame(columns=cols)
        for col in cols:
            df_um[col] = df_um[col].str.strip().str.strip('"')
        return df_um
    except Exception as e:
        return pd.DataFrame(columns=cols)

@lru_cache(maxsize=1)
def load_variavel():
    cols = ['CODG_VAR', 'DESC_VAR']
    try:
        try:
            df_var = pd.read_csv('db/variavel.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';')
        except:
            df_var = pd.read_csv('db/variavel.csv', low_memory=False, encoding='utf-8', dtype=str, sep=',')
        if len(df_var.columns) == 1 and ',' in df_var.columns[0]:
            df_var = pd.DataFrame([x.split(',') for x in df_var[df_var.columns[0]]])
            if len(df_var.columns) >= 2:
                df_var = df_var.iloc[:, [0, 1]]
                df_var.columns = cols
        if not all(col in df_var.columns for col in cols):
            return pd.DataFrame(columns=cols)
        for col in cols:
            df_var[col] = df_var[col].str.strip().str.strip('"')
        return df_var
    except Exception as e:
        return pd.DataFrame(columns=cols)

df = load_objetivos()
df_metas = load_metas()
df_indicadores = load_indicadores()
df_unidade_medida = load_unidade_medida()
df_variavel = load_variavel()

if not df.empty:
    row_objetivo_0 = df.iloc[(0,)]
    initial_header = row_objetivo_0['RES_OBJETIVO']
    initial_content = row_objetivo_0['DESC_OBJETIVO']
else:
    initial_header = "Erro ao carregar dados"
    initial_content = "Não foi possível carregar dados dos objetivos."

initial_meta_description = ""
meta_inicial = None
if not df.empty and not df_metas.empty:
    try:
        metas_filtradas_inicial = df_metas[df_metas['ID_OBJETIVO'] == df.iloc[(0,)]['ID_OBJETIVO']]
        metas_com_indicadores_inicial = [
            meta for _, meta in metas_filtradas_inicial.iterrows()
            if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
        ]
        if metas_com_indicadores_inicial:
             meta_inicial = metas_com_indicadores_inicial[0]
             initial_meta_description = meta_inicial['DESC_META']
    except Exception as e:
        pass

# Prepara os indicadores iniciais
# Cria componentes vazios para evitar erros de callback
initial_tabs_indicadores = dbc.Tabs(id='tabs-indicadores', children=[])
initial_indicadores_section = [
    html.H5("Indicadores", className="mt-4 mb-3", style={'display': 'none'}),
    dbc.Card(dbc.CardBody(initial_tabs_indicadores), className="mt-3", style={'display': 'none'}),
    # Componente vazio para lazy-load-container
    html.Div(id={'type': 'lazy-load-container', 'index': 'placeholder'}, style={'display': 'none'})
]

if meta_inicial:
    indicadores_meta_inicial = df_indicadores[df_indicadores['ID_META'] == meta_inicial['ID_META']]

# Função auxiliar para identificar colunas de filtro
def identify_filter_columns(df):
    """Identifica colunas no DataFrame que devem ser usadas como filtros dinâmicos."""
    if df is None or df.empty:
        return []
    all_cols = set(df.columns)
    non_filter_cols = {
        'CODG_ANO', 'VLR_VAR', 'CODG_UND_FED', 'CODG_UND_MED', 'CODG_VAR',
        'DESC_ANO', 'DESC_UND_FED', 'DESC_UND_MED', 'DESC_VAR',
        'ID_INDICADOR', 'ID_META', 'ID_OBJETIVO',
        'Unidade Federativa', 'Ano', 'Variável', 'Valor', 'Unidade de Medida'
    }
    non_filter_cols.update({col for col in all_cols if col.startswith('DESC_')})
    candidate_cols = all_cols - non_filter_cols
    filter_cols = [
        col for col in candidate_cols
        if col in constants.COLUMN_NAMES and df[col].nunique(dropna=True) > 1
    ]
    return sorted(filter_cols)

def create_visualization(df, indicador_id=None, selected_var=None, selected_filters=None):
    """Cria uma visualização (gráfico de linha, mapa e tabela) com os dados do DataFrame, aplicando filtros."""
    if df is None or df.empty:
        return dbc.Alert("Nenhum dado disponível para este indicador.", color="warning", className="textCenter p-3")

    try:
        colunas_necessarias = ['CODG_ANO', 'VLR_VAR']
        if not all(col in df.columns for col in colunas_necessarias):
            missing = [col for col in colunas_necessarias if col not in df.columns]
            return dbc.Alert(f"Dados incompletos. Colunas faltando: {', '.join(missing)}", color="warning", className="textCenter p-3")

        df_filtered = df.copy()

        # Aplica filtro de VARIÁVEL PRINCIPAL
        if 'CODG_VAR' in df_filtered.columns and selected_var:
            df_filtered['CODG_VAR'] = df_filtered['CODG_VAR'].astype(str).str.strip()
            selected_var_str = str(selected_var).strip()
            df_filtered = df_filtered[df_filtered['CODG_VAR'] == selected_var_str]
            if df_filtered.empty:
                var_name = selected_var_str
                df_var_desc = load_variavel()
                if not df_var_desc.empty:
                     var_info = df_var_desc[df_var_desc['CODG_VAR'] == selected_var_str]
                     if not var_info.empty:
                         var_name = var_info['DESC_VAR'].iloc[0]
                return dbc.Alert(f"Nenhum dado encontrado para a variável '{var_name}'.", color="warning")

        # Aplica FILTROS DINÂMICOS
        if selected_filters:
            for col_code, selected_value in selected_filters.items():
                if selected_value is not None and selected_value != 'all' and col_code in df_filtered.columns:
                    df_filtered[col_code] = df_filtered[col_code].astype(str).str.strip()
                    selected_value_str = str(selected_value).strip()
                    df_filtered = df_filtered[df_filtered[col_code] == selected_value_str]
                    if df_filtered.empty:
                        filter_name = constants.COLUMN_NAMES.get(col_code, col_code)
                        return dbc.Alert(f"Nenhum dado encontrado para o filtro '{filter_name}' = '{selected_value_str}'.", color="warning")

        if df_filtered.empty:
             return dbc.Alert("Nenhum dado encontrado após aplicar os filtros.", color="warning")

        # --- Adiciona/Garante Colunas de Descrição ---
        # Descrição UF
        if 'CODG_UND_FED' in df_filtered.columns:
            df_filtered['DESC_UND_FED'] = df_filtered['CODG_UND_FED'].astype(str).map(constants.UF_NAMES)
            df_filtered = df_filtered.dropna(subset=['DESC_UND_FED'])
        elif 'DESC_UND_FED' not in df_filtered.columns:
             df_filtered['DESC_UND_FED'] = 'N/D'

        # Descrição Variável
        df_variavel_loaded = load_variavel()
        if 'CODG_VAR' in df_filtered.columns and not df_variavel_loaded.empty:
            df_filtered['CODG_VAR'] = df_filtered['CODG_VAR'].astype(str)
            df_variavel_loaded['CODG_VAR'] = df_variavel_loaded['CODG_VAR'].astype(str)
            df_filtered = df_filtered.merge(df_variavel_loaded[['CODG_VAR', 'DESC_VAR']], on='CODG_VAR', how='left')
            df_filtered['DESC_VAR'] = df_filtered['DESC_VAR'].fillna('N/D')
        elif 'DESC_VAR' not in df_filtered.columns:
            df_filtered['DESC_VAR'] = 'N/D'

        # Descrição Unidade de Medida
        df_unidade_medida_loaded = load_unidade_medida()
        if 'CODG_UND_MED' in df_filtered.columns and not df_unidade_medida_loaded.empty:
            df_filtered['CODG_UND_MED'] = df_filtered['CODG_UND_MED'].astype(str)
            df_unidade_medida_loaded['CODG_UND_MED'] = df_unidade_medida_loaded['CODG_UND_MED'].astype(str)
            df_filtered = df_filtered.merge(df_unidade_medida_loaded[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
            df_filtered['DESC_UND_MED'] = df_filtered['DESC_UND_MED'].fillna('N/D')
        elif 'DESC_UND_MED' not in df_filtered.columns:
            df_filtered['DESC_UND_MED'] = 'N/D'

        # Descrições para Filtros Dinâmicos
        dynamic_filter_cols = identify_filter_columns(df) # Identifica filtros no DF ORIGINAL
        processed_desc_cols = set()
        for filter_col_code in dynamic_filter_cols:
            desc_col_code = 'DESC_' + filter_col_code[5:]
            if desc_col_code in processed_desc_cols:
                continue
            if desc_col_code not in df_filtered.columns:
                if desc_col_code in df.columns and filter_col_code in df_filtered.columns and filter_col_code in df.columns:
                    try:
                        merge_data = df[[filter_col_code, desc_col_code]].drop_duplicates().copy()
                        df_filtered[filter_col_code] = df_filtered[filter_col_code].astype(str)
                        merge_data[filter_col_code] = merge_data[filter_col_code].astype(str)
                        df_filtered = pd.merge(df_filtered, merge_data, on=filter_col_code, how='left')
                        df_filtered[desc_col_code] = df_filtered[desc_col_code].fillna('N/D')
                    except Exception as merge_err:
                        df_filtered[desc_col_code] = 'N/D'
                else:
                    df_filtered[desc_col_code] = 'N/D'
            else:
                df_filtered[desc_col_code] = df_filtered[desc_col_code].fillna('N/D')
            processed_desc_cols.add(desc_col_code)

        # Ordena e limpa dados numéricos
        df_filtered['CODG_ANO'] = df_filtered['CODG_ANO'].astype(str)
        df_filtered = df_filtered.sort_values('CODG_ANO')
        df_filtered['VLR_VAR'] = pd.to_numeric(df_filtered['VLR_VAR'], errors='coerce')
        df_filtered = df_filtered.dropna(subset=['VLR_VAR'])

        if df_filtered.empty:
            return dbc.Alert("Não há dados numéricos válidos para criar a visualização.", color="warning", className="textCenter p-3")

        df_original_for_table = df_filtered.copy()

        # --- Definição Dinâmica das Colunas da Tabela AG Grid ---
        base_col_defs = [
            {"field": 'DESC_UND_FED', "headerName": 'Unidade Federativa'},
            {"field": 'CODG_ANO', "headerName": 'Ano'},
            {"field": 'DESC_VAR', "headerName": 'Variável'},
        ]
        dynamic_desc_col_defs = []
        dynamic_desc_col_names = set()
        for filter_col_code in dynamic_filter_cols:
             desc_col_code = 'DESC_' + filter_col_code[5:]
             if desc_col_code in df_original_for_table.columns:
                  readable_name = constants.COLUMN_NAMES.get(desc_col_code, desc_col_code.replace('DESC_','').replace('_',' ').title())
                  dynamic_desc_col_defs.append({"field": desc_col_code, "headerName": readable_name})
                  dynamic_desc_col_names.add(desc_col_code)
        final_col_defs = base_col_defs + dynamic_desc_col_defs + [
             {"field": 'VLR_VAR', "headerName": 'Valor'},
             {"field": 'DESC_UND_MED', "headerName": 'Unidade de Medida'}
        ]
        columnDefs = []
        present_columns = df_original_for_table.columns
        for col_def in final_col_defs:
            field_name = col_def['field']
            if field_name in present_columns:
                 base_props = {"sortable": True, "filter": True, "minWidth": 100, "resizable": True, "wrapText": True, "autoHeight": True, "cellStyle": {"whiteSpace": "normal"}}
                 if field_name == 'DESC_VAR': flex_value = 3
                 elif field_name == 'DESC_UND_FED' or field_name == 'DESC_UND_MED': flex_value = 2
                 elif field_name == 'CODG_ANO' or field_name == 'VLR_VAR' or field_name in dynamic_desc_col_names: flex_value = 1
                 else: flex_value = 1
                 columnDefs.append({**base_props, "field": field_name, "headerName": col_def['headerName'], "flex": flex_value})
        defaultColDef = {
            "minWidth": 100, "resizable": True, "wrapText": True, "autoHeight": True,
            "cellStyle": {"whiteSpace": "normal", 'textAlign': 'left'}
        }

        # --- Criação das Figuras dos Gráficos ---
        main_fig = go.Figure() # Figura principal (pode ser linha ou barra)
        fig_map = go.Figure()
        anos_unicos = sorted(df_filtered['CODG_ANO'].unique())
        ano_default = anos_unicos[-1] if anos_unicos else None

        # Verifica qual tipo de gráfico principal deve ser criado (Linha ou Barras)
        grafico_linha_flag = 1 # Padrão é gráfico de linha
        if indicador_id and not df_indicadores.empty:
            indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
            if not indicador_info.empty and 'GRAFICO_LINHA' in indicador_info.columns:
                try:
                    # Tenta converter para numérico, tratando NaN ou erros
                    grafico_linha_flag = pd.to_numeric(indicador_info['GRAFICO_LINHA'].iloc[0], errors='coerce')
                    if pd.isna(grafico_linha_flag):
                        grafico_linha_flag = 1 # Volta para o padrão em caso de NaN
                    else:
                        grafico_linha_flag = int(grafico_linha_flag)
                except (ValueError, TypeError):
                    grafico_linha_flag = 1 # Volta para o padrão em caso de erro

        # --- Criação do Gráfico Principal (Linha ou Barras) ---
        if grafico_linha_flag == 1:
            # Lógica para criar Gráfico de Linha (código existente movido para cá)
            if len(df_filtered) >= 1:
                group_cols_line = ['CODG_ANO', 'DESC_UND_FED'] if 'DESC_UND_FED' in df_filtered.columns else ['CODG_ANO']
                df_grouped_line = df_filtered.groupby(group_cols_line, as_index=False).agg(
                    VLR_VAR=('VLR_VAR', 'first'), DESC_UND_MED=('DESC_UND_MED', 'first'), DESC_VAR=('DESC_VAR', 'first')
                ).sort_values('CODG_ANO')

                if not df_grouped_line.empty:
                    config_line = {'x': 'CODG_ANO', 'y': 'VLR_VAR', 'labels': {'CODG_ANO': "", 'VLR_VAR': ""}}
                    if 'DESC_UND_FED' in df_grouped_line.columns:
                        config_line['color'] = 'DESC_UND_FED'
                        config_line['labels']['color'] = f"<b>{constants.COLUMN_NAMES.get('DESC_UND_FED', 'UF')}</b>"
                    fig_line = px.line(df_grouped_line, **config_line)
                    fig_line.update_traces(
                        line_shape='spline', mode='lines+markers',
                        marker=dict(size=14, symbol='circle', line=dict(width=2, color='white')),
                        hovertemplate = (
                            "<b>%{customdata[0]}</b><br>Ano: %{x}<br>Valor: %{y}<br>Unidade: %{customdata[1]}<extra></extra>"
                        ) if 'DESC_UND_FED' in df_grouped_line.columns else (
                            "Ano: %{x}<br>Valor: %{y}<br>Unidade: %{customdata[0]}<extra></extra>"
                        )
                    )
                    if 'DESC_UND_FED' in df_grouped_line.columns:
                        fig_line.update_traces(customdata=df_grouped_line[['DESC_UND_FED', 'DESC_UND_MED']])
                        for trace in fig_line.data:
                            if trace.name == 'Goiás':
                                trace.line.color = '#229846'; trace.line.width = 6; trace.name = '<b>Goiás</b>'
                            elif trace.name == 'Maranhão': trace.line.color = '#D2B48C'
                    else:
                        fig_line.update_traces(customdata=df_grouped_line[['DESC_UND_MED']])
                    layout_updates_line = DEFAULT_LAYOUT.copy()
                    layout_updates_line.update({
                        'xaxis': dict(showgrid=False, zeroline=False, tickfont=dict(size=12, color='black'), tickangle=45),
                        'yaxis': dict(showgrid=False, zeroline=False, tickfont=dict(size=12, color='black'), title=None)
                    })
                    if 'CODG_ANO' in df_grouped_line.columns:
                        unique_years_line = sorted(df_grouped_line['CODG_ANO'].unique())
                        layout_updates_line['xaxis']['ticktext'] = [f"<b>{x}</b>" for x in unique_years_line]
                        layout_updates_line['xaxis']['tickvals'] = unique_years_line
                    fig_line.update_layout(layout_updates_line)
                    main_fig = fig_line # Atribui à figura principal
            else:
                # Se não houver dados suficientes para o gráfico de linha, retorna alerta + tabela
                return html.Div([
                    dbc.Alert("Dados insuficientes para o gráfico de linha. Mostrando tabela.", color="info", className="textCenter p-3"),
                    dag.AgGrid(
                        rowData=df_original_for_table.to_dict('records'), columnDefs=columnDefs, defaultColDef=defaultColDef,
                        dashGridOptions={ "pagination": True, "paginationPageSize": 10, "domLayout": "autoHeight" },
                        style={"width": "100%"}
                    )
                ])
        elif grafico_linha_flag == 0:
            # Lógica para criar Gráfico de Barras
            if 'DESC_UND_FED' in df_filtered.columns and ano_default:
                df_bar_data = df_filtered[df_filtered['CODG_ANO'] == ano_default]
                if not df_bar_data.empty:
                    # Ordena por valor para melhor visualização (opcional)
                    df_bar_data = df_bar_data.sort_values('VLR_VAR', ascending=False)

                    und_med_bar = df_bar_data['DESC_UND_MED'].iloc[0] if not df_bar_data['DESC_UND_MED'].empty else ''
                    fig_bar = px.bar(df_bar_data, x='DESC_UND_FED', y='VLR_VAR', color='DESC_UND_FED',
                                     labels={'DESC_UND_FED': '', 'VLR_VAR': ''},
                                     title=f'Valores para o ano {ano_default}')
                    fig_bar.update_traces(
                        hovertemplate=f"<b>%{{x}}</b><br>Valor: %{{y}}{' ' + und_med_bar if und_med_bar else ''}<extra></extra>",
                        marker_line_color='rgb(8,48,107)', marker_line_width=1.5, opacity=0.8
                    )
                    layout_updates_bar = DEFAULT_LAYOUT.copy()
                    layout_updates_bar.update({
                        'xaxis': dict(showgrid=False, zeroline=False, tickfont=dict(size=12, color='black'), tickangle=45, title=None),
                        'yaxis': dict(showgrid=False, zeroline=False, tickfont=dict(size=12, color='black'), title=None),
                        'showlegend': False # Geralmente não precisa de legenda para barras por estado
                    })
                    fig_bar.update_layout(layout_updates_bar)
                    main_fig = fig_bar # Atribui à figura principal
                else:
                    # Retorna alerta se não houver dados para o ano default do gráfico de barras
                    return dbc.Alert(f"Não há dados disponíveis para o ano {ano_default} para gerar o gráfico de barras.", color="warning")
            else:
                # Retorna alerta se a coluna UF ou ano default não estiverem disponíveis para o gráfico de barras
                missing_info = []
                if 'DESC_UND_FED' not in df_filtered.columns: missing_info.append("'Unidade Federativa (DESC_UND_FED)'")
                if not ano_default: missing_info.append("'Ano padrão'")
                return dbc.Alert(f"Não é possível gerar o gráfico de barras. Informações ausentes: {', '.join(missing_info)}.", color="warning")
        else:
            # Caso flag seja inválido (não deve ocorrer devido ao tratamento acima, mas por segurança)
            return dbc.Alert("Configuração de tipo de gráfico inválida.", color="danger")

        # Criação do Mapa (se houver UF e ano) - Lógica existente mantida
        if 'DESC_UND_FED' in df_filtered.columns and ano_default:
            df_map_data = df_filtered[df_filtered['CODG_ANO'] == ano_default]
            if not df_map_data.empty:
                try:
                    with open('db/br_geojson.json', 'r', encoding='utf-8') as f: geojson = json.load(f)
                    und_med_map = df_map_data['DESC_UND_MED'].iloc[0] if not df_map_data['DESC_UND_MED'].empty else ''
                    fig_map = px.choropleth(
                        df_map_data, geojson=geojson, locations='DESC_UND_FED', featureidkey='properties.name',
                        color='VLR_VAR', color_continuous_scale='Greens_r', scope="south america"
                    )
                    fig_map.update_geos(visible=False, showcoastlines=True, coastlinecolor="White", showland=True, landcolor="white", showframe=False, center=dict(lat=-12.9598, lon=-53.2729), projection=dict(type='mercator', scale=2.6))
                    fig_map.update_traces(marker_line_color='white', marker_line_width=1, hovertemplate=f"<b>%{{location}}</b><br>Valor: %{{z}}{' ' + und_med_map if und_med_map else ''}<extra></extra>")
                    fig_map.update_layout(margin=dict(r=0, l=0, t=0, b=0), coloraxis_colorbar=dict(title=None, tickfont=dict(size=12, color='black')))
                except Exception as map_err:
                     print(f"Erro ao gerar mapa: {map_err}")
                     # Mantem fig_map vazio

        # --- Monta o Layout da Visualização ---
        graph_layout = []

        # Define o conteúdo do gráfico principal (linha OU barra) - Removido estilo de borda
        main_chart_content = dcc.Graph(id={'type': 'main-chart', 'index': indicador_id}, figure=main_fig)

        # Monta o conteúdo da Card de visualização
        visualization_card_content = None
        if 'DESC_UND_FED' in df_filtered.columns and fig_map.data: # Se tem mapa (independente do gráfico principal)
            map_content = html.Div([
                html.Label("Ano (Mapa):", style={'fontWeight': 'bold','marginBottom': '5px','display': 'block'}),
                dcc.Dropdown(
                    id={'type': 'year-dropdown', 'index': indicador_id},
                    options=[{'label': ano, 'value': ano} for ano in anos_unicos],
                    value=ano_default,
                    clearable=False,
                    style={'width': '100%', 'marginBottom': '10px'}
                ),
                dcc.Graph(id={'type': 'choropleth-map', 'index': indicador_id}, figure=fig_map)
            ]) # Removido estilo de borda

            visualization_card_content = dbc.CardBody(
                dbc.Row([
                    dbc.Col(main_chart_content, md=7, xs=12, className="mb-4 mb-md-0"), # Usa main_chart_content
                    dbc.Col(map_content, md=5, xs=12)
                ])
            )
        else: # Layout sem Mapa (sem dados de UF ou erro na criação do mapa)
            visualization_card_content = dbc.CardBody(
                dbc.Row([
                    dbc.Col(main_chart_content, width=12) # Usa main_chart_content
                ])
            )

        # Adiciona a Card de Visualização ao layout principal
        if visualization_card_content:
            graph_layout.append(dbc.Row([
                dbc.Col(dbc.Card(visualization_card_content, className="mb-4"), width=12) # Adiciona Card e margem inferior
            ]))

        # Adiciona Tabela Detalhada sempre
        graph_layout.append(dbc.Row([
            dbc.Col(dbc.Card([
                html.H5("Dados Detalhados", className="mt-4", style={'marginLeft': '20px'}),
                dbc.CardBody(dag.AgGrid(
                    id={'type': 'detail-table', 'index': indicador_id},
                    rowData=df_original_for_table.to_dict('records'),
                    columnDefs=columnDefs,
                    defaultColDef=defaultColDef,
                    dashGridOptions={
                        "pagination": True, "paginationPageSize": 10,
                        "paginationPageSizeSelector": [5, 10, 20, 50, 100],
                        "domLayout": "autoHeight", "suppressMovableColumns": True,
                        "animateRows": True, "suppressColumnVirtualisation": True
                    },
                    style={"width": "100%"}
                ))
            ]), className="mt-4")
        ]))
        return graph_layout

    except Exception as e:
        print(f"Erro em create_visualization para {indicador_id}: {e}")
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"Erro ao gerar visualização para {indicador_id}.", color="danger")

# Define o layout padrão
DEFAULT_LAYOUT = {
    'showlegend': True,
    'legend': dict(
        title=None,
        orientation="h",  # Legenda horizontal
        yanchor="top",
        y=1.2,  # Posiciona abaixo do gráfico
        xanchor="center",
        x=0.5  # Centraliza horizontalmente
    ),
    'margin': dict(l=20, r=20, t=40, b=100),  # Ajusta margens para acomodar a legenda
    'xaxis': dict(showgrid=False, zeroline=False),
    'yaxis': dict(showgrid=False, zeroline=False),
    'xaxis_automargin': True,
    'yaxis_automargin': True
}

# Define o layout do aplicativo
app.layout = dbc.Container([
    # Header com imagens e título
    dbc.Row(dbc.Col(dbc.Card([
        dbc.CardBody(dbc.Row([
            dbc.Col(html.Img(src='/assets/img/sgg.png', className="img-fluid", style={'maxWidth': '150px', 'height': 'auto'}), xs=12, sm=6, md=3, className="p-2"),
            dbc.Col(html.Img(src='/assets/img/imb720.png', className="img-fluid", style={'maxWidth': '150px', 'height': 'auto'}), xs=12, sm=6, md=3, className="p-2"),
            dbc.Col(html.H1('Instituto Mauro Borges - ODS - Agenda 2030', className="align-middle", style={'margin': '0', 'padding': '0'}), xs=12, sm=12, md=6, className="d-flex align-items-center justify-content-center justify-content-md-start p-2")
        ], className="align-items-center"))
    ], className="mb-4", style={'marginTop': '15px', 'marginLeft': '15px', 'marginRight': '15px'}))),
    # Card Principal
    dbc.Row(dbc.Col(dbc.Card([
        dbc.CardBody(dbc.Row([
            # Menu Lateral (Objetivos)
            dbc.Col(dbc.Card(dbc.CardBody(dbc.Row([
                dbc.Col(html.Div(html.Img(src=row['BASE64'], style={'width': '100%', 'marginBottom': '10px', 'cursor': 'pointer'}, className="img-fluid", id=f"objetivo{idx}", n_clicks=1 if idx == 0 else 0)), width=4)
                for idx, row in df.iterrows()
            ], className="g-2"))), lg=2),
            # Conteúdo Principal (Metas e Indicadores)
            dbc.Col(dbc.Card([
                dbc.CardHeader(html.H3(id='card-header', children=initial_header)),
                dbc.CardBody([
                    html.Div(id='card-content', children=initial_content),
                    dbc.Nav(id='metas-nav', pills=True, className="nav nav-pills gap-2", style={'display': 'flex', 'flexWrap': 'wrap', 'marginBottom': '1rem'}, children=[]),
                    html.Div(id='meta-description', children=initial_meta_description, className="textJustify mt-4"),
                    html.Div(id='loading-indicator', children=[]),
                    html.Div(id='indicadores-section', children=initial_indicadores_section),
                    # Componente oculto para acionar o carregamento do primeiro indicador
                    html.Div(id='trigger-first-tab-load', style={'display': 'none'})
                ])
            ]), lg=10)
        ]))
    ], className="border-0 shadow-none")))
], fluid=True)

# Callback para atualizar o conteúdo do card principal (metas, indicadores)
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
    prevent_initial_call=True # Impede execução inicial
)
def update_card_content(*args):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    triggered_id_str = ctx.triggered[0]['prop_id']
    triggered_value = ctx.triggered[0]['value']

    # Ignora cliques iniciais ou cliques sem valor (n_clicks=0)
    if triggered_value is None or triggered_value == 0:
        raise PreventUpdate

    try:
        # --- Clique em uma META ---
        if 'meta-button' in triggered_id_str:
            # Forma mais robusta de obter o ID usando o contexto
            if isinstance(ctx.triggered_id, dict):
                meta_id = ctx.triggered_id.get('index')
            else: # Fallback (menos provável de ser necessário agora)
                 try:
                      meta_id = json.loads(triggered_id_str.split('.')[0])['index']
                 except (json.JSONDecodeError, IndexError, KeyError):
                      print(f"Erro ao parsear meta_id de: {triggered_id_str}")
                      raise PreventUpdate

            if not meta_id:
                 raise PreventUpdate # Não conseguiu obter o meta_id

            meta_filtrada = df_metas[df_metas['ID_META'] == meta_id]
            if meta_filtrada.empty:
                 return no_update, no_update, no_update, "Meta não encontrada.", [] # Atualiza descrição

            meta_desc = meta_filtrada['DESC_META'].iloc[0]
            objetivo_id = meta_filtrada['ID_OBJETIVO'].iloc[0]

            # Recria a barra de navegação das metas, marcando a ativa
            metas_obj_filtradas = df_metas[df_metas['ID_OBJETIVO'] == objetivo_id]
            metas_com_indicadores = [
                meta for _, meta in metas_obj_filtradas.iterrows()
                if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
            ]
            metas_nav_children = [
                dbc.NavLink(
                    meta['ID_META'],
                    id={'type': 'meta-button', 'index': meta['ID_META']},
                    href="#",
                    active=(meta['ID_META'] == meta_id),
                    className="nav-link",
                    n_clicks=0 # Reset n_clicks
                ) for meta in metas_com_indicadores
            ]

            # Gera a seção de indicadores para a meta clicada
            indicadores_meta_selecionada = df_indicadores[df_indicadores['ID_META'] == meta_id]
            tabs_indicadores = []

            # Inicia o pré-carregamento preditivo em segundo plano (opcional, mas bom manter)
            preload_related_indicators(meta_id, df_indicadores, _load_dados_indicador_original)

            if not indicadores_meta_selecionada.empty:
                valor_inicial_variavel_primeira_aba = None

                for i, (_, row_ind) in enumerate(indicadores_meta_selecionada.iterrows()):
                    indicador_id_atual = row_ind['ID_INDICADOR']
                    is_first_indicator = (i == 0)

                    if is_first_indicator:
                        # Carrega dados e cria conteúdo COMPLETO apenas para o primeiro indicador
                        df_dados = load_dados_indicador_cache(indicador_id_atual)
                        tab_content = []
                        dynamic_filters_div = []
                        valor_inicial_variavel = None

                        if df_dados is not None and not df_dados.empty:
                            try:
                                # Identifica filtros dinâmicos
                                filter_cols = identify_filter_columns(df_dados)

                                # Prepara os filtros dinâmicos
                                for idx_filter, filter_col_code in enumerate(filter_cols):
                                    desc_col_code = 'DESC_' + filter_col_code[5:]
                                    code_to_desc = {}
                                    if desc_col_code in df_dados.columns:
                                        try:
                                            mapping_df = df_dados[[filter_col_code, desc_col_code]].dropna().drop_duplicates()
                                            code_to_desc = pd.Series(mapping_df[desc_col_code].astype(str).values,
                                                                     index=mapping_df[filter_col_code].astype(str)).to_dict()
                                        except Exception as map_err:
                                            print(f"Erro mapeamento {filter_col_code}: {map_err}")
                                    unique_codes = sorted(df_dados[filter_col_code].dropna().astype(str).unique())
                                    col_options = [{'label': 'Todos', 'value': 'all'}] + \
                                                  [{'label': str(code_to_desc.get(code, code)), 'value': code} for code in unique_codes]
                                    filter_label = constants.COLUMN_NAMES.get(filter_col_code, filter_col_code)
                                    md_width = 7 if idx_filter % 2 == 0 else 5
                                    dynamic_filters_div.append(dbc.Col([
                                        html.Label(f"{filter_label}:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '5px'}),
                                        dcc.Dropdown(
                                            id={'type': 'dynamic-filter-dropdown', 'index': indicador_id_atual, 'filter_col': filter_col_code},
                                            options=col_options,
                                            value='all',
                                            style={'marginBottom': '10px', 'width': '100%'}
                                        )
                                    ], md=md_width, xs=12))

                                # Dropdown de variável principal
                                indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id_atual]
                                has_variable_dropdown = not indicador_info.empty and 'VARIAVEIS' in indicador_info.columns and indicador_info['VARIAVEIS'].iloc[0] == '1'
                                variable_dropdown_div = []
                                if has_variable_dropdown:
                                    df_variavel_loaded = load_variavel()
                                    if 'CODG_VAR' in df_dados.columns:
                                        variaveis_indicador = df_dados['CODG_VAR'].astype(str).unique()
                                        if not df_variavel_loaded.empty:
                                            df_variavel_filtrado = df_variavel_loaded[df_variavel_loaded['CODG_VAR'].astype(str).isin(variaveis_indicador)]
                                            if not df_variavel_filtrado.empty:
                                                valor_inicial_variavel = df_variavel_filtrado['CODG_VAR'].iloc[0]
                                                valor_inicial_variavel_primeira_aba = valor_inicial_variavel # Salva para o Store
                                                variable_dropdown_div = [html.Div([
                                                    html.Label("Selecione uma Variável:",
                                                             style={'fontWeight': 'bold','display': 'block','marginBottom': '5px'},
                                                             id={'type': 'var-label', 'index': indicador_id_atual}),
                                                    dcc.Dropdown(
                                                        id={'type': 'var-dropdown', 'index': indicador_id_atual},
                                                        options=[{'label': row['DESC_VAR'], 'value': row['CODG_VAR']} for _, row in df_variavel_filtrado.iterrows()],
                                                        value=valor_inicial_variavel,
                                                        style={'width': '100%', 'marginBottom': '15px'}
                                                    )
                                                ])] # Removido ID e style do Div container

                                # Cria a visualização inicial
                                initial_visualization = create_visualization(df_dados, indicador_id_atual, valor_inicial_variavel, None)
                                tab_content = [html.P(row_ind['DESC_INDICADOR'], className="textJustify p-3", style={'marginBottom': '10px'})]
                                tab_content.extend(variable_dropdown_div)
                                if dynamic_filters_div:
                                    tab_content.append(dbc.Row(dynamic_filters_div))
                                tab_content.append(html.Div(id={'type': 'graph-container', 'index': indicador_id_atual}, children=initial_visualization))
                            except Exception as e_inner:
                                print(f"Erro interno ao gerar conteúdo da aba {indicador_id_atual}: {e_inner}")
                                tab_content = [dbc.Alert(f"Erro ao gerar conteúdo para {indicador_id_atual}.", color="danger")]
                        else:
                            tab_content = [dbc.Alert(f"Dados não disponíveis para {indicador_id_atual}.", color="warning")]
                    else:
                        # Para os demais indicadores, cria apenas placeholder (lazy loading)
                        tab_content = [
                            html.Div([
                                html.P(row_ind['DESC_INDICADOR'], className="textJustify", style={'display': 'inline-block', 'marginRight': '10px'}),
                                dbc.Spinner(color="primary", size="sm", type="grow", spinner_style={'display': 'inline-block'}, id={'type': 'spinner-indicator', 'index': indicador_id_atual})
                            ], className="p-3"),
                            html.Div(id={'type': 'lazy-load-container', 'index': indicador_id_atual}, style={'minHeight': '50px'})
                        ]

                    # Adiciona Store para CADA aba (carregada ou não)
                    # Para a primeira aba, usa o valor_inicial_variavel encontrado
                    # Para as outras, o valor inicial da variável será None até serem carregadas
                    store_data = {
                        'selected_var': valor_inicial_variavel_primeira_aba if is_first_indicator else None,
                        'selected_filters': {}
                    }
                    tab_content.append(dcc.Store(id={'type': 'visualization-state-store', 'index': indicador_id_atual}, data=store_data))

                    # Adiciona a aba
                    tabs_indicadores.append(dbc.Tab(tab_content, label=indicador_id_atual, tab_id=f"tab-{indicador_id_atual}", id={'type': 'tab-indicador', 'index': indicador_id_atual}))

            # Define a primeira aba como ativa
            first_tab_id = tabs_indicadores[0].tab_id if tabs_indicadores else None

            # Monta a seção de indicadores
            indicadores_section = [
                html.H5("Indicadores", className="mt-4 mb-3"),
                dbc.Card(dbc.CardBody(
                    dbc.Tabs(id='tabs-indicadores', children=tabs_indicadores, active_tab=first_tab_id)
                ), className="mt-3")
            ] if tabs_indicadores else [] # Só mostra seção se houver indicadores

            # Retorna SEM no_update para header/content para permitir voltar ao desc do objetivo se necessário
            objetivo_row = df[df['ID_OBJETIVO'] == objetivo_id].iloc[0]
            header_obj = f"{objetivo_row['ID_OBJETIVO']} - {objetivo_row['RES_OBJETIVO']}"
            content_obj = objetivo_row['DESC_OBJETIVO']
            return header_obj, content_obj, metas_nav_children, meta_desc, indicadores_section

        # --- Clique em um OBJETIVO ---
        elif 'objetivo' in triggered_id_str:
            index = int(triggered_id_str.replace('objetivo', '').split('.')[0])
            if index >= len(df):
                return "Erro", "Objetivo não encontrado.", [], "", []
            row_obj = df.iloc[index]
            header = f"{row_obj['ID_OBJETIVO']} - {row_obj['RES_OBJETIVO']}" if index > 0 else row_obj['RES_OBJETIVO']
            content = row_obj['DESC_OBJETIVO']

            # Se for objetivo 0, limpa metas e indicadores
            if index == 0:
                return header, content, [], "", []

            # Encontra metas com indicadores para este objetivo
            metas_obj_filtradas = df_metas[df_metas['ID_OBJETIVO'] == row_obj['ID_OBJETIVO']]
            metas_com_indicadores = [
                meta for _, meta in metas_obj_filtradas.iterrows()
                if not df_indicadores[df_indicadores['ID_META'] == meta['ID_META']].empty
            ]

            if not metas_com_indicadores:
                # Retorna o alerta na seção de indicadores com estilo
                alert_message = dbc.Alert(
                    "Não existem metas com indicadores disponíveis para este objetivo.",
                    color="warning",
                    className="mt-4",
                    style={'textAlign': 'center', 'font-weight': 'bold'} # Adiciona estilo aqui
                )
                return header, content, [], "", [alert_message] # Limpa descrição da meta, mostra alerta

            # Seleciona a primeira meta e gera a navegação
            meta_selecionada = metas_com_indicadores[0]
            metas_nav_children = [
                dbc.NavLink(
                    meta['ID_META'],
                    id={'type': 'meta-button', 'index': meta['ID_META']},
                    href="#",
                    active=(meta['ID_META'] == meta_selecionada['ID_META']),
                    className="nav-link",
                    n_clicks=0 # Reset n_clicks
                ) for meta in metas_com_indicadores
            ]
            meta_description = meta_selecionada['DESC_META']

            # Gera a seção de indicadores para a primeira meta
            meta_id = meta_selecionada['ID_META']
            indicadores_primeira_meta = df_indicadores[df_indicadores['ID_META'] == meta_id]
            tabs_indicadores = []

            # Inicia o pré-carregamento preditivo dos indicadores desta meta em segundo plano
            preload_related_indicators(meta_id, df_indicadores, _load_dados_indicador_original)

            if not indicadores_primeira_meta.empty:
                # Variável para armazenar o valor inicial da variável (usado apenas para o primeiro indicador)
                valor_inicial_variavel = None

                # Cria abas para todos os indicadores da primeira meta
                for i, row_ind in indicadores_primeira_meta.iterrows():
                    # Apenas o primeiro indicador é carregado completamente
                    is_first_indicator = (i == 0)

                    if is_first_indicator:
                        # Carrega dados apenas para o primeiro indicador
                        df_dados = load_dados_indicador_cache(row_ind['ID_INDICADOR'])
                        tab_content = []
                        dynamic_filters_div = []
                        valor_inicial_variavel = None

                        if df_dados is not None and not df_dados.empty:
                            try:
                                # Identifica filtros dinâmicos
                                filter_cols = identify_filter_columns(df_dados)

                                # Prepara os filtros dinâmicos
                                for idx, filter_col_code in enumerate(filter_cols):
                                    desc_col_code = 'DESC_' + filter_col_code[5:]
                                    code_to_desc = {}
                                    if desc_col_code in df_dados.columns:
                                        try:
                                            mapping_df = df_dados[[filter_col_code, desc_col_code]].dropna().drop_duplicates()
                                            code_to_desc = pd.Series(mapping_df[desc_col_code].astype(str).values,
                                                                     index=mapping_df[filter_col_code].astype(str)).to_dict()
                                        except Exception as map_err:
                                            print(f"Erro ao criar mapeamento para {filter_col_code} -> {desc_col_code}: {map_err}")

                                    # Gera opções para o dropdown
                                    unique_codes = sorted(df_dados[filter_col_code].dropna().astype(str).unique())
                                    col_options = [{'label': 'Todos', 'value': 'all'}] + \
                                                  [{'label': str(code_to_desc.get(code, code)), 'value': code} for code in unique_codes]
                                    filter_label = constants.COLUMN_NAMES.get(filter_col_code, filter_col_code)

                                    # Define larguras alternadas para os filtros
                                    md_width = 7 if idx % 2 == 0 else 5

                                    dynamic_filters_div.append(
                                        dbc.Col([
                                            html.Label(f"{filter_label}:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '5px'}),
                                            dcc.Dropdown(
                                                id={'type': 'dynamic-filter-dropdown', 'index': row_ind['ID_INDICADOR'], 'filter_col': filter_col_code},
                                                options=col_options,
                                                value='all',
                                                style={'marginBottom': '10px', 'width': '100%'}
                                            )
                                        ], md=md_width, xs=12)
                                    )

                                # Dropdown de variável principal
                                indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == row_ind['ID_INDICADOR']]
                                has_variable_dropdown = not indicador_info.empty and 'VARIAVEIS' in indicador_info.columns and indicador_info['VARIAVEIS'].iloc[0] == '1'
                                variable_dropdown_div = []
                                if has_variable_dropdown:
                                    df_variavel_loaded = load_variavel()
                                    if 'CODG_VAR' in df_dados.columns:
                                        variaveis_indicador = df_dados['CODG_VAR'].astype(str).unique()
                                        if not df_variavel_loaded.empty:
                                            df_variavel_filtrado = df_variavel_loaded[df_variavel_loaded['CODG_VAR'].astype(str).isin(variaveis_indicador)]
                                            if not df_variavel_filtrado.empty:
                                                valor_inicial_variavel = df_variavel_filtrado['CODG_VAR'].iloc[0]
                                                variable_dropdown_div = [html.Div([
                                                    html.Label("Selecione uma Variável:",
                                                             style={'fontWeight': 'bold','display': 'block','marginBottom': '5px'},
                                                             id={'type': 'var-label', 'index': row_ind['ID_INDICADOR']}),
                                                    dcc.Dropdown(
                                                        id={'type': 'var-dropdown', 'index': row_ind['ID_INDICADOR']},
                                                        options=[{'label': row['DESC_VAR'], 'value': row['CODG_VAR']} for _, row in df_variavel_filtrado.iterrows()],
                                                        value=valor_inicial_variavel,
                                                        style={'width': '100%', 'marginBottom': '15px'}
                                                    )
                                                ])]

                                # Cria a visualização inicial para o primeiro indicador
                                initial_visualization = create_visualization(df_dados, row_ind['ID_INDICADOR'], valor_inicial_variavel, None)
                                tab_content = [html.P(row_ind['DESC_INDICADOR'], className="textJustify p-3", style={'marginBottom': '10px'})]
                                tab_content.extend(variable_dropdown_div)
                                if dynamic_filters_div:
                                    tab_content.append(dbc.Row(dynamic_filters_div))
                                tab_content.append(html.Div(id={'type': 'graph-container', 'index': row_ind['ID_INDICADOR']}, children=initial_visualization))

                            except Exception as e_inner:
                                print(f"Erro interno ao gerar conteúdo da aba {row_ind['ID_INDICADOR']}: {e_inner}")
                                tab_content = [dbc.Alert(f"Erro ao gerar conteúdo para {row_ind['ID_INDICADOR']}.", color="danger")]
                        else:
                            tab_content = [dbc.Alert(f"Dados não disponíveis para {row_ind['ID_INDICADOR']}.", color="warning")]
                    else:
                        # Para os demais indicadores, cria apenas um placeholder que será carregado sob demanda
                        tab_content = [
                            # Coloca o spinner ao lado do título para economizar espaço
                            html.Div([
                                html.P(row_ind['DESC_INDICADOR'], className="textJustify", style={'display': 'inline-block', 'marginRight': '10px'}),
                                dbc.Spinner(color="primary", size="sm", type="grow", spinner_style={'display': 'inline-block'}, id={'type': 'spinner-indicator', 'index': row_ind['ID_INDICADOR']})
                            ], className="p-3"),
                            # Div oculta que será substituída pelo conteúdo quando carregado
                            html.Div(id={'type': 'lazy-load-container', 'index': row_ind['ID_INDICADOR']}, style={'minHeight': '50px'})
                        ]

                    # Adiciona Store para esta aba
                    tab_content.append(dcc.Store(id={'type': 'visualization-state-store', 'index': row_ind['ID_INDICADOR']},
                                                data={'selected_var': valor_inicial_variavel if is_first_indicator else None, 'selected_filters': {}}))

                    # Adiciona a aba ao conjunto de abas
                    tabs_indicadores.append(dbc.Tab(tab_content,
                                                   label=row_ind['ID_INDICADOR'],
                                                   tab_id=f"tab-{row_ind['ID_INDICADOR']}",
                                                   id={'type': 'tab-indicador', 'index': row_ind['ID_INDICADOR']}))

            # Adiciona um trigger para carregar o primeiro indicador automaticamente
            first_tab_id = tabs_indicadores[0].tab_id if tabs_indicadores else None

            indicadores_section = [
                 html.H5("Indicadores", className="mt-4 mb-3"),
                 dbc.Card(dbc.CardBody(
                     dbc.Tabs(id='tabs-indicadores', children=tabs_indicadores, active_tab=first_tab_id)
                 ), className="mt-3")
            ] if tabs_indicadores else []

            return header, content, metas_nav_children, meta_description, indicadores_section
        else:
            # Caso ID não seja nem meta nem objetivo (não deve acontecer)
            raise PreventUpdate

    except Exception as e:
        print(f"Erro geral em update_card_content: {e}")
        import traceback
        traceback.print_exc()
        # Retorna um estado seguro em caso de erro inesperado
        return initial_header, initial_content, [], "Ocorreu um erro.", []

# Callback para carregar os dados de cada indicador (REMOVIDO, pois update_visualization_from_store faz isso)

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
        df_map = load_dados_indicador_cache(indicador_id)
        if df_map is None or df_map.empty:
             # Prevenir atualização se dados não carregarem para este indicador
             print(f"update_map: Dados não encontrados para {indicador_id}, prevenindo update do mapa.")
             # Encontra o índice do mapa correspondente para retornar no_update específico
             target_output_index = -1
             for i, output_spec in enumerate(ctx.outputs_list):
                 if isinstance(output_spec['id'], dict) and output_spec['id'].get('index') == indicador_id:
                     target_output_index = i
                     break
             output_list = [no_update] * len(ctx.outputs_list)
             return output_list # Retorna lista com no_update para todos

        # Filtra os dados para o ano selecionado e cria uma cópia explícita
        df_ano = df_map[df_map['CODG_ANO'] == selected_year].copy()

        # Substitui os códigos das UFs pelos nomes completos
        if 'CODG_UND_FED' in df_ano.columns:
            df_ano['DESC_UND_FED'] = df_ano['CODG_UND_FED'].astype(str).map(constants.UF_NAMES)
            df_ano = df_ano.dropna(subset=['DESC_UND_FED'])

        if df_ano.empty:
             # Se não houver dados para o ano/UF específico, retorna no_update para este mapa
             print(f"update_map: Dados não encontrados para {indicador_id} no ano {selected_year}, prevenindo update.")
             target_output_index = -1
             for i, output_spec in enumerate(ctx.outputs_list):
                 if isinstance(output_spec['id'], dict) and output_spec['id'].get('index') == indicador_id:
                     target_output_index = i
                     break
             output_list = [no_update] * len(ctx.outputs_list)
             # Não precisa atualizar se não há dados
             return output_list

        # Carrega o GeoJSON
        with open('db/br_geojson.json', 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        # Pega a unidade de medida (de forma segura)
        und_med_map = ''
        if 'DESC_UND_MED' in df_ano.columns and not df_ano['DESC_UND_MED'].empty:
            und_med_map = df_ano['DESC_UND_MED'].iloc[0]

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

        # Atualiza o layout do mapa e adiciona linhas de divisão brancas e mais grossas
        fig_map.update_traces(
            marker_line_color='white',
            marker_line_width=1,
            hovertemplate="<b>%{location}</b><br>" +
                        f"Valor: %{{z}}" + (f" {und_med_map}" if und_med_map else "") + "<extra></extra>"
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
        print(f"Erro ao atualizar mapa para indicador {indicador_id}: {e}")
        # Retorna no_update para todas as saídas em caso de erro
        return [no_update] * len(ctx.outputs_list)

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

# --- Novos Callbacks usando dcc.Store ---

# Callback 1: Atualiza o Store quando a variável principal muda
@app.callback(
    Output({'type': 'visualization-state-store', 'index': MATCH}, 'data', allow_duplicate=True),
    Input({'type': 'var-dropdown', 'index': MATCH}, 'value'),
    State({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
    prevent_initial_call=True
)
def update_store_from_variable(selected_var, current_data):
    if selected_var is None and not callback_context.triggered_id: # Permite atualização inicial se var for None
        raise PreventUpdate

    current_data = current_data or {'selected_var': None, 'selected_filters': {}}
    current_data['selected_var'] = selected_var
    return current_data

# Callback 2: Atualiza o Store quando um filtro dinâmico muda
@app.callback(
    Output({'type': 'visualization-state-store', 'index': MATCH}, 'data', allow_duplicate=True),
    Input({'type': 'dynamic-filter-dropdown', 'index': MATCH, 'filter_col': ALL}, 'value'),
    State({'type': 'dynamic-filter-dropdown', 'index': MATCH, 'filter_col': ALL}, 'id'),
    State({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
    prevent_initial_call=True
)
def update_store_from_filters(filter_values, filter_ids, current_data):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    current_data = current_data or {'selected_var': None, 'selected_filters': {}}

    selected_filters = {}
    if filter_ids and filter_values:
        try:
            if len(filter_ids) != len(filter_values):
                print(f"Aviso [update_store_from_filters]: Comprimento de filter_ids({len(filter_ids)}) e filter_values({len(filter_values)}) não coincide.")
                raise PreventUpdate # Evita erro de zip

            for filter_id, filter_value in zip(filter_ids, filter_values):
                if filter_id and 'filter_col' in filter_id and filter_value is not None and filter_value != 'all':
                    col_name = filter_id['filter_col']
                    selected_filters[col_name] = filter_value
        except Exception as e:
            print(f"Erro ao processar filtros dinâmicos no store: {e}")
            raise PreventUpdate

    current_data['selected_filters'] = selected_filters
    return current_data

# Callback 3: Atualiza a visualização (gráficos/tabela) quando o Store muda
@app.callback(
    Output({'type': 'graph-container', 'index': MATCH}, 'children'),
    Input({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
    State({'type': 'visualization-state-store', 'index': MATCH}, 'id'),
    # prevent_initial_call=True # Comentado intencionalmente
)
def update_visualization_from_store(store_data, store_id):
    if store_id is None:
        raise PreventUpdate

    indicador_id = store_id['index']
    store_data = store_data or {'selected_var': None, 'selected_filters': {}}
    selected_var = store_data.get('selected_var')
    selected_filters = store_data.get('selected_filters', {})

    try:
        df = load_dados_indicador_cache(indicador_id)
        if df is None or df.empty:
            return dbc.Alert(f"Dados não encontrados para o indicador {indicador_id} ao atualizar visualização.", color="warning")

        return create_visualization(df, indicador_id, selected_var, selected_filters)

    except Exception as e:
        print(f"--- ERROR in update_visualization_from_store for indicator {indicador_id} ---")
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"Ocorreu um erro ao atualizar a visualização para o indicador {indicador_id}.", color="danger")

# Callback para acionar o carregamento do primeiro indicador quando o objetivo é selecionado
@app.callback(
    Output('trigger-first-tab-load', 'children'),
    Input('indicadores-section', 'children'),
    prevent_initial_call=True
)
def trigger_first_tab_load(indicadores_section):
    # Se não houver indicadores, não faz nada
    if not indicadores_section:
        raise PreventUpdate

    # Retorna um valor qualquer para acionar o callback
    return html.Div(f"Loaded at {time.time()}", style={'display': 'none'})

# Callback para garantir que a primeira aba esteja ativa
@app.callback(
    Output('tabs-indicadores', 'active_tab'),
    Input('trigger-first-tab-load', 'children'),
    State('tabs-indicadores', 'children'),
    State('tabs-indicadores', 'active_tab'),
    prevent_initial_call=True
)
def set_first_tab_active(_trigger, tabs, current_active_tab):
    # Se já houver uma aba ativa, mantém ela
    if current_active_tab:
        return current_active_tab

    # Se não houver abas, não faz nada
    if not tabs or len(tabs) == 0:
        raise PreventUpdate

    try:
        # Tenta obter o ID da primeira aba
        return tabs[0].tab_id
    except (AttributeError, IndexError):
        # Se não conseguir, não faz nada
        raise PreventUpdate

# Callback para carregar indicadores sob demanda quando uma aba é clicada
@app.callback(
    [Output({'type': 'lazy-load-container', 'index': MATCH}, 'children'),
     Output({'type': 'spinner-indicator', 'index': MATCH}, 'style')],
    Input('tabs-indicadores', 'active_tab'),
    State({'type': 'lazy-load-container', 'index': MATCH}, 'id'),
    prevent_initial_call=True
)
def load_indicator_on_demand(active_tab, container_id):
    # Só carrega se a aba estiver ativa
    if not active_tab or not container_id:
        raise PreventUpdate

    # Obtém o ID do indicador
    indicador_id = container_id['index']

    # Ignora o placeholder
    if indicador_id == 'placeholder':
        raise PreventUpdate

    # Verifica se a aba ativa corresponde a este indicador
    if active_tab != f"tab-{indicador_id}":
        raise PreventUpdate

    # Verifica se já está carregado (se já tiver um graph-container, não precisa carregar novamente)
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    # Carrega os dados do indicador
    df_dados = load_dados_indicador_cache(indicador_id)
    tab_content = []
    dynamic_filters_div = []
    valor_inicial_variavel = None

    # Busca informações do indicador
    indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
    if indicador_info.empty:
        return [dbc.Alert(f"Informações não encontradas para o indicador {indicador_id}.", color="danger")], {'display': 'none'}

    # Adiciona a descrição do indicador
    tab_content = [html.P(indicador_info.iloc[0]['DESC_INDICADOR'], className="textJustify p-3")]

    if df_dados is not None and not df_dados.empty:
        try:
            # Identifica filtros dinâmicos
            filter_cols = identify_filter_columns(df_dados)

            # Prepara os filtros dinâmicos
            for idx, filter_col_code in enumerate(filter_cols):
                desc_col_code = 'DESC_' + filter_col_code[5:]
                code_to_desc = {}
                if desc_col_code in df_dados.columns:
                    try:
                        mapping_df = df_dados[[filter_col_code, desc_col_code]].dropna().drop_duplicates()
                        code_to_desc = pd.Series(mapping_df[desc_col_code].astype(str).values,
                                                 index=mapping_df[filter_col_code].astype(str)).to_dict()
                    except Exception as map_err:
                        print(f"Erro mapeamento {filter_col_code}: {map_err}")
                unique_codes = sorted(df_dados[filter_col_code].dropna().astype(str).unique())
                col_options = [{'label': 'Todos', 'value': 'all'}] + \
                              [{'label': str(code_to_desc.get(code, code)), 'value': code} for code in unique_codes]
                filter_label = constants.COLUMN_NAMES.get(filter_col_code, filter_col_code)

                # Define larguras alternadas para os filtros
                md_width = 7 if idx % 2 == 0 else 5

                dynamic_filters_div.append(dbc.Col([
                    html.Label(f"{filter_label}:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '5px'}),
                    dcc.Dropdown(
                        id={'type': 'dynamic-filter-dropdown', 'index': indicador_id, 'filter_col': filter_col_code},
                        options=col_options,
                        value='all',
                        style={'marginBottom': '10px', 'width': '100%'}
                    )
                ], md=md_width, xs=12))

            # Dropdown de variável principal
            has_variable_dropdown = not indicador_info.empty and 'VARIAVEIS' in indicador_info.columns and indicador_info['VARIAVEIS'].iloc[0] == '1'
            variable_dropdown_div = []
            if has_variable_dropdown:
                df_variavel_loaded = load_variavel()
                if 'CODG_VAR' in df_dados.columns:
                    variaveis_indicador = df_dados['CODG_VAR'].astype(str).unique()
                    if not df_variavel_loaded.empty:
                        df_variavel_filtrado = df_variavel_loaded[df_variavel_loaded['CODG_VAR'].astype(str).isin(variaveis_indicador)]
                        if not df_variavel_filtrado.empty:
                            valor_inicial_variavel = df_variavel_filtrado['CODG_VAR'].iloc[0]
                            variable_dropdown_div = [html.Div([
                                html.Label("Selecione uma Variável:",
                                         style={'fontWeight': 'bold','display': 'block','marginBottom': '5px'},
                                         id={'type': 'var-label', 'index': indicador_id}),
                                dcc.Dropdown(
                                    id={'type': 'var-dropdown', 'index': indicador_id},
                                    options=[{'label': desc, 'value': cod} for cod, desc in zip(df_variavel_filtrado['CODG_VAR'], df_variavel_filtrado['DESC_VAR'])],
                                    value=valor_inicial_variavel,
                                    style={'width': '100%'}
                                )
                            ], style={'paddingBottom': '20px', 'paddingTop': '20px'}, id={'type': 'var-dropdown-container', 'index': indicador_id})]

            # Cria a visualização inicial
            initial_visualization = create_visualization(df_dados, indicador_id, valor_inicial_variavel, None)
            tab_content.extend(variable_dropdown_div)
            if dynamic_filters_div:
                tab_content.append(dbc.Row(dynamic_filters_div))
            tab_content.append(html.Div(id={'type': 'graph-container', 'index': indicador_id}, children=initial_visualization))

        except Exception as e_inner:
            print(f"Erro interno ao gerar conteúdo da aba {indicador_id}: {e_inner}")
            import traceback
            traceback.print_exc()
            tab_content.append(dbc.Alert(f"Erro ao gerar conteúdo para {indicador_id}.", color="danger"))
            return tab_content, {'display': 'none'}
    else:
        tab_content.append(dbc.Alert(f"Dados não disponíveis para {indicador_id}.", color="warning"))
        return tab_content, {'display': 'none'}

    # Retorna apenas o conteúdo para o contêiner de carregamento
    # Não retornamos a descrição do indicador, pois ela já está na aba
    # Retornamos apenas os filtros, variáveis e visualizações
    dynamic_content = []

    # Adiciona os dropdowns de variáveis se existirem
    for item in tab_content:
        if isinstance(item, html.Div) and item.id and isinstance(item.id, dict) and item.id.get('type') == 'var-dropdown-container':
            dynamic_content.append(item)

    # Adiciona os filtros dinâmicos
    if dynamic_filters_div:
        dynamic_content.append(dbc.Row(dynamic_filters_div))

    # Adiciona a visualização
    dynamic_content.append(html.Div(id={'type': 'graph-container', 'index': indicador_id}, children=initial_visualization))

    # Nota: Não precisamos criar um novo store ou callback, pois eles já existem na aba

    # Oculta o spinner quando os dados são carregados
    spinner_style = {'display': 'none'}

    return dynamic_content, spinner_style

# Obtém a instância do servidor Flask
server = app.server

def update_maintenance_mode(new_state: bool):
    """Atualiza o estado do modo de manutenção no arquivo .env"""
    env_vars = {}

    # Se o arquivo .env existe, lê as variáveis existentes
    if os.path.exists('.env'):
        with open('.env', 'r', encoding='utf-8') as f:
            for loc in f:
                if '=' in loc:
                    key, value = loc.strip().split('=', 1)
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
            host=HOST
        )
    else:
        # Em produção, o uWSGI irá usar a variável 'server'
        app.run_server(
            debug=False,
            use_reloader=False,
            port=PORT,
            host=HOST
        )
