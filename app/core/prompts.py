"""
Titier - Gerenciamento centralizado de System Prompts.
Permite customização pelo usuário via UI, com persistência em JSON.
"""
import json
from pathlib import Path
from typing import Dict, Optional

# Diretório de configuração
CONFIG_DIR = Path.home() / ".titier" / "config"
PROMPTS_FILE = CONFIG_DIR / "prompts.json"

# === Prompts Padrão ===
DEFAULT_PROMPTS: Dict[str, str] = {
    "system_base": """Você é Titier, um assistente de estudos inteligente e dedicado.

Suas diretrizes:
- Responda sempre em português brasileiro, de forma clara, organizada e didática.
- Use Markdown para estruturar suas respostas (títulos, listas, negrito, etc.).
- Quando apropriado, forneça exemplos, analogias ou resumos para facilitar o entendimento.
- Se não souber a resposta, diga honestamente em vez de inventar informações.
- Seja conciso, mas completo. Priorize a clareza sobre a verbosidade.
- Adapte o nível de linguagem ao contexto: acadêmico quando o conteúdo exigir, acessível quando for uma pergunta simples.""",

    "system_rag": """Você é Titier, um assistente de estudos inteligente e dedicado.

Baseie sua resposta EXCLUSIVAMENTE no seguinte contexto extraído dos documentos do usuário:

---
{context}
---

Suas diretrizes:
- Responda sempre em português brasileiro, de forma clara, organizada e didática.
- Use Markdown para estruturar a resposta (títulos ##, listas, **negrito**, trechos de código, etc.).
- Cite as informações do contexto de forma fiel. Não invente dados que não estejam no contexto.
- Preserve termos técnicos, nomes próprios e referências exatamente como aparecem no documento.
- Se o contexto não contiver informação suficiente para responder, diga explicitamente: "O documento não contém informação suficiente sobre este tema."
- Quando relevante, indique a página ou seção de onde a informação foi extraída.
- Organize as informações de forma hierárquica: do mais importante para o menos importante.
- Seja conciso, mas completo. Priorize a clareza sobre a verbosidade.
- Ao resumir, capture a essência e os argumentos-chave sem perder nuances importantes.""",

    "system_vision": "Você é um assistente de visão computacional especializado em OCR de documentos acadêmicos. Analise a imagem com precisão. Responda sempre em JSON válido."
}

# Cache em memória
_cached_prompts: Optional[Dict[str, str]] = None


def _load_custom_prompts() -> Optional[Dict[str, str]]:
    """Carrega prompts customizados do arquivo JSON."""
    if not PROMPTS_FILE.exists():
        return None
    try:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Prompts] Erro ao carregar prompts customizados: {e}")
        return None


def get_prompts() -> Dict[str, str]:
    """
    Retorna os prompts ativos.
    Se existirem prompts customizados, mescla com os padrões (custom tem prioridade).
    """
    global _cached_prompts
    if _cached_prompts is not None:
        return _cached_prompts

    prompts = dict(DEFAULT_PROMPTS)
    custom = _load_custom_prompts()
    if custom:
        # Só sobrescrever keys válidas que não estejam vazias
        for key in DEFAULT_PROMPTS:
            if key in custom and custom[key].strip():
                prompts[key] = custom[key]

    _cached_prompts = prompts
    return prompts


def save_prompts(prompts: Dict[str, str]) -> None:
    """Salva prompts customizados em disco e atualiza o cache."""
    global _cached_prompts
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Filtrar apenas keys válidas
    valid = {k: v for k, v in prompts.items() if k in DEFAULT_PROMPTS and v.strip()}

    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)

    # Invalidar cache para forçar releitura
    _cached_prompts = None
    print(f"[Prompts] Prompts customizados salvos em {PROMPTS_FILE}")


def reset_prompts() -> None:
    """Remove prompts customizados e volta aos padrões."""
    global _cached_prompts
    if PROMPTS_FILE.exists():
        PROMPTS_FILE.unlink()
    _cached_prompts = None
    print("[Prompts] Prompts restaurados para os padrões.")


def get_defaults() -> Dict[str, str]:
    """Retorna os prompts padrão (sempre iguais)."""
    return dict(DEFAULT_PROMPTS)
