
import asyncio
import sys
from pathlib import Path

# Adicionar o diretório app ao path
sys.path.append(str(Path(__file__).parent.parent / "app"))

from core.model_manager import get_model_manager

async def test_discovery():
    manager = get_model_manager()
    print("Iniciando descoberta de modelos...")
    models = await asyncio.to_thread(manager.get_recommended_models)
    
    print(f"\nEncontrados {len(models)} modelos recomendados:")
    for i, m in enumerate(models, 1):
        pos = f"{i}."
        print(f"{pos:<3} {m['name']} ({m['repo']})")
        print(f"    RAM: {m['vram_required']}GB | Desc: {m['description']}")
        print(f"    Score: {m.get('score', 'N/A')}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_discovery())
