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
    is_highlight: bool = False
    highlight_color: Optional[str] = None
    annotation: Optional[str] = None


class PDFProcessor:
    """
    Processador de PDF com chunking inteligente.
    Usa PyMuPDF para extração rápida de texto.
    """
    
    def __init__(
        self,
        chunk_size: int = 100,
        chunk_overlap: int = 30,
        min_chunk_length: int = 20
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length
    
    def extract_text(self, pdf_path: str) -> tuple[str, list[int]]:
        """
        Extrai texto de todas as páginas do PDF.
        Retorna (texto_completo, páginas_com_imagens).
        """
        with fitz.open(pdf_path) as doc:
            full_text = []
            pages_with_images = []
            
            for page_num, page in enumerate(doc):
                # Extrair texto
                text = page.get_text()
                full_text.append(text)
                
                # Verificar se tem imagens
                if page.get_images():
                    pages_with_images.append(page_num + 1)
            
            return "\n\n".join(full_text), pages_with_images

    def has_images(self, pdf_path_or_doc) -> bool:
        """Verificação rápida se o PDF contém imagens. Aceita path ou fitz.Document."""
        doc = pdf_path_or_doc if isinstance(pdf_path_or_doc, fitz.Document) else fitz.open(pdf_path_or_doc)
        found = False
        for page in doc:
            if page.get_images():
                found = True
                break
        if not isinstance(pdf_path_or_doc, fitz.Document):
            doc.close()
        return found
    

    def _map_highlight_color(self, color: Optional[tuple]) -> str:
        """Mapeia cor RGB do PyMuPDF para nome legível em português."""
        if not color: return "desconhecida"
        r, g, b = color
        # Heurística para cores comuns de marca-texto
        if r > 0.8 and g > 0.8 and b < 0.3: return "amarelo"
        if r < 0.4 and g > 0.8 and b < 0.4: return "verde"
        if r < 0.4 and g < 0.4 and b > 0.8: return "azul"
        if r > 0.8 and g < 0.4 and b < 0.4: return "vermelho"
        if r > 0.8 and g < 0.4 and b > 0.8: return "rosa"
        if r > 0.9 and g > 0.5 and b < 0.3: return "laranja"
        if r > 0.7 and g > 0.7 and b > 0.7: return "cinza"
        return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

    def extract_pages(self, pdf_path_or_doc) -> Generator[dict, None, None]:
        """Extrai texto página por página. Aceita path ou fitz.Document."""
        doc = pdf_path_or_doc if isinstance(pdf_path_or_doc, fitz.Document) else fitz.open(pdf_path_or_doc)
        
        try:
            for page_num, page in enumerate(doc):
                # 0. Extrair anotações e grifos da página
                highlights = list(page.annots())
                highlight_data = [] # list of (rect, color_name, annotation_text)
                for annot in highlights:
                    if annot.type[0] == 8: # Highlight
                        color = annot.colors.get('stroke')
                        color_name = self._map_highlight_color(color)
                        note = annot.info.get("content", "").strip()
                        highlight_data.append((annot.rect, color_name, note))
                
                if highlight_data:
                    print(f"[PDF] Página {page_num+1}: Encontrados {len(highlight_data)} grifos.")

                # Usar blocos para filtragem espacial
                blocks = page.get_text("blocks")
                blocks.sort(key=lambda b: (b[1], b[0]))
                
                clean_blocks = []
                for b in blocks:
                    x0, y0, x1, y1, text, block_no, block_type = b
                    if block_type != 0: continue
                    
                    content = text.strip()
                    if content:
                        block_rect = fitz.Rect(x0, y0, x1, y1)
                        is_h = False
                        h_color = None
                        h_note = None
                        
                        for h_rect, h_col, h_nt in highlight_data:
                            h_rect_tol = fitz.Rect(h_rect)
                            h_rect_tol.y0 -= 3
                            h_rect_tol.y1 += 3
                            
                            if block_rect.intersects(h_rect_tol):
                                is_h = True
                                h_color = h_col
                                h_note = h_nt
                                break
                        
                        clean_blocks.append({
                            "text": content,
                            "is_highlight": is_h,
                            "color": h_color,
                            "note": h_note,
                            "bbox": [x0, y0, x1, y1]
                        })
                
                page_text = "\n".join([b["text"] for b in clean_blocks])
                
                yield {
                    "page": page_num + 1,
                    "text": page_text,
                    "blocks": clean_blocks,
                    "has_images": len(page.get_images()) > 0,
                    "image_count": len(page.get_images())
                }
        finally:
            if not isinstance(pdf_path_or_doc, fitz.Document):
                doc.close()
    
    def chunk_text(self, text: str) -> Generator[str, None, None]:
        """
        Divide texto em chunks com overlap.
        Usa separação por palavras para manter contexto.
        """
        words = text.split()
        
        if len(words) <= self.chunk_size:
            if text.strip():
                yield text.strip()
            return
        
        start = 0
        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk = " ".join(chunk_words)
            
            if chunk.strip():
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
        
        with fitz.open(pdf_path) as doc:
            for page_data in self.extract_pages(doc):
                page_num = page_data["page"]
                has_images = page_data["has_images"]
                
                for block in page_data["blocks"]:
                    text = block["text"]
                    is_h = block["is_highlight"]
                    color = block["color"]
                    note = block["note"]
                    
                    processed_text = text
                    if is_h:
                        prefix = f"[DESTAQUE {color.upper()}]"
                        if note:
                            prefix += f" (Nota: {note})"
                        processed_text = f"{prefix}\n{text}"

                    for chunk_text in self.chunk_text(processed_text):
                        chunks.append(PDFChunk(
                            text=chunk_text,
                            source=filename,
                            page=page_num,
                            chunk_id=chunk_id,
                            has_images=has_images,
                            bbox=block["bbox"],
                            is_highlight=is_h,
                            highlight_color=color,
                            annotation=note
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
                "bbox": chunk.bbox,
                "is_highlight": chunk.is_highlight,
                "highlight_color": chunk.highlight_color,
                "annotation": chunk.annotation
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
    Processador híbrido que usa OCR para páginas com imagens.
    Suporta:
    - VisionOCREngine (PaddleOCR-VL-1.5) - preferencial
    - vision_engine (llama.cpp) - legado
    - OCREngine (RapidOCR) - fallback
    """
    
    def __init__(
        self,
        vision_engine=None,
        vision_ocr=None,  # VisionOCREngine para PaddleOCR-VL-1.5
        **kwargs
    ):
        super().__init__(**kwargs)
        self.vision_engine = vision_engine
        self.vision_ocr = vision_ocr
    
    def extract_image_as_temp(self, doc: fitz.Document, page_num: int) -> Optional[str]:
        """Extraira página como imagem temporária para análise visual."""
        import tempfile
        
        page = doc[page_num]
        
        # Renderizar página como imagem (150 DPI para OCR balanceado)
        pix = page.get_pixmap(dpi=150)
        
        # Salvar em arquivo temporário
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            pix.save(f.name)
            temp_path = f.name
        
        return temp_path
    
    def process(self, pdf_path: str) -> list[PDFChunk]:
        """Override para usar visão por padrão se disponível."""
        return self.process_with_vision(pdf_path)

    
    def process_page_with_ocr(self, doc: fitz.Document, page_num: int) -> list[PDFChunk]:
        """Processa uma página específica usando OCR Engine otimizado (PaddleOCR/ONNX)."""
        from .ocr_engine import get_ocr_engine
        
        # Usar singleton do OCR Engine (cached, GPU otimizado)
        ocr = get_ocr_engine()
        
        temp_image = self.extract_image_as_temp(doc, page_num - 1)
        if not temp_image:
            return []
            
        try:
            results = ocr.process_image(temp_image)
            chunks = []
            
            for result in results:
                chunks.append(PDFChunk(
                    text=result.text,
                    source=Path(doc.name).name,
                    page=page_num,
                    chunk_id=len(chunks),  # ID temporário
                    has_images=True,
                    bbox=result.bbox
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
        Se vision_engine não estiver disponível, usa apenas OCR.
        """
        filename = Path(pdf_path).name
        print(f"[PDF] Analisando estrutura de {filename}...")
        
        chunks = []
        pages_to_analyze = []
        
        with fitz.open(pdf_path) as doc:
            # 1. Primeira passada: extrair texto e identificar páginas com imagens
            for page_data in self.extract_pages(doc):
                page_num = page_data["page"]
                has_images = page_data["has_images"]
                
                # Adicionar chunks de texto se encontrados
                if page_data["text"].strip():
                    for block in page_data["blocks"]:
                        text = block["text"]
                        is_h = block["is_highlight"]
                        color = block["color"]
                        note = block["note"]
                        
                        processed_text = text
                        if is_h:
                            prefix = f"[DESTAQUE {color.upper()}]"
                            if note:
                                prefix += f" (Nota: {note})"
                            processed_text = f"{prefix}\n{text}"

                        for chunk_text in self.chunk_text(processed_text):
                            chunks.append(PDFChunk(
                                text=chunk_text,
                                source=filename,
                                page=page_num,
                                chunk_id=len(chunks),
                                has_images=has_images,
                                bbox=block["bbox"],
                                is_highlight=is_h,
                                highlight_color=color,
                                annotation=note
                            ))
                
                if has_images and analyze_pages_with_images:
                    pages_to_analyze.append(page_num)

            if not pages_to_analyze:
                return chunks
            
            total_ocr_pages = len(pages_to_analyze)
            print(f"[PDF] {total_ocr_pages} páginas precisam de análise visual/OCR.")

            # 2. Segunda passada (ou processamento das páginas identificadas)
            # Prioridade: VisionOCREngine > OCREngine (RapidOCR)
            if not self.vision_engine:
                # Tentar PaddleOCR-VL-1.5 primeiro
                if self.vision_ocr and self.vision_ocr.is_available:
                    import time
                    start_time = time.time()
                    print(f"[PDF] Processando com PaddleOCR-VL-1.5...")
                    for i, page_num in enumerate(pages_to_analyze):
                        try:
                            print(f"[OCR] Página {i+1}/{total_ocr_pages} (Doc: {page_num})...", flush=True)
                            result = self.vision_ocr.process_page(pdf_path, page_num)
                            chunks.append(PDFChunk(
                                text=result.markdown or result.text,
                                source=filename,
                                page=page_num,
                                chunk_id=len(chunks),
                                has_images=True,
                                bbox=None
                            ))
                        except Exception as e:
                            print(f"[VisionOCR] Erro na página {page_num}: {e}")
                    
                    print(f"[OCR] Concluído em {time.time() - start_time:.2f}s")
                    return chunks
                
                # Fallback: RapidOCR
                import time
                start_time = time.time()
                print(f"[PDF] Processando com OCR (RapidOCR fallback)...")
                for i, page_num in enumerate(pages_to_analyze):
                    try:
                        print(f"[OCR] Página {i+1}/{total_ocr_pages} (Doc: {page_num})...")
                        ocr_chunks = self.process_page_with_ocr(doc, page_num)
                        for chunk in ocr_chunks:
                            chunk.chunk_id = len(chunks)
                            chunks.append(chunk)
                    except Exception as e:
                        print(f"[OCR] Erro na página {page_num}: {e}")
                
                print(f"[OCR] Concluído em {time.time() - start_time:.2f}s")
                return chunks
            
            # Modo completo: OCR + Vision AI
            import time
            start_time = time.time()
            print(f"[PDF] Analisando com Vision AI...")
            
            vision_schema = {
                "type": "object",
                "properties": {
                    "image_descriptions": {
                        "type": "array", 
                        "items": {"type": "string"}, 
                        "description": "Lista de descrições detalhadas de elementos visuais (gráficos, fotos, diagramas, tabelas). Ignore o texto."
                    }
                },
                "required": ["image_descriptions"]
            }
            
            for i, page_num in enumerate(pages_to_analyze):
                try:
                    print(f"[PDF] Página {i+1}/{total_ocr_pages} (Doc: {page_num}) via Vision AI...")
                    # OCR
                    ocr_chunks = self.process_page_with_ocr(doc, page_num)
                    for chunk in ocr_chunks:
                        chunk.chunk_id = len(chunks)
                        chunks.append(chunk)

                    # Vision Descriptions
                    temp_image = self.extract_image_as_temp(doc, page_num - 1)
                    if temp_image:
                        response_text = self.vision_engine.analyze_image(
                            temp_image,
                            prompt="Descreva elementos visuais (gráficos, tabelas, fotos). Não transcreva texto.",
                            json_schema=vision_schema
                        )
                        import json
                        try:
                            data = json.loads(response_text)
                            for desc in data.get("image_descriptions", []):
                                if desc.strip():
                                    chunks.append(PDFChunk(
                                        text=f"[Descrição Visual - Página {page_num}]: {desc}",
                                        source=filename,
                                        page=page_num,
                                        chunk_id=len(chunks),
                                        has_images=True,
                                        bbox=None
                                    ))
                        except: pass
                        Path(temp_image).unlink(missing_ok=True)
                except Exception as e:
                    print(f"[PDF] Erro na página {page_num}: {e}")
            
            print(f"[PDF] Processamento visual completo em {time.time() - start_time:.2f}s")
            return chunks
