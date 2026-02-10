#!/usr/bin/env python3
"""
Titier - Teste de Performance do OCR Engine
Compara PaddleOCR vs RapidOCR (se disponível)
"""

import sys
import time
from pathlib import Path

# Adicionar o diretório app ao path
sys.path.append(str(Path(__file__).parent.parent / "app"))


def test_ocr_engine():
    """Testa o OCR Engine e mostra informações."""
    print("=" * 50)
    print("Titier - Teste do OCR Engine")
    print("=" * 50)
    
    from core.ocr_engine import get_ocr_engine, reset_ocr_engine
    
    # Reset para garantir teste limpo
    reset_ocr_engine()
    
    print("\n1. Inicializando OCR Engine...")
    start = time.time()
    ocr = get_ocr_engine()
    init_time = time.time() - start
    
    info = ocr.get_info()
    print(f"   ✓ Engine: {info['engine']}")
    print(f"   ✓ Backend: {info['backend']}")
    print(f"   ✓ GPU: {'✅ Sim' if info['gpu_enabled'] else '❌ Não'}")
    print(f"   ✓ Idioma: {info['language']}")
    print(f"   ✓ Tempo de inicialização: {init_time:.2f}s")
    
    print("\n2. Teste de processamento de imagem...")
    
    # Criar imagem de teste simples
    test_image_path = Path(__file__).parent / "test_ocr_image.png"
    
    if not test_image_path.exists():
        print("   → Criando imagem de teste...")
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Criar imagem com texto
            img = Image.new('RGB', (400, 100), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((20, 40), "Teste OCR - Titier PDF AI", fill='black')
            img.save(str(test_image_path))
            print(f"   ✓ Imagem criada: {test_image_path.name}")
        except ImportError:
            print("   ⚠️ PIL não disponível. Pulando teste de imagem.")
            test_image_path = None
    
    if test_image_path and test_image_path.exists():
        start = time.time()
        results = ocr.process_image(str(test_image_path))
        process_time = time.time() - start
        
        print(f"   ✓ Tempo de processamento: {process_time:.3f}s")
        print(f"   ✓ Resultados encontrados: {len(results)}")
        
        for i, r in enumerate(results[:3]):  # Mostrar até 3 resultados
            print(f"   → [{i+1}] \"{r.text[:50]}...\" (conf: {r.confidence:.2f})")
        
        # Limpar imagem de teste
        test_image_path.unlink(missing_ok=True)
    
    print("\n" + "=" * 50)
    print("✅ Teste concluído!")
    print("=" * 50)


def benchmark_ocr():
    """Benchmark do OCR com múltiplas repetições."""
    print("\n📊 Benchmark OCR (5 repetições)...")
    
    from core.ocr_engine import get_ocr_engine
    
    try:
        from PIL import Image, ImageDraw
        
        # Criar imagem de teste
        img = Image.new('RGB', (800, 200), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((20, 80), "Lorem ipsum dolor sit amet, consectetur adipiscing elit.", fill='black')
        
        test_path = Path(__file__).parent / "benchmark_ocr.png"
        img.save(str(test_path))
        
        ocr = get_ocr_engine()
        times = []
        
        for i in range(5):
            start = time.time()
            ocr.process_image(str(test_path))
            times.append(time.time() - start)
            print(f"   Run {i+1}: {times[-1]:.3f}s")
        
        avg = sum(times) / len(times)
        print(f"\n   📈 Média: {avg:.3f}s")
        print(f"   📈 Min: {min(times):.3f}s")
        print(f"   📈 Max: {max(times):.3f}s")
        
        test_path.unlink(missing_ok=True)
        
    except ImportError:
        print("   ⚠️ PIL não disponível para benchmark.")


if __name__ == "__main__":
    test_ocr_engine()
    
    # Benchmark opcional
    if len(sys.argv) > 1 and sys.argv[1] == "--benchmark":
        benchmark_ocr()
