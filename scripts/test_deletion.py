
import sys
import os
from pathlib import Path

# Adicionar o diretório app ao path
sys.path.append(str(Path(__file__).parent.parent / "app"))

from core.model_manager import get_model_manager

def test_deletion():
    manager = get_model_manager()
    model_dir = manager.model_dir
    
    # Criar arquivos dummy
    model_file = "test_model.gguf"
    mmproj_file = "mmproj-test.gguf"
    
    (model_dir / model_file).write_text("dummy model content")
    (model_dir / mmproj_file).write_text("dummy mmproj content")
    
    print(f"Arquivos criados em {model_dir}")
    print(f"Existe model? {(model_dir / model_file).exists()}")
    print(f"Existe mmproj? {(model_dir / mmproj_file).exists()}")
    
    # Adicionar ao cache para simular modelo conhecido
    manager.model_cache["test__id"] = {
        "filename": model_file,
        "mmproj_file": mmproj_file
    }
    
    # Executar exclusão
    print("\nExecutando exclusão...")
    success = manager.delete_model(model_file)
    
    print(f"Sucesso na exclusão? {success}")
    print(f"Existe model? {(model_dir / model_file).exists()}")
    print(f"Existe mmproj? {(model_dir / mmproj_file).exists()}")
    
    if success and not (model_dir / model_file).exists() and not (model_dir / mmproj_file).exists():
        print("\nTESTE PASSOU: Ambos os arquivos foram removidos com sucesso.")
    else:
        print("\nTESTE FALHOU.")

if __name__ == "__main__":
    test_deletion()
