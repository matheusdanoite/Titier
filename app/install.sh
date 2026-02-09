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

echo ""
echo "📦 Instalando dependências base..."
poetry install

echo ""
echo "🔧 Configurando llama-cpp-python com aceleração GPU..."

case "$OS" in
    macos)
        echo "   → Compilando com suporte a Metal (Apple Silicon)..."
        CMAKE_ARGS="-DGGML_METAL=on" poetry run pip install llama-cpp-python --force-reinstall --no-cache-dir
        ;;
    windows)
        echo "   → Compilando com suporte a CUDA (NVIDIA)..."
        echo "   ⚠️  Certifique-se de que o CUDA Toolkit está instalado!"
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
echo "✅ Verificando instalação..."
poetry run python -c "from app.core.inference import check_installation; check_installation()"

echo ""
echo "========================================"
echo "✅ Instalação concluída!"
echo "========================================"
echo ""
echo "Próximos passos:"
echo "  1. Baixe um modelo GGUF (ex: Llama-3.1-8B-Q4_K_M.gguf)"
echo "  2. Coloque em ~/.titier/models/"
echo "  3. Execute: poetry run python server.py"
