import json.decoder
from functools import lru_cache
from pathlib import Path
import time

import pandas as pd
import requests

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
                print(f'Erro de conexão após {max_retries + 1} tentativas para o '
                      f'indicador {indicador}: {e}')
            else:
                print(f'Tentativa {retry_count} falhou. '
                      f'Tentando novamente em 5 segundos...')
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
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Converter CODG_ANO para string
    if 'CODG_ANO' in df.columns:
        df['CODG_ANO'] = df['CODG_ANO'].astype(str)
    
    # Converter colunas categóricas
    for col in colunas_categoricas:
        if col in df.columns:
            df[col] = df[col].astype('category')
    
    return df


def process_indicadores(filtered_list_indicadores, url_base, list_colunas,
                       df_und_med, df_variavel, df_indicadores):
    for objetivo in filtered_list_indicadores.keys():
        for meta in filtered_list_indicadores[objetivo].keys():
            for indicador in filtered_list_indicadores[objetivo][meta].keys():
                link = url_base + str(filtered_list_indicadores[objetivo][meta].get(indicador))
                try:
                    df_temp = pd.DataFrame(get_sidra_data(link))
                    df_temp.columns = df_temp.iloc[(0,)]
                    df_temp = df_temp[1:]
                    df_temp = df_temp.rename(columns=list_colunas)
                    df_temp.insert(0, 'ID_INDICADOR',
                                 f'Indicador {indicador.split("Indicador")[1]}')
                    df_und_med = pd.concat([df_und_med, df_temp[['CODG_UND_MED',
                                                                'DESC_UND_MED']]])
                    df_variavel = pd.concat([df_variavel, df_temp[['CODG_VAR',
                                                              'DESC_VAR']]])
                    try:
                        # Lista de todas as colunas que queremos remover
                        colunas_para_remover = [
                            'CODG_NIV_TER', 'DESC_NIV_TER', 'DESC_UND_MED',
                            'DESC_VAR', 'DESC_ANO', 'DESC_UND_FED', 'DESC_IDADE',
                            'DESC_SEXO', 'DESC_SIT_SEG_ALI_DOM', 'DESC_RACA',
                            'DESC_TIPO_DOENCA', 'DESC_BIENIO',
                            'DESC_DEF_GAST_SAUDE', 'DESC_GRU_IDADE_NIV_ENS',
                            'DESC_SIT_DOM', 'DESC_REGIAO',
                            'DESC_CLAS_PERC_REND_DOM_PER_CAP', 'DESC_INF_ESC',
                            'DESC_GRUP_ATIV_TRAB', 'DESC_ATV_TRAB', 'DESC_DEF',
                            'DESC_GRUP_OCUP_TRAB_PNAD', 'DESC_TIP_MOV',
                            'DESC_TIP_MEIO_TRANSP', 'DESC_ATV_IND_SET_IND',
                            'DESC_TIP_COB_TEF_MOV', 'DESC_MES_ANO',
                            'DESC_TRI_ANO', 'DESC_SEXENIO', 'DESC_TIP_PATR',
                            'DESC_NIV_GOV', 'DESC_DISP_FINAL', 'DESC_TRIENIO',
                            'DESC_FAI_PESS_OCUP', 'DESC_FONT_EMIS_GAS_EFEITO_EST',
                            'DESC_BIOMA', 'DESC_KAPOS', 'DESC_NIV_INSTR',
                            'DESC_ETAPA_ENS', 'DESC_REND_MENSAL_DOM_PER_CAP',
                            'DESC_NIV_INST_PUBL', 'DESC_VEL_LIGACAO',
                            'DESC_REG_HIDR', 'DESC_SET_ATIV', 'DESC_ECO_REL_AGUA',
                            'DESC_TIP_DIN_ECO_REL_AGUA',
                            'DESC_TIP_DESB_BRUTO_AJUDA_OFICIAL'
                        ]

                        # Filtra apenas as colunas que existem no DataFrame
                        colunas_existentes = [col for col in colunas_para_remover
                                            if col in df_temp.columns]

                        if colunas_existentes:
                            df_temp = df_temp.drop(columns=colunas_existentes)
                        else:
                            print(f'Nenhuma das colunas descritivas foi '
                                  f'encontrada no indicador: {indicador}')

                    except Exception as e:
                        print(f'Erro ao remover colunas do indicador {indicador}: '
                              f'{str(e)}')

                    list_var = list(df_temp['CODG_VAR'].value_counts().to_dict().keys())
                    if len(list_var) > 1:
                        df_combined = pd.DataFrame()
                        for cod_var in list_var:
                            df_temp_var = df_temp[df_temp['CODG_VAR'] == cod_var].copy()
                            # Converte os tipos de dados antes de concatenar
                            df_temp_var = converter_tipos_dados(df_temp_var)
                            df_combined = pd.concat([df_combined, df_temp_var],
                                                  ignore_index=True)
                        
                        # Salva o arquivo parquet
                        arquivo_parquet = str(Path(__file__).parent) + f'/db/resultados/{indicador.lower().replace(' ', '')}.parquet'
                        df_combined.to_parquet(arquivo_parquet)
                        
                        # Salva os metadados
                        metadados = {
                            'colunas': {
                                col: str(df_combined[col].dtype) for col in df_combined.columns
                            },
                            'total_linhas': len(df_combined),
                            'total_colunas': len(df_combined.columns),
                            'colunas_numericas': [col for col in df_combined.columns if pd.api.types.is_numeric_dtype(df_combined[col])],
                            'colunas_categoricas': [col for col in df_combined.columns if isinstance(df_combined[col].dtype, pd.CategoricalDtype)],
                            'data_criacao': time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        # Salva os metadados em um arquivo JSON
                        arquivo_metadados = str(Path(__file__).parent) + f'/db/resultados/{indicador.lower().replace(' ', '')}_metadata.json'
                        with open(arquivo_metadados, 'w', encoding='utf-8') as f:
                            json.dump(metadados, f, ensure_ascii=False, indent=4)
                        
                        # Atualiza a coluna VARIAVEIS baseado na presença de variáveis
                        df_indicadores.loc[df_indicadores['ID_INDICADOR'] == indicador,
                                         'VARIAVEIS'] = 1

                        # Salva o DataFrame atualizado no indicadores.csv
                        df_indicadores.to_csv(Path(__file__).parent / 'db/indicadores.csv',
                                            sep=';', index=False)
                    else:
                        # Converte os tipos de dados antes de salvar
                        df_temp = converter_tipos_dados(df_temp)
                        
                        # Salva o arquivo parquet
                        arquivo_parquet = str(Path(__file__).parent) + f'/db/resultados/{indicador.lower().replace(' ', '')}.parquet'
                        df_temp.to_parquet(arquivo_parquet)
                        
                        # Salva os metadados
                        metadados = {
                            'colunas': {
                                col: str(df_temp[col].dtype) for col in df_temp.columns
                            },
                            'total_linhas': len(df_temp),
                            'total_colunas': len(df_temp.columns),
                            'colunas_numericas': [col for col in df_temp.columns if pd.api.types.is_numeric_dtype(df_temp[col])],
                            'colunas_categoricas': [col for col in df_temp.columns if isinstance(df_temp[col].dtype, pd.CategoricalDtype)],
                            'data_criacao': time.strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        # Salva os metadados em um arquivo JSON
                        arquivo_metadados = str(Path(__file__).parent) + f'/db/resultados/{indicador.lower().replace(' ', '')}_metadata.json'
                        with open(arquivo_metadados, 'w', encoding='utf-8') as f:
                            json.dump(metadados, f, ensure_ascii=False, indent=4)

                except json.decoder.JSONDecodeError as e:
                    print(f'Erro ao processar o arquivo {indicador}.csv: {e}')

                print(f'O arquivo {indicador.lower().replace(' ', '')}.parquet '
                      f'foi criado.')

                df_und_med.to_csv(str(Path(__file__).parent) +
                                f'/db/unidade_medida.csv', sep=';', index=False)
                df_variavel.to_csv(str(Path(__file__).parent) +
                               f'/db/variavel.csv', sep=';', index=False)
        print(f'{objetivo} finalizado!')


def main():
    url_base = 'https://apisidra.ibge.gov.br/values'

    list_col_padrao = {'ID_INDICADOR', 'CODG_UND_MED', 'CODG_UND_FED',
                       'CODG_VAR', 'VLR_VAR', 'CODG_ANO'}

    df_und_med = pd.DataFrame(columns=['CODG_UND_MED', 'DESC_UND_MED'])
    df_variavel = pd.DataFrame(columns=['CODG_VAR', 'DESC_VAR'])

    # Carregar os indicadores
    df_indicadores = load_indicadores()
    df_indicadores = df_indicadores[df_indicadores['RBC'] == True]
    indicadores_ids = df_indicadores['ID_INDICADOR'].tolist()

    filtered_list_indicadores = filter_indicadores(LIST_INDICADORES,
                                                 indicadores_ids)

    process_indicadores(filtered_list_indicadores, url_base, LIST_COLUNAS,
                       df_und_med, df_variavel, df_indicadores)

    remove_duplicates_from_csv(str(Path(__file__).parent) +
                             f'/db/unidade_medida.csv').sort_values(by='CODG_UND_MED').to_csv(
        str(Path(__file__).parent) + f'/db/unidade_medida.csv',
        header=True, index=False, sep=';')
    remove_duplicates_from_csv(str(Path(__file__).parent) +
                             f'/db/variavel.csv').sort_values(by='CODG_VAR').to_csv(
        str(Path(__file__).parent) + f'/db/variavel.csv',
        header=True, index=False, sep=';')


if __name__ == '__main__':
    main()
