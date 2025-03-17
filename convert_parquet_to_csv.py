import os
import pandas as pd
from pathlib import Path

def converter_parquet_para_csv():
    # Diretório de entrada (parquet) e saída (csv)
    dir_entrada = Path('db/resultados')
    dir_saida = Path('db/resultados_csv')
    
    # Criar diretório de saída se não existir
    dir_saida.mkdir(parents=True, exist_ok=True)
    
    # Contador de arquivos processados
    total_arquivos = 0
    
    print(f"Iniciando conversão de arquivos parquet para CSV...")
    
    # Iterar sobre todos os arquivos parquet no diretório
    for arquivo_parquet in dir_entrada.glob('*.parquet'):
        try:
            # Ler arquivo parquet
            print(f"Lendo arquivo: {arquivo_parquet.name}")
            df = pd.read_parquet(arquivo_parquet)
            
            # Criar nome do arquivo CSV
            arquivo_csv = dir_saida / arquivo_parquet.name.replace('.parquet', '.csv')
            
            # Salvar como CSV
            print(f"Salvando como CSV: {arquivo_csv.name}")
            df.to_csv(arquivo_csv, index=False)
            
            total_arquivos += 1
            print(f"Arquivo convertido com sucesso: {arquivo_csv.name}")
            print("-" * 50)
            
        except Exception as e:
            print(f"Erro ao processar {arquivo_parquet.name}: {str(e)}")
    
    print(f"\nConversão finalizada!")
    print(f"Total de arquivos convertidos: {total_arquivos}")
    print(f"Os arquivos CSV foram salvos em: {dir_saida.absolute()}")

if __name__ == "__main__":
    converter_parquet_para_csv() 