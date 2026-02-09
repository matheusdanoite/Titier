"""
Titier - Model Manager
Gerenciamento e download de modelos do Hugging Face
"""
from pathlib import Path
from typing import Optional
import os
import asyncio
from dataclasses import dataclass
from enum import Enum


# Modelos recomendados para diferentes casos de uso
RECOMMENDED_MODELS = [
    {
        "id": "llama-3.1-8b",
        "name": "Llama 3.1 8B Instruct",
        "repo": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "size_gb": 4.9,
        "vram_required": 6,
        "description": "Modelo equilibrado para chat e RAG",
        "recommended": True
    },
    {
        "id": "llama-3.2-3b",
        "name": "Llama 3.2 3B Instruct",
        "repo": "lmstudio-community/Llama-3.2-3B-Instruct-GGUF",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size_gb": 2.0,
        "vram_required": 4,
        "description": "Modelo leve, ideal para GPUs com pouca VRAM",
        "recommended": False
    },
    {
        "id": "phi-3-mini",
        "name": "Phi-3 Mini 4K",
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "filename": "Phi-3-mini-4k-instruct-q4.gguf",
        "size_gb": 2.2,
        "vram_required": 4,
        "description": "Modelo compacto da Microsoft, muito eficiente",
        "recommended": False
    },
    {
        "id": "mistral-7b",
        "name": "Mistral 7B Instruct",
        "repo": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        "filename": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "size_gb": 4.4,
        "vram_required": 6,
        "description": "Excelente para tarefas de raciocínio",
        "recommended": False
    },
    {
        "id": "qwen2-7b",
        "name": "Qwen2 7B Instruct",
        "repo": "Qwen/Qwen2-7B-Instruct-GGUF",
        "filename": "qwen2-7b-instruct-q4_k_m.gguf",
        "size_gb": 4.4,
        "vram_required": 6,
        "description": "Modelo multilíngue com bom suporte a português",
        "recommended": False
    },
    {
        "id": "minicpm-v-2.6",
        "name": "MiniCPM-V 2.6 (Vision)",
        "repo": "openbmb/MiniCPM-V-2_6-gguf",
        "filename": "ggml-model-Q4_K_M.gguf",
        "mmproj_file": "mmproj-model-f16.gguf",
        "size_gb": 4.7,
        "vram_required": 6,
        "description": "Modelo multimodal para OCR e análise de imagens",
        "recommended": False,
        "is_vision": True
    }
]


class DownloadStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadProgress:
    model_id: str
    status: DownloadStatus
    progress: float  # 0-100
    downloaded_bytes: int
    total_bytes: int
    speed_mbps: float
    error: Optional[str] = None


class ModelManager:
    """Gerencia download e instalação de modelos GGUF."""
    
    DEFAULT_MODEL_DIR = Path.home() / ".titier" / "models"
    
    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or self.DEFAULT_MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._downloads: dict[str, DownloadProgress] = {}
        self._download_tasks: dict[str, asyncio.Task] = {}
    
    def get_recommended_models(self) -> list[dict]:
        """Retorna lista de modelos recomendados com status de instalação."""
        result = []
        for model in RECOMMENDED_MODELS:
            model_info = model.copy()
            model_path = self.model_dir / model["filename"]
            model_info["installed"] = model_path.exists()
            if model_path.exists():
                model_info["local_path"] = str(model_path)
                model_info["actual_size_gb"] = round(model_path.stat().st_size / (1024**3), 2)
            result.append(model_info)
        return result
    
    def get_installed_models(self) -> list[dict]:
        """Lista modelos instalados localmente."""
        models = []
        for gguf_file in self.model_dir.glob("*.gguf"):
            # Tentar encontrar info nos recomendados
            known = next(
                (m for m in RECOMMENDED_MODELS if m["filename"] == gguf_file.name),
                None
            )
            
            models.append({
                "filename": gguf_file.name,
                "path": str(gguf_file),
                "size_gb": round(gguf_file.stat().st_size / (1024**3), 2),
                "name": known["name"] if known else gguf_file.stem,
                "description": known["description"] if known else "Modelo personalizado"
            })
        return models
    
    def get_model_by_id(self, model_id: str) -> Optional[dict]:
        """Busca modelo por ID."""
        return next((m for m in RECOMMENDED_MODELS if m["id"] == model_id), None)
    
    def get_vision_model_path(self) -> Optional[dict]:
        """Retorna paths do primeiro modelo de visão disponível (model_path, mmproj_path)."""
        # Iterar sobre modelos recomendados para achar um de visão instalado
        for model_info in RECOMMENDED_MODELS:
            if model_info.get("is_vision", False):
                path = self.model_dir / model_info["filename"]
                
                if path.exists():
                    # Verificar se existe o projetor separado
                    mmproj_path = None
                    if "mmproj_file" in model_info:
                        p_path = self.model_dir / model_info["mmproj_file"]
                        # Se existe o arquivo, usá-lo. Se não existe, retornamos None e o inference.py
                        # vai tentar usar o main model como projetor (embedded)
                        if p_path.exists():
                            mmproj_path = p_path
                            
                    return {"model_path": path, "mmproj_path": mmproj_path}
                    
        return None
        
    def get_chat_model_path(self) -> Optional[Path]:
        """Retorna o caminho do melhor modelo de chat disponível (excluindo visão)."""
        # Priorizar Llama 3.2, depois Phi-3, etc.
        priority_ids = ["llama-3.2-3b", "llama-3.1-8b", "phi-3-mini", "mistral-7b", "qwen2-7b"]
        
        for model_id in priority_ids:
            model_info = self.get_model_by_id(model_id)
            if model_info:
                path = self.model_dir / model_info["filename"]
                if path.exists():
                    return path
                    
        # Fallback: pegar qualquer gguf que não seja o vision
        vision_path = self.get_vision_model_path()
        for gguf in self.model_dir.glob("*.gguf"):
            if vision_path and gguf.name == vision_path.name:
                continue
            return gguf
            
        return None
    
    async def download_model(
        self,
        model_id: str,
        progress_callback=None
    ) -> DownloadProgress:
        """
        Baixa um modelo do Hugging Face Hub.
        Retorna progresso final.
        """
        model = self.get_model_by_id(model_id)
        if not model:
            return DownloadProgress(
                model_id=model_id,
                status=DownloadStatus.FAILED,
                progress=0,
                downloaded_bytes=0,
                total_bytes=0,
                speed_mbps=0,
                error="Modelo não encontrado"
            )
        
        # Verificar se já existe
        target_path = self.model_dir / model["filename"]
        if target_path.exists():
            return DownloadProgress(
                model_id=model_id,
                status=DownloadStatus.COMPLETED,
                progress=100,
                downloaded_bytes=target_path.stat().st_size,
                total_bytes=target_path.stat().st_size,
                speed_mbps=0
            )
        
        total_bytes = int(model["size_gb"] * 1024**3)
        
        # Inicializar progresso
        self._downloads[model_id] = DownloadProgress(
            model_id=model_id,
            status=DownloadStatus.DOWNLOADING,
            progress=0,
            downloaded_bytes=0,
            total_bytes=total_bytes,
            speed_mbps=0
        )
        
        try:
            from huggingface_hub import hf_hub_download
            import time
            import threading
            
            start_time = time.time()
            download_complete = threading.Event()
            
            # Thread para monitorar progresso via tamanho do arquivo
            def monitor_progress():
                # Procurar arquivos temporários ou parciais sendo baixados
                possible_paths = [
                    target_path,  # Arquivo final
                    target_path.with_suffix('.incomplete'),  # Possível temp
                ]
                
                last_size = 0
                while not download_complete.is_set():
                    current_size = 0
                    
                # Verificar todos os arquivos sendo baixados (inclusive ocultos/temp)
                    try:
                        for f in self.model_dir.iterdir():
                            # Se o nome do arquivo contém o nome do modelo (ex: .filename.gguf.incomplete)
                            if model["filename"] in f.name:
                                try:
                                    current_size = max(current_size, f.stat().st_size)
                                except:
                                    pass
                    except Exception as e:
                        print(f"Erro no monitoramento: {e}")
                    
                    # Também checar cache do HuggingFace
                    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
                    for f in hf_cache.rglob(f"*{model['filename']}*"):
                        try:
                            current_size = max(current_size, f.stat().st_size)
                        except:
                            pass
                    
                    if current_size > 0:
                        elapsed = time.time() - start_time
                        speed = ((current_size - last_size) / (1024**2)) / 1.0 if elapsed > 0 else 0
                        progress = min(99, (current_size / total_bytes) * 100)
                        
                        self._downloads[model_id] = DownloadProgress(
                            model_id=model_id,
                            status=DownloadStatus.DOWNLOADING,
                            progress=round(progress, 1),
                            downloaded_bytes=current_size,
                            total_bytes=total_bytes,
                            speed_mbps=round(speed, 2)
                        )
                        last_size = current_size
                    
                    time.sleep(1)
            
            # Iniciar monitoramento
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()
            
            # Download usando huggingface_hub
            downloaded_path = await asyncio.to_thread(
                hf_hub_download,
                repo_id=model["repo"],
                filename=model["filename"],
                local_dir=str(self.model_dir),
                local_dir_use_symlinks=False
            )
            
            # Download do mmproj (se houver)
            if "mmproj_file" in model:
                print(f"[ModelManager] Baixando projetor {model['mmproj_file']}...")
                await asyncio.to_thread(
                    hf_hub_download,
                    repo_id=model["repo"],
                    filename=model["mmproj_file"],
                    local_dir=str(self.model_dir),
                    local_dir_use_symlinks=False
                )
            
            download_complete.set()
            elapsed = time.time() - start_time
            file_size = Path(downloaded_path).stat().st_size
            speed = (file_size / (1024**2)) / elapsed if elapsed > 0 else 0
            
            self._downloads[model_id] = DownloadProgress(
                model_id=model_id,
                status=DownloadStatus.COMPLETED,
                progress=100,
                downloaded_bytes=file_size,
                total_bytes=file_size,
                speed_mbps=round(speed, 2)
            )
            
        except Exception as e:
            self._downloads[model_id] = DownloadProgress(
                model_id=model_id,
                status=DownloadStatus.FAILED,
                progress=0,
                downloaded_bytes=0,
                total_bytes=int(model["size_gb"] * 1024**3),
                speed_mbps=0,
                error=str(e)
            )
        
        return self._downloads[model_id]
    
    def get_download_progress(self, model_id: str) -> Optional[DownloadProgress]:
        """Retorna progresso atual do download."""
        return self._downloads.get(model_id)
    
    def delete_model(self, filename: str) -> bool:
        """Remove um modelo instalado."""
        model_path = self.model_dir / filename
        if model_path.exists():
            model_path.unlink()
            return True
        return False


# Singleton
_model_manager: Optional[ModelManager] = None

def get_model_manager() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
