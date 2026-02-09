
import { motion } from 'framer-motion';
import { X, Terminal, Cpu, HardDrive, Info } from 'lucide-react';
import './DebugMenu.css';

interface DebugMenuProps {
    isOpen: boolean;
    onClose: () => void;
    health: any;
    stats: any;
    tauriStatus?: any;
}

export function DebugMenu({ isOpen, onClose, health, stats, tauriStatus }: DebugMenuProps) {
    if (!isOpen) return null;

    const debugInfo = {
        frontend: {
            version: '0.2.0',
            user_agent: navigator.userAgent,
            timestamp: new Date().toISOString(),
        },
        backend: health ? {
            status: health.status,
            engine: health.backend,
            gpu: health.gpu_available ? 'Available' : 'Unavailable',
            docs: health.documents_indexed,
            model_loaded: health.model_available ? 'Yes' : 'No'
        } : 'Not Connected',
        tauri: tauriStatus || 'N/A',
        system: stats ? {
            platform: stats.platform,
            backend_api: stats.backend,
            models_dir: stats.model_dir,
            uploads_dir: stats.uploads_dir,
            vectors: stats.vector_store?.points_count || 0
        } : 'No Stats'
    };

    const copyToClipboard = () => {
        const text = JSON.stringify(debugInfo, null, 2);
        navigator.clipboard.writeText(text);
        alert('Debug info copied to clipboard!');
    };

    return (
        <div className="debug-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="debug-modal glass-panel"
            >
                <div className="debug-header">
                    <h2><Terminal size={20} /> Debug Info</h2>
                    <div className="debug-header-actions">
                        <button className="copy-btn" onClick={copyToClipboard}>Copy JSON</button>
                        <button className="close-button" onClick={onClose}><X /></button>
                    </div>
                </div>

                <div className="debug-content">
                    <section>
                        <h3><Info size={16} /> Backend Connectivity</h3>
                        <pre className="selectable">
                            {`Status: ${health?.status || 'Offline'}
API URL: http://127.0.0.1:8000
GPU Access: ${health?.gpu_available ? 'YES' : 'NO'}
Active Engine: ${health?.backend || 'None'}`}
                        </pre>
                    </section>

                    <section>
                        <h3><Cpu size={16} /> System & Tauri</h3>
                        <pre className="selectable">
                            {`Platform: ${stats?.platform || 'Unknown'}
Build Mode: ${import.meta.env.MODE}
Tauri Sidecar: ${tauriStatus?.alive ? 'RUNNING' : 'NOT RUNNING'}
Sidecar PID: ${tauriStatus?.pid || 'N/A'}`}
                        </pre>
                    </section>

                    <section>
                        <h3><HardDrive size={16} /> Storage & Data</h3>
                        <pre className="selectable">
                            {`Models Dir: ${stats?.model_dir || 'N/A'}
Uploads Dir: ${stats?.uploads_dir || 'N/A'}
Indexed Docs: ${health?.documents_indexed || 0}
Vector Points: ${stats?.vector_store?.points_count || 0}`}
                        </pre>
                    </section>

                    <div className="debug-footer">
                        <p>Press Option + D / Alt + D to toggle this menu</p>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
