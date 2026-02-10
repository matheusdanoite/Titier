import React, { useState, useRef, useEffect } from 'react';
import { Send, FileText, ChevronDown, Sparkles, X } from 'lucide-react';
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
}

export const ChatSession: React.FC<ChatSessionProps> = ({
    title,
    isActive,
    onClose,
    contextFilter,
    searchMode = 'local',
    initialMessages = [],
    onMessagesChange,
    autoStartPrompt
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

    const handleMessagesUpdate = (newMessages: Message[] | ((prev: Message[]) => Message[])) => {
        setMessages(prev => {
            const updated = typeof newMessages === 'function' ? newMessages(prev) : newMessages;
            if (onMessagesChange) {
                // Defer update to avoid render cycle issues, or just call it
                setTimeout(() => onMessagesChange(updated), 0);
            }
            return updated;
        });
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
                    // TODO: Pass history properly if backend supports it
                })
            });

            if (!response.ok) throw new Error(response.statusText);

            const reader = response.body?.getReader();
            if (!reader) throw new Error("No reader available");

            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n\n');

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') break;

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
                            } else if (parsed.type === 'error') {
                                fullResponse += `\n\n[Erro: ${parsed.message}]`;
                            }
                        } catch (e) {
                            console.error("Erro ao parsear SSE:", e);
                        }
                    }
                }
            }
        } catch (error) {
            fullResponse += "\n\n[Erro de conexão com o servidor]";
        } finally {
            setLoading(false);
            handleMessagesUpdate(prev => prev.map(msg =>
                msg.id === assistantMsgId
                    ? { ...msg, content: fullResponse, isStreaming: false, sources: sources }
                    : msg
            ));
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
            <div className="session-header">
                <div className="session-info">
                    <span className="session-icon"><Sparkles size={14} /></span>
                    <span className="session-title">{title}</span>
                </div>
                {onClose && (
                    <button onClick={onClose} className="close-session-btn" title="Fechar conversa">
                        <X size={14} />
                    </button>
                )}
            </div>

            {/* Lista de Mensagens */}
            <div className="messages-area">
                {messages.length === 0 ? (
                    <div className="empty-state">
                        <Sparkles size={48} className="empty-icon" />
                        <h3>Comece uma nova conversa</h3>
                        <p>{contextFilter ? `Contexto: ${contextFilter}` : "Contexto Global"}</p>
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
                        placeholder={`Pergunte algo sobre ${contextFilter || 'seus documentos'}...`}
                        disabled={loading}
                    />
                    <button
                        onClick={() => sendMessage()}
                        disabled={!input.trim() || loading}
                        className="send-btn"
                    >
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </div>
    );
};
