"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, ChevronLeft, ChevronRight } from "lucide-react";

type PdfViewport = { width: number; height: number };

type PdfPageProxy = {
  getViewport: (params: { scale: number }) => PdfViewport;
  render: (params: { canvas: HTMLCanvasElement; viewport: PdfViewport }) => {
    promise: Promise<void>;
    cancel: () => void;
  };
  streamTextContent: () => ReadableStream;
};

type PdfDocument = {
  numPages: number;
  getPage: (pageNumber: number) => Promise<PdfPageProxy>;
};

function PdfPage({
  pdf,
  pageNumber,
  width,
  forced,
}: {
  pdf: PdfDocument;
  pageNumber: number;
  width: number;
  forced: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  const isNear = forced || near;

  useEffect(() => {
    const node = wrapRef.current;
    if (!node || isNear) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) setNear(true);
    }, { rootMargin: "800px 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [isNear]);

  useEffect(() => {
    if (!isNear) return;
    let cancelled = false;
    let renderTask: { promise: Promise<void>; cancel: () => void } | null = null;
    let textTask: { cancel: () => void } | null = null;

    const paint = async () => {
      const page = await pdf.getPage(pageNumber);
      if (cancelled) return;
      const canvas = canvasRef.current;
      const textLayerDiv = textLayerRef.current;
      if (!canvas || !textLayerDiv) return;
      const base = page.getViewport({ scale: 1 });
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      const cssScale = width / base.width;
      const viewport = page.getViewport({ scale: cssScale * pixelRatio });
      const textViewport = page.getViewport({ scale: cssScale });
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${Math.floor(textViewport.width)}px`;
      canvas.style.height = `${Math.floor(textViewport.height)}px`;
      textLayerDiv.style.setProperty("--scale-factor", String(cssScale));
      textLayerDiv.replaceChildren();
      renderTask = page.render({ canvas, viewport });
      if (cancelled) {
        renderTask.cancel();
        return;
      }
      try {
        await renderTask.promise;
      } catch (error) {
        const name = error instanceof Error ? error.name : "";
        if (!cancelled && name !== "RenderingCancelledException") {
          console.error("Failed to render PDF page", error);
        }
      }
      if (cancelled) return;
      try {
        const pdfjs = await import("pdfjs-dist");
        const layer = new pdfjs.TextLayer({
          textContentSource: page.streamTextContent(),
          container: textLayerDiv,
          viewport: textViewport as never,
        });
        textTask = layer;
        await layer.render();
      } catch (error) {
        if (!cancelled) console.error("Failed to prepare selectable text", error);
      }
    };

    void paint();
    return () => {
      cancelled = true;
      try {
        renderTask?.cancel();
        textTask?.cancel();
      } catch {
        // The page finished rendering before cancel.
      }
    };
  }, [isNear, pdf, pageNumber, width]);

  return (
    <div
      ref={wrapRef}
      data-page={pageNumber}
      className="flex items-start justify-center scroll-mt-4"
      style={{ minHeight: Math.max(240, Math.round(width * 1.294)) }}
    >
      <div className="pdf-page-sheet shadow-md">
        <canvas ref={canvasRef} className="block h-auto max-w-full bg-white" />
        <div ref={textLayerRef} className="textLayer" />
      </div>
    </div>
  );
}

export function PdfViewer({
  data,
  loading,
  error,
  activePage,
  jumpToken,
  onJumpToPage,
  onVisiblePage,
  onPageCount,
  readerRootRef,
}: {
  data: ArrayBuffer | null;
  loading: boolean;
  error: string | null;
  activePage: number;
  jumpToken: number;
  onJumpToPage: (page: number) => void;
  onVisiblePage: (page: number) => void;
  onPageCount: (count: number) => void;
  readerRootRef: React.RefObject<HTMLDivElement | null>;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pdf, setPdf] = useState<PdfDocument | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [width, setWidth] = useState(720);
  const activePageRef = useRef(activePage);
  const onVisiblePageRef = useRef(onVisiblePage);
  const onPageCountRef = useRef(onPageCount);

  useEffect(() => {
    activePageRef.current = activePage;
    onVisiblePageRef.current = onVisiblePage;
    onPageCountRef.current = onPageCount;
  }, [activePage, onVisiblePage, onPageCount]);

  useEffect(() => {
    const node = scrollRef.current;
    if (!node) return;
    const measure = () => {
      const padding = node.clientWidth < 640 ? 16 : 48;
      setWidth(Math.max(260, node.clientWidth - padding));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [pdf, loading]);

  useEffect(() => {
    if (!data) return;
    let cancelled = false;
    let loadingTask: { destroy: () => Promise<void> } | null = null;

    const open = async () => {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const task = pdfjs.getDocument({ data: new Uint8Array(data.slice(0)) });
        loadingTask = task;
        const opened = await task.promise;
        if (cancelled) {
          await task.destroy();
          return;
        }
        const document = opened as unknown as PdfDocument;
        setParseError(null);
        setPdf(document);
        onPageCountRef.current(document.numPages);
      } catch (openError) {
        if (cancelled) return;
        const name = openError instanceof Error ? openError.name : "";
        setParseError(name === "PasswordException"
          ? "This PDF is password protected, so it cannot be shown."
          : "Could not open this PDF.");
        setPdf(null);
      }
    };

    void open();
    return () => {
      cancelled = true;
      void loadingTask?.destroy().catch(() => undefined);
    };
  }, [data]);

  useEffect(() => {
    if (!jumpToken || !pdf) return;
    const target = scrollRef.current?.querySelector(`[data-page="${activePageRef.current}"]`);
    target?.scrollIntoView({ behavior: "auto", block: "start" });
  }, [jumpToken, pdf]);

  useEffect(() => {
    const root = scrollRef.current;
    if (!root || !pdf) return;
    const nodes = Array.from(root.querySelectorAll<HTMLElement>("[data-page]"));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      const page = Number((visible.target as HTMLElement).dataset.page);
      if (page) onVisiblePageRef.current(page);
    }, { root, threshold: [0.5] });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [pdf]);

  const pageCount = pdf?.numPages ?? 0;
  const pageIndex = pageCount > 0 ? Math.min(Math.max(activePage, 1), pageCount) : 0;
  const message = error || parseError;

  return (
    <div className="flex flex-col h-full min-w-0">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-secondary/20 shrink-0">
        <button
          onClick={() => pageIndex > 1 && onJumpToPage(pageIndex - 1)}
          disabled={pageIndex <= 1}
          className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeft size={18} />
        </button>
        <p className="text-sm text-muted-foreground">
          {pageCount > 0 ? (
            <>Page <span className="text-foreground font-medium">{pageIndex}</span> / {pageCount}</>
          ) : (
            "PDF"
          )}
        </p>
        <button
          onClick={() => pageCount > 0 && pageIndex < pageCount && onJumpToPage(pageIndex + 1)}
          disabled={pageCount === 0 || pageIndex >= pageCount}
          className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors"
          aria-label="Next page"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      <div
        ref={(node) => {
          scrollRef.current = node;
          readerRootRef.current = node;
        }}
        data-reader-root
        className="flex-1 overflow-y-auto bg-secondary/30 px-2 sm:px-4 py-3 sm:py-6 selection:bg-primary/25"
      >
        {loading || (data && !pdf && !message) ? (
          <div className="mx-auto max-w-3xl space-y-4">
            {Array.from({ length: 2 }).map((_, card) => (
              <div key={card} className="bg-card border border-border shadow-sm rounded-sm aspect-[1/1.294] animate-pulse" />
            ))}
          </div>
        ) : message ? (
          <div className="flex h-full items-center justify-center text-muted-foreground text-sm text-center px-6">
            {message}
          </div>
        ) : !pdf ? (
          <div className="flex h-full items-center justify-center text-muted-foreground flex-col gap-2">
            <BookOpen size={32} className="opacity-40" />
            <p className="text-sm">The original PDF is not available for this book.</p>
          </div>
        ) : (
          <div className="mx-auto flex w-full flex-col gap-4">
            {Array.from({ length: pdf.numPages }, (_, index) => {
              const pageNumber = index + 1;
              return (
                <PdfPage
                  key={pageNumber}
                  pdf={pdf}
                  pageNumber={pageNumber}
                  width={width}
                  forced={pageNumber === activePage}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
