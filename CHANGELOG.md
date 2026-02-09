# Registro de Alterações (Changelog)

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/spec/v2.0.0.html).

## [0.4.0] - 2026-02-09

### Adicionado
- **Chat Multi-Sessão:** Suporte a múltiplas conversas simultâneas com contextos independentes.
- **Streaming de Tokens:** Respostas da LLM são exibidas token a token em tempo real.
- **Componente `ChatSession.tsx`:** Novo componente encapsulado para gerenciamento de sessões de chat individuais.
- **Componente `SidebarMenu.tsx`:** Menu lateral para criar, selecionar e excluir sessões de chat.
- **Endpoint `/chat/stream`:** Nova API de streaming via Server-Sent Events (SSE).
- **Gestão Dinâmica de Contexto:** O sistema calcula automaticamente os tokens disponíveis e ajusta `max_tokens` para evitar estouro de memória.
- **ErrorBoundary:** Tratamento global de erros no frontend para evitar travamentos.

### Alterado
- **Janela de Contexto Otimizada:** `n_ctx` definido para 8192 tokens (estável para hardware local).
- **RAG Otimizado:** 
  - Tamanho de chunks reduzido de 500 para 200 palavras.
  - Overlap reduzido de 50 para 30 palavras.
  - Limite de recuperação reduzido de 5 para 3 chunks.
- **`max_tokens` padrão:** Aumentado para 4096 tokens para respostas mais completas.
- **Refatoração de `App.tsx`:** Arquitetura de estado para suportar múltiplas sessões ativas.

### Corrigido
- Erro `ValueError: Requested tokens exceed context window` ao processar documentos grandes.
- Travamento do sistema ao tentar usar contexto completo do modelo (128k tokens).
- Truncamento prematuro de respostas da LLM.
- `ReferenceError: FileText` no frontend.

---

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