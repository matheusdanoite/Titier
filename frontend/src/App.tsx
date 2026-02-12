import React, { useState, useEffect, useRef, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Sparkles,
  GripVertical,
  ZoomIn,
  ZoomOut,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  Menu,
  Columns as ColumnsIcon,
  Maximize2,
  FileText,
  Flame, // Imported for "hot" icon
  Plus,

  Save,
} from 'lucide-react';




import Onboarding from './components/Onboarding';
import { Settings } from './components/Settings';
import { DebugMenu } from './components/DebugMenu';
import { ChatSession, Message } from './components/ChatSession';
import { SidebarMenu } from './components/SidebarMenu';
import { Session, IHighlight } from './types';
import { EmptyState } from './components/EmptyState';
import { ProcessingView } from './components/ProcessingView';
import { savePDF } from './utils/pdfUtils';

// Lazy load PDF Editor to avoid bundle crash if pdfjs fails
const PDFEditor = React.lazy(() => import('./components/PDFEditor').then(module => ({ default: module.PDFEditor })));

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



// Extends functionality of basic session with message history
interface SessionData extends Session {
  messages: Message[];
  searchMode: 'local' | 'global';
  contextFilter: string | null;
  pdf_hash?: string | null;
  autoStartPrompt?: string | null;
  titlingAttempted?: boolean;
  includeOtherChats?: boolean;
}

// Helper to convert hex to r,g,b
const hexToRgb = (hex: string) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : '99, 102, 241';
};

function App() {
  console.log('--- APP COMPONENT RENDERING (v0.5.2-debug) ---');

  // App State
  const [showOnboarding, setShowOnboarding] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [tauriStatus, setTauriStatus] = useState<any>(null);

  const [showDebug, setShowDebug] = useState(false);

  // Theme State
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('dark');
  const [accentColor, setAccentColor] = useState<string>('#6366f1');
  const [colorTemp, setColorTemp] = useState<number>(0); // 0 = neutral, 100 = very warm
  const [pdfBgColor, setPdfBgColor] = useState<string>('#f0f0f5'); // Background for PDF Viewer area
  const [applyPdfTint, setApplyPdfTint] = useState<boolean>(true); // Whether color temp applies to PDF
  const [multiWindowMode, setMultiWindowMode] = useState<boolean>(false);
  const [defaultMultiChatContext, setDefaultMultiChatContext] = useState<boolean>(false);
  const [windowLabel, setWindowLabel] = useState<string>('main');

  // PDF Editor State
  // PDF Editor State
  const [activeColor, setActiveColor] = useState<string>('#facc15'); // Default yellow
  const [customColors, setCustomColors] = useState<string[]>(['#facc15', '#4ade80', '#60a5fa', '#f87171']); // Yellow, Green, Blue, Red
  const [isAreaSelectionMode, setIsAreaSelectionMode] = useState(false);

  const colorInputRef = useRef<HTMLInputElement>(null);

  const handleAddColor = (newColor: string) => {
    if (!customColors.includes(newColor)) {
      setCustomColors([...customColors, newColor]);
    }
    setActiveColor(newColor);
  };


  // Drag & Drop / Upload
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingFileName, setProcessingFileName] = useState('');

  // Chat Sessions State
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [activeSessionIds, setActiveSessionIds] = useState<string[]>([]);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Layout State
  const [sidebarWidth, setSidebarWidth] = useState(400);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [currentPDF, setCurrentPDF] = useState<any>(null);
  const [pdfZoom, setPdfZoom] = useState(100);
  const [highlights, setHighlights] = useState<IHighlight[]>([]);

  const sessionsRef = useRef(sessions);
  useEffect(() => {
    sessionsRef.current = sessions;
  }, [sessions]);

  // Filtro de sessões por PDF atual
  const filteredSessions = React.useMemo(() => {
    if (!currentPDF) {
      // Se não houver PDF aberto, mostrar apenas sessões sem hash (gerais)
      return sessions.filter(s => !s.pdf_hash);
    }
    // Mostrar apenas sessões do PDF atual
    return sessions.filter(s => s.pdf_hash === currentPDF.file_hash);
  }, [sessions, currentPDF]);

  const handleMessagesChange = useCallback((sessionId: string, newMessages: Message[]) => {
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        // Update preview based on last user message or assistant message
        const lastMsg = newMessages[newMessages.length - 1];
        const preview = lastMsg ? lastMsg.content.slice(0, 50) + (lastMsg.content.length > 50 ? '...' : '') : s.preview;

        return { ...s, messages: newMessages, preview };
      }
      return s;
    }));
  }, []);

  const handleNewSession = useCallback(async (pdfName?: any, autoPrompt?: string) => {
    let contextStr: string | null = null;
    let sessionColor: string | undefined = undefined;
    let pdfHash: string | null = null;

    if (typeof pdfName === 'string') {
      contextStr = pdfName;
    } else if (pdfName && typeof pdfName === 'object') {
      const isEvent = 'nativeEvent' in pdfName || 'target' in pdfName || 'preventDefault' in pdfName;
      if (!isEvent) {
        if (pdfName.color) sessionColor = pdfName.color;
        if (pdfName.hash) pdfHash = pdfName.hash;
        contextStr = pdfName.toString?.() || null;
        if (contextStr === '[object Object]' && currentPDF?.name) {
          contextStr = currentPDF.name;
        }
      }
    }

    const sessionId = Date.now().toString();
    const newSession: SessionData = {
      id: sessionId,
      title: (contextStr && contextStr !== '[object Object]') ? `Chat: ${contextStr}` : 'Nova Conversa',
      date: new Date(),
      preview: autoPrompt ? 'Gerando resumo...' : 'Inicie a conversa...',
      messages: [],
      searchMode: 'local',
      contextFilter: contextStr,
      pdf_hash: pdfHash || (currentPDF?.file_hash),
      autoStartPrompt: autoPrompt || null,
      color: sessionColor,
      includeOtherChats: defaultMultiChatContext
    };

    try {
      await fetch(`${API_URL}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: newSession.id,
          title: newSession.title,
          color: newSession.color,
          pdf_hash: pdfHash || (currentPDF?.file_hash),
          search_mode: newSession.searchMode,
          include_other_chats: newSession.includeOtherChats
        })
      });
    } catch (e) {
      console.error('Failed to save session to backend:', e);
    }

    setSessions(prev => [newSession, ...prev]);
    setActiveSessionIds(prev => [...prev, newSession.id]);
    setIsMenuOpen(false);
  }, [currentPDF, defaultMultiChatContext]);

  const handleToggleSearchMode = useCallback(async (sessionId: string, mode: 'local' | 'global') => {
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, searchMode: mode } : s));
    try {
      await fetch(`${API_URL}/sessions/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ search_mode: mode })
      });
    } catch (e) {
      console.error('Failed to update search mode:', e);
    }
  }, []);

  const handleToggleIncludeOtherChats = useCallback(async (sessionId: string, include: boolean) => {
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, includeOtherChats: include } : s));
    try {
      await fetch(`${API_URL}/sessions/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ include_other_chats: include })
      });
    } catch (e) {
      console.error('Failed to update include past chats:', e);
    }
  }, []);

  const handleAddHighlight = useCallback(async (highlight: IHighlight) => {
    console.log('Adding highlight:', highlight);
    setHighlights(prev => [{ ...highlight, id: Date.now().toString() }, ...prev]);

    const contextPrompt = `O usuário destacou o seguinte trecho no documento "${currentPDF?.name}":\n\n"${highlight.content.text}"\n\nAnalise este trecho e o contexto dele.`;

    const existingSession = sessionsRef.current.find(s =>
      s.color === highlight.color &&
      (s.pdf_hash === currentPDF?.file_hash || s.contextFilter === currentPDF?.name)
    );

    if (existingSession) {
      console.log(`Consolidating highlight into existing session: ${existingSession.id}`);

      const newMessage: Message = {
        id: Date.now().toString(),
        role: 'user',
        content: contextPrompt
      };

      handleMessagesChange(existingSession.id, [...existingSession.messages, newMessage]);

      try {
        await fetch(`${API_URL}/sessions/${existingSession.id}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role: 'user',
            content: contextPrompt
          })
        });
      } catch (e) {
        console.error('Failed to save consolidated message:', e);
      }

      if (!activeSessionIds.includes(existingSession.id)) {
        setActiveSessionIds(prev => [...prev, existingSession.id]);
      }
    } else {
      handleNewSession({ toString: () => currentPDF?.name || 'Documento', color: highlight.color }, contextPrompt);
    }
  }, [currentPDF, activeSessionIds, handleMessagesChange, handleNewSession]);


  const handleUpdateHighlight = (id: string, position: Partial<IHighlight['position']>, content: Partial<IHighlight['content']>) => {
    console.log('Updating highlight:', id);
    setHighlights(prev => prev.map(h => h.id === id ? { ...h, position: { ...h.position, ...position }, content: { ...h.content, ...content } } : h));
  };

  const handleSavePDF = async () => {
    if (!currentPDF) return;
    await savePDF(currentPDF.url, highlights, currentPDF.name);
  };



  const handleExtractedColors = useCallback((colors: string[]) => {
    if (colors.length > 0) {
      const newColors = colors.map((color, index) => ({
        id: `extracted-${index}`,
        value: color,
        label: `Cor PDF ${index + 1}`
      }));
      const validColors = newColors.filter(c => c.value && c.value.startsWith('#'));
      if (validColors.length > 0) {
        const newColorValues = validColors.map(c => c.value);
        // Só atualiza se houver mudança real nas cores
        setCustomColors(prev => {
          if (JSON.stringify(prev) === JSON.stringify(newColorValues)) return prev;
          return newColorValues;
        });

        validColors.forEach(colorObj => {
          const colorName = colorObj.label;
          const sessionKey = `${currentPDF?.file_hash || currentPDF?.name}-${colorObj.value}`;
          if (processedColorSessions.current.has(sessionKey)) return;

          const exists = sessionsRef.current.find(s => s.color === colorObj.value && (s.pdf_hash === currentPDF?.file_hash || s.contextFilter === currentPDF?.name));
          if (!exists) {
            processedColorSessions.current.add(sessionKey);
            handleNewSession({
              toString: () => `${colorName}`,
              color: colorObj.value,
              hash: currentPDF?.file_hash
            }, `Este é um chat focado nos trechos marcados com a cor ${colorName}. O que você gostaria de saber sobre eles?`);
          } else {
            processedColorSessions.current.add(sessionKey);
          }
        });
      }
    } else {
      setCustomColors(['#facc15', '#4ade80', '#60a5fa', '#f87171']);
    }
  }, [currentPDF, defaultMultiChatContext, handleNewSession]);

  const [viewMode, setViewMode] = useState<'stack' | 'grid'>('stack'); // For multi-view layout
  const [zoomMenu, setZoomMenu] = useState<{ x: number; y: number } | null>(null);

  const handleZoomAction = (action: 'width' | 'page' | number) => {
    if (action === 'width') {
      // We'll pass -1 for width, -2 for page for PDFEditor to handle
      setPdfZoom(-1);
    } else if (action === 'page') {
      setPdfZoom(-2);
    } else {
      setPdfZoom(action);
    }
    setZoomMenu(null);
  };

  const fileInputRef = useRef<HTMLInputElement>(null);
  const resizeRef = useRef<HTMLDivElement>(null);
  const inFlightTitling = useRef<Set<string>>(new Set());
  const processedColorSessions = useRef<Set<string>>(new Set());

  useEffect(() => {
    checkHealth();
    // Detect current window label
    try {
      const win = getCurrentWindow();
      setWindowLabel(win.label);
      console.log('Current window label:', win.label);
    } catch (e) {
      console.error('Failed to get window label:', e);
    }
  }, []);

  // Initialize a default session if none exists
  useEffect(() => {
    if (!showOnboarding && sessions.length === 0) {
      handleNewSession();
    }
  }, [showOnboarding, handleNewSession, sessions.length]);

  // Load settings from localStorage
  useEffect(() => {
    const savedColors = localStorage.getItem('customColors');
    const savedActiveColor = localStorage.getItem('activeColor');
    if (savedColors) setCustomColors(JSON.parse(savedColors));
    if (savedActiveColor) setActiveColor(savedActiveColor);
  }, []);

  // Save settings to localStorage
  useEffect(() => {
    localStorage.setItem('customColors', JSON.stringify(customColors));
  }, [customColors]);

  useEffect(() => {
    localStorage.setItem('activeColor', activeColor);
  }, [activeColor]);

  // Load Theme Settings
  useEffect(() => {
    const savedTheme = localStorage.getItem('themeMode') as 'light' | 'dark';
    const savedAccent = localStorage.getItem('appAccentColor');
    const savedTemp = localStorage.getItem('appColorTemp');
    const savedPdfBg = localStorage.getItem('appPdfBg');

    if (savedTheme) setThemeMode(savedTheme);
    if (savedAccent) setAccentColor(savedAccent);
    if (savedTemp) setColorTemp(parseInt(savedTemp));
    if (savedPdfBg) setPdfBgColor(savedPdfBg);
    const savedPdfTint = localStorage.getItem('appApplyPdfTint');
    if (savedPdfTint !== null) setApplyPdfTint(savedPdfTint === 'true');
    const savedMultiWindow = localStorage.getItem('appMultiWindowMode');
    if (savedMultiWindow !== null) setMultiWindowMode(savedMultiWindow === 'true');
    const savedMultiChat = localStorage.getItem('defaultMultiChatContext');
    if (savedMultiChat !== null) setDefaultMultiChatContext(savedMultiChat === 'true');

    // Load and hydrate sessions from Backend
    const fetchSessions = async () => {
      try {
        const res = await fetch(`${API_URL}/sessions`);
        if (res.ok) {
          const fetched = await res.json();
          const hydrated = fetched.map((s: any) => ({
            ...s,
            id: s.id,
            title: s.title,
            date: new Date(s.created_at || s.date || Date.now()),
            preview: s.preview || 'Sessão recuperada',
            color: s.color,
            messages: [], // Messages will be loaded per session when opened
            searchMode: s.search_mode as 'local' | 'global',
            contextFilter: s.pdf_hash || s.contextFilter,
            includeOtherChats: s.include_other_chats === 1,
            titlingAttempted: s.titling_attempted === 1
          }));
          setSessions(hydrated);
        }
      } catch (e) {
        console.error('Failed to fetch sessions from backend:', e);
        // Fallback to localStorage if backend fails? 
        const savedSessions = localStorage.getItem('chat-sessions');
        if (savedSessions) {
          const parsed = JSON.parse(savedSessions);
          setSessions(parsed.map((s: any) => ({ ...s, date: new Date(s.date) })));
        }
      }
    };
    fetchSessions();
  }, []);

  // Listen for storage events (Sync between windows)
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      // Ignore events from this window to prevent loops
      if (!e.newValue || e.newValue === e.oldValue) return;

      // In some browsers, we might need a way to distinguish windows.
      // e.newValue comparison is a simple heuristic.

      if (e.key === 'themeMode') setThemeMode(e.newValue as 'light' | 'dark');
      if (e.key === 'appAccentColor') setAccentColor(e.newValue);
      if (e.key === 'appColorTemp') setColorTemp(parseInt(e.newValue));
      if (e.key === 'appPdfBg') setPdfBgColor(e.newValue);
      if (e.key === 'appApplyPdfTint') setApplyPdfTint(e.newValue === 'true');
      if (e.key === 'appMultiWindowMode') setMultiWindowMode(e.newValue === 'true');

      // Sync sessions if they change (important for multi-window)
      if (e.key === 'chat-sessions') {
        const newSessions = JSON.parse(e.newValue);
        // Hydrate dates
        const hydrated = newSessions.map((s: any) => ({
          ...s,
          date: new Date(s.date)
        }));
        setSessions(hydrated);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Apply Theme Settings
  useEffect(() => {
    // Save to localStorage
    localStorage.setItem('themeMode', themeMode);
    localStorage.setItem('appAccentColor', accentColor);
    localStorage.setItem('appColorTemp', colorTemp.toString());
    localStorage.setItem('appPdfBg', pdfBgColor);
    localStorage.setItem('appApplyPdfTint', String(applyPdfTint));
    localStorage.setItem('appMultiWindowMode', String(multiWindowMode));
    localStorage.setItem('defaultMultiChatContext', String(defaultMultiChatContext));
  }, [themeMode, accentColor, colorTemp, pdfBgColor, applyPdfTint, multiWindowMode, defaultMultiChatContext]);

  // Session persistence moved to specific handles and individual message saves in ChatSession.tsx
  // We keep a lightweight localStorage sync for active layout/tabs if needed, but the core is backend.

  // Apply Theme Settings
  useEffect(() => {
    // Apply Theme Mode
    document.documentElement.setAttribute('data-theme', themeMode);

    // Apply Accent Color
    const rgb = hexToRgb(accentColor);
    document.documentElement.style.setProperty('--accent', accentColor);
    document.documentElement.style.setProperty('--accent-rgb', rgb);
    document.documentElement.style.setProperty('--accent-hover', accentColor); // Simplified

    // Apply PDF Background
    document.documentElement.style.setProperty('--pdf-bg', pdfBgColor);

    // Update Window Theme for Title Bar
    // On macOS with transparent title bar, the text color usually adapts to the system theme or window theme.
    // We can try to force it via Tauri API.
    const updateWindowTheme = async () => {
      try {
        const win = getCurrentWindow();
        await win.setTheme(themeMode === 'dark' ? 'dark' : 'light');
      } catch (e) {
        console.error('Failed to set window theme:', e);
      }
    };
    updateWindowTheme();

  }, [themeMode, accentColor, colorTemp, pdfBgColor]);

  // Handle Resize
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


  const handleSelectSession = (id: string) => {
    if (!activeSessionIds.includes(id)) {
      setActiveSessionIds(prev => [...prev, id]);
    }
    setIsMenuOpen(false);

    // If multi-window mode is ON, spawn a new window for the session
    if (multiWindowMode && id) {
      spawnSessionWindow(id);
    }
  };

  const spawnSessionWindow = async (sessionId: string) => {
    const session = sessions.find(s => s.id === sessionId);
    if (!session) return;

    try {
      const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow');
      // Create a unique label for the chat window
      const label = `chat-${sessionId}`;

      // Create the window
      const win = new WebviewWindow(label, {
        title: `Chat: ${session.title}`,
        url: 'index.html', // Same app entry point
        width: 600,
        height: 800,
        resizable: true,
        decorations: true,
        transparent: true,
        titleBarStyle: 'overlay'
      });

      win.once('tauri://created', () => {
        console.log(`Window ${label} created`);
      });

      win.once('tauri://error', (e) => {
        console.error(`Failed to create window ${label}:`, e);
      });
    } catch (e) {
      console.error('Error spawning window:', e);
    }
  };

  const handleCloseSession = (id: string) => {
    setActiveSessionIds(prev => prev.filter(sid => sid !== id));
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_URL}/sessions/${id}`, { method: 'DELETE' });
    } catch (e) {
      console.error('Failed to delete session:', e);
    }
    setSessions(prev => prev.filter(s => s.id !== id));
    setActiveSessionIds(prev => prev.filter(sid => sid !== id));
  };

  const handleClearAllSessions = async () => {
    try {
      const res = await fetch(`${API_URL}/sessions`, { method: 'DELETE' });
      if (res.ok) {
        setSessions([]);
        setActiveSessionIds([]);
      }
    } catch (e) {
      console.error('Failed to clear all sessions:', e);
    }
  };

  const handleRenameSession = (id: string, newTitle: string) => {
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title: newTitle } : s));
  };

  const generateSessionTitle = async (sessionId: string, userMsg: string, assistantMsg: string) => {
    console.log(`[AutoTitle] Starting generation for ${sessionId}...`);
    try {
      const response = await fetch(`${API_URL}/chat/generate-title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, response: assistantMsg })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.title) {
          handleRenameSession(sessionId, data.title);
        }
      }
    } catch (e) {
      console.error("Erro ao gerar título:", e);
    } finally {
      inFlightTitling.current.delete(sessionId);
    }
  };

  // --- Drag & Drop (HTML5 + Tauri Events) ---
  useEffect(() => {
    let dragCounter = 0;
    const unlisteners: Promise<() => void>[] = [];

    // HTML5 Handlers
    const handleDocumentDragEnter = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter++;
      console.log('HTML5 Drag Enter:', e.dataTransfer?.types);
      if (e.dataTransfer?.types?.includes('Files')) {
        setIsDragging(true);
      }
    };
    const handleDocumentDragLeave = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounter--;
      console.log('HTML5 Drag Leave:', dragCounter);
      if (dragCounter <= 0) {
        setIsDragging(false);
        dragCounter = 0;
      }
    };
    const handleDocumentDrop = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      console.log('HTML5 Drop');
      setIsDragging(false);
      dragCounter = 0;
      if (e.dataTransfer?.files?.length) {
        const file = e.dataTransfer.files[0];
        if (file.type === 'application/pdf') uploadPDF(file);
      }
    };
    const handleDocumentDragOver = (e: DragEvent) => { e.preventDefault(); e.stopPropagation(); };

    document.addEventListener('dragenter', handleDocumentDragEnter);
    document.addEventListener('dragleave', handleDocumentDragLeave);
    document.addEventListener('dragover', handleDocumentDragOver);
    document.addEventListener('drop', handleDocumentDrop);

    // Tauri Event Handlers (Native Drag & Drop)
    unlisteners.push(listen('tauri://drag-enter', (event) => {
      console.log('Tauri Drag Enter:', event);
      setIsDragging(true);
    }));
    unlisteners.push(listen('tauri://drag-leave', (event) => {
      console.log('Tauri Drag Leave:', event);
      setIsDragging(false);
    }));

    const handleTauriDrop = async (event: any) => {
      console.log('Tauri Drop Event:', event);
      setIsDragging(false);

      // Payload in v2 might be { paths: string[], position: ... } OR just string[] depending on exact event
      // The log showed payload: { paths: [...] } for drag-enter, so likely same for drop.
      let paths: string[] = [];
      if (event.payload?.paths) {
        paths = event.payload.paths;
      } else if (Array.isArray(event.payload)) {
        paths = event.payload;
      }

      if (paths && paths.length > 0) {
        const filePath = paths[0];
        const fileName = filePath.split(/[/\\]/).pop() || 'document.pdf';

        if (!fileName.toLowerCase().endsWith('.pdf')) {
          alert('Por favor, solte apenas arquivos PDF.');
          return;
        }

        try {
          console.log('Reading dropped file:', filePath);
          // Dynamically import to avoid build errors if plugin missing (though we installed it)
          const { readFile } = await import('@tauri-apps/plugin-fs');
          const fileBytes = await readFile(filePath);
          const file = new File([fileBytes], fileName, { type: 'application/pdf' });

          console.log('File created from bytes:', file);
          uploadPDF(file);
        } catch (err) {
          console.error('Error reading dropped file:', err);
          alert('Erro ao ler o arquivo solto. Verifique as permissões.');
        }
      }
    };

    unlisteners.push(listen('tauri://drop', handleTauriDrop));
    unlisteners.push(listen('tauri://drag-drop', handleTauriDrop)); // Specific v2 element drop
    unlisteners.push(listen('tauri://file-drop', handleTauriDrop)); // Legacy/Alternative fallback

    return () => {
      document.removeEventListener('dragenter', handleDocumentDragEnter);
      document.removeEventListener('dragleave', handleDocumentDragLeave);
      document.removeEventListener('dragover', handleDocumentDragOver);
      document.removeEventListener('drop', handleDocumentDrop);
      unlisteners.forEach(u => u.then(unlisten => unlisten()));
    };
  }, []);

  // Debug Shortcut for Overlay
  useEffect(() => {
    const handleDebugKey = (e: KeyboardEvent) => {
      if (e.altKey && (e.key === 'o' || e.key === 'O')) {
        setIsDragging(prev => !prev);
        console.log('Toggled Drag Overlay');
      }
    };
    window.addEventListener('keydown', handleDebugKey);
    return () => window.removeEventListener('keydown', handleDebugKey);
  }, []);

  // Remove component-level handlers since we use window now


  const uploadPDF = async (file: File) => {
    setUploadProgress(`Processando ${file.name}...`);
    setIsProcessing(true);
    setProcessingFileName(file.name);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        const fileHash = data.file_hash;
        const summary = data.summary;

        setStats((prev: any) => ({ ...prev, documents_indexed: (prev?.documents_indexed || 0) + 1 }));

        const pdfUrl = URL.createObjectURL(file);
        const newPDFState = {
          name: file.name,
          url: pdfUrl,
          file_hash: fileHash
        };
        setCurrentPDF(newPDFState);

        // Success! Strictly only Summary Chat and Color Chats (Color chats created in handleExtractedColors)
        const summaryPrompt = summary || `Resuma o documento...`;
        handleNewSession({ toString: () => `Resumo: ${file.name}`, hash: fileHash }, summaryPrompt);

        setIsProcessing(false);
        setTimeout(() => setUploadProgress(null), 3000);
      } else {
        setUploadProgress('Erro no upload');
        setIsProcessing(false);
      }
    } catch (e) {
      console.error('Upload error:', e);
      setUploadProgress('Erro de conexão');
      setIsProcessing(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadPDF(file);
    }
  };

  if (showOnboarding && windowLabel === 'main') {
    return <Onboarding onComplete={() => {
      setShowOnboarding(false);
      checkHealth();
    }} />;
  }

  // Standalone Chat Window Rendering
  if (windowLabel.startsWith('chat-')) {
    const sessionId = windowLabel.replace('chat-', '');
    const sessionData = sessions.find(s => s.id === sessionId);

    if (!sessionData) {
      return (
        <div className="flex items-center justify-center h-full bg-background">
          <p>Sessão não encontrada ou carregando...</p>
        </div>
      );
    }

    return (
      <div className="app-container standalone-chat" data-tauri-drag-region>
        {/* Color Temperature Overlay */}
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: '#ff9500',
            opacity: (colorTemp / 100) * 0.2,
            pointerEvents: 'none',
            zIndex: 2000,
            mixBlendMode: 'multiply',
            transition: 'opacity 0.3s ease'
          }}
        />
        <ChatSession
          sessionId={sessionId}
          title={sessionData.title}
          isActive={true}
          onClose={() => getCurrentWindow().close()}
          contextFilter={sessionData.contextFilter}
          searchMode={sessionData.searchMode}
          includeOtherChats={sessionData.includeOtherChats}
          onToggleSearchMode={(mode) => handleToggleSearchMode(sessionId, mode)}
          onToggleIncludeOtherChats={(inc) => handleToggleIncludeOtherChats(sessionId, inc)}
          initialMessages={sessionData.messages}
          onMessagesChange={(msgs) => handleMessagesChange(sessionId, msgs)}
          autoStartPrompt={sessionData.autoStartPrompt}
          onGenerationFinished={(assistantMsg) => {
            if ((sessionData.title === 'Nova Conversa' || sessionData.title.startsWith('Chat: ')) && !sessionData.titlingAttempted && !inFlightTitling.current.has(sessionId)) {
              inFlightTitling.current.add(sessionId);
              generateSessionTitle(sessionId, sessionData.messages[0]?.content || '', assistantMsg);
              setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, titlingAttempted: true } : s));
            }
          }}
        />
      </div>
    );
  }

  return (
    <div
      className="app-container split-layout"
    >
      <AnimatePresence>
        {!currentPDF && !showOnboarding && !isProcessing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ position: 'fixed', inset: 0, zIndex: 100 }}
          >
            <EmptyState
              onFileSelect={() => fileInputRef.current?.click()}
              onSettingsClick={() => setShowSettings(true)}
              isDragging={isDragging}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isProcessing && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ position: 'fixed', inset: 0, zIndex: 90 }}
          >
            <ProcessingView
              fileName={processingFileName}
              progressText={uploadProgress}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <Settings
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        themeMode={themeMode}
        setThemeMode={setThemeMode}
        accentColor={accentColor}
        setAccentColor={setAccentColor}
        colorTemp={colorTemp}
        setColorTemp={setColorTemp}
        pdfBgColor={pdfBgColor}
        setPdfBgColor={setPdfBgColor}
        applyPdfTint={applyPdfTint}
        setApplyPdfTint={setApplyPdfTint}
        multiWindowMode={multiWindowMode}
        setMultiWindowMode={setMultiWindowMode}
        defaultMultiChatContext={defaultMultiChatContext}
        setDefaultMultiChatContext={setDefaultMultiChatContext}
        onClearAllSessions={handleClearAllSessions}
      />


      {/* Color Temperature Overlay */}
      <div
        style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: '#ff9500', // Amber/Orange
          opacity: (colorTemp / 100) * 0.2, // Max 20% opacity
          pointerEvents: 'none',
          zIndex: 2000, // Covers everything including Settings (1000)
          mixBlendMode: 'multiply',
          transition: 'opacity 0.3s ease'
        }}
      />

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
        sessions={filteredSessions}
        activeSessionId={activeSessionIds[activeSessionIds.length - 1] || null} // Highlight last active
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onRenameSession={handleRenameSession}
        onOpenSettings={() => setShowSettings(true)}
      />

      {/* Drag Overlay for !currentPDF state is handled inside EmptyState? 
          The user requested an overlay with "Drop like it's hot!"
          I'll add it here for global handling when !start but covers everything.
      */}
      {/* Drag Overlay for !currentPDF state */}
      <AnimatePresence>
        {isDragging && !currentPDF && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="drop-overlay"
          >
            <div className="drop-content">
              <div className="hot-icon-wrapper">
                <Flame size={48} />
              </div>
              <h2>Drop like it's hot!</h2>
              <p>Solte o PDF para começar</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Drag Overlay for currentPDF state */}
      <AnimatePresence>
        {isDragging && currentPDF && (
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
        <header className="viewer-header" data-tauri-drag-region>
          <div className="header-left">
            <button className="icon-button" onClick={() => setIsMenuOpen(true)}>
              <Menu size={20} />
            </button>
          </div>
          <div className="header-center" data-tauri-drag-region>
            {currentPDF && (
              <div className="pdf-controls">

                <div className="highlight-toolbar">
                  {/* Area Selection Toggle */}
                  <button
                    className={`tool-btn ${isAreaSelectionMode ? 'active' : ''}`}
                    title="Seleção de Área"
                    onClick={() => setIsAreaSelectionMode(!isAreaSelectionMode)}
                  >
                    <div style={{ border: '1px dashed currentColor', width: '14px', height: '14px', borderRadius: '2px' }} />
                  </button>

                  <div className="divider" />

                  {/* Dynamic Color Picker */}
                  {customColors.map((color, index) => (
                    <button
                      key={index}
                      className={`color-btn ${activeColor === color ? 'active' : ''}`}
                      title={`Cor ${index + 1}`}
                      style={{ backgroundColor: color }}
                      onClick={() => setActiveColor(color)}
                    />
                  ))}

                  {/* Add New Color Button */}
                  <div className="relative">
                    <button
                      className="tool-btn"
                      title="Adicionar nova cor"
                      onClick={() => colorInputRef.current?.click()}
                    >
                      <Plus size={16} />
                    </button>
                    <input
                      ref={colorInputRef}
                      type="color"
                      style={{ position: 'absolute', opacity: 0, width: 0, height: 0, visibility: 'hidden' }}
                      onChange={(e) => handleAddColor(e.target.value)}
                    />
                  </div>
                </div>

                <div className="zoom-controls">
                  <button
                    onClick={() => setPdfZoom(z => Math.max(50, z - 10))}
                    title="Zoom Out"
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setZoomMenu({ x: e.clientX, y: e.clientY });
                    }}
                  >
                    <ZoomOut size={16} />
                  </button>

                  <div className="zoom-display">
                    <input
                      type="number"
                      value={pdfZoom > 0 ? pdfZoom : 100}
                      onChange={(e) => {
                        const val = parseInt(e.target.value);
                        if (!isNaN(val) && val > 0 && val <= 500) setPdfZoom(val);
                      }}
                      className="zoom-input"
                      title="Nível de Zoom"
                    />
                    <span>%</span>
                  </div>

                  <button
                    onClick={() => setPdfZoom(z => Math.min(500, z + 10))}
                    title="Zoom In"
                    onContextMenu={(e) => {
                      e.preventDefault();
                      setZoomMenu({ x: e.clientX, y: e.clientY });
                    }}
                  >
                    <ZoomIn size={16} />
                  </button>
                </div>

                {/* Zoom Context Menu */}
                {zoomMenu && (
                  <div
                    className="custom-context-menu"
                    style={{ top: zoomMenu.y, left: zoomMenu.x }}
                    onMouseLeave={() => setZoomMenu(null)}
                  >
                    <button onClick={() => handleZoomAction(100)}>100%</button>
                    <button onClick={() => handleZoomAction(150)}>150%</button>
                    <button onClick={() => handleZoomAction(200)}>200%</button>
                    <div className="menu-divider" />
                    <button onClick={() => handleZoomAction('width')}>Ajustar à Largura</button>
                    <button onClick={() => handleZoomAction('page')}>Ajustar à Página</button>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="header-right">
            {currentPDF && (
              <button
                className="icon-button"
                onClick={handleSavePDF}
                title="Salvar PDF com Anotações"
                style={{ marginRight: '8px' }}
              >
                <Save size={20} />
              </button>
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
        <div className="pdf-viewer" style={{ position: 'relative', zIndex: 'auto' }}>
          {currentPDF ? (
            <React.Suspense fallback={<div className="flex items-center justify-center h-full"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div></div>}>
              {/* @ts-ignore */}
              <PDFEditor
                url={currentPDF}
                activeColor={activeColor}
                zoom={pdfZoom}
                isAreaSelectionMode={isAreaSelectionMode}
                highlights={highlights}
                onAddHighlight={handleAddHighlight}
                onUpdateHighlight={handleUpdateHighlight}
                onLoadAnnotations={handleExtractedColors}
                applyPdfTint={applyPdfTint}
              />
            </React.Suspense>
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
      {
        !isSidebarCollapsed && !multiWindowMode && (
          <div
            ref={resizeRef}
            className={`resize-handle ${isResizing ? 'active' : ''}`}
            onMouseDown={() => setIsResizing(true)}
          >
            <GripVertical size={16} />
          </div>
        )
      }

      {/* Chat Sidebar */}
      <aside
        className={`chat-sidebar ${isSidebarCollapsed || multiWindowMode ? 'collapsed' : ''}`}
        style={{ width: (isSidebarCollapsed || multiWindowMode) ? (multiWindowMode ? 0 : 48) : sidebarWidth, display: multiWindowMode ? 'none' : 'flex' }}
      >
        <button
          className="sidebar-toggle"
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          title={isSidebarCollapsed ? "Expandir chat" : "Recolher chat"}
        >
          {isSidebarCollapsed ? <ChevronLeft size={20} /> : <ChevronRightIcon size={20} />}
        </button>

        {!(isSidebarCollapsed || multiWindowMode) && (
          <div className="sidebar-content-wrapper">
            {/* Sidebar Header */}
            <div className="sidebar-header" data-tauri-drag-region>
              <div className="header-left-actions">
                <div className="sidebar-title" data-tauri-drag-region>
                  <span data-tauri-drag-region>Chat</span>
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
                        autoStartPrompt={sessionData.autoStartPrompt}
                        onGenerationFinished={(assistantMsg) => {
                          if ((sessionData.title === 'Nova Conversa' || sessionData.title.startsWith('Chat: ')) && !sessionData.titlingAttempted && !inFlightTitling.current.has(sessionId)) {
                            inFlightTitling.current.add(sessionId);
                            console.log(`[AutoTitle] Callback trigger for ${sessionId}`);
                            generateSessionTitle(sessionId, sessionData.messages[0]?.content || '', assistantMsg);
                            setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, titlingAttempted: true } : s));
                          }
                        }}
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
    </div >
  );
}

export default App;
