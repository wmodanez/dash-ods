import pandas as pd
from pathlib import Path


def analisar_arquivo(arquivo):
    """
    Analisa um arquivo parquet e retorna informações básicas sobre sua estrutura.
    """
    try:
        df = pd.read_parquet(arquivo)
        return {
            'total_registros': len(df),
            'colunas': df.columns.tolist(),
            'tipos': df.dtypes.to_dict()
        }
    except Exception as e:
        print(f"Erro ao analisar {arquivo.name}: {e}")
        return None


def main():
    # Diretório dos arquivos parquet
    diretorio = Path('db/resultados')
    arquivos = sorted(diretorio.glob('*.parquet'))
    
    # Agrupar indicadores por ODS
    ods_grupos = {}
    
    # Coletar todos os campos adicionais únicos
    campos_adicionais = set()
    
    for arquivo in arquivos:
        if arquivo.name.startswith('indicador'):
            try:
                # Extrair número do ODS do nome do arquivo
                ods = arquivo.name.split('.')[0].split('indicador')[1].split('.')[0]
                
                if ods not in ods_grupos:
                    ods_grupos[ods] = []
                
                info = analisar_arquivo(arquivo)
                if info:
                    # Coletar campos adicionais
                    for col in info['colunas']:
                        if col not in ['ID_INDICADOR', 'CODG_UND_MED', 'VLR_VAR', 
                                     'CODG_UND_FED', 'CODG_VAR', 'CODG_ANO']:
                            campos_adicionais.add(col)
                    
                    ods_grupos[ods].append({
                        'arquivo': arquivo.name,
                        'info': info
                    })
            except Exception as e:
                print(f"Erro ao processar {arquivo.name}: {e}")
    
    # Gerar markdown
    markdown = "# Dicionário de Dados\n\n"
    
    # Estrutura Básica
    markdown += "## Estrutura Básica\n\n"
    markdown += "Todos os arquivos parquet seguem uma estrutura básica comum com as seguintes colunas:\n\n"
    markdown += "| Coluna | Descrição | Tipo |\n"
    markdown += "|--------|-----------|------|\n"
    markdown += "| ID_INDICADOR | Identificador único do indicador | Categoria |\n"
    markdown += "| CODG_UND_MED | Código da unidade de medida | Categoria |\n"
    markdown += "| VLR_VAR | Valor da variável | Numérico |\n"
    markdown += "| CODG_UND_FED | Código da unidade federativa | Categoria |\n"
    markdown += "| CODG_VAR | Código da variável | Categoria |\n"
    markdown += "| CODG_ANO | Código do ano | Inteiro |\n\n"
    
    # Campos Adicionais
    markdown += "## Campos Adicionais\n\n"
    markdown += "Além da estrutura básica, os indicadores podem conter campos adicionais para desagregação dos dados:\n\n"
    markdown += "| Campo | Descrição | Tipo |\n"
    markdown += "|-------|-----------|------|\n"
    
    # Descrições dos campos adicionais
    descricoes = {
        'CODG_IDADE': 'Código da faixa etária',
        'CODG_SEXO': 'Código do sexo',
        'CODG_RACA': 'Código da raça/cor',
        'CODG_SIT_DOM': 'Código da situação do domicílio (urbano/rural)',
        'CODG_NIV_INSTR': 'Código do nível de instrução',
        'CODG_REND_MENSAL_DOM_PER_CAP': 'Código da renda mensal domiciliar per capita',
        'CODG_TIPO_DOENCA': 'Código do tipo de doença',
        'COD_GRU_IDADE_NIV_ENS': 'Código do grupo de idade por nível de ensino',
        'CODG_INF_ESC': 'Código da infraestrutura escolar',
        'CODG_ETAPA_ENS': 'Código da etapa de ensino',
        'CODG_SET_ATIV': 'Código do setor de atividade',
        'CODG_ECO_REL_AGUA': 'Código do ecossistema relacionado à água',
        'CODG_TIP_DIN_ECO_REL_AGUA': 'Código do tipo de dinâmica do ecossistema relacionado à água',
        'CODG_ATV_TRAB': 'Código da atividade de trabalho',
        'CODG_DEF': 'Código do tipo de deficiência'
    }
    
    # Ordenar campos adicionais
    campos_ordenados = sorted(list(campos_adicionais))
    
    for campo in campos_ordenados:
        descricao = descricoes.get(campo, 'Campo de desagregação específico do indicador')
        markdown += f"| {campo} | {descricao} | Categoria |\n"
    
    markdown += "\n"
    
    # Estatísticas dos Indicadores
    markdown += "## Estatísticas dos Indicadores\n\n"
    
    # Ordem dos ODSs
    ordem_ods = ['1', '3', '4', '5', '6', '7', '8', '9', '11', '13', '16']
    
    for ods in ordem_ods:
        if ods in ods_grupos:
            # Nome do ODS
            nome_ods = {
                '1': 'Erradicação da Pobreza',
                '3': 'Saúde e Bem-estar',
                '4': 'Educação de Qualidade',
                '5': 'Igualdade de Gênero',
                '6': 'Água Potável e Saneamento',
                '7': 'Energia Acessível e Limpa',
                '8': 'Trabalho Decente e Crescimento Econômico',
                '9': 'Indústria, Inovação e Infraestrutura',
                '11': 'Cidades e Comunidades Sustentáveis',
                '13': 'Ação Contra a Mudança Global do Clima',
                '16': 'Paz, Justiça e Instituições Eficazes'
            }.get(ods, f'ODS {ods}')
            
            markdown += f"### ODS {ods} - {nome_ods}\n"
            markdown += "| Indicador | Total de Registros | Desagregações | Nível de Desagregação |\n"
            markdown += "|-----------|-------------------|---------------|----------------------|\n"
            
            for arquivo_info in ods_grupos[ods]:
                info = arquivo_info['info']
                nome_indicador = arquivo_info['arquivo'].replace('indicador', '').replace('.parquet', '')
                
                # Identificar desagregações
                desagregacoes = []
                for col in info['colunas']:
                    if col not in ['ID_INDICADOR', 'CODG_UND_MED', 'VLR_VAR', 
                                 'CODG_UND_FED', 'CODG_VAR', 'CODG_ANO']:
                        desagregacoes.append(col)
                
                # Determinar nível de desagregação
                total_registros = info['total_registros']
                if total_registros <= 100:
                    nivel = 'Básico'
                elif total_registros <= 1000:
                    nivel = 'Médio'
                elif total_registros <= 5000:
                    nivel = 'Alto'
                else:
                    nivel = 'Muito Alto'
                
                markdown += f"| {nome_indicador} | {total_registros:,} | "
                markdown += f"{', '.join(desagregacoes) if desagregacoes else '-'} | {nivel} |\n"
            
            markdown += "\n"
    
    # Legenda
    markdown += "## Legenda do Nível de Desagregação\n\n"
    markdown += "- **Básico**: Apenas com as colunas padrão (até 100 registros)\n"
    markdown += "- **Médio**: Com uma desagregação adicional (100-1.000 registros)\n"
    markdown += "- **Alto**: Com duas desagregações adicionais (1.000-5.000 registros)\n"
    markdown += "- **Muito Alto**: Com três ou mais desagregações (mais de 5.000 registros)\n\n"
    
    # Observações
    markdown += "## Observações\n\n"
    markdown += "1. Os campos são armazenados em tipos de dados apropriados:\n"
    markdown += "   - Valores numéricos (VLR_VAR): float64\n"
    markdown += "   - Anos (CODG_ANO): Int64\n"
    markdown += "   - Códigos e identificadores: category\n"
    markdown += "2. A estrutura básica é comum a todos os indicadores\n"
    markdown += "3. As colunas adicionais variam de acordo com a especificidade de cada indicador\n"
    markdown += "4. O número de registros varia significativamente entre os indicadores\n"
    markdown += "5. A desagregação dos dados permite análises mais detalhadas por diferentes dimensões\n"
    
    # Atualizar README
    try:
        with open('README.md', 'r', encoding='utf-8') as f:
            conteudo = f.read()
        
        # Encontrar início e fim da seção de dicionário de dados
        inicio = conteudo.find('# Dicionário de Dados')
        fim = conteudo.find('\n\n', inicio) if inicio != -1 else -1
        
        if inicio != -1:
            # Substituir a seção existente pelo novo conteúdo
            novo_conteudo = conteudo[:inicio] + markdown
            if fim != -1:
                novo_conteudo += conteudo[fim:]
        else:
            # Adicionar a seção no final do arquivo
            novo_conteudo = conteudo.rstrip() + '\n\n' + markdown
        
        with open('README.md', 'w', encoding='utf-8') as f:
            f.write(novo_conteudo)
        print("README atualizado com sucesso!")
    except Exception as e:
        print(f"Erro ao atualizar README: {e}")

if __name__ == '__main__':
    main()