import json
import os
from pathlib import Path
from typing import List

# Define o caminho para o diretório e o arquivo de log
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "extracao_log.json"

def carregar_logs_existentes(filepath: Path) -> list:
    """
    Carrega os logs do arquivo JSON. Se o arquivo não existir ou
    estiver vazio, retorna uma lista vazia.
    """
    if not filepath.exists():
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return []
    except json.JSONDecodeError:
        # Se o arquivo estiver corrompido ou vazio
        return []

def salvar_logs(filepath: Path, data: list):
    """
    Salva a lista de logs de volta no arquivo JSON,
    garantindo que o diretório exista.
    """
    # Cria o diretório 'logs' se ele não existir
    filepath.parent.mkdir(exist_ok=True)
    
    # Escreve a lista completa de volta no arquivo
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def coletar_input_validado(pergunta: str, validos: List[str]) -> str:
    """
    Coleta um input do usuário e valida se está na lista de opções válidas.
    """
    while True:
        resposta = input(pergunta).upper().strip()
        if resposta in validos:
            return resposta
        else:
            print(f"Resposta inválida. Por favor, digite uma das opções: {validos}")

def calcular_proximo_id(logs: list) -> int:
    """
    Calcula o próximo ID sequencial com base nos logs existentes.
    """
    if not logs:
        return 1
    
    # Encontra o ID mais alto, garantindo que sejam inteiros
    max_id = 0
    for log in logs:
        log_id = log.get("id_bloco")
        if isinstance(log_id, int) and log_id > max_id:
            max_id = log_id
            
    return max_id + 1

def main():
    """
    Função principal para coletar e registrar um novo bloco de extração.
    """
    # Carrega os dados existentes para calcular o novo ID
    logs = carregar_logs_existentes(LOG_FILE)
    
    # --- NOVO: Calcula o ID automaticamente ---
    novo_id = calcular_proximo_id(logs)
    
    print(f"--- Registro de Novo Bloco de Código (ID: {novo_id}) ---")
    
    # Coleta as informações (remoção da pergunta do ID)
    origem_arquivo = input("Arquivo de origem (ex: Lesson01.ipynb): ").strip()
    
    # Coleta e processa as células de origem
    while True:
        celulas_str = input("Células de origem (separadas por vírgula, ex: 28,29,31): ")
        try:
            origem_celulas = [int(c.strip()) for c in celulas_str.split(',') if c.strip().isdigit()]
            if not origem_celulas:
                raise ValueError
            break
        except ValueError:
            print("Formato inválido. Digite apenas números separados por vírgula.")

    descricao_bloco = input("Descrição do bloco: ").strip()
    
    print("\n--- Filtros Binários ---")
    filtros = {}
    filtros["e_essencial"] = coletar_input_validado("É essencial? (S/N): ", ["S", "N"])
    filtros["e_generalizavel"] = coletar_input_validado("É generalizável? (S/N): ", ["S", "N"])
    filtros["nao_e_trivial"] = coletar_input_validado("Não é trivial (via API nativa)? (S/N): ", ["S", "N"])
    
    # Define o status baseado nos filtros
    if all(valor == "S" for valor in filtros.values()):
        status = "Aprovado para adaptação"
    else:
        status = "Rejeitado"
        
    # Monta o novo registro
    novo_log = {
        "id_bloco": novo_id,  # --- MODIFICADO ---
        "origem_arquivo": origem_arquivo,
        "origem_celulas": origem_celulas,
        "descricao_bloco": descricao_bloco,
        "filtros": filtros,
        "status": status
    }
    
    # Adiciona o novo registro à lista
    logs.append(novo_log)
    
    # Salva a lista atualizada
    salvar_logs(LOG_FILE, logs)
    
    print("\n" + "="*50)
    print(f"[Sucesso] Log para ID {novo_id} salvo em {LOG_FILE}.") # --- MODIFICADO ---
    if status == "Rejeitado":
        print("Status: Bloco REJEITADO (não passou em todos os filtros).")
    else:
        print("Status: Bloco APROVADO para adaptação.")
    print("="*50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nRegistro cancelado pelo usuário.")