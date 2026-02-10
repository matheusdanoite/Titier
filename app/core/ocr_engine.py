"""
Titier - OCR Engine com PaddleOCR Nativo + ONNX High-Performance
Detecta automaticamente CUDA/Metal e configura inferência otimizada.
"""
import platform
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import os

PLATFORM = platform.system()
IS_MACOS = PLATFORM == "Darwin"
IS_WINDOWS = PLATFORM == "Windows"
IS_LINUX = PLATFORM == "Linux"


@dataclass
class OCRResult:
    """Resultado de OCR com coordenadas."""
    text: str
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float


class OCREngine:
    """
    Engine OCR usando PaddleOCR com inferência ONNX/Paddle otimizada.
    Detecta automaticamente o melhor backend disponível.
    """
    
    def __init__(self, use_gpu: bool = True, lang: str = "pt"):
        self.use_gpu = use_gpu
        self.lang = lang
        self._ocr = None
        self._backend = "cpu"
        self._initialized = False
        
    def _lazy_init(self):
        """Inicialização lazy para evitar import lento no startup."""
        if self._initialized:
            return
            
        print("[OCR] Inicializando PaddleOCR Engine...", flush=True)
        
        try:
            from paddleocr import PaddleOCR
            
            # Detectar GPU disponível
            use_gpu = self._detect_gpu() if self.use_gpu else False
            
            # Configurar PaddleOCR com ONNX para alta performance
            # Nota: use_onnx=True acelera em até 5x
            self._ocr = PaddleOCR(
                use_angle_cls=True,  # Detectar rotação de texto
                lang=self.lang,
                use_gpu=use_gpu,
                enable_mkldnn=not use_gpu,  # Intel MKL-DNN para CPU
                # ONNX High-Performance Mode
                use_onnx=True,
                # Otimizações
                det_db_score_mode="fast",  # Detecção rápida
                show_log=False,  # Silenciar logs do Paddle
            )
            
            self._backend = "cuda" if use_gpu else ("mkldnn" if not IS_MACOS else "cpu")
            print(f"[OCR] Backend: {self._backend.upper()}", flush=True)
            
        except ImportError as e:
            print(f"[OCR] PaddleOCR não instalado, usando RapidOCR fallback: {e}", flush=True)
            self._init_rapidocr_fallback()
        except Exception as e:
            print(f"[OCR] Erro ao inicializar PaddleOCR, usando fallback: {e}", flush=True)
            self._init_rapidocr_fallback()
            
        self._initialized = True
    
    def _init_rapidocr_fallback(self):
        """Fallback para RapidOCR se PaddleOCR falhar."""
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._ocr = RapidOCR()
            self._backend = "rapidocr-cpu"
            self._is_rapidocr = True
        except ImportError:
            raise RuntimeError("Nenhum engine OCR disponível. Instale paddleocr ou rapidocr-onnxruntime.")
    
    def _detect_gpu(self) -> bool:
        """Detecta se GPU está disponível para PaddlePaddle."""
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
        except Exception:
            return False
    
    @property
    def backend(self) -> str:
        """Retorna o backend em uso."""
        if not self._initialized:
            self._lazy_init()
        return self._backend
    
    @property
    def is_gpu_enabled(self) -> bool:
        """Verifica se GPU está ativa."""
        return "cuda" in self.backend.lower()
    
    def process_image(self, image_path: str) -> list[OCRResult]:
        """
        Processa imagem e retorna lista de resultados OCR.
        
        Args:
            image_path: Caminho para a imagem
            
        Returns:
            Lista de OCRResult com texto, bbox e confiança
        """
        if not self._initialized:
            self._lazy_init()
            
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        
        # Verifica se é RapidOCR (fallback)
        if hasattr(self, '_is_rapidocr') and self._is_rapidocr:
            return self._process_with_rapidocr(image_path)
        
        # PaddleOCR
        result = self._ocr.ocr(image_path, cls=True)
        
        if not result or not result[0]:
            return []
        
        ocr_results = []
        for line in result[0]:
            coords, (text, conf) = line
            
            # Converter coords [[x1,y1],[x2,y1],[x2,y2],[x1,y2]] para [x1,y1,x2,y2]
            x_coords = [p[0] for p in coords]
            y_coords = [p[1] for p in coords]
            bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
            
            ocr_results.append(OCRResult(
                text=text,
                bbox=bbox,
                confidence=conf
            ))
        
        return ocr_results
    
    def _process_with_rapidocr(self, image_path: str) -> list[OCRResult]:
        """Processa usando RapidOCR (fallback)."""
        result, _ = self._ocr(image_path)
        
        if not result:
            return []
        
        ocr_results = []
        for line in result:
            coords, text, conf = line
            x_coords = [p[0] for p in coords]
            y_coords = [p[1] for p in coords]
            bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
            
            ocr_results.append(OCRResult(
                text=text,
                bbox=bbox,
                confidence=conf
            ))
        
        return ocr_results
    
    def get_info(self) -> dict:
        """Retorna informações sobre a engine."""
        if not self._initialized:
            self._lazy_init()
            
        return {
            "engine": "paddleocr" if not hasattr(self, '_is_rapidocr') else "rapidocr",
            "backend": self._backend,
            "gpu_enabled": self.is_gpu_enabled,
            "language": self.lang
        }


# Singleton global
_ocr_engine: Optional[OCREngine] = None


def get_ocr_engine(use_gpu: bool = True, lang: str = "pt") -> OCREngine:
    """Retorna instância singleton do OCR Engine."""
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = OCREngine(use_gpu=use_gpu, lang=lang)
    return _ocr_engine


def reset_ocr_engine():
    """Reset do singleton (útil para testes)."""
    global _ocr_engine
    _ocr_engine = None
