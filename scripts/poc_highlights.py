import fitz
import os

def create_highlighted_pdf(path):
    doc = fitz.open()
    page = doc.new_page()
    
    text1 = "Este é um parágrafo que será grifado em amarelo."
    page.insert_text((50, 100), text1)
    
    text2 = "Este parágrafo será grifado em verde e terá uma anotação."
    page.insert_text((50, 150), text2)
    
    text3 = "Este será um grifo vermelho para teste."
    page.insert_text((50, 200), text3)
    
    # Criar grifos
    # 1. Amarelo
    rl1 = page.search_for(text1)
    annot1 = page.add_highlight_annot(rl1)
    annot1.set_colors(stroke=(1, 1, 0)) # Amarelo
    annot1.update()
    
    # 2. Verde com anotação
    rl2 = page.search_for(text2)
    annot2 = page.add_highlight_annot(rl2)
    annot2.set_colors(stroke=(0, 1, 0)) # Verde
    annot2.set_info(content="Importante: Contexto de sustentabilidade")
    annot2.update()
    
    # 3. Vermelho
    rl3 = page.search_for(text3)
    annot3 = page.add_highlight_annot(rl3)
    annot3.set_colors(stroke=(1, 0, 0)) # Vermelho
    annot3.update()
    
    doc.save(path)
    doc.close()
    print(f"PDF com grifos criado em: {path}")

def map_color(color):
    if not color: return "desconhecida"
    r, g, b = color
    # Heurística simples
    if r > 0.8 and g > 0.8 and b < 0.2: return "amarelo"
    if r < 0.2 and g > 0.8 and b < 0.2: return "verde"
    if r < 0.2 and g < 0.2 and b > 0.8: return "azul"
    if r > 0.8 and g < 0.2 and b < 0.2: return "vermelho"
    if r > 0.8 and g < 0.2 and b > 0.8: return "rosa"
    if r > 0.8 and g > 0.5 and b < 0.2: return "laranja"
    return f"rgb({r:.1f},{g:.1f},{b:.1f})"

def verify_extraction(path):
    doc = fitz.open(path)
    print("\n--- Verificando Extração ---")
    page = doc[0]
    for annot in page.annots():
        if annot.type[0] == 8: # Highlight
            color = annot.colors.get('stroke')
            color_name = map_color(color)
            content = annot.info.get("content", "")
            text = page.get_text("text", clip=annot.rect).strip()
            print(f"Encontrado: [{color_name}] '{text}'")
            if content:
                print(f"  Anotação: {content}")
    doc.close()

if __name__ == "__main__":
    test_file = "test_highlights.pdf"
    create_highlighted_pdf(test_file)
    verify_extraction(test_file)
    if os.path.exists(test_file):
        os.remove(test_file)
