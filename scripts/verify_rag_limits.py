import sys
import os
from pathlib import Path
from typing import Optional

# Adicionar app ao path
sys.path.append(str(Path(__file__).parent.parent / "app"))

from server import _get_dynamic_rag_limit, ChatRequest

class MockModel:
    def __init__(self, n_ctx):
        self.n_ctx = n_ctx

def test_rag_limits():
    print("--- Teste de Limites de RAG Dinâmicos ---")
    
    # 1. Teste sem modelo (Default)
    req = ChatRequest(message="Olá")
    print(f"Sem modelo (Default): {_get_dynamic_rag_limit(req, None)} (Esperado: 3)")
    
    # 2. Teste com modelo de baixo contexto
    model_low = MockModel(n_ctx=2048)
    print(f"Modelo 2K n_ctx: {_get_dynamic_rag_limit(req, model_low)} (Esperado: 2)")
    
    # 3. Teste com modelo de contexto médio
    model_med = MockModel(n_ctx=4096)
    print(f"Modelo 4K n_ctx: {_get_dynamic_rag_limit(req, model_med)} (Esperado: 5)")
    
    # 4. Teste com modelo de contexto alto
    model_high = MockModel(n_ctx=8192)
    print(f"Modelo 8K n_ctx: {_get_dynamic_rag_limit(req, model_high)} (Esperado: 10)")
    
    # 5. Teste com modelo de contexto ultra (Llama 3.1/3.2)
    model_ultra = MockModel(n_ctx=131072)
    print(f"Modelo 128K n_ctx: {_get_dynamic_rag_limit(req, model_ultra)} (Esperado: 20)")
    
    # 6. Teste com override manual
    req_override = ChatRequest(message="Olá", rag_chunks=50)
    print(f"Override manual (50): {_get_dynamic_rag_limit(req_override, model_ultra)} (Esperado: 50)")

if __name__ == "__main__":
    test_rag_limits()
