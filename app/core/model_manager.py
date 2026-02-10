"""
Titier - Model Manager
Gerenciamento e download de modelos do Hugging Face
"""
from pathlib import Path
from typing import Optional
import asyncio
from dataclasses import dataclass
from enum import Enum
import psutil
from datetime import datetime, timezone
from huggingface_hub import HfApi
import os

# Modelos recomendados e base para busca
RECOMMENDED_MODELS = [
    {
        "id": "llama-3.2-3b-q4",
        "name": "Llama 3.2 3B Instruct (Q4_K_M)",
        "repo": "lmstudio-community/Llama-3.2-3B-Instruct-GGUF",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size_gb": 2.1,
        "vram_required": 4,
        "description": "Modelo ultra-rápido e econômico, ideal para Macs com 8GB de RAM.",
        "recommended": True,
    },
    {
        "id": "llama-3.1-8b-q5",
        "name": "Llama 3.1 8B Instruct (Q5_K_M)",
        "repo": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf",
        "size_gb": 5.7,
        "vram_required": 8,
        "description": "Modelo potente, ideal para placas RTX 5060 (8GB VRAM) ou Macs com 16GB+.",
        "recommended": False,
    },
    {
        "id": "paddleocr-vl-1.5",
        "name": "PaddleOCR-VL 1.5 (Vision OCR)",
        "repo": "PaddlePaddle/PaddleOCR-VL-1.5",
        "size_gb": 1.8,
        "vram_required": 4,
        "description": "OCR com visão para documentos escaneados (PaddlePaddle)",
        "is_vision": True,
        "uses_paddleocr": True,
    },
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
        self.hf_token = os.getenv("HF_TOKEN")
        
        # Ativar hf_transfer para velocidade máxima
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
        
        self._hf_api = HfApi(token=self.hf_token)
        
        # Cache para modelos descobertos dinamicamente
        # Chave: model_id (com __), Valor: dict do modelo
        self.model_cache = {}

    def _estimate_specs(self, model_id: str, filename: str) -> tuple[float, float]:
        """Estima tamanho e VRAM baseada no nome/ID do modelo com mais precisão."""
        try:
            import re
            
            # Normalizar input
            text = model_id.lower()
            
            # Tentar extrair parâmetros (ex: 7b, 8b, 72b, 400m)
            # 1. Bilhões (B)
            billions = re.search(r'(\d+(?:\.\d+)?)\s*b', text)
            if billions:
                params = float(billions.group(1))
            else:
                # 2. Milhões (M) -> Converter para B (ex: 400m = 0.4b)
                millions = re.search(r'(\d+(?:\.\d+)?)\s*m', text)
                if millions:
                    params = float(millions.group(1)) / 1000
                else:
                    # Fallback para nomes comuns conhecidos
                    if "llama-3" in text: params = 8
                    elif "mistral" in text: params = 7
                    elif "gemma" in text: params = 2
                    elif "qwen" in text: params = 7
                    elif "phi" in text: params = 3
                    elif "glm" in text: params = 9
                    elif "stories" in text: params = 0.1
                    else: return 0.0, 0.0

            # Tentar extrair bits da quantização (ex: Q4, Q5, Q8, F16)
            fname = filename.lower()
            if "q4_k_m" in fname: bits = 4.8 # Q4_K_M é ligeiramente maior que Q4_0
            elif "q4_0" in fname: bits = 4.5
            elif "q4" in fname: bits = 4.5
            elif "q5" in fname: bits = 5.5
            elif "q6" in fname: bits = 6.5
            elif "q8" in fname: bits = 8.5
            elif "f16" in fname: bits = 16
            elif "f32" in fname: bits = 32
            elif "iq" in fname: bits = 4
            else: bits = 5 # fallback seguro
            
            # Tamanho do arquivo em GB = (Params * Bits) / 8
            size_gb = (params * bits) / 8
            
            # VRAM = Tamanho + Contexto (overhead de ~1-2GB para contexto de 8k-32k)
            # Para modelos pequenos, o overhead é percentualmente maior
            vram_gb = size_gb + max(1.0, size_gb * 0.1)
            
            return round(size_gb, 1), round(vram_gb, 1)
            
        except Exception:
            return 0.0, 0.0

    def import_model(self, source_path: str) -> dict:
        """Importa um modelo local (.gguf) para a pasta de modelos."""
        import shutil
        import hashlib
        
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {source_path}")
            
        if not source.name.lower().endswith(".gguf"):
            raise ValueError("O arquivo deve ter extensão .gguf")
            
        # Calcular specs básicos
        size_gb = round(source.stat().st_size / (1024**3), 2)
        vram_required = size_gb + 1.5 # Estimativa conservadora
        
        target_path = self.model_dir / source.name
        
        # Copiar arquivo (pode demorar, idealmente deveria ser async ou ter progresso, mas copy é robusto)
        print(f"[ModelManager] Importando {source.name}...")
        shutil.copy2(source, target_path)
        
        model_id = f"local__{source.stem.lower()}"
        model_data = {
            "id": model_id,
            "name": source.stem,
            "filename": source.name,
            "size_gb": size_gb,
            "vram_required": vram_required,
            "description": "Modelo importado manualmente",
            "installed": True,
            "path": str(target_path)
        }
        
        # Atualizar cache
        self.model_cache[model_id] = model_data
        return model_data

    def get_recommended_models(self) -> list[dict]:
        """Retorna lista de modelos recomendados (agora estática)."""
        models = []
        for model in RECOMMENDED_MODELS:
            m = model.copy()
            # Checar se instalado
            if "filename" in m:
                m["installed"] = (self.model_dir / m["filename"]).exists()
                if m["installed"]:
                    m["local_path"] = str(self.model_dir / m["filename"])
            else:
                m["installed"] = False
            models.append(m)
        return models

    # Mantendo compatibilidade com métodos antigos
    
    def get_system_ram(self) -> float:
        """Retorna RAM total do sistema em GB."""
        return psutil.virtual_memory().total / (1024**3)

    def get_installed_models(self) -> list[dict]:
        """Lista modelos instalados localmente com metadados completos."""
        models = []
        for gguf_file in self.model_dir.glob("*.gguf"):
            # Ignorar arquivos mmproj (projetores) da lista principal de modelos
            if gguf_file.name.startswith("mmproj-"):
                continue

            # Tentar encontrar info nos recomendados ou cache
            known = next(
                (m for m in RECOMMENDED_MODELS if "filename" in m and m["filename"] == gguf_file.name),
                None
            )
            
            if not known:
                for m in self.model_cache.values():
                    if m.get("filename") == gguf_file.name:
                        known = m
                        break
            
            # Se não conhecemos, estimamos os specs na hora
            if known:
                size_gb = known.get("size_gb", round(gguf_file.stat().st_size / (1024**3), 2))
                vram_required = known.get("vram_required", 0)
                name = known["name"]
                description = known["description"]
                model_id = known.get("id", f"local__{gguf_file.stem.lower()}")
            else:
                size_gb, vram_required = self._estimate_specs(gguf_file.stem, gguf_file.name)
                # Se a estimativa falhou (0), pegamos o tamanho real do arquivo
                if size_gb == 0:
                    size_gb = round(gguf_file.stat().st_size / (1024**3), 2)
                    vram_required = size_gb + 1 # Fallback simples
                
                name = gguf_file.stem
                description = "Instalado localmente"
                model_id = f"local__{gguf_file.stem.lower()}"

            models.append({
                "id": model_id,
                "filename": gguf_file.name,
                "path": str(gguf_file),
                "size_gb": size_gb,
                "vram_required": vram_required,
                "name": name,
                "description": description,
                "installed": True
            })
        return models
    
    def get_model_by_id(self, model_id: str) -> Optional[dict]:
        """Busca modelo por ID (no cache dinâmico ou estáticos)."""
        # 1. Verificar cache dinâmico
        if model_id in self.model_cache:
            return self.model_cache[model_id]
            
        # 2. Verificar lista estática (legado)
        return next((m for m in RECOMMENDED_MODELS if m["id"] == model_id), None)
    
    def get_vision_model_path(self) -> Optional[dict]:
        """Retorna paths do primeiro modelo de visão disponível (model_path, mmproj_path).
        
        Busca dinamicamente em:
        1. Modelos instalados marcados como visão
        2. Lista de modelos recomendados
        3. Cache de modelos descobertos
        """
        # 1. Verificar modelos recomendados conhecidos (prioridade)
        for model_info in RECOMMENDED_MODELS:
            if model_info.get("is_vision", False):
                if "filename" not in model_info:
                    continue
                path = self.model_dir / model_info["filename"]
                
                if path.exists():
                    mmproj_path = None
                    if "mmproj_file" in model_info:
                        p_path = self.model_dir / model_info["mmproj_file"]
                        if p_path.exists():
                            mmproj_path = p_path
                            
                    return {"model_path": path, "mmproj_path": mmproj_path}
        
        # 2. Buscar qualquer modelo de visão instalado (dinâmico)
        for model in self.model_cache.values():
            if model.get("is_vision", False):
                path = self.model_dir / model["filename"]
                if path.exists():
                    mmproj_path = None
                    if "mmproj_file" in model:
                        p_path = self.model_dir / model["mmproj_file"]
                        if p_path.exists():
                            mmproj_path = p_path
                    return {"model_path": path, "mmproj_path": mmproj_path}
        
        # 3. Heurística: qualquer GGUF com 'vision', 'vl', ou 'minicpm' no nome
        for gguf in self.model_dir.glob("*.gguf"):
            name_lower = gguf.name.lower()
            if any(marker in name_lower for marker in ["vision", "-vl-", "minicpm", "llava"]):
                # Tentar encontrar mmproj correspondente
                mmproj_path = None
                for mmproj in self.model_dir.glob("mmproj*.gguf"):
                    mmproj_path = mmproj
                    break
                return {"model_path": gguf, "mmproj_path": mmproj_path}
                    
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
                last_monitor_time = start_time
                while not download_complete.is_set():
                    current_size = 0
                    # Verificar todos os arquivos sendo baixados (inclusive ocultos/temp e .cache)
                    try:
                        # 1. Checar se o arquivo final já existe (ou parcial no rglob)
                        if target_path.exists():
                            current_size = target_path.stat().st_size
                        
                        # 2. Procurar na pasta de download do cache local
                        cache_download_dir = self.model_dir / ".cache" / "huggingface" / "download"
                        if cache_download_dir.exists():
                            # Tentar achar pelo arquivo .metadata
                            metadata_file = cache_download_dir / f"{model['filename']}.metadata"
                            if metadata_file.exists():
                                try:
                                    lines = metadata_file.read_text().splitlines()
                                    if len(lines) >= 2:
                                        hash_val = lines[1].strip()
                                        for f in cache_download_dir.glob(f"*{hash_val}*.incomplete"):
                                            current_size = max(current_size, f.stat().st_size)
                                except:
                                    pass
                        
                        # 3. Fallback: rglob por partes do nome se tudo falhar
                        if current_size == 0:
                            for f in self.model_dir.rglob("*"):
                                if f.is_file() and (model["filename"] in f.name):
                                    try:
                                        current_size = max(current_size, f.stat().st_size)
                                    except:
                                        pass
                    except Exception as e:
                        # Silenciosamente ignorar erros de IO durante monitoramento
                        pass
                    
                    if current_size > 0:
                        now = time.time()
                        elapsed_since_last = now - last_monitor_time
                        if elapsed_since_last >= 1.0:
                            speed = ((current_size - last_size) / (1024**2)) / elapsed_since_last
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
                            last_monitor_time = now
                    
                    time.sleep(0.5) # Monitoramento mais frequente (0.5s)
            
            # Iniciar monitoramento
            monitor_thread = threading.Thread(target=monitor_progress, daemon=True)
            monitor_thread.start()
            
            # Download usando huggingface_hub
            downloaded_path = await asyncio.to_thread(
                hf_hub_download,
                repo_id=model["repo"],
                filename=model["filename"],
                local_dir=str(self.model_dir),
                local_dir_use_symlinks=False,
                resume_download=True  # Garantir resume
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
        
    def get_all_downloads(self) -> list[DownloadProgress]:
        """Retorna todos os downloads ativos ou recentes."""
        # Limpar downloads antigos/completados se necessário? 
        # Por enquanto retornar tudo que está na memória
        return list(self._downloads.values())
    
    def delete_model(self, filename: str) -> bool:
        """Remove um modelo instalado e seus arquivos auxiliares."""
        model_path = self.model_dir / filename
        success = False
        
        if model_path.exists():
            print(f"[ModelManager] Removendo modelo: {filename}")
            model_path.unlink()
            success = True
            
            # Tentar encontrar se este modelo tem um projetor multimodal associado
            # Procuramos por modelos conhecidos (estáticos ou cache) que usam este filename
            model_info = None
            
            # 1. Procurar no cache dinâmico
            for m in self.model_cache.values():
                if m.get("filename") == filename:
                    model_info = m
                    break
            
            # 2. Procurar nos recomendados estáticos
            if not model_info:
                for m in RECOMMENDED_MODELS:
                    if m.get("filename") == filename:
                        model_info = m
                        break
            
            # Se encontramos a info e tem mmproj, remover
            if model_info and "mmproj_file" in model_info:
                mmproj_filename = model_info["mmproj_file"]
                mmproj_path = self.model_dir / mmproj_filename
                if mmproj_path.exists():
                    print(f"[ModelManager] Removendo projetor associado: {mmproj_filename}")
                    try:
                        mmproj_path.unlink()
                    except Exception as e:
                        print(f"[ModelManager] Erro ao remover projetor: {e}")
            
            # Fallback: Se o nome segue o padrão MiniCPM, tentar achar mmproj similar
            if not model_info and "minicpm" in filename.lower():
                for p in self.model_dir.glob("mmproj-*.gguf"):
                    print(f"[ModelManager] Removendo possível projetor órfão: {p.name}")
                    p.unlink()

        return success


# Singleton
_model_manager: Optional[ModelManager] = None

def get_model_manager() -> ModelManager:
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
