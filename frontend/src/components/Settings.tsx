
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
    FileText,
    MessageSquare,
    RotateCcw,

    Save,
    Palette,
    Sun,
    Moon
} from 'lucide-react';
import './Settings.css';
import './Onboarding.css';

const API_URL = 'http://127.0.0.1:8000';

interface SettingsProps {
    isOpen: boolean;
    onClose: () => void;
    themeMode: 'light' | 'dark';
    setThemeMode: (mode: 'light' | 'dark') => void;
    accentColor: string;
    setAccentColor: (color: string) => void;
    colorTemp: number;
    setColorTemp: (temp: number) => void;

    pdfBgColor: string;
    setPdfBgColor: (color: string) => void;
    applyPdfTint: boolean;
    setApplyPdfTint: (apply: boolean) => void;
    multiWindowMode: boolean;
    setMultiWindowMode: (enabled: boolean) => void;
    defaultMultiChatContext: boolean;
    setDefaultMultiChatContext: (enabled: boolean) => void;
    onClearAllSessions: () => Promise<void>;
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



export function Settings({
    isOpen,
    onClose,
    themeMode,
    setThemeMode,
    accentColor,
    setAccentColor,
    colorTemp,

    setColorTemp,
    pdfBgColor,
    setPdfBgColor,
    applyPdfTint,
    setApplyPdfTint,
    multiWindowMode,
    setMultiWindowMode,
    defaultMultiChatContext,
    setDefaultMultiChatContext,
    onClearAllSessions
}: SettingsProps) {
    const [activeTab, setActiveTab] = useState<'models' | 'database' | 'prompts' | 'graphics'>('models');
    const [stats, setStats] = useState<SystemStats | null>(null);
    const [models, setModels] = useState<Model[]>([]);

    const [isClearing, setIsClearing] = useState(false);
    const [deletingDoc, setDeletingDoc] = useState<string | null>(null);

    const [confirmAction, setConfirmAction] = useState<{
        title: string;
        message: string;
        action: () => Promise<void>;
    } | null>(null);

    // Prompt states
    const [promptBase, setPromptBase] = useState('');
    const [promptRag, setPromptRag] = useState('');
    const [promptVision, setPromptVision] = useState('');
    const [isSavingPrompts, setIsSavingPrompts] = useState(false);
    const [promptFeedback, setPromptFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

    useEffect(() => {
        if (isOpen) {
            fetchStats();
            fetchModels();
            fetchPrompts();
        }
    }, [isOpen]);

    const fetchPrompts = async () => {
        try {
            const res = await fetch(`${API_URL}/prompts`);
            const data = await res.json();
            setPromptBase(data.active.system_base || '');
            setPromptRag(data.active.system_rag || '');
            setPromptVision(data.active.system_vision || '');
        } catch (err) {
            console.error('Erro ao buscar prompts:', err);
        }
    };

    const handleSavePrompts = async () => {
        setIsSavingPrompts(true);
        setPromptFeedback(null);
        try {
            const res = await fetch(`${API_URL}/prompts`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    system_base: promptBase,
                    system_rag: promptRag,
                    system_vision: promptVision
                })
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Erro ao salvar');
            }
            setPromptFeedback({ type: 'success', msg: 'Prompts salvos com sucesso!' });
            setTimeout(() => setPromptFeedback(null), 3000);
        } catch (err: any) {
            setPromptFeedback({ type: 'error', msg: err.message || 'Erro ao salvar prompts' });
        } finally {
            setIsSavingPrompts(false);
        }
    };

    const handleResetPrompts = async () => {
        try {
            const res = await fetch(`${API_URL}/prompts`, { method: 'DELETE' });
            if (res.ok) {
                const data = await res.json();
                setPromptBase(data.active.system_base || '');
                setPromptRag(data.active.system_rag || '');
                setPromptVision(data.active.system_vision || '');
                setPromptFeedback({ type: 'success', msg: 'Prompts restaurados para os padrões!' });
                setTimeout(() => setPromptFeedback(null), 3000);
            }
        } catch (err) {
            console.error('Erro ao restaurar prompts:', err);
            setPromptFeedback({ type: 'error', msg: 'Erro ao restaurar prompts' });
        }
    };

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
            const res = await fetch(`${API_URL}/models`);
            const data = await res.json();

            // Deduplicação: Se um modelo está em 'installed', remover versões dele do 'recommended'
            // baseando-se no filename para garantir que não apareça duplicado
            const installedFiles = new Set(data.installed.map((m: Model) => m.filename));
            const filteredRecommended = data.recommended.filter((m: Model) => !installedFiles.has(m.filename));

            setModels([...data.installed, ...filteredRecommended]);
        } catch (err) {
            console.error('Erro ao buscar modelos:', err);
        }
    };

    const [importPath, setImportPath] = useState('');
    const [isImporting, setIsImporting] = useState(false);

    const handleImport = async () => {
        if (!importPath.trim()) return;
        setIsImporting(true);
        try {
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

            alert('Modelo importado com sucesso!');
            setImportPath('');
            fetchModels();
        } catch (err: any) {
            alert(err.message || 'Erro ao importar modelo');
        } finally {
            setIsImporting(false);
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
                        <button
                            className={`settings-tab ${activeTab === 'prompts' ? 'active' : ''}`}
                            onClick={() => setActiveTab('prompts')}
                        >
                            <MessageSquare size={18} /> Prompts
                        </button>
                        <button
                            className={`settings-tab ${activeTab === 'graphics' ? 'active' : ''}`}
                            onClick={() => setActiveTab('graphics')}
                        >
                            <Palette size={18} /> Gráficos
                        </button>

                        {stats && (
                            <div className="settings-sidebar-footer">
                                <div className="sidebar-stat">
                                    <span className="stat-label">Architecture</span>
                                    <span className={`stat-value ${stats.gpu_available ? 'success' : 'warning'}`}>
                                        {stats.backend?.toUpperCase() || 'UNKNOWN'}
                                    </span>
                                </div>
                                <div className="sidebar-stat">
                                    <span className="stat-label">Core Version</span>
                                    <span className="stat-value">{stats.version || '0.2.0'}</span>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="settings-panel">
                        {activeTab === 'models' && (
                            <div className="panel-section">
                                <div className="models-container">
                                    {/* Seção de Modelos Instalados */}
                                    <div className="models-subsection">
                                        <h3>Modelos Instalados</h3>
                                        <div className="models-grid">
                                            {models.filter(m => m.installed).length > 0 ? (
                                                models.filter(m => m.installed).map(model => (
                                                    <div key={model.id} className="model-card installed">
                                                        <h4>{model.name}</h4>
                                                        <p>{model.description}</p>
                                                        <div className="model-specs">
                                                            <span>{model.size_gb} GB</span>
                                                            <span>{model.vram_required} GB VRAM</span>
                                                        </div>

                                                        <div className="model-actions-row">
                                                            <button className="model-button installed" disabled>
                                                                <Check size={16} /> Instalado
                                                            </button>
                                                            <button
                                                                className="model-button delete"
                                                                onClick={() => requestDeleteModel(model)}
                                                                title="Excluir modelo"
                                                            >
                                                                <Trash2 size={18} />
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))
                                            ) : (
                                                <div className="empty-state">
                                                    <p>Nenhum modelo instalado.</p>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Seção de Importação Manual */}
                                    <div className="models-subsection" style={{ marginTop: '40px' }}>
                                        <h3 style={{ borderBottomColor: 'var(--glass-border)' }}>Importar Modelo Local</h3>
                                        <div className="import-section glass-panel">
                                            <p style={{ marginBottom: '10px', fontSize: '0.9em', color: 'var(--text-secondary)' }}>
                                                Adicione modelos <strong>.gguf</strong> manualmente apontando o caminho do arquivo no seu computador.
                                            </p>

                                            <div style={{ display: 'flex', gap: '10px' }}>
                                                <input
                                                    type="text"
                                                    placeholder="C:\Caminho\Para\modelo.gguf"
                                                    value={importPath}
                                                    onChange={(e) => setImportPath(e.target.value)}
                                                    className="search-input"
                                                    style={{ flex: 1 }}
                                                />
                                                <button
                                                    className="model-button"
                                                    onClick={handleImport}
                                                    disabled={!importPath || isImporting}
                                                    style={{ minWidth: '120px' }}
                                                >
                                                    {isImporting ? <Loader2 className="spin" size={16} /> : <Download size={16} />}
                                                    Importar
                                                </button>
                                            </div>
                                        </div>
                                    </div>
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
                                            {isClearing ? 'Limpando...' : 'Limpar Bancos'}
                                        </button>
                                    </div>
                                    <div className="danger-action" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid rgba(239, 68, 68, 0.2)' }}>
                                        <p>Apagar todo o histórico de conversas ("Minhas Conversas").</p>
                                        <button
                                            className="danger-button"
                                            onClick={() => {
                                                setConfirmAction({
                                                    title: 'Apagar Histórico',
                                                    message: 'Tem certeza que deseja apagar todas as conversas? Isso não pode ser desfeito.',
                                                    action: async () => {
                                                        setConfirmAction(null);
                                                        await onClearAllSessions();
                                                    }
                                                });
                                            }}
                                        >
                                            <Trash2 size={18} />
                                            Apagar Conversas
                                        </button>
                                    </div>
                                </div>
                            </div>
                        )}

                        {activeTab === 'prompts' && (
                            <div className="panel-section">
                                <h3>System Prompts</h3>
                                <p className="prompt-description">
                                    Personalize os prompts que definem o comportamento da IA. Alterações são aplicadas imediatamente nas próximas conversas.
                                </p>

                                <div className="prompt-group">
                                    <label className="prompt-label">Prompt Base (sem documentos)</label>
                                    <p className="prompt-hint">Usado quando o usuário faz uma pergunta sem documentos indexados.</p>
                                    <textarea
                                        className="prompt-textarea"
                                        value={promptBase}
                                        onChange={(e) => setPromptBase(e.target.value)}
                                        rows={8}
                                    />
                                </div>

                                <div className="prompt-group">
                                    <label className="prompt-label">Prompt RAG (com documentos)</label>
                                    <p className="prompt-hint">
                                        Usado quando há contexto dos PDFs. O placeholder <code>{'{context}'}</code> é <strong>obrigatório</strong> — será substituído pelo conteúdo dos documentos.
                                    </p>
                                    <textarea
                                        className="prompt-textarea"
                                        value={promptRag}
                                        onChange={(e) => setPromptRag(e.target.value)}
                                        rows={10}
                                    />
                                </div>

                                <div className="prompt-group">
                                    <label className="prompt-label">Prompt de Visão (OCR)</label>
                                    <p className="prompt-hint">Usado na análise de imagens e extração de texto por OCR.</p>
                                    <textarea
                                        className="prompt-textarea"
                                        value={promptVision}
                                        onChange={(e) => setPromptVision(e.target.value)}
                                        rows={3}
                                    />
                                </div>

                                {promptFeedback && (
                                    <div className={`prompt-feedback ${promptFeedback.type}`}>
                                        {promptFeedback.type === 'success' ? <Check size={16} /> : <AlertTriangle size={16} />}
                                        {promptFeedback.msg}
                                    </div>
                                )}

                                <div className="prompt-actions">
                                    <button
                                        className="prompt-btn save"
                                        onClick={handleSavePrompts}
                                        disabled={isSavingPrompts}
                                    >
                                        {isSavingPrompts ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
                                        Salvar Prompts
                                    </button>
                                    <button
                                        className="prompt-btn reset"
                                        onClick={handleResetPrompts}
                                    >
                                        <RotateCcw size={16} /> Restaurar Padrão
                                    </button>
                                </div>
                            </div>
                        )}

                        {activeTab === 'graphics' && (
                            <div className="panel-section">
                                <h3>Aparência e Gráficos</h3>

                                <div className="prompt-group">
                                    <label className="prompt-label">Tema do Sistema</label>
                                    <p className="prompt-hint">Escolha entre o modo claro e escuro.</p>
                                    <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                                        <button
                                            className={`model-button ${themeMode === 'light' ? 'installed' : ''}`}
                                            onClick={() => setThemeMode('light')}
                                            style={{ flex: 1, justifyContent: 'center', background: themeMode === 'light' ? 'var(--accent)' : 'rgba(var(--accent-rgb), 0.1)', color: themeMode === 'light' ? '#fff' : 'var(--text-primary)' }}
                                        >
                                            <Sun size={18} /> Claro
                                        </button>
                                        <button
                                            className={`model-button ${themeMode === 'dark' ? 'installed' : ''}`}
                                            onClick={() => setThemeMode('dark')}
                                            style={{ flex: 1, justifyContent: 'center', background: themeMode === 'dark' ? 'var(--accent)' : 'rgba(var(--accent-rgb), 0.1)', color: themeMode === 'dark' ? '#fff' : 'var(--text-primary)' }}
                                        >
                                            <Moon size={18} /> Escuro
                                        </button>
                                    </div>
                                </div>

                                <div className="prompt-group" style={{ marginTop: '30px' }}>
                                    <label className="prompt-label">Cor de Destaque</label>
                                    <p className="prompt-hint">Selecione a cor principal da aplicação. Afeta botões, bordas e detalhes.</p>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '10px' }}>
                                        <input
                                            type="color"
                                            value={accentColor}
                                            onChange={(e) => setAccentColor(e.target.value)}
                                            style={{
                                                background: 'none',
                                                border: 'none',
                                                padding: 0,
                                                width: '60px',
                                                height: '40px',
                                                cursor: 'pointer'
                                            }}
                                        />
                                        <button
                                            className="model-button"
                                            onClick={() => setAccentColor('#6366f1')}
                                            title="Restaurar Roxo Titier"
                                            style={{ width: 'auto', gap: '6px', height: '40px', display: 'flex', alignItems: 'center' }}
                                        >
                                            <RotateCcw size={14} /> Roxo Titier
                                        </button>
                                    </div>
                                </div>

                                <div className="prompt-group" style={{ marginTop: '30px' }}>
                                    <label className="prompt-label">Fundo do PDF</label>
                                    <p className="prompt-hint">Personalize a cor de fundo da área de visualização do documento.</p>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '10px' }}>
                                        <input
                                            type="color"
                                            value={pdfBgColor}
                                            onChange={(e) => setPdfBgColor(e.target.value)}
                                            style={{
                                                background: 'none',
                                                border: 'none',
                                                padding: 0,
                                                width: '100px',
                                                height: '40px',
                                                cursor: 'pointer'
                                            }}
                                        />
                                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                            <button
                                                className="model-button installed"
                                                onClick={() => setPdfBgColor('#f0f0f5')} // Light Default
                                                title="Padrão Claro"
                                                style={{ padding: '0 12px', width: 'auto', height: '40px', display: 'flex', alignItems: 'center' }}
                                            >
                                                Original
                                            </button>
                                            <button
                                                className="model-button installed"
                                                onClick={() => setPdfBgColor('#1a1a24')} // Dark Default
                                                title="Padrão Escuro"
                                                style={{ padding: '0 12px', width: 'auto', background: '#1a1a24', color: '#fff', height: '40px', display: 'flex', alignItems: 'center' }}
                                            >
                                                Dark
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <div className="prompt-group" style={{ marginTop: '30px' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div>
                                            <label className="prompt-label">Temperatura de Cor (Conforto Ocular)</label>
                                            <p className="prompt-hint">Ajuste para tons mais quentes para reduzir a fatiga visual.</p>
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <input
                                                type="checkbox"
                                                id="applyPdfTint"
                                                checked={applyPdfTint}
                                                onChange={(e) => setApplyPdfTint(e.target.checked)}
                                                style={{ width: '16px', height: '16px', accentColor: 'var(--accent)', cursor: 'pointer' }}
                                            />
                                            <label htmlFor="applyPdfTint" style={{ fontSize: '0.9rem', color: 'var(--text-primary)', cursor: 'pointer' }}>Aplicar ao PDF</label>
                                        </div>
                                    </div>
                                    <div style={{ marginTop: '16px', padding: '0 10px' }}>
                                        <input
                                            type="range"
                                            min="0"
                                            max="100"
                                            value={colorTemp}
                                            onChange={(e) => setColorTemp(parseInt(e.target.value))}
                                            style={{ width: '100%' }}
                                        />
                                        <div style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            marginTop: '8px',
                                            fontSize: '0.8rem',
                                            color: 'var(--text-secondary)'
                                        }}>
                                            <span>Neutro (0%)</span>
                                            <span>Quente (100%)</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="prompt-group" style={{ marginTop: '30px', padding: '16px', background: 'rgba(var(--accent-rgb), 0.05)', borderRadius: '12px', border: '1px solid var(--glass-border)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <label className="prompt-label" style={{ marginBottom: 0 }}>Múltiplas Janelas (Beta)</label>
                                                <div style={{ background: 'var(--accent)', color: '#fff', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold' }}>ULTRA-WIDE</div>
                                            </div>
                                            <p className="prompt-hint" style={{ marginTop: '4px' }}>Abre cada chat em uma janela independente do sistema operacional. Ideal para múltiplos monitores.</p>
                                        </div>
                                        <div className="flex items-center">
                                            <input
                                                type="checkbox"
                                                id="multiWindowMode"
                                                checked={multiWindowMode}
                                                onChange={(e) => setMultiWindowMode(e.target.checked)}
                                                style={{ width: '20px', height: '20px', accentColor: 'var(--accent)', cursor: 'pointer' }}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="prompt-group" style={{ marginTop: '16px', padding: '16px', background: 'rgba(var(--accent-rgb), 0.05)', borderRadius: '12px', border: '1px solid var(--glass-border)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                <label className="prompt-label" style={{ marginBottom: 0 }}>Contexto Multi-Chat</label>
                                                <div style={{ background: 'var(--accent)', color: '#fff', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', fontWeight: 'bold' }}>RAG</div>
                                            </div>
                                            <p className="prompt-hint" style={{ marginTop: '4px' }}>Permite que a IA consulte conhecimentos de outros chats passados por padrão.</p>
                                        </div>
                                        <div className="flex items-center">
                                            <input
                                                type="checkbox"
                                                id="defaultMultiChatContext"
                                                checked={defaultMultiChatContext}
                                                onChange={(e) => setDefaultMultiChatContext(e.target.checked)}
                                                style={{ width: '20px', height: '20px', accentColor: 'var(--accent)', cursor: 'pointer' }}
                                            />
                                        </div>
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
