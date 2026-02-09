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
        "id": "llama-3.1-8b",
        "name": "Llama 3.1 8B Instruct",
        "repo": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "size_gb": 4.9,
        "vram_required": 8, # Ajustado para margem de segurança
        "description": "Modelo equilibrado para chat e RAG",
    },
    {
        "id": "llama-3.2-3b",
        "name": "Llama 3.2 3B Instruct",
        "repo": "lmstudio-community/Llama-3.2-3B-Instruct-GGUF",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "size_gb": 2.0,
        "vram_required": 4,
        "description": "Modelo leve, ideal para hardware modesto",
    },
    {
        "id": "phi-3-mini",
        "name": "Phi-3 Mini 4K",
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "filename": "Phi-3-mini-4k-instruct-q4.gguf",
        "size_gb": 2.2,
        "vram_required": 4,
        "description": "Modelo compacto da Microsoft, muito eficiente",
    },
    {
        "id": "mistral-7b",
        "name": "Mistral 7B Instruct",
        "repo": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        "filename": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "size_gb": 4.4,
        "vram_required": 8,
        "description": "Excelente para tarefas de raciocínio",
    },
    {
        "id": "qwen2-7b",
        "name": "Qwen2 7B Instruct",
        "repo": "Qwen/Qwen2-7B-Instruct-GGUF",
        "filename": "qwen2-7b-instruct-q4_k_m.gguf",
        "size_gb": 4.4,
        "vram_required": 8,
        "description": "Modelo multilíngue com bom suporte a português",
    },
    {
        "id": "minicpm-v-2.6",
        "name": "MiniCPM-V 2.6 (Vision)",
        "repo": "openbmb/MiniCPM-V-2_6-gguf",
        "filename": "ggml-model-Q4_K_M.gguf",
        "mmproj_file": "mmproj-model-f16.gguf",
        "size_gb": 4.7,
        "vram_required": 8,
        "description": "Modelo multimodal para OCR e análise de imagens",
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
        self.hf_token = os.getenv("HF_TOKEN")
        self._hf_api = HfApi(token=self.hf_token)
        
        # Cache para modelos descobertos dinamicamente
        # Chave: model_id (com __), Valor: dict do modelo
        self.model_cache = {}

    def _estimate_specs(self, model_id: str, filename: str) -> tuple[float, float]:
        """Estima tamanho e VRAM baseada no nome/ID do modelo."""
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
                    elif "gemma" in text: params = 2 # gemma padrão é 2b ou 7b, assumir menor
                    elif "qwen" in text: params = 7
                    elif "phi" in text: params = 3
                    elif "glm" in text: params = 9 # GLM-4 costuma ser 9B
                    elif "stories" in text: params = 0.1 # muito pequeno
                    else: return 0.0, 0.0

            # Tentar extrair bits da quantização (ex: Q4, Q5, Q8, F16)
            fname = filename.lower()
            if "q4" in fname: bits = 4.5
            elif "q5" in fname: bits = 5.5
            elif "q6" in fname: bits = 6.5
            elif "q8" in fname: bits = 8.5
            elif "f16" in fname: bits = 16
            elif "f32" in fname: bits = 32
            elif "iq" in fname: bits = 4 # i-quants (ex: IQ4_XS) costumam ser < 4 bits reais, assumir 4
            else: bits = 5 # fallback seguro
            
            # Tamanho do arquivo em GB = (Params * Bits) / 8
            size_gb = (params * bits) / 8
            
            # VRAM = Tamanho + Contexto (estimativa conservadora +20%)
            vram_gb = size_gb * 1.2
            
            return round(size_gb, 1), round(vram_gb, 1)
            
        except Exception:
            return 0.0, 0.0

    def search_models(self, query: str) -> list[dict]:
        """Busca modelos específicos no HF, filtrando por hardware."""
        print(f"[ModelManager] Buscando por '{query}'...")
        system_ram = self.get_system_ram()
        # Permitir usar até 80-90% da RAM para não travar o sistema
        # Mas sendo conservador: RAM Total - 2GB (OS)
        max_usable_ram = max(2.0, system_ram - 2.0)
        
        try:
             models = self._hf_api.list_models(
                search=query,
                filter="gguf",
                sort="downloads",
                limit=50 # Buscar mais para poder filtrar
            )
             
             results = []
             for base_model in models:
                try:
                    # Fetch details for siblings
                    model = self._hf_api.model_info(base_model.modelId)
                    
                    if not model.siblings:
                        continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings: continue
                    
                    # Priorizar Q4_K_M -> Q4_0 -> Qualquer um
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), 
                                    next((f for f in siblings if "Q4_0" in f), siblings[0]))
                    
                    estimated_size, estimated_vram = self._estimate_specs(model.modelId, best_quant)
                    
                    # FILTRAGEM DE HARDWARE
                    # Se não conseguimos estimar (0.0), mostramos por precaução (ou escondemos?)
                    # O usuário pediu para excluir os que excedem.
                    # Vamos excluir apenas se tivermos uma estimativa alta confiável > max_usable_ram
                    # Se for 0.0 (desconhecido), deixamos passar com m aviso visual (frontend lida ou mostra 0)
                    if estimated_vram > max_usable_ram:
                         continue
                    
                    results.append({
                        "id": model.modelId.replace("/", "__"),
                        "name": model.modelId.split("/")[-1],
                        "repo": model.modelId,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Resultado da busca - {model.downloads} downloads",
                        "downloads": model.downloads,
                        "url": f"https://huggingface.co/{model.modelId}"
                    })
                except Exception as e:
                    print(f"Error searching {base_model.modelId}: {e}")
                    pass

                
             return results[:10] # Retornar top 10 filtrados
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []
    def discover_models(self) -> list[dict]:
        """Descobre modelos GGUF populares no Hugging Face compatíveis com o hardware."""
        system_ram = self.get_system_ram()
        available_target = max(2, system_ram - 2)
        
        print(f"[ModelManager] Buscando modelos GGUF populares (RAM alvo: {available_target:.1f}GB)...")
        
        try:
            # Reduzir limite pois faremos chamadas n+1
            models = self._hf_api.list_models(
                filter=["gguf", "text-generation"],
                sort="downloads",
                limit=50
            )
            
            discovered = []
            
            for base_model in models:
                try:
                    # Precisamos de detalhes para ver os arquivos (siblings)
                    # Isso adiciona latência, mas é necessário
                    model = self._hf_api.model_info(base_model.modelId)
                    
                    # Pular modelos de visão por enquanto (foco em chat)
                    if model.tags and ("vision" in model.tags or "clip" in model.tags):
                        continue
                    
                    # Análise rápida do repo para achar arquivos GGUF
                    if not model.siblings:
                         continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings:
                        continue
                        
                    # Tentar achar a melhor quantização (Q4_K_M é o sweet spot)
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), None)
                    if not best_quant:
                        best_quant = next((f for f in siblings if "Q4_0" in f), None)
                    if not best_quant:
                        best_quant = siblings[0] # Fallback
                        
                    # Estimar tamanho (aproximado pelo nome ou metadados se possível)
                    # Como list_models não retorna tamanho do arquivo, teríamos que fazer uma request extra
                    # Para otimizar, vamos assumir que modelos < 10B params cabem se quantizados
                    # Uma verificação real exigiria list_repo_tree o que é lento para muitos modelos
                    
                    # Filtro heurístico pelo nome
                    name_lower = model.modelId.lower()
                            
                    estimated_size, estimated_vram = self._estimate_specs(model.modelId, best_quant)

                    # Filtragem Hard HARDWARE: Se soubermos que não cabe, não mostrar.
                    if estimated_vram > available_target:
                        continue

                    # Filtro de Qualidade: Ignorar modelos muito pequenos (< 3GB RAM) para casos de uso sérios
                    if estimated_vram < 3.0:
                        continue

                    model_data = {
                        "id": model.modelId.replace("/", "__"),
                        "name": model.modelId.split("/")[-1],
                        "repo": model.modelId,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Downloads: {model.downloads}",
                        "downloads": model.downloads,
                        "createdAt": model.created_at,
                        "url": f"https://huggingface.co/{model.modelId}"
                    }
                    
                    self.model_cache[model_data["id"]] = model_data
                    discovered.append(model_data)
                    
                    if len(discovered) >= 12:
                        break
                        
                except Exception:
                    continue

            
            # Recalcular score para ordenar melhor
            # Usar a mesma lógica de recência
            for d in discovered:
                 # Injetar dados simulados para nossa formula de score
                 age_days = (datetime.now(timezone.utc) - d["createdAt"]).days
                 recency = max(1, age_days + 30)
                 score = (d["downloads"] * 2) / recency # Simplificado sem likes
                 d["score"] = score
                 
            discovered.sort(key=lambda x: x["score"], reverse=True)
            
            # Marcar o top 1 como recomendado (REMOVIDO a pedido do usuário)
            # if discovered:
            #     discovered[0]["recommended"] = True
            #     discovered[0]["recommendation_reason"] = "Tendência no Hugging Face e compatível com seu perfil."
            
            return discovered
            
        except Exception as e:
            print(f"[ModelManager] Erro na descoberta: {e}")
            return []

    def search_models(self, query: str) -> list[dict]:
        """Busca modelos específicos no HF."""
        print(f"[ModelManager] Buscando por '{query}'...")
        try:
            models = self._hf_api.list_models(
                search=query,
                filter=["gguf", "text-generation"],
                sort="downloads",
                limit=50 # Buscar mais para poder filtrar
            )
             
            results = []
            for base_model in models:
                try:
                    # Fetch details for siblings
                    model = self._hf_api.model_info(base_model.modelId)
                    
                    if not model.siblings:
                        continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings: continue
                    
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), next((f for f in siblings if "Q4_0" in f), siblings[0]))
                    
                    estimated_size, estimated_vram = self._estimate_specs(model.modelId, best_quant)
                    
                    # Filtro de Qualidade: Ignorar modelos muito pequenos (< 3GB RAM) para casos de uso sérios
                    if estimated_vram < 3.0:
                        continue

                    model_data = {
                        "id": model.modelId.replace("/", "__"),
                        "name": model.modelId.split("/")[-1],
                        "repo": model.modelId,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Downloads: {model.downloads}",
                        "downloads": model.downloads,
                        "url": f"https://huggingface.co/{model.modelId}"
                    }
                    
                    self.model_cache[model_data["id"]] = model_data
                    results.append(model_data)
                except Exception as e:
                    print(f"Error searching {base_model.modelId}: {e}")
                    pass

            return results
        except Exception as e:
            print(f"Erro na busca: {e}")
            return []

    def get_recommended_models(self) -> list[dict]:
        """Retorna descoberta dinâmica ou fallback para estáticos se falhar."""
        try:
            discovered = self.discover_models()
            if discovered:
                # Adicionar status de instalado
                for model in discovered:
                    # Checar se qualquer arquivo desse repo existe
                    model["installed"] = False
                    for f in self.model_dir.glob("*.gguf"):
                        # Heurística simples
                        if model["name"] in f.name: 
                            model["installed"] = True
                            model["local_path"] = str(f)
                return discovered
        except Exception as e:
            print(f"Erro no discovery, usando fallback: {e}")
            
        # Fallback para o comportamento antigo (usando RECOMMENDED_MODELS estático se necessário, 
        # mas idealmente queremos o dinâmico)
        return []

    # Mantendo compatibilidade com métodos antigos
    
    def get_system_ram(self) -> float:
        """Retorna RAM total do sistema em GB."""
        return psutil.virtual_memory().total / (1024**3)

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
        """Busca modelo por ID (no cache dinâmico ou estáticos)."""
        # 1. Verificar cache dinâmico
        if model_id in self.model_cache:
            return self.model_cache[model_id]
            
        # 2. Verificar lista estática (legado)
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
