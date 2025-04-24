import json.decoder
from functools import lru_cache
from pathlib import Path
import time
import logging

import pandas as pd
import requests
import numpy as np

from constants import LIST_INDICADORES, LIST_COLUNAS

# Configuração inicial de logging (pode ser ajustada se necessário)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()]) # Log para o console

def get_sidra_data(indicador):
    max_retries = 5
    retry_count = 0
    while retry_count < max_retries:
        try:
            logging.info(f"Tentando obter dados de: {indicador}")
            response = requests.get(indicador, timeout=90)
            response.encoding = 'UTF-8'

            if response.status_code == 200:
                logging.info(f"Sucesso ao obter dados de: {indicador}")
                data = response.json()
                return data
            else:
                logging.warning(f"Falha ao obter dados de {indicador}. Status code: {response.status_code}")

        except Exception as e:
            logging.warning(f"Exceção ao tentar obter dados de {indicador}: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                logging.error(f'Erro de conexão após {max_retries} tentativas para o indicador {indicador}: {e}')
            else:
                logging.warning(f'Tentativa {retry_count}/{max_retries} falhou para {indicador}. Tentando novamente em 5 segundos...')
                time.sleep(5)
    return None


@lru_cache(maxsize=1)
def load_indicadores() -> pd.DataFrame:
    df = pd.read_csv(
        Path(__file__).parent / 'db/indicadores.csv', sep=';'
    )
    return df


@lru_cache(maxsize=1)
def remove_duplicates_from_csv(file_path: str) -> pd.DataFrame:
    df = pd.read_csv(file_path, sep=';', na_filter=False)
    df = df.drop_duplicates()
    df.columns = df.columns.str.replace('"', '').str.replace("'", '')
    return df


def filter_indicadores(list_indicadores, indicadores_ids):
    return {
        objetivo: {
            meta: {
                indicador: url
                for indicador, url in metas.items()
                if indicador in indicadores_ids
            }
            for meta, metas in metas_objetivo.items()
        }
        for objetivo, metas_objetivo in list_indicadores.items()
    }


def converter_tipos_dados(df):
    """
    Converte os tipos de dados do DataFrame para formatos mais apropriados.
    
    Args:
        df (pd.DataFrame): DataFrame com os dados a serem convertidos
        
    Returns:
        pd.DataFrame: DataFrame com os tipos de dados convertidos
    """
    # Colunas que devem ser numéricas
    colunas_numericas = ['VLR_VAR']
    
    # Colunas que devem ser categóricas
    colunas_categoricas = [
        'ID_INDICADOR', 'CODG_UND_MED', 'CODG_UND_FED', 'CODG_VAR',
        'CODG_SEXO', 'CODG_IDADE', 'CODG_RACA', 'CODG_SIT_DOM',
        'CODG_NIV_INSTR', 'CODG_REND_MENSAL_DOM_PER_CAP',
        'COD_GRU_IDADE_NIV_ENS', 'CODG_INF_ESC', 'CODG_ETAPA_ENS',
        'CODG_SET_ATIV', 'CODG_ECO_REL_AGUA', 'CODG_TIP_DIN_ECO_REL_AGUA',
        'CODG_TIPO_DOENCA', 'CODG_DEF', 'CODG_ATV_TRAB'
    ]
    
    # Converter colunas numéricas
    for col in colunas_numericas:
        if col in df.columns:
            try:
                # Modificado: Limpeza antes da conversão numérica
                df[col] = df[col].astype(str)
                codes_to_nan = ["...", "-", "X"]
                df[col] = df[col].replace(codes_to_nan, np.nan)
                df[col] = df[col].str.replace('.', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception as e:
                logging.error(f"Erro ao converter coluna numérica '{col}': {e}")
                # Decide se quer parar ou continuar com a coluna como objeto
                # df[col] = pd.Series(dtype='object') # Exemplo: Mantém como objeto se falhar
    
    # Converter CODG_ANO para string
    if 'CODG_ANO' in df.columns:
        try:
            df['CODG_ANO'] = df['CODG_ANO'].astype(str)
        except Exception as e:
            logging.error(f"Erro ao converter CODG_ANO para string: {e}")
    
    # Converter colunas categóricas
    for col in colunas_categoricas:
        if col in df.columns:
            try:
                df[col] = df[col].astype('category')
            except Exception as e:
                logging.error(f"Erro ao converter coluna '{col}' para category: {e}")
    
    return df


def process_indicadores(filtered_list_indicadores, url_base, list_colunas,
                       df_und_med, df_variavel, df_indicadores):
    # Define o diretório base de resultados uma vez
    base_dir = Path(__file__).parent
    results_dir = base_dir / 'db' / 'resultados'

    for objetivo in filtered_list_indicadores.keys():
        for meta in filtered_list_indicadores[objetivo].keys():
            for indicador in filtered_list_indicadores[objetivo][meta].keys():
                link = url_base + str(filtered_list_indicadores[objetivo][meta].get(indicador))
                data = get_sidra_data(link)

                if data is None:
                    logging.error(f"Não foi possível obter dados para o indicador {indicador} após múltiplas tentativas. Pulando.")
                    continue

                try:
                    df_temp = pd.DataFrame(data)
                    if df_temp.empty or len(df_temp) < 2:
                        logging.warning(f"DataFrame vazio ou sem header para {indicador}. Pulando.")
                        continue

                    df_temp.columns = df_temp.iloc[(0,)]
                    df_temp = df_temp[1:]
                    df_temp = df_temp.rename(columns=list_colunas)
                    df_temp.insert(0, 'ID_INDICADOR',
                                 f'Indicador {indicador.split("Indicador")[1]}')

                    # Adiciona dados aos dataframes auxiliares ANTES de remover colunas
                    if 'CODG_UND_MED' in df_temp.columns and 'DESC_UND_MED' in df_temp.columns:
                       df_und_med = pd.concat([df_und_med, df_temp[['CODG_UND_MED', 'DESC_UND_MED']]])
                    if 'CODG_VAR' in df_temp.columns and 'DESC_VAR' in df_temp.columns:
                       df_variavel = pd.concat([df_variavel, df_temp[['CODG_VAR', 'DESC_VAR']]])

                    # --- Remoção de Colunas Descritivas --- 
                    colunas_para_remover = [
                        'CODG_NIV_TER', 'DESC_NIV_TER', # Nível territorial
                        'DESC_UND_MED', 'DESC_VAR',    # Descrições de Unid. Medida e Variável (já tratadas)
                        'DESC_ANO',                    # Descrição do Ano (usamos CODG_ANO)
                        # Manter outras DESC_* (DESC_SEXO, DESC_RACA, etc.) para usar nos filtros
                    ]
                    colunas_existentes = [col for col in colunas_para_remover if col in df_temp.columns]
                    if colunas_existentes:
                        df_temp = df_temp.drop(columns=colunas_existentes)
                    else:
                        logging.warning(f'Nenhuma das colunas descritivas padrão foi encontrada no indicador: {indicador}')
                    # --- Fim Remoção --- 

                    list_var = df_temp['CODG_VAR'].unique().tolist() if 'CODG_VAR' in df_temp.columns else []

                    # Define nome base do arquivo
                    filename_part = indicador.lower().replace(' ', '')
                    arquivo_parquet = results_dir / f'{filename_part}.parquet'
                    arquivo_metadados = results_dir / f'{filename_part}_metadata.json'

                    # Corrigido: Cria o diretório ANTES de salvar
                    results_dir.mkdir(parents=True, exist_ok=True)

                    if len(list_var) > 1:
                        df_combined = pd.DataFrame()
                        for cod_var in list_var:
                            df_temp_var = df_temp[df_temp['CODG_VAR'] == cod_var].copy()
                            df_temp_var = converter_tipos_dados(df_temp_var)
                            df_combined = pd.concat([df_combined, df_temp_var], ignore_index=True)

                        df_to_save = df_combined
                        # Atualiza a coluna VARIAVEIS
                        df_indicadores.loc[df_indicadores['ID_INDICADOR'] == indicador, 'VARIAVEIS'] = 1
                        # Salva o DataFrame atualizado no indicadores.csv (apenas se necessário?)
                        # Considerar salvar apenas no final para performance
                    else:
                        df_temp = converter_tipos_dados(df_temp)
                        df_to_save = df_temp

                    # Salva Parquet
                    df_to_save.to_parquet(arquivo_parquet)

                    # Salva Metadados
                    metadados = {
                        'colunas': {col: str(df_to_save[col].dtype) for col in df_to_save.columns},
                        'total_linhas': len(df_to_save),
                        'total_colunas': len(df_to_save.columns),
                        'colunas_numericas': [col for col in df_to_save.columns if pd.api.types.is_numeric_dtype(df_to_save[col])],
                        'colunas_categoricas': [col for col in df_to_save.columns if isinstance(df_to_save[col].dtype, pd.CategoricalDtype)],
                        'data_criacao': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    with open(arquivo_metadados, 'w', encoding='utf-8') as f:
                        json.dump(metadados, f, ensure_ascii=False, indent=4)

                    logging.info(f'Arquivo {filename_part}.parquet e metadados criados.')

                except json.decoder.JSONDecodeError as e:
                    logging.exception(f'Erro de JSONDecode ao processar dados para {indicador}: {e}')
                except KeyError as e:
                    logging.exception(f"Erro de KeyError (coluna faltando?) ao processar {indicador}: {e}")
                except Exception as e:
                    logging.exception(f'Erro inesperado ao processar o indicador {indicador}: {e}')

                print(f'O arquivo {filename_part}.parquet foi criado.')

                df_und_med.to_csv(str(Path(__file__).parent) +
                                f'/db/unidade_medida.csv', sep=';', index=False)
                df_variavel.to_csv(str(Path(__file__).parent) +
                               f'/db/variavel.csv', sep=';', index=False)
        print(f'{objetivo} finalizado!')


def main():
    # Configuração de logging movida para o topo do módulo
    logging.info("Iniciando atualização da base de dados...")
    url_base = 'https://apisidra.ibge.gov.br/values'

    # Carrega/inicializa DataFrames auxiliares
    # É mais seguro ler os arquivos existentes se eles já tiverem dados consolidados
    db_path = Path(__file__).parent / 'db'
    try:
        df_und_med = pd.read_csv(db_path / 'unidade_medida.csv', sep=';')
    except FileNotFoundError:
        df_und_med = pd.DataFrame(columns=['CODG_UND_MED', 'DESC_UND_MED'])
    try:
        df_variavel = pd.read_csv(db_path / 'variavel.csv', sep=';')
    except FileNotFoundError:
        df_variavel = pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])

    # Carregar os indicadores
    try:
        df_indicadores = load_indicadores()
        df_indicadores = df_indicadores[df_indicadores['RBC'] == True].copy() # Pega apenas RBC=True e cria cópia
        # Garante que a coluna 'VARIAVEIS' exista, inicializando com 0 se necessário
        if 'VARIAVEIS' not in df_indicadores.columns:
             df_indicadores['VARIAVEIS'] = 0
        else:
             df_indicadores['VARIAVEIS'] = df_indicadores['VARIAVEIS'].fillna(0).astype(int)

        indicadores_ids = df_indicadores['ID_INDICADOR'].tolist()
        logging.info(f"{len(indicadores_ids)} indicadores RBC encontrados para processar.")
    except Exception as e:
        logging.exception("Erro ao carregar ou processar o arquivo db/indicadores.csv. Abortando.")
        return

    filtered_list_indicadores = filter_indicadores(LIST_INDICADORES, indicadores_ids)

    process_indicadores(filtered_list_indicadores, url_base, LIST_COLUNAS,
                       df_und_med, df_variavel, df_indicadores)

    # Remoção de duplicatas e salvamento final movidos para dentro de process_indicadores
    # para salvar após cada objetivo.

    logging.info("Atualização da base de dados concluída.")


if __name__ == '__main__':
    main()
