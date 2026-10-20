"use client";

import { useEffect, useRef, useState, useCallback, type FormEvent, type MouseEvent } from "react";
import { documentsService } from "@/services/documents";
import type { DocumentResponse } from "@/types/api";
import { UploadModal } from "@/components/upload/UploadModal";
import {
  Book, FileText, File, MoreVertical, Plus, Loader2,
  Pencil, Trash2, X, Star, Check
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { useRouter } from "next/navigation";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "favorites">("all");

  // Edit State
  const [editingDocument, setEditingDocument] = useState<DocumentResponse | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editAuthor, setEditAuthor] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Delete State
  const [deletingDocument, setDeletingDocument] = useState<DocumentResponse | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Toast feedback state
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const router = useRouter();

  const showToast = (message: string, type: "success" | "error" = "success") => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToast({ message, type });
    toastTimerRef.current = setTimeout(() => {
      setToast(null);
    }, 4000);
  };

  const fetchDocuments = useCallback(async () => {
    try {
      const data = await documentsService.list();
      setDocuments(data.documents);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchDocuments();
  }, [fetchDocuments]);

  useEffect(() => {
    const handleClickOutside = (event: globalThis.MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("[data-menu-trigger]") || target?.closest("[data-menu-dropdown]")) {
        return;
      }
      setOpenMenuId(null);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenMenuId(null);
    };
    document.addEventListener("click", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("click", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  // 1. Toggle Favorite / Star Option
  const handleToggleFavorite = async (e: MouseEvent, doc: DocumentResponse) => {
    e.stopPropagation();
    setOpenMenuId(null);
    const newFavorite = !doc.is_favorite;

    // Optimistically update UI
    setDocuments((current) =>
      current.map((d) => (d.id === doc.id ? { ...d, is_favorite: newFavorite } : d))
    );

    try {
      await documentsService.update(doc.id, { is_favorite: newFavorite });
      showToast(
        newFavorite ? `"${doc.title}" marked as favorite ⭐` : `"${doc.title}" removed from favorites`
      );
    } catch {
      // Revert on error
      setDocuments((current) =>
        current.map((d) => (d.id === doc.id ? { ...d, is_favorite: !newFavorite } : d))
      );
      showToast("Could not update favorite status.", "error");
    }
  };

  // 2. Edit Book Card Option
  const openEdit = (e: MouseEvent, doc: DocumentResponse) => {
    e.stopPropagation();
    setOpenMenuId(null);
    setEditTitle(doc.title);
    setEditAuthor(doc.author || "");
    setEditError(null);
    setEditingDocument(doc);
  };

  const handleSaveEdit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingDocument) return;

    const title = editTitle.trim();
    if (!title) {
      setEditError("Enter a document title.");
      return;
    }

    setIsSavingEdit(true);
    setEditError(null);
    try {
      const updated = await documentsService.update(editingDocument.id, {
        title,
        author: editAuthor.trim() || undefined,
      });
      setDocuments((current) => current.map((doc) => (doc.id === updated.id ? updated : doc)));
      setEditingDocument(null);
      showToast(`Updated "${updated.title}" successfully!`);
    } catch {
      setEditError("Could not update this document. Please try again.");
    } finally {
      setIsSavingEdit(false);
    }
  };

  // 3. Delete Book Card Option
  const openDelete = (e: MouseEvent, doc: DocumentResponse) => {
    e.stopPropagation();
    setOpenMenuId(null);
    setDeleteError(null);
    setDeletingDocument(doc);
  };

  const handleDelete = async () => {
    if (!deletingDocument) return;

    setIsDeleting(true);
    setDeleteError(null);
    try {
      await documentsService.delete(deletingDocument.id);
      const deletedTitle = deletingDocument.title;
      setDocuments((current) => current.filter((doc) => doc.id !== deletingDocument.id));
      setDeletingDocument(null);
      showToast(`"${deletedTitle}" deleted successfully.`);
    } catch {
      setDeleteError("Could not delete this document. Please try again.");
    } finally {
      setIsDeleting(false);
    }
  };

  const getIcon = (type: string) => {
    switch (type) {
      case "book":
        return <Book className="w-5 h-5 text-primary" />;
      case "research_paper":
        return <FileText className="w-5 h-5 text-accent" />;
      default:
        return <File className="w-5 h-5 text-muted-foreground" />;
    }
  };

  const favoritesCount = documents.filter((d) => d.is_favorite).length;
  const filteredDocuments = filter === "favorites" ? documents.filter((d) => d.is_favorite) : documents;

  return (
    <main className="min-h-screen p-4 sm:p-8 md:p-12 lg:p-24 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 sm:mb-10 gap-4 sm:gap-6">
        <div>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-1 sm:mb-2 text-primary">FootNote</h1>
          <p className="text-muted-foreground text-sm sm:text-lg">Turn every document into a conversation.</p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="w-full sm:w-auto justify-center bg-primary text-primary-foreground px-5 py-2.5 sm:px-6 sm:py-3 rounded-xl font-medium shadow-sm hover:shadow-md hover:bg-primary/90 transition-all flex items-center gap-2 cursor-pointer"
        >
          <Plus size={18} />
          Add Document
        </button>
      </div>

      {/* Filter Tabs */}
      {!loading && documents.length > 0 && (
        <div className="flex items-center gap-2 mb-6 border-b border-border pb-3">
          <button
            onClick={() => setFilter("all")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              filter === "all"
                ? "bg-primary text-primary-foreground shadow-2xs"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary"
            }`}
          >
            All Documents ({documents.length})
          </button>
          <button
            onClick={() => setFilter("favorites")}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
              filter === "favorites"
                ? "bg-amber-500 text-white shadow-2xs"
                : "text-muted-foreground hover:text-foreground hover:bg-secondary"
            }`}
          >
            <Star size={13} className={filter === "favorites" ? "fill-white" : "fill-amber-400 text-amber-500"} />
            Favorites ({favoritesCount})
          </button>
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary/50" />
        </div>
      ) : documents.length === 0 ? (
        <div className="text-center py-24 border-2 border-dashed border-border rounded-3xl bg-secondary/30">
          <Book className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Your knowledge library is empty</h2>
          <p className="text-muted-foreground mb-6 max-w-md mx-auto">
            Upload a book, research paper, or document to start building your personal knowledge base.
          </p>
          <button
            onClick={() => setShowUpload(true)}
            className="text-primary font-medium hover:underline cursor-pointer"
          >
            Upload your first document
          </button>
        </div>
      ) : filteredDocuments.length === 0 ? (
        <div className="text-center py-16 border border-dashed border-border rounded-2xl bg-secondary/20">
          <Star className="w-12 h-12 text-amber-400/50 mx-auto mb-3" />
          <h3 className="text-base font-semibold mb-1">No favorite documents yet</h3>
          <p className="text-xs text-muted-foreground mb-4">
            Click the star icon or choose &quot;Mark as Favorite&quot; in the 3-dots menu on any book card.
          </p>
          <button
            onClick={() => setFilter("all")}
            className="text-xs font-medium text-primary hover:underline cursor-pointer"
          >
            Show all documents
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDocuments.map((doc) => (
            <div
              key={doc.id}
              className="group bg-card border border-border hover:border-primary/40 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all flex flex-col cursor-pointer relative"
              onClick={() => {
                if (doc.status === "ready") {
                  router.push(`/documents/${doc.id}/chat`);
                } else {
                  router.push(`/documents/${doc.id}/processing`);
                }
              }}
            >
              {/* Top card row: Icon + Favorite Star + 3-Dot Actions Menu */}
              <div className="flex justify-between items-start mb-4">
                <div className="p-3 bg-secondary/50 rounded-xl">{getIcon(doc.document_type)}</div>

                <div className="flex items-center gap-1">
                  {/* Quick Star / Favorite Toggle */}
                  <button
                    type="button"
                    aria-label={doc.is_favorite ? "Remove from favorites" : "Mark as favorite"}
                    onClick={(e) => handleToggleFavorite(e, doc)}
                    className={`p-1.5 rounded-lg transition-all cursor-pointer ${
                      doc.is_favorite
                        ? "text-amber-500 hover:bg-amber-500/15"
                        : "text-muted-foreground/30 hover:text-amber-500 hover:bg-secondary"
                    }`}
                    title={doc.is_favorite ? "Starred Favorite" : "Mark as favorite"}
                  >
                    <Star
                      size={18}
                      className={doc.is_favorite ? "fill-amber-400 text-amber-500" : ""}
                    />
                  </button>

                  {/* 3-Dots Action Button */}
                  <div className="relative">
                    <button
                      type="button"
                      data-menu-trigger={doc.id}
                      aria-label={`Actions for ${doc.title}`}
                      aria-haspopup="menu"
                      aria-expanded={openMenuId === doc.id}
                      className="text-muted-foreground hover:text-foreground hover:bg-secondary p-1.5 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        setOpenMenuId((prev) => (prev === doc.id ? null : doc.id));
                      }}
                      title="More actions"
                    >
                      <MoreVertical size={18} />
                    </button>

                    {/* 3-Dots Dropdown Menu */}
                    {openMenuId === doc.id && (
                      <div
                        role="menu"
                        data-menu-dropdown={doc.id}
                        aria-label={`Actions for ${doc.title}`}
                        className="absolute right-0 mt-2 w-48 bg-card border border-border rounded-xl shadow-xl overflow-hidden z-20 py-1 animate-in fade-in zoom-in-95 duration-150"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {/* 1. Star / Favorite Option */}
                        <button
                          type="button"
                          role="menuitem"
                          onClick={(e) => handleToggleFavorite(e, doc)}
                          className="w-full flex items-center gap-2.5 text-left px-3.5 py-2.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors cursor-pointer"
                        >
                          <Star
                            size={14}
                            className={doc.is_favorite ? "fill-amber-400 text-amber-500" : "text-muted-foreground"}
                          />
                          <span>{doc.is_favorite ? "Unmark Favorite" : "Mark as Favorite"}</span>
                        </button>

                        {/* 2. Edit Book Card Option */}
                        <button
                          type="button"
                          role="menuitem"
                          onClick={(e) => openEdit(e, doc)}
                          className="w-full flex items-center gap-2.5 text-left px-3.5 py-2.5 text-xs font-medium text-foreground hover:bg-secondary transition-colors cursor-pointer"
                        >
                          <Pencil size={14} className="text-muted-foreground" />
                          <span>Edit Details</span>
                        </button>

                        <div className="h-px bg-border my-1" />

                        {/* 3. Delete Book Card Option */}
                        <button
                          type="button"
                          role="menuitem"
                          onClick={(e) => openDelete(e, doc)}
                          className="w-full flex items-center gap-2.5 text-left px-3.5 py-2.5 text-xs font-medium text-destructive hover:bg-destructive/10 transition-colors cursor-pointer"
                        >
                          <Trash2 size={14} />
                          <span>Delete Book</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Card Body */}
              <div className="flex-1 mb-6">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-lg line-clamp-1 flex-1" title={doc.title}>
                    {doc.title}
                  </h3>
                  {doc.is_favorite && (
                    <span className="shrink-0 inline-flex items-center gap-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-md border border-amber-500/20">
                      <Star size={10} className="fill-amber-400 text-amber-500" /> Favorite
                    </span>
                  )}
                </div>

                {doc.author && <p className="text-sm text-muted-foreground mb-3">{doc.author}</p>}

                <div className="flex flex-wrap gap-2 text-xs font-medium text-muted-foreground mt-2">
                  <span className="capitalize bg-secondary px-2 py-1 rounded-md">
                    {doc.document_type.replace("_", " ")}
                  </span>
                  {doc.processing?.pages && (
                    <span className="bg-secondary px-2 py-1 rounded-md">{doc.processing.pages} pages</span>
                  )}
                  {doc.status !== "ready" && (
                    <span className="bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300 px-2 py-1 rounded-md capitalize">
                      {doc.status}
                    </span>
                  )}
                </div>
              </div>

              {/* Card Footer */}
              <div className="flex items-center justify-between mt-auto pt-4 border-t border-border">
                <span className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(doc.updated_at), { addSuffix: true })}
                </span>

                {doc.status === "ready" ? (
                  <button
                    onClick={() => router.push(`/documents/${doc.id}/chat`)}
                    className="text-sm font-medium text-primary hover:underline flex items-center gap-1 cursor-pointer"
                  >
                    Open Chat
                  </button>
                ) : (
                  <button
                    onClick={() => router.push(`/documents/${doc.id}/processing`)}
                    className="text-sm font-medium text-muted-foreground hover:underline cursor-pointer"
                  >
                    View Status
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showUpload && (
        <UploadModal
          onClose={() => setShowUpload(false)}
          onSuccess={() => fetchDocuments()}
        />
      )}

      {/* Edit Document Dialog */}
      {editingDocument && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => !isSavingEdit && setEditingDocument(null)}
        >
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-document-title"
            onSubmit={handleSaveEdit}
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
                  <Pencil size={16} />
                </div>
                <h2 id="edit-document-title" className="text-base font-semibold">
                  Edit Book Details
                </h2>
              </div>
              <button
                type="button"
                aria-label="Close edit dialog"
                onClick={() => setEditingDocument(null)}
                disabled={isSavingEdit}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary disabled:opacity-50 cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4 p-5">
              <div className="space-y-1.5">
                <label htmlFor="document-title" className="text-xs font-semibold text-foreground/80">
                  Book Title <span className="text-destructive">*</span>
                </label>
                <input
                  id="document-title"
                  autoFocus
                  maxLength={500}
                  value={editTitle}
                  onChange={(event) => setEditTitle(event.target.value)}
                  placeholder="Enter book title"
                  className="w-full rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="document-author" className="text-xs font-semibold text-foreground/80">
                  Author Name (optional)
                </label>
                <input
                  id="document-author"
                  maxLength={300}
                  value={editAuthor}
                  onChange={(event) => setEditAuthor(event.target.value)}
                  placeholder="e.g. Carl Jung, Richard Feynman"
                  className="w-full rounded-xl border border-input bg-background px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              {editError && (
                <p role="alert" className="text-xs text-destructive">
                  {editError}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 border-t border-border px-5 py-4">
              <button
                type="button"
                onClick={() => setEditingDocument(null)}
                disabled={isSavingEdit}
                className="rounded-xl px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-secondary disabled:opacity-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSavingEdit}
                className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 cursor-pointer shadow-sm"
              >
                {isSavingEdit && <Loader2 size={13} className="animate-spin" />}
                Save Changes
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Delete Document Confirmation Dialog */}
      {deletingDocument && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs animate-in fade-in duration-150"
          onClick={() => !isDeleting && setDeletingDocument(null)}
        >
          <section
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-document-title"
            aria-describedby="delete-document-description"
            onClick={(event) => event.stopPropagation()}
            className="w-full max-w-md rounded-2xl border border-destructive/20 bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <div className="flex items-center gap-2 text-destructive">
                <div className="p-1.5 rounded-lg bg-destructive/10">
                  <Trash2 size={16} />
                </div>
                <h2 id="delete-document-title" className="text-base font-semibold">
                  Delete Book Card?
                </h2>
              </div>
              <button
                type="button"
                aria-label="Close delete dialog"
                onClick={() => setDeletingDocument(null)}
                disabled={isDeleting}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-secondary disabled:opacity-50 cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            <div className="space-y-3 p-5">
              <p id="delete-document-description" className="text-sm text-muted-foreground leading-relaxed">
                Are you sure you want to permanently delete{" "}
                <strong className="text-foreground font-semibold">&quot;{deletingDocument.title}&quot;</strong>?
              </p>
              <p className="text-xs text-muted-foreground/80">
                This will delete the book from your library, remove its indexed pages, and clear all notes and chat history. This action cannot be undone.
              </p>
              {deleteError && (
                <p role="alert" className="text-xs text-destructive">
                  {deleteError}
                </p>
              )}
            </div>

            <div className="flex justify-end gap-2 border-t border-border px-5 py-4">
              <button
                type="button"
                onClick={() => setDeletingDocument(null)}
                disabled={isDeleting}
                className="rounded-xl px-4 py-2 text-xs font-medium text-muted-foreground hover:bg-secondary disabled:opacity-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={isDeleting}
                className="flex items-center gap-2 rounded-xl bg-destructive px-4 py-2 text-xs font-medium text-destructive-foreground hover:opacity-90 disabled:opacity-50 cursor-pointer shadow-sm"
              >
                {isDeleting && <Loader2 size={13} className="animate-spin" />}
                Delete Book
              </button>
            </div>
          </section>
        </div>
      )}

      {/* Toast Notification */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`fixed bottom-6 left-4 right-4 sm:left-auto sm:right-6 sm:max-w-md z-50 flex items-center gap-3 px-4 py-3 rounded-2xl shadow-2xl border text-xs font-medium animate-in fade-in slide-in-from-bottom-5 duration-200 backdrop-blur-md ${
            toast.type === "success"
              ? "bg-card border-emerald-500/30 text-foreground"
              : "bg-destructive text-destructive-foreground border-destructive/40"
          }`}
        >
          <div
            className={`h-6 w-6 rounded-full flex items-center justify-center shrink-0 ${
              toast.type === "success"
                ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                : "bg-white/20 text-white"
            }`}
          >
            <Check size={14} strokeWidth={2.5} />
          </div>
          <span>{toast.message}</span>
          <button
            onClick={() => setToast(null)}
            className="p-1 rounded-md hover:bg-secondary/60 text-muted-foreground hover:text-foreground ml-1 cursor-pointer"
          >
            <X size={13} />
          </button>
        </div>
      )}
    </main>
  );
}
