import pandas as pd
import json
import logging
import io

# Configura o logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackendOrchestrator:
    """
    Gerencia a lógica de negócios local, o estado dos dados
    e a execução de código.
    """
    def __init__(self, kb_path="data/kb.jsonl"):
        self.kb_path = kb_path
        self.knowledge_base = self.load_knowledge_base()
        logger.info(f"{len(self.knowledge_base)} funções carregadas da KB.")

    def load_knowledge_base(self):
        """Carrega a Base de Conhecimento (KB) a partir do arquivo JSONL."""
        kb = []
        try:
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        kb.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        logger.warning(f"Ignorando linha mal formatada no JSONL: {line}")
            return kb
        except FileNotFoundError:
            logger.error(f"Arquivo da KB não encontrado em: {self.kb_path}")
            return []
        except Exception as e:
            logger.error(f"Erro ao carregar a KB: {e}")
            return []

    def get_kb_function_info(self):
        """
        Retorna uma lista de dicionários com 'titulo' e 'descricao'
        para enviar ao LLM (Etapa 3 / Etapa 4).
        """
        return [
            {"titulo": func.get("titulo"), "descricao": func.get("descricao")}
            for func in self.knowledge_base
        ]
        
    def get_kb_function_by_title(self, title):
        """Retorna o dicionário completo da função pelo título."""
        for func in self.knowledge_base:
            if func.get("titulo") == title:
                return func
        return None

    def generate_metadata(self, df):
        """
        Etapa 1: Gera metadados descritivos e estatísticos do DataFrame.
        NÃO envia dados brutos.
        """
        try:
            buffer = io.StringIO()
            df.info(buf=buffer)
            info_str = buffer.getvalue()
            
            numeric_cols = df.select_dtypes(include=['number']).columns
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns
            
            metadata = {
                "info": info_str,
                "shape": df.shape,
                "numeric_columns": list(numeric_cols),
                "categorical_columns": list(categorical_cols),
                "missing_values_summary": self.get_missing_values_summary(df).to_dict()
            }
            
            # Converte para uma string formatada para o prompt
            metadata_str = f"""
            Formato (Linhas, Colunas): {metadata['shape']}
            Colunas Numéricas: {metadata['numeric_columns']}
            Colunas Categóricas: {metadata['categorical_columns']}
            
            Informações Detalhadas (Tipos e Nulos):
            {metadata['info']}
            
            Resumo de Valores Ausentes (se houver):
            {metadata['missing_values_summary']}
            """
            
            logger.info("Metadados gerados com sucesso.")
            return metadata_str
            
        except Exception as e:
            logger.error(f"Erro ao gerar metadados: {e}")
            return f"Erro ao gerar metadados: {e}"

    def get_missing_values_summary(self, df):
        """Função auxiliar para gerar resumo de valores ausentes."""
        missing_count = df.isnull().sum()
        missing_percentage = (missing_count / len(df)) * 100
        summary_df = pd.DataFrame({
            'Missing_Count': missing_count,
            'Missing_Percentage': missing_percentage
        })
        summary_df = summary_df[summary_df['Missing_Count'] > 0]
        return summary_df.sort_values(by='Missing_Percentage', ascending=False)

    def execute_code(self, code_str, df):
        """
        Etapa 4: Executa o código gerado pelo LLM de forma "segura".
        
        ATENÇÃO: `exec` é inerentemente inseguro. Em produção,
        isso DEVE ser substituído por um sandbox (ex: Docker, gVisor, Pyodide).
        Para este projeto de TCD, com aprovação explícita do usuário,
        é uma solução paliativa.
        
        O código pode modificar 'df' ou retornar um novo df, ou uma figura.
        """
        
        # Cria um "ambiente" de execução com o dataframe 'df'
        local_scope = {"df": df.copy()} # Usa uma cópia para reversibilidade
        global_scope = {}
        
        # Variáveis para capturar os resultados
        result_df = None
        result_fig = None
        error_message = None
        
        logger.warning(f"Executando código (ATENÇÃO: 'exec' é inseguro): \n{code_str}")
        
        try:
            # Compila e executa o código
            # O código deve atribuir seu resultado a 'result_df' ou 'result_fig'
            # (Vamos adaptar o prompt para sugerir isso)
            
            # Tentativa de tornar a captura de resultado mais robusta:
            # O código gerado pode:
            # 1. Modificar 'df' (capturamos em local_scope['df'])
            # 2. Retornar uma figura (o prompt pede para atribuir a 'fig')
            # 3. Retornar um novo df (o prompt pede para atribuir a 'df_limpo' ou similar)
            
            # Vamos padronizar: o código gerado deve reatribuir 'df' ou 'fig'
            exec_globals = {
                "pd": pd,
                "__builtins__": __builtins__
            }
            exec_locals = {"df": df.copy()} # Passa uma cópia
            
            # Executa o código
            exec(code_str, exec_globals, exec_locals)
            
            # Captura os resultados do escopo local
            result_df = exec_locals.get('df')
            result_fig = exec_locals.get('fig') # O prompt pede para salvar a figura em 'fig'
            
            if result_df is None:
                result_df = df # Se o df não foi modificado, retorna o original
                
            if result_fig:
                logger.info("Execução gerou uma figura.")
            else:
                logger.info("Execução alterou o DataFrame.")
                
        except Exception as e:
            logger.error(f"Erro durante a execução do código: {e}")
            error_message = str(e)

        return result_df, result_fig, error_message
