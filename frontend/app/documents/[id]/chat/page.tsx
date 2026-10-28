"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { chatService } from "@/services/chat";
import { documentsService } from "@/services/documents";
import { notesService } from "@/services/notes";
import { useChatStream } from "@/hooks/useChatStream";
import { useTextSelection } from "@/hooks/useTextSelection";
import type {
  MessageResponse,
  DocumentResponse,
  NoteResponse,
  DocumentPageContent,
  SourceInfo,
  ConversationResponse,
} from "@/types/api";
import {
  Send, ArrowLeft, BookOpen, X, ChevronRight, ChevronLeft,
  ChevronDown, NotebookPen, Sparkles, MessageSquare, Check, Plus,
  Trash2, Edit3, Hash, GripVertical, BookMarked, History, Loader2,
  Layers
} from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PdfViewer } from "@/components/reader/PdfViewer";


// ── Types ─────────────────────────────────────────────────────────────────────
type Panel = "toc" | "notes";

// ── QuoteChip ──────────────────────────────────────────────────────────────────
function QuoteChip({ text, page, onRemove }: { text: string; page?: number | null; onRemove: () => void }) {
  return (
    <div className="flex items-start gap-2 bg-primary/10 border border-primary/25 rounded-lg px-3 py-2 text-sm mb-2">
      <span className="text-primary font-semibold shrink-0">"</span>
      <span className="text-foreground/80 line-clamp-2 flex-1">{text.slice(0, 120)}{text.length > 120 ? '…' : ''}</span>
      {page && <span className="text-xs text-muted-foreground shrink-0 self-end">p.{page}</span>}
      <button onClick={onRemove} className="text-muted-foreground hover:text-destructive shrink-0 mt-0.5 transition-colors">
        <X size={14} />
      </button>
    </div>
  );
}

// ── Accordion ─────────────────────────────────────────────────────────────────
function Accordion({
  label,
  badge,
  children,
  defaultOpen = false,
  className = "",
  headerClassName = "",
}: {
  label: string;
  badge?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  headerClassName?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`border border-border/50 rounded-xl overflow-hidden transition-all ${className}`}>
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center justify-between px-4 py-2.5 bg-secondary/30 hover:bg-secondary/60 transition-colors text-sm font-medium ${headerClassName}`}
      >
        <span className="flex items-center gap-2">
          {label}
          {badge && <span className="text-xs text-muted-foreground font-normal">· {badge}</span>}
        </span>
        <ChevronDown size={15} className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-4 py-3.5 text-sm leading-relaxed text-foreground/85">{children}</div>}
    </div>
  );
}

// ── SourceBadge ────────────────────────────────────────────────────────────────
function SourceBadge({ sources, onJumpToPage }: { sources?: SourceInfo[]; onJumpToPage?: (page: number) => void }) {
  if (!sources || sources.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {sources.slice(0, 3).map((src, i) => {
        const parts: string[] = [];
        if (src.page) parts.push(`Page ${src.page}`);
        if (src.chapter) parts.push(src.chapter);
        if (src.section) parts.push(src.section);
        if (parts.length === 0) return null;
        return (
          <button
            key={i}
            onClick={() => src.page && onJumpToPage?.(src.page)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-primary/8 border border-primary/20 text-xs text-primary hover:bg-primary/15 hover:border-primary/35 transition-all cursor-pointer"
            title={`Jump to ${parts.join(' › ')}`}
          >
            <BookMarked size={11} className="shrink-0" />
            <span className="truncate max-w-[180px]">{parts.join(' › ')}</span>
          </button>
        );
      })}
    </div>
  );
}

// Helper to extract or derive sources from message
function getSourcesForMessage(msg: MessageResponse): SourceInfo[] {
  const fromPassages: SourceInfo[] = (msg.passages || [])
    .map(p => ({
      page: p.source.page,
      chapter: p.source.chapter,
      section: p.source.section,
    }))
    .filter(s => s.page || s.chapter || s.section);

  if (fromPassages.length > 0) return fromPassages;

  // Fallback: extract from content text (e.g. "📖 **Source:** Page 12, Chapter 3")
  const extracted: SourceInfo[] = [];
  const sourceMatch = msg.content.match(/(?:📖\s*)?\*{0,2}Source:?\*{0,2}\s*([^\n\r]+)/i);
  if (sourceMatch) {
    const text = sourceMatch[1];
    const pageMatch = text.match(/page\s*(\d+)/i);
    const chapterMatch = text.match(/chapter\s*([^,\.]+)/i);
    const sectionMatch = text.match(/section\s*([^,\.]+)/i);
    if (pageMatch || chapterMatch || sectionMatch) {
      extracted.push({
        page: pageMatch ? parseInt(pageMatch[1], 10) : undefined,
        chapter: chapterMatch ? chapterMatch[1].trim() : undefined,
        section: sectionMatch ? sectionMatch[1].trim() : undefined,
      });
    }
  }

  // Also check for "Page X" anywhere in Proof accordion or content
  if (extracted.length === 0) {
    const genericPage = msg.content.match(/\b(?:Page|p\.)\s*(\d+)\b/i);
    if (genericPage) {
      extracted.push({ page: parseInt(genericPage[1], 10) });
    }
  }

  return extracted;
}

// ── AnswerCard ─────────────────────────────────────────────────────────────────
function AnswerCard({
  content, isStreaming, sources, onSaveToNotes, onInDetail, onDiscuss, onJumpToPage
}: {
  content: string;
  isStreaming: boolean;
  sources?: SourceInfo[];
  onSaveToNotes: () => void;
  onInDetail: () => void;
  onDiscuss: () => void;
  onJumpToPage?: (page: number) => void;
}) {
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = () => {
    onSaveToNotes();
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  // Parse <details> blocks from content for Proof/Simple/Example
  const parseDetails = (text: string) => {
    const answer = text.replace(/<details[\s\S]*?<\/details>/gi, '').replace(/\*\*Answer\*\*/g, '').trim();
    const proofMatch = text.match(/<details[^>]*>\s*<summary[^>]*>(?:📖\s*)?Proof<\/summary>([\s\S]*?)<\/details>/i);
    const simpleMatch = text.match(/<details[^>]*>\s*<summary[^>]*>(?:💡\s*)?Simple Explanation<\/summary>([\s\S]*?)<\/details>/i);
    const exampleMatch = text.match(/<details[^>]*>\s*<summary[^>]*>(?:🎯\s*)?Example<\/summary>([\s\S]*?)<\/details>/i);
    return {
      answer,
      proof: proofMatch?.[1]?.trim(),
      simple: simpleMatch?.[1]?.trim(),
      example: exampleMatch?.[1]?.trim(),
    };
  };

  const parsed = parseDetails(content);

  // Extract page number from proof text or sources if available
  const proofPageMatch = parsed.proof?.match(/page\s*(\d+)/i);
  const proofPageNumber = proofPageMatch
    ? parseInt(proofPageMatch[1], 10)
    : (sources?.find(s => s.page)?.page ?? null);

  // Clean proof text to avoid nested quotes or ugly formatting
  const cleanProofText = parsed.proof
    ? parsed.proof.replace(/^["'“”]+|["'“”]+$/g, '').trim()
    : "";

  return (
    <div className="bg-card border border-border shadow-sm rounded-2xl rounded-tl-sm p-5 space-y-4">
      {/* Main Answer with GFM Markdown Tables */}
      <div className="prose prose-sm prose-stone dark:prose-invert max-w-none text-[15px] leading-relaxed">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: ({ node, ...props }) => (
              <div className="my-3 overflow-x-auto rounded-xl border border-border shadow-xs bg-background/50">
                <table className="w-full text-left text-xs border-collapse" {...props} />
              </div>
            ),
            thead: ({ node, ...props }) => (
              <thead className="bg-secondary/70 border-b border-border text-foreground font-semibold" {...props} />
            ),
            th: ({ node, ...props }) => (
              <th className="px-3 py-2.5 text-xs font-semibold text-foreground tracking-wide whitespace-nowrap" {...props} />
            ),
            td: ({ node, ...props }) => (
              <td className="px-3 py-2.5 border-b border-border/40 text-foreground/85 align-top text-xs leading-relaxed" {...props} />
            ),
            tr: ({ node, ...props }) => (
              <tr className="even:bg-secondary/20 hover:bg-secondary/40 transition-colors" {...props} />
            ),
          }}
        >
          {parsed.answer || content}
        </ReactMarkdown>
        {isStreaming && <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-middle" />}
      </div>

      {/* Source citations — proof of accuracy */}
      {!isStreaming && <SourceBadge sources={sources} onJumpToPage={onJumpToPage} />}

      {/* Dropdowns only when streaming is done */}
      {!isStreaming && parsed.proof && (
        <div className="space-y-2 pt-1">
          {/* Normal upright Proof Dropdown (strictly max 3 lines) */}
          <Accordion
            label="📖 Proof"
            badge={proofPageNumber ? `Page ${proofPageNumber}` : undefined}
          >
            <div className="space-y-2">
              <p className="text-xs font-medium text-foreground/85">
                {proofPageNumber
                  ? `Page ${proofPageNumber} ke is part ke base par ye answer diya gaya hai:`
                  : "Document ke is part ke base par ye answer diya gaya hai:"}
              </p>

              <div className="border-l-2 border-primary/40 pl-3 py-0.5">
                <p className="proof-quote not-italic font-normal text-[13.5px] leading-relaxed text-foreground/90 select-text line-clamp-3">
                  "{cleanProofText}"
                </p>
              </div>

              {proofPageNumber && (
                <button
                  type="button"
                  onClick={() => onJumpToPage?.(proofPageNumber)}
                  className="mt-1.5 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary/10 hover:bg-primary/20 text-xs font-medium text-primary transition-all cursor-pointer shadow-2xs"
                >
                  <BookMarked size={12} />
                  Jump to Page {proofPageNumber} in reader
                </button>
              )}
            </div>
          </Accordion>

          {parsed.simple && (
            <Accordion label="💡 Simple Explanation">
              <div className="prose prose-sm prose-stone dark:prose-invert max-w-none text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{parsed.simple}</ReactMarkdown>
              </div>
            </Accordion>
          )}

          {parsed.example && (
            <Accordion label="🎯 Example">
              <div className="prose prose-sm prose-stone dark:prose-invert max-w-none text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{parsed.example}</ReactMarkdown>
              </div>
            </Accordion>
          )}
        </div>
      )}

      {/* Footer actions */}
      {!isStreaming && (
        <div className="flex items-center gap-3 pt-2 border-t border-border/50 flex-wrap">
          <button
            onClick={handleSave}
            className={`flex items-center gap-1.5 text-xs transition-all cursor-pointer ${isSaved
                ? "text-emerald-600 dark:text-emerald-400 font-semibold"
                : "text-muted-foreground hover:text-primary"
              }`}
            title="Save this answer to your document notes"
          >
            {isSaved ? <Check size={13} className="text-emerald-500 animate-in zoom-in-50 duration-200" /> : <NotebookPen size={13} />}
            {isSaved ? "Saved to notes!" : "Save to notes"}
          </button>
          <button
            onClick={onInDetail}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors cursor-pointer"
          >
            <Sparkles size={13} /> In detail
          </button>
          <button
            onClick={onDiscuss}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors cursor-pointer"
          >
            <MessageSquare size={13} /> Discuss this
          </button>
        </div>
      )}
    </div>
  );
}

function sentenceCase(value: string): string {
  const text = value.trim().toLowerCase();
  if (!text) return text;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function formatReadableParagraphs(raw: string): string[] {
  const text = (raw || "")
    .replace(/\r\n/g, "\n")
    .replace(/(\w)-\n(\w)/g, "$1$2")
    .replace(/\u00ad/g, "");
  const paragraphs: string[] = [];
  let buffer = "";

  const flush = () => {
    const cleaned = buffer.replace(/[ \t]{2,}/g, " ").trim();
    if (cleaned) paragraphs.push(cleaned);
    buffer = "";
  };

  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      flush();
      continue;
    }
    buffer = buffer ? `${buffer} ${trimmed}` : trimmed;
  }
  flush();
  return paragraphs;
}

// ── PageGrid ──────────────────────────────────────────────────────────────────
function PageGrid({
  title,
  pages,
  currentPage,
  onJumpToPage,
}: {
  title: string;
  pages: DocumentPageContent[];
  currentPage: number;
  onJumpToPage: (page: number) => void;
}) {
  const [hover, setHover] = useState<{ page: DocumentPageContent; top: number; left: number } | null>(null);

  return (
    <div className="p-3 font-sans">
      <p className="text-[13px] font-medium text-foreground/80 mb-0.5 px-0.5 truncate" title={sentenceCase(title)}>
        {sentenceCase(title)}
      </p>
      <p className="text-xs text-muted-foreground mb-2.5 px-0.5">
        {pages.length === 1 ? "1 page" : `${pages.length} pages`}
      </p>
      {pages.length === 0 ? (
        <p className="text-sm text-muted-foreground italic px-0.5">No pages stored for this book yet.</p>
      ) : (
        <div className="grid grid-cols-5 gap-1.5">
          {pages.map((page) => {
            const active = page.page === currentPage;
            return (
              <button
                key={page.page}
                type="button"
                onClick={() => onJumpToPage(page.page)}
                onMouseEnter={(event) => {
                  if (typeof window !== "undefined" && window.innerWidth >= 768) {
                    const rect = event.currentTarget.getBoundingClientRect();
                    setHover({ page, top: rect.top, left: rect.right + 10 });
                  }
                }}
                onMouseLeave={() => setHover(null)}
                className={`flex h-9 sm:h-7 items-center justify-center rounded-lg sm:rounded-md border text-xs font-medium tabular-nums leading-none transition-colors active:scale-95 ${active
                    ? "bg-primary/10 border-primary text-primary font-bold"
                    : "bg-background border-border text-foreground/80 hover:border-primary/40 hover:bg-primary/5"
                  }`}
                aria-label={`Open page ${page.page}`}
                aria-current={active ? "page" : undefined}
              >
                {page.page}
              </button>
            );
          })}
        </div>
      )}
      {hover && (
        <div
          className="fixed z-50 w-64 rounded-lg border border-border bg-card p-2.5 shadow-lg pointer-events-none font-sans"
          style={{
            top: Math.max(12, Math.min(hover.top, window.innerHeight - 148)),
            left: Math.min(hover.left, window.innerWidth - 272),
          }}
        >
          <p className="text-xs font-medium text-primary line-clamp-2">
            {sentenceCase(hover.page.heading || `Page ${hover.page.page}`)}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-foreground/80 line-clamp-4">
            {hover.page.preview ? sentenceCase(hover.page.preview) : "Open this page in the book."}
          </p>
        </div>
      )}
    </div>
  );
}

// ── BookReader ────────────────────────────────────────────────────────────────
function BookReader({
  pages,
  loading,
  error,
  activePage,
  jumpToken,
  onJumpToPage,
  onVisiblePage,
  readerRootRef,
}: {
  pages: DocumentPageContent[];
  loading: boolean;
  error: string | null;
  activePage: number;
  jumpToken: number;
  onJumpToPage: (page: number) => void;
  onVisiblePage: (page: number) => void;
  readerRootRef: React.RefObject<HTMLDivElement | null>;
}) {
  const activePageRef = useRef(activePage);
  activePageRef.current = activePage;
  const onVisiblePageRef = useRef(onVisiblePage);
  onVisiblePageRef.current = onVisiblePage;

  useEffect(() => {
    if (!jumpToken) return;
    const target = readerRootRef.current?.querySelector(`[data-page="${activePageRef.current}"]`);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [jumpToken, pages.length, readerRootRef]);

  useEffect(() => {
    const root = readerRootRef.current;
    if (!root || pages.length === 0) return;
    const nodes = Array.from(root.querySelectorAll<HTMLElement>("[data-page]"));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
      if (!visible) return;
      const page = Number((visible.target as HTMLElement).dataset.page);
      if (page) onVisiblePageRef.current(page);
    }, { root, threshold: [0.35, 0.6] });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [pages, readerRootRef]);

  const pageIndex = pages.findIndex((page) => page.page === activePage);

  return (
    <div className="flex flex-col h-full min-w-0">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-secondary/20 shrink-0">
        <button
          onClick={() => pageIndex > 0 && onJumpToPage(pages[pageIndex - 1].page)}
          disabled={pageIndex <= 0}
          className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeft size={18} />
        </button>
        <p className="text-sm text-muted-foreground">
          {pages.length > 0 ? (
            <>Page <span className="text-foreground font-medium">{activePage}</span> / {pages.length}</>
          ) : (
            "Reading"
          )}
        </p>
        <button
          onClick={() => pageIndex >= 0 && pageIndex < pages.length - 1 && onJumpToPage(pages[pageIndex + 1].page)}
          disabled={pageIndex < 0 || pageIndex >= pages.length - 1}
          className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors"
          aria-label="Next page"
        >
          <ChevronRight size={18} />
        </button>
      </div>

      <div
        ref={readerRootRef}
        data-reader-root
        className="flex-1 overflow-y-auto bg-secondary/30 px-2 sm:px-4 py-4 sm:py-8 md:px-8 selection:bg-primary/25"
      >
        {loading ? (
          <div className="mx-auto max-w-3xl space-y-4">
            {Array.from({ length: 3 }).map((_, card) => (
              <div key={card} className="bg-card border border-border rounded-xl p-8 space-y-3 animate-pulse">
                {Array.from({ length: 8 }).map((_, line) => (
                  <div key={line} className={`h-4 bg-muted rounded ${line % 5 === 4 ? "w-3/4" : "w-full"}`} />
                ))}
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">{error}</div>
        ) : pages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground flex-col gap-2">
            <BookOpen size={32} className="opacity-40" />
            <p className="text-sm">No pages were stored for this document.</p>
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 sm:space-y-8">
            {pages.map((page) => {
              const paragraphs = formatReadableParagraphs(page.content);
              const active = page.page === activePage;
              return (
                <article
                  key={page.page}
                  data-page={page.page}
                  className={`bg-card border rounded-xl shadow-sm px-4 py-6 sm:px-6 sm:py-8 md:px-10 ${active ? "border-primary/50 ring-2 ring-primary/15" : "border-border"
                    }`}
                >
                  <header className="flex items-start justify-between gap-4 mb-4 sm:mb-6 pb-3 border-b border-border">
                    <p className="text-sm font-medium text-primary line-clamp-2">
                      {page.heading || `Page ${page.page}`}
                    </p>
                    <span className="text-xs text-muted-foreground shrink-0 pt-0.5">Page {page.page}</span>
                  </header>
                  {paragraphs.length > 0 ? (
                    <div className="font-['Lora'] text-[15px] sm:text-[17px] leading-[1.8] sm:leading-[1.9] text-foreground/90 space-y-4">
                      {paragraphs.map((paragraph, index) => (
                        <p key={index}>{paragraph}</p>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground italic">This page has no extractable text.</p>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── NotepadPanel ──────────────────────────────────────────────────────────────
function NotepadPanel({
  documentId, notes, onAddNote, onDeleteNote, onEditNote, onJumpToPage
}: {
  documentId: string;
  notes: NoteResponse[];
  onAddNote: (content: string, page?: number) => void;
  onDeleteNote: (id: string) => void;
  onEditNote: (id: string, content: string) => void;
  onJumpToPage: (page: number) => void;
}) {
  const [newContent, setNewContent] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  const handleAdd = () => {
    if (!newContent.trim()) return;
    onAddNote(newContent.trim());
    setNewContent("");
  };

  const saveEdit = (id: string) => {
    onEditNote(id, editContent);
    setEditingId(null);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Add note */}
      <div className="p-3 border-b border-border shrink-0">
        <textarea
          value={newContent}
          onChange={e => setNewContent(e.target.value)}
          placeholder="Add a note..."
          rows={2}
          className="w-full text-sm bg-background border border-border rounded-lg px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <button
          onClick={handleAdd}
          disabled={!newContent.trim()}
          className="mt-1.5 w-full flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 rounded-md bg-primary/10 hover:bg-primary/20 text-primary disabled:opacity-40 transition-colors"
        >
          <Plus size={13} /> Add Note
        </button>
      </div>

      {/* Notes list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {notes.length === 0 ? (
          <p className="text-sm text-muted-foreground italic text-center pt-6">No notes yet. Select text and save, or type above.</p>
        ) : (
          notes.map(n => (
            <div key={n.id} className="bg-secondary/30 rounded-lg p-3 border border-border/40 group">
              {editingId === n.id ? (
                <div className="space-y-1.5">
                  <textarea
                    value={editContent}
                    onChange={e => setEditContent(e.target.value)}
                    rows={3}
                    className="w-full text-sm bg-background border border-border rounded px-2 py-1 resize-none focus:outline-none focus:ring-1 focus:ring-primary"
                    autoFocus
                  />
                  <div className="flex gap-1.5">
                    <button onClick={() => saveEdit(n.id)} className="flex items-center gap-1 text-xs text-primary hover:text-primary/80"><Check size={12} /> Save</button>
                    <button onClick={() => setEditingId(null)} className="text-xs text-muted-foreground hover:text-foreground">Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-sm text-foreground/80 leading-relaxed">{n.content}</p>
                  <div className="flex items-center justify-between mt-2">
                    {n.page && (
                      <button
                        onClick={() => onJumpToPage(n.page!)}
                        className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
                      >
                        <Hash size={11} /> p.{n.page}
                      </button>
                    )}
                    <div className="flex gap-2 ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
                      <button onClick={() => { setEditingId(n.id); setEditContent(n.content); }} className="text-muted-foreground hover:text-primary transition-colors">
                        <Edit3 size={13} />
                      </button>
                      <button onClick={() => onDeleteNote(n.id)} className="text-muted-foreground hover:text-destructive transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── Format Date for Chat History ───────────────────────────────────────────────
function formatChatDate(dateStr?: string) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 1) {
      const mins = Math.max(1, Math.round(diffMs / (1000 * 60)));
      return `${mins}m ago`;
    }
    if (diffHours < 24 && now.getDate() === d.getDate()) {
      return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }
    if (diffHours < 48) {
      return `Yesterday, ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    }
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

// ── Movable Chat Button ────────────────────────────────────────────────────────
function MovableChatButton({
  onClick,
  conversationCount,
}: {
  onClick: () => void;
  conversationCount?: number;
}) {
  const [position, setPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{
    startX: number;
    startY: number;
    initialX: number;
    initialY: number;
    hasMoved: boolean;
  } | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem("footnote_chat_icon_pos");
    const width = typeof window !== "undefined" ? window.innerWidth : 1200;
    const height = typeof window !== "undefined" ? window.innerHeight : 800;
    const defaultX = Math.max(16, width - 80);
    const defaultY = Math.max(16, height - 80);

    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (typeof parsed.x === "number" && typeof parsed.y === "number") {
          const clampedX = Math.max(16, Math.min(width - 68, parsed.x));
          const clampedY = Math.max(16, Math.min(height - 68, parsed.y));
          setPosition({ x: clampedX, y: clampedY });
          return;
        }
      } catch {
        // fallback
      }
    }
    setPosition({ x: defaultX, y: defaultY });
  }, []);

  useEffect(() => {
    const handleResize = () => {
      setPosition(prev => {
        if (!prev) return null;
        const clampedX = Math.max(16, Math.min(window.innerWidth - 68, prev.x));
        const clampedY = Math.max(16, Math.min(window.innerHeight - 68, prev.y));
        return { x: clampedX, y: clampedY };
      });
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handlePointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    e.preventDefault();
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // ignore
    }

    const currentX = position?.x ?? (window.innerWidth - 80);
    const currentY = position?.y ?? (window.innerHeight - 80);

    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      initialX: currentX,
      initialY: currentY,
      hasMoved: false,
    };
    setIsDragging(true);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;

    if (!dragRef.current.hasMoved && Math.hypot(dx, dy) > 4) {
      dragRef.current.hasMoved = true;
    }

    if (dragRef.current.hasMoved) {
      const nextX = Math.max(16, Math.min(window.innerWidth - 68, dragRef.current.initialX + dx));
      const nextY = Math.max(16, Math.min(window.innerHeight - 68, dragRef.current.initialY + dy));
      setPosition({ x: nextX, y: nextY });
    }
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (!dragRef.current) return;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // ignore
    }

    const wasDrag = dragRef.current.hasMoved;
    const finalX = position?.x ?? dragRef.current.initialX;
    const finalY = position?.y ?? dragRef.current.initialY;
    dragRef.current = null;
    setIsDragging(false);

    if (wasDrag) {
      localStorage.setItem("footnote_chat_icon_pos", JSON.stringify({ x: finalX, y: finalY }));
    } else {
      onClick();
    }
  };

  if (!position) return null;

  return (
    <div
      style={{
        position: "fixed",
        left: `${position.x}px`,
        top: `${position.y}px`,
        touchAction: "none",
        zIndex: 50,
      }}
    >
      <button
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        className={`relative group flex items-center justify-center w-13 h-13 rounded-full bg-primary text-primary-foreground shadow-lg select-none transition-shadow ${isDragging
            ? "cursor-grabbing scale-105 shadow-2xl ring-4 ring-primary/30"
            : "cursor-grab hover:scale-105 hover:shadow-xl active:scale-95"
          }`}
        title="Ask FootNote (Drag anywhere • Tap to open)"
        aria-label="Open chat"
      >
        <MessageSquare size={20} className="shrink-0 transition-transform group-hover:scale-110" />

        {/* Small grip dot handle */}
        <span className="absolute bottom-1.5 flex gap-0.5 opacity-60 group-hover:opacity-100 transition-opacity">
          <span className="w-1 h-1 rounded-full bg-primary-foreground/80" />
          <span className="w-1 h-1 rounded-full bg-primary-foreground/80" />
          <span className="w-1 h-1 rounded-full bg-primary-foreground/80" />
        </span>

        {/* Conversation badge */}
        {conversationCount !== undefined && conversationCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-background text-foreground text-[10px] font-bold border-2 border-primary flex items-center justify-center shadow-md">
            {conversationCount > 9 ? "9+" : conversationCount}
          </span>
        )}
      </button>
    </div>
  );
}

// ── Main Workspace Page ────────────────────────────────────────────────────────
export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  // State
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [bookPages, setBookPages] = useState<DocumentPageContent[]>([]);
  const [pagesLoading, setPagesLoading] = useState(true);
  const [pagesError, setPagesError] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [notes, setNotes] = useState<NoteResponse[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [loadingHistoryId, setLoadingHistoryId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);

  const [jumpToken, setJumpToken] = useState(0);
  const [pdfData, setPdfData] = useState<ArrayBuffer | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pdfPageCount, setPdfPageCount] = useState(0);

  // UI state — pinned stays open; hover peeks it open from the logo or icons
  const [sidebarPinned, setSidebarPinned] = useState(true);
  const [sidebarHover, setSidebarHover] = useState(false);
  const sidebarOpen = sidebarPinned || sidebarHover;
  const [chatOpen, setChatOpen] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>("toc");
  const [isMobile, setIsMobile] = useState(false);
  const [mobileDrawer, setMobileDrawer] = useState<"toc" | "notes" | null>(null);
  const [input, setInput] = useState("");
  const [inputPlaceholder, setInputPlaceholder] = useState("Ask what you're not understanding…");
  const [quoteChip, setQuoteChip] = useState<{ text: string; page?: number | null } | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [savedToast, setSavedToast] = useState<{ visible: boolean; page?: number; preview?: string }>({ visible: false });
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Mobile screen detection
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) {
        setSidebarPinned(false);
      }
    };
    handleResize();
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setChatOpen(false);
    }
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Resizable chat pane state
  const [chatWidth, setChatWidth] = useState(352); // ~22rem default
  const isDraggingRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragStartWidthRef = useRef(0);

  const CHAT_MIN_WIDTH = 280;
  const CHAT_MAX_WIDTH = 600;

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const readerRootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const sidebarCloseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Hooks
  const { state: stream, send: streamSend } = useChatStream();
  const { selection, clearSelection } = useTextSelection(readerRootRef);

  // ── Resize drag handlers ──────────────────────────────────────────────
  const handleResizeMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDraggingRef.current = true;
    dragStartXRef.current = e.clientX;
    dragStartWidthRef.current = chatWidth;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMouseMove = (ev: MouseEvent) => {
      if (!isDraggingRef.current) return;
      const delta = dragStartXRef.current - ev.clientX; // dragging left = bigger
      const newWidth = Math.max(CHAT_MIN_WIDTH, Math.min(CHAT_MAX_WIDTH, dragStartWidthRef.current + delta));
      setChatWidth(newWidth);
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [chatWidth]);

  // Show selection toolbar
  useEffect(() => {
    if (selection && selection.text.length >= 3) {
      setQuoteChip({ text: selection.text, page: selection.page });
      setInputPlaceholder("Ask what you're not understanding from these lines or paragraph…");
      setChatOpen(true);
      inputRef.current?.focus();
    }
  }, [selection]);

  // Load initial data in parallel
  useEffect(() => {
    const load = async () => {
      try {
        const [docData, convData, notesData] = await Promise.all([
          documentsService.get(documentId),
          chatService.listConversations(documentId),
          notesService.list(documentId),
        ]);

        if (docData.status !== "ready") {
          router.push(`/documents/${documentId}/processing`);
          return;
        }
        setDoc(docData);
        setNotes(notesData.notes);

        try {
          const pagesData = await documentsService.listPages(documentId);
          setBookPages(pagesData.pages);
          const saved = localStorage.getItem(`footnote_page_${documentId}`);
          const savedPage = saved ? parseInt(saved, 10) : 1;
          const initial = pagesData.pages.some((page) => page.page === savedPage)
            ? savedPage
            : pagesData.pages[0]?.page ?? 1;
          setCurrentPage(initial);
          if (pagesData.pages.length > 0) setJumpToken(1);
        } catch (pageErr) {
          console.error("Failed to load pages", pageErr);
          setPagesError("Could not load the pages of this book.");
        } finally {
          setPagesLoading(false);
        }

        // User requirement: Keep chat fresh and clean upon opening (no old messages preloaded)
        setConversations(convData.conversations);
      } catch (err) {
        console.error("Failed to load workspace", err);
      }
    };
    load();
  }, [documentId, router]);

  useEffect(() => {
    if (!doc || doc.id !== documentId || doc.file.format !== "pdf") {
      setPdfData(null);
      setPdfPageCount(0);
      setPdfLoading(false);
      return;
    }
    let cancelled = false;
    setPdfLoading(true);
    setPdfError(null);
    documentsService.getFile(documentId)
      .then((blob) => blob.arrayBuffer())
      .then((buffer) => {
        if (!cancelled) setPdfData(buffer);
      })
      .catch(() => {
        if (!cancelled) setPdfError("Could not load the original PDF.");
      })
      .finally(() => {
        if (!cancelled) setPdfLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [doc, documentId]);

  // Sync conversation ID from stream if freshly created
  useEffect(() => {
    if (stream.conversationId && !conversationId) {
      setConversationId(stream.conversationId);
    }
  }, [stream.conversationId, conversationId]);

  // Add streamed assistant message to history when done
  useEffect(() => {
    if (stream.status === "done" && stream.answer) {
      const activeConvId = conversationId || stream.conversationId || "";
      const assistantMsg: MessageResponse = {
        id: `stream_${Date.now()}`,
        conversation_id: activeConvId,
        role: "assistant",
        content: stream.answer,
        intent: stream.intent ?? undefined,
        passages: stream.sources?.map((s, idx) => ({
          chunk_id: `src_${idx}`,
          content: "",
          source: {
            document_id: documentId,
            document_title: doc?.title || "",
            page: s.page,
            chapter: s.chapter,
            section: s.section,
          },
        })),
        created_at: new Date().toISOString(),
      };
      setMessages(prev => {
        // Avoid duplicate if already added
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.content === stream.answer) return prev;
        return [...prev, assistantMsg];
      });

      if (stream.conversationId && !conversationId) {
        setConversationId(stream.conversationId);
      }

      // Refresh conversation list in background to include this new chat
      chatService.listConversations(documentId)
        .then(res => setConversations(res.conversations))
        .catch(() => { });
    }
  }, [stream.status, stream.answer, stream.intent, stream.sources, stream.conversationId, conversationId, documentId, doc?.title]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, stream.answer]);

  // Conversation history actions
  const handleNewChat = () => {
    setMessages([]);
    setConversationId(undefined);
    setShowHistory(false);
    setInput("");
    setQuoteChip(null);
    clearSelection();
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleSelectConversation = async (convId: string) => {
    try {
      setLoadingHistoryId(convId);
      const data = await chatService.getConversation(convId);
      setMessages(data.messages);
      setConversationId(convId);
      setShowHistory(false);
    } catch (err) {
      console.error("Failed to load conversation", err);
    } finally {
      setLoadingHistoryId(null);
    }
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await chatService.deleteConversation(convId);
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (conversationId === convId) {
        handleNewChat();
      }
    } catch (err) {
      console.error("Failed to delete conversation", err);
    }
  };


  const handleSend = async (customMessage?: string) => {
    const msg = customMessage ?? input.trim();
    if (!msg || stream.status === "streaming") return;

    setSendError(null);
    setInput("");
    setInputPlaceholder("Ask what you're not understanding…");

    const userMsg: MessageResponse = {
      id: `usr_${Date.now()}`,
      conversation_id: conversationId || "",
      role: "user",
      content: quoteChip ? `"${quoteChip.text.slice(0, 120)}…"\n\n${msg}` : msg,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setQuoteChip(null);
    clearSelection();

    try {
      await streamSend({
        document_id: documentId,
        message: msg,
        conversation_id: conversationId,
        selected_text: quoteChip?.text,
        selected_page: quoteChip?.page ?? undefined,
      });
    } catch {
      setSendError("Failed to get a response. Tap to retry.");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Notes CRUD
  const handleAddNote = async (content: string, page?: number) => {
    const note = await notesService.create({ document_id: documentId, content, page });
    setNotes(prev => [note, ...prev]);
  };

  const handleSaveAnswerToNotes = async (content: string, page?: number) => {
    await handleAddNote(content, page);
    const cleanSnippet = content
      .replace(/<details[\s\S]*?<\/details>/gi, "")
      .replace(/\*\*Answer\*\*/g, "")
      .replace(/[#*`_]/g, "")
      .trim()
      .slice(0, 95);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setSavedToast({ visible: true, page, preview: cleanSnippet });
    toastTimerRef.current = setTimeout(() => {
      setSavedToast(prev => ({ ...prev, visible: false }));
    }, 4500);
  };
  const handleDeleteNote = async (id: string) => {
    await notesService.delete(id);
    setNotes(prev => prev.filter(n => n.id !== id));
  };
  const handleEditNote = async (id: string, content: string) => {
    const updated = await notesService.update(id, content);
    setNotes(prev => prev.map(n => n.id === id ? updated : n));
  };

  const revealSidebar = (panel?: Panel) => {
    if (sidebarCloseTimer.current) clearTimeout(sidebarCloseTimer.current);
    if (panel && !sidebarOpen) setActivePanel(panel);
    if (!sidebarPinned) setSidebarHover(true);
  };

  const scheduleSidebarClose = () => {
    if (sidebarPinned) return;
    if (sidebarCloseTimer.current) clearTimeout(sidebarCloseTimer.current);
    sidebarCloseTimer.current = setTimeout(() => setSidebarHover(false), 180);
  };

  const toggleSidebar = () => {
    if (sidebarPinned) {
      setSidebarPinned(false);
      setSidebarHover(false);
    } else {
      setSidebarPinned(true);
    }
  };

  const handleJumpToPage = (page: number) => {
    setCurrentPage(page);
    setJumpToken((token) => token + 1);
    try {
      localStorage.setItem(`footnote_page_${documentId}`, String(page));
    } catch {
      // ignore
    }
    if (typeof window !== "undefined" && window.innerWidth < 768) {
      setMobileDrawer(null);
      setChatOpen(false);
    }
  };

  if (!doc) return <div className="h-screen bg-background animate-pulse" />;

  const isPdf = doc.file.format === "pdf";
  const previewByPage = new Map(bookPages.map((page) => [page.page, page]));
  const sidebarPages: DocumentPageContent[] = isPdf && pdfPageCount > 0
    ? Array.from({ length: pdfPageCount }, (_, index) => {
      const page = index + 1;
      return previewByPage.get(page) ?? { page, content: "", heading: "", preview: "" };
    })
    : bookPages;
  const isStreaming = stream.status === "streaming";

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans relative">
      {/* ── Mobile Slide-Over Drawer (TOC & Notes) ──────────────── */}
      {mobileDrawer && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            onClick={() => setMobileDrawer(null)}
            className="fixed inset-0 bg-black/60 backdrop-blur-xs animate-in fade-in duration-200"
          />
          {/* Drawer Panel */}
          <div className="relative w-[85%] max-w-sm bg-card h-full z-10 shadow-2xl flex flex-col border-r border-border animate-in slide-in-from-left duration-200">
            {/* Drawer Header */}
            <div className="flex items-center justify-between px-4 h-14 border-b border-border shrink-0">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  {mobileDrawer === "toc" ? <BookOpen size={16} /> : <NotebookPen size={16} />}
                </span>
                <span className="font-semibold text-sm">
                  {mobileDrawer === "toc" ? "Table of Contents" : "Document Notes"}
                </span>
              </div>
              <button
                onClick={() => setMobileDrawer(null)}
                className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                aria-label="Close drawer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Tab Switcher inside Drawer */}
            <div className="flex border-b border-border bg-secondary/30 p-1.5 gap-1 shrink-0">
              <button
                onClick={() => setMobileDrawer("toc")}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${mobileDrawer === "toc"
                    ? "bg-card text-foreground shadow-xs font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                  }`}
              >
                <BookOpen size={13} /> Contents
              </button>
              <button
                onClick={() => setMobileDrawer("notes")}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${mobileDrawer === "notes"
                    ? "bg-card text-foreground shadow-xs font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                  }`}
              >
                <NotebookPen size={13} /> Notes ({notes.length})
              </button>
            </div>

            {/* Drawer Content */}
            <div className="flex-1 overflow-y-auto">
              {mobileDrawer === "toc" ? (
                <PageGrid
                  title={doc.title}
                  pages={sidebarPages}
                  currentPage={currentPage}
                  onJumpToPage={handleJumpToPage}
                />
              ) : (
                <NotepadPanel
                  documentId={documentId}
                  notes={notes}
                  onAddNote={handleAddNote}
                  onDeleteNote={handleDeleteNote}
                  onEditNote={handleEditNote}
                  onJumpToPage={handleJumpToPage}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Desktop Sidebar ─────────────────────────────────────────────── */}
      <aside
        onMouseEnter={() => revealSidebar()}
        onMouseLeave={scheduleSidebarClose}
        className={`
        hidden md:flex shrink-0 flex-col border-r border-border bg-card transition-all duration-300 ease-in-out relative z-30
        ${sidebarOpen ? "w-80" : "w-16"}
        ${!sidebarOpen && "items-center"}
      `}>
        {/* Logo stays visible when collapsed; hovering it opens the sidebar */}
        <div className={`flex items-center border-b border-border shrink-0 ${sidebarOpen ? "h-14 justify-between px-3" : "flex-col gap-1 py-2"}`}>
          <Link
            href="/"
            onMouseEnter={() => revealSidebar()}
            className={`flex hover:opacity-80 transition-opacity ${sidebarOpen ? "items-center gap-2" : "flex-col items-center gap-1"}`}
            title="FootNote"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
              <BookOpen size={16} />
            </span>
            <span className={`font-semibold tracking-tight text-primary ${sidebarOpen ? "text-sm" : "text-[9px] leading-none"}`}>
              FootNote
            </span>
          </Link>
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded hover:bg-secondary transition-colors"
            aria-label={sidebarPinned ? "Close sidebar" : "Open sidebar"}
            aria-expanded={sidebarOpen}
            title={sidebarPinned ? "Close sidebar" : "Open sidebar"}
          >
            {sidebarPinned ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>

        {/* Back to library */}
        {sidebarOpen && (
          <div className="px-3 pt-3 pb-1 shrink-0">
            <Link href="/" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors py-1">
              <ArrowLeft size={13} /> Library
            </Link>
          </div>
        )}

        {/* Panel switcher */}
        <div className={`flex shrink-0 border-b border-border ${sidebarOpen ? "px-3 gap-1 py-2" : "flex-col items-center py-2 gap-1"}`}>
          <button
            onClick={() => { setActivePanel("toc"); revealSidebar(); }}
            onMouseEnter={() => revealSidebar("toc")}
            className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded-md transition-colors ${activePanel === "toc" ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"}`}
            title="Contents"
          >
            <BookOpen size={14} />
            {sidebarOpen && "Contents"}
          </button>
          <button
            onClick={() => { setActivePanel("notes"); revealSidebar(); }}
            onMouseEnter={() => revealSidebar("notes")}
            className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded-md transition-colors ${activePanel === "notes" ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"}`}
            title="Notepad"
          >
            <NotebookPen size={14} />
            {sidebarOpen && "Notepad"}
          </button>
        </div>

        {/* Panel content */}
        {sidebarOpen && (
          <div className="flex-1 overflow-y-auto">
            {activePanel === "toc" && (
              <PageGrid
                title={doc.title}
                pages={sidebarPages}
                currentPage={currentPage}
                onJumpToPage={handleJumpToPage}
              />
            )}
            {activePanel === "notes" && (
              <NotepadPanel
                documentId={documentId}
                notes={notes}
                onAddNote={handleAddNote}
                onDeleteNote={handleDeleteNote}
                onEditNote={handleEditNote}
                onJumpToPage={handleJumpToPage}
              />
            )}
          </div>
        )}
      </aside>

      {/* ── Main Document Reading Area ───────────────────────────── */}
      <div className="flex-1 min-w-0 w-full flex flex-col h-full overflow-hidden relative">
        {/* Mobile Top Header (md:hidden) */}
        <header className="md:hidden flex items-center justify-between px-3 h-14 border-b border-border bg-card/95 backdrop-blur-sm shrink-0 z-20">
          <div className="flex items-center gap-2 min-w-0 flex-1 mr-2">
            <Link
              href="/"
              className="p-1.5 -ml-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary shrink-0 transition-colors"
              title="Back to Library"
              aria-label="Back to Library"
            >
              <ArrowLeft size={18} />
            </Link>
            <div className="min-w-0 flex-1">
              <h1 className="text-xs font-semibold truncate text-foreground leading-tight">
                {doc.title}
              </h1>
              <p className="text-[10px] text-muted-foreground truncate">
                Page {currentPage} {pdfPageCount > 0 ? `of ${pdfPageCount}` : ""}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => setMobileDrawer("toc")}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
              title="Table of Contents"
              aria-label="Table of Contents"
            >
              <BookOpen size={18} />
            </button>
            <button
              onClick={() => setMobileDrawer("notes")}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors relative"
              title="Notepad"
              aria-label="Notepad"
            >
              <NotebookPen size={18} />
              {notes.length > 0 && (
                <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-primary" />
              )}
            </button>
            <button
              onClick={() => setChatOpen(true)}
              className="ml-1 p-1.5 px-2.5 rounded-lg bg-primary/10 text-primary hover:bg-primary/20 font-medium text-xs flex items-center gap-1 transition-colors"
              title="Ask FootNote"
              aria-label="Ask FootNote"
            >
              <Sparkles size={14} />
              <span>Ask</span>
            </button>
          </div>
        </header>

        {/* Reader Container */}
        <main className="flex-1 min-w-0 w-full flex flex-col h-full overflow-hidden pb-14 md:pb-0">
          {isPdf ? (
            <PdfViewer
              data={pdfData}
              loading={pdfLoading}
              error={pdfError}
              activePage={currentPage}
              jumpToken={jumpToken}
              onJumpToPage={handleJumpToPage}
              onVisiblePage={setCurrentPage}
              onPageCount={setPdfPageCount}
              readerRootRef={readerRootRef}
            />
          ) : (
            <BookReader
              pages={bookPages}
              loading={pagesLoading}
              error={pagesError}
              activePage={currentPage}
              jumpToken={jumpToken}
              onJumpToPage={handleJumpToPage}
              onVisiblePage={setCurrentPage}
              readerRootRef={readerRootRef}
            />
          )}
        </main>

        {/* Mobile Bottom Navigation Bar (md:hidden, visible when chat is closed) */}
        {!chatOpen && (
          <nav
            aria-label="Mobile Navigation"
            className="md:hidden fixed bottom-0 left-0 right-0 h-14 bg-card/95 backdrop-blur-md border-t border-border flex items-center justify-around px-3 z-30 shadow-lg"
          >
            <button
              onClick={() => setMobileDrawer("toc")}
              className="flex flex-col items-center justify-center flex-1 py-1 text-muted-foreground hover:text-foreground transition-colors"
            >
              <BookOpen size={18} />
              <span className="text-[10px] font-medium mt-0.5">Contents</span>
            </button>

            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-primary text-primary-foreground font-semibold text-xs shadow-md active:scale-95 transition-transform"
            >
              <Sparkles size={15} />
              <span>Ask FootNote</span>
            </button>

            <button
              onClick={() => setMobileDrawer("notes")}
              className="flex flex-col items-center justify-center flex-1 py-1 text-muted-foreground hover:text-foreground transition-colors relative"
            >
              <NotebookPen size={18} />
              <span className="text-[10px] font-medium mt-0.5">Notes</span>
              {notes.length > 0 && (
                <span className="absolute top-1 right-1/4 w-2 h-2 rounded-full bg-primary" />
              )}
            </button>
          </nav>
        )}
      </div>

      {/* ── Chat Pane (Responsive Sheet on Mobile / Resizable Column on Desktop) ── */}
      {chatOpen ? (
        <aside
          className="fixed inset-0 z-50 flex flex-col bg-card w-full h-[100dvh] md:relative md:inset-auto md:z-auto md:h-full md:border-l md:border-border shrink-0 shadow-2xl md:shadow-none animate-in fade-in duration-150"
          style={isMobile ? undefined : { width: `${chatWidth}px`, minWidth: `${CHAT_MIN_WIDTH}px`, maxWidth: `${CHAT_MAX_WIDTH}px` }}
        >
          {/* Drag handle for resizing - desktop only */}
          <div
            onMouseDown={handleResizeMouseDown}
            className="hidden md:flex absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize z-40 group hover:bg-primary/15 transition-colors items-center justify-center"
            title="Drag to resize chat"
          >
            <div className="w-0.5 h-8 rounded-full bg-border group-hover:bg-primary/50 transition-colors" />
          </div>

          {/* Chat header */}
          <div className="flex items-center justify-between px-4 h-14 border-b border-border shrink-0 bg-card">
            <div className="flex items-center gap-2 min-w-0">
              {/* Mobile back to reading button */}
              <button
                onClick={() => setChatOpen(false)}
                className="md:hidden p-1.5 -ml-1 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors mr-0.5 flex items-center gap-1"
                title="Back to Document"
                aria-label="Back to Document"
              >
                <ArrowLeft size={18} />
                <span className="text-xs font-medium">Reader</span>
              </button>

              {showHistory ? (
                <button
                  onClick={() => setShowHistory(false)}
                  className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors mr-0.5"
                  title="Back to chat"
                  aria-label="Back to chat"
                >
                  <ArrowLeft size={16} />
                </button>
              ) : (
                <div className="w-6 h-6 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                  <Sparkles size={14} className="text-primary" />
                </div>
              )}
              <div className="min-w-0">
                <span className="text-sm font-semibold truncate block">
                  {showHistory ? "Chat History" : "Ask FootNote"}
                </span>
                {!showHistory && conversationId && (
                  <span className="text-[10px] text-muted-foreground block -mt-0.5 truncate">
                    Past chat session
                  </span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              {/* Start new fresh chat */}
              <button
                onClick={handleNewChat}
                className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-primary transition-colors flex items-center gap-1"
                title="Start new fresh chat"
                aria-label="Start new fresh chat"
              >
                <Plus size={16} />
                <span className="text-xs font-medium hidden sm:inline">New</span>
              </button>

              {/* Chat history toggle button */}
              <button
                onClick={() => setShowHistory(prev => !prev)}
                className={`p-1.5 rounded-lg transition-colors relative ${showHistory
                    ? "bg-primary/15 text-primary"
                    : "hover:bg-secondary text-muted-foreground hover:text-foreground"
                  }`}
                title={showHistory ? "Close history" : "Open chat history"}
                aria-label="Chat history"
              >
                <History size={16} />
                {conversations.length > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-primary text-primary-foreground text-[10px] font-bold rounded-full flex items-center justify-center scale-90">
                    {conversations.length > 9 ? "9+" : conversations.length}
                  </span>
                )}
              </button>

              {/* Close chat pane */}
              <button
                onClick={() => setChatOpen(false)}
                className="p-1.5 rounded-lg hover:bg-secondary text-muted-foreground hover:text-destructive transition-colors ml-0.5"
                title="Minimize chat"
                aria-label="Close chat"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {showHistory ? (
            /* ── History Panel ─────────────────────────────────────────── */
            <div className="flex-1 overflow-y-auto p-4 flex flex-col bg-card">
              <button
                onClick={handleNewChat}
                className="w-full mb-3.5 flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-all shadow-xs"
              >
                <Plus size={15} /> Start New Fresh Chat
              </button>

              <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider px-1 mb-2.5 flex items-center justify-between">
                <span>Saved Conversations</span>
                <span className="text-[10px] bg-secondary px-1.5 py-0.5 rounded font-normal">
                  {conversations.length}
                </span>
              </div>

              {conversations.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center p-6 space-y-3">
                  <div className="w-12 h-12 rounded-full bg-secondary flex items-center justify-center text-muted-foreground">
                    <History size={22} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold">No chat history yet</p>
                    <p className="text-xs text-muted-foreground mt-1 max-w-[210px]">
                      Your conversations about "{doc.title}" will appear here so you can revisit them anytime.
                    </p>
                  </div>
                  <button
                    onClick={handleNewChat}
                    className="text-xs text-primary font-medium hover:underline pt-2"
                  >
                    Ask a question
                  </button>
                </div>
              ) : (
                <div className="space-y-2 flex-1 overflow-y-auto">
                  {conversations.map((c) => {
                    const isActive = c.id === conversationId;
                    const isLoading = loadingHistoryId === c.id;
                    return (
                      <div
                        key={c.id}
                        onClick={() => !isLoading && handleSelectConversation(c.id)}
                        className={`group relative p-3 rounded-xl border text-left cursor-pointer transition-all ${isActive
                            ? "bg-primary/10 border-primary/40 shadow-xs"
                            : "bg-background/80 hover:bg-secondary/60 border-border/70 hover:border-primary/30"
                          }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div className={`p-1.5 rounded-lg shrink-0 ${isActive ? "bg-primary text-primary-foreground" : "bg-primary/10 text-primary"}`}>
                              {isLoading ? (
                                <Loader2 size={13} className="animate-spin" />
                              ) : (
                                <MessageSquare size={13} />
                              )}
                            </div>
                            <span className="text-xs font-medium text-foreground line-clamp-1 truncate">
                              {c.title || "Conversation"}
                            </span>
                          </div>
                          <button
                            onClick={(e) => handleDeleteConversation(c.id, e)}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all shrink-0"
                            title="Delete conversation"
                            aria-label="Delete conversation"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>

                        <div className="flex items-center justify-between mt-2 pt-1 border-t border-border/30 text-[10px] text-muted-foreground">
                          <span>{formatChatDate(c.updated_at || c.created_at)}</span>
                          <span className="bg-secondary px-1.5 py-0.5 rounded text-[10px]">
                            {c.message_count} {c.message_count === 1 ? "msg" : "msgs"}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : (
            /* ── Active Chat View ───────────────────────────────────────── */
            <>
              {conversationId && (
                <div className="flex items-center justify-between bg-primary/5 border-b border-primary/15 px-3 py-1.5 text-xs text-muted-foreground shrink-0">
                  <span className="flex items-center gap-1.5 truncate">
                    <History size={12} className="text-primary shrink-0" />
                    <span className="truncate">Loaded past chat session</span>
                  </span>
                  <button
                    onClick={handleNewChat}
                    className="text-[11px] font-medium text-primary hover:underline flex items-center gap-1 shrink-0 ml-2"
                  >
                    <Plus size={11} /> Start fresh
                  </button>
                </div>
              )}

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.length === 0 && stream.status === "idle" && (
                  <div className="text-center pt-8 px-4 space-y-4">
                    <div className="bg-primary/10 w-12 h-12 rounded-full flex items-center justify-center mx-auto">
                      <MessageSquare size={20} className="text-primary" />
                    </div>
                    <div>
                      <p className="font-semibold text-sm">Ask about "{doc.title}"</p>
                      <p className="text-xs text-muted-foreground mt-1">Select text in the reader to ask about it, or type a question below.</p>
                    </div>
                    <div className="grid grid-cols-1 gap-2 text-left mt-2">
                      {["What is the main idea?", "Summarize the introduction.", "Explain the key concepts.", "Find important quotes."].map((p) => (
                        <button key={p} onClick={() => handleSend(p)} className="text-xs p-3 rounded-xl border border-border bg-background hover:border-primary/40 hover:shadow-sm text-left transition-all">
                          {p}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((msg, i) => (
                  <div key={msg.id || i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    {msg.role === "user" ? (
                      <div className="max-w-[85%] bg-primary text-primary-foreground rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    ) : (
                      <div className="max-w-full w-full">
                        <AnswerCard
                          content={msg.content}
                          isStreaming={false}
                          sources={getSourcesForMessage(msg)}
                          onSaveToNotes={() => {
                            const srcPage = getSourcesForMessage(msg).find(s => s.page)?.page;
                            handleSaveAnswerToNotes(msg.content, srcPage);
                          }}
                          onInDetail={() => handleSend("Can you explain that in more detail with a summary table?")}
                          onDiscuss={() => { setInput("Tell me more about this passage."); inputRef.current?.focus(); }}
                          onJumpToPage={handleJumpToPage}
                        />
                      </div>
                    )}
                  </div>
                ))}

                {/* Live streaming answer */}
                {isStreaming && (
                  <div className="flex justify-start">
                    <div className="w-full">
                      <AnswerCard
                        content={stream.answer || ""}
                        isStreaming
                        sources={stream.sources}
                        onSaveToNotes={() => { }}
                        onInDetail={() => { }}
                        onDiscuss={() => { }}
                        onJumpToPage={handleJumpToPage}
                      />
                    </div>
                  </div>
                )}

                {/* Empty streaming state (thinking) */}
                {isStreaming && !stream.answer && (
                  <div className="flex justify-start">
                    <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2">
                      <span className="flex gap-1">
                        {[0, 150, 300].map(d => (
                          <span key={d} className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-bounce" style={{ animationDelay: `${d}ms` }} />
                        ))}
                      </span>
                      <span className="text-xs text-muted-foreground">FootNote is reading…</span>
                    </div>
                  </div>
                )}

                {sendError && (
                  <button onClick={() => handleSend()} className="w-full text-xs text-destructive border border-destructive/30 rounded-lg p-2 hover:bg-destructive/5 transition-colors">
                    {sendError} Tap to retry.
                  </button>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="p-3 border-t border-border shrink-0">
                {quoteChip && (
                  <QuoteChip text={quoteChip.text} page={quoteChip.page} onRemove={() => { setQuoteChip(null); setInputPlaceholder("Ask what you're not understanding…"); }} />
                )}
                <div className="relative flex items-end bg-background rounded-xl border border-border focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/40 transition-all shadow-sm">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={inputPlaceholder}
                    rows={1}
                    disabled={isStreaming}
                    className="w-full py-3 pl-4 pr-12 bg-transparent resize-none outline-none text-sm max-h-28 min-h-[44px]"
                  />
                  <button
                    onClick={() => handleSend()}
                    disabled={!input.trim() || isStreaming}
                    className="absolute right-2 bottom-2 p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:pointer-events-none transition-all"
                  >
                    <Send size={15} />
                  </button>
                </div>
              </div>
            </>
          )}
        </aside>
      ) : (
        /* Floating movable chat reopen button (desktop only) */
        <div className="hidden md:block">
          <MovableChatButton
            onClick={() => setChatOpen(true)}
            conversationCount={conversations.length}
          />
        </div>
      )}

      {/* Proof of Save: Toast Notification Pop-up */}
      {savedToast.visible && (
        <div
          role="status"
          aria-live="polite"
          className="fixed bottom-20 left-4 right-4 sm:bottom-6 sm:left-auto sm:right-6 z-50 flex items-start gap-3 bg-card border-2 border-emerald-500/30 shadow-2xl rounded-2xl p-4 sm:max-w-sm animate-in fade-in slide-in-from-bottom-5 duration-200 backdrop-blur-md"
        >
          <div className="h-8 w-8 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
            <Check size={16} strokeWidth={2.5} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-semibold text-xs text-foreground">Saved to Notes!</p>
              {savedToast.page && (
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/10 text-primary">
                  Page {savedToast.page}
                </span>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
              {savedToast.preview ? `"${savedToast.preview}…"` : "Answer saved to your document notebook."}
            </p>
            <div className="flex items-center gap-2 mt-2 pt-1.5 border-t border-border/40">
              <button
                onClick={() => {
                  if (typeof window !== "undefined" && window.innerWidth < 768) {
                    setMobileDrawer("notes");
                  } else {
                    setActivePanel("notes");
                    setSidebarPinned(true);
                  }
                  setSavedToast({ visible: false });
                }}
                className="text-xs font-medium text-primary hover:underline flex items-center gap-1 cursor-pointer"
              >
                <NotebookPen size={12} /> View in Notes
              </button>
            </div>
          </div>
          <button
            onClick={() => setSavedToast({ visible: false })}
            className="text-muted-foreground hover:text-foreground p-1 shrink-0 -mr-1 -mt-1 rounded-md hover:bg-secondary transition-colors cursor-pointer"
            aria-label="Close notification"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
