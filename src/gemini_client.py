import google.generativeai as genai
import os
import logging
import time

# Configura o logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Cliente SÍNCRONO para interagir com a API do Google Gemini.
    Carrega a chave da API a partir de variáveis de ambiente.
    """
    def __init__(self, model_name="gemini-2.5-flash"):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("Variável de ambiente GEMINI_API_KEY não definida.")
            raise EnvironmentError("GEMINI_API_KEY não foi configurada.")
        
        genai.configure(api_key=self.api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"Cliente Gemini (Síncrono) inicializado com o modelo: {self.model_name}")

    def set_model(self, model_name):
        """Permite alterar o modelo Gemini em tempo de execução."""
        try:
            self.model_name = model_name
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"Modelo Gemini alterado para: {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Erro ao alterar o modelo Gemini: {e}")
            return False

    def _generate_with_retry(self, prompt_parts, max_retries=3):
        """
        Tenta gerar conteúdo com retentativa (versão SÍNCRONA).
        """
        delay = 1
        for attempt in range(max_retries):
            try:
                # Usa a chamada síncrona: generate_content()
                response = self.model.generate_content(prompt_parts)
                
                # Verifica se a resposta existe, tem texto, e não é SÓ espaço em branco
                if response and response.text and response.text.strip():
                    return response.text
                else:
                    logger.warning(f"Tentativa {attempt + 1}: Resposta inesperada ou vazia da API: {response}")
                    
            except Exception as e:
                logger.error(f"Tentativa {attempt + 1} falhou: {e}")
                if "429" in str(e): # Trata Throttling (Too Many Requests)
                    time.sleep(delay * (2 ** attempt))
                else:
                    time.sleep(delay) # Espera síncrona antes de tentar novamente
            
        logger.error(f"Falha ao gerar conteúdo após {max_retries} tentativas.")
        return None

    def generate_initial_plan(self, user_objective, df_metadata):
        """
        Etapa 2: Gera um plano de análise inicial.
        REGRA RÍGIDA: O passo 1 é instalação, os outros são APENAS análise.
        """
        prompt = f"""
        **Contexto:** Você é um assistente de análise de dados Sênior.
        
        **Objetivo do Usuário:**
        {user_objective}
        
        **Metadados do Dataset:**
        {df_metadata}
        
        **Instrução:**
        Gere um plano de análise passo-a-passo (lista numerada).
        
        **REGRAS OBRIGATÓRIAS DE ESTRUTURA (SIGA ESTRITAMENTE):**
        1. O **Passo 1** DEVE SER EXATAMENTE: "1. Instalação de Dependências e Configuração Inicial".
        2. Do **Passo 2** em diante, descreva apenas tarefas de análise (limpeza, plotagem, modelagem).
        3. **PROIBIDO** mencionar as palavras "instalar", "baixar" ou "pip" nos passos 2, 3, 4, etc. Assuma que o ambiente já está pronto.
        
        **Exemplo de Formato Correto:**
        1. Instalação de Dependências e Configuração Inicial.
        2. Tratamento de valores nulos nas colunas numéricas.
        3. Visualização da distribuição da coluna X.
        
        **Gere o Plano de Análise (lista):**
        """
        
        logger.info("Gerando plano de análise inicial (Síncrono)...")
        response_text = self._generate_with_retry([prompt])
        
        if response_text and response_text.strip():
            logger.info("Plano gerado com sucesso.")
            return response_text
        else:
            return "Erro: O LLM não conseguiu gerar um plano."

    def generate_code_from_plan(self, user_objective, df_metadata, plan_step, kb_functions_info):
        """
        Etapa 4: Gera código Python.
        REGRA RÍGIDA: Instalação APENAS se o passo atual for o número 1.
        """
        
        kb_info_str = "\n".join(
            [f"- Função: `{func['titulo']}` (Descrição: {func['descricao']})" for func in kb_functions_info]
        )
        
        prompt = f"""
        **Contexto:** Você é um desenvolvedor Python. Gere código para um passo de análise.
        
        **Passo Atual do Plano:** "{plan_step}"
        **Objetivo Geral:** {user_objective}
        **Metadados:** {df_metadata}
        **Funções KB:** {kb_info_str}
        
        ---------------------------------------------------------
        **REGRAS CRÍTICAS DE GERAÇÃO DE CÓDIGO (LEIA COM ATENÇÃO):**
        
        Analise o texto do "**Passo Atual do Plano**" acima.
        
        **CASO A: O passo começa com "1." ou contém "Instalação" / "Setup"**
           - Sua tarefa é PREPARAR O AMBIENTE.
           - Você DEVE usar `import subprocess` e `sys`.
           - Gere comandos para instalar TODAS as bibliotecas que você imagina que serão usadas no projeto todo (pandas, numpy, seaborn, matplotlib, scikit-learn, etc).
           - Exemplo: `subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "seaborn"])`
        
        **CASO B: O passo começa com "2.", "3.", etc. (Qualquer outro passo)**
           - Sua tarefa é APENAS ANÁLISE.
           - **ESTRITAMENTE PROIBIDO** usar `subprocess`, `pip install` ou tentar instalar nada.
           - APENAS faça os `import` necessários no topo (ex: `import pandas as pd`).
           - Se você acha que uma biblioteca pode não estar instalada, **NÃO INSTALE**. Apenas importe. Se der erro, um sistema externo corrigirá depois.
           - Foque na lógica de pandas/matplotlib e no uso das funções da KB.
        ---------------------------------------------------------
        
        **Requisitos:**
        - O código deve ser completo e executável.
        - Opere sobre o DataFrame `df`.
        - Se criar gráficos, salve em `fig`.
        
        **Gere APENAS o código Python:**
        ```python
        """
        
        logger.info(f"Gerando código para o passo: {plan_step}")
        response_text = self._generate_with_retry([prompt])
        
        if response_text:
            if "```python" in response_text:
                response_text = response_text.split("```python")[1].split("```")[0].strip()
            return response_text
        else:
            return "# Erro: Não foi possível gerar o código."

    def generate_code_fix(self, broken_code, error_message, plan_step, user_objective, df_metadata, kb_functions_info):
            """
            Conserta código que falhou.
            AQUI É O ÚNICO LUGAR (além do passo 1) onde instalação é permitida.
            """
            
            kb_info_str = "\n".join(
                [f"- Função: `{func['titulo']}` (Descrição: {func['descricao']})" for func in kb_functions_info]
            )
            
            prompt = f"""
            **Tarefa:** Corrigir código Python que falhou.
            
            **Erro Encontrado:** {error_message}
            
            **Código Quebrado:**
            ```python
            {broken_code}
            ```
            
            **Contexto:** Passo "{plan_step}" do objetivo "{user_objective}".
            **Funções KB:** {kb_info_str}
            
            **INSTRUÇÃO DE CORREÇÃO:**
            1. Analise o erro.
            2. Se o erro for `ModuleNotFoundError` ou "No module named...", **VOCÊ ESTÁ AUTORIZADO** a adicionar um bloco de instalação (`subprocess.check_call...`) para essa biblioteca específica antes dos imports.
            3. Se for erro de lógica ou sintaxe, corrija o código mantendo a lógica original.
            
            **Gere APENAS o código corrigido:**
            ```python
            """
            
            logger.info(f"Tentando corrigir código para o passo: {plan_step}...")
            response_text = self._generate_with_retry([prompt])
            
            if response_text:
                if "```python" in response_text:
                    response_text = response_text.split("```python")[1].split("```")[0].strip()
                return response_text
            else:
                return f"# Erro: O LLM não conseguiu corrigir o código.\n{broken_code}"