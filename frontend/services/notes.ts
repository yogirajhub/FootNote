import { api } from './api';
import type { NoteResponse, NoteCreateRequest } from '../types/api';

export const notesService = {
  async create(note: NoteCreateRequest): Promise<NoteResponse> {
    const { data } = await api.post<NoteResponse>('/notes', note);
    return data;
  },

  async list(documentId?: string): Promise<{ notes: NoteResponse[]; total: number }> {
    const { data } = await api.get<{ notes: NoteResponse[]; total: number }>('/notes', {
      params: documentId ? { document_id: documentId } : undefined,
    });
    return data;
  },

  async update(noteId: string, content: string): Promise<NoteResponse> {
    const { data } = await api.patch<NoteResponse>(`/notes/${noteId}`, { content });
    return data;
  },

  async delete(noteId: string): Promise<void> {
    await api.delete(`/notes/${noteId}`);
  },
};
