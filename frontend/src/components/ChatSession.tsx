import React, { useState, useRef, useEffect } from 'react';
import { Send, FileText, ChevronDown, Sparkles, X, Square, Database, MessageSquare } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import Markdown from 'react-markdown';
import './ChatSession.css';

const API_URL = 'http://127.0.0.1:8000';

export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    sources?: { text: string; page?: number }[];
    isStreaming?: boolean;
}

export interface ChatSessionProps {
    sessionId: string;
    title: string;
    isActive: boolean;
    onClose?: () => void;
    contextFilter?: string | null; // Nome do PDF para filtrar contexto
    searchMode?: 'local' | 'global';
    initialMessages?: Message[];
    onMessagesChange?: (messages: Message[]) => void;
    autoStartPrompt?: string | null;
    onGenerationFinished?: (lastAssistantMsg: string) => void;
    color?: string;
    includeOtherChats?: boolean;
    onToggleIncludeOtherChats?: (val: boolean) => void;
    onToggleSearchMode?: (val: 'local' | 'global') => void;
}

export const ChatSession: React.FC<ChatSessionProps> = ({
    sessionId,
    title,
    isActive,
    onClose,
    contextFilter,
    searchMode = 'local',
    initialMessages = [],
    onMessagesChange,
    autoStartPrompt,
    onGenerationFinished,
    color,
    includeOtherChats = false,
    onToggleIncludeOtherChats,
    onToggleSearchMode
}) => {
    const [messages, setMessages] = useState<Message[]>(initialMessages);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [showSources, setShowSources] = useState<string | null>(null);
    const autoStartedRef = useRef(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Scroll to bottom on new messages
    useEffect(() => {
        if (isActive) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isActive]);

    const handleMessagesUpdate = async (newMessages: Message[] | ((prev: Message[]) => Message[])) => {
        setMessages(prev => {
            const updated = typeof newMessages === 'function' ? newMessages(prev) : newMessages;

            if (onMessagesChange) {
                setTimeout(() => onMessagesChange(updated), 0);
            }
            return updated;
        });
    };

    const saveMessageToBackend = async (role: string, content: string, sources?: any[]) => {
        try {
            await fetch(`${API_URL}/sessions/${sessionId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role, content, sources })
            });
        } catch (e) {
            console.error('Failed to save message to backend:', e);
        }
    };

    const [isStopping, setIsStopping] = useState(false);

    const stopGeneration = async () => {
        setIsStopping(true);
        try {
            await fetch(`${API_URL}/chat/stop`, { method: 'POST' });
        } catch (e) {
            console.error("Erro ao parar geração:", e);
        } finally {
            // isStopping will be reset when sendMessage finishes its try/catch/finally
        }
    };

    const sendMessage = async (overridePrompt?: string) => {
        const textToSend = overridePrompt || input.trim();
        if (!textToSend || loading) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: textToSend
        };

        if (!overridePrompt) setInput('');
        setLoading(true);

        const assistantMsgId = (Date.now() + 1).toString();
        let fullResponse = "";
        let sources: any[] = [];

        // Adicionar mensagem temporária de assistente para streaming
        handleMessagesUpdate(prev => [...prev, {
            id: assistantMsgId,
            role: 'assistant',
            content: '',
            isStreaming: true
        }]);

        try {
            const response = await fetch(`${API_URL}/chat/stream`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userMsg.content,
                    source_filter: contextFilter,
                    search_mode: searchMode,
                    color_filter: color,
                    include_past_chats: includeOtherChats
                })
            });

            // Save user message to backend
            saveMessageToBackend('user', userMsg.content);

            if (!response.ok) throw new Error(response.statusText);

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No reader available");

            const decoder = new TextDecoder();
            let buffer = '';
            let streamDone = false;

            while (!streamDone) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    const trimmedLine = line.trim();
                    if (trimmedLine.startsWith('data: ')) {
                        const data = trimmedLine.slice(6);
                        if (data === '[DONE]') {
                            streamDone = true;
                            break;
                        }

                        try {
                            const parsed = JSON.parse(data);

                            if (parsed.type === 'token') {
                                fullResponse += parsed.content;
                                handleMessagesUpdate(prev => prev.map(msg =>
                                    msg.id === assistantMsgId
                                        ? { ...msg, content: fullResponse }
                                        : msg
                                ));
                            } else if (parsed.type === 'sources') {
                                sources = parsed.data;
                            } else if (parsed.type === 'finished') {
                                if (onGenerationFinished) {
                                    onGenerationFinished(fullResponse);
                                }
                            } else if (parsed.type === 'error') {
                                fullResponse += `\n\n[Erro: ${parsed.message}]`;
                            }
                        } catch (e) {
                            console.error("Erro ao parsear JSON no SSE:", e, "Data:", data);
                        }
                    }
                }
            }
        } catch (error) {
            fullResponse += "\n\n[Erro de conexão com o servidor]";
        } finally {
            setLoading(false);
            setIsStopping(false);
            handleMessagesUpdate(prev => prev.map(msg =>
                msg.id === assistantMsgId
                    ? { ...msg, content: fullResponse, isStreaming: false, sources: sources }
                    : msg
            ));

            // Save assistant message to backend
            if (fullResponse) {
                saveMessageToBackend('assistant', fullResponse, sources);
            }
        }
    };

    // Auto-start summary if needed
    useEffect(() => {
        if (isActive && !loading && messages.length === 0 && autoStartPrompt && !autoStartedRef.current) {
            autoStartedRef.current = true;
            sendMessage(autoStartPrompt);
        }
    }, [isActive, messages.length, autoStartPrompt, loading]);

    if (!isActive) return null;

    return (
        <div className="chat-session-container">
            {/* Header da Sessão (caso mostrado em modo grid/multi-view) */}
            <div className="session-header" data-tauri-drag-region>
                <div className="session-info" data-tauri-drag-region>
                    <span className="session-icon" style={{ color: color || 'var(--accent)' }} data-tauri-drag-region><Sparkles size={14} /></span>
                    <span className="session-title" data-tauri-drag-region>{title}</span>
                </div>

                <div className="session-controls">
                    {/* Search Mode Toggle */}
                    <button
                        className={`control-btn ${searchMode === 'global' ? 'active' : ''}`}
                        onClick={() => onToggleSearchMode?.(searchMode === 'local' ? 'global' : 'local')}
                        title={searchMode === 'local' ? "Pesquisar apenas neste documento" : "Pesquisar em todos os documentos"}
                    >
                        {searchMode === 'local' ? <FileText size={14} /> : <Database size={14} />}
                        <span>{searchMode === 'local' ? 'Local' : 'Global'}</span>
                    </button>

                    {/* Multi-Chat Context Toggle */}
                    <button
                        className={`control-btn ${includeOtherChats ? 'active' : ''}`}
                        onClick={() => onToggleIncludeOtherChats?.(!includeOtherChats)}
                        title="Incluir contexto de outras conversas"
                    >
                        <MessageSquare size={14} />
                    </button>

                    {onClose && (
                        <button className="close-btn" onClick={onClose}><X size={14} /></button>
                    )}
                </div>
            </div>

            {/* Lista de Mensagens */}
            <div className="messages-area">
                {messages.length === 0 ? (
                    <div className="empty-state">
                        <Sparkles size={48} className="empty-icon" />
                        <h3>Comece uma nova conversa</h3>
                        <p>{contextFilter ? `Contexto: ${contextFilter}` : "Contexto Global"}</p>
                        {color && <p style={{ fontSize: '0.8rem', marginTop: '4px', opacity: 0.8 }}>Filtro de cor: <span style={{ display: 'inline-block', width: '10px', height: '10px', backgroundColor: color, borderRadius: '50%', marginLeft: '4px' }}></span></p>}
                    </div>
                ) : (
                    messages.map((msg) => (
                        <motion.div
                            key={msg.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className={`message-bubble ${msg.role}`}
                        >
                            <div className="message-text">
                                <Markdown>{msg.content}</Markdown>
                                {msg.isStreaming && <span className="cursor-blink">|</span>}
                            </div>

                            {msg.sources && msg.sources.length > 0 && (
                                <div className="sources-container">
                                    <button
                                        className="sources-toggle-btn"
                                        onClick={() => setShowSources(showSources === msg.id ? null : msg.id)}
                                    >
                                        <FileText size={12} />
                                        {msg.sources.length} fontes
                                        <ChevronDown size={12} className={showSources === msg.id ? "rotate-180" : ""} />
                                    </button>

                                    <AnimatePresence>
                                        {showSources === msg.id && (
                                            <motion.div
                                                initial={{ height: 0, opacity: 0 }}
                                                animate={{ height: "auto", opacity: 1 }}
                                                exit={{ height: 0, opacity: 0 }}
                                                className="sources-content"
                                            >
                                                {msg.sources.map((src, idx) => (
                                                    <div key={idx} className="source-item">
                                                        <span className="source-page">p. {src.page}</span>
                                                        <p>{src.text}</p>
                                                    </div>
                                                ))}
                                            </motion.div>
                                        )}
                                    </AnimatePresence>
                                </div>
                            )}
                        </motion.div>
                    ))
                )}
                {loading && !messages.find(m => m.isStreaming) && (
                    <div className="loading-indicator">
                        <span className="dot"></span>
                        <span className="dot"></span>
                        <span className="dot"></span>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="input-area">
                <div className="input-wrapper">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                        placeholder={`O que vamos ler hoje?`}
                        disabled={loading}
                    />
                    <button
                        onClick={() => loading ? stopGeneration() : sendMessage()}
                        disabled={(!input.trim() && !loading) || isStopping}
                        className={`send-btn ${loading ? 'loading' : ''} ${isStopping ? 'stopping' : ''}`}
                        title={isStopping ? "Parando..." : (loading ? "Parar geração" : "Enviar mensagem")}
                    >
                        {loading ? <Square size={16} fill="currentColor" /> : <Send size={16} />}
                    </button>
                </div>
            </div>
        </div>
    );
};
