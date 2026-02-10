"""
Titier Backend Server
FastAPI server com RAG usando LlamaIndex-like pipeline
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional
import uvicorn
import os
import shutil
import asyncio

# Local imports
# Local imports
from core.inference import LLMEngine, MultimodalEngine, get_backend_info
from core.prompts import get_prompts, save_prompts, reset_prompts, get_defaults
from core.model_manager import get_model_manager, RECOMMENDED_MODELS, DownloadStatus
from db.vector_store import VectorStore
from core.pdf_processor import PDFProcessor, HybridPDFProcessor

# === App Setup ===
app = FastAPI(
    title="Titier Backend",
    version="0.5.0",
    description="Backend do assistente de estudos com IA local e RAG"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Global State ===
# Lazy loading - inicializado sob demanda
_chat_model: Optional[LLMEngine] = None
_vision_model: Optional[MultimodalEngine] = None
_vector_store: Optional[VectorStore] = None
_pdf_processor: Optional[PDFProcessor] = None

# Paths
UPLOAD_DIR = Path.home() / ".titier" / "uploads"
MODEL_DIR = Path.home() / ".titier" / "models"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def unload_models():
    """Descarrega todos os modelos da memória."""
    global _chat_model, _vision_model
    
    if _chat_model:
        print("[Server] Descarregando Chat Model...")
        _chat_model.unload()
        _chat_model = None
        
    if _vision_model:
        print("[Server] Descarregando Vision Model...")
        _vision_model.unload()
        _vision_model = None


def get_chat_model() -> Optional[LLMEngine]:
    """Carrega o modelo de chat (Llama 3.2, etc)."""
    global _chat_model, _vision_model
    
    if _chat_model is None:
        # Se vision model estiver carregado, descarregar para garantir VRAM
        if _vision_model:
            print("[Server] Trocando modelo: Vision -> Chat")
            _vision_model.unload()
            _vision_model = None
            
        manager = get_model_manager()
        model_path = manager.get_chat_model_path()
        
        if model_path:
            print(f"[Server] Carregando Chat Model: {model_path.name}")
            _chat_model = LLMEngine(model_path=str(model_path))
            _chat_model.load()
    
    return _chat_model


def get_vision_model() -> Optional[MultimodalEngine]:
    """Carrega o modelo de visão sob demanda (configurável)."""
    global _vision_model, _chat_model
    
    if _vision_model is None:
        # Se chat model estiver carregado, descarregar
        if _chat_model:
            print("[Server] Trocando modelo: Chat -> Vision")
            _chat_model.unload()
            _chat_model = None
            
        manager = get_model_manager()
        model_info = manager.get_vision_model_path()
        
        if model_info:
            # Suporte para retorno dict (novo padrão) ou Path (legado)
            if isinstance(model_info, dict):
                model_path = model_info["model_path"]
                mmproj_path = model_info.get("mmproj_path")
            else:
                model_path = model_info
                mmproj_path = None
                
            print(f"[Server] Carregando Vision Model: {model_path.name}")
            if mmproj_path:
                print(f"[Server] Projetor multimodal: {mmproj_path.name}")
                
            _vision_model = MultimodalEngine(
                model_path=str(model_path),
                mmproj_path=str(mmproj_path) if mmproj_path else None
            )
            _vision_model.load()
            
    return _vision_model




def get_vector_store() -> VectorStore:
    """Lazy loading do Vector Store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
        _vector_store.connect()
    return _vector_store


def get_pdf_processor(use_vision: bool = False) -> PDFProcessor:
    """Retorna processor adequado."""
    from core.hardware import detect_hardware_profile
    hw = detect_hardware_profile()
    chunk_args = {
        "chunk_size": hw.recommended_chunk_size,
        "chunk_overlap": hw.recommended_chunk_overlap
    }
    
    if use_vision:
        vision_model = get_vision_model()
        
        # Obter VisionOCR Engine dedicado (PaddleOCR-VL-1.5)
        from core.vision_ocr import get_vision_ocr_engine, is_vision_ocr_available
        vision_ocr = get_vision_ocr_engine() if is_vision_ocr_available() else None
        
        print(f"[Server] Instanciando HybridPDFProcessor (Vision AI: {'Sim' if vision_model else 'Não'}, Vision OCR: {'Sim' if vision_ocr else 'Não'}, Chunk: {chunk_args['chunk_size']})")
        return HybridPDFProcessor(vision_engine=vision_model, vision_ocr=vision_ocr, **chunk_args)
    
    # Processador padrão (leve, sem estado de modelo)
    return PDFProcessor(**chunk_args)


# === Models ===
class ChatRequest(BaseModel):
    message: str
    use_rag: bool = True
    max_tokens: int = 4096
    source_filter: Optional[str] = None  # Filtrar por nome do arquivo
    search_mode: str = "local"  # "local" (documento atual) ou "global" (todos)
    rag_chunks: Optional[int] = None  # Override manual do n_chunks
    highlight_only: Optional[bool] = None
    color_filter: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    sources: list = []
    model_used: Optional[str] = None


class UploadResponse(BaseModel):
    filename: str
    chunks_added: int
    message: str


# === Routes ===
@app.get("/health")
async def health_check():
    """Verifica status do backend."""
    backend_info = get_backend_info()
    
    # Verificar modelo
    manager = get_model_manager()
    has_chat = manager.get_chat_model_path() is not None
    model_available = has_chat
    
    # Verificar vector store
    try:
        vs = get_vector_store()
        stats = vs.get_stats()
        documents_count = stats.get("points_count", 0)
    except:
        documents_count = 0
    
    return {
        "status": "ok",
        "message": "Backend rodando!",
        "backend": backend_info["backend"],
        "gpu_available": backend_info["gpu_available"],
        "model_available": model_available,
        "documents_indexed": documents_count
    }




@app.get("/")
async def root():
    """Info da API."""
    return {
        "app": "Titier PDF AI",
        "version": "0.5.0",
        "docs": "/docs"
    }


@app.get("/models/ocr/recommended")
async def get_recommended_ocr_models():
    """Retorna modelos OCR recomendados."""
    manager = get_model_manager()
    return manager.discover_ocr_models()





@app.get("/ocr/status")
async def get_ocr_status():
    """Retorna status do engine OCR (PaddleOCR/RapidOCR)."""
    from core.ocr_engine import get_ocr_engine
    ocr = get_ocr_engine()
    return ocr.get_info()


@app.get("/ocr/vision/status")
async def get_vision_ocr_status():
    """Retorna status do VisionOCR (PaddleOCR-VL-1.5)."""
    from core.vision_ocr import get_vision_ocr_engine
    engine = get_vision_ocr_engine()
    return engine.get_info()


@app.get("/status")
async def get_status():
    """Status detalhado do sistema."""
    backend_info = get_backend_info()
    
    # Listar modelos disponíveis
    models = [f.name for f in MODEL_DIR.glob("*.gguf")]
    
    # Stats do vector store
    try:
        vs = get_vector_store()
        vs_stats = vs.get_stats()
    except:
        vs_stats = {"error": "Não conectado"}
    
    return {
        "platform": backend_info["platform"],
        "backend": backend_info["backend"],
        "gpu_available": backend_info["gpu_available"],
        "models": models,
        "model_dir": str(MODEL_DIR),
        "vector_store": vs_stats,
        "uploads_dir": str(UPLOAD_DIR)
    }


@app.get("/api/hardware")
async def get_hardware_info():
    """Retorna informações detalhadas do hardware e configurações otimizadas."""
    from core.hardware import detect_hardware_profile, get_recommended_models
    
    profile = detect_hardware_profile()
    
    return {
        "tier": profile.tier.value,
        "ram": {
            "total_gb": profile.ram_total_gb,
            "available_gb": profile.ram_available_gb
        },
        "vram": {
            "total_gb": profile.vram_total_gb,
            "available_gb": profile.vram_available_gb
        },
        "cpu_cores": {
            "physical": profile.cpu_cores_physical,
            "logical": profile.cpu_cores_logical
        },
        "backend": profile.backend,
        "gpu_name": profile.gpu_name,
        "config": {
            "n_ctx": profile.n_ctx,
            "n_batch": profile.n_batch,
            "n_gpu_layers": profile.n_gpu_layers,
            "n_threads": profile.n_threads,
            "n_threads_batch": profile.n_threads_batch,
            "flash_attn": profile.flash_attn,
            "kv_cache_type": profile.type_k or "F16",
            "use_mmap": profile.use_mmap,
            "use_mlock": profile.use_mlock,
            "offload_kqv": profile.offload_kqv
        },
        "max_tokens_default": profile.max_tokens_default,
        "recommended_models": get_recommended_models(profile.tier)
    }


def _get_dynamic_rag_limit(request: ChatRequest, model: Optional[LLMEngine]) -> int:
    """Calcula o limite de chunks baseado no modelo e no override do usuário."""
    if request.rag_chunks is not None:
        return request.rag_chunks
        
    # Default conservador
    limit = 3
    
    # Se estiver pedindo destaque, aumentamos o limite para pegar mais contexto colorido
    is_asking_highlights = any(kw in request.message.lower() for kw in ["grifado", "destaque", "marcado", "grifo"])
    if is_asking_highlights:
        limit = 15
    
    # Se modelo carregado, ajustar por n_ctx
    if model and hasattr(model, "n_ctx"):
        n_ctx = model.n_ctx
        if n_ctx <= 2048:
            limit = max(limit, 2)
        elif n_ctx <= 4096:
            limit = max(limit, 5)
        elif n_ctx <= 8192:
            limit = max(limit, 10)
        elif n_ctx > 8192:
            limit = max(limit, 20) # Permitir muito mais para modelos modernos (Llama 3.1/3.2, etc)
            
    return limit


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint principal de chat.
    Usa RAG se documentos estiverem indexados.
    """
    sources = []
    context = ""
    
    # Buscar contexto no vector store se RAG habilitado
    if request.use_rag:
        try:
            vs = get_vector_store()
            stats = vs.get_stats()
            
            if stats.get("points_count", 0) > 0:
                # Aplicar filtro se modo local e source_filter definido
                filter_source = None
                if request.search_mode == "local" and request.source_filter:
                    filter_source = request.source_filter
                
                # Limite dinâmico
                limit = _get_dynamic_rag_limit(request, get_chat_model())
                
                # Detectar intenção de destaques/cores
                msg_lower = request.message.lower()
                h_only = request.highlight_only or False
                c_filter = request.color_filter
                if h_only is False:
                    if any(kw in msg_lower for kw in ["grifado", "destaque", "marcado", "grifo"]):
                        h_only = True
                if c_filter is None:
                    cores = ["amarelo", "verde", "azul", "vermelho", "rosa", "laranja", "cinza"]
                    for cor in cores:
                        if cor in msg_lower:
                            c_filter = cor
                            h_only = True
                            break

                results = vs.search(
                    request.message, 
                    limit=limit,
                    source_filter=filter_source,
                    highlight_only=h_only,
                    color_filter=c_filter
                )
                sources = results
                context = "\n\n".join([r["text"] for r in results])
        except Exception as e:
            print(f"[Chat] Erro no RAG: {e}")
    
    # Construir prompt usando prompts centralizados
    prompts = get_prompts()
    if context:
        system_content = prompts["system_rag"].format(context=context)
    else:
        system_content = prompts["system_base"]
    
    # Gerar resposta
    if not _chat_model:
        # Tentar carregar se não estiver
        get_chat_model()
        
    if _chat_model:
        response_text = _chat_model.chat(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": request.message}
            ],
            max_tokens=request.max_tokens
        )
        return {
            "response": response_text,
            "sources": sources,
            "model_used": _chat_model.model_path
        }
    
    raise HTTPException(status_code=503, detail="Modelo de chat não disponível")


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Endpoint de chat com streaming.
    Retorna Server-Sent Events (SSE).
    """
    sources = []
    context = ""
    
    # 1. Recuperar contexto RAG (igual ao endpoint normal)
    if request.use_rag:
        try:
            vs = get_vector_store()
            stats = vs.get_stats()
            
            if stats.get("points_count", 0) > 0:
                filter_source = None
                if request.search_mode == "local" and request.source_filter:
                    filter_source = request.source_filter
                    print(f"[Chat] Filtrando por fonte: {filter_source}")
                
                # Definir limite dinâmico de chunks
                llm = get_chat_model()
                rag_limit = _get_dynamic_rag_limit(request, llm)
                
                # Detectar intenção de destaques/cores
                msg_lower = request.message.lower()
                h_only = request.highlight_only or False
                c_filter = request.color_filter
                if h_only is False:
                    if any(kw in msg_lower for kw in ["grifado", "destaque", "marcado", "grifo"]):
                        h_only = True
                if c_filter is None:
                    cores = ["amarelo", "verde", "azul", "vermelho", "rosa", "laranja", "cinza"]
                    for cor in cores:
                        if cor in msg_lower:
                            c_filter = cor
                            h_only = True
                            break

                print(f"[Chat] Limite de RAG dinâmico: {rag_limit} (n_ctx: {llm.n_ctx if llm else 'N/A'}, H_Only: {h_only}, Color: {c_filter})")
                results = vs.search(
                    request.message, 
                    limit=rag_limit, 
                    source_filter=filter_source,
                    highlight_only=h_only,
                    color_filter=c_filter
                )
                print(f"[Chat] Resultados encontrados: {len(results)}")
                
                sources = results
                context = "\n\n".join([r["text"] for r in results])
                print(f"[Chat] Tamanho do contexto: {len(context)} caracteres")
        except Exception as e:
            print(f"[Chat] Erro no RAG: {e}")

    # 2. Construir prompt usando prompts centralizados
    prompts = get_prompts()
    if context:
        system_prompt = prompts["system_rag"].format(context=context)
    else:
        system_prompt = prompts["system_base"]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.message}
    ]

    # 3. Gerador assíncrono para streaming
    async def event_generator():
        # Enviar fontes primeiro como evento JSON especial
        if sources:
            import json
            yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"
        
        model = get_chat_model()
        if not model:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Modelo não carregado'})}\n\n"
            return

        async for token in model.chat_stream(messages, max_tokens=request.max_tokens):
            # Enviar cada token
            # Formato SSE: data: <conteudo>\n\n
            if token:
                # Escape newlines for SSE data payload if needed, but simple replacement works for most clients
                # Or just send JSON for safety
                import json
                payload = json.dumps({"type": "token", "content": token})
                yield f"data: {payload}\n\n"
        
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload e indexação de PDF.
    Verifica se o documento já foi indexado para evitar duplicação.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos PDF são aceitos")
    
    # Salvar arquivo
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Calcular hash do arquivo
    vs = get_vector_store()
    file_hash = vs.compute_file_hash(str(file_path))
    
    # Passo 1 (Workflow): Verificar Hash
    if vs.is_document_indexed(file_hash):
        print(f"[Upload] Documento {file.filename} já indexado.")
        
        # Carregar modelo de chat para interação imediata
        print("[Upload] Preparando modelo de chat...")
        get_chat_model()
        
        return UploadResponse(
            filename=file.filename,
            chunks_added=0,
            message="Documento já indexado. Chat pronto!"
        )
    
    # Passo 2: Analisar conteúdo (Scan)
    temp_processor = get_pdf_processor(use_vision=False)
    has_images = temp_processor.has_images(str(file_path))
    
    # Passo 3: Processamento Condicional
    chunks = []
    try:
        if has_images:
            print(f"[Upload] Imagens detectadas em {file.filename}. Iniciando pipeline de Visão...")
            try:
                # Carregar Vision Model (unload chat se necessário)
                vision_processor = get_pdf_processor(use_vision=True)
                chunks = vision_processor.process(str(file_path))
                
                # Offload Vision Model para economizar recursos
                print("[Upload] Processamento visual concluído. Liberando modelo de visão...")
                unload_models()
            except Exception as vision_error:
                print(f"[Upload] Modelo de visão falhou ({vision_error}). Usando OCR fallback...")
                # Fallback: usar HybridPDFProcessor com VisionOCR ou RapidOCR
                ocr_processor = get_pdf_processor(use_vision=True) # Vai tentar vision_ocr internally
                chunks = ocr_processor.process(str(file_path))
                print("[Upload] Fallback OCR: Texto extraído via OCR Engine.")
        else:
            print(f"[Upload] Apenas texto detectado em {file.filename}. Usando pipeline padrão...")
            chunks = temp_processor.process(str(file_path))
            
    except Exception as e:
        print(f"[Upload] Erro no processamento: {e}")
        raise HTTPException(500, f"Erro ao processar PDF: {str(e)}")
    
    if not chunks:
        raise HTTPException(400, "Não foi possível extrair texto ou imagens do PDF")
    
    # Passo 4: Indexação
    texts, metadata = temp_processor.to_documents(chunks)
    for m in metadata:
        m["file_hash"] = file_hash
    
    count = vs.add_documents(texts, metadata)
    
    # Passo 5: Estado Final (Carregar Chat)
    print("[Upload] Indexação concluída. Carregando modelo de chat...")
    get_chat_model()
    
    return UploadResponse(
        filename=file.filename,
        chunks_added=count,
        message=f"PDF processado ({'Visual' if has_images else 'Texto'}) e indexado! Chat pronto."
    )


@app.get("/documents")
async def list_documents():
    """Lista documentos indexados com informações detalhadas."""
    try:
        print("DEBUG: Listando documentos...")
        vs = get_vector_store()
        stats = vs.get_stats()
        indexed_docs = vs.get_indexed_documents()
        print(f"DEBUG: Stats recuperados: {stats}")
        print(f"DEBUG: Docs indexados recuperados: {len(indexed_docs)} docs")
        
        # Listar PDFs na pasta de uploads
        pdfs = [f.name for f in UPLOAD_DIR.glob("*.pdf")]
        
        return {
            "total_chunks": stats.get("points_count", 0),
            "documents_count": len(indexed_docs),
            "uploaded_files": pdfs,
            "indexed_documents": indexed_docs
        }
    except Exception as e:
        print(f"ERRO ao listar documentos: {e}")
        return {"error": str(e)}


@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Remove um documento específico do índice e do disco."""
    try:
        print(f"DEBUG: Tentando deletar documento: {filename}")
        vs = get_vector_store()
        
        # Encontrar hash do documento pelo nome
        indexed_docs = vs.get_indexed_documents()
        doc = next((d for d in indexed_docs if d["source"] == filename), None)
        
        if not doc:
            print(f"DEBUG: Documento {filename} não encontrado no índice.")
            raise HTTPException(404, f"Documento '{filename}' não encontrado no índice")
        
        # Remover do vector store
        print(f"DEBUG: Removendo hash {doc['file_hash']} do VectorStore...")
        removed_count = vs.delete_document(doc["file_hash"])
        print(f"DEBUG: Removidos {removed_count} pontos do VectorStore.")
        
        # Remover arquivo do disco se existir
        file_path = UPLOAD_DIR / filename
        if file_path.exists():
            file_path.unlink()
            print(f"DEBUG: Arquivo {filename} deletado do disco.")
        else:
            print(f"DEBUG: Arquivo {filename} não encontrado no disco.")
        
        return {
            "message": f"Documento '{filename}' removido",
            "chunks_removed": removed_count
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERRO ao deletar documento: {e}")
        raise HTTPException(500, str(e))


@app.delete("/documents")
async def clear_documents():
    """Limpa todos os documentos indexados."""
    try:
        print("DEBUG: Iniciando limpeza completa do banco de dados...")
        vs = get_vector_store()
        vs.clear()
        
        # Limpar arquivos da pasta de uploads
        print("DEBUG: Limpando arquivos da pasta uploads...")
        for file in UPLOAD_DIR.glob("*.pdf"):
            file.unlink()
        print("DEBUG: Limpeza concluída.")
        
        return {"message": "Banco de dados e arquivos limpos com sucesso"}
    except Exception as e:
        print(f"ERRO ao limpar banco de dados: {e}")
        return {"error": str(e)}


# === Model Management Routes ===
@app.get("/models")
async def list_models():
    """Lista modelos disponíveis e instalados."""
    manager = get_model_manager()
    return {
        "recommended": manager.get_recommended_models(),
        "installed": manager.get_installed_models()
    }


@app.get("/models/recommended")
async def get_recommended_models():
    """Lista modelos recomendados (agora via descoberta dinâmica)."""
    manager = get_model_manager()
    # Retornar lista estática
    return manager.get_recommended_models()


class ImportModelRequest(BaseModel):
    path: str

@app.post("/models/import")
async def import_model(request: ImportModelRequest):
    """Importa um modelo local .gguf"""
    manager = get_model_manager()
    try:
        # Executar em thread/background pois pode envolver cópia de arquivo grande
        return await asyncio.to_thread(manager.import_model, request.path)
    except FileNotFoundError:
        raise HTTPException(404, "Arquivo não encontrado")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Erro ao importar: {e}")


@app.post("/models/download/{model_id}")
async def download_model(model_id: str, background_tasks: BackgroundTasks):
    """Inicia download de um modelo do HuggingFace."""
    manager = get_model_manager()
    model = manager.get_model_by_id(model_id)
    
    if not model:
        raise HTTPException(404, f"Modelo '{model_id}' não encontrado")
    
    # Modelos PaddleOCR usam PaddleHub, não GGUF
    if model.get("uses_paddleocr"):
        return {
            "status": "paddleocr_model",
            "message": f"PaddleOCR-VL é instalado automaticamente via pip, não requer download manual. Use: pip install paddleocr[doc-parser]",
            "installed": True
        }
    
    # Verificar se já existe
    model_path = manager.model_dir / model["filename"]
    if model_path.exists():
        return {
            "status": "already_installed",
            "message": f"Modelo {model['name']} já está instalado",
            "path": str(model_path)
        }
    
    # Iniciar download em background
    async def do_download_async():
        print(f"[Server] Iniciando tarefa de download para: {model_id}")
        try:
            await manager.download_model(model_id)
            print(f"[Server] Tarefa de download concluída: {model_id}")
        except Exception as e:
            print(f"[Server] Erro na tarefa de download {model_id}: {e}")
    
    background_tasks.add_task(do_download_async)
    
    return {
        "status": "started",
        "message": f"Download de {model['name']} iniciado",
        "model_id": model_id,
        "size_gb": model["size_gb"]
    }


@app.get("/models/download/status")
async def get_all_download_status():
    """Retorna status de todos os downloads ativos."""
    manager = get_model_manager()
    downloads = manager.get_all_downloads()
    
    return [
        {
            "model_id": d.model_id,
            "status": d.status.value,
            "progress": d.progress,
            "downloaded_mb": round(d.downloaded_bytes / (1024**2), 1),
            "total_mb": round(d.total_bytes / (1024**2), 1),
            "speed_mbps": d.speed_mbps,
            "error": d.error
        }
        for d in downloads
    ]


@app.get("/models/download/{model_id}/status")
async def get_download_status(model_id: str):
    """Verifica status do download."""
    manager = get_model_manager()
    progress = manager.get_download_progress(model_id)
    
    if not progress:
        # Verificar se modelo existe
        model = manager.get_model_by_id(model_id)
        if model:
            # Modelos PaddleOCR já estão instalados via pip
            if model.get("uses_paddleocr"):
                return {
                    "status": "completed",
                    "progress": 100,
                    "message": "PaddleOCR-VL instalado via pip"
                }
            model_path = manager.model_dir / model["filename"]
            if model_path.exists():
                return {
                    "status": "completed",
                    "progress": 100,
                    "message": "Modelo instalado"
                }
        return {"status": "not_started", "progress": 0}
    
    return {
        "status": progress.status.value,
        "progress": progress.progress,
        "downloaded_mb": round(progress.downloaded_bytes / (1024**2), 1),
        "total_mb": round(progress.total_bytes / (1024**2), 1),
        "speed_mbps": progress.speed_mbps,
        "error": progress.error
    }


@app.delete("/models/{filename}")
async def delete_model(filename: str):
    """Remove um modelo instalado."""
    manager = get_model_manager()
    
    if manager.delete_model(filename):
        # Resetar modelos se removidos
        global _chat_model, _vision_model
        if _chat_model and filename in str(_chat_model.model_path):
            _chat_model = None
        if _vision_model and filename in str(_vision_model.model_path):
            _vision_model = None
            
        return {"message": f"Modelo {filename} removido"}
    
    raise HTTPException(404, "Modelo não encontrado")


# === Onboarding Routes ===
@app.get("/onboarding/status")
async def get_onboarding_status():
    """Retorna status do setup inicial."""
    backend_info = get_backend_info()
    manager = get_model_manager()
    
    # Identificar recomendação ideal baseada no hardware atual
    tier = backend_info.get("tier", "medium")
    is_mac = backend_info.get("platform") == "Darwin"
    
    # Lógica de recomendação:
    # 8GB Mac -> 3B Model
    # 16GB+ Mac ou GPU 8GB -> 8B Model
    # Outros -> 3B Model (segurança)
    
    recommended_model_id = "llama-3.2-3b-q4" # Default seguro
    if is_mac:
        if backend_info.get("ram_total", 0) >= 16:
            recommended_model_id = "llama-3.1-8b-q5"
        else:
            recommended_model_id = "llama-3.2-3b-q4"
    elif backend_info.get("gpu_available") and backend_info.get("vram_total", 0) >= 7:
        recommended_model_id = "llama-3.1-8b-q5"
        
    recommended_llm = manager.get_model_by_id(recommended_model_id)
    
    # Atualizar flags de recomendação na lista estática para o frontend
    all_recommendations = manager.get_recommended_models()
    for m in all_recommendations:
        m["recommended"] = (m["id"] == recommended_model_id)
        
    # Verificar modelos instalados
    installed_models = manager.get_installed_models()
    has_llm = len(installed_models) > 0
    has_ocr = any(
        "ocr" in m["name"].lower() or 
        "vision" in m["name"].lower() or 
        "minicpm" in m["name"].lower() or
        "vl" in m["name"].lower()
        for m in installed_models
    )
    
    # Verificar se embeddings estão carregados
    embeddings_ready = False
    try:
        vs = get_vector_store()
        embeddings_ready = vs.encoder is not None
    except:
        pass
    
    steps = [
        {
            "id": "llm",
            "title": "Modelo de IA",
            "completed": has_llm,
            "description": "Pronto" if has_llm else "Pendente"
        },
        {
            "id": "ocr",
            "title": "Modelo de Visão (OCR)",
            "completed": has_ocr,
            "description": "Pronto" if has_ocr else "Pendente"
        },
        {
            "id": "embeddings",
            "title": "Busca Inteligente",
            "completed": embeddings_ready,
            "description": "Pronto" if embeddings_ready else "Não inicializado"
        }
    ]
    
    return {
        "steps": steps,
        "gpu": backend_info.get("gpu_name") or backend_info.get("backend"),
        "tier": backend_info.get("tier"),
        "ready_to_chat": has_llm and has_ocr and embeddings_ready,
        "recommended_llm": recommended_llm,
        "all_recommendations": all_recommendations
    }


# Estado global para inicialização
_init_status = {"embeddings": {"status": "idle", "progress": 0, "error": None}}


@app.post("/onboarding/init-embeddings")
async def init_embeddings(background_tasks: BackgroundTasks):
    """Pré-carrega o modelo de embeddings bge-m3."""
    global _init_status
    
    vs = get_vector_store()
    
    # Já inicializado?
    if vs.encoder is not None:
        return {"status": "already_initialized", "message": "Embeddings já carregado"}
    
    # Já inicializando?
    if _init_status["embeddings"]["status"] == "loading":
        return {"status": "loading", "message": "Inicialização em andamento"}
    
    _init_status["embeddings"] = {"status": "loading", "progress": 0, "error": None}
    
    def do_init():
        global _init_status
        try:
            _init_status["embeddings"]["progress"] = 10
            vs._get_encoder()  # Força o carregamento
            _init_status["embeddings"] = {"status": "completed", "progress": 100, "error": None}
        except Exception as e:
            _init_status["embeddings"] = {"status": "failed", "progress": 0, "error": str(e)}
    
    background_tasks.add_task(do_init)
    
    return {"status": "started", "message": "Inicializando modelo de embeddings leve (420 MB)"}


@app.get("/onboarding/init-embeddings/status")
async def get_embeddings_init_status():
    """Retorna status da inicialização dos embeddings."""
    vs = get_vector_store()
    
    # Checar se já está carregado
    if vs.encoder is not None:
        return {"status": "completed", "progress": 100, "error": None}
    
    return _init_status["embeddings"]


# === Prompt Management Routes ===
class PromptsUpdateRequest(BaseModel):
    system_base: Optional[str] = None
    system_rag: Optional[str] = None
    system_vision: Optional[str] = None


@app.get("/prompts")
async def get_system_prompts():
    """Retorna os prompts ativos e os padrões."""
    return {
        "active": get_prompts(),
        "defaults": get_defaults()
    }


@app.put("/prompts")
async def update_system_prompts(request: PromptsUpdateRequest):
    """Salva prompts customizados."""
    data = {}
    if request.system_base:
        data["system_base"] = request.system_base
    if request.system_rag:
        if "{context}" not in request.system_rag:
            raise HTTPException(400, "O prompt RAG deve conter o placeholder {context}")
        data["system_rag"] = request.system_rag
    if request.system_vision:
        data["system_vision"] = request.system_vision

    if not data:
        raise HTTPException(400, "Nenhum prompt fornecido")

    save_prompts(data)
    return {"message": "Prompts salvos com sucesso", "active": get_prompts()}


@app.delete("/prompts")
async def reset_system_prompts():
    """Restaura prompts para os valores padrão."""
    reset_prompts()
    return {"message": "Prompts restaurados para os padrões", "active": get_prompts()}


def main():
    """Ponto de entrada para o Poetry."""
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )

# === Server Entry ===
if __name__ == "__main__":
    main()
