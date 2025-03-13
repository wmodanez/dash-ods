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
            'tem_colunas_adicionais': bool(colunas_adicionais),
            'colunas_adicionais': list(colunas_adicionais),
            'tem_colunas_temporais': tem_colunas_temporais,
            'tem_colunas_categoricas': tem_colunas_categoricas,
            'sugestoes_visualizacao': sugestoes
        }
        
    except Exception as e:
        print(f"Erro ao analisar arquivo {file_path}: {e}")
        return None

def main():
    # Diretório dos indicadores
    indicators_dir = 'db'
    
    # Lista para armazenar todas as sugestões
    all_suggestions = []
    
    # Analisa cada arquivo parquet no diretório
    for file in os.listdir(indicators_dir):
        if file.endswith('.parquet') and file.startswith('indicador'):
            file_path = os.path.join(indicators_dir, file)
            suggestions = analyze_indicator(file_path)
            all_suggestions.extend(suggestions)
    
    # Converte para DataFrame
    df_suggestions = pd.DataFrame(all_suggestions)
    
    # Ordena por ID_INDICADOR e PRIORIDADE
    df_suggestions = df_suggestions.sort_values(['ID_INDICADOR', 'PRIORIDADE'])
    
    # Remove a coluna de prioridade
    df_suggestions = df_suggestions.drop('PRIORIDADE', axis=1)
    
    # Salva as sugestões
    df_suggestions.to_csv('db/sugestoes_visualizacao.csv', sep=';', index=False)
    
    # Cria um arquivo com sugestões aleatórias (máximo 3 por indicador)
    random_suggestions = []
    for indicator in df_suggestions['ID_INDICADOR'].unique():
        indicator_suggestions = df_suggestions[df_suggestions['ID_INDICADOR'] == indicator]
        num_suggestions = min(3, len(indicator_suggestions))
        random_suggestions.extend(indicator_suggestions.sample(n=num_suggestions).to_dict('records'))
    
    # Salva as sugestões aleatórias
    pd.DataFrame(random_suggestions).to_csv('db/sugestoes_visualizacao_aleatorias.csv', sep=';', index=False)

if __name__ == '__main__':
    main() 