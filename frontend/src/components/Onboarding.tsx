import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Loader2, Sparkles, Check, AlertCircle, Database, ChevronRight } from 'lucide-react';

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
    const [downloads, setDownloads] = useState<Record<string, DownloadStatus>>({});
    const [error, setError] = useState<string | null>(null);
    const [initializingEmbeddings, setInitializingEmbeddings] = useState(false);
    const [embeddingsProgress, setEmbeddingsProgress] = useState(0);
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [gpuAvailable, setGpuAvailable] = useState<string | boolean>(false);
    const [recommendedLLM, setRecommendedLLM] = useState<Model | null>(null);

    // Featured models defaults
    const DEFAULT_LLM: Model = {
        id: "llama-3.1-8b-q5",
        name: "Llama 3.1 8B Instruct (Q5)",
        description: "Modelo otimizado (8GB VRAM), ideal para sua RTX 5060.",
        size_gb: 5.7,
        vram_required: 8,
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

        // Polling para status de downloads global
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_URL}/models/download/status`);
                if (res.ok) {
                    const data = await res.json();
                    // Transformar array em mapa por model_id
                    const downloadsMap: Record<string, DownloadStatus> = {};
                    data.forEach((d: any) => {
                        downloadsMap[d.model_id] = d;
                    });
                    setDownloads(downloadsMap);
                }
            } catch (err) {
                console.error("Erro ao buscar status de downloads:", err);
            }
        }, 1000); // 1 segundo

        return () => clearInterval(interval);
    }, []);

    const fetchOnboardingStatus = async () => {
        try {
            const res = await fetch(`${API_URL}/onboarding/status`);
            const data = await res.json();
            setSteps(data.steps);
            setGpuAvailable(data.gpu);
            if (data.recommended_llm) setRecommendedLLM(data.recommended_llm);

            if (data.ready_to_chat) {
                onComplete();
            }
        } catch (err) {
            setError('Erro ao conectar com o backend');
        }
    };



    const [importPath, setImportPath] = useState('');
    const [isImporting, setIsImporting] = useState(false);

    const handleImport = async () => {
        if (!importPath.trim()) return;

        setIsImporting(true);
        setError(null);

        try {
            // Remover aspas que podem vir ao copiar caminho no Windows
            const cleanPath = importPath.replace(/^"|"$/g, '').trim();

            const res = await fetch(`${API_URL}/models/import`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: cleanPath })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Erro ao importar');
            }

            // Sucesso
            setImportPath('');
            fetchOnboardingStatus();
            setStep(prev => prev + 1);

        } catch (err: any) {
            setError(err.message || 'Erro ao importar modelo');
        } finally {
            setIsImporting(false);
        }
    };

    const downloadModel = async (modelId: string) => {
        setError(null);

        try {
            const response = await fetch(`${API_URL}/models/download/${modelId}`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.status === 'already_installed' || data.status === 'paddleocr_model') {
                console.log("Model already installed or is PaddleOCR, advancing step", data);
                fetchOnboardingStatus();
                setStep(prev => prev + 1);
                return;
            }

            console.log("Download started response:", data);
            if (data.status === 'started') {
                console.log("Status is started, advancing step");
                setStep(prev => prev + 1); // Avança automaticamente para o próximo passo

                // Inicializar status no estado local
                setDownloads(prev => ({
                    ...prev,
                    [modelId]: { status: 'pending', progress: 0, downloaded_mb: 0, total_mb: 0, speed_mbps: 0 }
                }));
            } else {
                console.warn("Unknown status:", data.status);
                setError(`Resposta inesperada do servidor: ${data.status || 'sem status'}`);
            }
        } catch (err: any) {
            console.error('Erro ao iniciar download:', err);
            setError(`Falha ao conectar ao servidor: ${err.message}`);
            window.alert(`Erro ao iniciar download: \n${err.message}`);
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

    const isAnyDownloadActive = Object.values(downloads).some(
        d => d.status === 'downloading' || d.status === 'pending'
    );

    const featuredModel = step === 1 ? (recommendedLLM || DEFAULT_LLM) : DEFAULT_OCR;
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

                        {steps.length > 0 && (
                            <div className="gpu-badge">
                                <Sparkles size={14} />
                                Aceleração por Hardware: <span>{gpuAvailable ? `Ativada (${gpuAvailable})` : 'Detectando...'}</span>
                            </div>
                        )}
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
                            const llmId = (recommendedLLM || DEFAULT_LLM).id;
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

                        const radius = 18; // Reverted to 18 (44px total), kept thicker stroke
                        const circumference = 2 * Math.PI * radius;
                        const offset = circumference - (activeProgress / 100) * circumference;

                        return (
                            <div key={i} className={`step-dot ${step >= i ? 'active' : ''} ${isCurrent ? 'current' : ''}`}>
                                <div className="dot-container">
                                    {showProgress && (
                                        <svg className="progress-ring" width="44" height="44">
                                            {/* Background circle for context */}
                                            <circle
                                                stroke="var(--glass-border)"
                                                strokeWidth="6"
                                                fill="transparent"
                                                r={radius}
                                                cx="22"
                                                cy="22"
                                            />
                                            <circle
                                                className="progress-ring__circle"
                                                stroke="var(--accent)"
                                                strokeWidth="6"
                                                strokeLinecap="round"
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
                                        <div className="model-status-installed">
                                            <button className="model-button installed" disabled>
                                                <Check size={18} /> Já Instalado
                                            </button>
                                            {/* Permite baixar o recomendado mesmo se já tiver outro modelo */}
                                            {steps.find(s => s.id === (step === 1 ? 'llm' : 'ocr'))?.completed && !downloads[featuredModel.id] && (
                                                <p className="status-note">Você já possui um modelo configurado, mas pode baixar este se desejar.</p>
                                            )}
                                        </div>
                                    ) : (
                                        <button
                                            className="primary-button"
                                            onClick={() => downloadModel(featuredModel.id)}
                                            disabled={downloads[featuredModel.id]?.status === 'downloading' || downloads[featuredModel.id]?.status === 'pending'}
                                        >
                                            {downloads[featuredModel.id]?.status === 'failed' ? (
                                                <><AlertCircle size={18} /> Tentar Novamente</>
                                            ) : (
                                                <><Download size={18} /> Instalar Agora</>
                                            )}
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Import Manually */}
                            <div className="advanced-options">
                                {step === 1 && (
                                    <button
                                        className="text-button"
                                        onClick={() => setShowAdvanced(!showAdvanced)}
                                    >
                                        {showAdvanced ? 'Cancelar Importação' : 'Já possuo um modelo (Importar .gguf)'}
                                    </button>
                                )}
                            </div>

                            {showAdvanced && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    className="advanced-section"
                                >
                                    <div className="import-section glass-panel">
                                        <h4>Importar Modelo Local</h4>
                                        <p>Cole o caminho completo do arquivo .gguf no seu computador.</p>

                                        <div className="search-bar-container">
                                            <input
                                                type="text"
                                                placeholder="C:\Users\Nome\Downloads\modelo.gguf"
                                                value={importPath}
                                                onChange={(e) => setImportPath(e.target.value)}
                                                className="search-input"
                                            />
                                            <button
                                                className="primary-button small"
                                                onClick={handleImport}
                                                disabled={!importPath || isImporting}
                                            >
                                                {isImporting ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
                                                Importar
                                            </button>
                                        </div>
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
                                        <h3>MiniLM-L12 (Multilingual)</h3>
                                        <p>Motor de busca leve e otimizado (420 MB)</p>
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
                            <button
                                className={`primary-button large ${isAnyDownloadActive ? 'disabled' : ''}`}
                                onClick={onComplete}
                                disabled={isAnyDownloadActive}
                            >
                                {isAnyDownloadActive ? (
                                    <>
                                        <Loader2 className="spin" size={20} /> Preparando Modelos...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles size={20} /> Começar a Usar
                                    </>
                                )}
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </motion.div>
        </div>
    );
}

export default Onboarding;
