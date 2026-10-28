"use client";

import { useState, useCallback, useId } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  FileText,
  X,
  Book,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  File,
  User,
  Tag,
  ArrowRight,
  RefreshCw,
  Trash2,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { documentsService } from "@/services/documents";
import { useRouter } from "next/navigation";

interface UploadModalProps {
  onClose: () => void;
  onSuccess?: () => void;
  isPage?: boolean;
}

const DOCUMENT_TYPES = [
  { id: "book", label: "Book", icon: Book, desc: "Textbooks, non-fiction, novels" },
  { id: "research_paper", label: "Research Paper", icon: FileText, desc: "Journals, arXiv, papers" },
  { id: "report", label: "Report", icon: FileText, desc: "Business & technical reports" },
  { id: "documentation", label: "Documentation", icon: FileText, desc: "Manuals & software guides" },
  { id: "other", label: "Notes / Other", icon: Tag, desc: "Personal notes, drafts, articles" },
];

const SUPPORTED_FORMATS = [
  { ext: "PDF", bg: "bg-red-500/10 text-red-500 border-red-500/20" },
  { ext: "EPUB", bg: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20" },
  { ext: "DOCX", bg: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  { ext: "TXT", bg: "bg-amber-500/10 text-amber-500 border-amber-500/20" },
  { ext: "MD", bg: "bg-purple-500/10 text-purple-500 border-purple-500/20" },
];

function cleanTitleFromFilename(filename: string): string {
  const base = filename.replace(/\.[^/.]+$/, "");
  const spaced = base.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  if (spaced.length > 0) {
    return spaced
      .split(" ")
      .map((word) => (word.length > 0 ? word.charAt(0).toUpperCase() + word.slice(1) : ""))
      .join(" ");
  }
  return base;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

export function UploadModal({ onClose, onSuccess, isPage = false }: UploadModalProps) {
  const router = useRouter();
  const fileInputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [description, setDescription] = useState("");
  const [docType, setDocType] = useState("book");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{
    percent: number;
    loaded: number;
    total: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
    if (fileRejections.length > 0) {
      setError("Please select a supported document file (PDF, EPUB, DOCX, TXT, MD) under 50 MB.");
      return;
    }
    if (acceptedFiles.length > 0) {
      const selected = acceptedFiles[0];
      if (selected.size > 50 * 1024 * 1024) {
        setError("File size exceeds 50 MB limit. Please select a smaller document.");
        return;
      }
      setFile(selected);
      setTitle(cleanTitleFromFilename(selected.name));
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    maxFiles: 1,
    noClick: !!file, // disable dropzone click if file is already picked
    accept: {
      "application/pdf": [".pdf"],
      "application/epub+zip": [".epub"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
      "text/markdown": [".md"],
    },
    maxSize: 50 * 1024 * 1024,
  });

  const handleUpload = async () => {
    if (!file || !title.trim()) {
      setError("Please select a file and provide a document title.");
      return;
    }

    setIsUploading(true);
    setError(null);
    setUploadProgress({ percent: 0, loaded: 0, total: file.size });

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title.trim());
      if (author.trim()) formData.append("author", author.trim());
      if (description.trim()) formData.append("description", description.trim());
      formData.append("document_type", docType);

      const doc = await documentsService.upload(formData, ({ percent, loaded, total }) => {
        setUploadProgress({ percent, loaded, total });
      });

      if (onSuccess) onSuccess();
      router.push(`/documents/${doc.id}/processing`);
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || "Upload failed. Please try again.";
      setError(msg);
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  const getFileExtension = (name: string) => {
    const parts = name.split(".");
    return parts.length > 1 ? parts[parts.length - 1].toUpperCase() : "FILE";
  };

  const content = (
    <div
      className={`bg-card border border-border/80 shadow-2xl rounded-2xl overflow-hidden transition-all duration-200 ${isPage ? "max-w-2xl w-full" : "w-full max-w-xl max-h-[92vh] flex flex-col animate-in fade-in zoom-in-95 duration-200"
        }`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-5 border-b border-border bg-muted/20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h2 id="upload-modal-title" className="text-xl font-semibold tracking-tight text-foreground">
              Add New Document
            </h2>
            <p className="text-xs text-muted-foreground">
              Build an interactive knowledge base with page-level citations
            </p>
          </div>
        </div>
        {!isPage && (
          <button
            onClick={onClose}
            disabled={isUploading}
            className="text-muted-foreground hover:text-foreground p-1.5 rounded-lg hover:bg-secondary transition-colors cursor-pointer disabled:opacity-50"
            title="Close"
          >
            <X size={18} />
          </button>
        )}
      </div>

      <div className="p-6 space-y-5 overflow-y-auto flex-1">
        {/* Dropzone or File Preview */}
        {!file ? (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 group ${isDragActive
                ? "border-primary bg-primary/10 scale-[1.01]"
                : "border-border/80 hover:border-primary/50 hover:bg-muted/30"
              }`}
          >
            <input {...getInputProps()} id={fileInputId} />
            <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-secondary/80 flex items-center justify-center text-primary group-hover:scale-105 transition-transform duration-200 shadow-xs">
              <Upload className="h-7 w-7" />
            </div>
            <p className="text-sm font-semibold text-foreground mb-1">
              Drag & Drop your document here, or <span className="text-primary hover:underline">browse files</span>
            </p>
            <p className="text-xs text-muted-foreground mb-4">
              Maximum file size: 50 MB • Instant local semantic indexing
            </p>
            {/* Format Pills */}
            <div className="flex flex-wrap items-center justify-center gap-1.5 pt-1">
              {SUPPORTED_FORMATS.map((f) => (
                <span
                  key={f.ext}
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-md border ${f.bg}`}
                >
                  {f.ext}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <div className="bg-secondary/40 border border-border/80 p-4 rounded-xl flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex flex-col items-center justify-center text-primary shrink-0">
              <FileText className="h-6 w-6" />
              <span className="text-[9px] font-bold tracking-wider mt-0.5">
                {getFileExtension(file.name)}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-foreground truncate" title={file.name}>
                {file.name}
              </p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-muted-foreground font-mono">{formatBytes(file.size)}</span>
                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                  <CheckCircle2 size={12} />
                  Ready to process
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={open}
                disabled={isUploading}
                className="text-xs text-primary hover:underline px-2 py-1 rounded hover:bg-primary/10 transition-colors cursor-pointer disabled:opacity-50"
              >
                Change
              </button>
              <button
                type="button"
                onClick={() => setFile(null)}
                disabled={isUploading}
                className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg transition-colors cursor-pointer disabled:opacity-50"
                title="Remove file"
              >
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="flex items-start gap-2.5 text-sm text-destructive bg-destructive/10 border border-destructive/20 p-3.5 rounded-xl animate-in fade-in">
            <AlertCircle size={18} className="shrink-0 mt-0.5" />
            <div className="flex-1 text-xs leading-relaxed">{error}</div>
            <button
              onClick={() => setError(null)}
              className="text-destructive/80 hover:text-destructive cursor-pointer"
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Form fields */}
        <div className="space-y-4">
          {/* Document Title */}
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Document Title <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-background border border-border rounded-xl px-3.5 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all placeholder:text-muted-foreground"
              placeholder="E.g., Thinking, Fast and Slow"
              disabled={isUploading}
              required
            />
          </div>

          {/* Author */}
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5 flex items-center justify-between">
              <span>Author</span>
              <span className="text-[11px] font-normal text-muted-foreground">Optional</span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                className="w-full bg-background border border-border rounded-xl pl-9 pr-3.5 py-2.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all placeholder:text-muted-foreground"
                placeholder="E.g., Daniel Kahneman"
                disabled={isUploading}
              />
              <User size={15} className="absolute left-3 top-3 text-muted-foreground pointer-events-none" />
            </div>
          </div>

          {/* Document Type Selector - Interactive chips */}
          <div>
            <label className="block text-xs font-semibold text-foreground mb-1.5">
              Document Category
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {DOCUMENT_TYPES.map((t) => {
                const Icon = t.icon;
                const isSelected = docType === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setDocType(t.id)}
                    disabled={isUploading}
                    className={`flex items-center gap-2 p-2.5 rounded-xl border text-left transition-all cursor-pointer ${isSelected
                        ? "bg-primary/10 border-primary text-primary font-semibold shadow-2xs ring-1 ring-primary/40"
                        : "bg-background border-border/80 text-muted-foreground hover:text-foreground hover:bg-muted/40"
                      }`}
                  >
                    <Icon size={16} className={isSelected ? "text-primary" : "text-muted-foreground"} />
                    <span className="text-xs truncate">{t.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Upload Progress Bar */}
        {isUploading && (
          <div className="p-4 rounded-xl bg-primary/5 border border-primary/20 space-y-2 animate-in fade-in duration-200">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-primary flex items-center gap-2">
                <RefreshCw size={14} className="animate-spin text-primary" />
                {uploadProgress && uploadProgress.percent >= 100
                  ? "Finalizing document transfer..."
                  : "Uploading document..."}
              </span>
              <span className="font-mono text-muted-foreground font-semibold">
                {uploadProgress ? `${uploadProgress.percent}%` : "Preparing..."}
              </span>
            </div>
            <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
              <div
                className="bg-primary h-full transition-all duration-300 ease-out"
                style={{ width: `${uploadProgress?.percent ?? 15}%` }}
              />
            </div>
            {uploadProgress && uploadProgress.total > 0 && (
              <div className="flex justify-between text-[11px] text-muted-foreground">
                <span>{formatBytes(uploadProgress.loaded)} uploaded</span>
                <span>{formatBytes(uploadProgress.total)}</span>
              </div>
            )}
          </div>
        )}

        {/* Feature Highlights */}
        <div className="grid grid-cols-3 gap-2 pt-1 border-t border-border/60 text-center">
          <div className="flex flex-col items-center gap-1 p-2 rounded-lg bg-muted/20">
            <Zap size={14} className="text-primary" />
            <span className="text-[10px] font-medium text-muted-foreground">Fast Ingestion</span>
          </div>
          <div className="flex flex-col items-center gap-1 p-2 rounded-lg bg-muted/20">
            <ShieldCheck size={14} className="text-emerald-500" />
            <span className="text-[10px] font-medium text-muted-foreground">100% Private</span>
          </div>
          <div className="flex flex-col items-center gap-1 p-2 rounded-lg bg-muted/20">
            <Sparkles size={14} className="text-accent" />
            <span className="text-[10px] font-medium text-muted-foreground">Page Citations</span>
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="p-5 border-t border-border bg-muted/20 flex items-center justify-between gap-3 shrink-0">
        {!isPage ? (
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-xl text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
            disabled={isUploading}
          >
            Cancel
          </button>
        ) : (
          <button
            type="button"
            onClick={() => router.push("/")}
            className="px-4 py-2.5 rounded-xl text-xs font-semibold text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
            disabled={isUploading}
          >
            Back to Library
          </button>
        )}
        <button
          type="button"
          onClick={handleUpload}
          disabled={!file || !title.trim() || isUploading}
          className="px-6 py-2.5 rounded-xl text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 cursor-pointer shadow-sm hover:shadow-md"
        >
          {isUploading ? (
            <>
              <RefreshCw size={14} className="animate-spin" />
              <span>Processing Upload...</span>
            </>
          ) : (
            <>
              <span>Upload & Build Knowledge Base</span>
              <ArrowRight size={14} />
            </>
          )}
        </button>
      </div>
    </div>
  );

  if (isPage) {
    return content;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isUploading) {
          onClose();
        }
      }}
    >
      {content}
    </div>
  );
}
