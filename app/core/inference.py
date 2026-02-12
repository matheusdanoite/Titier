"""
Titier - Motor de Inferência Cross-Platform
Suporta Metal (macOS) e CUDA (Windows/Linux)
"""
import os
import sys
import platform
from pathlib import Path
from typing import AsyncGenerator, Optional
import base64

# Detectar plataforma para configuração adequada
PLATFORM = platform.system()
IS_MACOS = PLATFORM == "Darwin"
IS_WINDOWS = PLATFORM == "Windows"
IS_LINUX = PLATFORM == "Linux"


def get_gpu_layers() -> int:
    """
    Retorna o número de layers para GPU baseado na plataforma.
    -1 = todas as layers na GPU (recomendado se tiver VRAM suficiente)
    """
    if IS_MACOS:
        # Metal no Apple Silicon - usar todas as layers
        return -1
    elif IS_WINDOWS or IS_LINUX:
        # CUDA - usar todas as layers (ajustar se OOM)
        return -1
    return 0  # CPU fallback


def get_backend_info() -> dict:
    """Retorna informações sobre o backend de aceleração disponível."""
    info = {
        "platform": PLATFORM,
        "backend": "cpu",
        "gpu_available": False
    }
    
    try:
        from llama_cpp import llama_supports_gpu_offload
        if llama_supports_gpu_offload():
            info["gpu_available"] = True
            info["backend"] = "metal" if IS_MACOS else "cuda"
    except ImportError:
        pass
    
    return info


class LLMEngine:
    """
    Motor de inferência usando llama-cpp-python.
    Detecta automaticamente o backend (Metal/CUDA/CPU) e otimiza parâmetros.
    """
    
    DEFAULT_MODEL_DIR = Path.home() / ".titier" / "models"
    
    _lock = None # Lock compartilhado para evitar múltiplas inferências simultâneas

    def __init__(
        self, 
        model_path: Optional[str] = None,
        n_ctx: Optional[int] = None,  # Auto-detectado se None
        n_gpu_layers: Optional[int] = None,  # Auto-detectado se None
        n_batch: Optional[int] = None,
        n_threads: Optional[int] = None,
        use_mmap: Optional[bool] = None,
        use_mlock: Optional[bool] = None,
        flash_attn: Optional[bool] = None,
        verbose: bool = False
    ):
        from .hardware import detect_hardware_profile, print_hardware_summary
        
        self.model_path = model_path
        self.verbose = verbose
        self.llm = None
        self._backend_info = get_backend_info()

        # Inicializar lock se ainda não existir
        import asyncio
        if LLMEngine._lock is None:
            LLMEngine._lock = asyncio.Lock()
        
        # Detectar perfil de hardware otimizado
        self._hw_profile = detect_hardware_profile(model_path)
        
        # Usar valores do perfil ou override manual
        self.n_ctx = n_ctx or self._hw_profile.n_ctx
        self.n_gpu_layers = n_gpu_layers if n_gpu_layers is not None else self._hw_profile.n_gpu_layers
        self.n_batch = n_batch or self._hw_profile.n_batch
        self.n_threads = n_threads or self._hw_profile.n_threads
        self.n_threads_batch = self._hw_profile.n_threads_batch
        self.use_mmap = use_mmap if use_mmap is not None else self._hw_profile.use_mmap
        self.use_mlock = use_mlock if use_mlock is not None else self._hw_profile.use_mlock
        self.flash_attn = flash_attn if flash_attn is not None else self._hw_profile.flash_attn
        self.offload_kqv = self._hw_profile.offload_kqv
        self.type_k = self._hw_profile.type_k
        self.type_v = self._hw_profile.type_v
        self.mul_mat_q = self._hw_profile.mul_mat_q
        
        # Log do perfil detectado
        if verbose:
            print_hardware_summary(self._hw_profile)
        
    @property
    def hardware_profile(self):
        """Retorna o perfil de hardware detectado."""
        return self._hw_profile
        
    @property
    def backend(self) -> str:
        return self._backend_info["backend"]
    
    @property
    def is_gpu_enabled(self) -> bool:
        return self._backend_info["gpu_available"]
    
    def load(self, model_path: Optional[str] = None) -> "LLMEngine":
        """Carrega o modelo na memória/GPU com parâmetros otimizados."""
        from llama_cpp import Llama
        from .hardware import get_ggml_type, detect_hardware_profile
        
        path = model_path or self.model_path
        if not path:
            raise ValueError("Model path não especificado")
        
        if not Path(path).exists():
            raise FileNotFoundError(f"Modelo não encontrado: {path}")
        
        # Recalcular perfil para o modelo específico se diferente
        if path != self.model_path:
            self._hw_profile = detect_hardware_profile(path)
            self.n_gpu_layers = self._hw_profile.n_gpu_layers
            self.n_ctx = self._hw_profile.n_ctx
        
        print(f"[LLM] Carregando modelo: {Path(path).name}")
        print(f"[LLM] Backend: {self.backend.upper()}, Tier: {self._hw_profile.tier.value.upper()}")
        print(f"[LLM] GPU Layers: {self.n_gpu_layers}, n_ctx: {self.n_ctx}, n_batch: {self.n_batch}")
        print(f"[LLM] Threads: {self.n_threads}, Flash Attn: {self.flash_attn}, KV Type: {self.type_k or 'F16'}")
        
        # Preparar argumentos opcionais
        llama_kwargs = {
            "model_path": str(path),
            "n_ctx": self.n_ctx,
            "n_gpu_layers": self.n_gpu_layers,
            "n_batch": self.n_batch,
            "n_threads": self.n_threads,
            "n_threads_batch": self.n_threads_batch,
            "use_mmap": self.use_mmap,
            "use_mlock": self.use_mlock,
            "mul_mat_q": self.mul_mat_q,
            "offload_kqv": self.offload_kqv,
            "verbose": self.verbose,
        }
        
        # Flash Attention (pode não estar disponível em todas as builds)
        if self.flash_attn:
            llama_kwargs["flash_attn"] = True
        
        # KV cache quantization (se disponível)
        type_k = get_ggml_type(self.type_k)
        type_v = get_ggml_type(self.type_v)
        if type_k is not None:
            llama_kwargs["type_k"] = type_k
        if type_v is not None:
            llama_kwargs["type_v"] = type_v
        
        try:
            self.llm = Llama(**llama_kwargs)
        except TypeError as e:
            # Fallback se algum parâmetro não for suportado
            print(f"[LLM] Aviso: Parâmetro não suportado, usando fallback: {e}")
            self.llm = Llama(
                model_path=str(path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_batch=self.n_batch,
                n_threads=self.n_threads,
                verbose=self.verbose,
            )
        
        print(f"[LLM] Modelo carregado com sucesso!")
        return self
    
    def generate(
        self, 
        prompt: str, 
        max_tokens: int = 512,
        temperature: float = 0.7,
        stop: Optional[list] = None
    ) -> str:
        """Gera resposta de forma síncrona."""
        if not self.llm:
            raise RuntimeError("Modelo não carregado. Chame load() primeiro.")
        
        # Síncrono não suporta lock assíncrono facilmente sem bloquear o loop
        # Como o app é assíncrono, vamos usar o lock via run_in_executor ou similar se necessário
        # Mas para simplicidade e segurança nas rotas async do FastAPI, vamos focar nos métodos async
        response = self.llm.create_completion(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or ["</s>", "\n\n"]
        )
        
        return response["choices"][0]["text"]
    
    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """Chat completion com histórico de mensagens."""
        if not self.llm:
            raise RuntimeError("Modelo não carregado. Chame load() primeiro.")
        
        response = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response["choices"][0]["message"]["content"]

    async def chat_async(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> str:
        """Chat completion assíncrono com lock."""
        if not self.llm:
            raise RuntimeError("Modelo não carregado. Chame load() primeiro.")
        
        import asyncio
        async with self._lock:
            # create_chat_completion do llama-cpp-python é bloqueante, 
            # mas o lock evita concorrência.
            response = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        
        return response["choices"][0]["message"]["content"]
    
    async def stream(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Streaming de tokens assíncrono."""
        if not self.llm:
            raise RuntimeError("Modelo não carregado. Chame load() primeiro.")
        
        for chunk in self.llm.create_completion(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        ):
            text = chunk["choices"][0]["text"]
            if text:
                yield text
    
    async def chat_stream(
        self,
        messages: list[dict],
        max_tokens: int = 512,
        temperature: float = 0.7,
        abort_check = None
    ) -> AsyncGenerator[str, None]:
        """Chat completion com streaming e contagem robusta de tokens."""
        if not self.llm:
            raise RuntimeError("Modelo não carregado. Chame load() primeiro.")
        
        # 1. Contagem robusta de tokens usando o chat handler ou template
        try:
            # Tentar formatar o chat primeiro para contar tokens reais com tags
            formatted_chat = self.llm.chat_handler.apply_chat_template(messages) if hasattr(self.llm, 'chat_handler') and self.llm.chat_handler else str(messages)
            prompt_tokens = len(self.llm.tokenize(formatted_chat.encode("utf-8")))
        except Exception as e:
            print(f"[LLM] Erro na tokenização precisa: {e}. Usando estimativa.")
            prompt_tokens = len(str(messages)) // 3 # Estimativa conservadora (3 chars per token)
        
        n_ctx = self.llm.n_ctx()
        print(f"[LLM] Contexto Max: {n_ctx}, Prompt Real: {prompt_tokens}")

        # Buffer de segurança maior (200 tokens) para evitar limite físico do KV cache
        available_tokens = n_ctx - prompt_tokens - 200 
        
        if available_tokens < 50:
            print("[LLM] Erro: Contexto insuficiente")
            yield "⚠️ **Erro de Contexto**: O texto pesquisado nos documentos é muito grande para o limite de memória da IA atual. Tente fazer uma pergunta mais específica ou reduzir o número de documentos selecionados."
            return

        final_max_tokens = min(max_tokens, available_tokens)
        print(f"[LLM] Tokens disponíveis para geração: {available_tokens}, Limitando a: {final_max_tokens}")
        
        print("[LLM] Iniciando geração...")
        try:
            import asyncio
            async with self._lock:
                for chunk in self.llm.create_chat_completion(
                    messages=messages,
                    max_tokens=final_max_tokens,
                    temperature=temperature,
                    stream=True
                ):
                    if abort_check and abort_check():
                        break
                    
                    if "content" in chunk["choices"][0]["delta"]:
                        token = chunk["choices"][0]["delta"]["content"]
                        yield token
                    
                    # Permitir que outras corrotinas rodem (ex: /chat/stop)
                    await asyncio.sleep(0)
            
            print("[LLM] Geração finalizada com sucesso.")
        except RuntimeError as e:
            if "-3" in str(e) or "llama_decode" in str(e):
                print(f"[LLM] Erro crítico de decodificação capturado: {e}")
                yield "\n\n⚠️ **Limite de Memória Atingido**: A IA não conseguiu completar a resposta porque o limite de contexto foi excedido durante a fala. Tente uma pergunta que exija menos contexto do documento."
            else:
                raise e
    
    def unload(self):
        """Libera o modelo da memória."""
        if self.llm:
            del self.llm
            self.llm = None


class MultimodalEngine(LLMEngine):
    """
    Motor para modelos multimodais como MiniCPM-V 2.6.
    Suporta entrada de imagens.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        mmproj_path: Optional[str] = None,
        **kwargs
    ):
        super().__init__(model_path, **kwargs)
        self.mmproj_path = mmproj_path
        self.chat_handler = None
    
    def load(self, model_path: Optional[str] = None) -> "MultimodalEngine":
        """Carrega modelo multimodal com handler de visão."""
        from llama_cpp import Llama
        
        path = model_path or self.model_path
        if not path:
            raise ValueError("Model path não especificado")
        
        if not Path(path).exists():
            raise FileNotFoundError(f"Modelo não encontrado: {path}")
        
        model_name = Path(path).name.lower()
        print(f"[Vision] Carregando modelo multimodal: {Path(path).name}")
        print(f"[Vision] Backend: {self.backend.upper()}")
        
        # Detectar tipo de modelo e configurar handler apropriado
        chat_format = None
        self.chat_handler = None
        
        # MiniCPM-V requer handler especial
        if "minicpm" in model_name:
            try:
                from llama_cpp.llama_chat_format import MiniCPMv26ChatHandler
                
                clip_path = self.mmproj_path
                if not clip_path or not Path(clip_path).exists():
                    clip_path = path
                
                print(f"[Vision] Usando MiniCPM handler com clip_path: {Path(clip_path).name}", flush=True)
                self.chat_handler = MiniCPMv26ChatHandler(
                    clip_model_path=str(clip_path)
                )
                chat_format = "minicpm-v-2.6"
            except ImportError:
                print("[Vision] MiniCPM handler não disponível", flush=True)
            except Exception as e:
                print(f"[Vision] Erro ao inicializar MiniCPM handler: {e}", flush=True)
        
        # PaddleOCR-VL e outros modelos de visão usam modo básico
        elif "paddleocr" in model_name or "ocr" in model_name:
            print("[Vision] Modelo OCR detectado - usando modo básico (sem chat handler)", flush=True)
            # PaddleOCR-VL não precisa de handler especial, funciona com completion básico
            chat_format = None
        
        # Outros modelos de visão genéricos
        else:
            print("[Vision] Modelo de visão genérico - tentando modo básico", flush=True)
        
        print(f"[Vision] Tier: {self._hw_profile.tier.value.upper()}, GPU Layers: {self.n_gpu_layers}, n_ctx: {self.n_ctx}")
        
        # Usar parâmetros otimizados do hardware profile
        try:
            self.llm = Llama(
                model_path=str(path),
                n_ctx=self.n_ctx,
                n_gpu_layers=self.n_gpu_layers,
                n_batch=self.n_batch,
                n_threads=self.n_threads,
                use_mmap=self.use_mmap,
                chat_format=chat_format,
                chat_handler=self.chat_handler,
                verbose=self.verbose
            )
        except Exception as e:
            print(f"[Vision] Erro ao carregar com parâmetros otimizados: {e}")
            # Fallback mais simples
            try:
                self.llm = Llama(
                    model_path=str(path),
                    n_ctx=4096,  # Contexto menor para modelos OCR
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=self.verbose
                )
            except Exception as e2:
                raise RuntimeError(f"Falha ao carregar modelo de visão: {e2}")
        
        print(f"[Vision] Modelo carregado com sucesso!")
        return self
    
    def analyze_image(
        self,
        image_path: str,
        prompt: str = "Descreva esta imagem em detalhes.",
        max_tokens: int = 1024,
        json_schema: Optional[dict] = None
    ) -> str:
        """Analisa uma imagem e retorna descrição textual ou JSON estruturado."""
        if not self.llm:
            raise RuntimeError("Modelo não carregado.")
        
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        
        # Codificar imagem em base64
        with open(image_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")
        
        # Determinar tipo MIME
        ext = Path(image_path).suffix.lower()
        mime_types = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".gif": "gif"}
        mime = mime_types.get(ext, "jpeg")
        
        from .prompts import get_prompts
        system_prompt = get_prompts()["system_vision"] if json_schema else None
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
            
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{mime};base64,{base64_image}"}
                }
            ]
        })
        
        # Configurar response_format se schema for fornecido
        response_format = None
        if json_schema:
            response_format = {
                "type": "json_object",
                "schema": json_schema
            }
        
        try:
            response = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                response_format=response_format,
                temperature=0.1 if json_schema else 0.7  # Menor temperatura para JSON
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[Vision] Erro na inferência: {e}")
            return "{}" if json_schema else f"Erro ao analisar imagem: {e}"


# Utilitário para verificação de instalação
def check_installation():
    """Verifica se llama-cpp-python está instalado corretamente."""
    info = get_backend_info()
    
    print("=" * 50)
    print("Titier - Verificação de Instalação")
    print("=" * 50)
    print(f"Plataforma: {info['platform']}")
    print(f"Backend: {info['backend'].upper()}")
    print(f"GPU Disponível: {'✅ Sim' if info['gpu_available'] else '❌ Não'}")
    
    if not info['gpu_available']:
        print("\n⚠️  Instalação sem aceleração GPU detectada!")
        if IS_MACOS:
            print("   Reinstale com: CMAKE_ARGS='-DGGML_METAL=on' pip install llama-cpp-python --force-reinstall")
        elif IS_WINDOWS:
            print("   Reinstale com: CMAKE_ARGS='-DGGML_CUDA=on' pip install llama-cpp-python --force-reinstall")
    
    print("=" * 50)
    return info


if __name__ == "__main__":
    check_installation()
