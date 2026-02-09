import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children?: ReactNode;
    fallback?: ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
    errorInfo?: ErrorInfo;
}

export class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false
    };

    public static getDerivedStateFromError(error: Error): State {
        // Update state so the next render will show the fallback UI.
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
        this.setState({ errorInfo });
    }

    public render() {
        if (this.state.hasError) {
            return (
                <div style={{
                    padding: '40px',
                    background: '#0a0a0f',
                    color: '#ef4444',
                    height: '100vh',
                    overflow: 'auto',
                    fontFamily: 'monospace'
                }}>
                    <h2>Algo deu errado na interface.</h2>
                    <details style={{ whiteSpace: 'pre-wrap', marginTop: '20px' }}>
                        <summary>Detalhes do Erro</summary>
                        <h3>{this.state.error?.toString()}</h3>
                        <p>{this.state.errorInfo?.componentStack}</p>
                    </details>
                    <button
                        onClick={() => window.location.reload()}
                        style={{
                            marginTop: '20px',
                            padding: '10px 20px',
                            background: '#6366f1',
                            color: 'white',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: 'pointer'
                        }}
                    >
                        Recarregar Aplicação
                    </button>
                </div>
            );
        }

        return this.props.children;
    }
}
