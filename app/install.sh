#!/bin/bash
# =============================================================================
# Titier - Script de Instalação de Dependências
# Configura llama-cpp-python com suporte a Metal (macOS) ou CUDA (Windows/Linux)
# =============================================================================

set -e

echo "========================================"
echo "Titier - Instalação de Dependências"
echo "========================================"

# Detectar sistema operacional
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

OS=$(detect_os)
echo "Sistema detectado: $OS"

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Por favor, instale Python 3.11+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python: $PYTHON_VERSION"

# Verificar Poetry
if ! command -v poetry &> /dev/null; then
    echo "⚠️  Poetry não encontrado. Instalando via pipx..."
    pip3 install pipx
    pipx install poetry
fi

# Ir para diretório do app
cd "$(dirname "$0")"

# === Ccache Setup (Speed up recompilations) ===
echo "🚀 Verificando ccache..."
if ! command -v ccache &> /dev/null; then
    echo "   → ccache não encontrado. Tentando instalar..."
    case "$OS" in
        macos)
            if command -v brew &> /dev/null; then
                brew install ccache
            else
                echo "   ⚠️ Homebrew não encontrado, pulando ccache"
            fi
            ;;
        linux)
            if command -v apt-get &> /dev/null; then
                sudo apt-get update && sudo apt-get install -y ccache
            elif command -v pacman &> /dev/null; then
                sudo pacman -S --noconfirm ccache
            fi
            ;;
    esac
fi

if command -v ccache &> /dev/null; then
    echo "   → ccache ativado! ✨"
    export CC="ccache cc"
    export CXX="ccache c++"
    export PATH="/usr/lib/ccache:/usr/local/opt/ccache/libexec:$PATH"
fi

echo ""
echo "📦 Instalando dependências base..."
poetry install

echo ""
echo "🔧 Configurando llama-cpp-python com aceleração GPU..."

case "$OS" in
    macos)
        echo "   → Compilando com suporte a Metal (Apple Silicon)..."
        # Usar --no-cache-dir para o pip, mas o ccache cuidará da compilação real
        CMAKE_ARGS="-DGGML_METAL=on" poetry run pip install llama-cpp-python --force-reinstall --no-cache-dir
        ;;
    windows)
        echo "   → Compilando com suporte a CUDA (NVIDIA)..."
        echo "   ⚠️  Certifique-se de que o CUDA Toolkit está instalado!"
        # Nota: ccache no windows requer setup extra (cl.exe), ignorando por enquanto
        CMAKE_ARGS="-DGGML_CUDA=on" poetry run pip install llama-cpp-python --force-reinstall --no-cache-dir
        ;;
    linux)
        # Detectar se tem NVIDIA GPU
        if command -v nvidia-smi &> /dev/null; then
            echo "   → GPU NVIDIA detectada, compilando com CUDA..."
            CMAKE_ARGS="-DGGML_CUDA=on" poetry run pip install llama-cpp-python --force-reinstall --no-cache-dir
        else
            echo "   → Sem GPU NVIDIA, usando CPU..."
            poetry run pip install llama-cpp-python --force-reinstall --no-cache-dir
        fi
        ;;
    *)
        echo "   → Sistema desconhecido, instalando versão CPU..."
        poetry run pip install llama-cpp-python --force-reinstall --no-cache-dir
        ;;
esac

echo ""
echo "✅ Verificando instalação llama-cpp..."
poetry run python -c "from app.core.inference import check_installation; check_installation()"

# === PaddleOCR GPU Configuration ===
echo ""
echo "🔧 Configurando PaddleOCR para aceleração GPU..."

case "$OS" in
    macos)
        echo "   → macOS: PaddleOCR usará CPU otimizado (MKL-DNN não disponível)"
        echo "   → ONNX High-Performance mode habilitado automaticamente"
        ;;
    windows|linux)
        if command -v nvidia-smi &> /dev/null; then
            echo "   → GPU NVIDIA detectada, instalando paddlepaddle-gpu..."
            # PaddlePaddle GPU para CUDA 11.8/12.x
            poetry run pip install paddlepaddle-gpu --upgrade 2>/dev/null || \
                echo "   ⚠️  Falha ao instalar paddlepaddle-gpu, usando CPU"
        else
            echo "   → Sem GPU NVIDIA, usando CPU com MKL-DNN"
        fi
        ;;
esac

echo ""
echo "✅ Verificando OCR Engines..."
echo "   Verificando RapidOCR fallback..."
poetry run python -c "from core.ocr_engine import get_ocr_engine; e = get_ocr_engine(); print(f'   → OCR Backend: {e.backend}')"

echo "   Verificando PaddleOCR-VL..."
poetry run python -c "from core.vision_ocr import is_vision_ocr_available; print(f'   → VisionOCR disponível: {is_vision_ocr_available()}')" 2>/dev/null || echo "   → VisionOCR: não instalado (instale paddleocr[doc-parser])"

echo ""
echo "========================================"
echo "✅ Instalação concluída!"
echo "========================================"
echo ""
echo "Próximos passos:"
echo "  1. Baixe um modelo GGUF (ex: Llama-3.1-8B-Q4_K_M.gguf)"
echo "  2. Coloque em ~/.titier/models/"
echo "  3. Execute: poetry run python server.py"
echo ""
echo "Para habilitar PaddleOCR-VL-1.5 (opcional):"
echo "  pip install paddlepaddle>=3.2.1"
echo "  pip install paddleocr[doc-parser]"
