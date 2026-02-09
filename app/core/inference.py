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
    Detecta automaticamente o backend (Metal/CUDA/CPU).
    """
    
    DEFAULT_MODEL_DIR = Path.home() / ".titier" / "models"
    
    def __init__(
        self, 
        model_path: Optional[str] = None,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        verbose: bool = False
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers if n_gpu_layers != -1 else get_gpu_layers()
        self.verbose = verbose
        self.llm = None
        self._backend_info = get_backend_info()
        
    @property
    def backend(self) -> str:
        return self._backend_info["backend"]
    
    @property
    def is_gpu_enabled(self) -> bool:
        return self._backend_info["gpu_available"]
    
    def load(self, model_path: Optional[str] = None) -> "LLMEngine":
        """Carrega o modelo na memória/GPU."""
        from llama_cpp import Llama
        
        path = model_path or self.model_path
        if not path:
            raise ValueError("Model path não especificado")
        
        if not Path(path).exists():
            raise FileNotFoundError(f"Modelo não encontrado: {path}")
        
        print(f"[LLM] Carregando modelo: {Path(path).name}")
        print(f"[LLM] Backend: {self.backend.upper()}, GPU Layers: {self.n_gpu_layers}")
        
        self.llm = Llama(
            model_path=str(path),
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            verbose=self.verbose,
            # Chat format será detectado automaticamente
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
        
        print(f"[Vision] Carregando modelo multimodal: {Path(path).name}")
        print(f"[Vision] Backend: {self.backend.upper()}")
        
        # Tentar carregar o chat handler para MiniCPM-V
        try:
            from llama_cpp.llama_chat_format import MiniCPMv26ChatHandler
            import sys
            
            # Se mmproj_path não for fornecido, tentar usar o próprio modelo (embedded projector)
            clip_path = self.mmproj_path
            if not clip_path or not Path(clip_path).exists():
                clip_path = path
            
            print(f"[Vision] Usando clip_path: {Path(clip_path).name}", flush=True)
            self.chat_handler = MiniCPMv26ChatHandler(
                clip_model_path=str(clip_path)
            )
        except ImportError:
            print("[Vision] Chat handler não disponível (ImportError), usando modo básico", flush=True)
        except Exception as e:
            print(f"[Vision] Erro ao inicializar chat handler: {e}", flush=True)
        
        # Só definir chat_format se tivermos o handler, caso contrário o llama-cpp vai reclamar
        chat_format = "minicpm-v-2.6" if self.chat_handler else None
        
        self.llm = Llama(
            model_path=str(path),
            n_ctx=self.n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            chat_format=chat_format,
            chat_handler=self.chat_handler,
            verbose=self.verbose
        )
        
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
        
        system_prompt = "Você é um assistente de visão computacional. Responda sempre em JSON válido." if json_schema else None
        
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
