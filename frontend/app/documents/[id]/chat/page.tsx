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
  SectionResponse,
  NoteResponse,
  PageResponse,
} from "@/types/api";
import {
  Send, ArrowLeft, BookOpen, Menu, X, ChevronRight, ChevronLeft,
  ChevronDown, NotebookPen, Sparkles, MessageSquare, Check, Plus,
  Trash2, Edit3, Hash
} from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

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
function Accordion({ label, badge, children }: { label: string; badge?: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border/50 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-secondary/30 hover:bg-secondary/60 transition-colors text-sm font-medium"
      >
        <span className="flex items-center gap-2">
          {label}
          {badge && <span className="text-xs text-muted-foreground font-normal">· {badge}</span>}
        </span>
        <ChevronDown size={15} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-4 py-3 text-sm leading-relaxed text-foreground/85">{children}</div>}
    </div>
  );
}

// ── AnswerCard ─────────────────────────────────────────────────────────────────
function AnswerCard({
  content, isStreaming, onSaveToNotes, onInDetail, onDiscuss
}: {
  content: string;
  isStreaming: boolean;
  onSaveToNotes: () => void;
  onInDetail: () => void;
  onDiscuss: () => void;
}) {
  // Parse <details> blocks from content for Proof/Simple/Example
  const parseDetails = (text: string) => {
    const answer = text.replace(/<details[\s\S]*?<\/details>/g, '').replace(/\*\*Answer\*\*/g, '').trim();
    const proofMatch = text.match(/<details>\s*<summary>Proof<\/summary>([\s\S]*?)<\/details>/);
    const simpleMatch = text.match(/<details>\s*<summary>Simple Explanation<\/summary>([\s\S]*?)<\/details>/);
    const exampleMatch = text.match(/<details>\s*<summary>Example<\/summary>([\s\S]*?)<\/details>/);
    return {
      answer,
      proof: proofMatch?.[1]?.trim(),
      simple: simpleMatch?.[1]?.trim(),
      example: exampleMatch?.[1]?.trim(),
    };
  };

  const parsed = parseDetails(content);

  return (
    <div className="bg-card border border-border shadow-sm rounded-2xl rounded-tl-sm p-5 space-y-4">
      {/* Main Answer */}
      <div className="prose prose-sm prose-stone dark:prose-invert max-w-none text-[15px] leading-relaxed">
        {parsed.answer ? (
          <ReactMarkdown>{parsed.answer}</ReactMarkdown>
        ) : (
          <ReactMarkdown>{content}</ReactMarkdown>
        )}
        {isStreaming && <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-middle" />}
      </div>

      {/* Dropdowns only when streaming is done */}
      {!isStreaming && parsed.proof && (
        <div className="space-y-2">
          <Accordion label="Proof" badge={parsed.proof.match(/page\s*\d+/i)?.[0]}>
            <p className="font-['Lora'] italic text-foreground/80">"{parsed.proof}"</p>
          </Accordion>
          {parsed.simple && (
            <Accordion label="Simple Explanation">
              <ReactMarkdown>{parsed.simple}</ReactMarkdown>
            </Accordion>
          )}
          {parsed.example && (
            <Accordion label="Example">
              <ReactMarkdown>{parsed.example}</ReactMarkdown>
            </Accordion>
          )}
        </div>
      )}

      {/* Footer actions */}
      {!isStreaming && (
        <div className="flex items-center gap-3 pt-2 border-t border-border/50 flex-wrap">
          <button onClick={onSaveToNotes} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors">
            <NotebookPen size={13} /> Save to notes
          </button>
          <button onClick={onInDetail} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors">
            <Sparkles size={13} /> In detail
          </button>
          <button onClick={onDiscuss} className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors">
            <MessageSquare size={13} /> Discuss this
          </button>
        </div>
      )}
    </div>
  );
}

// ── TocTree ────────────────────────────────────────────────────────────────────
function TocTree({
  sections, currentPage, onJumpToPage
}: {
  sections: SectionResponse[];
  currentPage: number;
  onJumpToPage: (page: number) => void;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggle = (id: string) => setExpanded(p => {
    const n = new Set(p);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  // Group into tree
  const roots = sections.filter(s => !s.parent_id);
  const children = (parentId: string) => sections.filter(s => s.parent_id === parentId);

  const renderItem = (sec: SectionResponse, depth = 0): React.ReactNode => {
    const hasChildren = children(sec.id).length > 0;
    const isExpanded = expanded.has(sec.id);
    const isActive = sec.page != null && currentPage === sec.page;

    return (
      <div key={sec.id}>
        <div
          className={`flex items-center gap-1 py-1.5 px-2 rounded-md cursor-pointer text-sm transition-colors ${
            isActive ? "bg-primary/10 text-primary font-medium" : "hover:bg-secondary/60 text-foreground/80"
          }`}
          style={{ paddingLeft: `${(depth + 1) * 12}px` }}
        >
          {hasChildren ? (
            <button onClick={() => toggle(sec.id)} className="p-0.5 shrink-0">
              <ChevronRight size={13} className={`transition-transform ${isExpanded ? "rotate-90" : ""}`} />
            </button>
          ) : (
            <span className="w-5 shrink-0" />
          )}
          <span
            className="truncate flex-1"
            onClick={() => sec.page && onJumpToPage(sec.page)}
            title={sec.title}
          >
            {sec.title}
          </span>
          {sec.page && (
            <span className="text-xs text-muted-foreground shrink-0 ml-1">p.{sec.page}</span>
          )}
        </div>
        {hasChildren && isExpanded && children(sec.id).map(c => renderItem(c, depth + 1))}
      </div>
    );
  };

  if (sections.length === 0) {
    return <p className="text-sm text-muted-foreground italic px-2">No table of contents detected.</p>;
  }

  return <div className="space-y-0.5">{roots.map(s => renderItem(s))}</div>;
}

// ── BookReader ────────────────────────────────────────────────────────────────
function BookReader({
  documentId, totalPages, onPageChange, readerRootRef
}: {
  documentId: string;
  totalPages: number;
  onPageChange: (page: number) => void;
  readerRootRef: React.RefObject<HTMLDivElement | null>;
}) {
  const [page, setPage] = useState(1);
  const [pageData, setPageData] = useState<PageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [inputPage, setInputPage] = useState("1");

  const loadPage = useCallback(async (p: number) => {
    if (p < 1 || (totalPages > 0 && p > totalPages)) return;
    setLoading(true);
    try {
      const data = await documentsService.getPage(documentId, p);
      setPageData(data);
      setPage(p);
      setInputPage(String(p));
      onPageChange(p);
      // Save to localStorage
      localStorage.setItem(`footnote_page_${documentId}`, String(p));
    } catch {
      // Page not yet stored
    } finally {
      setLoading(false);
    }
  }, [documentId, totalPages, onPageChange]);

  useEffect(() => {
    const saved = localStorage.getItem(`footnote_page_${documentId}`);
    loadPage(saved ? parseInt(saved, 10) : 1);
  }, [documentId, loadPage]);

  const handlePageInput = (e: React.FormEvent) => {
    e.preventDefault();
    const n = parseInt(inputPage, 10);
    if (!isNaN(n)) loadPage(n);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Page controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-secondary/20 shrink-0">
        <button onClick={() => loadPage(page - 1)} disabled={page <= 1 || loading} className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors">
          <ChevronLeft size={18} />
        </button>
        <form onSubmit={handlePageInput} className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Page</span>
          <input
            type="number"
            value={inputPage}
            onChange={e => setInputPage(e.target.value)}
            className="w-14 text-center bg-background border border-border rounded px-1 py-0.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
            min={1}
            max={totalPages || undefined}
          />
          {totalPages > 0 && <span className="text-muted-foreground">/ {totalPages}</span>}
        </form>
        <button onClick={() => loadPage(page + 1)} disabled={(totalPages > 0 && page >= totalPages) || loading} className="p-1.5 rounded hover:bg-secondary disabled:opacity-40 transition-colors">
          <ChevronRight size={18} />
        </button>
      </div>

      {/* Page content */}
      <div
        ref={readerRootRef}
        data-reader-root
        className="flex-1 overflow-y-auto px-8 py-6 font-['Lora'] text-[15px] leading-[1.85] selection:bg-primary/25"
      >
        {loading ? (
          <div className="space-y-3 animate-pulse">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className={`h-4 bg-muted rounded ${i % 5 === 4 ? "w-3/4" : "w-full"}`} />
            ))}
          </div>
        ) : pageData ? (
          <div data-page={page} className="whitespace-pre-wrap text-foreground/90">
            {pageData.content}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p>Pages not available for this document yet.</p>
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

// ── Main Workspace Page ────────────────────────────────────────────────────────
export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  // State
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [sections, setSections] = useState<SectionResponse[]>([]);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [notes, setNotes] = useState<NoteResponse[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [totalPages, setTotalPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);

  // UI state
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(true);
  const [activePanel, setActivePanel] = useState<Panel>("toc");
  const [input, setInput] = useState("");
  const [inputPlaceholder, setInputPlaceholder] = useState("Ask what you're not understanding…");
  const [quoteChip, setQuoteChip] = useState<{ text: string; page?: number | null } | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const readerRootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const readerRef = useRef<{ loadPage: (p: number) => void } | null>(null);

  // Hooks
  const { state: stream, send: streamSend } = useChatStream();
  const { selection, clearSelection } = useTextSelection(readerRootRef);

  // Show selection toolbar
  useEffect(() => {
    if (selection && selection.text.length >= 3) {
      setQuoteChip({ text: selection.text, page: selection.page });
      setInputPlaceholder("Ask what you're not understanding from these lines or paragraph…");
      inputRef.current?.focus();
    }
  }, [selection]);

  // Load initial data in parallel
  useEffect(() => {
    const load = async () => {
      try {
        const [docData, { sections: sectionsData }, convData, notesData] = await Promise.all([
          documentsService.get(documentId),
          documentsService.getSections(documentId),
          chatService.listConversations(documentId),
          notesService.list(documentId),
        ]);

        if (docData.status !== "ready") {
          router.push(`/documents/${documentId}/processing`);
          return;
        }
        setDoc(docData);
        setSections(sectionsData);
        setTotalPages(docData.processing?.pages ?? 0);
        setNotes(notesData.notes);

        if (convData.conversations.length > 0) {
          const recent = convData.conversations[0];
          setConversationId(recent.id);
          const { messages: msgs } = await chatService.getConversation(recent.id);
          setMessages(msgs);
        }
      } catch (err) {
        console.error("Failed to load workspace", err);
      }
    };
    load();
  }, [documentId, router]);

  // Add streamed assistant message to history when done
  useEffect(() => {
    if (stream.status === "done" && stream.answer) {
      const assistantMsg: MessageResponse = {
        id: `stream_${Date.now()}`,
        conversation_id: conversationId || "",
        role: "assistant",
        content: stream.answer,
        intent: stream.intent ?? undefined,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => {
        // Avoid duplicate if already added
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.content === stream.answer) return prev;
        return [...prev, assistantMsg];
      });
    }
  }, [stream.status, stream.answer, stream.intent, conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, stream.answer]);

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
  const handleDeleteNote = async (id: string) => {
    await notesService.delete(id);
    setNotes(prev => prev.filter(n => n.id !== id));
  };
  const handleEditNote = async (id: string, content: string) => {
    const updated = await notesService.update(id, content);
    setNotes(prev => prev.map(n => n.id === id ? updated : n));
  };

  const handleJumpToPage = (page: number) => {
    // Signal BookReader to jump
    setCurrentPage(page);
  };

  if (!doc) return <div className="h-screen bg-background animate-pulse" />;

  const isStreaming = stream.status === "streaming";

  return (
    <div className="flex h-screen bg-background overflow-hidden font-sans">
      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className={`
        shrink-0 flex flex-col border-r border-border bg-card transition-all duration-300 ease-in-out
        ${sidebarOpen ? "w-64" : "w-14"}
        fixed md:static inset-y-0 left-0 z-40 md:z-auto
        ${!sidebarOpen && "items-center"}
      `}>
        {/* Logo + collapse */}
        <div className={`flex items-center border-b border-border h-14 shrink-0 px-3 ${sidebarOpen ? "justify-between" : "justify-center"}`}>
          {sidebarOpen && (
            <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
              <BookOpen size={18} className="text-primary" />
              <span className="font-semibold text-sm tracking-tight">FootNote</span>
            </Link>
          )}
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-1.5 rounded hover:bg-secondary transition-colors" aria-label="Toggle sidebar" aria-expanded={sidebarOpen}>
            {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
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
            onClick={() => setActivePanel("toc")}
            className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded-md transition-colors ${activePanel === "toc" ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"}`}
            title="Table of Contents"
          >
            <BookOpen size={14} />
            {sidebarOpen && "Contents"}
          </button>
          <button
            onClick={() => setActivePanel("notes")}
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
              <div className="p-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-1">{doc.title}</p>
                <TocTree sections={sections} currentPage={currentPage} onJumpToPage={handleJumpToPage} />
              </div>
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

      {/* ── Reader Pane ──────────────────────────────────────────── */}
      <main className={`flex-1 flex flex-col h-full transition-all ${sidebarOpen ? "ml-0" : "ml-0"}`}>
        {totalPages > 0 ? (
          <BookReader
            documentId={documentId}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            readerRootRef={readerRootRef}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground flex-col gap-2">
            <BookOpen size={32} className="opacity-40" />
            <p className="text-sm">Reader not available — pages not indexed yet.</p>
            <p className="text-xs">Use the chat panel to ask questions.</p>
          </div>
        )}
      </main>

      {/* ── Chat Pane ─────────────────────────────────────────────── */}
      {chatOpen ? (
        <aside className="w-96 shrink-0 flex flex-col border-l border-border bg-card h-full">
          {/* Chat header */}
          <div className="flex items-center justify-between px-4 h-14 border-b border-border shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-primary" />
              <span className="text-sm font-semibold">Ask FootNote</span>
            </div>
            <button onClick={() => setChatOpen(false)} className="p-1.5 rounded hover:bg-secondary transition-colors" aria-label="Close chat">
              <X size={16} />
            </button>
          </div>

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
                      onSaveToNotes={() => handleAddNote(msg.content)}
                      onInDetail={() => handleSend("Can you explain that in more detail?")}
                      onDiscuss={() => { setInput("Tell me more about this passage."); inputRef.current?.focus(); }}
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
                    onSaveToNotes={() => {}}
                    onInDetail={() => {}}
                    onDiscuss={() => {}}
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
        </aside>
      ) : (
        /* Floating chat reopen button */
        <button
          onClick={() => setChatOpen(true)}
          className="fixed bottom-6 right-6 w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl hover:scale-105 transition-all flex items-center justify-center z-50"
          aria-label="Open chat"
        >
          <MessageSquare size={20} />
        </button>
      )}
    </div>
  );
}
