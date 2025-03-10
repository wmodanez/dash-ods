import json.decoder
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests
from pandas import DataFrame
from constants import LIST_INDICADORES, LIST_COLUNAS

def get_sidra_data(indicador):
    max_retries = 5
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = requests.get(indicador, timeout=90)
            response.encoding = 'UTF-8'

            if response.status_code == 200:
                data = response.json()
                return data

        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                print(f'Erro de conexão após {max_retries + 1} tentativas para o indicador {indicador}: {e}')
            else:
                print(f'Tentativa {retry_count} falhou. Tentando novamente em 5 segundos...')
                time.sleep(5)
    return None


@lru_cache(maxsize=1)
def load_indicadores() -> pd.DataFrame:
    df: pd.DataFrame = pd.read_csv(
        Path(__file__).parent / 'db/indicadores.csv', sep=';'
    )
    # df = df[df['RBC'] == True]
    return df


@lru_cache(maxsize=1)
def remove_duplicates_from_csv(file_path: str) -> pd.DataFrame:
    df: DataFrame = pd.read_csv(file_path, sep=';', na_filter=False)
    df = df.drop_duplicates()
    df.columns = df.columns.str.replace('"', '').str.replace("'", '')
    return df


# Filtrar a lista de indicadores
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


# Processar apenas os indicadores filtrados
def process_indicadores(filtered_list_indicadores, URL_BASE, list_colunas, df_und_med, df_filtro, df_indicadores):
    for objetivo in filtered_list_indicadores.keys():
        for meta in filtered_list_indicadores[objetivo].keys():
            for indicador in filtered_list_indicadores[objetivo][meta].keys():
                link = URL_BASE + str(filtered_list_indicadores[objetivo][meta].get(indicador))
                try:
                    df_temp = pd.DataFrame(get_sidra_data(link))
                    df_temp.columns = df_temp.iloc[0]
                    df_temp = df_temp[1:]
                    df_temp = df_temp.rename(columns=list_colunas)
                    df_temp.insert(0, 'ID_INDICADOR', f'Indicador {indicador.split("Indicador")[1]}')
                    df_und_med = pd.concat([df_und_med, df_temp[['CODG_UND_MED', 'DESC_UND_MED']]])
                    df_filtro = pd.concat([df_filtro, df_temp[['CODG_VAR', 'DESC_VAR']]])
                    try:
                        df_temp = df_temp.drop(
                            columns=['CODG_NIV_TER', 'DESC_NIV_TER', 'DESC_UND_MED', 'DESC_VAR', 'DESC_ANO'])
                    except KeyError as e:
                        print(f'Erro ao remover colunas do indicador: {indicador}')
                    list_var = list(df_temp['CODG_VAR'].value_counts().to_dict().keys())
                    if len(list_var) > 1:
                        df_combined = pd.DataFrame()
                        for cod_var in list_var:
                            df_temp_var = df_temp[df_temp['CODG_VAR'] == cod_var].copy()
                            df_temp_var['SUB_INDICADOR'] = cod_var
                            df_combined = pd.concat([df_combined, df_temp_var], ignore_index=True)
                        df_combined.to_parquet(str(Path(__file__).parent) + f'/db/resultados/{indicador.lower().replace(' ', '')}.parquet')
                        # Update the VARIAVEIS column based on the presence of variables
                        df_indicadores.loc[df_indicadores['ID_INDICADOR'] == indicador, 'VARIAVEIS'] = 1

                        # Save the updated DataFrame back to indicadores.csv
                        df_indicadores.to_csv(Path(__file__).parent / 'db/indicadores.csv', sep=';', index=False)
                    else:
                        df_temp.to_parquet(str(Path(__file__).parent) + f'/db/resultados/{indicador.lower().replace(' ', '')}.parquet')
                    try:
                        df_other_columns = df_temp.drop(columns=LIST_COL_PADRAO)
                    except KeyError as e:
                        print(f'Erro ao remover colunas do indicador: {indicador}')
                    if len(df_other_columns.columns) > 1:
                        for coluna in df_other_columns:
                            if 'CODG' in coluna:
                                df_other_columns['TIPO_CAMPO'] = coluna
                except json.decoder.JSONDecodeError as e:
                    print(f'Erro ao processar o arquivo {indicador}.csv: {e}')

                print(f'O arquivo {indicador.lower().replace(' ', '')}.parquet foi criado.')

                df_und_med.to_csv(str(Path(__file__).parent) + f'/db/unidade_medida.csv', index=False)
                df_filtro.to_csv(str(Path(__file__).parent) + f'/db/filtro.csv', index=False)
        print(f'{objetivo} finalizado!')


URL_BASE = 'https://apisidra.ibge.gov.br/values'

LIST_COL_PADRAO: list = {'CODG_UND_MED', 'CODG_UND_FED', 'CODG_VAR', 'VLR_VAR', 'CODG_ANO'}

df_und_med = pd.DataFrame(columns=['CODG_UND_MED', 'DESC_UND_MED'])
df_variavel = pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])
df_filtro = pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])

# Carregar os indicadores
df_indicadores = load_indicadores()
df_indicadores = df_indicadores[df_indicadores['RBC'] == True]
indicadores_ids = df_indicadores['ID_INDICADOR'].tolist()

filtered_list_indicadores = filter_indicadores(LIST_INDICADORES, indicadores_ids)

process_indicadores(filtered_list_indicadores, URL_BASE, LIST_COLUNAS, df_und_med, df_filtro, df_indicadores)

remove_duplicates_from_csv(str(Path(__file__).parent) + f'/db/unidade_medida.csv').to_csv(
    str(Path(__file__).parent) + f'/db/unidade_medida.csv', header=True, index=False, sep=';')
remove_duplicates_from_csv(str(Path(__file__).parent) + f'/db/filtro.csv').to_csv(
    str(Path(__file__).parent) + f'/db/filtro.csv', header=True, index=False, sep=';')
