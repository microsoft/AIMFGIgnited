import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Document, Page } from "react-pdf";
import { pdfjs } from "react-pdf";
import { BoundingPolygon, Coordinates } from "../api/models";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

interface PdfHighlighterProps {
    pdfPath: string;
    pageNumber: number;
    boundingPolygons: string;
}

const PdfHighlighter = ({ pdfPath, pageNumber, boundingPolygons }: PdfHighlighterProps) => {
    const canvasRef = useRef<HTMLCanvasElement | null>(null);
    const [pageSize, setPageSize] = useState<{ width: number; height: number } | null>(null);

    // Memoize parsed bounding polygons to avoid repeated JSON parsing
    const parsedPolygons = useMemo(() => {
        try {
            return JSON.parse(boundingPolygons) as BoundingPolygon[];
        } catch (error) {
            console.error("Failed to parse boundingPolygons:", error);
            return [];
        }
    }, [boundingPolygons]);

    const onPageLoadSuccess = ({ width, height }: { width: number; height: number }) => {
        setPageSize({ width, height });
    };

    const drawOverlay = useCallback(
        (coords: Coordinates[]) => {
            if (pageSize && canvasRef.current) {
                const canvas = canvasRef.current;
                const ctx = canvas.getContext("2d");

                if (ctx) {
                    ctx.strokeStyle = "blue";
                    ctx.lineWidth = 2;
                    ctx.beginPath();

                    // Adjust scaling based on page size and zoom level
                    const scaleX = canvas.width / pageSize.width;
                    const scaleY = canvas.height / pageSize.height;

                    coords.forEach((coord, index) => {
                        const x = coord.x * scaleX * 74;
                        const y = coord.y * scaleY * 72;
                        if (index === 0) {
                            ctx.moveTo(x, y);
                        } else {
                            ctx.lineTo(x, y);
                        }
                    });
                    ctx.closePath();
                    ctx.stroke();
                }
            }
        },
        [pageSize]
    );

    // eslint-disable-next-line react-hooks/exhaustive-deps
    const clearAndDraw = useCallback(() => {
        if (!canvasRef.current || !pageSize) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext("2d");

        if (ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Use requestAnimationFrame for smoother rendering
            requestAnimationFrame(() => {
                parsedPolygons.forEach(bound => {
                    drawOverlay(bound);
                });
            });
        }
    }, [canvasRef, pageSize, parsedPolygons, drawOverlay]);

    useEffect(() => {
        clearAndDraw();
    }, [clearAndDraw, pageSize, parsedPolygons]);

    useEffect(() => {
        const handleResize = () => {
            if (canvasRef.current && pageSize) {
                const container = canvasRef.current.parentElement;
                if (container) {
                    const { width, height } = container.getBoundingClientRect();
                    canvasRef.current.style.width = `${width}px`;
                    canvasRef.current.style.height = `${height}px`;

                    clearAndDraw();
                }
            }
        };

        window.addEventListener("resize", handleResize);
        return () => window.removeEventListener("resize", handleResize);
    }, [clearAndDraw, pageSize]);

    return (
        <div style={{ position: "relative" }}>
            <div style={{ position: "relative" }}>
                <Document file={pdfPath}>
                    <Page renderTextLayer={false} pageNumber={pageNumber} renderAnnotationLayer={false} onLoadSuccess={onPageLoadSuccess} />
                </Document>

                {pageSize && (
                    <canvas
                        ref={canvasRef}
                        width={pageSize.width}
                        height={pageSize.height}
                        style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            pointerEvents: "none",
                            width: "100%",
                            height: "100%"
                        }}
                    />
                )}
            </div>
        </div>
    );
};

export default PdfHighlighter;
