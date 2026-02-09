import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Download,
    Check,
    Loader2,
    Sparkles,
    ChevronRight,
    AlertCircle,
    Database
} from 'lucide-react';

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
}

interface OnboardingProps {
    onComplete: () => void;
}

const API_URL = 'http://127.0.0.1:8000';

export function Onboarding({ onComplete }: OnboardingProps) {
    const [step, setStep] = useState(0);
    const [steps, setSteps] = useState<OnboardingStep[]>([]);
    const [models, setModels] = useState<Model[]>([]);
    const [downloading, setDownloading] = useState<string | null>(null);
    const [downloadProgress, setDownloadProgress] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const [initializingEmbeddings, setInitializingEmbeddings] = useState(false);
    const [embeddingsProgress, setEmbeddingsProgress] = useState(0);

    useEffect(() => {
        fetchOnboardingStatus();
        fetchModels();
    }, []);

    const fetchOnboardingStatus = async () => {
        try {
            const res = await fetch(`${API_URL}/onboarding/status`);
            const data = await res.json();
            setSteps(data.steps);

            // Se já tem modelo, pular para o final
            if (data.ready_to_chat) {
                onComplete();
            }
        } catch (err) {
            setError('Erro ao conectar com o backend');
        }
    };

    const fetchModels = async () => {
        try {
            const res = await fetch(`${API_URL}/models/recommended`);
            const data = await res.json();
            setModels(data);
        } catch (err) {
            console.error('Erro ao buscar modelos:', err);
        }
    };

    const downloadModel = async (modelId: string) => {
        setDownloading(modelId);
        setDownloadProgress(0);
        setError(null);

        try {
            // Iniciar download
            const res = await fetch(`${API_URL}/models/download/${modelId}`, {
                method: 'POST'
            });
            const data = await res.json();

            if (data.status === 'already_installed') {
                setDownloading(null);
                fetchModels();
                fetchOnboardingStatus();
                return;
            }

            // Polling de progresso
            const pollProgress = async () => {
                const statusRes = await fetch(`${API_URL}/models/download/${modelId}/status`);
                const status = await statusRes.json();

                if (status.status === 'downloading' || status.status === 'pending') {
                    setDownloadProgress(status.progress || 0);
                    setTimeout(pollProgress, 1000);
                } else if (status.status === 'completed') {
                    setDownloading(null);
                    setDownloadProgress(100);
                    fetchModels();
                    fetchOnboardingStatus();
                } else if (status.status === 'failed') {
                    setError(status.error || 'Erro no download');
                    setDownloading(null);
                }
            };

            setTimeout(pollProgress, 2000);
        } catch (err) {
            setError('Erro ao iniciar download');
            setDownloading(null);
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

            // Polling de progresso
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

    return (
        <div className="onboarding-container">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="onboarding-card glass-panel"
            >
                {/* Header */}
                <div className="onboarding-header">
                    <Sparkles size={40} className="onboarding-icon" />
                    <h1>Bem-vindo ao Titier</h1>
                    <p>Vamos configurar seu assistente de estudos</p>
                </div>

                {/* Steps Indicator */}
                <div className="steps-indicator">
                    {['Modelo IA', 'Embeddings', 'Pronto!'].map((label, i) => (
                        <div key={i} className={`step-dot ${step >= i ? 'active' : ''}`}>
                            <div className="dot">{i + 1}</div>
                            <span>{label}</span>
                        </div>
                    ))}
                </div>

                {/* Step Content */}
                <AnimatePresence mode="wait">
                    {step === 0 && (
                        <motion.div
                            key="step0"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="step-content"
                        >
                            <h2>Escolha um Modelo de IA</h2>
                            <p className="step-description">
                                Selecione um modelo para baixar. Modelos maiores são mais precisos.
                            </p>

                            {error && (
                                <div className="error-banner">
                                    <AlertCircle size={18} />
                                    {error}
                                </div>
                            )}

                            <div className="models-grid">
                                {models.map((model) => (
                                    <div
                                        key={model.id}
                                        className={`model-card ${model.recommended ? 'recommended' : ''} ${model.installed ? 'installed' : ''}`}
                                    >
                                        {model.recommended && <span className="badge">Recomendado</span>}
                                        {model.installed && <span className="badge installed">Instalado</span>}

                                        <h3>{model.name}</h3>
                                        <p>{model.description}</p>

                                        <div className="model-specs">
                                            <span>{model.size_gb} GB</span>
                                            <span>{model.vram_required} GB VRAM</span>
                                        </div>

                                        {downloading === model.id ? (
                                            <div className="download-progress">
                                                <div className="progress-header">
                                                    <Loader2 className="spin" size={16} />
                                                    <span className="progress-text">
                                                        {downloadProgress < 100 ? 'Baixando...' : 'Finalizando...'}
                                                    </span>
                                                    <span className="progress-percent">{downloadProgress.toFixed(0)}%</span>
                                                </div>
                                                <div className="progress-bar">
                                                    <div
                                                        className="progress-fill"
                                                        style={{ width: `${downloadProgress}%` }}
                                                    />
                                                </div>
                                                <div className="progress-details">
                                                    <span>{(model.size_gb * downloadProgress / 100).toFixed(1)} / {model.size_gb} GB</span>
                                                </div>
                                            </div>
                                        ) : model.installed ? (
                                            <button className="model-button installed" disabled>
                                                <Check size={18} /> Instalado
                                            </button>
                                        ) : (
                                            <button
                                                className="model-button"
                                                onClick={() => downloadModel(model.id)}
                                                disabled={!!downloading}
                                            >
                                                <Download size={18} /> Baixar
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>

                            {models.some(m => m.installed) && (
                                <button className="primary-button" onClick={() => setStep(1)}>
                                    Continuar <ChevronRight size={18} />
                                </button>
                            )}
                        </motion.div>
                    )}

                    {step === 1 && (
                        <motion.div
                            key="step1"
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            className="step-content"
                        >
                            <h2>Modelo de Embeddings</h2>
                            <p className="step-description">
                                O modelo de embeddings é necessário para indexar e buscar conteúdo nos PDFs.
                                Este download acontece apenas uma vez.
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
                                    <div className="download-progress">
                                        <div className="progress-header">
                                            <Loader2 className="spin" size={16} />
                                            <span className="progress-text">Baixando modelo de embeddings...</span>
                                            <span className="progress-percent">{embeddingsProgress}%</span>
                                        </div>
                                        <div className="progress-bar">
                                            <div
                                                className="progress-fill"
                                                style={{ width: `${embeddingsProgress}%` }}
                                            />
                                        </div>
                                        <div className="progress-details">
                                            <span>Isso pode levar alguns minutos na primeira vez</span>
                                        </div>
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
                                <button className="primary-button" onClick={() => setStep(2)}>
                                    Continuar <ChevronRight size={18} />
                                </button>
                            )}
                        </motion.div>
                    )}

                    {step === 2 && (
                        <motion.div
                            key="step2"
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
