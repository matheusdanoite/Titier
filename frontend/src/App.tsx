import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  FileText,
  Upload,
  Settings as SettingsIcon,
  Sparkles,
  ChevronDown,
  BookOpen,
  MessageSquare,
  GripVertical,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  Globe
} from 'lucide-react';
import Onboarding from './components/Onboarding';
import { Settings } from './components/Settings';
import { DebugMenu } from './components/DebugMenu';
import './App.css';
import './components/Onboarding.css';

const API_URL = 'http://127.0.0.1:8000';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: { text: string; page?: number }[];
}

interface HealthStatus {
  status: string;
  backend: string;
  gpu_available: boolean;
  model_available: boolean;
  documents_indexed: number;
}

interface UploadedPDF {
  name: string;
  url: string;
  chunks: number;
}

function App() {
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [tauriStatus, setTauriStatus] = useState<any>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [showSources, setShowSources] = useState<string | null>(null);

  // New layout state
  const [sidebarWidth, setSidebarWidth] = useState(400);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [currentPDF, setCurrentPDF] = useState<UploadedPDF | null>(null);
  const [pdfZoom, setPdfZoom] = useState(100);
  const [globalSearch, setGlobalSearch] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const resizeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkHealth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const newWidth = window.innerWidth - e.clientX;
      setSidebarWidth(Math.max(300, Math.min(600, newWidth)));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${API_URL}/health`);
      const data = await res.json();
      setHealth(data);

      if (data.model_available) {
        setShowOnboarding(false);
      }

      // Also fetch stats for debug
      const statsRes = await fetch(`${API_URL}/status`);
      const statsData = await statsRes.json();
      setStats(statsData);

      // Fetch tauri status if in tauri environment
      try {
        const tStatus = await invoke('get_backend_status');
        setTauriStatus(tStatus);
      } catch (e) {
        console.warn('Tauri invoke failed (likely dev mode):', e);
      }
    } catch {
      setHealth(null);
    }
  };

  // Keyboard shortcut for debug menu
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Alt+D or Option+D
      if (e.altKey && (e.key === 'd' || e.key === 'D')) {
        e.preventDefault();
        setShowDebug(prev => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage.content,
          source_filter: currentPDF?.name || null,
          search_mode: globalSearch ? 'global' : 'local'
        })
      });

      const data = await res.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.response,
        sources: data.sources
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch {
      setMessages(prev => [...prev, {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Erro ao se comunicar com o backend. Verifique se o servidor está rodando.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = Array.from(e.dataTransfer.files);
    const pdfFiles = files.filter(f => f.type === 'application/pdf');

    if (pdfFiles.length > 0) {
      await uploadPDF(pdfFiles[0]);
    }
  }, []);

  const uploadPDF = async (file: File) => {
    setUploadProgress(`Enviando ${file.name}...`);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        setUploadProgress(`✓ ${data.filename} (${data.chunks_added} chunks)`);
        checkHealth();

        // Set current PDF for viewing
        const pdfUrl = URL.createObjectURL(file);
        setCurrentPDF({
          name: file.name,
          url: pdfUrl,
          chunks: data.chunks_added
        });

        setTimeout(() => setUploadProgress(null), 3000);
      } else {
        setUploadProgress('Erro no upload');
        setTimeout(() => setUploadProgress(null), 3000);
      }
    } catch {
      setUploadProgress('Erro de conexão');
      setTimeout(() => setUploadProgress(null), 3000);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadPDF(file);
    }
  };

  if (showOnboarding) {
    return <Onboarding onComplete={() => {
      setShowOnboarding(false);
      checkHealth();
    }} />;
  }

  return (
    <div
      className="app-container split-layout"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <Settings isOpen={showSettings} onClose={() => setShowSettings(false)} />
      <DebugMenu
        isOpen={showDebug}
        onClose={() => setShowDebug(false)}
        health={health}
        stats={stats}
        tauriStatus={tauriStatus}
      />

      {/* Drag Overlay */}
      <AnimatePresence>
        {isDragging && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="drag-overlay"
          >
            <Upload size={64} />
            <span>Solte o PDF aqui</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Upload Progress Toast */}
      <AnimatePresence>
        {uploadProgress && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="upload-toast"
          >
            <FileText size={18} />
            {uploadProgress}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content - PDF Viewer */}
      <main className="pdf-viewer-container">
        {/* Header */}
        <header className="viewer-header">
          <div className="header-left">
            <Sparkles className="logo-icon" />
            <h1>Titier</h1>
          </div>

          <div className="header-center">
            {currentPDF && (
              <div className="pdf-controls">
                <span className="pdf-name">{currentPDF.name}</span>
                <div className="zoom-controls">
                  <button onClick={() => setPdfZoom(z => Math.max(50, z - 10))} title="Zoom Out">
                    <ZoomOut size={16} />
                  </button>
                  <span>{pdfZoom}%</span>
                  <button onClick={() => setPdfZoom(z => Math.min(200, z + 10))} title="Zoom In">
                    <ZoomIn size={16} />
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="header-right">
            {health && (
              <div className="status-pills">
                <span className={`pill ${health.gpu_available ? 'success' : 'warning'}`}>
                  {health.backend.toUpperCase()}
                </span>
                {health.documents_indexed > 0 && (
                  <span className="pill info">
                    <BookOpen size={12} />
                    {health.documents_indexed} docs
                  </span>
                )}
              </div>
            )}

            <button
              className="icon-button"
              onClick={() => fileInputRef.current?.click()}
              title="Upload PDF"
            >
              <Upload size={20} />
            </button>
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </header>

        {/* PDF Viewer Area */}
        <div className="pdf-viewer">
          {currentPDF ? (
            <iframe
              src={`${currentPDF.url}#zoom=${pdfZoom}`}
              className="pdf-iframe"
              title="PDF Viewer"
            />
          ) : (
            <div className="pdf-placeholder">
              <Upload size={64} className="placeholder-icon" />
              <h2>Nenhum documento carregado</h2>
              <p>Arraste um PDF ou clique no botão de upload</p>
              <button
                className="upload-button"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload size={20} />
                Selecionar PDF
              </button>
            </div>
          )}
        </div>
      </main>

      {/* Resize Handle */}
      {!isSidebarCollapsed && (
        <div
          ref={resizeRef}
          className={`resize-handle ${isResizing ? 'active' : ''}`}
          onMouseDown={() => setIsResizing(true)}
        >
          <GripVertical size={16} />
        </div>
      )}

      {/* Chat Sidebar */}
      <aside
        className={`chat-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}
        style={{ width: isSidebarCollapsed ? 48 : sidebarWidth }}
      >
        {/* Collapse Toggle */}
        <button
          className="sidebar-toggle"
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          title={isSidebarCollapsed ? "Expandir chat" : "Recolher chat"}
        >
          {isSidebarCollapsed ? <ChevronLeft size={20} /> : <ChevronRightIcon size={20} />}
        </button>

        {!isSidebarCollapsed && (
          <>
            {/* Sidebar Header */}
            <div className="sidebar-header">
              <div className="sidebar-title">
                <MessageSquare size={20} />
                <span>Chat</span>
              </div>
              <div className="header-actions">
                <div className="search-mode-toggle">
                  <button
                    className={`mode-btn ${!globalSearch ? 'active' : ''}`}
                    onClick={() => setGlobalSearch(false)}
                    title="Buscar no Contexto Local (PDF atual)"
                  >
                    <FileText size={14} />
                  </button>
                  <button
                    className={`mode-btn ${globalSearch ? 'active' : ''}`}
                    onClick={() => setGlobalSearch(true)}
                    title="Buscar Globalmente (Todos os documentos)"
                  >
                    <Globe size={14} />
                  </button>
                </div>
                <button
                  className="icon-button"
                  onClick={() => setShowSettings(true)}
                  title="Configurações"
                >
                  <SettingsIcon size={20} />
                </button>
              </div>
            </div>

            {/* Context Indicator */}
            {currentPDF && !globalSearch && (
              <div className="context-indicator">
                <FileText size={14} />
                <span>Contexto: {currentPDF.name}</span>
              </div>
            )}
            {globalSearch && (
              <div className="context-indicator global">
                <Globe size={14} />
                <span>Buscando em todos os documentos</span>
              </div>
            )}

            {/* Messages */}
            <div className="sidebar-messages">
              {messages.length === 0 ? (
                <div className="chat-empty">
                  <Sparkles size={32} />
                  <p>Faça perguntas sobre seus documentos</p>
                </div>
              ) : (
                <div className="messages-list">
                  {messages.map((msg) => (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`message ${msg.role}`}
                    >
                      <div className="message-content">
                        {msg.content}
                      </div>

                      {msg.sources && msg.sources.length > 0 && (
                        <div className="message-sources">
                          <button
                            className="sources-toggle"
                            onClick={() => setShowSources(showSources === msg.id ? null : msg.id)}
                          >
                            <FileText size={14} />
                            {msg.sources.length} fonte(s)
                            <ChevronDown
                              size={14}
                              className={showSources === msg.id ? 'rotated' : ''}
                            />
                          </button>

                          <AnimatePresence>
                            {showSources === msg.id && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="sources-list"
                              >
                                {msg.sources.map((source, i) => (
                                  <div key={i} className="source-item">
                                    {source.page && <span className="page-badge">p. {source.page}</span>}
                                    <p>{source.text}</p>
                                  </div>
                                ))}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      )}
                    </motion.div>
                  ))}

                  {loading && (
                    <div className="message assistant loading">
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Input */}
            <div className="sidebar-input">
              <div className="input-wrapper">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                  placeholder="Pergunte algo..."
                  disabled={loading}
                />
                <button
                  className="send-button"
                  onClick={sendMessage}
                  disabled={!input.trim() || loading}
                >
                  <Send size={18} />
                </button>
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

export default App;
