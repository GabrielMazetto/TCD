import streamlit as st
import pandas as pd
import os
import re 
import time # Importado para os timers
from dotenv import load_dotenv
from src.backend import BackendOrchestrator
from src.gemini_client import GeminiClient
import logging

# Configura o logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente (GEMINI_API_KEY) do arquivo .env
load_dotenv()

# --- Configuração da Página ---
st.set_page_config(
    page_title="Assistente de Análise de Dados (TCD)",
    page_icon="🤖",
    layout="wide"
)

# --- INICIALIZAÇÃO DO ESTADO ---

def initialize_session():
    """Inicializa o estado da sessão focado em células."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = os.urandom(24).hex()
        logger.info(f"Nova sessão iniciada: {st.session_state.session_id}")
    
    if "backend" not in st.session_state:
        st.session_state.backend = BackendOrchestrator(kb_path="data/kb.jsonl")
    
    if "gemini_client" not in st.session_state:
        try:
            st.session_state.gemini_client = GeminiClient()
        except EnvironmentError as e:
            st.error(f"Erro de configuração: {e}. Verifique seu arquivo .env e a variável GEMINI_API_KEY.")
            st.stop()
            
    # Estado dos dados
    if "df" not in st.session_state:
        st.session_state.df = None
    
    if "df_metadata" not in st.session_state:
        st.session_state.df_metadata = None
        
    if "df_history" not in st.session_state:
        st.session_state.df_history = [] 

    # --- ALTERAÇÃO 1 (Requisito 1: Timer do Plano) ---
    if "plan_generation_time" not in st.session_state:
        st.session_state.plan_generation_time = None

    if "full_plan_editor_key" not in st.session_state:
        st.session_state.full_plan_editor_key = "" 

    if "cells" not in st.session_state:
        st.session_state.cells = [] 
        
    if "user_objective_key" not in st.session_state:
        st.session_state.user_objective_key = ""

# --- FUNÇÕES DE CALLBACK ---

def handle_file_upload():
    """Callback para quando um novo arquivo é carregado."""
    uploaded_file = st.session_state.get("file_uploader_key")
    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(('.xls', '.xlsx')):
                df = pd.read_excel(uploaded_file)
            else:
                st.error("Formato de arquivo não suportado. Use CSV ou Excel.")
                return

            st.session_state.df = df
            st.session_state.df_history = [df.copy()] 
            st.session_state.df_metadata = st.session_state.backend.generate_metadata(df)
            
            st.session_state.cells = [] 
            st.session_state.user_objective_key = ""
            st.session_state.full_plan_editor_key = ""
            st.session_state.plan_generation_time = None # Reseta o timer
            
            logger.info(f"Arquivo '{uploaded_file.name}' carregado. Shape: {df.shape}")
            
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            logger.error(f"Erro ao ler o arquivo: {e}")
            # Reseta tudo em caso de falha
            st.session_state.df = None
            st.session_state.df_metadata = None
            st.session_state.df_history = []
            st.session_state.cells = []
            st.session_state.full_plan_editor_key = ""
            st.session_state.plan_generation_time = None

def callback_generate_plan():
    """
    Etapa 2: Gera o plano, o armazena no editor de texto completo.
    """
    objective = st.session_state.get("user_objective_key", "")
    metadata = st.session_state.get("df_metadata", "")
    
    if not objective:
        st.warning("Por favor, descreva o objetivo da sua análise.")
        return
    if not metadata:
        st.error("Nenhum metadado de DataFrame encontrado. Faça o upload de um arquivo primeiro.")
        return

    client = st.session_state.gemini_client
    
    with st.spinner("O LLM está gerando o plano de análise... 🤖"):
        # --- ALTERAÇÃO 2 (Requisito 1: Timer do Plano) ---
        start_time = time.time() # Inicia o timer
        try:
            plan = client.generate_initial_plan(objective, metadata)
            
            # --- ALTERAÇÃO 3 (Requisito 1: Timer do Plano) ---
            end_time = time.time()
            st.session_state.plan_generation_time = end_time - start_time # Salva o tempo
            
            if "Erro:" in plan:
                st.error(plan)
                st.session_state.full_plan_editor_key = ""
                st.session_state.cells = []
                return

            st.session_state.full_plan_editor_key = plan
            st.session_state.cells = []
            
            logger.info(f"Plano de análise inicial gerado para edição em {st.session_state.plan_generation_time:.2f}s.")
        except Exception as e:
            st.error(f"Erro ao chamar a API do Gemini: {e}")
            logger.error(f"Erro na API Gemini (callback_generate_plan): {e}")

def callback_split_plan_into_cells():
    """
    Callback para dividir o plano (editável) em células.
    """
    editable_plan = st.session_state.get("full_plan_editor_key", "")

    if not editable_plan.strip():
        st.warning("O plano de análise está vazio. Por favor, gere um ou edite o texto.")
        return

    cleaned_plan = re.sub(r'^\s*(Plano de Análise \(lista\):|Exemplo de Resposta:|Plano de Análise:)\s*', '', editable_plan, flags=re.IGNORECASE | re.MULTILINE).strip()

    if not cleaned_plan:
        st.warning("Após a limpeza, o plano ficou vazio. Verifique o conteúdo.")
        return

    plan_steps_raw = re.split(r'(?=\d+\.\s)', cleaned_plan.strip())
    
    if not plan_steps_raw:
        st.warning("Plano está vazio.")
        return

    plan_steps_clean = []
    for step in plan_steps_raw:
        step_stripped = step.strip()
        if not step_stripped:
            continue
            
        if re.match(r'^\d+\.\s', step_stripped):
            plan_steps_clean.append(step_stripped)
        else:
            logger.info(f"Descartando parte introdutória do plano: '{step_stripped}'")
    
    if not plan_steps_clean:
        st.warning("Não foi possível encontrar nenhum passo numerado (ex: '1. ...') no plano. Verifique a formatação.")
        st.session_state.cells = []
        return

    st.session_state.cells = [] 
    for i, step_text in enumerate(plan_steps_clean):
        # --- ALTERAÇÃO 4 (Requisitos 2 & 3: Estado da Célula) ---
        # Adiciona os novos campos ao dicionário da célula
        st.session_state.cells.append({
            "id": i,
            "plan_step": step_text,
            "code": "", 
            "output": None,
            "error": None,
            "gen_time": None,         # Para o timer de geração de código
            "exec_time": None,        # Para o timer de execução
            "execution_attempts": 0   # Para o contador de correções
        })
    logger.info(f"{len(st.session_state.cells)} células criadas a partir do plano editado.")

def callback_generate_code_for_cell(cell_index):
    """
    Etapa 4: Gera o código para UMA célula específica.
    """
    objective = st.session_state.get("user_objective_key", "")
    metadata = st.session_state.get("df_metadata", "")
    
    try:
        current_plan_step = st.session_state.cells[cell_index]["plan_step"] 
    except Exception as e:
        st.error(f"Erro ao localizar a célula {cell_index}: {e}")
        return

    kb_info = st.session_state.backend.get_kb_function_info()
    client = st.session_state.gemini_client
    
    with st.spinner(f"O LLM está gerando o código para a Célula {cell_index + 1}... 💻"):
        # --- ALTERAÇÃO 5 (Requisito 2: Timer de Geração da Célula) ---
        start_time = time.time()
        try:
            code = client.generate_code_from_plan(
                objective,
                metadata,
                current_plan_step,
                kb_info
            )
            
            # --- ALTERAÇÃO 6 (Requisito 2: Timer de Geração da Célula) ---
            end_time = time.time()
            gen_duration = end_time - start_time
            
            st.session_state.cells[cell_index]["code"] = code
            st.session_state.cells[cell_index]["error"] = None
            st.session_state.cells[cell_index]["gen_time"] = gen_duration
            
            # --- ALTERAÇÃO 7 (Requisito 3: Reseta Contadores) ---
            # Se geramos um novo código, resetamos os contadores de execução
            st.session_state.cells[cell_index]["execution_attempts"] = 0
            st.session_state.cells[cell_index]["exec_time"] = None
            
            logger.info(f"Código gerado para a Célula {cell_index + 1} em {gen_duration:.2f}s.")
        except Exception as e:
            st.error(f"Erro ao chamar a API do Gemini: {e}")
            logger.error(f"Erro na API Gemini (callback_generate_code_for_step): {e}")

def callback_execute_code_for_cell(cell_index):
    """
    Etapa 4 (Execução): Executa o código de UMA célula e implementa o loop de correção.
    """
    cell = st.session_state.cells[cell_index]
    code = cell.get("code", "")
    
    current_df = st.session_state.df_history[-1].copy() 
    
    if not code:
        st.warning("Nenhum código gerado para executar.")
        return
        
    backend = st.session_state.backend
    
    with st.spinner(f"Executando Célula {cell_index + 1} (Tentativa {cell['execution_attempts'] + 1})... ⚙️"):
        # --- ALTERAÇÃO 8 (Requisitos 2 & 3: Timer de Execução e Contador) ---
        start_time = time.time()
        st.session_state.cells[cell_index]["execution_attempts"] += 1 # Incrementa a tentativa
        
        try:
            new_df, new_fig, error_msg = backend.execute_code(code, current_df)
            
            end_time = time.time()
            exec_duration = end_time - start_time
            st.session_state.cells[cell_index]["exec_time"] = exec_duration # Salva o tempo de execução
            
            if error_msg:
                # INÍCIO DA LÓGICA DE CORREÇÃO (POR CÉLULA)
                cell["error"] = error_msg 
                cell["output"] = None 
                logger.error(f"Erro de execução na Célula {cell_index + 1} (Tentativa {cell['execution_attempts']}): {error_msg}")
                
                st.warning(f"Ocorreu um erro na Célula {cell_index + 1}: '{error_msg}'. O LLM tentará gerar uma correção...")
                
                client = st.session_state.gemini_client
                objective = st.session_state.get("user_objective_key", "")
                metadata = st.session_state.get("df_metadata", "")
                kb_info = st.session_state.backend.get_kb_function_info()
                
                current_plan_step = cell["plan_step"]

                code_fix = client.generate_code_fix(
                    broken_code=code,
                    error_message=error_msg,
                    plan_step=current_plan_step,
                    user_objective=objective,
                    df_metadata=metadata,
                    kb_functions_info=kb_info
                )
                
                st.session_state.cells[cell_index]["code"] = code_fix
                
                st.rerun() 
                # FIM DA LÓGICA DE CORREÇÃO

            else:
                # SUCESSO: O código foi executado sem erros
                st.session_state.cells[cell_index]["error"] = None
                
                if new_fig:
                    st.session_state.cells[cell_index]["output"] = new_fig
                else:
                    st.session_state.cells[cell_index]["output"] = new_df 
                
                st.session_state.df = new_df
                st.session_state.df_history.append(new_df.copy())
                
                logger.info(f"Célula {cell_index + 1} executada com sucesso em {exec_duration:.2f}s (Tentativa {cell['execution_attempts']}).")
                st.success(f"Célula {cell_index + 1} concluída com sucesso!")
                
                st.rerun() 
                
        except Exception as e:
            st.session_state.cells[cell_index]["error"] = f"Erro crítico no backend: {e}"
            logger.critical(f"Erro crítico no backend.execute_code: {e}")
            st.rerun()

def callback_revert_last_step():
    """
    Reverte o estado do DataFrame (desfaz a última execução de célula bem-sucedida).
    """
    if len(st.session_state.df_history) > 1:
        st.session_state.df_history.pop() 
        st.session_state.df = st.session_state.df_history[-1] 
        
        for cell in st.session_state.cells:
            cell['output'] = None
            cell['error'] = None
            # Também resetamos os timers e contadores ao reverter
            cell['gen_time'] = None
            cell['exec_time'] = None
            cell['execution_attempts'] = 0
        
        logger.info(f"Estado do DataFrame revertido. Histórico: {len(st.session_state.df_history)} versões.")
        st.toast("Última alteração desfeita.")
        st.rerun()
    else:
        st.warning("Não há ações para reverter.")

def callback_model_selection():
    """Altera o modelo Gemini usado."""
    selected_model = st.session_state.get("model_selector_key")
    if selected_model:
        client = st.session_state.gemini_client
        success = client.set_model(selected_model)
        if success:
            st.toast(f"Modelo alterado para: {selected_model}")
        else:
            st.error("Não foi possível alterar o modelo.")
            
# --- Inicializa a sessão ---
initialize_session()

# --- Layout da UI (Frontend) ---

st.title("🤖 Assistente de Análise de Dados com LLM (TCD)")
st.caption(f"Executando na Sessão ID: `{st.session_state.session_id}` | Privacidade 100% Local")

# --- Coluna 1: Configuração e Upload (Barra Lateral) ---
with st.sidebar:
    st.header("1. Configuração", anchor=False)
    
    uploaded_file = st.file_uploader(
        "Faça o upload do seu Dataset (CSV ou Excel)",
        type=["csv", "xls", "xlsx"],
        key="file_uploader_key",
        on_change=handle_file_upload,
        help="Seus dados permanecem 100% locais e nunca são enviados."
    )
    
    st.selectbox(
        "Selecione o Modelo Gemini:",
        ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"),
        key="model_selector_key",
        on_change=callback_model_selection
    )

    st.button(
        "Desfazer Última Execução ⏪",
        on_click=callback_revert_last_step,
        disabled=len(st.session_state.df_history) <= 1
    )
    
    st.divider()
    
    st.header("2. Objetivo", anchor=False)
    user_objective = st.text_area(
        "Qual é o objetivo da sua análise?",
        key="user_objective_key",
        height=100,
        placeholder="Ex: 'Quero entender os fatores que levaram à sobrevivência no Titanic e criar um modelo preditivo.'"
    )
    
    st.button(
        "Gerar Plano de Análise 🤖",
        on_click=callback_generate_plan,
        disabled=(st.session_state.df is None),
        use_container_width=True,
        type="primary"
    )
    
    st.divider()
    
    if st.session_state.df is not None:
        st.header("DataFrame Atual", anchor=False)
        st.caption(f"Versão: {len(st.session_state.df_history) - 1} | Shape: {st.session_state.df.shape}")
        st.dataframe(st.session_state.df, height=200)
        
        with st.expander("Ver Metadados Atuais"):
            st.text(st.session_state.backend.generate_metadata(st.session_state.df))


# --- Layout Principal (Área de Células) ---

if st.session_state.df is None:
    st.info("Por favor, faça o upload de um dataset na barra lateral para começar.")
else:
    st.header("3. Plano de Análise Completo", anchor=False)
    st.caption("Revise e edite o plano gerado pelo LLM. Após a edição, clique em 'Dividir em Células' para prosseguir.")
    
    # --- ALTERAÇÃO 9 (Requisito 1: Timer do Plano) ---
    if st.session_state.plan_generation_time:
        st.caption(f"Plano gerado em {st.session_state.plan_generation_time:.2f} segundos.")
    
    st.text_area(
        "Plano Completo:",
        key="full_plan_editor_key", 
        height=300
    )
    
    st.button(
        "Dividir Plano em Células 👇",
        on_click=callback_split_plan_into_cells,
        disabled=(not st.session_state.full_plan_editor_key.strip()), 
        use_container_width=True,
        type="secondary"
    )
    
    st.divider()

    if not st.session_state.cells:
        st.info("Clique em 'Dividir Plano em Células' acima para iniciar a execução interativa.")
    else:
        st.header("4. Execução do Plano (Células Interativas)", anchor=False)
        st.caption("Gere e execute o código para cada etapa do plano. O DataFrame é passado de uma célula para a próxima.")
        
        for index, cell in enumerate(st.session_state.cells):
            st.subheader(f"Célula {index + 1}:", anchor=False)
            
            edited_plan_step = st.text_area(
                f"Detalhes do Plano para Célula {index + 1}:",
                value=cell['plan_step'], 
                key=f"cell_plan_step_editor_{cell['id']}", 
                height=100
            )
            
            if edited_plan_step != cell['plan_step']:
                st.session_state.cells[index]['plan_step'] = edited_plan_step
                st.session_state.cells[index]['code'] = ""
                st.session_state.cells[index]['output'] = None
                st.session_state.cells[index]['error'] = None
                # --- ALTERAÇÃO 10 (Requisitos 2 & 3: Resetar Métricas) ---
                st.session_state.cells[index]['gen_time'] = None
                st.session_state.cells[index]['exec_time'] = None
                st.session_state.cells[index]['execution_attempts'] = 0
                st.rerun() 
            
            col_gen, col_exec = st.columns(2)
            with col_gen:
                st.button(
                    "Gerar Código 💻",
                    key=f"gen_btn_{cell['id']}", 
                    on_click=callback_generate_code_for_cell,
                    args=(index,), 
                    use_container_width=True
                )
                # --- ALTERAÇÃO 11 (Requisito 2: Exibir Timer de Geração) ---
                if cell['gen_time']:
                    st.caption(f"Tempo de geração: {cell['gen_time']:.2f}s")
                    
            with col_exec:
                st.button(
                    "Executar Código 🚀",
                    key=f"exec_btn_{cell['id']}", 
                    on_click=callback_execute_code_for_cell,
                    args=(index,), 
                    use_container_width=True,
                    type="primary",
                    disabled=(not cell['code'])
                )
                # --- ALTERAÇÃO 12 (Requisitos 2 & 3: Exibir Timer de Execução e Tentativas) ---
                if cell['exec_time']:
                    st.caption(f"Tempo de execução: {cell['exec_time']:.2f}s")
                if cell['execution_attempts'] > 0:
                    st.caption(f"Tentativas de execução: {cell['execution_attempts']}")

            if cell['code']:
                st.code(cell['code'], language="python")
                
            if cell['error']:
                st.error(f"Erro na execução (Tentativa {cell['execution_attempts']}):\n\n{cell['error']}")
                
            if cell['output'] is not None:
                st.subheader("Resultado:", anchor=False)
                if isinstance(cell['output'], pd.DataFrame):
                    st.dataframe(cell['output'])
                elif "matplotlib.figure.Figure" in str(type(cell['output'])):
                    st.pyplot(cell['output'])
                else:
                    st.write(cell['output'])
            
            st.divider()