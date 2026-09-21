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
  intent?: string;
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

export interface ChatResponse {
  conversation_id: string;
  message: MessageResponse;
  passages: PassageResponse[];
  intent: string;
  processing_time_ms?: number;
}
