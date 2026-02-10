import React from 'react';
import { motion } from 'framer-motion';
import { Upload, Settings, Sparkles, FileText, MousePointer2 } from 'lucide-react';
import './EmptyState.css';

interface EmptyStateProps {
    onFileSelect: () => void;
    onSettingsClick: () => void;
    isDragging: boolean;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
    onFileSelect,
    onSettingsClick,
    isDragging
}) => {
    return (
        <div className={`empty-state-container ${isDragging ? 'is-dragging' : ''}`}>
            {/* Background Decorative Elements */}
            <div className="bg-glow-top" />
            <div className="bg-glow-bottom" />

            <div className="empty-state-content">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                    className="empty-state-card glass-panel"
                >
                    <div className="settings-shortcut-container">
                        <button
                            className="icon-button settings-btn"
                            onClick={onSettingsClick}
                            title="Configurações"
                        >
                            <Settings size={20} />
                        </button>
                    </div>

                    <div className="icon-wrapper">
                        <motion.div
                            animate={isDragging ? { scale: 1.2, rotate: 10 } : { scale: 1, rotate: 0 }}
                            className="main-icon-container"
                        >
                            <Upload size={64} className="main-icon" />
                        </motion.div>
                        <Sparkles className="sparkle-icon" size={24} />
                    </div>

                    <div className="text-content">
                        <h2 className="highlight-text">Nenhum documento carregado</h2>
                        <p className="description">
                            Titier está pronto para ajudar nos seus estudos.
                            <br />
                            Forneça um arquivo PDF para começar a interagir.
                        </p>
                    </div>

                    <div className="actions">
                        <button className="primary-button large upload-btn" onClick={onFileSelect}>
                            <FileText size={20} />
                            Selecionar PDF
                        </button>
                    </div>

                    <div className="drop-indicator">
                        <MousePointer2 size={16} />
                        <span>Ou arraste o PDF para qualquer lugar aqui</span>
                    </div>
                </motion.div>
            </div>

            {/* Drag Hint Overlay (only visible when dragging) */}
            {isDragging && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="drag-hint-overlay"
                >
                    <div className="drag-hint-content">
                        <div className="upload-circle">
                            <Upload size={48} />
                        </div>
                        <h3>Solte para fazer o upload</h3>
                    </div>
                </motion.div>
            )}
        </div>
    );
};
