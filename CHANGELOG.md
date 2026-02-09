# Registro de Alterações (Changelog)

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/spec/v2.0.0.html).

## [0.3.0] - 2026-02-09

### Adicionado
- Integração dinâmica com Hugging Face Hub para descoberta de modelos.
- Barra de busca dinâmica com debounce no fluxo de onboarding.
- Filtro automático de hardware baseado na RAM do sistema.
- Filtro de qualidade para excluir modelos menores que 3GB (experimental).
- Links diretos para os repositórios oficiais no Hugging Face em cada card de modelo.
- Sistema de cache dinâmico para modelos descobertos via busca.
- Suporte a aceleração por hardware (Metal/CUDA) integrado ao workflow de release do GitHub Actions.

### Alterado
- Refinamento da UI dos cards de modelo com Flexbox para alinhamento consistente dos botões.
- Descrições de modelos simplificadas para exibir apenas a contagem de downloads.
- Aumento do limite de descoberta para 12 modelos simultâneos.
- Melhoria no monitoramento de progresso de download para suportar arquivos temporários do `huggingface_hub`.
- Consolidação de dependências do backend no `app/pyproject.toml` (incluindo `llama-cpp-python` e extensões do LlamaIndex).

### Corrigido
- Erro 404 ao tentar baixar modelos descobertos dinamicamente.
- Erro no monitoramento de progresso que permanecia travado em 0% na interface.
- Bug de importação (`NameError: os`) no ModelManager.

## [0.2.0] - 2026-02-09

### Adicionado
- Workflow de GitHub Actions para automação de releases (Windows e macOS).

### Alterado
- Atualização da documentação no README.md.

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