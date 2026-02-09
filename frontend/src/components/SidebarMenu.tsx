import React from 'react';
import { Plus, MessageSquare, Trash2, X, MoreVertical } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './SidebarMenu.css';

export interface Session {
    id: string;
    title: string;
    date: Date;
    preview: string;
}

interface SidebarMenuProps {
    isOpen: boolean;
    onClose: () => void;
    sessions: Session[];
    activeSessionId: string | null;
    onSelectSession: (id: string) => void;
    onNewSession: () => void;
    onDeleteSession: (id: string, e: React.MouseEvent) => void;
}

export const SidebarMenu: React.FC<SidebarMenuProps> = ({
    isOpen,
    onClose,
    sessions,
    activeSessionId,
    onSelectSession,
    onNewSession,
    onDeleteSession
}) => {
    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="sidebar-overlay"
                        onClick={onClose}
                    />
                    <motion.div
                        initial={{ x: -280 }}
                        animate={{ x: 0 }}
                        exit={{ x: -280 }}
                        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                        className="sidebar-menu"
                    >
                        <div className="sidebar-header-area">
                            <h2>Minhas Conversas</h2>
                            <button onClick={onClose} className="close-btn">
                                <X size={20} />
                            </button>
                        </div>

                        <button className="new-chat-btn" onClick={onNewSession}>
                            <Plus size={18} />
                            Nova Conversa
                        </button>

                        <div className="sessions-list">
                            {sessions.length === 0 ? (
                                <div className="empty-sessions">
                                    <MessageSquare size={32} />
                                    <p>Nenhuma conversa salva</p>
                                </div>
                            ) : (
                                sessions.map(session => (
                                    <div
                                        key={session.id}
                                        className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
                                        onClick={() => onSelectSession(session.id)}
                                    >
                                        <div className="session-item-content">
                                            <span className="session-item-title">{session.title}</span>
                                            <span className="session-item-date">
                                                {session.date.toLocaleDateString()}
                                            </span>
                                        </div>
                                        <button
                                            className="delete-session-btn"
                                            onClick={(e) => onDeleteSession(session.id, e)}
                                            title="Excluir conversa"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                ))
                            )}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};
