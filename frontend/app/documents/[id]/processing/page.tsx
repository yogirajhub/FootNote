"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { documentsService } from "@/services/documents";
import type { ProcessingJobResponse, DocumentResponse } from "@/types/api";
import { CheckCircle2, Circle, Loader2, ArrowLeft, AlertCircle } from "lucide-react";
import Link from "next/link";

const STAGES = [
  { id: "upload", label: "File uploaded" },
  { id: "extraction", label: "Text extracted" },
  { id: "structure_detection", label: "Structure detected" },
  { id: "chunking", label: "Content chunked" },
  { id: "embedding", label: "Embeddings generated" },
  { id: "indexing", label: "Vector index created" },
];

export default function ProcessingPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [job, setJob] = useState<ProcessingJobResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      loadData(false);
    }, 2000);

    return () => clearInterval(interval);
  }, [documentId]);

  const loadData = async (initial = true) => {
    try {
      if (initial) {
        const docData = await documentsService.get(documentId);
        setDoc(docData);
      }
      const jobData = await documentsService.getStatus(documentId);
      setJob(jobData);

      if (jobData.status === "completed") {
        router.push(`/documents/${documentId}/chat`);
      }
    } catch (err: any) {
      if (initial) setError(err.message || "Failed to load processing status");
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="bg-destructive/10 text-destructive p-6 rounded-xl max-w-md w-full flex flex-col items-center text-center">
          <AlertCircle className="w-12 h-12 mb-4" />
          <h2 className="text-lg font-semibold mb-2">Processing Error</h2>
          <p className="text-sm mb-6">{error}</p>
          <Link href="/" className="bg-background px-4 py-2 rounded-lg text-sm font-medium hover:bg-muted transition-colors">
            Return to Library
          </Link>
        </div>
      </div>
    );
  }

  if (!doc || !job) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  const getStageStatus = (stageId: string, currentStage?: string, status?: string) => {
    if (status === "failed") return "failed";
    if (status === "completed") return "completed";
    
    const stageIndex = STAGES.findIndex(s => s.id === stageId);
    const currentIndex = STAGES.findIndex(s => s.id === currentStage);
    
    if (stageIndex < currentIndex) return "completed";
    if (stageIndex === currentIndex) return "processing";
    return "pending";
  };

  return (
    <main className="min-h-screen bg-background flex flex-col items-center py-20 px-4">
      <div className="w-full max-w-lg">
        <Link href="/" className="inline-flex items-center text-sm font-medium text-muted-foreground hover:text-foreground mb-8 transition-colors">
          <ArrowLeft size={16} className="mr-2" />
          Back to Library
        </Link>

        <div className="bg-card border border-border rounded-2xl shadow-sm overflow-hidden p-8">
          <div className="mb-8">
            <h1 className="text-2xl font-semibold mb-2">Processing Document</h1>
            <p className="text-muted-foreground line-clamp-1">{doc.file.filename}</p>
          </div>

          <div className="space-y-6 mb-10">
            {STAGES.map((stage) => {
              const status = getStageStatus(stage.id, job.current_stage, job.status);
              
              return (
                <div key={stage.id} className="flex items-center gap-4">
                  {status === "completed" ? (
                    <CheckCircle2 className="w-6 h-6 text-primary" />
                  ) : status === "processing" ? (
                    <Loader2 className="w-6 h-6 text-primary animate-spin" />
                  ) : (
                    <Circle className="w-6 h-6 text-muted" />
                  )}
                  <span className={`font-medium ${
                    status === "completed" ? "text-foreground" :
                    status === "processing" ? "text-primary" : "text-muted-foreground"
                  }`}>
                    {stage.label}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-sm font-medium text-muted-foreground">
              <span>Progress</span>
              <span>{job.progress}%</span>
            </div>
            <div className="w-full bg-secondary rounded-full h-2 overflow-hidden">
              <div 
                className="bg-primary h-full transition-all duration-500 ease-out"
                style={{ width: `${job.progress}%` }}
              />
            </div>
          </div>
          
          {(job.pages_processed > 0 || job.chunks_created > 0) && (
            <div className="mt-6 p-4 bg-secondary/50 rounded-xl grid grid-cols-2 gap-4 text-sm">
              {job.pages_processed > 0 && (
                <div>
                  <span className="block text-muted-foreground mb-1">Pages</span>
                  <span className="font-semibold">{job.pages_processed}</span>
                </div>
              )}
              {job.chunks_created > 0 && (
                <div>
                  <span className="block text-muted-foreground mb-1">Knowledge Chunks</span>
                  <span className="font-semibold">{job.chunks_created}</span>
                </div>
              )}
            </div>
          )}
          
          {job.status === "failed" && (
            <div className="mt-6 p-4 bg-destructive/10 text-destructive rounded-xl text-sm">
              Processing failed: {job.error || "Unknown error"}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
