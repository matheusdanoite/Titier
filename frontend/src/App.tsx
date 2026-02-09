import { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Settings as SettingsIcon,
  Sparkles,
  GripVertical,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  BookOpen,
  Menu,
  Columns as ColumnsIcon,
  Maximize2,
  FileText
} from 'lucide-react';

import Onboarding from './components/Onboarding';
import { Settings } from './components/Settings';
import { DebugMenu } from './components/DebugMenu';
import { ChatSession, Message } from './components/ChatSession';
import { SidebarMenu, Session } from './components/SidebarMenu';

import './App.css';
import './components/Onboarding.css';
import './components/ChatSession.css';
import './components/SidebarMenu.css';

const API_URL = 'http://127.0.0.1:8000';

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

// Extends functionality of basic session with message history
interface SessionData extends Session {
  messages: Message[];
  searchMode: 'local' | 'global';
  contextFilter: string | null;
}

function App() {
  // App State
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [tauriStatus, setTauriStatus] = useState<any>(null);
  const [showDebug, setShowDebug] = useState(false);

  // Drag & Drop / Upload
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  // Layout State
  const [sidebarWidth, setSidebarWidth] = useState(400);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [currentPDF, setCurrentPDF] = useState<UploadedPDF | null>(null);
  const [pdfZoom, setPdfZoom] = useState(100);

  // Chat Sessions State
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [activeSessionIds, setActiveSessionIds] = useState<string[]>([]);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [viewMode, setViewMode] = useState<'stack' | 'grid'>('stack'); // For multi-view layout

  const fileInputRef = useRef<HTMLInputElement>(null);
  const resizeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    checkHealth();
  }, []);

  // Initialize a default session if none exists
  useEffect(() => {
    if (!showOnboarding && sessions.length === 0) {
      handleNewSession();
    }
  }, [showOnboarding]);

  // Sync session context with current PDF if needed (optional behavior)
  useEffect(() => {
    if (currentPDF) {
      // Auto-update context for active sessions? 
      // Or keep them independent. Let's keep independent for now based on user request.
    }
  }, [currentPDF]);

  // Handle resize
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const newWidth = window.innerWidth - e.clientX;
      setSidebarWidth(Math.max(300, Math.min(800, newWidth)));
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

      const statsRes = await fetch(`${API_URL}/status`);
      const statsData = await statsRes.json();
      setStats(statsData);

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
      if (e.altKey && (e.key === 'd' || e.key === 'D')) {
        e.preventDefault();
        setShowDebug(prev => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // --- Session Management ---

  const handleNewSession = () => {
    const newSession: SessionData = {
      id: Date.now().toString(),
      title: currentPDF ? `Chat: ${currentPDF.name}` : 'Nova Conversa',
      date: new Date(),
      preview: 'Inicie a conversa...',
      messages: [],
      searchMode: 'local',
      contextFilter: currentPDF?.name || null
    };

    setSessions(prev => [newSession, ...prev]);
    setActiveSessionIds(prev => [...prev, newSession.id]);
    setIsMenuOpen(false);
  };

  const handleSelectSession = (id: string) => {
    if (!activeSessionIds.includes(id)) {
      setActiveSessionIds(prev => [...prev, id]);
    }
    setIsMenuOpen(false);
  };

  const handleCloseSession = (id: string) => {
    setActiveSessionIds(prev => prev.filter(sid => sid !== id));
  };

  const handleDeleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessions(prev => prev.filter(s => s.id !== id));
    setActiveSessionIds(prev => prev.filter(sid => sid !== id));
  };

  const handleMessagesChange = (sessionId: string, newMessages: Message[]) => {
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        // Update preview based on last user message or assistant message
        const lastMsg = newMessages[newMessages.length - 1];
        const preview = lastMsg ? lastMsg.content.slice(0, 50) + (lastMsg.content.length > 50 ? '...' : '') : s.preview;

        return { ...s, messages: newMessages, preview };
      }
      return s;
    }));
  };

  // --- Drag & Drop ---
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

        const pdfUrl = URL.createObjectURL(file);
        setCurrentPDF({
          name: file.name,
          url: pdfUrl,
          chunks: data.chunks_added
        });

        // Optionally creating a new session for the new PDF
        // handleNewSession(); 

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

      {/* Sidebar Menu Overlay */}
      <SidebarMenu
        isOpen={isMenuOpen}
        onClose={() => setIsMenuOpen(false)}
        sessions={sessions}
        activeSessionId={activeSessionIds[activeSessionIds.length - 1] || null} // Highlight last active
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
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
        <button
          className="sidebar-toggle"
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          title={isSidebarCollapsed ? "Expandir chat" : "Recolher chat"}
        >
          {isSidebarCollapsed ? <ChevronLeft size={20} /> : <ChevronRightIcon size={20} />}
        </button>

        {!isSidebarCollapsed && (
          <div className="sidebar-content-wrapper">
            {/* Sidebar Header */}
            <div className="sidebar-header">
              <div className="header-left-actions">
                <button className="icon-button" onClick={() => setIsMenuOpen(true)}>
                  <Menu size={20} />
                </button>
                <div className="sidebar-title">
                  <span>Chat</span>
                </div>
              </div>

              <div className="header-actions">
                <button
                  className="icon-button"
                  onClick={() => setViewMode(prev => prev === 'stack' ? 'grid' : 'stack')}
                  title={viewMode === 'stack' ? "Modo Grade" : "Modo Pilha"}
                  disabled={activeSessionIds.length < 2}
                >
                  {viewMode === 'stack' ? <ColumnsIcon size={18} /> : <Maximize2 size={18} />}
                </button>
                <button
                  className="icon-button"
                  onClick={() => setShowSettings(true)}
                  title="Configurações"
                >
                  <SettingsIcon size={20} />
                </button>
              </div>
            </div>

            {/* Active Sessions Area */}
            <div className={`active-sessions-container ${viewMode}`}>
              {activeSessionIds.length === 0 ? (
                <div className="no-active-session">
                  <Sparkles size={48} className="empty-icon" />
                  <h3>Nenhum chat aberto</h3>
                  <button onClick={handleNewSession} className="start-chat-btn">
                    Iniciar Conversa
                  </button>
                </div>
              ) : (
                activeSessionIds.map((sessionId, index) => {
                  const sessionData = sessions.find(s => s.id === sessionId);
                  if (!sessionData) return null;

                  return (
                    <div key={sessionId} className="session-wrapper" style={{ flex: viewMode === 'grid' ? 1 : '0 0 100%' }}>
                      <ChatSession
                        sessionId={sessionId}
                        title={sessionData.title}
                        isActive={true}
                        onClose={() => handleCloseSession(sessionId)}
                        contextFilter={sessionData.contextFilter}
                        searchMode={sessionData.searchMode}
                        initialMessages={sessionData.messages}
                        onMessagesChange={(msgs) => handleMessagesChange(sessionId, msgs)}
                      />
                      {viewMode === 'stack' && index < activeSessionIds.length - 1 && (
                        <div className="session-divider" />
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

export default App;
