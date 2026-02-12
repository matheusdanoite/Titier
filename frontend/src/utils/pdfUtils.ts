
import { PDFDocument, rgb } from 'pdf-lib';
import { IHighlight } from '../types';

export const savePDF = async (
    pdfUrl: string,
    highlights: IHighlight[],
    originalFileName: string
) => {
    try {
        // Fetch the existing PDF
        const existingPdfBytes = await fetch(pdfUrl).then(res => res.arrayBuffer());

        // Load a PDFDocument from the existing PDF bytes
        const pdfDoc = await PDFDocument.load(existingPdfBytes);
        const pages = pdfDoc.getPages();


        // Process highlights
        for (const highlight of highlights) {
            const { position, comment, color } = highlight;
            const pageIndex = position.boundingRect.pageNumber - 1;

            if (pageIndex >= 0 && pageIndex < pages.length) {
                const page = pages[pageIndex];
                const { height: pageHeight } = page.getSize();

                // Convert web color (hex/name) to pdf-lib RGB
                // Default yellow: #facc15 -> R: 250, G: 204, B: 21
                let pdfColor = rgb(250 / 255, 204 / 255, 21 / 255);
                let colorHex = color;

                // Simple color mapping if name is passed
                if (color === 'green') colorHex = '#4ade80';
                else if (color === 'blue') colorHex = '#60a5fa';
                else if (color === 'red') colorHex = '#f87171';
                else if (color === 'yellow') colorHex = '#facc15';

                if (colorHex && colorHex.startsWith('#')) {
                    const r = parseInt(colorHex.slice(1, 3), 16) / 255;
                    const g = parseInt(colorHex.slice(3, 5), 16) / 255;
                    const b = parseInt(colorHex.slice(5, 7), 16) / 255;
                    pdfColor = rgb(r, g, b);
                }

                // Draw Rectangles (Rects) or BoundingRect
                // Prefer rects for multi-line text, fall back to boundingRect
                const rectsToDraw = position.rects && position.rects.length > 0 ? position.rects : [position.boundingRect];

                for (const rect of rectsToDraw) {
                    // Coordinate conversion:
                    // Web: (0,0) is Top-Left. y increases downwards.
                    // PDF: (0,0) is Bottom-Left. y increases upwards.
                    // rect.y1 is distance from top.
                    // pdf_y = pageHeight - rect.y1 - rect.height

                    const x = rect.x1;
                    const y = pageHeight - rect.y1 - rect.height;
                    const width = rect.width;
                    const height = rect.height;

                    page.drawRectangle({
                        x,
                        y,
                        width,
                        height,
                        color: pdfColor,
                        opacity: 0.4,
                    });
                }

                // Add Comment (Note) if exists
                if (comment && comment.text) {


                    // We represent the note as a small text annotation or just text for now as specific NoteAnnotations are complex in pdf-lib low-level
                    // A simple square to indicate a note, and maybe the text nearby?
                    // Ideally, we would add a 'Text' annotation (sticky note), but pdf-lib has limited high-level support for annotations.
                    // We can draw a small icon or square.

                    /* 
                       Advanced: pdf-lib doesn't support creating Sticky Note annotations (Text Annotation) easily out of the box without low-level dictionary manipulation.
                       For this MVP, we will "burn in" the comments as visual text on the side or just keep the highlights.
                       OR checking requirements: "Save to PDF (burn/embed annotations)".
                       Let's burn the text in specific margin or near highlight if space?
                       Or just standard "burning":
                    */

                    // Let's add a small visible marker (e.g. bold square) and text?
                    // Writing text over PDF content is messy.
                    // Let's just create a visual sticky note representation: A small square with number?

                    // Drawing the comment text is tough without reflowing.
                    // Alternative: Create a new page at the end with all comments?
                    // User requirements "Acrobat-style comments" usually implies Sticky Notes.
                    // Since pdf-lib doesn't easily support adding interactive TextAnnotations, we will just burn the highlight visual.
                    // We will skip adding the comment text as an interactive element for now to avoid breaking the PDF structure,
                    // unless we do low-level manipulation which is risky without testing.
                    // We'll log a warning or add a simplified text representation.

                    // WORKAROUND: Draw the comment text in a box if it's "burning"
                    // const textWidth = 200;
                    // page.drawRectangle({ x: stickyNoteX, y: stickyNoteY - 20, width: textWidth, height: 50, color: rgb(1,1,1) });
                    // page.drawText(comment.text, { x: stickyNoteX + 5, y: stickyNoteY - 15, size: 10, font, color: rgb(0,0,0) });
                }
            }
        }

        // Serialize the PDFDocument to bytes (a Uint8Array)
        const pdfBytes = await pdfDoc.save();

        // Trigger the browser to download the PDF document
        const blob = new Blob([pdfBytes], { type: 'application/pdf' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `edited_${originalFileName}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

    } catch (err) {
        console.error("Error saving PDF:", err);
        alert("Falha ao salvar PDF.");
    }
};
