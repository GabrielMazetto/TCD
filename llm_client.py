# llm_client.py
"""
Wrapper simples para Gemini (google-genai).
Se não houver credenciais/SDK instalado, o wrapper faz um stub para desenvolvimento local.
"""

import os
from typing import Optional
import json
import time

# Tentativa de importar SDK oficial; se não estiver, usa stub
try:
    from google import genai
    _HAVE_GENAI = True
except Exception:
    _HAVE_GENAI = False

class LLMClient:
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
        self.api_key = os.getenv("GOOGLE_API_KEY", "AIzaSyANVfXx9oYMy0BTEaBzkOIDr0PaU1YC5u4") or os.getenv("GOOGLE_API_KEY")
        self.client = None
        self.available = False

        if _HAVE_GENAI and self.api_key:
            # passa api_key diretamente
            self.client = genai.Client(api_key=self.api_key)
            self.available = True

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0) -> str:
        """
        Gera texto usando Gemini. Se SDK não estiver configurado, retorna um stub com instruções.
        """
        start = time.time()
        if not self.available:
            return '{"error":"LLM não configurado corretamente. Verifique GEMINI_API_KEY."}'
        if self.client:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                # você pode adicionar config (ex: temperature) se quiser
            )
            elapsed = time.time() - start
            return resp.text
        else:
            # STUB: retorna um exemplo de JSON de plano ou uma resposta simples
            # Importante: em produção, remova o stub e garanta GOOGLE_API_KEY.
            elapsed = time.time() - start
            stub = {
                "note": "SDK google-genai não configurado; resposta stub retornada.",
                "prompt_excerpt": prompt[:800].replace("\n"," ") + ("..." if len(prompt)>800 else ""),
                "example_plan": {
                    "meta": {"title":"Plano exemplo (stub)", "description":"Retorno stub", "dataset_shape":[100,10]},
                    "steps":[
                        {"id":"step_01","title":"Inspeção inicial","description":"carregar e inspecionar","estimated_minutes":5,"outputs":["df"]},
                        {"id":"step_02","title":"Limpeza básica","description":"tratar nulos","estimated_minutes":10,"outputs":["df_clean"]}
                    ]
                }
            }
            return json.dumps(stub, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    client = LLMClient()
    print("LLM available:", bool(client.client))
    print(client.generate("Dê um plano curto para análise de dados."))
