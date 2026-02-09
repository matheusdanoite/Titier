"""
Titier - Processador de PDF
Extração híbrida: PyMuPDF (texto) + Vision Model (imagens/OCR)
"""
from pathlib import Path
from typing import Generator, Optional
from dataclasses import dataclass
import fitz  # PyMuPDF


@dataclass
class PDFChunk:
    """Representa um chunk de texto extraído do PDF."""
    text: str
    source: str
    page: int
    chunk_id: int
    has_images: bool = False
    bbox: Optional[list[float]] = None  # [x1, y1, x2, y2] relativo à página


class PDFProcessor:
    """
    Processador de PDF com chunking inteligente.
    Usa PyMuPDF para extração rápida de texto.
    """
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_length: int = 50
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length
    
    def extract_text(self, pdf_path: str) -> tuple[str, list[int]]:
        """
        Extrai texto de todas as páginas do PDF.
        Retorna (texto_completo, páginas_com_imagens).
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")
        
        doc = fitz.open(str(path))
        full_text = []
        pages_with_images = []
        
        for page_num, page in enumerate(doc):
            # Extrair texto
            text = page.get_text()
            full_text.append(text)
            
            # Verificar se tem imagens
            if page.get_images():
                pages_with_images.append(page_num + 1)
        
        doc.close()
        return "\n\n".join(full_text), pages_with_images

    def has_images(self, pdf_path: str) -> bool:
        """Verificação rápida se o PDF contém imagens."""
        doc = fitz.open(pdf_path)
        for page in doc:
            if page.get_images():
                doc.close()
                return True
        doc.close()
        return False
    
    def extract_pages(self, pdf_path: str) -> Generator[dict, None, None]:
        """Extrai texto página por página com metadados."""
        path = Path(pdf_path)
        doc = fitz.open(str(path))
        
        for page_num, page in enumerate(doc):
            yield {
                "page": page_num + 1,
                "text": page.get_text(),
                "has_images": len(page.get_images()) > 0,
                "image_count": len(page.get_images())
            }
        
        doc.close()
    
    def chunk_text(self, text: str) -> Generator[str, None, None]:
        """
        Divide texto em chunks com overlap.
        Usa separação por palavras para manter contexto.
        """
        words = text.split()
        
        if len(words) <= self.chunk_size:
            if len(text.strip()) >= self.min_chunk_length:
                yield text.strip()
            return
        
        start = 0
        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk = " ".join(chunk_words)
            
            if len(chunk.strip()) >= self.min_chunk_length:
                yield chunk.strip()
            
            start = end - self.chunk_overlap
    
    def process(self, pdf_path: str) -> list[PDFChunk]:
        """
        Processa PDF completo e retorna lista de chunks.
        """
        path = Path(pdf_path)
        filename = path.name
        
        print(f"[PDF] Processando: {filename}")
        
        chunks = []
        chunk_id = 0
        
        for page_data in self.extract_pages(pdf_path):
            page_text = page_data["text"]
            page_num = page_data["page"]
            has_images = page_data["has_images"]
            
            for chunk_text in self.chunk_text(page_text):
                chunks.append(PDFChunk(
                    text=chunk_text,
                    source=filename,
                    page=page_num,
                    chunk_id=chunk_id,
                    has_images=has_images
                ))
                chunk_id += 1
        
        print(f"[PDF] Extraídos {len(chunks)} chunks de {filename}")
        return chunks
    
    def to_documents(self, chunks: list[PDFChunk]) -> tuple[list[str], list[dict]]:
        """
        Converte chunks para formato compatível com VectorStore.
        Retorna (textos, metadados).
        """
        texts = []
        metadata = []
        
        for chunk in chunks:
            texts.append(chunk.text)
            metadata.append({
                "source": chunk.source,
                "page": chunk.page,
                "chunk_id": chunk.chunk_id,
                "has_images": chunk.has_images,
                "bbox": chunk.bbox
            })
        
        return texts, metadata
    
    def get_info(self, pdf_path: str) -> dict:
        """Retorna informações sobre o PDF."""
        doc = fitz.open(pdf_path)
        info = {
            "filename": Path(pdf_path).name,
            "page_count": len(doc),
            "metadata": doc.metadata,
            "has_toc": bool(doc.get_toc())
        }
        doc.close()
        return info


class HybridPDFProcessor(PDFProcessor):
    """
    Processador híbrido que usa modelo de visão para páginas com imagens.
    Requer MultimodalEngine para OCR avançado.
    """
    
    def __init__(
        self,
        vision_engine=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.vision_engine = vision_engine
    
    def extract_image_as_temp(self, pdf_path: str, page_num: int) -> Optional[str]:
        """Extrai página como imagem temporária para análise visual."""
        import tempfile
        
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        
        # Renderizar página como imagem
        pix = page.get_pixmap(dpi=100)
        
        # Salvar em arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            pix.save(f.name)
            temp_path = f.name
        
        doc.close()
        return temp_path
    
    def process(self, pdf_path: str) -> list[PDFChunk]:
        """Override para usar visão por padrão se disponível."""
        return self.process_with_vision(pdf_path)

    
    def process_page_with_ocr(self, pdf_path: str, page_num: int) -> list[PDFChunk]:
        """Processa uma página específica usando RapidOCR para obter coordenadas."""
        from rapidocr_onnxruntime import RapidOCR
        
        # Inicializar OCR (apenas na primeira vez ou singleton seria melhor, mas ok por agora)
        ocr = RapidOCR()
        
        temp_image = self.extract_image_as_temp(pdf_path, page_num - 1)
        if not temp_image:
            return []
            
        try:
            result, _ = ocr(temp_image)
            chunks = []
            
            if result:
                for line in result:
                    # line format: [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]], text, confidence]
                    coords, text, conf = line
                    
                    # Converter coords para bbox [x1, y1, x2, y2]
                    # Nota: Isso é relativo à imagem extraída (dpi=150), pode precisar de ajuste de escala para o PDF
                    x_coords = [p[0] for p in coords]
                    y_coords = [p[1] for p in coords]
                    bbox = [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                    
                    chunks.append(PDFChunk(
                        text=text,
                        source=Path(pdf_path).name,
                        page=page_num,
                        chunk_id=len(chunks), # ID temporário
                        has_images=True,
                        bbox=bbox
                    ))
            
            # Limpar
            Path(temp_image).unlink(missing_ok=True)
            return chunks
            
        except Exception as e:
            print(f"[OCR] Erro na página {page_num}: {e}")
            return []

    def process_with_vision(
        self,
        pdf_path: str,
        analyze_pages_with_images: bool = True
    ) -> list[PDFChunk]:
        """
        Processa PDF com análise visual para páginas complexas.
        """
        # Obter chunks de texto padrão
        chunks = super().process(pdf_path)
        
        if not analyze_pages_with_images or not self.vision_engine:
            return chunks
        
        # Identificar páginas que precisam de análise
        # 1. Páginas que geraram chunks marcados com imagens
        pages_to_analyze = set()
        for chunk in chunks:
            if chunk.has_images:
                pages_to_analyze.add(chunk.page)
                
        # 2. Se não extraímos nada (ou pouca coisa), verificar páginas com imagens diretamente
        # Isso cobre o caso de PDFs "scaneados" sem camada de texto
        if not chunks:
            print("[PDF] Nenhum texto extraído, verificando imagens...")
            for page_data in self.extract_pages(pdf_path):
                if page_data["has_images"]:
                    pages_to_analyze.add(page_data["page"])

        if not pages_to_analyze:
            return chunks
        
        print(f"[PDF] Analisando {len(pages_to_analyze)} páginas com imagens via Vision AI...")
        
        # Analisar cada página com visão
        # Analisamos todas que tem imagens para garantir OCR
        # Schema para saída estruturada (apenas descrição visual agora)
        vision_schema = {
            "type": "object",
            "properties": {
                "image_descriptions": {
                    "type": "array", 
                    "items": {"type": "string"}, 
                    "description": "Lista de descrições detalhadas de elementos visuais (gráficos, fotos, diagramas, tabelas) presentes na imagem. Ignore o texto nestas descrições."
                }
            },
            "required": ["image_descriptions"]
        }
        
        # Analisar cada página com visão
        for page_num in pages_to_analyze:
            try:
                print(f"[PDF] Analisando página {page_num}...")
                
                # 1. OCR com RapidOCR para texto e coordenadas
                ocr_chunks = self.process_page_with_ocr(pdf_path, page_num)
                for chunk in ocr_chunks:
                    chunk.chunk_id = len(chunks)
                    chunks.append(chunk)

                # 2. Vision Model para descrições visuais (sem OCR)
                temp_image = self.extract_image_as_temp(pdf_path, page_num - 1)
                if temp_image:
                    response_text = self.vision_engine.analyze_image(
                        temp_image,
                        prompt="Descreva apenas elementos visuais como gráficos, tabelas e fotos. Não transcreva texto, foque no conteúdo visual.",
                        json_schema=vision_schema
                    )
                    
                    # Parse do JSON
                    import json
                    try:
                        data = json.loads(response_text)
                        descriptions = data.get("image_descriptions", [])
                        
                        # Adicionar chunks de descrição visual (separados)
                        for desc in descriptions:
                            if desc.strip():
                                chunks.append(PDFChunk(
                                    text=f"[Descrição Visual - Página {page_num}]: {desc}",
                                    source=Path(pdf_path).name,
                                    page=page_num,
                                    chunk_id=len(chunks),
                                    has_images=True,
                                    bbox=None # Descrição visual é da página toda
                                ))
                                
                    except json.JSONDecodeError:
                        print(f"[PDF] Erro ao decodificar JSON da página {page_num}.")
                    
                    # Limpar arquivo temporário
                    Path(temp_image).unlink(missing_ok=True)
            except Exception as e:
                print(f"[PDF] Erro ao analisar página {page_num}: {e}")
        
        return chunks
