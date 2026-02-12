export interface IHighlight {
    content: { text?: string; image?: string };
    position: {
        boundingRect: { x1: number; y1: number; x2: number; y2: number; width: number; height: number; pageNumber: number };
        rects: { x1: number; y1: number; x2: number; y2: number; width: number; height: number; pageNumber: number }[];
    };
    comment: { text: string; author: string; timestamp: number };
    id: string;
    color?: string;
}

export interface Session {
    id: string;
    title: string;
    date: Date;
    preview: string;
    color?: string;
}
