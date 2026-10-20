"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { documentsService } from "@/services/documents";
import type { ProcessingJobResponse, DocumentResponse } from "@/types/api";
import {
  CheckCircle2,
  Circle,
  Loader2,
  ArrowLeft,
  AlertCircle,
  Trash2,
  Book,
  Sparkles,
  Layers,
  Cpu,
  Database,
  ShieldCheck,
  FileText,
} from "lucide-react";
import Link from "next/link";

const STAGES = [
  {
    id: "upload",
    label: "File uploaded",
    desc: "Document validated and stored securely in local database",
    icon: FileText,
  },
  {
    id: "extraction",
    label: "Text extracted",
    desc: "Extracting raw text and preserving exact page boundaries",
    icon: Book,
  },
  {
    id: "structure_detection",
    label: "Structure detected",
    desc: "Detecting chapters, sections, and document hierarchy",
    icon: Layers,
  },
  {
    id: "chunking",
    label: "Content chunked",
    desc: "Creating semantic chunks with page and section metadata",
    icon: Sparkles,
  },
  {
    id: "embedding",
    label: "Embeddings generated",
    desc: "Computing 384-dim neural vectors with sentence-transformers",
    icon: Cpu,
  },
  {
    id: "indexing",
    label: "Vector index created",
    desc: "Indexing vectors into database for millisecond retrieval",
    icon: Database,
  },
];

export default function ProcessingPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [job, setJob] = useState<ProcessingJobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hasRedirectedRef = useRef(false);

  useEffect(() => {
    let isMounted = true;

    const fetchStatus = async (initial = false) => {
      try {
        if (initial) {
          const docData = await documentsService.get(documentId);
          if (isMounted) setDoc(docData);
        }
        const jobData = await documentsService.getStatus(documentId);
        if (isMounted) {
          setJob(jobData);
          if (jobData.status === "completed" && !hasRedirectedRef.current) {
            hasRedirectedRef.current = true;
            // Short delay so user can see 100% completion
            setTimeout(() => {
              router.push(`/documents/${documentId}/chat`);
            }, 600);
          }
        }
      } catch (err: unknown) {
        if (initial && isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load processing status");
        }
      }
    };

    fetchStatus(true);
    // Poll every 1000ms for fast real-time feedback
    const interval = setInterval(() => {
      fetchStatus(false);
    }, 1000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [documentId, router]);

  const handleDelete = async () => {
    if (confirm("Are you sure you want to cancel and delete this document?")) {
      try {
        await documentsService.delete(documentId);
        router.push("/");
      } catch {
        setError("Failed to delete document");
      }
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-background">
        <div className="bg-destructive/10 border border-destructive/20 text-destructive p-8 rounded-2xl max-w-md w-full flex flex-col items-center text-center shadow-lg">
          <AlertCircle className="w-12 h-12 mb-4 text-destructive" />
          <h2 className="text-lg font-semibold mb-2">Processing Error</h2>
          <p className="text-xs mb-6 text-muted-foreground leading-relaxed">{error}</p>
          <Link
            href="/"
            className="bg-primary text-primary-foreground px-5 py-2.5 rounded-xl text-xs font-semibold hover:bg-primary/90 transition-colors shadow-sm"
          >
            Return to Library
          </Link>
        </div>
      </div>
    );
  }

  if (!doc || !job) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-xs text-muted-foreground font-medium">Connecting to knowledge engine...</p>
      </div>
    );
  }

  const getStageStatus = (stageId: string, currentStage?: string, status?: string) => {
    if (status === "failed") return "failed";
    if (status === "completed") return "completed";

    const stageIndex = STAGES.findIndex((s) => s.id === stageId);
    const currentIndex = STAGES.findIndex((s) => s.id === currentStage);

    if (currentIndex === -1) {
      return stageIndex === 0 ? "completed" : "pending";
    }

    if (stageIndex < currentIndex) return "completed";
    if (stageIndex === currentIndex) return "processing";
    return "pending";
  };

  const getStageDetail = (stageId: string) => {
    if (stageId === "extraction" && job.pages_processed > 0) {
      return `${job.pages_processed} pages extracted`;
    }
    if (stageId === "chunking" && job.chunks_created > 0) {
      return `${job.chunks_created} semantic chunks`;
    }
    if (stageId === "embedding" && job.embeddings_created > 0) {
      return `${job.embeddings_created} neural vectors`;
    }
    return null;
  };

  return (
    <main className="min-h-screen bg-background flex flex-col items-center py-12 md:py-20 px-4">
      <div className="w-full max-w-xl">
        <Link
          href="/"
          className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground mb-6 transition-colors group"
        >
          <ArrowLeft size={16} className="mr-1.5 transition-transform group-hover:-translate-x-1" />
          Back to Library
        </Link>

        <div className="bg-card border border-border rounded-2xl shadow-xl overflow-hidden p-6 sm:p-8 space-y-6">
          {/* Header */}
          <div className="flex justify-between items-start gap-4 pb-6 border-b border-border/80">
            <div className="min-w-0 flex-1">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-[11px] font-semibold mb-2">
                <Sparkles size={12} />
                <span>Building Knowledge Base</span>
              </div>
              <h1 className="text-xl font-bold text-foreground truncate" title={doc.title}>
                {doc.title}
              </h1>
              <p className="text-xs text-muted-foreground truncate mt-0.5">
                {doc.file.filename} • {doc.author || "Unknown Author"}
              </p>
            </div>
            <button
              onClick={handleDelete}
              className="p-2 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl transition-colors shrink-0 cursor-pointer"
              title="Cancel & Delete"
            >
              <Trash2 size={18} />
            </button>
          </div>

          {/* Progress Bar & Percentage */}
          <div className="space-y-2">
            <div className="flex justify-between items-center text-xs font-semibold">
              <span className="text-muted-foreground">Overall Progress</span>
              <span className="font-mono text-primary text-sm font-bold">{job.progress}%</span>
            </div>
            <div className="w-full bg-secondary rounded-full h-2.5 overflow-hidden p-0.5 border border-border/50">
              <div
                className="bg-primary h-full rounded-full transition-all duration-500 ease-out shadow-xs"
                style={{ width: `${Math.max(job.progress, 5)}%` }}
              />
            </div>
          </div>

          {/* Live Metric Counters */}
          {(job.pages_processed > 0 || job.chunks_created > 0 || job.embeddings_created > 0) && (
            <div className="grid grid-cols-3 gap-3 p-3.5 bg-secondary/40 border border-border/60 rounded-xl text-center animate-in fade-in">
              <div>
                <span className="block text-[11px] font-medium text-muted-foreground mb-0.5">Pages</span>
                <span className="text-base font-bold text-foreground font-mono">
                  {job.pages_processed || "—"}
                </span>
              </div>
              <div>
                <span className="block text-[11px] font-medium text-muted-foreground mb-0.5">Chunks</span>
                <span className="text-base font-bold text-foreground font-mono">
                  {job.chunks_created || "—"}
                </span>
              </div>
              <div>
                <span className="block text-[11px] font-medium text-muted-foreground mb-0.5">Embeddings</span>
                <span className="text-base font-bold text-primary font-mono">
                  {job.embeddings_created || "—"}
                </span>
              </div>
            </div>
          )}

          {/* Processing Stages Checklist */}
          <div className="space-y-4 pt-2">
            {STAGES.map((stage) => {
              const status = getStageStatus(stage.id, job.current_stage, job.status);
              const detail = getStageDetail(stage.id);

              return (
                <div
                  key={stage.id}
                  className={`flex items-start gap-3.5 p-3 rounded-xl transition-colors ${
                    status === "processing"
                      ? "bg-primary/5 border border-primary/20 shadow-2xs"
                      : "bg-transparent"
                  }`}
                >
                  <div className="shrink-0 mt-0.5">
                    {status === "completed" ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-500" />
                    ) : status === "processing" ? (
                      <Loader2 className="w-5 h-5 text-primary animate-spin" />
                    ) : (
                      <Circle className="w-5 h-5 text-muted-foreground/30" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-semibold ${
                          status === "completed"
                            ? "text-foreground"
                            : status === "processing"
                            ? "text-primary font-bold"
                            : "text-muted-foreground"
                        }`}
                      >
                        {stage.label}
                      </span>
                      {detail && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold">
                          {detail}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-muted-foreground leading-normal mt-0.5">
                      {stage.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Failure Banner */}
          {job.status === "failed" && (
            <div className="p-4 bg-destructive/10 border border-destructive/20 text-destructive rounded-xl text-xs space-y-1">
              <span className="font-semibold block">Processing Failed</span>
              <span>{job.error || "An unexpected error occurred during document parsing."}</span>
            </div>
          )}

          {/* Quality Guarantee Note */}
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-muted/30 border border-border/50 text-muted-foreground text-[11px]">
            <ShieldCheck size={16} className="text-emerald-500 shrink-0" />
            <span>
              FootNote indexes exact page coordinates and chapter hierarchies so every answer cites its source.
            </span>
          </div>
        </div>
      </div>
    </main>
  );
}
