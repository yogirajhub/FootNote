import { api } from './api';
import type { ChatResponse, ConversationResponse, MessageResponse } from '../types/api';

export const chatService = {
  async sendMessage(
    documentId: string,
    message: string,
    conversationId?: string,
    mode: 'document' | 'library' = 'document',
    documentIds?: string[]
  ): Promise<ChatResponse> {
    const { data } = await api.post<ChatResponse>('/chat', {
      document_id: documentId,
      message,
      conversation_id: conversationId,
      mode,
      document_ids: documentIds,
    });
    return data;
  },

  async listConversations(documentId?: string) {
    const { data } = await api.get<{ conversations: ConversationResponse[]; total: number }>('/conversations', {
      params: { document_id: documentId },
    });
    return data;
  },

  async getConversation(id: string) {
    const { data } = await api.get<{ conversation: ConversationResponse; messages: MessageResponse[] }>(
      `/conversations/${id}`
    );
    return data;
  },
};
