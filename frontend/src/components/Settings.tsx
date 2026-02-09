
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    X,
    Settings as SettingsIcon,
    HardDrive,
    Database,
    Trash2,
    Download,
    Check,
    Loader2,
    AlertTriangle,
    FileText
} from 'lucide-react';
import './Settings.css';
import './Onboarding.css';

const API_URL = 'http://127.0.0.1:8000';

interface SettingsProps {
    isOpen: boolean;
    onClose: () => void;
}

interface Model {
    id: string;
    name: string;
    description: string;
    size_gb: number;
    vram_required: number;
    installed: boolean;
    recommended?: boolean;
    filename: string;
}

interface WebDocument {
    source: string;
    file_hash: string;
    chunks_count: number;
}

interface SystemStats {
    platform: string;
    backend: string;
    gpu_available: boolean;
    vector_store: {
        points_count?: number;
        indexed_vectors_count?: number;
        status?: string;
        documents_count?: number;
    };
    indexed_documents?: WebDocument[];
    version?: string;
}

interface DownloadStatus {
    status: string;
    progress: number;
    downloaded_mb: number;
    total_mb: number;
    speed_mbps: number;
    error?: string;
}

export function Settings({ isOpen, onClose }: SettingsProps) {
    const [activeTab, setActiveTab] = useState<'models' | 'database'>('models');
    const [stats, setStats] = useState<SystemStats | null>(null);
    const [models, setModels] = useState<Model[]>([]);
    const [downloading, setDownloading] = useState<string | null>(null);
    const [downloadStatus, setDownloadStatus] = useState<DownloadStatus | null>(null);
    const [isClearing, setIsClearing] = useState(false);
    const [deletingDoc, setDeletingDoc] = useState<string | null>(null);
    const [hoveredModel, setHoveredModel] = useState<string | null>(null);
    const [confirmAction, setConfirmAction] = useState<{
        title: string;
        message: string;
        action: () => Promise<void>;
    } | null>(null);

    useEffect(() => {
        if (isOpen) {
            fetchStats();
            fetchModels();
        }
    }, [isOpen]);

    const fetchStats = async () => {
        try {
            console.log('Buscando estatísticas atualizadas...');
            const statusRes = await fetch(`${API_URL}/status?t=${Date.now()}`);
            const statusData = await statusRes.json();

            const docsRes = await fetch(`${API_URL}/documents?t=${Date.now()}`);
            const docsData = await docsRes.json();

            console.log('Docs recebidos:', docsData.indexed_documents?.length);

            setStats({
                ...statusData,
                version: statusData.version || '0.2.0',
                indexed_documents: docsData.indexed_documents || []
            });
        } catch (err) {
            console.error('Erro ao buscar status:', err);
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
        setDownloadStatus({ status: 'starting', progress: 0, downloaded_mb: 0, total_mb: 0, speed_mbps: 0 });

        try {
            const res = await fetch(`${API_URL}/models/download/${modelId}`, {
                method: 'POST'
            });
            const data = await res.json();

            if (data.status === 'already_installed') {
                setDownloading(null);
                setDownloadStatus(null);
                fetchModels();
                return;
            }

            const pollProgress = async () => {
                try {
                    const statusRes = await fetch(`${API_URL}/models/download/${modelId}/status`);
                    const status = await statusRes.json();

                    if (status.status === 'downloading' || status.status === 'pending') {
                        setDownloadStatus(status);
                        setTimeout(pollProgress, 1000);
                    } else if (status.status === 'completed') {
                        setDownloadStatus({ ...status, progress: 100 });
                        // Pequeno delay para mostrar 100%
                        setTimeout(() => {
                            setDownloading(null);
                            setDownloadStatus(null);
                            fetchModels();
                        }, 500);
                    } else if (status.status === 'failed') {
                        setDownloading(null);
                        setDownloadStatus(null);
                        alert('Erro no download: ' + (status.error || 'Erro desconhecido'));
                    }
                } catch (e) {
                    console.error('Erro no polling:', e);
                    setDownloading(null);
                    setDownloadStatus(null);
                }
            };
            setTimeout(pollProgress, 2000);
        } catch (err) {
            setDownloading(null);
            setDownloadStatus(null);
            console.error(err);
            alert('Erro ao iniciar download');
        }
    };

    const requestDeleteModel = (model: Model) => {
        setConfirmAction({
            title: 'Excluir Modelo',
            message: `Tem certeza que deseja remover o modelo "${model.name}"? Você precisará baixá-lo novamente para usar.`,
            action: () => deleteModel(model.filename)
        });
    };

    const deleteModel = async (filename: string) => {
        setConfirmAction(null);
        try {
            const res = await fetch(`${API_URL}/models/${filename}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                fetchModels();
            } else {
                alert('Erro ao remover modelo');
            }
        } catch (err) {
            console.error(err);
            alert('Erro ao remover modelo');
        }
    };

    const requestClearDatabase = () => {
        setConfirmAction({
            title: 'Limpar Banco de Dados',
            message: 'Tem certeza? Isso apagará todos os documentos indexados e não pode ser desfeito.',
            action: clearDatabase
        });
    };

    const requestDeleteDocument = (filename: string) => {
        setConfirmAction({
            title: 'Remover Documento',
            message: `Tem certeza que deseja remover "${filename}"?`,
            action: () => deleteDocument(filename)
        });
    };

    const clearDatabase = async () => {
        setConfirmAction(null);
        console.log('Iniciando limpeza do banco de dados...');
        setIsClearing(true);
        try {
            const res = await fetch(`${API_URL}/documents`, { method: 'DELETE' });
            console.log('Resposta do delete /documents:', res.status, res.statusText);

            if (!res.ok) {
                const errorData = await res.json();
                console.error('Erro detalhado do backend:', errorData);
                throw new Error('Falha na resposta do servidor');
            }

            console.log('Banco limpo. Atualizando stats...');
            await fetchStats();
            console.log('Stats atualizados.');
            alert('Banco de dados limpo com sucesso!');
        } catch (err) {
            console.error('Erro ao limpar banco de dados:', err);
            alert('Erro ao limpar banco de dados (ver console)');
        } finally {
            setIsClearing(false);
        }
    };

    const deleteDocument = async (filename: string) => {
        setConfirmAction(null);
        console.log(`Iniciando remoção do documento: ${filename}`);
        setDeletingDoc(filename);
        try {
            const res = await fetch(`${API_URL}/documents/${encodeURIComponent(filename)}`, {
                method: 'DELETE'
            });
            console.log(`Resposta do delete /documents/${filename}:`, res.status);

            if (res.ok) {
                console.log('Documento removido. Atualizando stats...');
                await fetchStats();
                console.log('Stats atualizados após remoção.');
            } else {
                const errorData = await res.json();
                console.error('Erro ao remover documento (backend):', errorData);
                alert(`Erro ao remover documento: ${errorData.detail || 'Erro desconhecido'}`);
            }
        } catch (err) {
            console.error('Erro de conexão/frontend ao remover documento:', err);
            alert('Erro de conexão ao remover documento');
        } finally {
            setDeletingDoc(null);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="settings-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="settings-modal glass-panel"
            >
                <div className="settings-header">
                    <h2><SettingsIcon /> Configurações</h2>
                    <button className="close-button" onClick={onClose}><X /></button>
                </div>

                <AnimatePresence>
                    {confirmAction && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="confirmation-overlay"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <motion.div
                                initial={{ scale: 0.9, y: 20 }}
                                animate={{ scale: 1, y: 0 }}
                                exit={{ scale: 0.9, y: 20 }}
                                className="confirmation-modal"
                            >
                                <AlertTriangle size={48} color="#ef4444" style={{ marginBottom: 16 }} />
                                <h3>{confirmAction.title}</h3>
                                <p>{confirmAction.message}</p>
                                <div className="confirmation-actions">
                                    <button
                                        className="cancel-btn"
                                        onClick={() => setConfirmAction(null)}
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        className="confirm-btn"
                                        onClick={confirmAction.action}
                                    >
                                        Confirmar
                                    </button>
                                </div>
                            </motion.div>
                        </motion.div>
                    )}
                </AnimatePresence>

                <div className="settings-content">
                    <div className="settings-sidebar">
                        <button
                            className={`settings-tab ${activeTab === 'models' ? 'active' : ''}`}
                            onClick={() => setActiveTab('models')}
                        >
                            <HardDrive size={18} /> Modelos IA
                        </button>
                        <button
                            className={`settings-tab ${activeTab === 'database' ? 'active' : ''}`}
                            onClick={() => setActiveTab('database')}
                        >
                            <Database size={18} /> Banco de Dados
                        </button>
                    </div>

                    <div className="settings-panel">
                        {activeTab === 'models' && (
                            <div className="panel-section">
                                <h3>Gerenciar Modelos</h3>
                                <div className="models-grid">
                                    {models.map(model => (
                                        <div key={model.id} className={`model-card ${model.installed ? 'installed' : ''}`}>
                                            <h4>{model.name}</h4>
                                            <p>{model.description}</p>
                                            <div className="model-specs">
                                                <span>{model.size_gb} GB</span>
                                                <span>{model.vram_required} GB VRAM</span>
                                            </div>

                                            {downloading === model.id ? (
                                                <div className="model-download-status">
                                                    <div
                                                        className="model-download-bar"
                                                        style={{ width: `${downloadStatus?.progress || 0}%` }}
                                                    />
                                                    <div className="model-download-text">
                                                        <Loader2 className="spin" size={14} />
                                                        <span>{downloadStatus?.progress?.toFixed(0)}%</span>
                                                        {downloadStatus?.speed_mbps ? (
                                                            <span style={{ opacity: 0.7, fontSize: '0.8em' }}>
                                                                ({downloadStatus.speed_mbps.toFixed(1)} MB/s)
                                                            </span>
                                                        ) : null}
                                                    </div>
                                                </div>
                                            ) : model.installed ? (
                                                <button
                                                    className={`model-button installed ${hoveredModel === model.id ? 'danger' : ''}`}
                                                    onMouseEnter={() => setHoveredModel(model.id)}
                                                    onMouseLeave={() => setHoveredModel(null)}
                                                    onClick={() => requestDeleteModel(model)}
                                                >
                                                    {hoveredModel === model.id ? (
                                                        <>
                                                            <Trash2 size={16} /> Excluir
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Check size={16} /> Instalado
                                                        </>
                                                    )}
                                                </button>
                                            ) : (
                                                <button className="model-button" onClick={() => downloadModel(model.id)}>
                                                    <Download size={16} /> Baixar
                                                </button>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {activeTab === 'database' && stats && (
                            <div className="panel-section">
                                <h3>Documentos Indexados ({stats.vector_store.documents_count || 0})</h3>
                                <div className="documents-list">
                                    {stats.indexed_documents && stats.indexed_documents.length > 0 ? (
                                        stats.indexed_documents.map((doc, i) => (
                                            <div key={i} className="document-item">
                                                <div className="document-info">
                                                    <FileText size={20} className="text-secondary" />
                                                    <div className="document-name">{doc.source}</div>
                                                </div>
                                                <button
                                                    className="delete-doc-btn"
                                                    onClick={() => requestDeleteDocument(doc.source)}
                                                    disabled={deletingDoc === doc.source}
                                                    title="Remover documento"
                                                >
                                                    {deletingDoc === doc.source ? (
                                                        <Loader2 size={18} className="spin" />
                                                    ) : (
                                                        <Trash2 size={18} />
                                                    )}
                                                </button>
                                            </div>
                                        ))
                                    ) : (
                                        <p style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                            Nenhum documento indexado.
                                        </p>
                                    )}
                                </div>

                                <div className="danger-zone" style={{ marginTop: 'auto' }}>
                                    <h3>Zona de Perigo</h3>
                                    <div className="danger-action">
                                        <p>Apagar todos os documentos indexados e limpar o banco de dados.</p>
                                        <button
                                            className="danger-button"
                                            onClick={requestClearDatabase}
                                            disabled={isClearing}
                                        >
                                            {isClearing ? <Loader2 className="spin" /> : <Trash2 size={18} />}
                                            {isClearing ? 'Limpando...' : 'Limpar Tudo'}
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
