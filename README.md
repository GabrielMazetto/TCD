# Assistente de Análise de Dados com LLM

Este projeto é um assistente inteligente desenvolvido em Python que utiliza Modelos de Linguagem Grande (LLMs), especificamente a família **Gemini**, para realizar análises de dados automatizadas.

O principal diferencial desta ferramenta é a **privacidade**: ela inverte o fluxo tradicional, mantendo os seus dados (datasets) na sua máquina local e enviando **apenas metadados estatísticos** para a IA.
O código de análise é gerado com base em uma **Base de Conhecimento (KB)** curada para evitar alucinações e erros de sintaxe.

---

## 📂 Estrutura do Projeto

```
TCD/
├── data/                  # Contém a Base de Conhecimento (kb.jsonl)
├── data_test/             # Datasets de referência utilizados para testes
├── src/                   # Scripts de backend e conexão com a API
│   ├── backend.py         # Lógica de processamento e segurança
│   └── gemini_client.py   # Cliente de conexão com o Google Gemini
├── app.py                 # Arquivo principal da interface Streamlit
├── requirements.txt       # Lista de dependências do projeto
└── README.md              # Documentação
```

---

## 🚀 Como Rodar

Siga os passos abaixo para configurar e executar o projeto.

### 1. Clone o repositório

```bash
git clone https://github.com/GabrielMazetto/TCD.git
cd TCD
```

### 2. Crie um Ambiente Virtual (venv)

É recomendável usar um ambiente virtual para isolar as dependências.

**No Windows:**

```bash
python -m venv venv
.\venv\Scripts\activate
```

**No Linux/Mac:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configuração da API Key

Para que o assistente funcione, você precisa configurar sua chave de API do Google AI Studio:

1. Abra o arquivo `src/gemini_client.py`.
2. Localize a string `YOUR_API_KEY`.
3. Substitua pelo valor da sua chave de API real.

> **Nota:** Nunca compartilhe sua API Key publicamente.

### 5. Execute a aplicação

Inicie o servidor do Streamlit com o comando:

```bash
streamlit run app.py
```

O navegador abrirá automaticamente.

---

## 👥 Autores

* **Gabriel De Antonio Mazetto**
* **Mateus Pereira Alves**
