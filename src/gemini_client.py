import google.generativeai as genai
import os
import logging
import json
import re  # Importante para a correção

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, model_name="gemini-2.5-flash-lite"):
        self.api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY")
        genai.configure(api_key=self.api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)

    def set_model(self, model_name):
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)

    def _generate_text(self, prompt):
        try:
            response = self.model.generate_content(prompt)
            return response.text if response else ""
        except Exception as e:
            return f"# Erro API: {e}"

    def _extract_code(self, text):
        """
        Extrai código Python de blocos markdown de forma segura usando Regex.
        Isso corrige o erro de 'invalid syntax' causado por restos de formatação.
        """
        # Tenta encontrar bloco ```python ... ```
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Tenta encontrar bloco genérico ``` ... ```
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
            
        # Se não tiver bloco, retorna o texto inteiro (assumindo que é só código)
        return text.strip()

    def generate_initial_plan(self, user_objective, df_metadata):
        prompt = f"""
        Atue como Arquiteto de Dados.
        Objetivo: {user_objective}
        Metadados: {df_metadata}
        Crie um plano de EDA (Análise Exploratória) em Markdown.
        Sem introduções. Apenas lista numerada.
        """
        return self._generate_text(prompt)

    def select_relevant_functions(self, step_description, kb_metadata_list):
        kb_text = "\n".join([f"- {item['titulo']}: {item['descricao']}" for item in kb_metadata_list])
        prompt = f"""
        Passo: "{step_description}"
        KB: {kb_text}
        Retorne JSON: {{ "funcoes_escolhidas": ["Titulo1"] }}
        """
        res = self._generate_text(prompt)
        try:
            # Limpeza específica para JSON
            clean = res.replace("```json", "").replace("```", "").strip()
            return json.loads(clean).get("funcoes_escolhidas", [])
        except:
            return []

    def generate_final_code(self, step_description, user_objective, df_metadata, relevant_functions_code):
        prompt = f"""
        Expert Python Data Science.
        Objetivo: {user_objective}
        Passo: {step_description}
        Metadados: {df_metadata}
        KB Contexto: {relevant_functions_code}
        
        **REGRAS:**
        1. `df` JÁ EXISTE e já está carregado. NÃO recrie. Use a variável `df` que já existe.
        2. USE `display(df)` para mostrar tabelas (NÃO use print).
        3. NÃO crie dados manuais (`data = {{...}}`).
        
        Gere apenas Python.
        """
        res = self._generate_text(prompt)
        return self._extract_code(res) # Usa o extrator seguro

    def validate_code_safety(self, generated_code, step_description):
        prompt = f"""
        Judge Python. Passo: "{step_description}"
        Código:
        ```python
        {generated_code}
        ```
        1. Remova `data = {{...}}` ou `pd.DataFrame({{...}})` (dados mock).
        2. Troque `print(df)` por `display(df)`.
        3. Verifique sintaxe.
        
        Retorne Python corrigido.
        """
        res = self._generate_text(prompt)
        return self._extract_code(res) # Usa o extrator seguro

    def generate_code_fix(self, broken_code, error_msg, step):
        prompt = f"""
        Corrija o código.
        Passo: {step}
        Erro: {error_msg}
        Código:
        {broken_code}
        Retorne Python corrigido.
        """
        res = self._generate_text(prompt)
        return self._extract_code(res) # Usa o extrator seguro