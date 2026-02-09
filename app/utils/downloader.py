import os
from huggingface_hub import hf_hub_download

MODELS = {
    "minicpm": {
        "repo_id": "openbmb/MiniCPM-V-2_6-GGUF",
        "filename": "MiniCPM-V-2_6-Q4_K_M.gguf",
    },
    "llama3": {
        "repo_id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
    }
}

def download_model(model_key: str, target_dir: str = "./models"):
    """
    Baixa um modelo do Hugging Face para o diretório local.
    """
    if model_key not in MODELS:
        print(f"Modelo '{model_key}' não catalogado.")
        return None

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    model_info = MODELS[model_key]
    target_path = os.path.join(target_dir, model_info["filename"])

    if os.path.exists(target_path):
        print(f"O modelo {model_info['filename']} já existe em {target_dir}. Pulando download.")
        return target_path

    print(f"Iniciando download de {model_info['filename']} de {model_info['repo_id']}...")
    
    path = hf_hub_download(
        repo_id=model_info["repo_id"],
        filename=model_info["filename"],
        local_dir=target_dir
    )
    
    print(f"Download concluído: {path}")
    return path

def check_and_download_all(target_dir: str = "./models"):
    """
    Verifica e baixa os modelos necessários para o projeto.
    """
    paths = {}
    for key in MODELS.keys():
        paths[key] = download_model(key, target_dir)
    return paths

if __name__ == "__main__":
    # Permite rodar o download direto via CLI
    check_and_download_all()
