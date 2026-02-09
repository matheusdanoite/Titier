import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Loader2, Sparkles, Search, ExternalLink, Check, AlertCircle, Database, ChevronRight } from 'lucide-react';
import { openUrl } from '@tauri-apps/plugin-opener';

interface OnboardingStep {
    id: string;
    title: string;
    completed: boolean;
    description: string;
}

interface Model {
    id: string;
    name: string;
    description: string;
    size_gb: number;
    vram_required: number;
    installed: boolean;
    recommended?: boolean;
    recommendation_reason?: string;
    repo?: string;
    filename?: string;
    downloads?: number;
    url?: string;
}

interface OnboardingProps {
    onComplete: () => void;
}

const API_URL = 'http://127.0.0.1:8000';

interface DownloadStatus {
    status: string;
    progress: number;
    downloaded_mb: number;
    total_mb: number;
    speed_mbps: number;
    error?: string;
}

export function Onboarding({ onComplete }: OnboardingProps) {
    const [step, setStep] = useState(0);
    const [steps, setSteps] = useState<OnboardingStep[]>([]);
    const [models, setModels] = useState<Model[]>([]);
    const [downloads, setDownloads] = useState<Record<string, DownloadStatus>>({});
    const [error, setError] = useState<string | null>(null);
    const [initializingEmbeddings, setInitializingEmbeddings] = useState(false);
    const [embeddingsProgress, setEmbeddingsProgress] = useState(0);
    const [isLoading, setIsLoading] = useState(true);

    // Search state
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [showAdvanced, setShowAdvanced] = useState(false);

    // Featured models defaults
    const DEFAULT_LLM: Model = {
        id: "llama-3.2-3b",
        name: "Llama 3.2 3B Instruct",
        description: "Modelo inteligente e extremamente rápido, ideal para a maioria dos computadores.",
        size_gb: 2.0,
        vram_required: 4,
        installed: false,
        recommended: true
    };

    const DEFAULT_OCR: Model = {
        id: "paddleocr-vl-1.5",
        name: "PaddleOCR-VL 1.5",
        description: "Modelo otimizado pela Baidu, mestre em extrair textos de documentos, tabelas e imagens complexas com precisão.",
        size_gb: 0.94,
        vram_required: 2,
        installed: false,
        recommended: true,
        repo: "nclssprt/PaddleOCR-VL-GGUF",
        filename: "paddleocr-vl-0.9b.gguf"
    };

    useEffect(() => {
        fetchOnboardingStatus();
    }, []);

    useEffect(() => {
        if (step === 1 && showAdvanced) fetchModels();
        if (step === 2 && showAdvanced) fetchOCRModels();
    }, [step, showAdvanced]);

    const handleSearch = (query: string) => {
        setSearchQuery(query);
        if (searchTimeout.current) clearTimeout(searchTimeout.current);

        if (!query.trim()) {
            if (step === 1) fetchModels();
            if (step === 2) fetchOCRModels();
            return;
        }

        setIsSearching(true);
        searchTimeout.current = setTimeout(async () => {
            try {
                const endpoint = step === 2 ? 'ocr/search' : 'search';
                const res = await fetch(`${API_URL}/models/${endpoint}?q=${encodeURIComponent(query)}`);
                const data = await res.json();
                setModels(data);
            } catch (err) {
                console.error("Erro na busca:", err);
            } finally {
                setIsSearching(false);
            }
        }, 500); // Debounce 500ms
    };

    const fetchOnboardingStatus = async () => {
        try {
            const res = await fetch(`${API_URL}/onboarding/status`);
            const data = await res.json();
            setSteps(data.steps);

            if (data.ready_to_chat) {
                onComplete();
            }
        } catch (err) {
            setError('Erro ao conectar com o backend');
        }
    };

    const fetchModels = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/models/recommended`);
            const data = await res.json();
            setModels(data);
        } catch (err) {
            console.error('Erro ao buscar modelos:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchOCRModels = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/models/ocr/recommended`);
            const data = await res.json();
            setModels(data);
        } catch (err) {
            console.error('Erro ao buscar modelos OCR:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const downloadModel = async (modelId: string) => {
        setError(null);

        try {
            const response = await fetch(`${API_URL}/models/download/${modelId}`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.status === 'already_installed') {
                fetchOnboardingStatus();
                setStep(prev => prev + 1);
                return;
            }

            if (data.status === 'started') {
                setStep(prev => prev + 1); // Avança automaticamente para o próximo passo

                // Inicializar status no estado local
                setDownloads(prev => ({
                    ...prev,
                    [modelId]: { status: 'pending', progress: 0, downloaded_mb: 0, total_mb: 0, speed_mbps: 0 }
                }));
            }

            const pollProgress = async () => {
                try {
                    const statusRes = await fetch(`${API_URL}/models/download/${modelId}/status`);
                    const status = await statusRes.json();

                    setDownloads(prev => ({
                        ...prev,
                        [modelId]: status
                    }));

                    if (status.status === 'downloading' || status.status === 'pending') {
                        setTimeout(pollProgress, 1000);
                    } else if (status.status === 'completed') {
                        setTimeout(() => {
                            fetchOnboardingStatus();
                        }, 1000);
                    } else if (status.status === 'failed') {
                        setError(status.error || 'Erro no download');
                    }
                } catch (e) {
                    console.error('Erro no polling:', e);
                }
            };

            setTimeout(pollProgress, 2000);
        } catch (err) {
            setError('Erro ao iniciar download');
        }
    };

    const initEmbeddings = async () => {
        setInitializingEmbeddings(true);
        setEmbeddingsProgress(0);
        try {
            const res = await fetch(`${API_URL}/onboarding/init-embeddings`, { method: 'POST' });
            const data = await res.json();

            if (data.status === 'already_initialized') {
                setInitializingEmbeddings(false);
                setEmbeddingsProgress(100);
                fetchOnboardingStatus();
                return;
            }

            const pollProgress = async () => {
                const statusRes = await fetch(`${API_URL}/onboarding/init-embeddings/status`);
                const status = await statusRes.json();

                if (status.status === 'loading') {
                    setEmbeddingsProgress(status.progress || 50);
                    setTimeout(pollProgress, 2000);
                } else if (status.status === 'completed') {
                    setInitializingEmbeddings(false);
                    setEmbeddingsProgress(100);
                    fetchOnboardingStatus();
                } else if (status.status === 'failed') {
                    setError(status.error || 'Erro ao carregar embeddings');
                    setInitializingEmbeddings(false);
                }
            };

            setTimeout(pollProgress, 3000);
        } catch (err) {
            setError('Erro ao inicializar embeddings');
            setInitializingEmbeddings(false);
        }
    };

    // Helper para verificar se um passo está completo no backend
    const isStepCompleted = (stepId: string) => {
        return steps.find(s => s.id === stepId)?.completed || false;
    };

    const featuredModel = step === 1 ? DEFAULT_LLM : DEFAULT_OCR;
    const isFeaturedInstalled = isStepCompleted(step === 1 ? 'llm' : 'ocr');

    return (
        <div className="onboarding-container">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="onboarding-card glass-panel"
            >
                {/* Header - Only visible on step 0 */}
                {step === 0 && (
                    <div className="onboarding-header">
                        <Sparkles size={40} className="onboarding-icon" />
                        <h1>Bem-vindo ao Titier</h1>
                        <p>Vamos configurar seu assistente de estudos</p>
                    </div>
                )}

                {/* Steps Indicator */}
                <div className="steps-indicator">
                    {['Início', 'Modelo IA', 'OCR', 'Embeddings', 'Pronto!'].map((label, i) => {
                        const isCurrent = step === i;

                        // Encontrar se há algum download ativo para esta etapa
                        // Etapa 1: LLM, Etapa 2: OCR, Etapa 3: Embeddings
                        let activeProgress = 0;
                        let showProgress = false;

                        if (i === 1) {
                            const llmId = DEFAULT_LLM.id;
                            if (downloads[llmId] && (downloads[llmId].status === 'downloading' || downloads[llmId].status === 'pending')) {
                                showProgress = true;
                                activeProgress = downloads[llmId].progress || 0;
                            }
                        } else if (i === 2) {
                            const ocrId = DEFAULT_OCR.id;
                            if (downloads[ocrId] && (downloads[ocrId].status === 'downloading' || downloads[ocrId].status === 'pending')) {
                                showProgress = true;
                                activeProgress = downloads[ocrId].progress || 0;
                            }
                        } else if (i === 3) {
                            if (initializingEmbeddings) {
                                showProgress = true;
                                activeProgress = embeddingsProgress;
                            }
                        }

                        const radius = 18;
                        const circumference = 2 * Math.PI * radius;
                        const offset = circumference - (activeProgress / 100) * circumference;

                        return (
                            <div key={i} className={`step-dot ${step >= i ? 'active' : ''} ${isCurrent ? 'current' : ''}`}>
                                <div className="dot-container">
                                    {showProgress && (
                                        <svg className="progress-ring" width="44" height="44">
                                            <circle
                                                className="progress-ring__circle"
                                                stroke="var(--accent)"
                                                strokeWidth="2"
                                                fill="transparent"
                                                r={radius}
                                                cx="22"
                                                cy="22"
                                                style={{
                                                    strokeDasharray: `${circumference} ${circumference}`,
                                                    strokeDashoffset: offset,
                                                    transition: 'stroke-dashoffset 0.3s'
                                                }}
                                            />
                                        </svg>
                                    )}
                                    <div className="dot">{i + 1}</div>
                                </div>
                                <span>{label}</span>
                            </div>
                        );
                    })}
                </div>

                {/* Step Content */}
                <AnimatePresence mode="wait">
                    {step === 0 && (
                        <motion.div
                            key="welcome"
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95 }}
                            className="step-content welcome-screen"
                        >
                            <div className="welcome-illustration">
                                <Sparkles size={64} className="welcome-icon-glow" />
                            </div>
                            <h2>Seu Novo Companheiro de Estudos</h2>
                            <p className="step-description">
                                O Titier usa inteligência artificial local para ajudar você a entender PDFs,
                                gerar resumos e responder perguntas sem que seus dados saiam do seu computador.
                            </p>
                            <button className="primary-button large" onClick={() => setStep(1)}>
                                Começar Configuração <ChevronRight size={20} />
                            </button>
                        </motion.div>
                    )}

                    {(step === 1 || step === 2) && (
                        <motion.div
                            key={step === 1 ? "step1" : "step2"}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="step-content"
                        >
                            <h2>{step === 1 ? 'Inteligência Artificial' : 'Percepção Visual (OCR)'}</h2>
                            <p className="step-description">
                                {step === 1
                                    ? 'Escolha o cérebro que processará seus estudos.'
                                    : 'Necessário para ler tabelas e imagens nos seus arquivos PDFs.'}
                            </p>

                            {error && (
                                <div className="error-banner">
                                    <AlertCircle size={18} />
                                    {error}
                                </div>
                            )}

                            {/* Featured Model Card */}
                            <div className="featured-model-section">
                                <div className={`model-card featured ${isFeaturedInstalled ? 'installed' : ''}`}>
                                    <div className="model-header">
                                        <h3>{featuredModel.name}</h3>
                                        {isFeaturedInstalled && <Check className="text-green-400" size={24} />}
                                    </div>
                                    <p>{featuredModel.description}</p>
                                    <div className="model-specs">
                                        <span>{featuredModel.size_gb} GB</span>
                                        <span>{featuredModel.vram_required} GB RAM</span>
                                    </div>

                                    {downloads[featuredModel.id] && (downloads[featuredModel.id].status === 'downloading' || downloads[featuredModel.id].status === 'pending') ? (
                                        <div className="compact-download-status">
                                            <Loader2 className="spin" size={16} />
                                            <span>Baixando {downloads[featuredModel.id].progress.toFixed(0)}%</span>
                                        </div>
                                    ) : isFeaturedInstalled ? (
                                        <button className="model-button installed" disabled>
                                            <Check size={18} /> Já Instalado
                                        </button>
                                    ) : (
                                        <button
                                            className="primary-button"
                                            onClick={() => downloadModel(featuredModel.id)}
                                            disabled={!!downloads[featuredModel.id]}
                                        >
                                            <Download size={18} /> Instalar Agora
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Advanced Toggle */}
                            <div className="advanced-options">
                                <button
                                    className="text-button"
                                    onClick={() => setShowAdvanced(!showAdvanced)}
                                >
                                    {showAdvanced ? 'Esconder outros modelos' : 'Desejo escolher outro modelo'}
                                </button>
                            </div>

                            {showAdvanced && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    className="advanced-section"
                                >
                                    <div className="search-bar-container">
                                        <Search className="search-icon" size={20} />
                                        <input
                                            type="text"
                                            placeholder="Pesquisar outros modelos..."
                                            value={searchQuery}
                                            onChange={(e) => handleSearch(e.target.value)}
                                            className="search-input"
                                        />
                                        {isSearching && <Loader2 className="spin" size={18} />}
                                    </div>

                                    <div className="models-grid mini">
                                        {isLoading || isSearching ? (
                                            <div className="loading-state">
                                                <Loader2 className="spin" size={24} />
                                            </div>
                                        ) : (
                                            models.filter(m => m.id !== featuredModel.id).map((model) => (
                                                <div
                                                    key={model.id}
                                                    className={`model-card mini ${model.installed ? 'installed' : ''}`}
                                                >
                                                    <div className="model-header">
                                                        <h4>{model.name}</h4>
                                                        {model.installed ? (
                                                            <Check size={16} className="text-green-400" />
                                                        ) : downloads[model.id] && (downloads[model.id].status === 'downloading' || downloads[model.id].status === 'pending') ? (
                                                            <div className="compact-download-status mini">
                                                                <Loader2 className="spin" size={12} />
                                                                <span>{downloads[model.id].progress.toFixed(0)}%</span>
                                                            </div>
                                                        ) : (
                                                            <button
                                                                className="icon-button"
                                                                onClick={() => downloadModel(model.id)}
                                                                disabled={Object.values(downloads).some(d => d.status === 'downloading' || d.status === 'pending')}
                                                            >
                                                                <Download size={16} />
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </motion.div>
                            )}

                            {isFeaturedInstalled && !Object.values(downloads).some(d => d.status === 'downloading' || d.status === 'pending') && (
                                <button className="primary-button outline" onClick={() => setStep(prev => prev + 1)}>
                                    Próximo Passo <ChevronRight size={18} />
                                </button>
                            )}

                            {/* Allow proceeding if something is downloading in the background */}
                            {(downloads[featuredModel.id]?.status === 'downloading' || downloads[featuredModel.id]?.status === 'pending') && (
                                <button className="primary-button outline" onClick={() => setStep(prev => prev + 1)}>
                                    Continuar Download em Segundo Plano <ChevronRight size={18} />
                                </button>
                            )}
                        </motion.div>
                    )}

                    {step === 3 && (
                        <motion.div
                            key="step3"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="step-content"
                        >
                            <h2>Base de Conhecimento</h2>
                            <p className="step-description">
                                Para terminar, precisamos preparar o motor de busca (Embeddings).
                                Isso permite que o Titier encontre rapidamente a parte relevante dos seus PDFs.
                            </p>

                            {error && (
                                <div className="error-banner">
                                    <AlertCircle size={18} />
                                    {error}
                                </div>
                            )}

                            <div className="embeddings-card glass-panel">
                                <div className="embeddings-info">
                                    <Database size={32} className="embeddings-icon" />
                                    <div>
                                        <h3>bge-m3</h3>
                                        <p>Modelo multilingual de alta qualidade (2.3 GB)</p>
                                    </div>
                                </div>

                                {initializingEmbeddings ? (
                                    <div className="compact-download-status">
                                        <Loader2 className="spin" size={16} />
                                        <span>Inicializando {embeddingsProgress}%</span>
                                    </div>
                                ) : steps.find(s => s.id === 'embeddings')?.completed ? (
                                    <button className="model-button installed" disabled>
                                        <Check size={18} /> Pronto
                                    </button>
                                ) : (
                                    <button className="model-button" onClick={initEmbeddings}>
                                        <Download size={18} /> Inicializar
                                    </button>
                                )}
                            </div>

                            {steps.find(s => s.id === 'embeddings')?.completed && (
                                <button className="primary-button" onClick={() => setStep(4)}>
                                    Finalizar Configuração <ChevronRight size={18} />
                                </button>
                            )}
                        </motion.div>
                    )}

                    {step === 4 && (
                        <motion.div
                            key="step4"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="step-content final-step"
                        >
                            <div className="success-icon">
                                <Check size={48} />
                            </div>
                            <h2>Tudo Pronto!</h2>
                            <p>
                                O Titier está configurado e pronto para ajudar nos seus estudos.
                                Você pode fazer upload de PDFs e conversar sobre o conteúdo.
                            </p>
                            <button className="primary-button large" onClick={onComplete}>
                                <Sparkles size={20} /> Começar a Usar
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}

export default Onboarding;
