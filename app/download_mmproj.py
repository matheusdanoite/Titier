import asyncio
from huggingface_hub import hf_hub_download
from pathlib import Path

async def download_mmproj():
    model_dir = Path.home() / ".titier" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Baixando mmproj-model-f16.gguf para {model_dir}...")
    
    try:
        path = await asyncio.to_thread(
            hf_hub_download,
            repo_id="openbmb/MiniCPM-V-2_6-gguf",
            filename="mmproj-model-f16.gguf",
            local_dir=str(model_dir),
            local_dir_use_symlinks=False
        )
        print(f"Sucesso! Arquivo salvo em: {path}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(download_mmproj())
