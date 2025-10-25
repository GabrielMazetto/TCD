import json
import inspect
import importlib.util
from pathlib import Path
from typing import Any, Dict, List

# Define o caminho para o arquivo KB
KB_FILE = Path("kb.jsonl")

def carregar_kb() -> List[Dict[str, Any]]:
    """Carrega a base de conhecimento (kb.jsonl)."""
    if not KB_FILE.exists():
        return []
    
    registros = []
    with open(KB_FILE, 'r', encoding='utf-8') as f:
        for linha in f:
            try:
                registros.append(json.loads(linha))
            except json.JSONDecodeError:
                print(f"Aviso: Ignorando linha mal formatada no {KB_FILE}")
    return registros

def salvar_no_kb(registro: Dict[str, Any]):
    """Salva um novo registro (linha) no kb.jsonl."""
    with open(KB_FILE, 'a', encoding='utf-8') as f:
        json.dump(registro, f, ensure_ascii=False)
        f.write('\n') # Adiciona uma nova linha

def coletar_input_validado(pergunta: str, validos: List[str]) -> str:
    """Coleta um input (S/N) do usuário."""
    while True:
        resposta = input(pergunta).upper().strip()
        if resposta in validos:
            return resposta
        else:
            print(f"Resposta inválida. Por favor, digite uma das opções: {validos}")

def carregar_funcao_do_arquivo(caminho_arquivo: Path, nome_funcao: str) -> Any:
    """Carrega dinamicamente um objeto de função a partir de um arquivo .py."""
    # Cria um nome de módulo único baseado no caminho
    nome_modulo = f"modules.{caminho_arquivo.parent.name}.{caminho_arquivo.stem}"

    spec = importlib.util.spec_from_file_location(nome_modulo, caminho_arquivo)
    if not spec or not spec.loader:
        raise ImportError(f"Não foi possível criar a especificação do módulo para {caminho_arquivo}")

    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    
    funcao = getattr(modulo, nome_funcao, None)
    if not funcao or not inspect.isfunction(funcao):
        raise AttributeError(f"Função '{nome_funcao}' não encontrada ou não é uma função em {caminho_arquivo}")
        
    return funcao

def gerar_id_funcao(categoria: str, titulo: str, versao: str) -> str:
    """Gera um ID legível (slug) para a função."""
    cat_slug = categoria.lower().replace(" ", "_").replace("ç", "c").replace("ã", "a")
    return f"{cat_slug}.{titulo}.{versao.replace('.', '_')}"

def main():
    print("--- Incorporação de Nova Função ao Knowledge Base (KB) ---")

    try:
        # 1. Obter o arquivo e o nome da função
        caminho_str = input("Caminho do módulo (ex: modules/limpeza_dados/clean_functions.py): ").strip()
        caminho_arquivo = Path(caminho_str)
        if not caminho_arquivo.exists():
            print(f"Erro: Arquivo '{caminho_str}' não encontrado.")
            return

        nome_funcao = input(f"Nome da função em '{caminho_str}' (ex: remove_rows_all_zeros_except): ").strip()
        
        # 2. Carregar a função dinamicamente
        funcao = carregar_funcao_do_arquivo(caminho_arquivo, nome_funcao)
        print(f"Função '{nome_funcao}' carregada com sucesso.")

        # 3. Coletar metadados
        categoria = input("Categoria (ex: Exploração e Limpeza de Dados): ").strip()
        subcategoria = input("Subcategoria (ex: Tratamento de Dados Inválidos): ").strip()
        descricao = input("Descrição breve (para o título): ").strip()
        versao = input("Versão (ex: 0.1.0): ").strip()

        # 4. Gerar ID e pegar código-fonte
        id_funcao = gerar_id_funcao(categoria, nome_funcao, versao)
        codigo_funcao = inspect.getsource(funcao)
        
        # 5. Coletar bibliotecas (simplificado)
        bibliotecas_str = input("Bibliotecas principais usadas (separadas por vírgula, ex: pandas, numpy): ")
        bibliotecas = [b.strip() for b in bibliotecas_str.split(',') if b.strip()]

        # 6. Executar Checklist de Aceitação (Etapa 7)
        print("\n--- Checklist de Aceitação (Etapa 7) ---")
        
        # Verificação automática (parcial)
        assinatura = inspect.signature(funcao)
        tem_hints = all(p.annotation != inspect.Parameter.empty for p in assinatura.parameters.values()) and \
                    (assinatura.return_annotation != inspect.Signature.empty)
        
        tem_docstring = inspect.getdoc(funcao) and "Args:" in inspect.getdoc(funcao) and "Returns:" in inspect.getdoc(funcao)

        if not tem_hints:
            print("AVISO: Função parece não ter type hints completos (parâmetros + retorno).")
        if not tem_docstring:
            print("AVISO: Docstring parece não estar no formato Google (Args: / Returns:).")

        # Verificação manual
        checklist = {}
        checklist["type_hints"] = coletar_input_validado("Assinatura com type hints está completa? (S/N): ", ["S", "N"])
        checklist["docstring"] = coletar_input_validado("Docstring Google Style (Args/Returns) está completa? (S/N): ", ["S", "N"])
        checklist["generalizavel"] = coletar_input_validado("Função não depende de nomes de colunas hard-coded? (S/N): ", ["S", "N"])
        checklist["testes_passaram"] = coletar_input_validado("Teste de incorporação (pytest) passou nos 2 datasets? (S/N): ", ["S", "N"])

        if not all(v == "S" for v in checklist.values()):
            print("\n[FALHA] A função não passou no checklist de aceitação. Corrija os pontos e tente novamente.")
            print("O registro NÃO foi salvo no kb.jsonl.")
            # Aqui você poderia salvar em 'rejected_functions.jsonl'
            return

        # 7. Montar o registro
        novo_registro = {
            "id_funcao": id_funcao,
            "titulo": nome_funcao,
            "categoria": categoria,
            "subcategoria": subcategoria,
            "descricao": descricao,
            "codigo_funcao": codigo_funcao,
            "bibliotecas": bibliotecas,
            "versao": versao
        }

        # 8. Salvar
        salvar_no_kb(novo_registro)
        print("\n" + "="*50)
        print(f"[Sucesso] Função '{nome_funcao}' (ID: {id_funcao})")
        print(f"incorporada com sucesso ao arquivo {KB_FILE}.")
        print("="*50)

    except Exception as e:
        print(f"\nOcorreu um erro inesperado: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nIncorporação cancelada pelo usuário.")