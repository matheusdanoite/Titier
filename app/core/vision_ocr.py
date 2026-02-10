"""
Titier - Vision OCR Engine usando PaddleOCR-VL-1.5
Pipeline dedicado para OCR em PDFs escaneados via modelo de visão.
"""
import platform
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

PLATFORM = platform.system()
IS_MACOS = PLATFORM == "Darwin"


@dataclass
class VisionOCRResult:
    """Resultado do OCR com visão."""
    text: str
    markdown: str
    tables: list[str]
    page: int = 1


class VisionOCREngine:
    """
    OCR via PaddleOCR-VL-1.5 usando PaddlePaddle.
    Suporta parsing completo de documentos com tabelas, fórmulas e imagens.
    """
    
    def __init__(self):
        self._pipeline = None
        self._available = None
        
    def _check_availability(self) -> bool:
        """Verifica se PaddleOCR-VL está disponível."""
        if self._available is not None:
            return self._available
            
        try:
            from paddleocr import PaddleOCRVL
            self._available = True
        except ImportError:
            print("[VisionOCR] PaddleOCR-VL não disponível. Instale com: pip install paddleocr")
            self._available = False
        except Exception as e:
            print(f"[VisionOCR] Erro ao verificar disponibilidade: {e}")
            self._available = False
            
        return self._available
    
    @property
    def is_available(self) -> bool:
        """Retorna se o engine está disponível."""
        return self._check_availability()
        
    def _lazy_init(self):
        """Inicialização lazy do pipeline."""
        if self._pipeline is not None:
            return
            
        if not self._check_availability():
            raise RuntimeError("PaddleOCR-VL não está instalado")
            
        print("[VisionOCR] Inicializando PaddleOCR-VL-1.5...", flush=True)
        
        try:
            from paddleocr import PaddleOCRVL
            self._pipeline = PaddleOCRVL()
            print("[VisionOCR] Pipeline inicializado com sucesso!", flush=True)
        except Exception as e:
            print(f"[VisionOCR] Erro ao inicializar: {e}")
            raise
    
    def process_image(self, image_path: str) -> VisionOCRResult:
        """
        Processa uma imagem e extrai texto estruturado.
        
        Args:
            image_path: Caminho para a imagem
            
        Returns:
            VisionOCRResult com texto, markdown e tabelas
        """
        self._lazy_init()
        
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        
        try:
            output = self._pipeline.predict(image_path)
            
            # Processar resultados
            text_parts = []
            markdown_parts = []
            tables = []
            
            for res in output:
                # PaddleOCR-VL retorna diferentes formatos
                if hasattr(res, 'save_to_markdown'):
                    # Formato novo com markdown
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
                        res.save_to_markdown(save_path=Path(f.name).parent)
                        md_file = Path(f.name).parent / "result.md"
                        if md_file.exists():
                            markdown_parts.append(md_file.read_text())
                            md_file.unlink()
                
                # Extrair texto bruto
                if hasattr(res, 'rec_texts'):
                    text_parts.extend(res.rec_texts)
                elif hasattr(res, 'text'):
                    text_parts.append(res.text)
                    
                # Extrair tabelas se disponível
                if hasattr(res, 'tables'):
                    tables.extend(res.tables)
            
            return VisionOCRResult(
                text="\n".join(text_parts),
                markdown="\n\n".join(markdown_parts) if markdown_parts else "\n".join(text_parts),
                tables=tables
            )
            
        except Exception as e:
            print(f"[VisionOCR] Erro ao processar imagem: {e}")
            raise
    
    def process_page(self, pdf_path: str, page_num: int) -> VisionOCRResult:
        """
        Processa uma página específica de um PDF.
        
        Args:
            pdf_path: Caminho para o PDF
            page_num: Número da página (1-indexed)
            
        Returns:
            VisionOCRResult
        """
        import fitz  # PyMuPDF
        import tempfile
        
        doc = fitz.open(pdf_path)
        if page_num < 1 or page_num > len(doc):
            doc.close()
            raise ValueError(f"Página {page_num} inválida (PDF tem {len(doc)} páginas)")
        
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=150)
        
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            pix.save(f.name)
            temp_path = f.name
        
        doc.close()
        
        try:
            result = self.process_image(temp_path)
            result.page = page_num
            return result
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def get_info(self) -> dict:
        """Retorna informações sobre o engine."""
        return {
            "engine": "paddleocr-vl",
            "model": "PaddleOCR-VL-1.5",
            "available": self.is_available,
            "gpu_support": not IS_MACOS,  # PaddlePaddle não suporta Metal
        }


# Singleton global
_vision_ocr_engine: Optional[VisionOCREngine] = None


def get_vision_ocr_engine() -> VisionOCREngine:
    """Retorna instância singleton do Vision OCR Engine."""
    global _vision_ocr_engine
    if _vision_ocr_engine is None:
        _vision_ocr_engine = VisionOCREngine()
    return _vision_ocr_engine


def is_vision_ocr_available() -> bool:
    """Verifica se Vision OCR está disponível sem inicializar."""
    try:
        from paddleocr import PaddleOCRVL
        return True
    except ImportError:
        return False
