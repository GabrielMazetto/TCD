import pandas as pd
import pytest
from pathlib import Path
from typing import Tuple

# --- AJUSTE OS NOMES DOS ARQUIVOS AQUI SE NECESSÁRIO ---
NOME_ARQUIVO_XLSX = "default_of_credit_card.xlsx"
NOME_ARQUIVO_CSV = "cleaned_of_credit_card.csv"
# ----------------------------------------------------

@pytest.fixture(scope="session")
def datasets_para_teste() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fixture do Pytest para carregar os dois datasets de validação (XLSX e CSV).
    ... (o resto da docstring) ...
    """
    
    # --- CORREÇÃO APLICADA AQUI ---
    # 1. Encontra a raiz do projeto "Preparação_dos_Dados" (onde o pytest.ini está)
    raiz_projeto_preparacao = Path(__file__).parent.parent
    # 2. Sobe mais um nível para encontrar a raiz "TCD"
    raiz_TCD = raiz_projeto_preparacao.parent
    # ----------------------------------------------------

    # Define os caminhos a partir da raiz "TCD"
    path_xlsx = raiz_TCD / "Datasets" / NOME_ARQUIVO_XLSX
    path_csv = raiz_TCD / "Datasets" / NOME_ARQUIVO_CSV

    # Tenta carregar os arquivos
    try:
        # Para o .xlsx, pandas usará a engine 'openpyxl'
        # (adicionada ao requirements.txt)
        df_original_xlsx = pd.read_excel(path_xlsx)
        
        # O .csv é leitura direta
        df_cleaned_csv = pd.read_csv(path_csv)
    
    except FileNotFoundError as e:
        # Mensagem de erro melhorada para clareza
        pytest.fail(f"Erro ao carregar dataset de teste: {e}. "
                    f"Verifique se a pasta 'Datasets' existe em '{raiz_TCD}' "
                    f"e contém os arquivos '{NOME_ARQUIVO_XLSX}' e "
                    f"'{NOME_ARQUIVO_CSV}'.")
    except Exception as e:
        pytest.fail(f"Erro inesperado ao processar os datasets: {e}")

    # Retorna os dataframes prontos para os testes
    return df_original_xlsx, df_cleaned_csv