import pandas as pd
import pytest
from modules.limpeza_dados.clean_functions import remove_rows_all_zeros_except

# --- Testes de Unidade (Lógica Pura) ---
# (Estes testes permanecem idênticos)

def test_remove_all_zero_rows_main_dataset():
    data = { 'ID': ['a', 'b', 'c'], 'feature1': [10, 0, 30], 'feature2': [20, 0, 40] }
    df = pd.DataFrame(data)
    df_cleaned = remove_rows_all_zeros_except(df, cols_to_ignore=['ID'])
    assert df_cleaned.shape[0] == 2
    assert 'b' not in df_cleaned['ID'].values

def test_no_rows_to_remove():
    data = {'col1': [1, 2, 3], 'col2': [0, 5, 0], 'col3': [7, 0, 9]}
    df = pd.DataFrame(data)
    df_original_shape = df.shape
    df_cleaned = remove_rows_all_zeros_except(df)
    assert df_cleaned.shape == df_original_shape

def test_inplace_modification():
    data = { 'ID': ['a', 'b', 'c'], 'feature1': [10, 0, 30], 'feature2': [20, 0, 40] }
    df = pd.DataFrame(data)
    result = remove_rows_all_zeros_except(df, cols_to_ignore=['ID'], inplace=True)
    assert result is None
    assert df.shape[0] == 2

# --- Teste de Integração (Compatibilidade com Datasets Reais) ---

def test_compatibilidade_datasets_reais(datasets_para_teste):
    """
    Testa se a função é executada sem erros nos dois datasets reais
    de validação (XLSX e CSV).
    """
    # Nomes de variáveis atualizados para maior clareza
    df_original_xlsx, df_cleaned_csv = datasets_para_teste

    # Testa no primeiro dataset (Original XLSX)
    try:
        df_original_copy = df_original_xlsx.copy()
        
        # Assumindo que 'ID' existe em ambos os datasets
        df_cleaned_xls = remove_rows_all_zeros_except(df_original_copy, cols_to_ignore=['ID'])
        
        assert isinstance(df_cleaned_xls, pd.DataFrame)
        assert df_cleaned_xls.shape[0] <= df_original_copy.shape[0]

    except Exception as e:
        pytest.fail(f"Função falhou ao rodar no dataset XLSX: {e}")

    # Testa no segundo dataset (Cleaned CSV)
    try:
        df_cleaned_copy = df_cleaned_csv.copy()
        df_cleaned_csv_result = remove_rows_all_zeros_except(df_cleaned_copy, cols_to_ignore=['ID'])
        
        assert isinstance(df_cleaned_csv_result, pd.DataFrame)
        assert df_cleaned_csv_result.shape[0] <= df_cleaned_copy.shape[0]

    except Exception as e:
        pytest.fail(f"Função falhou ao rodar no dataset CSV: {e}")