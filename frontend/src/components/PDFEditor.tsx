import React, { useState, useRef, useEffect } from 'react';
import {
    PdfLoader,
    PdfHighlighter,
    TextHighlight,
    AreaHighlight,

    useHighlightContainerContext,
    usePdfHighlighterContext,
    PdfHighlighterUtils,
    scaledPositionToViewport,
    ScaledPosition
} from 'react-pdf-highlighter-extended-plus';
import 'react-pdf-highlighter-extended-plus/dist/esm/style/PdfHighlighter.css';
import 'react-pdf-highlighter-extended-plus/dist/esm/style/TextHighlight.css';
import 'react-pdf-highlighter-extended-plus/dist/esm/style/AreaHighlight.css';
import 'react-pdf-highlighter-extended-plus/dist/esm/style/MouseSelection.css';
import 'react-pdf-highlighter-extended-plus/dist/esm/style/pdf_viewer.css';
import './PDFEditor.css';
import { Loader2, StickyNote } from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
// Set up the worker
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { IHighlight } from '../types';

try {
    pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorker;
    console.log('PDF Worker Configured:', pdfWorker);
} catch (e) {
    console.error('Failed to configure PDF Worker:', e);
}

interface PDFEditorProps {
    url: string;
    activeColor?: string;
    zoom: number;
    onLoadAnnotations?: (colors: string[]) => void;
    applyPdfTint?: boolean;
    onHighlightClick?: (highlight: IHighlight) => void;

    // Props explicitly used in the component but missing from interface in previous version
    isAreaSelectionMode: boolean;
    highlights: IHighlight[];
    onAddHighlight: (highlight: IHighlight) => void;
    onUpdateHighlight: (id: string, position: Partial<IHighlight['position']>, content: Partial<IHighlight['content']>) => void;
}

const Popup = ({
    onMouseOver,
    popupContent,
    onMouseOut,
    children,
}: {
    onMouseOver: (content: React.ReactNode) => void;
    popupContent: React.ReactNode;
    onMouseOut: () => void;
    children: React.ReactNode;
}) => {
    return (
        <div
            onMouseOver={() => {
                onMouseOver(popupContent);
            }}
            onMouseOut={() => {
                onMouseOut();
            }}
        >
            {children}
        </div>
    );
};

const HighlightPopup = ({
    comment,
    onEdit
}: {
    comment: { text: string; author: string; timestamp: number };
    onEdit: () => void;
}) => (
    <div className="Highlight__popup">
        {comment.text ? (
            <>
                <div className="popup-header">
                    <strong>{comment.author}</strong>
                    <span className="popup-date">{new Date(comment.timestamp).toLocaleString()}</span>
                </div>
                <div className="popup-content">
                    {comment.text}
                </div>
            </>
        ) : (
            <div className="popup-content" style={{ padding: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }} onClick={onEdit}>
                <StickyNote size={14} /> Inserir Nota
            </div>
        )}
    </div>
);

const SelectionMenu = ({
    onHighlight,
    onAddNote
}: {
    onHighlight: () => void;
    onAddNote: () => void;
}) => (
    <div className="Tip__menu">
        <button className="Tip__menu__btn" onClick={(e) => { e.preventDefault(); onHighlight(); }}>
            <div style={{ width: '12px', height: '12px', background: 'currentColor', borderRadius: '2px', marginRight: '6px' }} />
            Destacar
        </button>
        <button className="Tip__menu__btn" onClick={(e) => { e.preventDefault(); onAddNote(); }}>
            <StickyNote size={14} style={{ marginRight: '6px' }} />
            Nota
        </button>
    </div>
);

const NoteContent = ({
    onConfirm,
    color,
    initialText = ""
}: {
    onConfirm: (comment: { text: string; author: string; timestamp: number }) => void;
    color: string;
    initialText?: string;
}) => {
    const [text, setText] = useState(initialText);

    return (
        <div className="Tip" style={{ borderTop: `4px solid ${color}` }}>
            <div className="Tip__header">
                <span>Inserir Nota</span>
            </div>
            <div className="Tip__card">
                <textarea
                    placeholder="Escreva suas anotações..."
                    autoFocus
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    className="w-full text-sm p-2 border rounded"
                    rows={3}
                />
                <div className="flex justify-end mt-2 gap-2">
                    <button className="Tip__btn" onClick={() => onConfirm({ text, author: "Você", timestamp: Date.now() })}>Salvar</button>
                </div>
            </div>
        </div>
    );
};

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error: Error | null }> {
    constructor(props: { children: React.ReactNode }) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error("PDFEditor Error:", error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="p-4 text-red-500 bg-red-50 border border-red-200 rounded">
                    <h3>Something went wrong in PDF Editor.</h3>
                    <pre className="text-xs mt-2 overflow-auto">{this.state.error?.toString()}</pre>
                    <pre className="text-xs mt-2 overflow-auto">{this.state.error?.stack}</pre>
                </div>
            );
        }

        return this.props.children;
    }
}

const rgbToHex = (r: number, g: number, b: number) => {
    return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
};

const ColorExtractor = ({ pdfDocument, onLoadColors }: { pdfDocument: any, onLoadColors?: (colors: string[]) => void }) => {
    useEffect(() => {
        if (!pdfDocument || !onLoadColors) return;

        const extractColors = async () => {
            console.log("ColorExtractor: Starting deep extraction...");
            const colors = new Set<string>();
            const numPages = pdfDocument.numPages;
            const pagesToScan = Math.min(numPages, 50);

            for (let i = 1; i <= pagesToScan; i++) {
                try {
                    const page = await pdfDocument.getPage(i);
                    const annotations = await page.getAnnotations();

                    if (annotations.length > 0) {
                        console.log(`Page ${i}: Scanning ${annotations.length} annotations...`);

                        annotations.forEach((annot: any, index: number) => {
                            // Log every annotation's type and color raw data
                            const debugColor = annot.color || 'no-color';
                            const debugSubtype = annot.subtype;

                            let debugHex = 'N/A';
                            if (annot.color && annot.color.length === 3) {
                                const [r, g, b] = annot.color;
                                const isFloat = r <= 1 && g <= 1 && b <= 1;
                                const R = isFloat ? Math.floor(r * 255) : r;
                                const G = isFloat ? Math.floor(g * 255) : g;
                                const B = isFloat ? Math.floor(b * 255) : b;
                                debugHex = rgbToHex(R, G, B);
                            }

                            console.log(`[P${i}:A${index}] Type: ${debugSubtype}, Color: ${debugColor}, Hex: ${debugHex}`);

                            // Capture everything valid
                            if (annot.color && annot.color.length === 3) {
                                const [r, g, b] = annot.color;
                                if (typeof r === 'number' && typeof g === 'number' && typeof b === 'number') {
                                    const isFloat = r <= 1 && g <= 1 && b <= 1;
                                    const finalR = isFloat ? Math.floor(r * 255) : r;
                                    const finalG = isFloat ? Math.floor(g * 255) : g;
                                    const finalB = isFloat ? Math.floor(b * 255) : b;
                                    const hex = rgbToHex(finalR, finalG, finalB);

                                    colors.add(hex);
                                }
                            }
                        });
                    }
                } catch (e) {
                    console.error('Error extracting colors from page', i, e);
                }
            }

            console.log("ColorExtractor: Native extraction finished. Colors:", Array.from(colors));
            if (colors.size > 0) {
                onLoadColors(Array.from(colors));
            } else {
                onLoadColors([]);
            }
        };

        extractColors();
    }, [pdfDocument, onLoadColors]);

    return null;
};

const getColorStyle = (color: string) => {
    // If it's a hex code, return it directly with opacity
    if (color.startsWith('#')) {
        // Convert hex to rgba for opacity
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        return { backgroundColor: `rgba(${r}, ${g}, ${b}, 0.4)` };
    }

    switch (color) {
        case 'green': return { backgroundColor: 'rgba(74, 222, 128, 0.4)' };
        case 'blue': return { backgroundColor: 'rgba(96, 165, 250, 0.4)' };
        case 'red': return { backgroundColor: 'rgba(248, 113, 113, 0.4)' };
        case 'yellow':
        default: return { backgroundColor: 'rgba(250, 204, 21, 0.4)' };
    }
};

const SelectionHandler = ({
    selection,
    onActionTaken,
    addHighlight,
    activeColor,
    highlighterUtils
}: {
    selection: any;
    onActionTaken: () => void;
    addHighlight: (h: IHighlight) => void;
    activeColor: string;
    highlighterUtils: PdfHighlighterUtils | null;
}) => {
    const { setTip } = usePdfHighlighterContext();

    useEffect(() => {
        if (!selection) {
            setTip(null);
            return;
        }

        const viewer = highlighterUtils?.getViewer();
        if (!viewer) return;

        // Convert ScaledPosition to ViewportPosition for the Tip
        const viewportPosition = scaledPositionToViewport(selection.position, viewer);

        setTip({
            position: viewportPosition as any,
            content: (
                <SelectionMenu
                    onHighlight={() => {
                        onActionTaken();
                        addHighlight({
                            content: selection.content,
                            position: selection.position,
                            comment: { text: '', author: '', timestamp: 0 },
                            id: Date.now().toString(),
                            color: activeColor
                        });
                        setTip(null);
                    }}
                    onAddNote={() => {
                        onActionTaken();
                        setTip({
                            position: viewportPosition as any,
                            content: (
                                <NoteContent
                                    color={activeColor}
                                    onConfirm={(comment) => {
                                        addHighlight({
                                            content: selection.content,
                                            position: selection.position,
                                            comment,
                                            id: Date.now().toString(),
                                            color: activeColor
                                        });
                                        setTip(null);
                                    }}
                                />
                            )
                        });
                    }}
                />
            )
        });
    }, [selection, setTip, onActionTaken, addHighlight, activeColor, highlighterUtils]);

    return null;
};

const PDFEditorContent: React.FC<PDFEditorProps> = ({ url, activeColor = '#facc15', zoom, isAreaSelectionMode, highlights, onAddHighlight, onUpdateHighlight, onLoadAnnotations, applyPdfTint = true }) => {
    const highlighterUtilsRef = useRef<PdfHighlighterUtils | null>(null);
    const [activeSelection, setActiveSelection] = useState<any>(null);
    const isActionTakenRef = useRef<boolean>(false);

    const addHighlight = (highlight: IHighlight) => {
        console.log("Saving highlight", highlight);
        onAddHighlight(highlight);
    };

    const handleActionTaken = () => {
        isActionTakenRef.current = true;
    };

    const updateHighlight = (highlightId: string, position: Partial<IHighlight['position']>, content: Partial<IHighlight['content']>) => {
        console.log("Updating highlight", highlightId, position, content);
        onUpdateHighlight(highlightId, position, content);
    };

    const HighlightContainer = () => {
        const { highlight, viewportToScaled, screenshot, isScrolledTo } = useHighlightContainerContext<IHighlight>();
        const { setTip } = usePdfHighlighterContext();

        const isTextHighlight = !Boolean(
            highlight.content && highlight.content.image
        );

        const component = isTextHighlight ? (
            <TextHighlight
                isScrolledTo={isScrolledTo}
                highlight={highlight}
                style={getColorStyle(highlight.color || 'yellow')}
            />
        ) : (
            <AreaHighlight
                isScrolledTo={isScrolledTo}
                highlight={highlight}
                onChange={(boundingRect) => {
                    updateHighlight(
                        highlight.id,
                        { boundingRect: viewportToScaled(boundingRect) },
                        { image: screenshot(boundingRect) }
                    );
                }}
            />
        );

        return (
            <Popup
                popupContent={
                    <HighlightPopup
                        comment={highlight.comment}
                        onEdit={() => {
                            const viewer = highlighterUtilsRef.current?.getViewer();
                            if (viewer) {
                                // Convert Scaled position back to Viewport for the TipContainer
                                // This ensures the tip is positioned correctly relative to the page
                                const viewportPosition = scaledPositionToViewport(highlight.position as unknown as ScaledPosition, viewer);
                                setTip({
                                    position: viewportPosition as any,
                                    content: (
                                        <NoteContent
                                            color={highlight.color || 'yellow'}
                                            onConfirm={(comment) => {
                                                onUpdateHighlight(highlight.id, {}, { comment: comment } as any);
                                                setTip(null);
                                            }}
                                        />
                                    )
                                });
                            }
                        }}
                    />
                }
                onMouseOver={(popupContent) => {
                    const viewer = highlighterUtilsRef.current?.getViewer();
                    if (viewer) {
                        const viewportPosition = scaledPositionToViewport(highlight.position as unknown as ScaledPosition, viewer);
                        setTip({ position: viewportPosition as any, content: popupContent });
                    }
                }}
                onMouseOut={() => {
                    setTip(null);
                }}
                children={component}
            />
        );
    };

    return (
        <div className="pdf-editor-container">
            <div className="pdf-editor-main" style={{ zIndex: applyPdfTint ? 'auto' : 2001, position: 'relative' }}>
                {/* Sidebar logic needs to be moved here if it was separate, but wait, the existing code didn't show sidebar in return? */}
                {/* Ah, I need to check the exact return of PDFEditorContent in previous view_file. */}
                {/* The previous view_file (313) showed return starting at 428. */}
                {/* Text: <div className="pdf-editor-container"><div className="pdf-editor-main">... */}
                {/* It seems Sidebar is MISSING in the view? Or I missed it? */}
                {/* Let's look at PDFEditor.css lines 44. It styles .pdf-editor-sidebar. */}
                {/* But the JSX in view_file 313 (lines 428-487) DOES NOT have .pdf-editor-sidebar. */}
                {/* It only has .pdf-editor-main. */}
                {/* Maybe Sidebar is rendered elsewhere? Or I need to add it? */}
                {/* Wait, the existing code I read in 313 DOES NOT have sidebar in JSX! */}
                {/* "pdf-editor-container" -> "pdf-editor-main". */}
                {/* If there is no sidebar in JSX, then my plan to 'un-isolate' container is still valid. */}
                {/* I will stick to modifying .pdf-editor-main style. */}
                <div className="pdf-editor-main" style={{ zIndex: applyPdfTint ? 'auto' : 2001, position: 'relative' }}>
                    <PdfLoader document={url} beforeLoad={() => <div className="flex items-center justify-center h-full"><Loader2 className="animate-spin" /></div>}>
                        {(pdfDocument) => {
                            const getScaleValue = (z: number): string | number => {
                                if (z === -1) return 'page-width';
                                if (z === -2) return 'page-fit';
                                return z / 100;
                            };

                            return (
                                <>
                                    <PdfHighlighter
                                        pdfDocument={pdfDocument}
                                        enableAreaSelection={(event) => isAreaSelectionMode || event.altKey}
                                        pdfScaleValue={getScaleValue(zoom) as any}
                                        utilsRef={(utils) => {
                                            highlighterUtilsRef.current = utils;
                                        }}
                                        onSelection={(selection) => {
                                            console.log("Selection changed:", selection);

                                            // Fallback logic: apenas se a nova seleção for null (clique para fora)
                                            // e houver uma seleção ativa que não foi confirmada.
                                            if (selection === null && activeSelection && !isActionTakenRef.current) {
                                                if (activeSelection.content.text || activeSelection.content.image) {
                                                    console.log("Applying fallback highlight (click away)");
                                                    addHighlight({
                                                        content: activeSelection.content,
                                                        position: activeSelection.position,
                                                        comment: { text: '', author: '', timestamp: 0 },
                                                        id: Date.now().toString(),
                                                        color: activeColor
                                                    });
                                                }
                                            }

                                            setActiveSelection(selection);
                                            isActionTakenRef.current = false;
                                        }}
                                        highlights={highlights}
                                    >
                                        <HighlightContainer />
                                        <SelectionHandler
                                            selection={activeSelection}
                                            onActionTaken={handleActionTaken}
                                            addHighlight={addHighlight}
                                            activeColor={activeColor}
                                            highlighterUtils={highlighterUtilsRef.current}
                                        />
                                    </PdfHighlighter>

                                    <ColorExtractor pdfDocument={pdfDocument} onLoadColors={onLoadAnnotations} />
                                </>
                            );
                        }}
                    </PdfLoader>
                </div>
            </div>
        </div>
    );
};

export const PDFEditor = (props: PDFEditorProps) => {
    const {
        url,
        activeColor,
        zoom,
        isAreaSelectionMode,
        highlights,
        onAddHighlight,
        onUpdateHighlight,
        onLoadAnnotations,
        applyPdfTint
    } = props;

    if (!url) {
        console.error('PDFEditor rendered with no URL');
        return null;
    }

    return (
        <ErrorBoundary>
            <PDFEditorContent
                url={url}
                activeColor={activeColor}
                zoom={zoom}
                isAreaSelectionMode={isAreaSelectionMode}
                highlights={highlights}
                onAddHighlight={onAddHighlight}
                onUpdateHighlight={onUpdateHighlight}
                onLoadAnnotations={onLoadAnnotations}
                applyPdfTint={applyPdfTint}
            />
        </ErrorBoundary>
    );
};
