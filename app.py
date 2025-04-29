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
from dash.exceptions import PreventUpdate 
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
import logging 
import math

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

# Configuração do Logging
log_level = logging.DEBUG if DEBUG else logging.INFO
# logging.basicConfig(
#     level=log_level,
#     format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
#     datefmt='%Y-%m-%d %H:%M:%S'
# )

# --- Nova Configuração de Logging com Arquivo Timestamped ---
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True)
# MODIFICADO: Nome do arquivo agora é baseado apenas na data (um arquivo por dia)
log_filename = datetime.now().strftime(f'{log_dir}/app_log_%Y-%m-%d.log')

log_formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(log_formatter)

# Configura o logger raiz
root_logger = logging.getLogger()
root_logger.setLevel(log_level)
root_logger.addHandler(file_handler)

# Opcional: Adiciona também um handler para o console se ainda quiser ver logs no terminal
# console_handler = logging.StreamHandler()
# console_handler.setFormatter(log_formatter)
# root_logger.addHandler(console_handler)
# --- Fim da Nova Configuração ---

logging.info(f"Iniciando aplicação. Nível de log: {logging.getLevelName(log_level)}. Logando em: {log_filename}")

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
        # print("\n====================== ERRO DO NAVEGADOR ======================")
        # print(f"Mensagem: {data.get('message', 'Sem mensagem')}")
        # print(f"Stack: {data.get('stack', 'Sem stack')}")
        # print("===============================================================\n")
        # Usamos logging.error para registrar o erro do navegador no backend
        # Corrigido: Removida a quebra de linha dentro da string de formatação
        logging.error("Erro do navegador recebido: Mensagem: %s Stack: %s",
                      data.get('message', 'Sem mensagem'),
                      data.get('stack', 'Sem stack'))
        return jsonify({"status": "logged", "success": True})
    except Exception as e:
        # print(f"Erro ao processar log do cliente: {str(e)}")
        # Usamos logging.exception para capturar o erro e o traceback
        logging.exception("Erro ao processar log do cliente:")
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
        if not os.path.exists(arquivo_parquet):
            # print(f"Aviso: Arquivo parquet não encontrado para {indicador_id}: {arquivo_parquet}")
            # Usamos logging.warning para avisos
            logging.warning("Arquivo parquet não encontrado para %s: %s", indicador_id, arquivo_parquet)
            return pd.DataFrame()
        try:
            df_load = pd.read_parquet(arquivo_parquet)
            if df_load.empty:
                # print(f"Aviso: Arquivo parquet vazio para {indicador_id}: {arquivo_parquet}")
                # Usamos logging.warning para avisos
                logging.warning("Arquivo parquet vazio para %s: %s", indicador_id, arquivo_parquet)
                return pd.DataFrame()
        except Exception as e:
            # print(f"Erro ao ler arquivo parquet para {indicador_id}: {e}")
            # Usamos logging.exception para capturar o erro e o traceback
            logging.exception("Erro ao ler arquivo parquet para %s", indicador_id)
            return pd.DataFrame()
        return df_load
    except Exception as e:
        # print(f"Erro geral em _load_dados_indicador_original para {indicador_id}: {e}")
        # Usamos logging.exception para capturar o erro e o traceback
        logging.exception("Erro geral em _load_dados_indicador_original para %s", indicador_id)
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
        # Usamos logging.exception aqui também, embora redirecione
        logging.exception("Erro ao limpar cache:")
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
             logging.error("Colunas obrigatórias faltando em objetivos.csv: %s", [col for col in required_columns if col not in df_obj.columns])
             return pd.DataFrame(columns=required_columns)
        return df_obj
    except Exception as e:
        logging.exception("Erro ao carregar db/objetivos.csv") # Adicionado logging
        return pd.DataFrame(columns=['ID_OBJETIVO', 'RES_OBJETIVO', 'DESC_OBJETIVO', 'BASE64'])


@lru_cache(maxsize=1)
def load_metas():
    try:
        return pd.read_csv('db/metas.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
    except Exception as e:
        logging.exception("Erro ao carregar db/metas.csv") # Adicionado logging
        return pd.DataFrame()


def load_indicadores():
    try:
        df_ind = pd.read_csv('db/indicadores.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
        # Converte RBC e RANKING_ORDEM para numérico, tratando erros
        df_ind['RBC'] = pd.to_numeric(df_ind['RBC'], errors='coerce')
        if 'RANKING_ORDEM' in df_ind.columns:
            df_ind['RANKING_ORDEM'] = pd.to_numeric(df_ind['RANKING_ORDEM'], errors='coerce').fillna(0).astype(int) # Converte para int, NaN vira 0
        else:
            df_ind['RANKING_ORDEM'] = 0 # Adiciona coluna com 0 se não existir
        # Garante que TIPO_GRAFICO existe e é string
        if 'TIPO_GRAFICO' not in df_ind.columns:
            logging.warning("Coluna 'TIPO_GRAFICO' não encontrada em indicadores.csv. Adicionando como 'S' (Simples) por padrão.")
            df_ind['TIPO_GRAFICO'] = 'S' # Valor padrão se a coluna não existir
        df_ind['TIPO_GRAFICO'] = df_ind['TIPO_GRAFICO'].fillna('S').astype(str).str.upper() # Garante que é string e maiúscula, padrão 'S'
        # Filtra por RBC == 1
        return df_ind.loc[df_ind['RBC'] == 1]
    except Exception as e:
        # Retorna DataFrame vazio com as colunas esperadas em caso de erro
        # Modificado: Colunas esperadas atualizadas
        logging.exception("Erro ao carregar indicadores:")
        return pd.DataFrame(columns=['ID_INDICADOR', 'ID_META', 'ID_OBJETIVO', 'DESC_INDICADOR', 'VARIAVEIS', 'RBC', 'RANKING_ORDEM', 'TIPO_GRAFICO'])


@lru_cache(maxsize=1)
def load_sugestoes_visualizacao():
    try:
        return pd.read_csv('db/sugestoes_visualizacao.csv', low_memory=False, encoding='utf-8', dtype=str, sep=';', on_bad_lines='skip')
    except Exception as e:
        logging.exception("Erro ao carregar db/sugestoes_visualizacao.csv") # Adicionado logging
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
            logging.error("Colunas obrigatórias faltando em unidade_medida.csv: %s", [col for col in cols if col not in df_um.columns])
            return pd.DataFrame(columns=cols)
        for col in cols:
            df_um[col] = df_um[col].str.strip().str.strip('"')
        return df_um
    except Exception as e:
        logging.exception("Erro ao carregar db/unidade_medida.csv") # Adicionado logging
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
            if len(df_var.columns) >= 3:
                df_var = df_var.iloc[:, [0, 1, 2]]
                df_var.columns = cols
            elif len(df_var.columns) >= 2:
                df_var = df_var.iloc[:, [0, 1]]
                df_var.columns = cols[:2]
        return df_var
    except Exception as e:
        logging.exception("Erro ao carregar db/variavel.csv") # Adicionado logging
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
        logging.warning("Erro ao determinar meta inicial ou descrição: %s", e) # Modificado: Adicionado logging

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


# Função auxiliar para formatar número no padrão brasileiro (pt-BR)
def format_br(value):
    """Formats a number to Brazilian standard (dot for thousands, comma for decimal).
       Shows integer if no significant decimal part, otherwise shows up to 2 decimals,
       removing trailing zeros.
    """
    if pd.isna(value) or value is None:
        return ""
    # MODIFICADO: Lógica para tratar inteiros e remover zeros decimais
    try:
        f_value = float(value)
        # Check if it's effectively an integer
        if f_value == int(f_value):
            # Format as integer with thousands separators
            int_str = f"{int(f_value):,}".replace(",", ".")
            return int_str
        else:
            # Format as float with 2 decimal places first for consistent rounding
            formatted_str = f"{f_value:.2f}" # e.g., "1459.89", "15.00", "4.90"
            int_part, dec_part = formatted_str.split('.')

            # Format integer part with dots
            int_part_formatted = f"{int(int_part):,}".replace(",", ".")

            # Only add decimal part if it's not "00"
            if dec_part == "00":
                return int_part_formatted
            else:
                # Remove trailing zeros from decimal part *before* combining
                dec_part = dec_part.rstrip('0') # "89" -> "89", "90" -> "9"
                # Handle cases like "4.0" which become "4," -> should be "4"
                if not dec_part: # If rstrip removed everything (e.g., was "00")
                    return int_part_formatted # Return only integer part
                return f"{int_part_formatted},{dec_part}"

    except (ValueError, TypeError):
        logging.warning(f"Could not format value '{value}' to Brazilian standard.")
        return str(value) # Fallback


def create_visualization(df, indicador_id=None, selected_var=None, selected_filters=None):
    """Cria uma visualização (gráfico principal, ranking, mapa e tabela) com os dados do DataFrame, aplicando filtros."""
    # --- MODIFICADO: Inicializa main_chart_content com um Alerta padrão ---
    main_chart_content = dbc.Alert("Visualização não disponível devido a dados insuficientes ou erro.", color="warning", className="textCenter p-3")

    if df is None or df.empty:
        # Retorna o alerta padrão se o DF de entrada já for inválido
        return main_chart_content

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
                if selected_value is not None and col_code in df_filtered.columns:
                    # Convert selected value to string for comparison
                    selected_value_str = str(selected_value).strip()
                    # Compare using string representation of the column, without changing its type
                    # Convert column to string *before* filling NA and stripping
                    df_filtered = df_filtered[
                        df_filtered[col_code].astype(str).fillna('').str.strip() == selected_value_str
                    ]
                    if df_filtered.empty:
                        filter_name = constants.COLUMN_NAMES.get(col_code, col_code)
                        return dbc.Alert(f"Nenhum dado encontrado para o filtro '{filter_name}' = '{selected_value_str}'.", color="warning")

        if df_filtered.empty:
             return dbc.Alert("Nenhum dado encontrado após aplicar os filtros.", color="warning")

        # Adicionado: Verifica se todos os valores restantes são zero APÓS fillna(0)
        if not df_filtered.empty and (df_filtered['VLR_VAR'] == 0).all():
            # Constrói a mensagem explicando os filtros
            filter_desc = []
            if selected_var:
                 df_var_desc = load_variavel()
                 var_info = df_var_desc[df_var_desc['CODG_VAR'] == str(selected_var)]
                 var_name = var_info['DESC_VAR'].iloc[0] if not var_info.empty else f"Variável Cód: {selected_var}"
                 filter_desc.append(f"Variável: '{var_name}'")
            if selected_filters:
                 for col_code, value in selected_filters.items():
                      col_name = constants.COLUMN_NAMES.get(col_code, col_code)
                      # Tenta obter a descrição do valor se disponível
                      desc_col_code = 'DESC_' + col_code[5:]
                      value_desc = str(value)
                      if desc_col_code in df.columns:
                          try:
                              desc_map = df[[col_code, desc_col_code]].drop_duplicates()
                              desc_map[col_code] = desc_map[col_code].astype(str)
                              matched_desc = desc_map[desc_map[col_code] == str(value)]
                              if not matched_desc.empty:
                                  value_desc = matched_desc[desc_col_code].iloc[0]
                          except Exception:
                              pass # Mantém o código se a descrição falhar
                      filter_desc.append(f"{col_name}: '{value_desc}'")
            message = (
                "A combinação selecionada " +
                ("(" + ", ".join(filter_desc) + ") " if filter_desc else "") +
                "resultou apenas em valores iguais a zero. "
                "Não há dados a serem exibidos. Por favor, tente outra combinação de filtros."
            )
            return dbc.Alert(message, color="info", className="textCenter p-3")

        df_original_for_table = df_filtered.copy()

        # --- Adiciona/Garante Colunas de Descrição ---
        # Descrição UF
        if 'CODG_UND_FED' in df_filtered.columns:
            df_filtered['DESC_UND_FED'] = df_filtered['CODG_UND_FED'].astype(str).map(constants.UF_NAMES)
            df_filtered = df_filtered.dropna(subset=['DESC_UND_FED']) # Garante que temos UFs válidas
        elif 'DESC_UND_FED' not in df_filtered.columns:
             df_filtered['DESC_UND_FED'] = 'N/D'

        df_variavel_loaded = load_variavel()
        if 'CODG_VAR' in df_filtered.columns and not df_variavel_loaded.empty:
            df_filtered['CODG_VAR'] = df_filtered['CODG_VAR'].astype(str)
            df_variavel_loaded['CODG_VAR'] = df_variavel_loaded['CODG_VAR'].astype(str)

            # Merge para obter as descrições das variáveis
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
                        # Garante que ambas as colunas de chave são string para o merge
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

        # Garante que df_original_for_table também tenha as descrições dinâmicas
        for desc_col in processed_desc_cols:
            if desc_col not in df_original_for_table.columns and desc_col in df_filtered.columns:
                # Pega o código correspondente
                filter_col_code = 'CODG' + desc_col[4:]
                if filter_col_code in df_original_for_table.columns:
                     try:
                         merge_data_orig = df_filtered[[filter_col_code, desc_col]].drop_duplicates().copy()
                         df_original_for_table[filter_col_code] = df_original_for_table[filter_col_code].astype(str)
                         merge_data_orig[filter_col_code] = merge_data_orig[filter_col_code].astype(str)
                         df_original_for_table = pd.merge(df_original_for_table, merge_data_orig, on=filter_col_code, how='left')
                         df_original_for_table[desc_col] = df_original_for_table[desc_col].fillna('N/D')
                     except Exception:
                         df_original_for_table[desc_col] = 'N/D'

        # Adiciona colunas faltantes no df_original_for_table se necessário (UF, Var, UndMed)
        if 'DESC_UND_FED' not in df_original_for_table.columns and 'DESC_UND_FED' in df_filtered.columns:
            df_original_for_table['DESC_UND_FED'] = df_original_for_table['CODG_UND_FED'].astype(str).map(constants.UF_NAMES).fillna('N/D')
        if 'DESC_VAR' not in df_original_for_table.columns and 'DESC_VAR' in df_filtered.columns:
             if 'CODG_VAR' in df_original_for_table.columns and not df_variavel_loaded.empty:
                df_original_for_table['CODG_VAR'] = df_original_for_table['CODG_VAR'].astype(str)
                df_variavel_loaded['CODG_VAR'] = df_variavel_loaded['CODG_VAR'].astype(str)
                df_original_for_table = pd.merge(df_original_for_table, df_variavel_loaded[['CODG_VAR', 'DESC_VAR']], on='CODG_VAR', how='left')
                df_original_for_table['DESC_VAR'] = df_original_for_table['DESC_VAR'].fillna('N/D')
             else:
                df_original_for_table['DESC_VAR'] = 'N/D'
        if 'DESC_UND_MED' not in df_original_for_table.columns and 'DESC_UND_MED' in df_filtered.columns:
            if 'CODG_UND_MED' in df_original_for_table.columns and not df_unidade_medida_loaded.empty:
                df_original_for_table['CODG_UND_MED'] = df_original_for_table['CODG_UND_MED'].astype(str)
                df_unidade_medida_loaded['CODG_UND_MED'] = df_unidade_medida_loaded['CODG_UND_MED'].astype(str)
                df_original_for_table = pd.merge(df_original_for_table, df_unidade_medida_loaded[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
                df_original_for_table['DESC_UND_MED'] = df_original_for_table['DESC_UND_MED'].fillna('N/D')
            else:
                df_original_for_table['DESC_UND_MED'] = 'N/D'

        # Ordena e limpa dados numéricos
        df_filtered['CODG_ANO'] = df_filtered['CODG_ANO'].astype(str)
        df_filtered = df_filtered.sort_values('CODG_ANO')
        df_filtered['VLR_VAR'] = pd.to_numeric(df_filtered['VLR_VAR'], errors='coerce')
        df_filtered['VLR_VAR'] = df_filtered['VLR_VAR'].fillna(0) # Preenche NA com 0 *antes* de verificar

        # Verifica novamente se está vazio após fillna
        if df_filtered.empty:
            return dbc.Alert("Não há dados disponíveis para a combinação de filtros selecionada.", color="warning", className="textCenter p-3")

        # --- Definição Dinâmica das Colunas da Tabela AG Grid ---
        base_col_defs = [
            {"field": 'DESC_UND_FED', "headerName": 'Unidade Federativa'},
            {"field": 'CODG_ANO', "headerName": 'Ano'},
            {"field": 'DESC_VAR', "headerName": 'Variável'},
        ]
        dynamic_desc_col_defs = []
        dynamic_desc_col_names = set()
        # Usa df_original_for_table para determinar colunas da tabela
        present_columns_in_table = df_original_for_table.columns
        for filter_col_code in dynamic_filter_cols:
             desc_col_code = 'DESC_' + filter_col_code[5:]
             if desc_col_code in present_columns_in_table: # Verifica no DF da tabela
                  readable_name = constants.COLUMN_NAMES.get(desc_col_code, desc_col_code.replace('DESC_','').replace('_',' ').title())
                  if desc_col_code not in dynamic_desc_col_names: # Evita duplicados
                      dynamic_desc_col_defs.append({"field": desc_col_code, "headerName": readable_name})
                      dynamic_desc_col_names.add(desc_col_code)
        final_col_defs = base_col_defs + dynamic_desc_col_defs + [
             {"field": 'VLR_VAR', "headerName": 'Valor'},
             {"field": 'DESC_UND_MED', "headerName": 'Unidade de Medida'}
        ]
        columnDefs = []
        for col_def in final_col_defs:
            field_name = col_def['field']
            if field_name in present_columns_in_table: # Verifica novamente no DF da tabela
                 base_props = {"sortable": True, "filter": True, "minWidth": 100, "resizable": True, "wrapText": True, "autoHeight": True, "cellStyle": {"whiteSpace": "normal"}}
                 # Ajuste de flex baseado na coluna
                 if field_name == 'DESC_VAR': flex_value = 3
                 elif field_name == 'DESC_UND_FED' or field_name == 'DESC_UND_MED': flex_value = 2
                 elif field_name in dynamic_desc_col_names: flex_value = 2 # Aumenta um pouco para descrições dinâmicas
                 elif field_name == 'CODG_ANO' or field_name == 'VLR_VAR': flex_value = 1
                 else: flex_value = 1
                 columnDefs.append({**base_props, "field": field_name, "headerName": col_def['headerName'], "flex": flex_value})
        defaultColDef = {
            "minWidth": 100, "resizable": True, "wrapText": True, "autoHeight": True,
            "cellStyle": {"whiteSpace": "normal", 'textAlign': 'left'}
        }

        # --- Criação das Figuras dos Gráficos ---
        main_fig = go.Figure() # Inicializa a figura principal
        fig_ranking = go.Figure() # Inicializa a figura do ranking
        fig_map = go.Figure()  # Inicializa a figura do mapa

        # Obter anos únicos e ano padrão
        anos_unicos = sorted(df_filtered['CODG_ANO'].unique())
        num_anos = len(anos_unicos)
        ano_default = anos_unicos[-1] if anos_unicos else None

        # --- Modificado: Lê TIPO_GRAFICO e RANKING_ORDEM ---
        tipo_grafico = 'S' # Padrão: Coluna Simples
        ranking_ordem = 0 # Padrão (0 = maior para menor, 1 = menor para maior)
        if indicador_id and not df_indicadores.empty:
            indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
            if not indicador_info.empty:
                indicador_info_row = indicador_info.iloc[0]
                # Lê TIPO_GRAFICO
                if 'TIPO_GRAFICO' in indicador_info_row.index:
                    tipo_grafico = indicador_info_row['TIPO_GRAFICO'].strip().upper() or 'S' # Garante que não seja vazio, padrão 'S'

                # Lê RANKING_ORDEM
                if 'RANKING_ORDEM' in indicador_info_row.index:
                    try:
                        ranking_ordem_val = pd.to_numeric(indicador_info_row['RANKING_ORDEM'], errors='coerce')
                        if not pd.isna(ranking_ordem_val): ranking_ordem = int(ranking_ordem_val)
                    except (ValueError, TypeError): pass # Mantém padrão 0
        # --- Fim da Modificação ---

        # Define o número mínimo de anos para gráficos temporais (Linha ou Coluna Agrupada)
        min_years_for_temporal = 5
        # Determina se o gráfico principal deve ser temporal baseado no tipo e número de anos
        is_temporal = (tipo_grafico in ['L', 'C']) and (num_anos >= min_years_for_temporal)

        # --- Modificado: Criação do Gráfico Principal baseada em TIPO_GRAFICO ---
        if is_temporal:
            main_fig = go.Figure() # Inicializa figura para L ou C
            if tipo_grafico == 'L':
                # --- Lógica do Gráfico de Linha (Refatorado com go.Figure) ---
                main_fig = go.Figure() # Reinicializa para garantir que está vazia
                if 'DESC_UND_FED' in df_filtered.columns:
                    df_line_data = df_filtered.sort_values(['DESC_UND_FED', 'CODG_ANO'])
                    if not df_line_data.empty:
                        for uf in df_line_data['DESC_UND_FED'].unique():
                            df_state = df_line_data[df_line_data['DESC_UND_FED'] == uf]
                            # Adiciona verificação se df_state não está vazio
                            if df_state.empty: continue
                            # Modificado: Adiciona valor formatado ao customdata
                            customdata_state = np.column_stack((
                                np.full(len(df_state), uf),
                                df_state['DESC_UND_MED'].values,
                                df_state['VLR_VAR'].values, # Original value
                                df_state['VLR_VAR'].apply(format_br).values # Formatted value
                            ))
                            # Modificado: Usa a função format_br
                            text_values = df_state['VLR_VAR'].apply(format_br)
                            trace_name = f"<b>{uf}</b>" if uf == 'Goiás' else uf
                            color_map = {
                                'Goiás': '#229846', 'Maranhão': '#D2B48C', 'Distrito Federal': '#636efa',
                                'Mato Grosso': '#ab63fa', 'Mato Grosso do Sul': '#ffa15a', 'Rondônia': '#19d3f3',
                                'Tocantins': '#ff6692', 'Brasil': '#FF0000' # Adiciona Brasil
                            }
                            line_color = color_map.get(uf)
                            line_width = 6 if uf == 'Goiás' else 2

                            main_fig.add_trace(go.Scatter(
                                x=df_state['CODG_ANO'], y=df_state['VLR_VAR'], name=trace_name,
                                customdata=customdata_state, text=text_values, mode='lines+markers+text',
                                texttemplate='%{text}', textposition='top center', textfont=dict(size=10),
                                marker=dict(size=10, symbol='circle', line=dict(width=1, color='white')),
                                line=dict(width=line_width, color=line_color),
                                hovertemplate=(
                                    "<b>%{customdata[0]}</b><br>" # UF do customdata
                                    "Ano: %{x}<br>"
                                    "Valor: %{customdata[3]}<br>" # Modificado: Usa customdata[3] (pré-formatado)
                                    "Unidade: %{customdata[1]}<extra></extra>"
                                )
                            ))

                        max_y_line = df_line_data['VLR_VAR'].max()
                        y_range_line = [0, max_y_line * 1.15]

                        layout_updates_line = DEFAULT_LAYOUT.copy()
                        layout_updates_line.update({
                            'xaxis': dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), tickangle=45),
                            'yaxis': dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d', range=y_range_line)
                        })
                        unique_years_line = sorted(df_line_data['CODG_ANO'].unique())
                        layout_updates_line['xaxis']['ticktext'] = [f"<b>{x}</b>" for x in unique_years_line]
                        layout_updates_line['xaxis']['tickvals'] = unique_years_line
                        main_fig.update_layout(layout_updates_line)
                    else:
                        main_fig = go.Figure().update_layout(title='Dados insuficientes para o gráfico de linha.', xaxis={'visible': False}, yaxis={'visible': False})

                else: # Gráfico de linha sem UF (e.g., só 'Brasil')
                    df_line_data = df_filtered.sort_values('CODG_ANO')
                    if not df_line_data.empty:
                         # Adapta customdata para não ter UF, adiciona valor formatado
                         customdata_line_no_uf = np.column_stack((
                             df_line_data['DESC_UND_MED'].values,
                             df_line_data['VLR_VAR'].values, # Original value
                             df_line_data['VLR_VAR'].apply(format_br).values # Formatted value
                         ))
                         # Modificado: Usa a função format_br
                         text_values = df_line_data['VLR_VAR'].apply(format_br)
                         main_fig.add_trace(go.Scatter(
                             x=df_line_data['CODG_ANO'], y=df_line_data['VLR_VAR'], name='Valor',
                             customdata=customdata_line_no_uf, text=text_values, mode='lines+markers+text',
                             line=dict(color='#229846', width=3), # Cor padrão ou específica
                             hovertemplate=(
                                 "Ano: %{x}<br>"
                                 "Valor: %{customdata[2]}<br>" # Modificado: Usa customdata[2] (pré-formatado)
                                 "Unidade: %{customdata[0]}<extra></extra>"
                             )
                         ))

                         max_y_line_no_uf = df_line_data['VLR_VAR'].max()
                         y_range_line_no_uf = [0, max_y_line_no_uf * 1.15]

                         layout_updates_line_no_uf = DEFAULT_LAYOUT.copy()
                         layout_updates_line_no_uf.update({
                             'showlegend': False,
                             'xaxis': dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), tickangle=45),
                             'yaxis': dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d', range=y_range_line_no_uf)
                         })
                         unique_years_line_no_uf = sorted(df_line_data['CODG_ANO'].unique())
                         layout_updates_line_no_uf['xaxis']['ticktext'] = [f"<b>{x}</b>" for x in unique_years_line_no_uf]
                         layout_updates_line_no_uf['xaxis']['tickvals'] = unique_years_line_no_uf
                         main_fig.update_layout(layout_updates_line_no_uf)
                    else:
                         main_fig = go.Figure().update_layout(title='Dados insuficientes para o gráfico de linha.', xaxis={'visible': False}, yaxis={'visible': False})

            elif tipo_grafico == 'C':
                # --- Lógica do Gráfico de Barras AGRUPADO POR ANO (Refatorado com go.Figure) ---
                main_fig = go.Figure()
                if 'DESC_UND_FED' in df_filtered.columns and 'CODG_ANO' in df_filtered.columns:
                    df_bar_grouped_data = df_filtered.sort_values(['CODG_ANO', 'DESC_UND_FED'])
                    if not df_bar_grouped_data.empty:
                        color_map = {
                            'Goiás': '#229846', 'Maranhão': '#D2B48C', 'Distrito Federal': '#636efa',
                            'Mato Grosso': '#ab63fa', 'Mato Grosso do Sul': '#ffa15a', 'Rondônia': '#19d3f3',
                            'Tocantins': '#ff6692', 'Brasil': '#FF0000' # Adiciona Brasil
                        }
                        for uf in df_bar_grouped_data['DESC_UND_FED'].unique():
                            df_state = df_bar_grouped_data[df_bar_grouped_data['DESC_UND_FED'] == uf]
                            if df_state.empty: continue # Pula UF sem dados
                            # Modificado: Adiciona valor formatado ao customdata
                            customdata_state = np.column_stack((
                                np.full(len(df_state), uf),
                                df_state['DESC_UND_MED'].values,
                                df_state['VLR_VAR'].values, # Original value
                                df_state['VLR_VAR'].apply(format_br).values # Formatted value
                            ))
                            # Modificado: Usa a função format_br
                            text_values = df_state['VLR_VAR'].apply(format_br)
                            trace_name = f"<b>{uf}</b>" if uf == 'Goiás' else uf
                            bar_color = color_map.get(uf)

                            main_fig.add_trace(go.Bar(
                                x=df_state['CODG_ANO'], y=df_state['VLR_VAR'], name=trace_name,
                                customdata=customdata_state, text=text_values,
                                texttemplate='<b>%{text}</b>', # <--- MODIFICADO
                                textposition='outside', marker_color=bar_color, marker_line_width=1.5,
                                hovertemplate=(
                                    "<b>%{customdata[0]}</b><br>" # UF do customdata
                                    "Ano: %{x}<br>"
                                    "Valor: %{customdata[3]}<br>" # Modificado: Usa customdata[3] (pré-formatado)
                                    "Unidade: %{customdata[1]}<extra></extra>"
                                )
                            ))

                        max_y_grouped = df_bar_grouped_data['VLR_VAR'].max()
                        y_range_grouped = [0, max_y_grouped * 1.15]

                        layout_updates_bar_grouped = DEFAULT_LAYOUT.copy()
                        layout_updates_bar_grouped.update({
                            'barmode': 'group',
                            'xaxis': dict(showgrid=True, tickfont=dict(size=12, color='black'), tickangle=45, title=None),
                            'yaxis': dict(showgrid=True, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d', range=y_range_grouped)
                        })
                        unique_years_bar = sorted(df_bar_grouped_data['CODG_ANO'].unique())
                        layout_updates_bar_grouped['xaxis']['ticktext'] = [f"<b>{x}</b>" for x in unique_years_bar]
                        layout_updates_bar_grouped['xaxis']['tickvals'] = unique_years_bar
                        main_fig.update_layout(layout_updates_bar_grouped)
                    else:
                        main_fig = go.Figure().update_layout(title='Dados insuficientes para o gráfico de barras agrupado.', xaxis={'visible': False}, yaxis={'visible': False})
                else:
                    # Caso sem UF mas com série temporal -> Barras simples por ano
                    df_bar_no_uf = df_filtered.sort_values('CODG_ANO')
                    if not df_bar_no_uf.empty:
                        # Modificado: Adiciona valor formatado ao customdata
                        customdata_bar_no_uf = np.column_stack((
                            df_bar_no_uf['DESC_UND_MED'].values,
                            df_bar_no_uf['VLR_VAR'].values, # Original value
                            df_bar_no_uf['VLR_VAR'].apply(format_br).values # Formatted value
                        ))
                        # Modificado: Usa a função format_br
                        text_values = df_bar_no_uf['VLR_VAR'].apply(format_br)
                        main_fig.add_trace(go.Bar(
                            x=df_bar_no_uf['CODG_ANO'],
                            y=df_bar_no_uf['VLR_VAR'],
                            text=text_values, texttemplate='<b>%{text}</b>', textposition='outside', # <-- MODIFICADO
                            marker_color='#229846', # Cor padrão ou específica
                            hovertemplate=(
                                "Ano: %{x}<br>"
                                "Valor: %{customdata[2]}<br>" # Modificado: Usa customdata[2] (pré-formatado)
                                "Unidade: %{customdata[0]}<extra></extra>"
                            )
                        ))

                        max_y_bar_no_uf = df_bar_no_uf['VLR_VAR'].max()
                        y_range_bar_no_uf = [0, max_y_bar_no_uf * 1.15]
                        layout_updates_bar_no_uf = DEFAULT_LAYOUT.copy()
                        layout_updates_bar_no_uf.update({
                            'showlegend': False,
                            'xaxis': dict(showgrid=True, tickfont=dict(size=12, color='black'), tickangle=45, title=None),
                            'yaxis': dict(showgrid=True, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d', range=y_range_bar_no_uf)
                        })
                        unique_years_bar_no_uf = sorted(df_bar_no_uf['CODG_ANO'].unique())
                        layout_updates_bar_no_uf['xaxis']['ticktext'] = [f"<b>{x}</b>" for x in unique_years_bar_no_uf]
                        layout_updates_bar_no_uf['xaxis']['tickvals'] = unique_years_bar_no_uf
                        main_fig.update_layout(layout_updates_bar_no_uf)
                    else:
                        main_fig = go.Figure().update_layout(title='Dados insuficientes para o gráfico de barras.', xaxis={'visible': False}, yaxis={'visible': False})

            # --- MODIFICADO: Atribui main_chart_content AQUI para L e C ---
            main_chart_content = dcc.Graph(id={'type': 'main-chart', 'index': indicador_id}, figure=main_fig)

        else: # Não é temporal (tipo_grafico == 'S' ou 'B', ou poucos anos para 'L'/'C')
             if tipo_grafico == 'B':
                 # --- MODIFICADO: Lógica do Gráfico Boxplot Interativo por Ano ---
                 anos_unicos_box = sorted(df_filtered['CODG_ANO'].unique()) # Obtém todos os anos
                 ano_default_box = anos_unicos_box[-1] if anos_unicos_box else None
                 main_chart_content = dbc.Alert("Boxplot requer dados por UF e pelo menos um ano.", color="warning", className="textCenter p-3") # Padrão

                 if 'DESC_UND_FED' in df_filtered.columns and ano_default_box:
                     # Filtra para o ano inicial
                     df_boxplot_initial = df_filtered[df_filtered['CODG_ANO'] == ano_default_box].copy()

                     if not df_boxplot_initial.empty:
                         # --- Criação da Figura Inicial ---
                         df_boxplot_initial = df_boxplot_initial.sort_values('DESC_UND_FED')
                         # Adiciona valor formatado ao customdata
                         df_boxplot_initial['VLR_VAR_FORMATADO'] = df_boxplot_initial['VLR_VAR'].apply(format_br)

                         fig_boxplot_initial = px.box(
                             df_boxplot_initial, x='DESC_UND_FED', y='VLR_VAR', points="all",
                             color='DESC_UND_FED',
                             hover_data={
                                 'DESC_UND_FED': True, 'VLR_VAR': False,
                                 'VLR_VAR_FORMATADO': True, 'DESC_UND_MED': True
                             }
                         )
                         fig_boxplot_initial.update_traces(
                             hovertemplate="<b>%{x}</b><br>Valor: %{customdata[0]}<br>Unidade: %{customdata[1]}<extra></extra>",
                             customdata=np.column_stack((
                                 df_boxplot_initial['VLR_VAR_FORMATADO'].values,
                                 df_boxplot_initial['DESC_UND_MED'].values
                             ))
                         )
                         # Layout
                         layout_updates_boxplot = DEFAULT_LAYOUT.copy()
                         layout_updates_boxplot.update({
                             'yaxis': dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d'),
                             'xaxis': dict(showgrid=False, tickfont=dict(size=12, color='black'), tickangle=45, title=None, categoryorder='array', categoryarray=sorted(df_boxplot_initial['DESC_UND_FED'].unique())),
                             'showlegend': False, 'margin': dict(l=60, r=50, t=50, b=120)
                         })
                         all_ufs_box_initial = sorted(df_boxplot_initial['DESC_UND_FED'].unique())
                         x_ticktext_box_initial = [f"<b>{label}</b>" if label == 'Goiás' else f"{label}" for label in all_ufs_box_initial]
                         layout_updates_boxplot['xaxis']['ticktext'] = x_ticktext_box_initial
                         layout_updates_boxplot['xaxis']['tickvals'] = all_ufs_box_initial
                         fig_boxplot_initial.update_layout(layout_updates_boxplot)
                         # --- Fim Figura Inicial ---

                         # --- Monta o Conteúdo com Dropdown e Gráfico ---
                         main_chart_content = html.Div([
                             html.Label("Ano:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                             dcc.Dropdown(
                                 id={'type': 'year-dropdown-boxplot', 'index': indicador_id},
                                 options=[{'label': ano, 'value': ano} for ano in anos_unicos_box],
                                 value=ano_default_box,
                                 clearable=False,
                                 style={'width': '100%', 'marginBottom': '10px'}
                             ),
                             dcc.Graph(id={'type': 'boxplot-chart', 'index': indicador_id}, figure=fig_boxplot_initial)
                         ])
                         # --- Fim Conteúdo ---
                     else: # Alinhado com 'if not df_boxplot_initial.empty:'
                         # Se não houver dados nem para o ano default, mostra alerta com dropdown vazio
                         main_chart_content = html.Div([
                             html.Label("Ano:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                             dcc.Dropdown(
                                 id={'type': 'year-dropdown-boxplot', 'index': indicador_id},
                                 options=[{'label': ano, 'value': ano} for ano in anos_unicos_box], # Usa anos totais se houver
                                 value=ano_default_box,
                                 clearable=False,
                                 disabled=not anos_unicos_box, # Desabilita se não houver anos
                                 style={'width': '100%', 'marginBottom': '10px'}
                             ),
                             dbc.Alert(f"Dados insuficientes para Boxplot no ano {ano_default_box}.", color="warning", className="textCenter p-3")
                         ])

                 # IMPORTANTE: Não atribui mais main_fig aqui para o tipo 'B'.
                 # main_chart_content já foi definido acima.

             else: # tipo_grafico == 'S' (ou 'L'/'C' com poucos anos) -> Gráfico de Coluna Simples # Alinhado com 'if tipo_grafico == \'B\':'
                 # --- Lógica do Gráfico de Barras SIMPLES (Último Ano) ---
                 main_fig = go.Figure() # Inicializa figura para S

                 # Prepara dados para barras simples (último ano)
                 df_bar_simple_data = pd.DataFrame()
                 if ano_default:
                     df_bar_simple_data = df_filtered[df_filtered['CODG_ANO'] == ano_default].copy()

                 if not df_bar_simple_data.empty:
                     # Adiciona descrições se necessário (UF, Und Medida)
                     if 'DESC_UND_FED' not in df_bar_simple_data.columns and 'CODG_UND_FED' in df_bar_simple_data.columns:
                         df_bar_simple_data['DESC_UND_FED'] = df_bar_simple_data['CODG_UND_FED'].astype(str).map(constants.UF_NAMES).fillna('N/D')
                     elif 'DESC_UND_FED' not in df_bar_simple_data.columns:
                          df_bar_simple_data['DESC_UND_FED'] = 'Brasil' # Ou algum padrão

                     if 'DESC_UND_MED' not in df_bar_simple_data.columns and 'CODG_UND_MED' in df_bar_simple_data.columns:
                        df_um = load_unidade_medida()
                        if not df_um.empty:
                             df_um['CODG_UND_MED'] = df_um['CODG_UND_MED'].astype(str)
                             df_bar_simple_data['CODG_UND_MED'] = df_bar_simple_data['CODG_UND_MED'].astype(str)
                             df_bar_simple_data = pd.merge(df_bar_simple_data, df_um[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
                             df_bar_simple_data['DESC_UND_MED'] = df_bar_simple_data['DESC_UND_MED'].fillna('N/D')
                        else:
                             df_bar_simple_data['DESC_UND_MED'] = 'N/D'
                     elif 'DESC_UND_MED' not in df_bar_simple_data.columns:
                         df_bar_simple_data['DESC_UND_MED'] = 'N/D'

                     # Ordena e formata
                     df_bar_simple_data = df_bar_simple_data.sort_values('VLR_VAR', ascending=False)
                     df_bar_simple_data['VLR_VAR_FORMATADO'] = df_bar_simple_data['VLR_VAR'].apply(format_br)

                     # --- MODIFICADO: Define o mapa de cores igual aos gráficos temporais ---
                     color_map_simple = {
                         'Goiás': '#229846', 'Maranhão': '#D2B48C', 'Distrito Federal': '#636efa',
                         'Mato Grosso': '#ab63fa', 'Mato Grosso do Sul': '#ffa15a', 'Rondônia': '#19d3f3',
                         'Tocantins': '#ff6692', 'Brasil': '#FF0000' # Adiciona Brasil
                     }
                     # --- FIM DA MODIFICAÇÃO ---

                     # Cria a figura
                     main_fig = px.bar(
                         df_bar_simple_data, x='DESC_UND_FED', y='VLR_VAR',
                         text='VLR_VAR_FORMATADO',
                         # --- MODIFICADO: Usa color e color_discrete_map ---
                         color='DESC_UND_FED',  # Colore com base no estado
                         color_discrete_map=color_map_simple, # Aplica o mapa de cores definido
                         # color_discrete_sequence=['#229846'] * len(df_bar_simple_data), # Linha removida
                         # --- FIM DA MODIFICAÇÃO ---
                         hover_data={
                             'DESC_UND_FED': True,
                             'VLR_VAR': False,
                             'VLR_VAR_FORMATADO': True,
                             'DESC_UND_MED': True
                         }
                     )
                     main_fig.update_traces(
                         texttemplate='<b>%{text}</b>', textposition='outside',
                         hovertemplate="<b>%{x}</b><br>Valor: %{customdata[0]}<br>Unidade: %{customdata[1]}<extra></extra>",
                         customdata=np.column_stack((
                            df_bar_simple_data['VLR_VAR_FORMATADO'].values,
                            df_bar_simple_data['DESC_UND_MED'].values
                         ))
                     )

                     max_y_simple = df_bar_simple_data['VLR_VAR'].max()
                     y_range_simple = [0, max_y_simple * 1.15]
                     layout_updates_bar_simple = DEFAULT_LAYOUT.copy()
                     layout_updates_bar_simple.update({
                         'xaxis': dict(showgrid=False, tickfont=dict(size=12, color='black'), tickangle=45, title=None),
                         'yaxis': dict(showgrid=True, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d', range=y_range_simple),
                         'showlegend': False
                     })
                     all_ufs_simple = sorted(df_bar_simple_data['DESC_UND_FED'].unique())
                     x_ticktext_simple = [f"<b>{label}</b>" if label == 'Goiás' else f"{label}" for label in all_ufs_simple]
                     layout_updates_bar_simple['xaxis']['ticktext'] = x_ticktext_simple
                     layout_updates_bar_simple['xaxis']['tickvals'] = all_ufs_simple
                     main_fig.update_layout(layout_updates_bar_simple)

                 else:
                     main_fig = go.Figure().update_layout(title=f'Dados insuficientes para Gráfico de Barras no ano {ano_default}.', xaxis={'visible': False}, yaxis={'visible': False})

                 # --- ADICIONADO: Atribui main_chart_content AQUI para S ---
                 main_chart_content = dcc.Graph(id={'type': 'main-chart', 'index': indicador_id}, figure=main_fig)


        # --- Criação do Mapa (se houver UF e ano) ---
        map_content = dbc.Alert("Mapa não disponível (requer dados por Unidade Federativa).", color="info", className="textCenter p-3") # Inicialização padrão
        map_center = {'lat': -12.95984198, 'lon': -53.27299730}
        # Obtém todos os anos únicos disponíveis APÓS filtros gerais, para usar no dropdown
        anos_unicos_map = sorted(df_filtered['CODG_ANO'].unique()) if 'CODG_ANO' in df_filtered.columns else []

        if 'DESC_UND_FED' in df_filtered.columns and ano_default:
            # Filtra dados para o ano padrão inicial
            df_map_data_initial = df_filtered[df_filtered['CODG_ANO'] == ano_default].copy()

            # Conteúdo padrão dentro do Div (será substituído se o mapa puder ser gerado)
            map_children_content = dbc.Alert(f"Mapa não disponível para o ano {ano_default}.", color="info", className="textCenter p-3")

            if not df_map_data_initial.empty:
                counts_per_uf_map = df_map_data_initial['DESC_UND_FED'].value_counts()
                if (counts_per_uf_map > 1).any():
                     # MODIFICADO: Define o ALERTA como conteúdo filho, mas o Div com dropdown será criado abaixo
                     map_children_content = dbc.Alert(
                         "Mapa não pode ser gerado: múltiplos valores por UF para o ano selecionado. "
                         "Aplique filtros adicionais se disponíveis.", color="warning", className="textCenter p-3"
                     )
                else:
                    # Tenta gerar o mapa se os dados do ano inicial são válidos
                    try:
                        with open('db/br_geojson.json', 'r', encoding='utf-8') as f: geojson = json.load(f)
                        und_med_map = df_map_data_initial['DESC_UND_MED'].dropna().iloc[0] if not df_map_data_initial['DESC_UND_MED'].dropna().empty else ''
                        df_map_data_initial['VLR_VAR_FORMATADO'] = df_map_data_initial['VLR_VAR'].apply(format_br)

                        fig_map = px.choropleth(
                            df_map_data_initial, geojson=geojson, locations='DESC_UND_FED',
                            featureidkey='properties.name', color='VLR_VAR',
                            color_continuous_scale=[[0.0, 'rgba(34, 152, 70, 0.2)'], [1.0, 'rgba(34, 152, 70, 1)']]
                        )
                        geos_update = dict(
                            visible=False, showcoastlines=True, coastlinecolor="White",
                            showland=True, landcolor="white", showframe=False,
                            projection=dict(type='mercator', scale=15), center=map_center
                        )
                        fig_map.update_geos(**geos_update)
                        fig_map.update_traces(
                            marker_line_color='white', marker_line_width=1,
                            customdata=df_map_data_initial[['VLR_VAR_FORMATADO']],
                            hovertemplate="<b>%{location}</b><br>Valor: %{customdata[0]}" + (f" {und_med_map}" if und_med_map else "") + "<extra></extra>"
                        )
                        fig_map.update_layout(coloraxis_colorbar_title_text='')

                        # MODIFICADO: Se o mapa foi gerado com sucesso, define o Graph como conteúdo filho
                        map_children_content = dcc.Graph(id={'type': 'choropleth-map', 'index': indicador_id}, figure=fig_map)

                    except Exception as map_err:
                         logging.warning(f"Erro ao gerar mapa inicial: {map_err}")
                         # MODIFICADO: Define alerta de erro como conteúdo filho
                         map_children_content = dbc.Alert("Erro ao gerar o mapa.", color="danger", className="textCenter p-3")
            # else: # Se df_map_data_initial estava vazio
                 # map_children_content já está definido como Alerta "não disponível para ano X"

            # --- MODIFICADO: Monta o map_content final com Dropdown + Conteúdo Filho (Graph ou Alert) ---
            # Isso garante que o Dropdown sempre apareça se houver dados por UF
            map_content = html.Div([
                html.Label("Ano:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                dcc.Dropdown(
                    id={'type': 'year-dropdown-map', 'index': indicador_id},
                    options=[{'label': ano, 'value': ano} for ano in anos_unicos_map], # Usa todos os anos disponíveis
                    value=ano_default,
                    clearable=False,
                    disabled=not anos_unicos_map, # Desabilita se não houver anos
                    style={'width': '100%', 'marginBottom': '10px'}
                ),
                # Container para o Graph ou Alert
                html.Div(id={'type': 'map-container', 'index': indicador_id}, children=map_children_content)
            ])
        # else: # Se não houver 'DESC_UND_FED' ou 'ano_default'
            # map_content permanece como o Alert inicial "Mapa não disponível (requer dados...)"

        # Inicialização do ranking (mantém como antes)
        ranking_content = dbc.Alert("Ranking não disponível (requer dados por Unidade Federativa).", color="info", className="textCenter p-3")

        # --- Monta o Layout da Visualização com Abas ---
        graph_layout = []

        # Conteúdo do gráfico principal (sempre exibido)
        # !! MODIFICADO !! A variável 'main_chart_content' agora contém ou o dcc.Graph (tipos L, C, S)
        # OU o html.Div com Dropdown+Graph (tipo B).
        # O ID do gráfico principal ('main-chart') não é mais usado para o tipo 'B'.
        # O callback de atualização do boxplot usará {'type': 'boxplot-chart', 'index': MATCH}

        # Cria as abas para Ranking e Mapa
        tabs_content = []
        # Adiciona aba de Ranking
        if 'DESC_UND_FED' in df_filtered.columns:
             # --- Lógica para gerar ranking_content (com dropdown de ano) ---
             anos_ranking = sorted(df_filtered['CODG_ANO'].unique())
             ano_default_ranking = anos_ranking[-1] if anos_ranking else None

             # --- MODIFICADO: Define o conteúdo inicial para o container do ranking ---
             initial_ranking_children = dbc.Alert(f"Ranking não disponível para o ano {ano_default_ranking}.", color="info", className="textCenter p-3") # Padrão: Alerta

             # Tenta gerar a figura/gráfico inicial se possível
             if ano_default_ranking:
                 try:
                     # Reutiliza a lógica do callback update_ranking_chart para gerar o conteúdo inicial
                     # Passa os dados filtrados gerais (df_filtered) e o ano padrão
                     df_ranking_initial_check = df_filtered[df_filtered['CODG_ANO'] == ano_default_ranking].copy()

                     if df_ranking_initial_check.empty:
                         initial_ranking_children = dbc.Alert(f'Ranking não disponível para {ano_default_ranking} com filtros aplicados.', color="warning", className="textCenter p-3")
                     elif df_ranking_initial_check['DESC_UND_FED'].nunique() != len(df_ranking_initial_check):
                         initial_ranking_children = dbc.Alert('Ranking não gerado (inicial): múltiplos valores por UF.', color="warning", className="textCenter p-3")
                     else:
                         # Se os dados são válidos, tenta gerar a figura
                         ranking_ordem = 0
                         indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
                         if not indicador_info.empty and 'RANKING_ORDEM' in indicador_info.columns:
                             try:
                                 ranking_ordem_val = pd.to_numeric(indicador_info['RANKING_ORDEM'].iloc[0], errors='coerce')
                                 if not pd.isna(ranking_ordem_val): ranking_ordem = int(ranking_ordem_val)
                             except (ValueError, TypeError): pass

                         ascending_rank = (ranking_ordem == 0)
                         df_ranking_ano_fig = df_ranking_initial_check.sort_values('VLR_VAR', ascending=ascending_rank)

                         # Adiciona DESC_UND_MED se necessário para hovertemplate
                         if 'DESC_UND_MED' not in df_ranking_ano_fig.columns and 'CODG_UND_MED' in df_ranking_ano_fig.columns:
                             df_um_rank = load_unidade_medida()
                             if not df_um_rank.empty:
                                 df_um_rank['CODG_UND_MED'] = df_um_rank['CODG_UND_MED'].astype(str)
                                 df_ranking_ano_fig['CODG_UND_MED'] = df_ranking_ano_fig['CODG_UND_MED'].astype(str)
                                 df_ranking_ano_fig = pd.merge(df_ranking_ano_fig, df_um_rank[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
                                 df_ranking_ano_fig['DESC_UND_MED'] = df_ranking_ano_fig['DESC_UND_MED'].fillna('N/D')
                             else:
                                 df_ranking_ano_fig['DESC_UND_MED'] = 'N/D'
                         elif 'DESC_UND_MED' not in df_ranking_ano_fig.columns:
                             df_ranking_ano_fig['DESC_UND_MED'] = 'N/D'

                         fig_ranking_initial = go.Figure()
                         goias_color = 'rgba(34, 152, 70, 1)'
                         other_color = 'rgba(34, 152, 70, 0.2)'
                         for _, row in df_ranking_ano_fig.iterrows():
                             uf = row['DESC_UND_FED']
                             valor = row['VLR_VAR']
                             und_med = row.get('DESC_UND_MED', 'N/D')
                             bar_color = goias_color if uf == 'Goiás' else other_color
                             text_value = format_br(valor)
                             fig_ranking_initial.add_trace(go.Bar(
                                 y=[uf], x=[valor], name=uf, orientation='h',
                                 marker_color=bar_color, text=text_value,
                                 textposition='outside', texttemplate='<b>%{text}</b>',
                                 hovertemplate=f"<b>{uf}</b><br>Valor: {text_value}<br>Unidade: {und_med}<extra></extra>"
                             ))

                         max_x_ranking = df_ranking_ano_fig['VLR_VAR'].max() if not df_ranking_ano_fig.empty else 0
                         x_range_ranking = [0, max_x_ranking * 1.15]
                         fig_ranking_initial.update_layout(
                             xaxis_title=None, yaxis_title=None,
                             yaxis=dict(showgrid=False, tickfont=dict(size=12, color='black'), categoryorder='array', categoryarray=df_ranking_ano_fig['DESC_UND_FED'].tolist()),
                             xaxis=dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), range=x_range_ranking, tickformat='d'),
                             showlegend=False, margin=dict(l=150, r=20, t=30, b=30), bargap=0.1
                         )
                         # Se chegou aqui, o conteúdo inicial é o gráfico
                         initial_ranking_children = dcc.Graph(id={'type': 'ranking-chart', 'index': indicador_id}, figure=fig_ranking_initial)

                 except Exception as initial_rank_err:
                     logging.warning("Erro ao gerar gráfico inicial do ranking: %s", initial_rank_err)
                     initial_ranking_children = dbc.Alert(f'Erro ao gerar ranking inicial para {ano_default_ranking}.', color="danger", className="textCenter p-3")
                     # Garante que a figura esteja vazia em caso de erro na geração
                     fig_ranking_initial = go.Figure().update_layout(title=None, xaxis={'visible': False}, yaxis={'visible': False})
             else:
                  # Se não há ano default, a figura inicial deve ser vazia mesmo
                  fig_ranking_initial = go.Figure().update_layout(title=None, xaxis={'visible': False}, yaxis={'visible': False})
                  # O alerta padrão já foi definido

             # Monta o conteúdo completo da aba Ranking - Nível 1
             ranking_content = html.Div([
                 html.Label("Ano:", style={'fontWeight': 'bold', 'marginBottom': '5px', 'display': 'block'}),
                 dcc.Dropdown(
                     id={'type': 'year-dropdown-ranking', 'index': indicador_id},
                     options=[{'label': ano, 'value': ano} for ano in anos_ranking],
                     value=ano_default_ranking,
                     clearable=False,
                     disabled=not anos_ranking,
                     style={'width': '100%', 'marginBottom': '10px'}
                 ),
                 html.Div(
                     id={'type': 'ranking-container', 'index': indicador_id},
                     # MODIFICADO: Usa o conteúdo (Graph ou Alert) gerado acima
                     children=initial_ranking_children
                 )
             ])
             # --- Fim Lógica Ranking --- Nível 1
             tabs_content.append(dbc.Tab(ranking_content, label="Ranking", tab_id=f'tab-ranking-{indicador_id}', id={'type': 'tab-ranking', 'index': indicador_id}))

        # Adiciona aba de Mapa - Nível 0 (alinhado com o if principal)
        if 'DESC_UND_FED' in df_filtered.columns:
            tabs_content.append(dbc.Tab(map_content, label="Mapa Coroplético", tab_id=f'tab-map-{indicador_id}', id={'type': 'tab-map', 'index': indicador_id}))

        # Container para as abas (se existirem)
        tabs_container = html.Div() # Vazio por padrão
        if tabs_content:
             tabs_container = dbc.Tabs(
                 id={'type': 'visualization-tabs', 'index': indicador_id},
                 children=tabs_content,
                 active_tab=tabs_content[0].tab_id if tabs_content else None
             )

        # Monta o layout final com gráfico principal e abas lado a lado
        # Usa a variável main_chart_content diretamente
        visualization_card_content = dbc.CardBody([
            # --- MODIFICADO: Alterado para align-items-end ---
            dbc.Row([
                dbc.Col(main_chart_content, md=7, xs=12, className="mb-4 mb-md-0 h-100"), # Coluna Gráfico Principal
                dbc.Col(tabs_container, md=5, xs=12, className="h-100") # Coluna Abas
            ], className="align-items-end") # Alinha o conteúdo das colunas na parte inferior
            # --- FIM DA MODIFICAÇÃO ---
        ])

        graph_layout.append(dbc.Row([
            dbc.Col(dbc.Card(visualization_card_content, className="mb-4"), width=12)
        ]))

        # Adiciona Tabela Detalhada sempre
        graph_layout.append(dbc.Row([
            dbc.Col(dbc.Card([
                html.H5("Dados Detalhados", className="mt-4", style={'marginLeft': '20px'}),
                dbc.CardBody(dag.AgGrid(
                    id={'type': 'detail-table', 'index': indicador_id},
                    # Usa df_original_for_table para a tabela AG Grid
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
        # Modificado: Usa logging.exception em vez de print/traceback
        logging.exception("Erro em create_visualization para %s:", indicador_id)
        return dbc.Alert(f"Erro ao gerar visualização para {indicador_id}. Consulte os logs.", color="danger")

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


# Callback para carregar indicadores sob demanda quando uma aba é clicada
@app.callback(
    [Output({'type': 'lazy-load-container', 'index': MATCH}, 'children'),
     Output({'type': 'spinner-indicator', 'index': MATCH}, 'style')],
    Input('tabs-indicadores', 'active_tab'),
    State({'type': 'lazy-load-container', 'index': MATCH}, 'id'),
    prevent_initial_call=True
)
def load_indicator_on_demand(active_tab, container_id): # <--- DEFINIÇÃO DA FUNÇÃO
    # Só carrega se a aba estiver ativa
    if not active_tab or not container_id:
        raise PreventUpdate

    # Obtém o ID do indicador
    indicador_id = container_id['index']
    logging.debug("Tentando carregar indicador sob demanda: %s (Aba ativa: %s)", indicador_id, active_tab)

    # Ignora o placeholder
    if indicador_id == 'placeholder':
        raise PreventUpdate

    # Verifica se a aba ativa corresponde a este indicador
    if active_tab != f"tab-{indicador_id}":
        raise PreventUpdate

    # --- INÍCIO DO BLOCO TRY...EXCEPT ---
    try:
        # Carrega os dados do indicador
        logging.debug("Carregando dados para %s", indicador_id)
        df_dados = load_dados_indicador_cache(indicador_id)

        # Busca informações do indicador (descrição, etc.)
        indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
        if indicador_info.empty:
            logging.error("Informações não encontradas para indicador %s", indicador_id)
            # Oculta spinner, mostra erro
            return [dbc.Alert(f"Informações de configuração não encontradas para o indicador {indicador_id}.", color="danger")], {'display': 'none'}

        # Adiciona a descrição do indicador (será retornada junto com o conteúdo ou erro)
        desc_p = html.P(indicador_info.iloc[0]['DESC_INDICADOR'], className="textJustify p-3")

        # Verifica se os dados foram carregados
        if df_dados is None or df_dados.empty:
            logging.warning("Dados não disponíveis para %s em load_indicator_on_demand.", indicador_id)
            # Retorna descrição + alerta de dados não disponíveis
            return [desc_p, dbc.Alert(f"Dados não disponíveis para {indicador_id}.", color="warning")], {'display': 'none'} # Oculta spinner

        # Variáveis para montar o conteúdo
        dynamic_filters_div = []
        variable_dropdown_div = []
        valor_inicial_variavel = None
        initial_dynamic_filters = {} # Dicionário para filtros iniciais

        # --- Geração de Filtros Dinâmicos ---
        logging.debug("Gerando filtros dinâmicos para %s", indicador_id)
        filter_cols = identify_filter_columns(df_dados)
        for idx, filter_col_code in enumerate(filter_cols):
            desc_col_code = 'DESC_' + filter_col_code[5:]
            code_to_desc = {}
            if desc_col_code in df_dados.columns:
                try:
                    mapping_df = df_dados[[filter_col_code, desc_col_code]].dropna().drop_duplicates()
                    code_to_desc = pd.Series(mapping_df[desc_col_code].astype(str).values,
                                             index=mapping_df[filter_col_code].astype(str)).to_dict()
                except Exception as map_err:
                    logging.error("Erro ao mapear código/descrição para filtro %s em %s: %s", filter_col_code, indicador_id, map_err)
            unique_codes = sorted(df_dados[filter_col_code].dropna().astype(str).unique())
            col_options = [{'label': str(code_to_desc.get(code, code)), 'value': code} for code in unique_codes]
            filter_label = constants.COLUMN_NAMES.get(filter_col_code, filter_col_code)
            md_width = 7 if idx % 2 == 0 else 5
            initial_value = unique_codes[0] if unique_codes else None
            if initial_value is not None:
                 initial_dynamic_filters[filter_col_code] = initial_value
            dynamic_filters_div.append(dbc.Col([
                html.Label(f"{filter_label}:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '5px'}),
                dcc.Dropdown(
                    id={'type': 'dynamic-filter-dropdown', 'index': indicador_id, 'filter_col': filter_col_code},
                    options=col_options, value=initial_value, style={'marginBottom': '10px', 'width': '100%'}
                )
            ], md=md_width, xs=12))

        # --- Geração do Dropdown de Variável Principal ---
        logging.debug("Verificando dropdown de variável para %s", indicador_id)
        has_variable_dropdown = not indicador_info.empty and 'VARIAVEIS' in indicador_info.columns and indicador_info['VARIAVEIS'].iloc[0] == '1'
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
                                value=valor_inicial_variavel, style={'width': '100%'}
                            )
                        ], style={'paddingBottom': '20px', 'paddingTop': '20px'}, id={'type': 'var-dropdown-container', 'index': indicador_id})]

        # --- Geração da Visualização ---
        logging.debug("Gerando visualização para %s", indicador_id)
        initial_visualization = create_visualization(
            df_dados, indicador_id, valor_inicial_variavel, initial_dynamic_filters
        )

        # --- Monta o conteúdo dinâmico final ---
        dynamic_content = []
        dynamic_content.extend(variable_dropdown_div)
        if dynamic_filters_div:
            dynamic_content.append(dbc.Row(dynamic_filters_div))
        dynamic_content.append(html.Div(id={'type': 'graph-container', 'index': indicador_id}, children=initial_visualization))

        # Retorna descrição + conteúdo dinâmico e oculta o spinner
        logging.debug("Conteúdo carregado com sucesso para %s", indicador_id)
        # Modificado: Retorna APENAS o conteúdo dinâmico
        return dynamic_content, {'display': 'none'}

    # --- FIM DO BLOCO TRY...EXCEPT ---
    except Exception as e_load:
        logging.exception("Erro CRÍTICO ao carregar conteúdo sob demanda para %s", indicador_id)
        # Modificado: Retorna APENAS o alerta de erro
        return [dbc.Alert(f"Erro ao carregar dados para {indicador_id}. Consulte os logs do servidor.", color="danger")], {'display': 'none'} # Oculta spinner, mostra erro


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
                      logging.error("Erro ao parsear meta_id de: %s", triggered_id_str)
                      raise PreventUpdate

            if not meta_id:
                 raise PreventUpdate # Não conseguiu obter o meta_id
            logging.debug("Atualizando conteúdo - Clique na Meta ID: %s", meta_id) # Log de Debug

            meta_filtrada = df_metas[df_metas['ID_META'] == meta_id]
            if meta_filtrada.empty:
                 return no_update, no_update, no_update, "Meta não encontrada.", [] # Atualiza descrição

            meta_desc = meta_filtrada['DESC_META'].iloc[0]
            objetivo_id = meta_filtrada['ID_OBJETIVO'].iloc[0]

            # Recria a barra de navegação das metas, marcando a ativa
            metas_obj_filtradas = df_metas[df_metas['ID_OBJETIVO'] == objetivo_id]
            metas_com_indicadores = []
            for _, meta in metas_obj_filtradas.iterrows():
                indicadores_meta = df_indicadores[df_indicadores['ID_META'] == meta['ID_META']]
                if not indicadores_meta.empty:
                    # Verifica se pelo menos um indicador tem dados
                    for _, row_ind in indicadores_meta.iterrows():
                        indicador_id = row_ind['ID_INDICADOR']
                        nome_arquivo = indicador_id.lower().replace("indicador ", "")
                        arquivo_parquet = f'db/resultados/indicador{nome_arquivo}.parquet'
                        if os.path.exists(arquivo_parquet):
                            metas_com_indicadores.append(meta)
                            break

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
                    active=(meta['ID_META'] == meta_id),
                    className="nav-link",
                    n_clicks=0 # Reset n_clicks
                ) for meta in metas_com_indicadores
            ]

            # Gera a seção de indicadores para a meta clicada
            indicadores_meta_selecionada = df_indicadores[df_indicadores['ID_META'] == meta_id]
            tabs_indicadores = []

            # Comentado para desabilitar pré-carregamento
            # preload_related_indicators(meta_id, df_indicadores, _load_dados_indicador_original)

            if not indicadores_meta_selecionada.empty:
                valor_inicial_variavel_primeira_aba = None
                
                # Filtra apenas indicadores que realmente possuem dados disponíveis
                indicadores_com_dados = []
                for _, row_ind in indicadores_meta_selecionada.iterrows():
                    indicador_id_atual = row_ind['ID_INDICADOR']
                    # Verifica se o arquivo do indicador existe
                    nome_arquivo = indicador_id_atual.lower().replace("indicador ", "")
                    arquivo_parquet = f'db/resultados/indicador{nome_arquivo}.parquet'
                    if os.path.exists(arquivo_parquet):
                        indicadores_com_dados.append(row_ind)
                
                # Se não houver indicadores com dados disponíveis, exibe mensagem
                if not indicadores_com_dados:
                    return header, content, metas_nav_children, meta_desc, [
                        html.H5("Indicadores", className="mt-4 mb-3"),
                        dbc.Alert("Não há dados disponíveis para os indicadores desta meta.", color="warning", 
                                 className="textCenter p-3 mt-3")
                    ]
                
                for i, row_ind in enumerate(indicadores_com_dados):
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
                                initial_dynamic_filters = {} # Dicionário para guardar filtros iniciais

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
                                            logging.error("Erro ao mapear código/descrição para filtro %s: %s", filter_col_code, map_err)
                                            # Adiciona log de erro para mapeamento
                                            logging.error("Erro ao mapear código/descrição para filtro %s: %s", filter_col_code, map_err)
                                    unique_codes = sorted(df_dados[filter_col_code].dropna().astype(str).unique())
                                    col_options = [{'label': str(code_to_desc.get(code, code)), 'value': code} for code in unique_codes]
                                    filter_label = constants.COLUMN_NAMES.get(filter_col_code, filter_col_code)
                                    md_width = 7 if idx % 2 == 0 else 5
                                    # Define o valor inicial e armazena
                                    initial_value = unique_codes[0] if unique_codes else None
                                    if initial_value is not None:
                                         initial_dynamic_filters[filter_col_code] = initial_value

                                    dynamic_filters_div.append(dbc.Col([
                                        html.Label(f"{filter_label}:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '5px'}),
                                        dcc.Dropdown(
                                            id={'type': 'dynamic-filter-dropdown', 'index': indicador_id_atual, 'filter_col': filter_col_code},
                                            options=col_options,
                                            value=initial_value, # Usa o valor inicial definido
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
                                                # Usar o primeiro valor disponível no dropdown
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
                                                ])]

                                # Cria a visualização inicial PASSANDO OS FILTROS INICIAIS
                                initial_visualization = create_visualization(
                                    df_dados, indicador_id_atual, valor_inicial_variavel, initial_dynamic_filters
                                )
                                tab_content = [html.P(row_ind['DESC_INDICADOR'], className="textJustify p-3", style={'marginBottom': '10px'})]
                                tab_content.extend(variable_dropdown_div)
                                if dynamic_filters_div:
                                    tab_content.append(dbc.Row(dynamic_filters_div))
                                tab_content.append(html.Div(id={'type': 'graph-container', 'index': indicador_id_atual}, children=initial_visualization))
                            except Exception as e_inner:
                                logging.exception("Erro interno ao gerar conteúdo da aba %s", indicador_id_atual)
                                tab_content = [dbc.Alert(f"Erro ao gerar conteúdo para {indicador_id_atual}.", color="danger")]
                                # Usamos logging.exception aqui
                                logging.exception("Erro interno ao gerar conteúdo da aba %s", indicador_id_atual)
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
                    # --- MODIFICADO: Inclui initial_dynamic_filters no Store ---
                    initial_filters_for_store = {}
                    if is_first_indicator:
                         initial_filters_for_store = initial_dynamic_filters # Usa os filtros coletados
                    store_data = {
                        'selected_var': valor_inicial_variavel_primeira_aba if is_first_indicator else None,
                        'selected_filters': initial_filters_for_store # Usa o dict de filtros iniciais
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
            logging.debug("Atualizando conteúdo - Clique no Objetivo ID: %s (Index: %d)", row_obj['ID_OBJETIVO'], index) # Log de Debug
            header = f"{row_obj['ID_OBJETIVO']} - {row_obj['RES_OBJETIVO']}" if index > 0 else row_obj['RES_OBJETIVO']
            content = row_obj['DESC_OBJETIVO']

            # Se for objetivo 0, limpa metas e indicadores
            if index == 0:
                return header, content, [], "", []

            # Encontra metas com indicadores para este objetivo
            metas_obj_filtradas = df_metas[df_metas['ID_OBJETIVO'] == row_obj['ID_OBJETIVO']]
            metas_com_indicadores = []
            for _, meta in metas_obj_filtradas.iterrows():
                indicadores_meta = df_indicadores[df_indicadores['ID_META'] == meta['ID_META']]
                if not indicadores_meta.empty:
                    # Verifica se pelo menos um indicador tem dados
                    for _, row_ind in indicadores_meta.iterrows():
                        indicador_id = row_ind['ID_INDICADOR']
                        nome_arquivo = indicador_id.lower().replace("indicador ", "")
                        arquivo_parquet = f'db/resultados/indicador{nome_arquivo}.parquet'
                        if os.path.exists(arquivo_parquet):
                            metas_com_indicadores.append(meta)
                            break

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

            # Comentado para desabilitar pré-carregamento
            # preload_related_indicators(meta_id, df_indicadores, _load_dados_indicador_original)

            if not indicadores_primeira_meta.empty:
                # Variável para armazenar o valor inicial da variável (usado apenas para o primeiro indicador)
                valor_inicial_variavel = None
                initial_dynamic_filters = {} # Dicionário para guardar filtros iniciais para clique em objetivo
                
                # Filtra apenas indicadores que realmente possuem dados disponíveis
                indicadores_com_dados = []
                for _, row_ind in indicadores_primeira_meta.iterrows():
                    indicador_id_atual = row_ind['ID_INDICADOR']
                    # Verifica se o arquivo do indicador existe
                    nome_arquivo = indicador_id_atual.lower().replace("indicador ", "")
                    arquivo_parquet = f'db/resultados/indicador{nome_arquivo}.parquet'
                    if os.path.exists(arquivo_parquet):
                        indicadores_com_dados.append(row_ind)
                
                # Se não houver indicadores com dados disponíveis, exibe mensagem
                if not indicadores_com_dados:
                    return header, content, metas_nav_children, meta_description, [
                        html.H5("Indicadores", className="mt-4 mb-3"),
                        dbc.Alert("Não há dados disponíveis para os indicadores desta meta.", color="warning", 
                                 className="textCenter p-3 mt-3")
                    ]

                # Cria abas para todos os indicadores da primeira meta
                for i, row_ind in enumerate(indicadores_com_dados):
                    # Apenas o primeiro indicador é carregado completamente
                    is_first_indicator = (i == 0)

                    if is_first_indicator:
                        # Carrega dados apenas para o primeiro indicador
                        df_dados = load_dados_indicador_cache(row_ind['ID_INDICADOR'])
                        tab_content = []
                        dynamic_filters_div = []
                        valor_inicial_variavel = None
                        initial_dynamic_filters = {} # Reseta para este indicador

                        if df_dados is not None and not df_dados.empty:
                            try:
                                # Identifica filtros dinâmicos
                                filter_cols = identify_filter_columns(df_dados)
                                initial_dynamic_filters = {} # Dicionário para filtros iniciais

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
                                            logging.error("Erro ao mapear código/descrição para filtro %s: %s", filter_col_code, map_err)
                                            # Adiciona log de erro para mapeamento
                                            logging.error("Erro ao mapear código/descrição para filtro %s: %s", filter_col_code, map_err)
                                    unique_codes = sorted(df_dados[filter_col_code].dropna().astype(str).unique())
                                    col_options = [{'label': str(code_to_desc.get(code, code)), 'value': code} for code in unique_codes]
                                    filter_label = constants.COLUMN_NAMES.get(filter_col_code, filter_col_code)

                                    # Define larguras alternadas para os filtros
                                    md_width = 7 if idx % 2 == 0 else 5
                                    # Define o valor inicial e armazena
                                    initial_value = unique_codes[0] if unique_codes else None
                                    if initial_value is not None:
                                         initial_dynamic_filters[filter_col_code] = initial_value

                                    dynamic_filters_div.append(
                                        dbc.Col([
                                            html.Label(f"{filter_label}:", style={'fontWeight': 'bold', 'display': 'block', 'marginBottom': '5px'}),
                                            dcc.Dropdown(
                                                id={'type': 'dynamic-filter-dropdown', 'index': row_ind['ID_INDICADOR'], 'filter_col': filter_col_code},
                                                options=col_options,
                                                value=initial_value, # Usa o valor inicial definido
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
                                                # Usar o primeiro valor disponível no dropdown
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

                                # Cria a visualização inicial PASSANDO OS FILTROS INICIAIS
                                initial_visualization = create_visualization(
                                    df_dados, row_ind['ID_INDICADOR'], valor_inicial_variavel, initial_dynamic_filters
                                )
                                tab_content = [html.P(row_ind['DESC_INDICADOR'], className="textJustify p-3", style={'marginBottom': '10px'})]
                                tab_content.extend(variable_dropdown_div)
                                if dynamic_filters_div:
                                    tab_content.append(dbc.Row(dynamic_filters_div))
                                tab_content.append(html.Div(id={'type': 'graph-container', 'index': row_ind['ID_INDICADOR']}, children=initial_visualization))

                            except Exception as e_inner:
                                logging.exception("Erro interno ao gerar conteúdo da aba %s (clique objetivo)", row_ind['ID_INDICADOR'])
                                tab_content = [dbc.Alert(f"Erro ao gerar conteúdo para {row_ind['ID_INDICADOR']}.", color="danger")]
                                # Usamos logging.exception aqui
                                logging.exception("Erro interno ao gerar conteúdo da aba %s (clique objetivo)", row_ind['ID_INDICADOR'])
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
                                                data={'selected_var': valor_inicial_variavel if is_first_indicator else None,
                                                      'selected_filters': initial_dynamic_filters})) # Usa o dict de filtros iniciais

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
        logging.exception("Erro geral em update_card_content:")
        # Retorna um estado seguro em caso de erro inesperado
        return initial_header, initial_content, [], "Ocorreu um erro.", []


# Callback para atualizar o store quando a variável ou filtros são alterados
@app.callback(
    Output({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
    [
        Input({'type': 'var-dropdown', 'index': MATCH}, 'value'),
        Input({'type': 'dynamic-filter-dropdown', 'index': MATCH, 'filter_col': ALL}, 'value')
    ],
    [
        State({'type': 'dynamic-filter-dropdown', 'index': MATCH, 'filter_col': ALL}, 'id'),
        State({'type': 'visualization-state-store', 'index': MATCH}, 'data')
    ],
    prevent_initial_call=True
)
def update_store_on_filter_change(var_value, filter_values, filter_ids, current_data):
    """Atualiza o store quando variável ou filtros são alterados"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    # Inicializa o store se não existir
    if current_data is None:
        current_data = {'selected_var': None, 'selected_filters': {}}
    
    # Cria uma cópia para não modificar o original
    updated_data = dict(current_data)
    
    # Identifica qual input foi alterado
    trigger_id = ctx.triggered[0]['prop_id']
    
    # Se foi o dropdown de variável
    if 'var-dropdown' in trigger_id:
        updated_data['selected_var'] = var_value
    
    # Se foi algum filtro dinâmico
    elif 'dynamic-filter-dropdown' in trigger_id:
        # Inicializa dicionário de filtros se não existir
        if not updated_data.get('selected_filters'):
            updated_data['selected_filters'] = {}
        
        # Mapeia valores para ids correspondentes
        for i, filter_id in enumerate(filter_ids):
            filter_col = filter_id.get('filter_col')
            if filter_col:
                updated_data['selected_filters'][filter_col] = filter_values[i]
    
    return updated_data


# Callback para atualizar visualizações quando o store é alterado
@app.callback(
    Output({'type': 'graph-container', 'index': MATCH}, 'children'),
    Input({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
    State({'type': 'graph-container', 'index': MATCH}, 'id'),
    prevent_initial_call=True
)
def update_visualization_on_store_change(store_data, container_id):
    """Atualiza todas as visualizações quando o store é alterado"""
    if not store_data:
        raise PreventUpdate
    
    indicador_id = container_id['index']
    
    # Carrega dados do indicador
    df_dados = load_dados_indicador_cache(indicador_id)
    if df_dados is None or df_dados.empty:
        return dbc.Alert(f"Dados não disponíveis para {indicador_id}.", color="warning")
    
    # Extrai variáveis e filtros do store
    selected_var = store_data.get('selected_var')
    selected_filters = store_data.get('selected_filters', {})
    
    # Gera nova visualização
    try:
        visualization = create_visualization(
            df_dados, indicador_id, selected_var, selected_filters
        )
        return visualization
    except Exception as e:
        logging.exception("Erro ao atualizar visualização para %s", indicador_id)
        return dbc.Alert(f"Erro ao atualizar visualização: {str(e)}", color="danger")


# Callback para atualizar o Ranking quando o ano é alterado
# --- MODIFICADO: Adicionado Output para a figura do gráfico principal ---
@app.callback(
    [
        Output({'type': 'ranking-container', 'index': MATCH}, 'children'),
        Output({'type': 'main-chart', 'index': MATCH}, 'figure') # Novo Output
    ],
    [Input({'type': 'year-dropdown-ranking', 'index': MATCH}, 'value')],
    [
        State({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
        State({'type': 'ranking-container', 'index': MATCH}, 'id'),
        # Adicionado State para obter o ID do gráfico principal correspondente
        State({'type': 'main-chart', 'index': MATCH}, 'id')
    ],
    prevent_initial_call=True
)
def update_ranking_chart(selected_year, store_data, ranking_container_id, main_chart_id): # Modificada assinatura
    """Atualiza o ranking e, se aplicável, o gráfico principal (barras simples) quando o ano é selecionado."""
    ctx = callback_context
    # Verifica se o callback foi acionado e se os dados necessários existem
    # Adicionado main_chart_id à verificação
    if not ctx.triggered or not selected_year or not store_data or not ranking_container_id or not main_chart_id:
        raise PreventUpdate

    # Confirma se os IDs do indicador correspondem (sanity check)
    indicador_id_ranking = ranking_container_id['index']
    indicador_id_main = main_chart_id['index']
    if indicador_id_ranking != indicador_id_main:
        logging.warning(f"IDs de indicador incompatíveis no callback update_ranking_chart: Ranking={indicador_id_ranking}, Main={indicador_id_main}")
        raise PreventUpdate # Previne atualização se os IDs não baterem

    indicador_id = indicador_id_ranking # Usa o ID confirmado

    # --- Inicializa saídas padrão ---
    ranking_output = dbc.Alert('Erro inesperado ao atualizar ranking.', color="danger", className="textCenter p-3")
    main_chart_figure_output = dash.no_update # Gráfico principal não atualiza por padrão

    # Extrai filtros do store
    selected_var = store_data.get('selected_var')
    selected_filters = store_data.get('selected_filters', {})

    # Carrega os dados do indicador (apenas uma vez)
    df_base = load_dados_indicador_cache(indicador_id)
    # Verifica se os dados base existem e contêm colunas essenciais (ano, valor, uf)
    if df_base is None or df_base.empty or not all(col in df_base.columns for col in ['CODG_ANO', 'VLR_VAR']) or ('DESC_UND_FED' not in df_base.columns and 'CODG_UND_FED' not in df_base.columns):
        ranking_output = dbc.Alert('Dados não disponíveis ou incompletos.', color="warning", className="textCenter p-3")
        return ranking_output, main_chart_figure_output # Retorna alerta e no_update

    # --- Aplica filtros (Variável principal e dinâmicos) ao DF base ---
    # (Este código é similar ao início da função original, mas opera no df_base)
    df_filtered_base = df_base.copy()
    # Garante que CODG_ANO seja string para filtragem consistente
    df_filtered_base['CODG_ANO'] = df_filtered_base['CODG_ANO'].astype(str)
    # Filtro Variável Principal
    if 'CODG_VAR' in df_filtered_base.columns and selected_var:
        df_filtered_base['CODG_VAR'] = df_filtered_base['CODG_VAR'].astype(str).str.strip()
        selected_var_str = str(selected_var).strip()
        df_filtered_base = df_filtered_base[df_filtered_base['CODG_VAR'] == selected_var_str]
    # Filtros Dinâmicos
    if selected_filters:
        for col_code, selected_value in selected_filters.items():
            if selected_value is not None and col_code in df_filtered_base.columns:
                # Convert column to string *before* fillna/strip for comparison
                df_filtered_base[col_code] = df_filtered_base[col_code].astype(str).fillna('').str.strip()
                selected_value_str = str(selected_value).strip()
                df_filtered_base = df_filtered_base[df_filtered_base[col_code] == selected_value_str]

    # --- Adiciona colunas de descrição necessárias (UF, UND_MED) ---
    # Adiciona DESC_UND_FED
    if 'DESC_UND_FED' not in df_filtered_base.columns and 'CODG_UND_FED' in df_filtered_base.columns:
        df_filtered_base['DESC_UND_FED'] = df_filtered_base['CODG_UND_FED'].astype(str).map(constants.UF_NAMES)
        # Mantém linhas mesmo que a UF não seja encontrada, pode ser 'Brasil' ou outro nível
        # df_filtered_base = df_filtered_base.dropna(subset=['DESC_UND_FED']) # Removido dropna aqui

    # Adiciona DESC_UND_MED
    if 'DESC_UND_MED' not in df_filtered_base.columns and 'CODG_UND_MED' in df_filtered_base.columns:
        df_unidade_medida_loaded = load_unidade_medida()
        if not df_unidade_medida_loaded.empty:
            # Garante que as chaves de merge são strings
            df_filtered_base['CODG_UND_MED'] = df_filtered_base['CODG_UND_MED'].astype(str)
            df_unidade_medida_loaded['CODG_UND_MED'] = df_unidade_medida_loaded['CODG_UND_MED'].astype(str)
            df_filtered_base = pd.merge(df_filtered_base, df_unidade_medida_loaded[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
            df_filtered_base['DESC_UND_MED'] = df_filtered_base['DESC_UND_MED'].fillna('N/D')
        else:
            df_filtered_base['DESC_UND_MED'] = 'N/D'
    elif 'DESC_UND_MED' not in df_filtered_base.columns:
            df_filtered_base['DESC_UND_MED'] = 'N/D' # Garante que a coluna existe

    # --- Verifica se o Gráfico Principal deve ser Barras Simples ---
    # (Baseado nos dados filtrados gerais e no tipo/anos do indicador)
    tipo_grafico = 'S' # Padrão
    indicador_info = df_indicadores[df_indicadores['ID_INDICADOR'] == indicador_id]
    if not indicador_info.empty:
         tipo_grafico = indicador_info.iloc[0].get('TIPO_GRAFICO', 'S').strip().upper() or 'S'

    # Calcula número de anos únicos *após* aplicar os filtros
    anos_unicos_filtrados = df_filtered_base['CODG_ANO'].unique()
    num_anos_filtrados = len(anos_unicos_filtrados)
    min_years_for_temporal = 5 # Definido como em create_visualization

    is_simple_bar_chart = (tipo_grafico == 'S') or ((tipo_grafico in ['L', 'C']) and (num_anos_filtrados < min_years_for_temporal))

    # --- Geração do Gráfico Principal (se for Barras Simples) ---
    if is_simple_bar_chart:
        # Filtra os dados base JÁ FILTRADOS para o ANO SELECIONADO
        df_simple_bar_ano = df_filtered_base[df_filtered_base['CODG_ANO'] == str(selected_year)].copy()

        if not df_simple_bar_ano.empty:
            try:
                # Garante DESC_UND_FED (pode ser 'Brasil')
                if 'DESC_UND_FED' not in df_simple_bar_ano.columns:
                    df_simple_bar_ano['DESC_UND_FED'] = 'Brasil' # Ou N/D

                # Ordena, formata e adiciona coluna de valor formatado
                df_simple_bar_ano = df_simple_bar_ano.sort_values('VLR_VAR', ascending=False)
                df_simple_bar_ano['VLR_VAR_FORMATADO'] = df_simple_bar_ano['VLR_VAR'].apply(format_br)

                # Define o mapa de cores
                color_map_simple = {
                    'Goiás': '#229846', 'Maranhão': '#D2B48C', 'Distrito Federal': '#636efa',
                    'Mato Grosso': '#ab63fa', 'Mato Grosso do Sul': '#ffa15a', 'Rondônia': '#19d3f3',
                    'Tocantins': '#ff6692', 'Brasil': '#FF0000'
                }

                # Cria a figura de barras simples
                fig_simple_bar = px.bar(
                    df_simple_bar_ano, x='DESC_UND_FED', y='VLR_VAR',
                    text='VLR_VAR_FORMATADO',
                    color='DESC_UND_FED',
                    color_discrete_map=color_map_simple,
                    hover_data={
                        'DESC_UND_FED': True, 'VLR_VAR': False,
                        'VLR_VAR_FORMATADO': True, 'DESC_UND_MED': True
                    }
                )
                fig_simple_bar.update_traces(
                    texttemplate='<b>%{text}</b>', textposition='outside',
                    hovertemplate="<b>%{x}</b><br>Valor: %{customdata[0]}<br>Unidade: %{customdata[1]}<extra></extra>",
                    customdata=np.column_stack((
                       df_simple_bar_ano['VLR_VAR_FORMATADO'].values,
                       df_simple_bar_ano['DESC_UND_MED'].values
                    ))
                )

                # Aplica layout
                max_y_simple = df_simple_bar_ano['VLR_VAR'].max()
                y_range_simple = [0, max_y_simple * 1.15]
                layout_updates_bar_simple = DEFAULT_LAYOUT.copy()
                layout_updates_bar_simple.update({
                    'title': None, # Remove título que pode vir por padrão
                    'xaxis': dict(showgrid=False, tickfont=dict(size=12, color='black'), tickangle=45, title=None),
                    'yaxis': dict(showgrid=True, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d', range=y_range_simple),
                    'showlegend': False
                })
                # Ajusta ticks do eixo X
                all_ufs_simple = sorted(df_simple_bar_ano['DESC_UND_FED'].unique())
                x_ticktext_simple = [f"<b>{label}</b>" if label == 'Goiás' else f"{label}" for label in all_ufs_simple]
                layout_updates_bar_simple['xaxis']['ticktext'] = x_ticktext_simple
                layout_updates_bar_simple['xaxis']['tickvals'] = all_ufs_simple
                fig_simple_bar.update_layout(layout_updates_bar_simple)

                # Atribui a figura gerada à saída do gráfico principal
                main_chart_figure_output = fig_simple_bar

            except Exception as e_simple_bar:
                logging.exception(f"Erro ao gerar gráfico de barras simples para {indicador_id}, ano {selected_year}: {e_simple_bar}")
                # Se falhar, main_chart_figure_output continua como no_update
        else:
            # Se não houver dados para o ano selecionado no gráfico simples
            logging.warning(f"Dados insuficientes para gráfico de barras simples ({indicador_id}, ano {selected_year})")
            # Retorna uma figura vazia com aviso para o gráfico principal
            fig_vazia = go.Figure().update_layout(title=f'Dados insuficientes para {selected_year}', xaxis={'visible': False}, yaxis={'visible': False})
            main_chart_figure_output = fig_vazia
    # else: Se não for gráfico de barras simples, main_chart_figure_output permanece dash.no_update

    # --- Geração do Conteúdo do Ranking (código existente adaptado) ---
    # Usa o df_filtered_base já filtrado pelas variáveis/filtros dinâmicos
    df_ranking_ano = df_filtered_base[df_filtered_base['CODG_ANO'] == str(selected_year)].copy()

    # Verifica se há dados e unicidade de UF APÓS filtrar pelo ano
    if df_ranking_ano.empty:
         ranking_output = dbc.Alert(f'Ranking não disponível para {selected_year} com filtros aplicados.', color="warning", className="textCenter p-3")
    elif 'DESC_UND_FED' not in df_ranking_ano.columns:
         ranking_output = dbc.Alert(f'Ranking não disponível (sem dados por UF).', color="warning", className="textCenter p-3")
    elif (df_ranking_ano['DESC_UND_FED'].value_counts() > 1).any():
         ranking_output = dbc.Alert('Ranking não gerado: múltiplos valores por UF. Verifique os filtros.', color="warning", className="textCenter p-3")
    else:
        # Tenta gerar a figura do ranking
        try:
            ranking_ordem = 0 # Padrão
            if not indicador_info.empty and 'RANKING_ORDEM' in indicador_info.columns:
                try:
                    ranking_ordem_val = pd.to_numeric(indicador_info['RANKING_ORDEM'].iloc[0], errors='coerce')
                    if not pd.isna(ranking_ordem_val): ranking_ordem = int(ranking_ordem_val)
                except (ValueError, TypeError) as e_rank:
                    logging.warning("Erro ao converter RANKING_ORDEM para %s: %s. Usando padrão 0.", indicador_id, e_rank)

            ascending_rank = (ranking_ordem == 0)
            df_ranking_ano_sorted = df_ranking_ano.sort_values('VLR_VAR', ascending=ascending_rank)

            goias_color = 'rgba(34, 152, 70, 1)'
            other_color = 'rgba(34, 152, 70, 0.2)'

            fig_ranking_updated = go.Figure()
            for _, row in df_ranking_ano_sorted.iterrows():
                uf = row['DESC_UND_FED']
                valor = row['VLR_VAR']
                und_med = row.get('DESC_UND_MED', 'N/D') # Já garantimos que existe
                bar_color = goias_color if uf == 'Goiás' else other_color
                text_value = format_br(valor)

                fig_ranking_updated.add_trace(go.Bar(
                    y=[uf], x=[valor], name=uf, orientation='h',
                    marker_color=bar_color, text=text_value,
                    textposition='outside', texttemplate='<b>%{text}</b>',
                    hovertemplate=(
                        f"<b>{uf}</b><br>"
                        f"Valor: {text_value}<br>"
                        f"Unidade: {und_med}<extra></extra>"
                    )
                ))

            max_x_ranking = df_ranking_ano_sorted['VLR_VAR'].max() if not df_ranking_ano_sorted.empty else 0
            x_range_ranking = [0, max_x_ranking * 1.15]

            fig_ranking_updated.update_layout(
                xaxis_title=None, yaxis_title=None,
                yaxis=dict(showgrid=False, tickfont=dict(size=12, color='black'), categoryorder='array', categoryarray=df_ranking_ano_sorted['DESC_UND_FED'].tolist()),
                xaxis=dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), range=x_range_ranking, tickformat='d'),
                showlegend=False, margin=dict(l=150, r=20, t=30, b=30), bargap=0.1
            )

            # Define a saída do ranking como o gráfico gerado
            ranking_output = dcc.Graph(id={'type': 'ranking-chart', 'index': indicador_id}, figure=fig_ranking_updated)

        except Exception as e_rank_fig:
            logging.exception(f"Erro ao gerar figura de ranking para {indicador_id}, ano {selected_year}: {e_rank_fig}")
            ranking_output = dbc.Alert(f'Erro ao gerar ranking para {selected_year}.', color="danger", className="textCenter p-3")

    # --- Retorna as duas saídas ---
    return ranking_output, main_chart_figure_output


# Callback para atualizar o mapa quando o ano é alterado
@app.callback(
    # MODIFICADO: Output agora é o children do container do mapa
    Output({'type': 'map-container', 'index': MATCH}, 'children'),
    [Input({'type': 'year-dropdown-map', 'index': MATCH}, 'value')],
    [
        # State({'type': 'choropleth-map', 'index': MATCH}, 'id'), # Removido
        State({'type': 'visualization-state-store', 'index': MATCH}, 'data'),
        # Adicionado State para pegar ID do indicador do container
        State({'type': 'map-container', 'index': MATCH}, 'id')
    ],
    prevent_initial_call=True
)
def update_map_on_year_change(selected_year, store_data, container_id):
    """Atualiza o conteúdo do container do mapa (gráfico ou alerta) quando o ano é alterado"""
    if not selected_year or not store_data:
        raise PreventUpdate

    indicador_id = container_id['index']

    # Extrai filtros do store
    selected_var = store_data.get('selected_var')
    selected_filters = store_data.get('selected_filters', {})

    # Carrega os dados do indicador
    df_map_base = load_dados_indicador_cache(indicador_id)
    if df_map_base is None or df_map_base.empty or ('CODG_UND_FED' not in df_map_base.columns and 'DESC_UND_FED' not in df_map_base.columns):
        # MODIFICADO: Retorna Alerta
        return dbc.Alert('Dados não disponíveis ou incompletos para mapa.', color="warning", className="textCenter p-3")

    # Aplica filtros (Variável principal e dinâmicos)
    df_filtered_map = df_map_base.copy()

    # Filtro Variável Principal
    if 'CODG_VAR' in df_filtered_map.columns and selected_var:
        df_filtered_map['CODG_VAR'] = df_filtered_map['CODG_VAR'].astype(str).str.strip()
        selected_var_str = str(selected_var).strip()
        df_filtered_map = df_filtered_map[df_filtered_map['CODG_VAR'] == selected_var_str]

    # Filtros Dinâmicos
    if selected_filters:
        for col_code, selected_value in selected_filters.items():
            if selected_value is not None and col_code in df_filtered_map.columns:
                df_filtered_map[col_code] = df_filtered_map[col_code].astype(str).fillna('').str.strip()
                selected_value_str = str(selected_value).strip()
                df_filtered_map = df_filtered_map[df_filtered_map[col_code] == selected_value_str]

    # Adiciona DESC_UND_FED se não existir
    if 'DESC_UND_FED' not in df_filtered_map.columns and 'CODG_UND_FED' in df_filtered_map.columns:
        df_filtered_map['DESC_UND_FED'] = df_filtered_map['CODG_UND_FED'].astype(str).map(constants.UF_NAMES)
        df_filtered_map = df_filtered_map.dropna(subset=['DESC_UND_FED'])
    elif 'DESC_UND_FED' not in df_filtered_map.columns:
         # Se ainda não tem UF, não pode gerar mapa
         return dbc.Alert('Dados não contêm Unidade Federativa para gerar mapa.', color="warning", className="textCenter p-3")

    # Filtra pelo ano selecionado
    df_filtered_map['CODG_ANO'] = df_filtered_map['CODG_ANO'].astype(str).str.strip()
    df_map_ano = df_filtered_map[df_filtered_map['CODG_ANO'] == str(selected_year).strip()]

    # Se não houver dados após filtrar por ano, retorna alerta
    if df_map_ano.empty:
        # MODIFICADO: Retorna Alerta
        return dbc.Alert(f'Nenhum dado disponível para o mapa no ano {selected_year}', color="info", className="textCenter p-3")

    # Verifica unicidade por UF
    counts_per_uf_map = df_map_ano['DESC_UND_FED'].value_counts()
    if (counts_per_uf_map > 1).any():
        # MODIFICADO: Retorna Alerta
        return dbc.Alert(
            f"Mapa não pode ser gerado para {selected_year}: múltiplos valores por UF. "
            "Verifique os filtros aplicados.", color="warning", className="textCenter p-3"
        )

    # Cria o mapa coroplético
    try:
        df_map_ano['VLR_VAR_FORMATADO'] = df_map_ano['VLR_VAR'].apply(format_br)

        und_med_map = ''
        if 'DESC_UND_MED' in df_map_ano.columns:
             und_med_series = df_map_ano['DESC_UND_MED'].dropna()
             if not und_med_series.empty: und_med_map = und_med_series.iloc[0]
        elif 'CODG_UND_MED' in df_map_ano.columns:
            codg_und_med_values = df_map_ano['CODG_UND_MED'].dropna().unique()
            if len(codg_und_med_values) > 0:
                df_um = load_unidade_medida()
                if not df_um.empty:
                    codg_und_med = str(codg_und_med_values[0])
                    df_um['CODG_UND_MED'] = df_um['CODG_UND_MED'].astype(str)
                    match = df_um[df_um['CODG_UND_MED'] == codg_und_med]
                    if not match.empty: und_med_map = match['DESC_UND_MED'].iloc[0]

        with open('db/br_geojson.json', 'r', encoding='utf-8') as f: geojson = json.load(f)

        fig_map = px.choropleth(
            df_map_ano, geojson=geojson, locations='DESC_UND_FED',
            featureidkey='properties.name', color='VLR_VAR',
            color_continuous_scale=[[0.0, 'rgba(34, 152, 70, 0.2)'], [1.0, 'rgba(34, 152, 70, 1)']]
        )
        map_center = {'lat': -12.95984198, 'lon': -53.27299730}
        geos_update = dict(
            visible=False, showcoastlines=True, coastlinecolor="White",
            showland=True, landcolor="white", showframe=False,
            projection=dict(type='mercator', scale=15), center=map_center
        )
        fig_map.update_geos(**geos_update)
        fig_map.update_traces(
            marker_line_color='white', marker_line_width=1,
            customdata=df_map_ano[['VLR_VAR_FORMATADO']],
            hovertemplate="<b>%{location}</b><br>Valor: %{customdata[0]}" + (f" {und_med_map}" if und_med_map else "") + "<extra></extra>"
        )
        fig_map.update_layout(coloraxis_colorbar_title_text='')

        # MODIFICADO: Retorna o componente Graph
        return dcc.Graph(id={'type': 'choropleth-map', 'index': indicador_id}, figure=fig_map)

    except Exception as e:
        logging.exception("Erro ao criar mapa para %s, ano %s:", indicador_id, selected_year)
        # MODIFICADO: Retorna Alerta
        return dbc.Alert(f"Erro ao criar mapa para {selected_year}: {str(e)}", color="danger", className="textCenter p-3")


# Callback para atualizar o Boxplot quando o ano é alterado
@app.callback(
    Output({'type': 'boxplot-chart', 'index': MATCH}, 'figure'),
    [Input({'type': 'year-dropdown-boxplot', 'index': MATCH}, 'value')],
    [
        State({'type': 'boxplot-chart', 'index': MATCH}, 'id'),
        State({'type': 'visualization-state-store', 'index': MATCH}, 'data')
    ],
    prevent_initial_call=True
)
def update_boxplot_chart(selected_year, chart_id, store_data):
    """Atualiza o gráfico Boxplot quando o ano é selecionado no dropdown."""
    ctx = callback_context
    if not ctx.triggered or not selected_year or not store_data:
        raise PreventUpdate

    indicador_id = chart_id['index']

    # Extrai filtros do store
    selected_var = store_data.get('selected_var')
    selected_filters = store_data.get('selected_filters', {})

    # Carrega os dados do indicador
    df_boxplot_base = load_dados_indicador_cache(indicador_id)
    if df_boxplot_base is None or df_boxplot_base.empty or 'DESC_UND_FED' not in df_boxplot_base.columns:
        # Retorna figura vazia com aviso
        return go.Figure().update_layout(title='Dados não disponíveis ou incompletos para Boxplot.',
                                        xaxis={'visible': False}, yaxis={'visible': False})

    # --- Aplica filtros (Variável principal e dinâmicos) ---
    df_filtered_boxplot = df_boxplot_base.copy()
    # Filtro Variável Principal
    if 'CODG_VAR' in df_filtered_boxplot.columns and selected_var:
        df_filtered_boxplot['CODG_VAR'] = df_filtered_boxplot['CODG_VAR'].astype(str).str.strip()
        selected_var_str = str(selected_var).strip()
        df_filtered_boxplot = df_filtered_boxplot[df_filtered_boxplot['CODG_VAR'] == selected_var_str]
    # Filtros Dinâmicos
    if selected_filters:
        for col_code, selected_value in selected_filters.items():
            if selected_value is not None and col_code in df_filtered_boxplot.columns:
                # Converte ambos para string para comparação segura
                df_filtered_boxplot[col_code] = df_filtered_boxplot[col_code].astype(str).fillna('').str.strip()
                selected_value_str = str(selected_value).strip()
                df_filtered_boxplot = df_filtered_boxplot[df_filtered_boxplot[col_code] == selected_value_str]

    # Filtra pelo ANO selecionado no dropdown
    df_boxplot_ano = df_filtered_boxplot[df_filtered_boxplot['CODG_ANO'] == selected_year].copy()

    if df_boxplot_ano.empty:
         return go.Figure().update_layout(title=f'Boxplot não disponível para {selected_year} com filtros aplicados.',
                                         xaxis={'visible': False}, yaxis={'visible': False})

    # --- Criação da Figura Atualizada ---
    try:
        df_boxplot_ano = df_boxplot_ano.sort_values('DESC_UND_FED')
        # Adiciona colunas de descrição e formatação necessárias
        if 'DESC_UND_MED' not in df_boxplot_ano.columns and 'CODG_UND_MED' in df_boxplot_ano.columns:
            df_um = load_unidade_medida()
            if not df_um.empty:
                 df_um['CODG_UND_MED'] = df_um['CODG_UND_MED'].astype(str)
                 df_boxplot_ano['CODG_UND_MED'] = df_boxplot_ano['CODG_UND_MED'].astype(str)
                 df_boxplot_ano = pd.merge(df_boxplot_ano, df_um[['CODG_UND_MED', 'DESC_UND_MED']], on='CODG_UND_MED', how='left')
                 df_boxplot_ano['DESC_UND_MED'] = df_boxplot_ano['DESC_UND_MED'].fillna('N/D')
            else:
                 df_boxplot_ano['DESC_UND_MED'] = 'N/D'
        elif 'DESC_UND_MED' not in df_boxplot_ano.columns:
            df_boxplot_ano['DESC_UND_MED'] = 'N/D'

        df_boxplot_ano['VLR_VAR_FORMATADO'] = df_boxplot_ano['VLR_VAR'].apply(format_br)

        fig_boxplot_updated = px.box(
            df_boxplot_ano, x='DESC_UND_FED', y='VLR_VAR', points="all",
            color='DESC_UND_FED',
            hover_data={
                'DESC_UND_FED': True, 'VLR_VAR': False,
                'VLR_VAR_FORMATADO': True, 'DESC_UND_MED': True
            }
        )
        fig_boxplot_updated.update_traces(
            hovertemplate="<b>%{x}</b><br>Valor: %{customdata[0]}<br>Unidade: %{customdata[1]}<extra></extra>",
            customdata=np.column_stack((
                df_boxplot_ano['VLR_VAR_FORMATADO'].values,
                df_boxplot_ano['DESC_UND_MED'].values
            ))
        )
        # Layout
        layout_updates_boxplot = DEFAULT_LAYOUT.copy()
        layout_updates_boxplot.update({
            'yaxis': dict(showgrid=True, zeroline=False, tickfont=dict(size=12, color='black'), title=None, type='linear', tickformat='d'),
            'xaxis': dict(showgrid=False, tickfont=dict(size=12, color='black'), tickangle=45, title=None, categoryorder='array', categoryarray=sorted(df_boxplot_ano['DESC_UND_FED'].unique())),
            'showlegend': False, 'margin': dict(l=60, r=50, t=50, b=120)
        })
        all_ufs_box_updated = sorted(df_boxplot_ano['DESC_UND_FED'].unique())
        x_ticktext_box_updated = [f"<b>{label}</b>" if label == 'Goiás' else f"{label}" for label in all_ufs_box_updated]
        layout_updates_boxplot['xaxis']['ticktext'] = x_ticktext_box_updated
        layout_updates_boxplot['xaxis']['tickvals'] = all_ufs_box_updated
        fig_boxplot_updated.update_layout(layout_updates_boxplot)

        return fig_boxplot_updated

    except Exception as e:
        logging.exception("Erro ao gerar Boxplot atualizado para %s, ano %s:", indicador_id, selected_year)
        return go.Figure().update_layout(title=f'Erro ao gerar Boxplot para {selected_year}.',
                                        xaxis={'visible': False}, yaxis={'visible': False})

if __name__ == '__main__':
    # Verifica se o arquivo .env existe
    if not os.path.exists('.env'):
        logging.warning("Arquivo .env não encontrado. Criando com configurações padrão...")

        # Gera uma nova SECRET_KEY e atualiza o arquivo .env
        new_secret_key = generate_secret_key()
        update_env_file(generate_password_hash(MAINTENANCE_PASSWORD))

        logging.info("Arquivo .env criado com sucesso!")
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
