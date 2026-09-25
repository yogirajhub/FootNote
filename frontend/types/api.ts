export type DocumentType = 'book' | 'research_paper' | 'report' | 'study_material' | 'notes' | 'documentation' | 'article' | 'manual' | 'other';
export type DocumentStatus = 'uploading' | 'queued' | 'processing' | 'ready' | 'failed';

export interface FileInfo {
  filename: string;
  format: string;
  size: number;
}

export interface ProcessingInfo {
  pages?: number;
  chunks?: number;
  embedding_model?: string;
  processed_at?: string;
}

export interface DocumentResponse {
  id: string;
  user_id: string;
  title: string;
  author?: string;
  description?: string;
  document_type: DocumentType;
  file: FileInfo;
  status: DocumentStatus;
  processing?: ProcessingInfo;
  created_at: string;
  updated_at: string;
}

export interface ProcessingJobResponse {
  job_id: string;
  document_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  current_stage?: string;
  progress: number;
  pages_processed: number;
  chunks_created: number;
  embeddings_created: number;
  error?: string;
}

export interface SectionResponse {
  id: string;
  document_id: string;
  title: string;
  level: number;
  parent_id?: string;
  page?: number;
  order: number;
}

export interface PageResponse {
  page: number;
  total_pages: number;
  content: string;
  headings: string[];
}

// ── Evidence & Panels ──────────────────────────────────────────────────────────

export interface Evidence {
  quote: string;
  page?: number;
  chapter?: string;
  section?: string;
  line_start?: number;
  line_end?: number;
  char_start?: number;
  char_end?: number;
  verified: boolean;
}

export interface Panels {
  simple?: string;
  example?: string;
}

// ── Messages ──────────────────────────────────────────────────────────────────

export interface SourceLocation {
  document_id: string;
  document_title: string;
  chapter?: string;
  section?: string;
  page?: number;
  chunk_id?: string;
}

export interface PassageResponse {
  chunk_id: string;
  content: string;
  source: SourceLocation;
  relevance_score?: number;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  passages?: PassageResponse[];
  evidence?: Evidence;
  panels?: Panels;
  intent?: string;
  detail?: boolean;
  fallback?: boolean;
  fallback_reason?: string;
  suggestions?: string[];
  disclaimer?: string;
  selection?: string;
  created_at: string;
}

export interface ConversationResponse {
  id: string;
  user_id: string;
  document_id: string;
  title?: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatRequest {
  document_id: string;
  message: string;
  conversation_id?: string;
  selected_text?: string;
  selected_page?: number;
  detail?: boolean;
  mode?: 'document' | 'library';
  document_ids?: string[];
}

export interface ChatResponse {
  conversation_id: string;
  message: MessageResponse;
  intent: string;
  processing_time_ms?: number;
}

// ── SSE Stream Events ──────────────────────────────────────────────────────────

export interface SSEMetadata {
  type: 'metadata';
  intent: string;
  rewritten_query: string;
}

export interface SSEDelta {
  type: 'delta';
  content: string;
}

export interface SSEDone {
  type: 'done';
  processing_time_ms: number;
  timings?: Record<string, number>;
}

export interface SSEError {
  type: 'error';
  message: string;
}

export type SSEEvent = SSEMetadata | SSEDelta | SSEDone | SSEError;

// ── Notes ─────────────────────────────────────────────────────────────────────

export interface NoteResponse {
  id: string;
  document_id: string;
  content: string;
  page?: number;
  source: 'selection' | 'answer' | 'manual';
  created_at: string;
  updated_at: string;
}

export interface NoteCreateRequest {
  document_id: string;
  content: string;
  page?: number;
  source?: string;
}
