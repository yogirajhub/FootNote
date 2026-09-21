import { api } from './api';
import type { DocumentResponse, ProcessingJobResponse, SectionResponse } from '../types/api';

export const documentsService = {
  async upload(formData: FormData): Promise<DocumentResponse> {
    const { data } = await api.post<DocumentResponse>('/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
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

  async getStatus(id: string): Promise<ProcessingJobResponse> {
    const { data } = await api.get<ProcessingJobResponse>(`/documents/${id}/status`);
    return data;
  },

  async getSections(id: string): Promise<{ sections: SectionResponse[] }> {
    const { data } = await api.get<{ sections: SectionResponse[] }>(`/documents/${id}/sections`);
    return data;
  },
};
