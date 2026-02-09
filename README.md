# 🚀 Titier

**O Titier é um assistente de estudos impulsionado por IA que funciona de forma 100% local e privada.** Ele transforma seus PDFs em conhecimento acessível, permitindo que você converse com seus documentos usando Inteligência Artificial rodando 100% no seu computador.

## 🚀 Como Obter o Titier

### Opção 1: Download do Executável (Recomendado)
Você pode baixar as versões mais recentes prontas para uso na página de **[Releases do GitHub](https://github.com/matheusdanoite/Titier/releases)**. Temos instaladores para:
- **Windows**: `.exe` (Suporta NVIDIA CUDA)
- **macOS**: `.dmg` (Nativo para Apple Silicon)

### Opção 2: Compilação Manual
Se você deseja compilar o projeto do zero, siga as instruções abaixo:

## 🛠 Pré-requisitos

![Status](https://img.shields.io/badge/Status-Em_Desenvolvimento-warning)
![License](https://img.shields.io/badge/License-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Tauri](https://img.shields.io/badge/Tauri-2.0-orange)
![React](https://img.shields.io/badge/React-19-blue)

## ✨ Funcionalidades

- **🔒 100% Local (Privacidade Total):** Seus documentos e conversas nunca saem do seu computador.
- **🧠 IA Multimodal:** Entende texto, tabelas, gráficos e anotações manuscritas.
- **📚 RAG (Retrieval-Augmented Generation):** Respostas baseadas fielmente no conteúdo dos seus PDFs.
- **💬 Chat Multi-Sessão:** Gerencie múltiplas conversas simultâneas com contextos independentes.
- **⚡ Streaming em Tempo Real:** Respostas exibidas token a token para feedback instantâneo.
- **🚀 Performance Nativa:** Backend em Python otimizado (Metal/CUDA) + Frontend leve em Rust/Tauri.

---

## 🛠️ Tecnologias

- **Backend:** Python 3.11, FastAPI, LlamaIndex, Qdrant (Vetores), PyMuPDF.
- **AI Engine:** `llama-cpp-python` para visão e linguagem, `rapidocr-onnxruntime` para OCR.
- **Frontend:** Tauri v2, React, TypeScript, Vite, TailwindCSS.

---

## 📋 Pré-requisitos

Antes de começar, certifique-se de ter instalado:

1.  **Node.js** (v18 ou superior)
2.  **Python** (v3.11 recomendado)
3.  **Rust** (Latest stable)
4.  **Poetry** (Gerenciador de dependências Python)
    ```bash
    pip install poetry
    ```
5.  **Compiladores C++:**
    - **macOS:** Xcode Command Line Tools (`xcode-select --install`)
    - **Windows:** Visual Studio com "Desktop development with C++"

---

## 🚀 Instalação e Execução (Desenvolvimento)

Siga os passos abaixo para rodar o projeto localmente.

### 1. Backend (Python)

Configuração do servidor de IA e API.

```bash
# 1. Navegue até a pasta do projeto
cd titier

# 2. Instale as dependências com Poetry
poetry install

# 3. Configure a aceleração de hardware (Metal/CUDA)
# Este script recompila o llama-cpp-python para sua GPU específica
chmod +x app/install.sh
./app/install.sh
```

**Modelos de IA:**
O sistema precisa de modelos GGUF para funcionar.
1.  Crie a pasta: `mkdir -p ~/.titier/models`
2.  Baixe modelos (ex: Llama-3.1-8B-Instruct-Q4_K_M.gguf) e coloque nesta pasta.
3.  O `server.py` buscará modelos automaticamente neste diretório e utilizará uma **janela de contexto otimizada de 8192 tokens** para garantir estabilidade e performance em hardware local.

**Rodar o Backend:**
```bash
poetry run python -m app.server
# O servidor iniciará em http://127.0.0.1:8000
```

### 2. Frontend (Tauri/React)

Interface gráfica do usuário.

```bash
# 1. Navegue para a pasta frontend
cd frontend

# 2. Instale as dependências
npm install

# 3. Inicie o modo de desenvolvimento
npm run tauri dev
```

O aplicativo abrirá em uma janela nativa.

---

## 📦 Build para Produção

Para gerar o executável final (`.app` ou `.exe`).

### 1. Compilar o Backend (Sidecar)

O Tauri precisa de um executável do Python para empacotar junto. Usamos o PyInstaller.

```bash
# Na raiz do projeto
poetry run pyinstaller app/server.py \
  --name titier-backend \
  --onefile \
  --collect-all llama_cpp \
  --collect-all sentence_transformers \
  --collect-all qdrant_client
```

*Nota: Mova o executável gerado em `dist/titier-backend` para `frontend/src-tauri/sidecars/` renomeando-o conforme a arquitetura (ex: `titier-backend-aarch64-apple-darwin`).*

### 2. Compilar o App Tauri

```bash
cd frontend
npm run tauri build
```

O instalador estará em `frontend/src-tauri/target/release/bundle`.

---

## 📂 Estrutura do Projeto

```
Titier/
├── app/                 # Backend Python (FastAPI + IA)
│   ├── core/            # Lógica de IA (Inferência, Agente)
│   ├── db/              # Banco de Vetores (Qdrant)
│   ├── server.py        # Entry point da API
│   └── install.sh       # Script de setup de ambiente
├── frontend/            # Frontend (Tauri + React)
│   ├── src/             # Código React
│   └── src-tauri/       # Configuração Rust/Tauri
├── poetry.lock          # Dependências Python travadas
└── pyproject.toml       # Configuração do projeto Python
```

## 🤝 Contribuição

1.  Faça um Fork do projeto
2.  Crie uma Branch para sua Feature (`git checkout -b feature/metamorfose`)
3.  Commit suas mudanças (`git commit -m 'Uma metamorfose ambulante'`)
4.  Push para a Branch (`git push origin feature/metamorfose`)
5.  Abra um Pull Request