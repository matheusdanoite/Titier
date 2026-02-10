import fitz
import sys

def test_extract_highlights(pdf_path):
    doc = fitz.open(pdf_path)
    print(f"Analisando {pdf_path}...")
    
    for page in doc:
        print(f"\n--- Página {page.number + 1} ---")
        annots = page.annots()
        if not annots:
            print("Nenhuma anotação encontrada.")
            continue
            
        for annot in annots:
            kind = annot.type[0]
            if kind == 8: # Highlight
                color = annot.colors.get('stroke')
                # Mapear cor RGB para nome
                color_name = "desconhecida"
                if color:
                    r, g, b = color
                    if r > 0.8 and g > 0.8 and b < 0.2: color_name = "amarelo"
                    elif r < 0.2 and g > 0.8 and b < 0.2: color_name = "verde"
                    elif r < 0.2 and g < 0.2 and b > 0.8: color_name = "azul"
                    elif r > 0.8 and g < 0.2 and b < 0.2: color_name = "vermelho"
                    elif r > 0.8 and g < 0.2 and b > 0.8: color_name = "rosa"
                    elif r > 0.8 and g > 0.5 and b < 0.2: color_name = "laranja"
                
                content = annot.info.get("content", "")
                text = page.get_text("text", clip=annot.rect).strip()
                
                print(f"GRIFO [{color_name}]: {text}")
                if content:
                    print(f"  ANOTAÇÃO: {content}")
            else:
                print(f"Outro tipo de anotação: {kind}")
                
    doc.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_extract_highlights(sys.argv[1])
    else:
        print("Uso: python scripts/test_highlights.py <caminho_do_pdf>")
