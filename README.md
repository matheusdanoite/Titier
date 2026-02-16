# Titier

[Português Brasileiro](README.pt-br.md)

"Why don't you use NotebookLM?" asked a friend when I told him the purpose of this software, which was born from my friend Cássio's need: a PDF editor so he could read and make notes, but with an integrated AI to make texts from a humanities degree much more digestible. Less like a NotebookLM and more like an Acrobat Reader with Adobe AI, perhaps. True, he could use either of those, but Cássio also has a powerful PC. Thinking of extracting the maximum computational power with something other than League of Legends, we decided to embark on this journey of creating Titier.

**Titier is an AI-powered study assistant that works 100% locally and privately.**

Privacy is a priority for Titier. Your PDF data does not leave your device; no data leaves, in fact. The AI runs locally, deeply integrated into the machine, using many resources, true, but it's cool for those who like to push their hardware to the limit.

Titier accepts models in GGUF format for text inference, and PaddleOCR is used for character recognition in PDFs with images (or scanned). This means you can use whatever model you want, and your machine accepts, to perform the inference process.

## How Titier Works
When uploading a PDF file, a check is performed on its content: if there is pure text, if there are images, if there are annotations and highlights, as well as their respective colors. If there are images, PaddleOCR is used to extract text from the images. Both text extracted from images and pure text from better-formatted PDFs are indexed and stored locally. Annotations of the same colors are kept in a single context, that is, Titier understands that these highlighted excerpts have related content. You can ask "what is highlighted in yellow?" and Titier answers.

## Features
- **100% Local (Total Privacy):** Your documents and conversations never leave your computer.
- **Multimodal AI:** Understands text, tables, charts, and handwritten notes.
- **RAG (Retrieval-Augmented Generation):** Answers based on the content of your PDFs.
- **Multi-Session Chat:** Manage multiple simultaneous conversations with independent contexts.
- **Real-Time Streaming:** Answers displayed token by token for instant feedback.
- **Structured Auto-Summary:** Upon opening a PDF, Titier generates a complete summary with overview, key points, detailed summary, and conclusions.
- **Highlight Extraction:** Captures highlighted texts, their colors, and notes; each color generates a new "topic" within the PDF and its content is prioritized in answers.
- **Beautiful Interface:** Ugly software, excuse me, but aesthetics are fundamental.
- **Customizable Prompts:** Customize system prompts directly through Settings to adapt Titier to your study style.
- **Native & Intelligent Performance:** Optimized backend (Metal/CUDA) that self-configures based on your hardware.
- **Optimized for MacBook Air M1 8GB:** Specific settings to ensure Titier runs on my humble Mac.

## Technologies
- **Backend:** Python 3.11, FastAPI, Qdrant (Vectors), PyMuPDF.
- **AI Engine:** `llama-cpp-python` for vision and language, `PaddleOCR-VL-1.5` (Vision OCR) and `rapidocr-onnxruntime`.
- **Frontend:** Tauri v2, React, TypeScript, Vite.
- **AI Models:** Titier is smart enough to recommend the best model for your PC:
  - **MacBook Air M1 (8GB)**: We recommend **Llama 3.2 3B** to manage running something.
  - **Superior Hardware**: The system will suggest larger models like **Llama 3.1 8B**. `server.py` uses an **optimized context window of 8192 tokens** and **adaptive chunking** to ensure stability and performance.
  - If you're good, you can use [Hugging Face](https://huggingface.co/) to get awesome models optimized for your use.

## How to Get Titier
### Option 1: Download Executable (Recommended)
You can download the latest ready-to-use versions on the **[GitHub Releases](https://github.com/matheusdanoite/Titier/releases)** page. We (will) have installers for:
- **Windows**: `.exe` (Supports NVIDIA CUDA)
- **macOS**: `.dmg` (Native for Apple Silicon)

### Option 2: Manual Compilation
If you wish to compile the project from scratch, follow the instructions below:

#### Prerequisites
Before starting, make sure you have installed:
1.  **Node.js** (v18 or higher)
2.  **Python** (v3.11 recommended)
3.  **Rust** (Latest stable)
4.  **Poetry** (Python dependency manager)
    ```bash
    pip install poetry
    ```
5.  **C++ Compilers:**
    - **macOS:** Xcode Command Line Tools (`xcode-select --install`)
    - **Windows:** Visual Studio with "Desktop development with C++"

#### Installation and Execution (Development)
Follow the steps below to run the project locally.

##### 1. Backend (Python)
AI server and API configuration.
```bash
# 1. Navigate to the project folder
cd titier

# 2. Install dependencies with Poetry
poetry install

# 3. Configure hardware acceleration (Metal/CUDA)
# This script recompiles llama-cpp-python for your specific GPU
chmod +x app/install.sh
./app/install.sh
```
Run the Backend:
```bash
poetry run python -m app.server
# The server will start at http://127.0.0.1:8000
```

##### 2. Frontend (Tauri/React)
Graphical User Interface.
```bash
# 1. Navigate to the frontend folder
cd frontend

# 2. Install dependencies
npm install

# 3. Start development mode
npm run tauri dev
```
The application will open in a native window.

#### Build for Production
To generate the final executable (`.app` or `.exe`).

##### 1. Compile the Backend (Sidecar)
Tauri needs a Python executable to package along. We use PyInstaller.
```bash
# In the project root
cd app
poetry run pyinstaller server.py \
  --name titier-backend \
  --onefile \
  --paths . \
  --collect-all llama_cpp \
  --collect-all sentence_transformers \
  --collect-all qdrant_client
```
*Note: Move the generated executable in `dist/titier-backend` to `frontend/src-tauri/sidecars/` renaming it according to the architecture (e.g., `titier-backend-aarch64-apple-darwin` for Macs with Apple Silicon).*

##### 2. Compile the Tauri App
```bash
cd frontend
npm run tauri build
```

##### 3. Install
The installer will be in `frontend/src-tauri/target/release/bundle`.

##### 4. Study
What's the point of being beautiful and not smart?

## Project Structure
```
Titier/
├── app/                 # Python Backend (FastAPI + AI)
│   ├── core/            # AI Logic (Inference, Hardware, OCR, PDF)
│   ├── db/              # Vector Database (Qdrant)
│   ├── server.py        # API Entry point
│   ├── install.sh       # Environment setup script
│   └── pyproject.toml   # Python configuration and dependencies (Poetry)
├── frontend/            # Frontend (Tauri + React)
│   ├── src/             # React Code
│   └── src-tauri/       # Rust/Tauri Configuration
├── scripts/             # Test and verification scripts
└── CHANGELOG.md         # Change log
```

## Contributing

1.  Fork the project
2.  Create a Branch for your Feature (`git checkout -b feature/metamorphosis`)
3.  Commit your changes (`git commit -m 'A walking metamorphosis'`)
4.  Push to the Branch (`git push origin feature/metamorphosis`)
5.  Open a Pull Request

*Made by matheusdanoite 🤝 with inputs from Cássio*
