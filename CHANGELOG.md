# Registro de Alterações (Changelog)

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/spec/v2.0.0.html).

## [0.1.0] - 2026-02-09

### Adicionado
- Lançamento inicial do **Titier**.
- Suporte multiplataforma (macOS Metal, Windows CUDA).
- RAG (Geração Aumentada por Recuperação) local com LlamaIndex e Qdrant.
- Suporte a IA Multimodal usando análise de imagem e OCR.
- Suporte a modelos apenas de texto (Llama 3.2, Phi-3, Mistral, Qwen2).
- Pipeline de processamento de PDF com extração híbrida (PyMuPDF + Vision AI).
- Interface de desktop nativa construída com Tauri v2 e React.
- Sistema de gerenciamento de modelos para baixar e gerenciar modelos GGUF do Hugging Face.
- Fluxo de integração (onboarding) para configuração inicial (verificação de GPU, download de modelo, inicialização de embeddings).