import sys
import os
from pathlib import Path

# Adicionar app ao path
sys.path.append(str(Path(__file__).parent.parent / "app"))

import fitz
from core.pdf_processor import PDFProcessor

def create_test_pdf(path):
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page()
        # Cabeçalho repetitivo
        page.insert_text((50, 30), "Relatório Confidencial Titier", fontsize=10)
        # Conteúdo variável
        page.insert_text((50, 100), f"Este é o conteúdo principal da página {i+1}.")
        # Rodapé repetitivo
        page.insert_text((50, 780), "RODAPE FIXO", fontsize=8)
    doc.save(path)
    doc.close()
    print(f"PDF de teste criado em: {path}")

def test_extraction():
    test_pdf = "test_no_cleaning.pdf"
    create_test_pdf(test_pdf)
    
    print("\n--- Verificando Extração (Sem Filtros) ---")
    processor = PDFProcessor()
    chunks = processor.process(test_pdf)
    full_text = "\n".join([c.text for c in chunks])
    
    header_found = "Relatório Confidencial Titier" in full_text
    footer_found = "RODAPE FIXO" in full_text
    
    print(f"Cabeçalho encontrado: {header_found}")
    print(f"Rodapé encontrado: {footer_found}")
    
    if header_found and footer_found:
        print("\n[SUCESSO] Cabeçalhos e rodapés foram preservados conforme solicitado.")
    else:
        print("\n[FALHA] Algum conteúdo ainda está sendo filtrado.")

    if os.path.exists(test_pdf):
        os.remove(test_pdf)

if __name__ == "__main__":
    test_extraction()
