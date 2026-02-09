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
from core.model_manager import get_model_manager, RECOMMENDED_MODELS, DownloadStatus
from db.vector_store import VectorStore
from core.pdf_processor import PDFProcessor, HybridPDFProcessor

# === App Setup ===
app = FastAPI(
    title="Titier Backend",
    version="0.2.0",
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
    """Carrega o modelo de visão (MiniCPM) sob demanda."""
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
    global _pdf_processor
    
    if use_vision:
        vision_model = get_vision_model()
        if vision_model:
            print("[Server] Instanciando HybridPDFProcessor com Vision AI")
            return HybridPDFProcessor(vision_engine=vision_model)
    
    # Processador padrão (leve, sem estado de modelo)
    return PDFProcessor()


# === Models ===
class ChatRequest(BaseModel):
    message: str
    use_rag: bool = True
    max_tokens: int = 512
    source_filter: Optional[str] = None  # Filtrar por nome do arquivo
    search_mode: str = "local"  # "local" (documento atual) ou "global" (todos)


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
        "version": "0.2.0",
        "docs": "/docs"
    }


@app.get("/status")
async def status():
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
                
                results = vs.search(
                    request.message, 
                    limit=5,
                    source_filter=filter_source
                )
                sources = results
                context = "\n\n".join([r["text"] for r in results])
        except Exception as e:
            print(f"[Chat] Erro no RAG: {e}")
    
    # Construir prompt
    if context:
        prompt = f"""Baseado no seguinte contexto dos documentos:

{context}

Responda a pergunta do usuário de forma clara e precisa:

Pergunta: {request.message}

Resposta:"""
    else:
        prompt = f"""Você é Titier, um assistente de estudos inteligente.
Responda de forma clara e útil:

Pergunta: {request.message}

Resposta:"""
    
    # Gerar resposta
    llm = get_chat_model()
    if llm:
        try:
            response_text = llm.generate(
                prompt=prompt,
                max_tokens=request.max_tokens,
                temperature=0.7
            )
            model_used = Path(llm.model_path).name if llm.model_path else None
        except Exception as e:
            response_text = f"Erro ao gerar resposta: {str(e)}"
            model_used = None
    else:
        # Fallback sem modelo
        if context:
            response_text = f"[Sem modelo LLM] Encontrei informações relevantes nos documentos:\n\n{context[:500]}..."
        else:
            response_text = f"[Sem modelo LLM] Echo: {request.message}\n\nPara respostas com IA, baixe um modelo de Chat (Llama 3.2, etc)."
        model_used = None
    
    return ChatResponse(
        response=response_text.strip(),
        sources=[{"text": s["text"][:200], "page": s.get("page")} for s in sources],
        model_used=model_used
    )


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
    temp_processor = PDFProcessor()
    has_images = temp_processor.has_images(str(file_path))
    
    # Passo 3: Processamento Condicional
    chunks = []
    try:
        if has_images:
            print(f"[Upload] Imagens detectadas em {file.filename}. Iniciando pipeline de Visão...")
            # Carregar Vision Model (unload chat se necessário)
            vision_processor = get_pdf_processor(use_vision=True)
            chunks = vision_processor.process(str(file_path))
            
            # Offload Vision Model para economizar recursos
            print("[Upload] Processamento visual concluído. Liberando modelo de visão...")
            unload_models()
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
    """Lista modelos recomendados com status."""
    manager = get_model_manager()
    return manager.get_recommended_models()


@app.post("/models/download/{model_id}")
async def download_model(model_id: str, background_tasks: BackgroundTasks):
    """Inicia download de um modelo do HuggingFace."""
    manager = get_model_manager()
    model = manager.get_model_by_id(model_id)
    
    if not model:
        raise HTTPException(404, f"Modelo '{model_id}' não encontrado")
    
    # Verificar se já existe
    model_path = manager.model_dir / model["filename"]
    if model_path.exists():
        return {
            "status": "already_installed",
            "message": f"Modelo {model['name']} já está instalado",
            "path": str(model_path)
        }
    
    # Iniciar download em background (sync wrapper)
    def do_download():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.download_model(model_id))
        finally:
            loop.close()
    
    background_tasks.add_task(do_download)
    
    return {
        "status": "started",
        "message": f"Download de {model['name']} iniciado",
        "model_id": model_id,
        "size_gb": model["size_gb"]
    }


@app.get("/models/download/{model_id}/status")
async def get_download_status(model_id: str):
    """Verifica status do download."""
    manager = get_model_manager()
    progress = manager.get_download_progress(model_id)
    
    if not progress:
        # Verificar se modelo existe
        model = manager.get_model_by_id(model_id)
        if model:
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
    
    installed_models = manager.get_installed_models()
    has_model = len(installed_models) > 0
    
    # Verificar se embeddings estão carregados
    embeddings_ready = False
    try:
        vs = get_vector_store()
        embeddings_ready = vs.encoder is not None
        stats = vs.get_stats()
        has_documents = stats.get("points_count", 0) > 0
    except:
        has_documents = False
    
    steps = [
        {
            "id": "gpu",
            "title": "Aceleração GPU",
            "completed": backend_info["gpu_available"],
            "description": f"Backend: {backend_info['backend'].upper()}"
        },
        {
            "id": "model",
            "title": "Modelo de IA",
            "completed": has_model,
            "description": installed_models[0]["name"] if has_model else "Nenhum modelo instalado"
        },
        {
            "id": "embeddings",
            "title": "Modelo de Embeddings",
            "completed": embeddings_ready,
            "description": "bge-m3 pronto" if embeddings_ready else "Não inicializado (2.3 GB)"
        },
        {
            "id": "documents",
            "title": "Documentos",
            "completed": has_documents,
            "description": f"{stats.get('points_count', 0)} chunks indexados" if has_documents else "Nenhum PDF carregado"
        }
    ]
    
    all_completed = all(s["completed"] for s in steps)
    
    return {
        "completed": all_completed,
        "steps": steps,
        "ready_to_chat": has_model and embeddings_ready
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
    
    return {"status": "started", "message": "Inicializando modelo de embeddings (2.3 GB)"}


@app.get("/onboarding/init-embeddings/status")
async def get_embeddings_init_status():
    """Retorna status da inicialização dos embeddings."""
    vs = get_vector_store()
    
    # Checar se já está carregado
    if vs.encoder is not None:
        return {"status": "completed", "progress": 100, "error": None}
    
    return _init_status["embeddings"]


# === Server Entry ===
if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
