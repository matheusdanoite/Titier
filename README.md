# Titier

![Status](https://img.shields.io/badge/Status-Em_Desenvolvimento-warning)
![License](https://img.shields.io/badge/License-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Tauri](https://img.shields.io/badge/Tauri-2.0-orange)
![React](https://img.shields.io/badge/React-19-blue)

"Então você usa o NotebookLM", disse um amigo quando eu contei o próposito deste software, que nasceu da necessidade do meu amigo Cássio: um editor de PDF para que ele pudesse ler e fazer anotações, mas com uma IA integrada para deixar os textos de uma graduação de ciências humanas muito mais digeríveis. Menos para um NotebookLM e mais para um Acrobat Reader com a IA da Adobe, talvez. É verdade, poderia usar qualquer um desses dois, mas o Cássio também tem um PC foderoso. Pensando em extrair o máximo do poder computacional com algo que não fosse League of Legends, decidimos entrar nessa jornada de criação do Titier.

**O Titier é um assistente de estudos impulsionado por IA que funciona de forma 100% local e privada.** 

Privacidade é prioridade para o Titier. Os dados do seu PDF não saem do seu dispositivo; nenhum tipo de dado sai, na verdade. A IA roda localmente de maneira profundamente integrada à máquina, utilizando muitos recursos, é verdade, mas é legal para quem gosta de puxar o hardware ao seu limite.

O Titier aceita modelos em formato GGUF para a inferência de texto, e o PaddleOCR é usado para reconhecimento de caracteres em PDFs com imagens (ou escaneados). Isso significa que você pode utilizar o modelo que você quiser, e sua máquina aceitar, para realizar o processo de inferência.

## Como funciona o Titier

Ao enviar um arquivo PDF, é realizada uma verificação do seu conteúdo: se há texto puro, se há imagens, se há anotações e se há trechos destacados, bem como suas respectivas cores. Se houver imagens, o PaddleOCR é utilizado para extrair o texto das imagens. Tanto o texto extraído de imagens quanto o texto puro de PDFs mais bem formatados são indexados e armazenados localmente. Anotações de mesmas cores são mantidas em um só contexto, isto é, o Titier entende que estes trechos grifados possuem conteúdo relacionado. Você pode perguntar "o que está grifado em amarelo?" e o Titier responde.

## Funcionalidades
- **100% Local (Privacidade Total):** Seus documentos e conversas nunca saem do seu computador.
- **IA Multimodal:** Entende texto, tabelas, gráficos e anotações manuscritas.
- **RAG (Retrieval-Augmented Generation):** Respostas baseadas no conteúdo dos seus PDFs.
- **Chat Multi-Sessão:** Gerencie múltiplas conversas simultâneas com contextos independentes.
- **Streaming em Tempo Real:** Respostas exibidas token a token para feedback instantâneo.
- **Resumo Automático Estruturado:** Ao abrir um PDF, o Titier gera um resumo completo com visão geral, pontos-chave, resumo detalhado e conclusões.
- **Extração de Destaques:** Captura textos grifados, suas cores e anotações; cada cor gera um novo "assunto" dentro do PDF e seu conteúdo é priorizado nas respostas.
- **Interface Bonita:** Softwares feios que me desculpem, mas estética é fundamental.
- **Prompts Customizáveis:** Personalize os prompts de sistema diretamente pelas Configurações para adaptar o Titier ao seu estilo de estudo.
- **Performance Nativa & Inteligente:** Backend otimizado (Metal/CUDA) que se auto-configura baseado no seu hardware.
- **Otimizado para MacBook Air M1 8GB:** Configurações específicas para garantir que o Titier rode no meu singelo Mac.

## Tecnologias

- **Backend:** Python 3.11, FastAPI, Qdrant (Vetores), PyMuPDF.
- **AI Engine:** `llama-cpp-python` para visão e linguagem, `PaddleOCR-VL-1.5` (Vision OCR) e `rapidocr-onnxruntime`.
- **Frontend:** Tauri v2, React, TypeScript, Vite.
- **Modelos de IA:** O Titier é inteligente o suficiente para recomendar o melhor modelo para seu PC:
  - **MacBook Air M1 (8GB)**: Recomendamos o **Llama 3.2 3B** para conseguir rodar algo.
  - **Hardware Superior**: O sistema sugerirá modelos maiores como **Llama 3.1 8B**.O `server.py` utiliza uma **janela de contexto otimizada de 8192 tokens** e **chunking adaptativo** para garantir estabilidade e performance.
  - Se você for bom, pode usar o [Hugging Face](https://huggingface.co/) para obter modelos fodásticos e otimizados para seu uso.

## Como Obter o Titier

### Opção 1: Download do Executável (Recomendado)
Você pode baixar as versões mais recentes prontas para uso na página de **[Releases do GitHub](https://github.com/matheusdanoite/Titier/releases)**. Temos instaladores para:
- **Windows**: `.exe` (Suporta NVIDIA CUDA)
- **macOS**: `.dmg` (Nativo para Apple Silicon)

### Opção 2: Compilação Manual
Se você deseja compilar o projeto do zero, siga as instruções abaixo:

#### Pré-requisitos

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

#### Instalação e Execução (Desenvolvimento)

Siga os passos abaixo para rodar o projeto localmente.

##### 1. Backend (Python)

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

Rodar o Backend:
```bash
poetry run python -m app.server
# O servidor iniciará em http://127.0.0.1:8000
```

##### 2. Frontend (Tauri/React)

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

#### Build para Produção

Para gerar o executável final (`.app` ou `.exe`).

##### 1. Compilar o Backend (Sidecar)

O Tauri precisa de um executável do Python para empacotar junto. Usamos o PyInstaller.

```bash
# Na raiz do projeto
cd app
poetry run pyinstaller server.py \
  --name titier-backend \
  --onefile \
  --paths . \
  --collect-all llama_cpp \
  --collect-all sentence_transformers \
  --collect-all qdrant_client
```

*Nota: Mova o executável gerado em `dist/titier-backend` para `frontend/src-tauri/sidecars/` renomeando-o conforme a arquitetura (ex: `titier-backend-aarch64-apple-darwin` para Macs com Apple Silicon).*

##### 2. Compilar o App Tauri

```bash
cd frontend
npm run tauri build
```

##### 3. Instalar

O instalador estará em `frontend/src-tauri/target/release/bundle`.

##### 4. Estudar

De que adianta ser bonita e não ser inteligente?

## Estrutura do Projeto

```
Titier/
├── app/                 # Backend Python (FastAPI + IA)
│   ├── core/            # Lógica de IA (Inferência, Hardware, OCR, PDF)
│   ├── db/              # Banco de Vetores (Qdrant)
│   ├── server.py        # Entry point da API
│   ├── install.sh       # Script de setup de ambiente
│   └── pyproject.toml   # Configuração e dependências Python (Poetry)
├── frontend/            # Frontend (Tauri + React)
│   ├── src/             # Código React
│   └── src-tauri/       # Configuração Rust/Tauri
├── scripts/             # Scripts de teste e verificação
└── CHANGELOG.md         # Registro de alterações
```

## Contribuição

1.  Faça um Fork do projeto
2.  Crie uma Branch para sua Feature (`git checkout -b feature/metamorfose`)
3.  Commit suas mudanças (`git commit -m 'Uma metamorfose ambulante'`)
4.  Push para a Branch (`git push origin feature/metamorfose`)
5.  Abra um Pull Request

---

*Feito por matheusdanoite 🤝 com inputs de Cássio*