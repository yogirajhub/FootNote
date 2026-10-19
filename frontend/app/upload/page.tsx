"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { UploadModal } from "@/components/upload/UploadModal";

export default function UploadPage() {
  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center p-4 sm:p-8 md:p-12">
      <div className="w-full max-w-2xl mb-6">
        <Link
          href="/"
          className="inline-flex items-center text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors group"
        >
          <ArrowLeft size={16} className="mr-1.5 transition-transform group-hover:-translate-x-1" />
          Back to Library
        </Link>
      </div>

      <UploadModal onClose={() => {}} isPage={true} />
    </main>
  );
}
