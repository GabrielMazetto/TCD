import pandas as pd
from typing import List, Optional

def remove_rows_all_zeros_except(
    df: pd.DataFrame,
    cols_to_ignore: Optional[List[str]] = None,
    inplace: bool = False
) -> Optional[pd.DataFrame]:
    """
    Remove linhas de um DataFrame onde todas as colunas, exceto as especificadas, são zero.

    Esta função identifica e remove linhas que são preenchidas majoritariamente por zeros,
    o que geralmente indica dados inválidos ou de preenchimento. É útil para limpar
    datasets após importações ou junções que podem gerar registros vazios.

    Args:
        df (pd.DataFrame): O DataFrame de entrada a ser processado.
        cols_to_ignore (List[str], optional): Lista de nomes de colunas a serem
            ignoradas na verificação de zeros. Por padrão, nenhuma coluna é ignorada.
        inplace (bool, optional): Se True, a modificação é feita no DataFrame
            original e a função retorna None. Se False (padrão), retorna um novo
            DataFrame com as linhas removidas.

    Returns:
        pd.DataFrame or None: Um novo DataFrame com as linhas removidas ou None se
            inplace=True.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("O argumento 'df' deve ser um DataFrame do pandas.")

    df_copy = df if inplace else df.copy()

    cols_to_check = df_copy.columns
    if cols_to_ignore:
        # Valida se as colunas a ignorar existem
        non_existent_cols = [col for col in cols_to_ignore if col not in df_copy.columns]
        if non_existent_cols:
            raise ValueError(f"As seguintes colunas não existem no DataFrame: {non_existent_cols}")
        cols_to_check = df_copy.columns.drop(cols_to_ignore)

    # Máscara para identificar linhas onde todas as colunas a verificar são zero
    zero_mask = (df_copy[cols_to_check] == 0).all(axis=1)

    rows_to_drop = df_copy[zero_mask].index
    df_copy.drop(rows_to_drop, inplace=True)

    if inplace:
        return None
    else:
        return df_copy