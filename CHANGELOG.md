# Changelog

## [0.5.1] - 2026-02-09

### Removed

#### Dead Code (Backend)
- **`app/main.py`:** Initial prototype that imported non-existent classes (`InferenceEngine`). Replaced by `server.py`.
- **`app/core/agent.py`:** `StudyAgent` with LlamaIndex Agent — never used by the main server.
- **`app/download_mmproj.py`:** Standalone download script replaced by `ModelManager`.
- **`app/utils/downloader.py`:** Legacy download module, used only by `main.py` (dead). `app/utils/` directory removed.
- **`app/test_header_footer.pdf`:** Test PDF forgotten in the backend root.

#### Unused Dependencies (Backend)
- **`llama-index`**, **`llama-index-llms-llama-cpp`**, **`llama-index-embeddings-huggingface`**, **`llama-index-vector-stores-qdrant`**, **`llama-index-tools-google`:** 5 packages removed from `pyproject.toml` — were used only in dead code (`agent.py` and `main.py`).
- **`requirements.txt`:** Duplicate file removed — `pyproject.toml` (Poetry) is the official source of dependencies.

#### Unused Dependencies (Frontend)
- **`@radix-ui/react-dialog`:** Never imported in any `.tsx` component.
- **`@tauri-apps/plugin-opener`:** Never imported in any `.tsx` component.

#### Outdated Documentation
- **`Pano de Implementação Frontend.md`**, **`Plano de Implementação Backend.md`**, **`Walkthrough 1.md`:** Initial project plans and walkthroughs removed — the project structure has diverged significantly.

#### Structural Cleanup
- Empty directories in root removed: `db/`, `data/`, `models/`.

### Fixed
- **API Version:** Fixed `server.py` from `0.2.0` to `0.5.0` to synchronize with `pyproject.toml` and `package.json`.

---

## [0.5.0] - 2026-02-09

### Added

#### User Interface & Experience
- **Empty State Screen (`EmptyState`):** New full-screen view when no PDF is loaded, with upload icon, highlighted text, drag-and-drop support, and shortcut to settings.
- **Processing Screen (`ProcessingView`):** Premium animation displayed during document analysis, with orbital rings, scan line effect, shimmer progress bar, and real-time status.
- **System Prompt Customization:** New "Prompts" tab in Settings, allowing the user to customize system prompts (RAG, Base, Vision) with default restoration.
- **Structured Auto-Summary:** Upon opening a PDF, Titier automatically generates a summary with sections: Overview, Key Points, Detailed Summary, and Conclusions.

#### Document Processing
- **Highlight Extraction:** New system that captures highlighted texts, their colors (yellow, green, blue, etc.), and associated notes from PDFs.
- **Highlight Color Filter:** Queries can be filtered by highlight color (e.g., "what is highlighted in yellow?") with automatic intent detection.
- **PaddleOCR-VL-1.5 Integration:** Advanced visual OCR engine for table extraction, complex layouts, and scanned PDFs.
- **Hybrid OCR with Fallback:** Automatic priority for VisionOCR (PaddleOCR), with transparent fallback to RapidOCR (optimized CPU).
- **Text Cleaning and Header/Footer Removal:** Heuristic system in PyMuPDF to identify and ignore repetitive elements across multiple pages.
- **Margin Filtering:** Support for ignoring specific page areas during text extraction.
- **Smart Block Sorting:** Text extraction respects the natural reading order (Y, then X), improving coherence in multi-column documents.
- **OCR Progress Logs:** Real-time tracking in the terminal (`Page X/Y`, time per page, and total time).

#### Backend & Optimization
- **Dynamic Hardware Detection:** `hardware.py` module that automatically detects RAM, VRAM (Metal/CUDA), and CPU cores.
- **Automatic Hardware Profiles:** System classifies hardware into 4 tiers (LOW/MEDIUM/HIGH/ULTRA) with optimized parameters.
- **Smart Layer Offloading:** `n_gpu_layers` calculated dynamically based on available VRAM.
- **Quantized KV Cache:** HIGH/ULTRA tiers use Q8_0 cache to reduce VRAM usage.
- **Flash Attention:** Automatically enabled when available.
- **`/api/hardware` Endpoint:** Exposes detailed hardware information and calculated settings.
- **OCR Status Endpoints:** `/ocr/vision/status` and `/ocr/status` for monitoring OCR engines.
- **Adaptive Chunking (Hardware-Aware):** Chunk size scales with hardware (100 to 300 words).
- **Optimization for 8GB Macs (M1/M2):** Automatic recommendation of Llama 3.2 3B.

### Changed
- **Refined RAG Prompts:** New guidelines include preservation of technical terms, hierarchical organization, and capturing nuances when summarizing.
- **Default Vision Engine:** Replaced MiniCPM-V with PaddleOCR-VL-1.5 for better compatibility.
- **Dynamic `n_ctx`:** Context window calculated automatically (2K-16K+) based on available memory.
- **Optimized `n_batch`:** Value adjusted by tier (128-1024) for better throughput.
- **Smart Threading:** `n_threads` and `n_threads_batch` configured based on CPU cores.
- **Refactored LLMEngine:** Accepts optional parameters and uses auto-detected values as default.
- **Dynamic RAG Limit:** The number of retrieved chunks is automatically adjusted by the model's context window size (2 to 20 chunks).

### Fixed
- **Scanned PDF Processing:** Fixed bug where files without a text layer failed extraction.
- **Non-GGUF Model Download:** Fixed `KeyError: 'filename'` error when downloading models from external hubs.
- **NumPy Compatibility:** Automatic downgrade to NumPy < 2.0 for compatibility with PaddleOCR.
- **Download Progress:** Fixed bug where UI stuck at 0% — now recursively monitors cache directories.
- **GPU Support (Metal/CUDA):** Fixed incorrect GPU backend reporting in frontend.
- Excessive VRAM usage in large models avoided via automatic offload to RAM.

---

## [0.4.0] - 2026-02-09

### Added
- **Multi-Session Chat:** Support for multiple simultaneous conversations with independent contexts.
- **Token Streaming:** LLM responses are displayed token by token in real-time.
- **`ChatSession.tsx` Component:** New encapsulated component for managing individual chat sessions.
- **`SidebarMenu.tsx` Component:** Sidebar menu to create, select, and delete chat sessions.
- **`/chat/stream` Endpoint:** New streaming API via Server-Sent Events (SSE).
- **Dynamic Context Management:** System automatically calculates available tokens and adjusts `max_tokens` to prevent memory overflow.
- **ErrorBoundary:** Global error handling in frontend to prevent crashes.

### Changed
- **Optimized Context Window:** `n_ctx` set to 8192 tokens (stable for local hardware).
- **Optimized RAG:** 
  - Chunk size reduced from 500 to 200 words.
  - Overlap reduced from 50 to 30 words.
  - Retrieval limit reduced from 5 to 3 chunks.
- **Default `max_tokens`:** Increased to 4096 tokens for more complete answers.
- **`App.tsx` Refactoring:** State architecture to support multiple active sessions.

### Fixed
- `ValueError: Requested tokens exceed context window` error when processing large documents.
- System crash when trying to use full model context (128k tokens).
- Premature truncation of LLM responses.
- `ReferenceError: FileText` in frontend.

---

## [0.3.0] - 2026-02-09

### Added
- Dynamic integration with Hugging Face Hub for model discovery.
- Dynamic search bar with debounce in onboarding flow.
- Automatic hardware filter based on system RAM.
- Quality filter to exclude models smaller than 3GB (experimental).
- Direct links to official repositories on Hugging Face in each model card.
- Dynamic cache system for models discovered via search.
- Hardware acceleration support (Metal/CUDA) integrated into GitHub Actions release workflow.

### Changed
- Refined model card UI with Flexbox for consistent button alignment.
- Simplified model descriptions to display only download count.
- Increased discovery limit to 12 simultaneous models.
- Improved download progress monitoring to support `huggingface_hub` temporary files.
- Consolidated backend dependencies in `app/pyproject.toml` (including `llama-cpp-python` and LlamaIndex extensions).

### Fixed
- 404 error when attempting to download dynamically discovered models.
- Error in progress monitoring that remained stuck at 0% in interface.
- Import bug (`NameError: os`) in ModelManager.

## [0.2.0] - 2026-02-09

### Added
- GitHub Actions workflow for release automation (Windows and macOS).

### Changed
- Updated documentation in README.md.

## [0.1.0] - 2026-02-09

### Added
- Initial release of **Titier**.
- Cross-platform support (macOS Metal, Windows CUDA).
- Local RAG (Retrieval-Augmented Generation) with LlamaIndex and Qdrant.
- Multimodal AI support using image analysis and OCR.
- Text-only model support (Llama 3.2, Phi-3, Mistral, Qwen2).
- PDF processing pipeline with hybrid extraction (PyMuPDF + Vision AI).
- Native desktop interface built with Tauri v2 and React.
- Model management system to download and manage GGUF models from Hugging Face.
- Onboarding flow for initial configuration (GPU check, model download, embeddings initialization).