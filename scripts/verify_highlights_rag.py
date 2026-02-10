import sys
import os
from pathlib import Path

# Adicionar app ao path
sys.path.append(str(Path(__file__).parent.parent / "app"))

import fitz
from core.pdf_processor import PDFProcessor
from db.vector_store import VectorStore

def create_highlighted_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    
    texts = [
        ("Este é o ponto crucial em amarelo.", (1, 1, 0), "Amarelo", None),
        ("Este detalhe técnico está em verde.", (0, 1, 0), "Verde", "Nota de engenharia"),
        ("Informação secundária sem grifo.", None, None, None),
        ("Aviso importante em vermelho.", (1, 0, 0), "Vermelho", "Urgente"),
    ]
    
    for i, (text, color, name, note) in enumerate(texts):
        y = 100 + (i * 50)
        page.insert_text((50, y), text)
        if color:
            rl = page.search_for(text)
            annot = page.add_highlight_annot(rl)
            annot.set_colors(stroke=color)
            if note:
                annot.set_info(content=note)
            annot.update()
            
    doc.save(path)
    doc.close()
    print(f"PDF de teste criado: {path}")

def verify_extraction(path):
    doc = fitz.open(path)
    print("\n--- Verificando Extração (Baixo Nível) ---")
    page = doc[0]
    for annot in page.annots():
        kind = annot.type[0]
        color = annot.colors.get('stroke')
        print(f"Annot Type: {kind}, Rect: {annot.rect}, Color: {color}")
    doc.close()

def test_highlight_rag():
    test_pdf = "test_rag_highlights.pdf"
    create_highlighted_pdf(test_pdf)
    verify_extraction(test_pdf)
    
    try:
        # 1. Processar PDF
        processor = PDFProcessor()
        chunks = processor.process(test_pdf)
        
        print(f"\nChunks extraídos: {len(chunks)}")
        for i, c in enumerate(chunks):
            print(f"Chunk {i}: Highlight={c.is_highlight}, Color={c.highlight_color}, Note={c.annotation}")
            print(f"  Text: {c.text[:100]}...")

        # 2. Vector Store (usar pasta temporária para não poluir)
        vs = VectorStore(storage_path="./temp_qdrant_highlights")
        vs.clear()
        
        texts, metadata = processor.to_documents(chunks)
        vs.add_documents(texts, metadata)
        
        # 3. Testar buscas filtradas
        print("\n--- Teste 1: Buscar por 'verde' ---")
        results_verde = vs.search("qualquer coisa", color_filter="verde", highlight_only=True)
        for r in results_verde:
            print(f"Result (Verde): {r['text']}")
            
        print("\n--- Teste 2: Buscar por 'vermelho' ---")
        results_vermelho = vs.search("qualquer coisa", color_filter="vermelho", highlight_only=True)
        for r in results_vermelho:
            print(f"Result (Vermelho): {r['text']}")

        print("\n--- Teste 3: Busca Geral (Deve vir tudo) ---")
        results_all = vs.search("ponto crucial")
        for r in results_all:
            print(f"Result (Geral): {r['text']}")

    finally:
        if os.path.exists(test_pdf):
            os.remove(test_pdf)
        import shutil
        if os.path.exists("./temp_qdrant_highlights"):
            shutil.rmtree("./temp_qdrant_highlights")

if __name__ == "__main__":
    test_highlight_rag()
