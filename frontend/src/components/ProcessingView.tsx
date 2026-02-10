import React from 'react';
import { motion } from 'framer-motion';
import { Sparkles, FileText } from 'lucide-react';
import './ProcessingView.css';

interface ProcessingViewProps {
    fileName: string;
    progressText?: string | null;
}

export const ProcessingView: React.FC<ProcessingViewProps> = ({
    fileName,
    progressText
}) => {
    return (
        <div className="processing-container">
            {/* Background Decorative Elements */}
            <div className="proc-bg-glow-1" />
            <div className="proc-bg-glow-2" />
            <div className="proc-bg-glow-3" />

            <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="processing-content"
            >
                {/* Animated Icon */}
                <div className="proc-icon-area">
                    <div className="orbit-ring ring-1">
                        <div className="orbit-dot" />
                    </div>
                    <div className="orbit-ring ring-2">
                        <div className="orbit-dot" />
                    </div>
                    <div className="orbit-ring ring-3">
                        <div className="orbit-dot" />
                    </div>

                    <div className="proc-center-icon">
                        <FileText size={48} />
                        <div className="scan-line" />
                    </div>
                </div>

                {/* Text */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3, duration: 0.4 }}
                    className="proc-text-area"
                >
                    <h2 className="proc-title">Estudando PDF</h2>
                    <p className="proc-filename">{fileName}</p>

                    {/* Animated Progress Dots */}
                    <div className="proc-status">
                        <Sparkles size={16} className="proc-sparkle" />
                        <span>{progressText || 'Analisando conteúdo...'}</span>
                        <span className="dot-animation">
                            <span className="dot">.</span>
                            <span className="dot">.</span>
                            <span className="dot">.</span>
                        </span>
                    </div>
                </motion.div>

                {/* Animated Progress Bar */}
                <div className="proc-progress-track">
                    <div className="proc-progress-shimmer" />
                </div>
            </motion.div>
        </div>
    );
};
