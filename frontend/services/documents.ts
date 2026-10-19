import { api } from './api';
import type { DocumentResponse, ProcessingJobResponse, SectionResponse, PageResponse, DocumentPageContent } from '../types/api';

export const documentsService = {
  async upload(
    formData: FormData,
    onProgress?: (progress: { percent: number; loaded: number; total: number }) => void
  ): Promise<DocumentResponse> {
    const { data } = await api.post<DocumentResponse>('/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress({ percent, loaded: progressEvent.loaded, total: progressEvent.total });
        }
      },
    });
    return data;
  },

  async list(skip = 0, limit = 20) {
    const { data } = await api.get<{ documents: DocumentResponse[]; total: number }>('/documents', {
      params: { skip, limit },
    });
    return data;
  },

  async get(id: string): Promise<DocumentResponse> {
    const { data } = await api.get<DocumentResponse>(`/documents/${id}`);
    return data;
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/documents/${id}`);
  },

  async update(id: string, updates: Partial<DocumentResponse>): Promise<DocumentResponse> {
    const { data } = await api.patch<DocumentResponse>(`/documents/${id}`, updates);
    return data;
  },

  async getStatus(id: string): Promise<ProcessingJobResponse> {
    const { data } = await api.get<ProcessingJobResponse>(`/documents/${id}/status`);
    return data;
  },

  async getSections(id: string): Promise<{ sections: SectionResponse[] }> {
    const { data } = await api.get<{ sections: SectionResponse[] }>(`/documents/${id}/sections`);
    return data;
  },

  async getPage(id: string, page: number): Promise<PageResponse> {
    const { data } = await api.get<PageResponse>(`/documents/${id}/pages/${page}`);
    return data;
  },

  async listPages(id: string): Promise<{ total_pages: number; pages: DocumentPageContent[] }> {
    const { data } = await api.get<{ total_pages: number; pages: DocumentPageContent[] }>(`/documents/${id}/pages`);
    return data;
  },

  async getFile(id: string): Promise<Blob> {
    const { data } = await api.get<Blob>(`/documents/${id}/file`, { responseType: "blob" });
    return data;
  },
};
