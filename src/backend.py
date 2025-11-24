import pandas as pd
import json
import logging
import io
import ast
import sys
import subprocess
import importlib.util
from contextlib import redirect_stdout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackendOrchestrator:
    def __init__(self, kb_path="data/kb.jsonl"):
        self.kb_path = kb_path
        self.knowledge_base = self.load_knowledge_base()

    def load_knowledge_base(self):
        kb = []
        try:
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try: kb.append(json.loads(line.strip()))
                    except: pass
            return kb
        except: return []

    def get_kb_metadata(self):
        return [{"titulo": f.get("titulo"), "descricao": f.get("descricao")} for f in self.knowledge_base]
        
    def get_specific_functions_code(self, function_titles):
        selected_code = []
        titles_lower = [t.lower().strip() for t in function_titles]
        for func in self.knowledge_base:
            if func.get("titulo", "").lower().strip() in titles_lower:
                selected_code.append(f"# KB: {func.get('titulo')}\n{func.get('codigo_funcao')}\n")
        return "\n".join(selected_code)

    def generate_metadata(self, df):
        try:
            buffer = io.StringIO()
            df.info(buf=buffer)
            return f"Shape: {df.shape}\nCols: {list(df.columns)}\nInfo: {buffer.getvalue()}\nHead:\n{df.head(3).to_string()}"
        except: return str(df.shape)

    def check_missing_dependencies(self, code_str):
        # Tenta parsear. Se der SyntaxError, loga e retorna vazio (deixa estourar na execução)
        try: tree = ast.parse(code_str)
        except SyntaxError as e:
            logger.warning(f"Erro de sintaxe ao checar deps: {e}")
            return []
            
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names: imports.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module: imports.add(node.module.split('.')[0])
        
        std_libs = {'json','os','sys','io','re','logging','subprocess','ast','math','random','typing','warnings','time','collections','copy','pathlib'}
        sys_libs = set(sys.builtin_module_names)
        
        missing = []
        for lib in imports:
            if lib not in sys_libs and lib not in std_libs:
                # Verifica se a spec existe
                if importlib.util.find_spec(lib) is None: 
                    missing.append(lib)
        return list(set(missing))

    def install_libraries(self, libraries):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + libraries)
            return True, "Instalado com sucesso."
        except Exception as e: return False, str(e)

    def execute_code(self, code_str, df):
        local_scope = {"df": df.copy(), "fig": None}
        captured_displays = []

        def custom_display(obj):
            captured_displays.append(obj)

        exec_globals = {
            "pd": pd, 
            "__builtins__": __builtins__,
            "display": custom_display
        }
        
        try:
            import numpy as np; exec_globals["np"] = np
            import matplotlib.pyplot as plt; exec_globals["plt"] = plt
            import seaborn as sns; exec_globals["sns"] = sns
            import plotly.express as px; exec_globals["px"] = px
            import plotly.graph_objects as go; exec_globals["go"] = go
        except: pass
        
        f_stdout = io.StringIO()
        
        try:
            with redirect_stdout(f_stdout):
                exec(code_str, exec_globals, local_scope)
            
            captured_output = f_stdout.getvalue()
            res_df = local_scope.get('df')
            if res_df is None: res_df = df.copy()
            
            return res_df, local_scope.get('fig'), None, captured_output, captured_displays
            
        except ModuleNotFoundError as e:
            # --- CORREÇÃO CRÍTICA ---
            # Se falhar aqui por falta de lib, retornamos um erro especial
            # Formato: "No module named 'networkx'" -> extrai 'networkx'
            try:
                missing_lib = str(e).split("'")[-2]
                return None, None, f"MissingDependency:{missing_lib}", f_stdout.getvalue(), []
            except:
                return None, None, str(e), f_stdout.getvalue(), []
                
        except Exception as e:
            return None, None, str(e), f_stdout.getvalue(), []