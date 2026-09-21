"use client";

import { useEffect, useState } from "react";
import { documentsService } from "@/services/documents";
import type { DocumentResponse } from "@/types/api";
import { UploadModal } from "@/components/upload/UploadModal";
import { Book, FileText, File, MoreVertical, Plus, Loader2 } from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { useRouter } from "next/navigation";

export default function Home() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const router = useRouter();

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const data = await documentsService.list();
      setDocuments(data.documents);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setLoading(false);
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

  return (
    <main className="min-h-screen p-8 md:p-12 lg:p-24 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-12 gap-6">
        <div>
          <h1 className="text-4xl font-bold tracking-tight mb-2 text-primary">FootNote</h1>
          <p className="text-muted-foreground text-lg">Turn every document into a conversation.</p>
        </div>
        <button
          onClick={() => setShowUpload(true)}
          className="bg-primary text-primary-foreground px-6 py-3 rounded-xl font-medium shadow-sm hover:shadow-md hover:bg-primary/90 transition-all flex items-center gap-2"
        >
          <Plus size={20} />
          Add Document
        </button>
      </div>

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
            className="text-primary font-medium hover:underline"
          >
            Upload your first document
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="group bg-card border border-border rounded-2xl p-6 shadow-sm hover:shadow-md transition-all flex flex-col"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="p-3 bg-secondary/50 rounded-xl">{getIcon(doc.document_type)}</div>
                <button className="text-muted-foreground hover:text-foreground p-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <MoreVertical size={18} />
                </button>
              </div>

              <div className="flex-1 mb-6">
                <h3 className="font-semibold text-lg line-clamp-1 mb-1" title={doc.title}>
                  {doc.title}
                </h3>
                {doc.author && <p className="text-sm text-muted-foreground mb-3">{doc.author}</p>}
                
                <div className="flex flex-wrap gap-2 text-xs font-medium text-muted-foreground">
                  <span className="capitalize bg-secondary px-2 py-1 rounded-md">{doc.document_type.replace('_', ' ')}</span>
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

              <div className="flex items-center justify-between mt-auto pt-4 border-t border-border">
                <span className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(doc.updated_at), { addSuffix: true })}
                </span>
                
                {doc.status === "ready" ? (
                  <button
                    onClick={() => router.push(`/documents/${doc.id}/chat`)}
                    className="text-sm font-medium text-primary hover:underline flex items-center gap-1"
                  >
                    Open Chat
                  </button>
                ) : (
                  <button
                    onClick={() => router.push(`/documents/${doc.id}/processing`)}
                    className="text-sm font-medium text-muted-foreground hover:underline"
                  >
                    View Status
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} />}
    </main>
  );
}
