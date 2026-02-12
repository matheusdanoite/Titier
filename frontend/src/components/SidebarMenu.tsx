import React from 'react';
import { Plus, MessageSquare, Trash2, X, Settings, Edit2, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import './SidebarMenu.css';

import { Session } from '../types';

interface SidebarMenuProps {
    isOpen: boolean;
    onClose: () => void;
    sessions: Session[];
    activeSessionId: string | null;
    onSelectSession: (id: string) => void;
    onNewSession: () => void;
    onDeleteSession: (id: string, e: React.MouseEvent) => void;
    onRenameSession: (id: string, newTitle: string) => void;
    onOpenSettings: () => void;
}

export const SidebarMenu: React.FC<SidebarMenuProps> = ({
    isOpen,
    onClose,
    sessions,
    activeSessionId,
    onSelectSession,
    onNewSession,
    onDeleteSession,
    onRenameSession,
    onOpenSettings
}) => {
    const [editingId, setEditingId] = React.useState<string | null>(null);
    const [editTitle, setEditTitle] = React.useState('');
    const editInputRef = React.useRef<HTMLInputElement>(null);

    React.useEffect(() => {
        if (editingId && editInputRef.current) {
            editInputRef.current.focus();
            editInputRef.current.select();
        }
    }, [editingId]);

    const handleStartEdit = (e: React.MouseEvent, session: Session) => {
        e.stopPropagation();
        setEditingId(session.id);
        setEditTitle(session.title);
    };

    const handleSaveEdit = (e?: React.FormEvent | React.MouseEvent) => {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        if (editingId && editTitle.trim()) {
            onRenameSession(editingId, editTitle.trim());
        }
        setEditingId(null);
    };

    const handleCancelEdit = () => {
        setEditingId(null);
    };
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
                                        className={`session-item ${activeSessionId === session.id ? 'active' : ''} ${editingId === session.id ? 'editing' : ''}`}
                                        onClick={() => editingId !== session.id && onSelectSession(session.id)}
                                        style={{ borderLeft: session.color ? `4px solid ${session.color}` : '4px solid transparent' }}
                                    >
                                        <div className="session-item-content">
                                            {editingId === session.id ? (
                                                <form className="edit-form" onSubmit={handleSaveEdit} onClick={e => e.stopPropagation()}>
                                                    <input
                                                        ref={editInputRef}
                                                        type="text"
                                                        value={editTitle}
                                                        onChange={e => setEditTitle(e.target.value)}
                                                        onKeyDown={e => e.key === 'Escape' && handleCancelEdit()}
                                                        onBlur={() => handleSaveEdit()}
                                                        className="edit-input"
                                                    />
                                                </form>
                                            ) : (
                                                <>
                                                    <span className="session-item-title">{session.title}</span>
                                                    <span className="session-item-date">
                                                        {session.date.toLocaleDateString()}
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                        <div className="session-actions">
                                            {editingId === session.id ? (
                                                <button
                                                    className="save-session-btn"
                                                    onClick={handleSaveEdit}
                                                    title="Salvar"
                                                >
                                                    <Check size={14} />
                                                </button>
                                            ) : (
                                                <>
                                                    <button
                                                        className="edit-session-btn"
                                                        onClick={(e) => handleStartEdit(e, session)}
                                                        title="Renomear"
                                                    >
                                                        <Edit2 size={14} />
                                                    </button>
                                                    <button
                                                        className="delete-session-btn"
                                                        onClick={(e) => onDeleteSession(session.id, e)}
                                                        title="Excluir conversa"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                        </div>

                        <div className="sidebar-footer">
                            <div className="divider" />
                            <button
                                className="settings-btn"
                                onClick={() => {
                                    onOpenSettings();
                                    onClose();
                                }}
                            >
                                <Settings size={18} />
                                Configurações
                            </button>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};
