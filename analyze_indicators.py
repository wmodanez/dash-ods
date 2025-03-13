import pandas as pd
import numpy as np
import os
import random
from pathlib import Path

def analyze_indicator(file_path):
    """
    Analisa um arquivo parquet e gera sugestões de visualização baseadas em sua estrutura.

    Args:
        file_path (str): Caminho do arquivo parquet

    Returns:
        dict: Dicionário com informações sobre o indicador e sugestões de visualização
    """
    try:
        # Lê o arquivo parquet
        df = pd.read_parquet(file_path)
        
        # Define colunas básicas e adicionais
        colunas_basicas = {
            'ID_INDICADOR',
            'CODG_UND_MED',
            'VLR_VAR',
            'CODG_UND_FED',
            'CODG_VAR',
            'CODG_ANO'
        }
        
        colunas_temporais = {'ANO', 'MES', 'TRIMESTRE', 'SEMESTRE', 'DATA'}
        colunas_categoricas = {'DESCRICAO', 'CATEGORIA', 'TIPO', 'CLASSIFICACAO', 'NIVEL'}
        
        # Verifica estrutura do arquivo
        colunas_arquivo = set(df.columns)
        tem_estrutura_padrao = colunas_basicas.issubset(colunas_arquivo)
        colunas_adicionais = colunas_arquivo - colunas_basicas
        tem_colunas_temporais = bool(colunas_adicionais & colunas_temporais)
        tem_colunas_categoricas = bool(colunas_adicionais & colunas_categoricas)
        tem_colunas_adicionais = bool(colunas_adicionais)
        
        # Gera sugestões de visualização
        sugestoes = []
        
        # Sugestões básicas
        sugestoes.extend([
            {
                'tipo': 'bar',
                'titulo': 'Gráfico de Barras',
                'descricao': 'Visualização em barras dos valores por unidade federativa',
                'config': {
                    'x': 'CODG_UND_FED',
                    'y': 'VLR_VAR',
                    'color': 'CODG_UND_FED'
                }
            },
            {
                'tipo': 'line',
                'titulo': 'Gráfico de Linha',
                'descricao': 'Evolução temporal dos valores',
                'config': {
                    'x': 'CODG_ANO',
                    'y': 'VLR_VAR',
                    'color': 'CODG_UND_FED'
                }
            }
        ])
        
        # Sugestões para dados temporais
        if tem_colunas_temporais:
            sugestoes.extend([
                {
                    'tipo': 'area',
                    'titulo': 'Gráfico de Área Temporal',
                    'descricao': 'Evolução temporal com área preenchida',
                    'config': {
                        'x': 'DATA',
                        'y': 'VLR_VAR',
                        'color': 'CODG_UND_FED'
                    }
                },
                {
                    'tipo': 'heatmap',
                    'titulo': 'Heatmap Temporal',
                    'descricao': 'Visualização de padrões temporais',
                    'config': {
                        'x': 'MES',
                        'y': 'CODG_UND_FED',
                        'z': 'VLR_VAR'
                    }
                }
            ])
        
        # Sugestões para dados categóricos
        if tem_colunas_categoricas:
            sugestoes.extend([
                {
                    'tipo': 'pie',
                    'titulo': 'Gráfico de Pizza',
                    'descricao': 'Distribuição por categoria',
                    'config': {
                        'values': 'VLR_VAR',
                        'names': 'CATEGORIA'
                    }
                },
                {
                    'tipo': 'treemap',
                    'titulo': 'Gráfico de Treemap',
                    'descricao': 'Visualização hierárquica por categoria',
                    'config': {
                        'path': ['CATEGORIA', 'TIPO'],
                        'values': 'VLR_VAR'
                    }
                }
            ])
        
        # Sugestões para análise de distribuição
        sugestoes.extend([
            {
                'tipo': 'histogram',
                'titulo': 'Histograma',
                'descricao': 'Distribuição dos valores',
                'config': {
                    'x': 'VLR_VAR',
                    'nbinsx': 30
                }
            },
            {
                'tipo': 'box',
                'titulo': 'Box Plot',
                'descricao': 'Distribuição estatística por unidade federativa',
                'config': {
                    'x': 'CODG_UND_FED',
                    'y': 'VLR_VAR'
                }
            }
        ])
        
        # Sugestões para análise de correlação
        if tem_colunas_adicionais:
            sugestoes.extend([
                {
                    'tipo': 'scatter',
                    'titulo': 'Gráfico de Dispersão',
                    'descricao': 'Correlação entre variáveis',
                    'config': {
                        'x': 'VLR_VAR',
                        'y': 'CODG_ANO',
                        'color': 'CODG_UND_FED'
                    }
                },
                {
                    'tipo': 'bubble',
                    'titulo': 'Gráfico de Bolhas',
                    'descricao': 'Visualização multidimensional',
                    'config': {
                        'x': 'CODG_ANO',
                        'y': 'VLR_VAR',
                        'size': 'CODG_UND_MED',
                        'color': 'CODG_UND_FED'
                    }
                }
            ])
        
        return {
            'tem_estrutura_padrao': tem_estrutura_padrao,
            'tem_colunas_adicionais': tem_colunas_adicionais,
            'colunas_adicionais': list(colunas_adicionais),
            'tem_colunas_temporais': tem_colunas_temporais,
            'tem_colunas_categoricas': tem_colunas_categoricas,
            'sugestoes_visualizacao': sugestoes
        }
        
    except Exception as e:
        print(f"Erro ao analisar arquivo {file_path}: {e}")
        return None

def main():
    """
    Função principal que analisa os indicadores e gera sugestões de visualização.
    """
    # Diretório dos indicadores
    indicators_dir = Path('db/resultados')
    
    # Lista para armazenar todas as análises
    todas_analises = []
    
    # Lista para armazenar a ordem dos arquivos
    ordem_arquivos = []
    
    # Analisa cada arquivo parquet no diretório
    for arquivo in indicators_dir.glob('*.parquet'):
        if arquivo.name.startswith('indicador'):
            ordem_arquivos.append(arquivo.name)
            print(f"Analisando arquivo: {arquivo.name}")
            analise = analyze_indicator(str(arquivo))
            if analise:
                # Adiciona o ID do indicador à análise
                analise['id_indicador'] = arquivo.name.replace('.parquet', '').replace('indicador', '')
                todas_analises.append(analise)
    
    if not todas_analises:
        print("Nenhuma análise foi realizada com sucesso.")
        return
    
    # Converte para DataFrame
    df_analises = pd.DataFrame(todas_analises)
    
    # Cria um DataFrame com as sugestões expandidas
    sugestoes_expandidas = []
    for _, row in df_analises.iterrows():
        id_indicador = row['id_indicador']
        for sugestao in row['sugestoes_visualizacao']:
            sugestao['ID_INDICADOR'] = f"Indicador {id_indicador}"
            sugestoes_expandidas.append(sugestao)
    
    if not sugestoes_expandidas:
        print("Nenhuma sugestão foi gerada.")
        return
    
    df_sugestoes = pd.DataFrame(sugestoes_expandidas)
    
    # Reordena as colunas para colocar ID_INDICADOR primeiro
    colunas = ['ID_INDICADOR'] + [col for col in df_sugestoes.columns if col != 'ID_INDICADOR']
    df_sugestoes = df_sugestoes[colunas]
    
    # Ordena os indicadores conforme a ordem de leitura
    ordem_indicadores = [f"Indicador {nome.replace('.parquet', '').replace('indicador', '')}" for nome in ordem_arquivos]
    df_sugestoes['ordem'] = df_sugestoes['ID_INDICADOR'].map(lambda x: ordem_indicadores.index(x))
    df_sugestoes = df_sugestoes.sort_values('ordem')
    df_sugestoes = df_sugestoes.drop('ordem', axis=1)
    
    # Salva as sugestões completas
    df_sugestoes.to_csv('db/sugestoes_visualizacao.csv', sep=';', index=False, encoding='utf-8')
    print(f"\nArquivo sugestoes_visualizacao.csv atualizado com sucesso!")
    print(f"Total de sugestões geradas: {len(df_sugestoes)}")
      
    # Mostra estatísticas
    print("\nEstatísticas:")
    print(f"Total de indicadores analisados: {len(df_analises)}")
    print(f"Indicadores com estrutura padrão: {df_analises['tem_estrutura_padrao'].sum()}")
    print(f"Indicadores com colunas temporais: {df_analises['tem_colunas_temporais'].sum()}")
    print(f"Indicadores com colunas categóricas: {df_analises['tem_colunas_categoricas'].sum()}")
    print(f"Indicadores com colunas adicionais: {df_analises['tem_colunas_adicionais'].sum()}")

if __name__ == '__main__':
    main() 