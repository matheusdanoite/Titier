# Registro de Alterações (Changelog)

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Versionamento Semântico](https://semver.org/lang/pt-BR/spec/v2.0.0.html).

## [0.5.0] - 2026-02-09

### Adicionado

#### Interface & Experiência do Usuário
- **Tela de Estado Vazio (`EmptyState`):** Nova visualização full-screen quando nenhum PDF está carregado, com ícone de upload, texto destacado, suporte a drag-and-drop, e atalho para configurações.
- **Tela de Processamento (`ProcessingView`):** Animação premium exibida durante a análise de documentos, com anéis orbitais, efeito de varredura (scan line), barra de progresso shimmer, e status em tempo real.
- **Customização de System Prompts:** Nova aba "Prompts" nas Configurações, permitindo ao usuário personalizar os prompts de sistema (RAG, Base, Visão) com restauração de padrões.
- **Resumo Automático Estruturado:** Ao abrir um PDF, o Titier gera automaticamente um resumo com seções: Visão Geral, Pontos-Chave, Resumo Detalhado, e Conclusões.

#### Processamento de Documentos
- **Extração de Destaques (Highlights):** Novo sistema que captura textos grifados, suas cores (amarelo, verde, azul, etc.) e anotações associadas dos PDFs.
- **Filtro por Cor de Destaque:** Consultas podem ser filtradas por cor de grifo (ex: "o que está grifado em amarelo?") com detecção automática de intenção.
- **Integração PaddleOCR-VL-1.5:** Motor de OCR visual avançado para extração de tabelas, layouts complexos e PDFs escaneados.
- **OCR Híbrido com Fallback:** Prioridade automática para VisionOCR (PaddleOCR), com fallback transparente para RapidOCR (CPU otimizado).
- **Limpeza de Texto e Remoção de Cabeçalhos/Rodapés:** Sistema heurístico no PyMuPDF para identificar e ignorar elementos repetitivos em múltiplas páginas.
- **Filtragem por Margem:** Suporte para ignorar áreas específicas da página durante a extração de texto.
- **Ordenação Inteligente de Blocos:** Extração de texto respeita a ordem natural de leitura (Y, depois X), melhorando a coerência em documentos com colunas.
- **Logs de Progresso de OCR:** Acompanhamento em tempo real no terminal (`Página X/Y`, tempo por página e tempo total).

#### Backend & Otimização
- **Detecção Dinâmica de Hardware:** Módulo `hardware.py` que detecta automaticamente RAM, VRAM (Metal/CUDA), e CPU cores.
- **Perfis de Hardware Automáticos:** Sistema classifica hardware em 4 tiers (LOW/MEDIUM/HIGH/ULTRA) com parâmetros otimizados.
- **Smart Layer Offloading:** `n_gpu_layers` calculado dinamicamente baseado na VRAM disponível.
- **KV Cache Quantizado:** Tiers HIGH/ULTRA usam cache Q8_0 para reduzir uso de VRAM.
- **Flash Attention:** Habilitado automaticamente quando disponível.
- **Endpoint `/api/hardware`:** Expõe informações detalhadas do hardware e configurações calculadas.
- **Endpoints de Status OCR:** `/ocr/vision/status` e `/ocr/status` para monitoramento dos motores de OCR.
- **Chunking Adaptativo (Hardware-Aware):** Tamanho dos chunks escala com o hardware (100 a 300 palavras).
- **Otimização para Macs de 8GB (M1/M2):** Recomendação automática do Llama 3.2 3B.

### Alterado
- **Prompts RAG Refinados:** Novas diretrizes incluem preservação de termos técnicos, organização hierárquica, e captura de nuances ao resumir.
- **Motor de Visão Padrão:** Substituído MiniCPM-V por PaddleOCR-VL-1.5 para melhor compatibilidade.
- **`n_ctx` Dinâmico:** Janela de contexto calculada automaticamente (2K-16K+) baseada na memória disponível.
- **`n_batch` Otimizado:** Valor ajustado por tier (128-1024) para melhor throughput.
- **Threading Inteligente:** `n_threads` e `n_threads_batch` configurados baseado nos cores da CPU.
- **LLMEngine Refatorado:** Aceita parâmetros opcionais e usa valores auto-detectados como padrão.
- **Limite Dinâmico de RAG:** O número de chunks recuperados é ajustado automaticamente pelo tamanho da janela de contexto do modelo (2 a 20 chunks).

### Corrigido
- **Processamento de PDFs Escaneados:** Corrigido bug onde arquivos sem camada de texto falhavam na extração.
- **Download de Modelos Non-GGUF:** Corrigido erro `KeyError: 'filename'` ao baixar modelos de hubs externos.
- **Compatibilidade NumPy:** Downgrade automático para NumPy < 2.0 para compatibilidade com PaddleOCR.
- **Progresso de Download:** Corrigido bug onde a UI ficava travada em 0% — agora monitora recursivamente diretórios de cache.
- **Suporte GPU (Metal/CUDA):** Corrigido reporte incorreto do backend de GPU no frontend.
- Uso excessivo de VRAM em modelos grandes evitado via offload automático para RAM.

---

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