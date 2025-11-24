import streamlit as st
import pandas as pd
import re
from dotenv import load_dotenv
from src.backend import BackendOrchestrator
from src.gemini_client import GeminiClient

load_dotenv()
st.set_page_config(page_title="TCD - Data Assistant", layout="wide")

st.markdown("""
<style>
div.cell-sticky-toolbar {
    position: sticky;
    top: 55px;
    background-color: #ffffff;
    z-index: 990;
    padding: 10px 5px;
    border-bottom: 2px solid #f0f2f6;
    border-radius: 0 0 5px 5px;
    margin-bottom: 15px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.log-box {
    background-color: #f0f8ff;
    border-left: 3px solid #0099cc;
    padding: 8px;
    font-family: monospace;
    font-size: 0.85em;
    margin-bottom: 5px;
    white-space: pre-wrap;
    border-radius: 4px;
}
.print-box {
    background-color: #262730;
    color: #e0e0e0;
    padding: 10px;
    border-radius: 5px;
    font-family: monospace;
    max-height: 200px;
    overflow-y: auto;
    font-size: 0.8em;
}
</style>
""", unsafe_allow_html=True)

# --- Inicialização ---
def init_state():
    if "backend" not in st.session_state:
        st.session_state.backend = BackendOrchestrator()
    if "gemini" not in st.session_state:
        st.session_state.gemini = GeminiClient()
    if "df" not in st.session_state:
        st.session_state.df = None
    if "df_history" not in st.session_state:
        st.session_state.df_history = []
    if "cells" not in st.session_state:
        st.session_state.cells = []
    if "pending_install" not in st.session_state:
        st.session_state.pending_install = None

init_state()

# --- Helpers ---
def get_log_html(logs):
    html = ""
    for log in logs:
        html += f'<div class="log-box">{log}</div>'
    return html

def append_log_realtime(cell_index, message, placeholder):
    st.session_state.cells[cell_index]["logs"].append(message)
    placeholder.markdown(get_log_html(st.session_state.cells[cell_index]["logs"]), unsafe_allow_html=True)

# --- Callbacks ---
def handle_upload():
    f = st.session_state.uploader
    if f:
        try:
            df = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            st.session_state.df = df
            st.session_state.df_history = [df.copy()]
            st.session_state.df_meta_llm = st.session_state.backend.generate_metadata(df)
            st.session_state.cells = []
            st.session_state.raw_plan = ""
        except Exception as e:
            st.error(f"Erro arquivo: {e}")

def change_model():
    st.session_state.gemini.set_model(st.session_state.model_selector)
    st.toast(f"Modelo: {st.session_state.model_selector}")

def revert_last_step():
    if len(st.session_state.df_history) > 1:
        st.session_state.df_history.pop()
        st.session_state.df = st.session_state.df_history[-1]
        st.toast("⏪ Desfeito!")
        st.rerun()

def generate_plan():
    if not st.session_state.get("objective") or st.session_state.df is None: return
    with st.spinner("Gerando plano..."):
        raw_text = st.session_state.gemini.generate_initial_plan(
            st.session_state.objective, st.session_state.df_meta_llm
        )
        match = re.search(r'(?m)^\s*1\..*', raw_text, re.DOTALL)
        if match:
            st.session_state.raw_plan = match.group(0)
        else:
            st.session_state.raw_plan = raw_text

def split_plan():
    raw = st.session_state.get("raw_plan_edit", "")
    steps = [s.strip() for s in re.split(r'(?m)^\d+\.\s+', raw) if s.strip()]
    st.session_state.cells = [{
        "id": i, "step": s, "code": "", "output": None, "print_output": "",
        "display_outputs": [], "error": None, "logs": [], "edit_mode": False 
    } for i, s in enumerate(steps)]

def process_cell_generation(index, log_placeholder):
    cell = st.session_state.cells[index]
    cell["logs"] = []
    
    append_log_realtime(index, "🚀 Iniciando geração...", log_placeholder)
    
    try:
        append_log_realtime(index, "🔍 Selecionando KB...", log_placeholder)
        kb_meta = st.session_state.backend.get_kb_metadata()
        funcs = st.session_state.gemini.select_relevant_functions(cell['step'], kb_meta)
        full_code = st.session_state.backend.get_specific_functions_code(funcs)
        if funcs: append_log_realtime(index, f"📚 Funções: {', '.join(funcs)}", log_placeholder)
        
        append_log_realtime(index, "✍️ Escrevendo código...", log_placeholder)
        draft = st.session_state.gemini.generate_final_code(
            cell['step'], st.session_state.objective, st.session_state.df_meta_llm, full_code
        )
        
        append_log_realtime(index, "⚖️ Judge: Validando...", log_placeholder)
        final_code = st.session_state.gemini.validate_code_safety(draft, cell['step'])
        
        # --- CORREÇÃO DE SEGURANÇA (Sintaxe Válida) ---
        if "data = {" in final_code or "pd.DataFrame({" in final_code:
            append_log_realtime(index, "⚠️ Mock removido.", log_placeholder)
            # Substitui por dicionário vazio para não quebrar sintaxe do python
            final_code = final_code.replace("data = {", "data = {} # Seguranca: Mock removed").replace("pd.DataFrame({", "pd.DataFrame({}) # Seguranca: Mock removed")

        append_log_realtime(index, "📦 Checando deps...", log_placeholder)
        missing = st.session_state.backend.check_missing_dependencies(final_code)
        
        if missing:
            append_log_realtime(index, f"⚠️ Instalação Requerida: {missing}", log_placeholder)
            st.session_state.pending_install = {"libs": missing, "index": index, "code": final_code}
        else:
            st.session_state.cells[index]['code'] = final_code
            st.session_state.cells[index]['error'] = None
            append_log_realtime(index, "✅ Código pronto!", log_placeholder)
            
    except Exception as e:
        append_log_realtime(index, f"❌ Erro: {str(e)}", log_placeholder)
        st.error(str(e))

def execute_cell(index):
    code = st.session_state.cells[index]['code']
    new_df, fig, err, captured_stdout, captured_displays = st.session_state.backend.execute_code(code, st.session_state.df)
    
    st.session_state.cells[index]['print_output'] = captured_stdout 
    st.session_state.cells[index]['display_outputs'] = captured_displays
    
    # --- TRATAMENTO DE DEPENDECIA EM RUNTIME ---
    if err and err.startswith("MissingDependency:"):
        missing_lib = err.split(":")[1]
        # Aciona o fluxo de instalação se der erro na execução
        st.session_state.cells[index]['error'] = f"Falta biblioteca: {missing_lib}"
        st.session_state.pending_install = {"libs": [missing_lib], "index": index, "code": code}
        st.rerun()
    elif err:
        st.session_state.cells[index]['error'] = err
    else:
        st.session_state.cells[index]['error'] = None
        st.session_state.cells[index]['output'] = fig if fig else new_df
        if isinstance(new_df, pd.DataFrame):
            st.session_state.df = new_df
            st.session_state.df_history.append(new_df.copy())
    st.rerun()

def fix_cell_code(index):
    cell = st.session_state.cells[index]
    fixed = st.session_state.gemini.generate_code_fix(cell['code'], cell['error'], cell['step'])
    st.session_state.cells[index]['code'] = fixed
    st.toast("Código corrigido!")

def toggle_edit_mode(index):
    st.session_state.cells[index]['edit_mode'] = not st.session_state.cells[index]['edit_mode']

def confirm_install():
    p = st.session_state.pending_install
    if p:
        ok, msg = st.session_state.backend.install_libraries(p['libs'])
        if ok:
            # Se for instalação via erro de execução, limpamos o erro
            idx = p['index']
            st.session_state.cells[idx]['error'] = None
            
            st.session_state.cells[idx]['code'] = p['code']
            st.session_state.pending_install = None
            st.rerun()
        else:
            st.error(msg)

# --- UI ---
with st.sidebar:
    st.title("Configurações")
    st.selectbox("Modelo", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"], 
                 key="model_selector", on_change=change_model)
    st.file_uploader("Dataset", key="uploader", on_change=handle_upload)
    st.button("⏪ Desfazer Ação", on_click=revert_last_step, disabled=len(st.session_state.df_history)<=1)

st.title("Assistente de Análise 🤖")

if st.session_state.df is not None:
    with st.expander(f"📊 Explorador de Dados (Shape: {st.session_state.df.shape})", expanded=True):
        tab1, tab2, tab3 = st.tabs(["📋 Amostra", "📈 Estatísticas", "ℹ️ Estrutura"])
        with tab1: st.dataframe(st.session_state.df.head(), use_container_width=True)
        with tab2: st.dataframe(st.session_state.df.describe(), use_container_width=True)
        with tab3:
            info_df = pd.DataFrame({"Tipo": st.session_state.df.dtypes.astype(str), "Nulos": st.session_state.df.isnull().sum()})
            st.dataframe(info_df, use_container_width=True)

    st.divider()
    st.text_area("Objetivo", key="objective", placeholder="Ex: Analisar dados...")
    if st.button("Gerar Plano", type="primary"): generate_plan()

    if st.session_state.get("raw_plan"):
        with st.expander("📝 Editar Plano Bruto", expanded=False):
            st.text_area("Plano", key="raw_plan_edit", value=st.session_state.raw_plan, height=200)
        st.markdown(f"### Plano Gerado:\n{st.session_state.raw_plan}")
        st.button("Dividir em Células 👇", on_click=split_plan)

# Loop de Células
if st.session_state.cells:
    st.divider()
    for i, cell in enumerate(st.session_state.cells):
        
        # Sticky Header
        st.markdown(f'<div class="cell-sticky-toolbar">', unsafe_allow_html=True)
        c_tit, c_b1, c_b2, c_b3 = st.columns([6, 1, 1, 1])
        with c_tit: st.markdown(f"**Passo {i+1}**")
        
        log_ph = st.empty()
        if cell['logs']: log_ph.markdown(get_log_html(cell['logs']), unsafe_allow_html=True)

        with c_b1:
            if st.button("🎲 Gerar", key=f"gen_{i}", use_container_width=True):
                process_cell_generation(i, log_ph)
                st.rerun()
        with c_b2:
            if st.button("▶️ Rodar", key=f"run_{i}", disabled=not cell['code'], type="primary", use_container_width=True):
                execute_cell(i)
        with c_b3:
             if cell.get('error'):
                if st.button("🔧 Corrigir", key=f"fix_{i}", type="secondary", use_container_width=True):
                    fix_cell_code(i)
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # 1. Descrição
        st.markdown(cell['step'])
        with st.expander("✏️ Editar Descrição", expanded=False):
             new_step = st.text_area("Texto", value=cell['step'], key=f"step_{i}", height=100)
             if new_step != cell['step']: st.session_state.cells[i]['step'] = new_step

        # --- INSTALAÇÃO PENDENTE (Renderizado DENTRO da célula correta) ---
        if st.session_state.pending_install and st.session_state.pending_install['index'] == i:
            with st.container(border=True):
                st.error(f"⚠️ Instalação Necessária: {', '.join(st.session_state.pending_install['libs'])}")
                c1, c2 = st.columns(2)
                c1.button("✅ Sim, Instalar", on_click=confirm_install, key=f"inst_yes_{i}")
                c2.button("❌ Não", on_click=lambda: st.session_state.pop("pending_install"), key=f"inst_no_{i}")

        # 2. Código
        if cell['code']:
            with st.expander("🐍 Código Python", expanded=True):
                col_view, col_tog = st.columns([8, 1])
                with col_tog:
                    icon = "👁️" if cell['edit_mode'] else "✏️"
                    if st.button(icon, key=f"tog_{i}", help="Editar Código"):
                        toggle_edit_mode(i)
                        st.rerun()
                
                if cell['edit_mode']:
                    new_code = st.text_area("Editor", value=cell['code'], key=f"ed_{i}", height=300)
                    if new_code != cell['code']: st.session_state.cells[i]['code'] = new_code
                else:
                    st.code(cell['code'], language='python')

        # 3. Erro
        if cell.get('error'):
            st.error(f"Erro:\n{cell['error']}")

        # 4. Resultados
        has_out = cell.get('output') is not None or cell.get('display_outputs') or (cell.get('print_output') and not cell.get('error'))
        if has_out:
            st.markdown("### Resultado")
            
            if cell.get('display_outputs'):
                for obj in cell['display_outputs']:
                    if isinstance(obj, (pd.DataFrame, pd.Series)): st.dataframe(obj, use_container_width=True)
                    else: st.write(obj)

            if cell.get('print_output'):
                with st.expander("Console Output (Prints)", expanded=False):
                    st.markdown(f'<div class="print-box">{cell["print_output"]}</div>', unsafe_allow_html=True)

            out = cell['output']
            if isinstance(out, pd.DataFrame): st.dataframe(out, use_container_width=True)
            elif out: st.pyplot(out)
                
        st.markdown("---")