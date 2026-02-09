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
    },
    {
        "id": "paddleocr-vl-1.5",
        "name": "PaddleOCR-VL 1.5",
        "repo": "nclssprt/PaddleOCR-VL-GGUF",
        "filename": "paddleocr-vl-0.9b.gguf",
        "size_gb": 0.94,
        "vram_required": 2,
        "description": "Modelo otimizado pela Baidu, mestre em extrair textos de documentos, tabelas e imagens complexas com precisão.",
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

    def discover_models(self) -> list[dict]:
        """Descobre modelos GGUF populares no Hugging Face compatíveis com o hardware."""
        system_ram = self.get_system_ram()
        # Margem de segurança mais dinâmica
        available_target = max(1.5, system_ram - (2.5 if system_ram > 8 else 1.5))
        
        print(f"[ModelManager] Buscando modelos GGUF (RAM disponível estimada: {available_target:.1f}GB)...")
        
        try:
            # Lista de modelos populares GGUF
            models = self._hf_api.list_models(
                filter=["gguf", "text-generation"],
                sort="downloads",
                limit=60 # Pegar margem para diversidade
            )
            
            discovered = []
            seen_families = set()
            
            # Autores preferidos (comunidade de quantização de alta qualidade)
            priority_authors = ["bartowski", "MaziyarPanahi", "mradermacher", "lmstudio-community", "QuantFactory", "LoneStriker"]
            
            for base_model in models:
                try:
                    # Evitar duplicar a mesma família de modelo (ex: não mostrar 5 variações do Qwen 2.5 7B)
                    # Heurística: extrair o nome base (ex: Qwen2.5-7B-Instruct)
                    model_id = base_model.modelId
                    family_parts = model_id.split("/")[-1].split("-")
                    # Pegar os primeiros 3-4 termos para identificar a família
                    family = "-".join(family_parts[:min(len(family_parts), 3)]).lower()
                    
                    if family in seen_families and len(discovered) < 8:
                        continue
                    
                    model = self._hf_api.model_info(model_id)
                    
                    # Pular modelos de visão por enquanto (conforme feedback do usuário)
                    if model.tags and ("vision" in model.tags or "clip" in model.tags or "multimodal" in model.tags):
                        continue
                    
                    if not model.siblings:
                         continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings:
                        continue
                        
                    # Tentar achar a melhor quantização
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), None)
                    if not best_quant:
                        best_quant = next((f for f in siblings if "Q4_0" in f), None)
                    if not best_quant:
                        best_quant = siblings[0]
                            
                    estimated_size, estimated_vram = self._estimate_specs(model_id, best_quant)

                    # Filtragem Hard HARDWARE
                    if estimated_vram > available_target and estimated_vram > 0:
                        continue

                    # Filtro de Qualidade: Ignorar modelos irrelevantes ou mal catalogados
                    if model.downloads < 100:
                        continue

                    # Bônus de Idioma/Qualidade
                    score_bonus = 1.0
                    tags_str = " ".join(model.tags) if model.tags else ""
                    if "pt" in tags_str or "portuguese" in tags_str.lower() or "multilingual" in tags_str.lower():
                        score_bonus *= 1.5
                    
                    author = model_id.split("/")[0]
                    if author in priority_authors:
                        score_bonus *= 1.3

                    # Recalcular score
                    age_days = (datetime.now(timezone.utc) - model.created_at).days
                    recency = max(7, age_days) # Pelo menos 1 semana para estabilizar
                    score = (model.downloads / recency) * score_bonus
                    
                    model_data = {
                        "id": model_id.replace("/", "__"),
                        "name": model_id.split("/")[-1],
                        "repo": model_id,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Downloads: {model.downloads:,}".replace(",", "."),
                        "downloads": model.downloads,
                        "score": score,
                        "url": f"https://huggingface.co/{model_id}",
                        "installed": (self.model_dir / best_quant).exists()
                    }
                    
                    self.model_cache[model_data["id"]] = model_data
                    discovered.append(model_data)
                    seen_families.add(family)
                    
                    if len(discovered) >= 15: # Pegar um pouco mais para ordenar final
                        break
                        
                except Exception:
                    continue

            discovered.sort(key=lambda x: x["score"], reverse=True)
            return discovered[:12] # Top 12 final
            
        except Exception as e:
            print(f"[ModelManager] Erro na descoberta: {e}")
            return []

    def discover_ocr_models(self) -> list[dict]:
        """Descobre modelos de visão/OCR compatíveis."""
        system_ram = self.get_system_ram()
        available_target = max(1.5, system_ram - 1.5)
        
        print(f"[ModelManager] Buscando modelos OCR (RAM disponível estimada: {available_target:.1f}GB)...")
        
        try:
            # Busca específica por visão e multimodais
            models = self._hf_api.list_models(
                filter=["gguf", "image-text-to-text"],
                sort="downloads",
                limit=40
            )
            
            discovered = []
            for base_model in models:
                try:
                    model_id = base_model.modelId
                    model = self._hf_api.model_info(model_id)
                    
                    # Verificar se é realmente de visão/multimodal
                    tags_str = " ".join(model.tags) if model.tags else ""
                    is_ocr = any(x in tags_str.lower() or x in model_id.lower() for x in ["ocr", "vision", "multimodal", "vl", "minicpm"])
                    
                    if not is_ocr or not model.siblings:
                        continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings: continue
                        
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), next((f for f in siblings if "Q4_0" in f), siblings[0]))
                    estimated_size, estimated_vram = self._estimate_specs(model_id, best_quant)

                    if estimated_vram > available_target:
                        continue

                    # Score baseado em downloads e relevância OCR
                    score_bonus = 1.0
                    if "ocr" in model_id.lower() or "ocr" in tags_str.lower():
                        score_bonus *= 2.0
                        
                    score = (model.downloads / 30) * score_bonus
                    
                    model_data = {
                        "id": model_id.replace("/", "__"),
                        "name": model_id.split("/")[-1],
                        "repo": model_id,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Downloads: {model.downloads:,} | OCR/Vision Model".replace(",", "."),
                        "downloads": model.downloads,
                        "score": score,
                        "url": f"https://huggingface.co/{model_id}",
                        "installed": (self.model_dir / best_quant).exists()
                    }
                    
                    self.model_cache[model_data["id"]] = model_data
                    discovered.append(model_data)
                    
                    if len(discovered) >= 10: break
                        
                except Exception:
                    continue

            # Adicionar modelos recomendados estáticos de visão
            for rm in RECOMMENDED_MODELS:
                if rm.get("is_vision") and not any(d["id"] == rm["id"] for d in discovered):
                    model_path = self.model_dir / rm["filename"]
                    rm["installed"] = model_path.exists()
                    rm["score"] = 999  # Garantir que fiquem no topo
                    discovered.append(rm)

            discovered.sort(key=lambda x: x.get("score", 0), reverse=True)
            return discovered
            
        except Exception as e:
            print(f"[ModelManager] Erro na descoberta OCR: {e}")
            return []

    def search_ocr_models(self, query: str) -> list[dict]:
        """Busca modelos de OCR específicos."""
        print(f"[ModelManager] Buscando OCR por '{query}'...")
        system_ram = self.get_system_ram()
        available_target = max(2.0, system_ram - 1.0)
        
        try:
            models = self._hf_api.list_models(
                search=query,
                filter=["gguf", "image-text-to-text"],
                sort="downloads",
                limit=30
            )
             
            results = []
            for base_model in models:
                try:
                    model = self._hf_api.model_info(base_model.modelId)
                    if not model.siblings: continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings: continue
                    
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), next((f for f in siblings if "Q4_0" in f), siblings[0]))
                    estimated_size, estimated_vram = self._estimate_specs(base_model.modelId, best_quant)

                    if estimated_vram > available_target: continue

                    results.append({
                        "id": base_model.modelId.replace("/", "__"),
                        "name": base_model.modelId.split("/")[-1],
                        "repo": base_model.modelId,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Downloads: {model.downloads:,} | Vision".replace(",", "."),
                        "downloads": model.downloads,
                        "url": f"https://huggingface.co/{base_model.modelId}",
                        "installed": (self.model_dir / best_quant).exists()
                    })
                    
                    self.model_cache[results[-1]["id"]] = results[-1]
                    if len(results) >= 8: break
                except Exception: continue
                
            return results
        except Exception as e:
            print(f"[ModelManager] Erro na busca OCR: {e}")
            return []

    def search_models(self, query: str) -> list[dict]:
        """Busca modelos específicos no HF, filtrando por hardware e qualidade."""
        print(f"[ModelManager] Buscando por '{query}'...")
        system_ram = self.get_system_ram()
        available_target = max(2.0, system_ram - 1.5)
        
        try:
            models = self._hf_api.list_models(
                search=query,
                filter=["gguf", "text-generation"],
                sort="downloads",
                limit=30
            )
             
            results = []
            for base_model in models:
                try:
                    model = self._hf_api.model_info(base_model.modelId)
                    
                    if not model.siblings:
                        continue

                    siblings = [f.rfilename for f in model.siblings if f.rfilename.endswith(".gguf")]
                    if not siblings: continue
                    
                    best_quant = next((f for f in siblings if "Q4_K_M" in f), 
                                    next((f for f in siblings if "Q4_0" in f), siblings[0]))
                    
                    estimated_size, estimated_vram = self._estimate_specs(model.modelId, best_quant)
                    
                    # Na busca manual, somos menos restritivos mas avisamos se não couber (escondendo apenas se for absurdo)
                    if estimated_vram > system_ram + 4: # Claramente impossível
                         continue

                    model_data = {
                        "id": model.modelId.replace("/", "__"),
                        "name": model.modelId.split("/")[-1],
                        "repo": model.modelId,
                        "filename": best_quant,
                        "size_gb": estimated_size,
                        "vram_required": estimated_vram,
                        "description": f"Downloads: {model.downloads:,}".replace(",", "."),
                        "downloads": model.downloads,
                        "url": f"https://huggingface.co/{model.modelId}"
                    }
                    
                    self.model_cache[model_data["id"]] = model_data
                    results.append(model_data)
                except Exception as e:
                    pass

            return results[:10]
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
        """Lista modelos instalados localmente com metadados completos."""
        models = []
        for gguf_file in self.model_dir.glob("*.gguf"):
            # Ignorar arquivos mmproj (projetores) da lista principal de modelos
            if gguf_file.name.startswith("mmproj-"):
                continue

            # Tentar encontrar info nos recomendados ou cache
            known = next(
                (m for m in RECOMMENDED_MODELS if m["filename"] == gguf_file.name),
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
